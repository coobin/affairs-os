"""读取 xrxs2ldap 写入的 OpenLDAP，并同步到 AffairsOS 本地目录。"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from ldap3 import ALL, Connection, Server, SUBTREE

from .department_directory import (
    DEPARTMENT_MERGE_TARGET,
    allocate_department_code,
    canonical_department_name,
    create_department,
    is_standard_department_code,
)
from .models import Department, EmployeeProfile


logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass(frozen=True, slots=True)
class LdapDepartmentRecord:
    source_id: str
    name: str
    parent_source_id: str | None
    dn: str


@dataclass(frozen=True, slots=True)
class LdapEmployeeRecord:
    uid: str
    display_name: str
    email: str
    employee_number: str
    department_source_id: str | None
    phone: str
    title: str
    active: bool
    dn: str


@dataclass(frozen=True, slots=True)
class LdapSnapshot:
    departments: tuple[LdapDepartmentRecord, ...] = ()
    employees: tuple[LdapEmployeeRecord, ...] = ()


@dataclass(slots=True)
class LdapSyncResult:
    departments_created: int = 0
    departments_updated: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    employees_deactivated: int = 0
    employees_skipped: int = 0
    departments_without_parent: int = 0
    employees_without_department: int = 0
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def as_dict(self) -> dict[str, object]:
        return {
            "departments_created": self.departments_created,
            "departments_updated": self.departments_updated,
            "employees_created": self.employees_created,
            "employees_updated": self.employees_updated,
            "employees_deactivated": self.employees_deactivated,
            "employees_skipped": self.employees_skipped,
            "departments_without_parent": self.departments_without_parent,
            "employees_without_department": self.employees_without_department,
            "warnings": list(self.warnings),
        }


class LdapDirectoryError(RuntimeError):
    """LDAP 配置、连接或目录结构不可用。"""


class LdapDirectoryClient:
    """只读读取 xrxs2ldap 约定的人员条目和部门组。"""

    _PEOPLE_ATTRIBUTES = [
        "uid",
        "cn",
        "displayName",
        "mail",
        "employeeNumber",
        "departmentNumber",
        "employeeType",
        "telephoneNumber",
        "title",
    ]
    _GROUP_ATTRIBUTES = ["cn", "description"]

    def fetch_snapshot(self) -> LdapSnapshot:
        connection = self._connect()
        try:
            departments = tuple(self._fetch_departments(connection))
            employees = tuple(self._fetch_employees(connection))
            if not departments:
                raise LdapDirectoryError(
                    "LDAP 未读取到 xrxs2ldap 管理的部门组，为避免清空本地部门，已拒绝同步。"
                )
            if not employees:
                raise LdapDirectoryError(
                    "LDAP 未读取到人员，为避免清空本地人员，已拒绝同步。"
                )
            return LdapSnapshot(departments=departments, employees=employees)
        finally:
            connection.unbind()

    def _connect(self) -> Connection:
        missing = [
            name
            for name, value in (
                ("LDAP_URI", settings.LDAP_URI),
                ("LDAP_BIND_DN", settings.LDAP_BIND_DN),
                ("LDAP_BIND_PASSWORD", settings.LDAP_BIND_PASSWORD),
            )
            if not value
        ]
        if missing:
            raise LdapDirectoryError(f"LDAP 配置不完整：缺少 {', '.join(missing)}。")

        try:
            server = Server(
                settings.LDAP_URI,
                get_info=ALL,
                connect_timeout=settings.LDAP_CONNECT_TIMEOUT_SECONDS,
            )
            return Connection(
                server,
                user=settings.LDAP_BIND_DN,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True,
                raise_exceptions=True,
            )
        except Exception as exc:  # ldap3 的异常类型随连接阶段不同而不同
            logger.exception("LDAP connection failed")
            raise LdapDirectoryError("LDAP 连接失败，请检查地址、绑定账号和网络。") from exc

    def _fetch_departments(self, connection: Connection) -> list[LdapDepartmentRecord]:
        try:
            searched = connection.search(
                search_base=settings.LDAP_GROUPS_BASE_DN,
                search_filter="(objectClass=posixGroup)",
                search_scope=SUBTREE,
                attributes=self._GROUP_ATTRIBUTES,
            )
            if not searched:
                raise LdapDirectoryError("LDAP 部门组查询未成功。")
        except Exception as exc:
            raise LdapDirectoryError("读取 LDAP 部门组失败，请检查部门组基准 DN。") from exc

        records: list[LdapDepartmentRecord] = []
        seen_ids: set[str] = set()
        for entry in connection.entries:
            markers = self._description_markers(entry)
            source_id = markers.get("xrxsDepartmentId", "").strip()
            if not source_id:
                # 只消费 xrxs2ldap 管理的部门组，避免把其他 LDAP 组变成部门。
                continue
            if source_id in seen_ids:
                raise LdapDirectoryError(f"LDAP 中发现重复的部门 ID：{source_id}。")
            seen_ids.add(source_id)
            raw_name = self._first_value(entry, "cn") or source_id
            records.append(
                LdapDepartmentRecord(
                    source_id=source_id,
                    name=self._department_name(raw_name, source_id),
                    parent_source_id=markers.get("xrxsParentDepartmentId") or None,
                    dn=entry.entry_dn,
                )
            )
        return records

    def _fetch_employees(self, connection: Connection) -> list[LdapEmployeeRecord]:
        try:
            searched = connection.search(
                search_base=settings.LDAP_PEOPLE_BASE_DN,
                search_filter="(&(objectClass=inetOrgPerson)(uid=*))",
                search_scope=SUBTREE,
                attributes=self._PEOPLE_ATTRIBUTES,
            )
            if not searched:
                raise LdapDirectoryError("LDAP 人员查询未成功。")
        except Exception as exc:
            raise LdapDirectoryError("读取 LDAP 人员失败，请检查人员基准 DN。") from exc

        records: list[LdapEmployeeRecord] = []
        seen_uids: set[str] = set()
        for entry in connection.entries:
            uid = self._first_value(entry, "uid")
            if not uid:
                continue
            if uid.casefold() in seen_uids:
                raise LdapDirectoryError(f"LDAP 中发现重复的 UID：{uid}。")
            seen_uids.add(uid.casefold())
            display_name = (
                self._first_value(entry, "displayName")
                or self._first_value(entry, "cn")
                or uid
            )
            employee_type = self._first_value(entry, "employeeType").casefold()
            # xrxs2ldap 明确写入 active/inactive；缺少状态的 admin/dev 等条目不作为员工新增。
            records.append(
                LdapEmployeeRecord(
                    uid=uid,
                    display_name=display_name,
                    email=self._first_value(entry, "mail"),
                    employee_number=self._first_value(entry, "employeeNumber"),
                    department_source_id=self._first_value(entry, "departmentNumber") or None,
                    phone=self._first_value(entry, "telephoneNumber"),
                    title=self._first_value(entry, "title"),
                    active=employee_type == "active",
                    dn=entry.entry_dn,
                )
            )
        return records

    @staticmethod
    def _first_value(entry: object, attribute: str) -> str:
        if attribute not in entry:
            return ""
        values = [str(value).strip() for value in entry[attribute].values]
        return next((value for value in values if value), "")

    @classmethod
    def _description_markers(cls, entry: object) -> dict[str, str]:
        markers: dict[str, str] = {}
        if "description" not in entry:
            return markers
        for value in entry["description"].values:
            text = str(value).strip()
            if "=" not in text:
                continue
            key, marker_value = text.split("=", 1)
            markers[key.strip()] = marker_value.strip()
        return markers

    @staticmethod
    def _department_name(raw_name: str, source_id: str) -> str:
        # xrxs2ldap 只在同级重名时给 cn 追加 -<部门ID前8位>，同步时还原 HR 部门名称。
        suffix = f"-{source_id[:8]}"
        if raw_name.endswith(suffix):
            return raw_name[: -len(suffix)]
        return raw_name


class LdapDirectorySyncService:
    """把 LDAP 快照安全地合并进本地用户和部门，不删除本地记录。"""

    def __init__(self, snapshot: LdapSnapshot | None = None) -> None:
        self.snapshot = snapshot

    def sync(self, dry_run: bool = False) -> LdapSyncResult:
        snapshot = self.snapshot or LdapDirectoryClient().fetch_snapshot()
        result = LdapSyncResult()
        with transaction.atomic():
            departments = self._sync_departments(snapshot.departments, result, dry_run)
            self._sync_employees(snapshot.employees, departments, result, dry_run)
        return result

    def _sync_departments(
        self,
        records: tuple[LdapDepartmentRecord, ...],
        result: LdapSyncResult,
        dry_run: bool,
    ) -> dict[str, Department]:
        prepared_records, alias_to_source, alias_to_local = self._prepare_department_records(records)
        pending = {record.source_id: record for record in prepared_records}
        existing_by_source_id = {
            department.ldap_department_id: department
            for department in Department.objects.exclude(ldap_department_id__isnull=True)
            if department.ldap_department_id
        }
        used_department_ids: set[int] = set()
        resolved: dict[str, Department] = dict(alias_to_local)
        used_department_ids.update(
            department.pk for department in alias_to_local.values() if department.pk
        )

        while pending:
            progressed = False
            for source_id, record in list(pending.items()):
                if record.parent_source_id and record.parent_source_id in pending:
                    continue

                parent = resolved.get(record.parent_source_id) if record.parent_source_id else None
                department = existing_by_source_id.get(source_id)
                if department is None:
                    department = self._match_legacy_department(
                        record,
                        parent,
                        used_department_ids,
                    )

                if department is None:
                    if dry_run:
                        # 让后续预览中的子部门能看到一个稳定的临时父级 ID。
                        department = Department(
                            name=record.name[:100],
                            code=f"263-{abs(len(resolved) + 1)}",
                            parent=parent,
                            is_active=True,
                            ldap_department_id=source_id,
                            ldap_dn=record.dn[:512],
                        )
                        department.pk = -(len(resolved) + 1)
                    else:
                        department = create_department(
                            name=record.name[:100],
                            parent=parent,
                            is_active=True,
                            ldap_department_id=source_id,
                            ldap_dn=record.dn[:512],
                        )
                    result.departments_created += 1
                else:
                    code_needs_update = not is_standard_department_code(department.code)
                    changed = (
                        department.name != record.name[:100]
                        or department.parent_id != (parent.pk if parent else None)
                        or not department.is_active
                        or department.ldap_department_id != source_id
                        or department.ldap_dn != record.dn[:512]
                        or code_needs_update
                    )
                    if changed:
                        result.departments_updated += 1
                    if not dry_run:
                        if code_needs_update:
                            department.code = allocate_department_code()
                        department.name = record.name[:100]
                        department.parent = parent
                        department.is_active = True
                        department.ldap_department_id = source_id
                        department.ldap_dn = record.dn[:512]
                        department.save(
                            update_fields=[
                                "name",
                                "parent",
                                "code",
                                "is_active",
                                "ldap_department_id",
                                "ldap_dn",
                                "updated_at",
                            ]
                        )

                if parent is None and record.parent_source_id:
                    result.departments_without_parent += 1
                    result.warn(
                        f"部门“{record.name}”的上级 {record.parent_source_id} 在 LDAP 快照中不存在，已按顶级部门处理。"
                    )
                resolved[source_id] = department
                if department.pk:
                    used_department_ids.add(department.pk)
                del pending[source_id]
                progressed = True

            if not progressed:
                cycle = ", ".join(sorted(pending))
                raise LdapDirectoryError(f"LDAP 部门层级存在循环，无法同步：{cycle}。")

        for alias_source_id, canonical_source_id in alias_to_source.items():
            department = resolved.get(canonical_source_id)
            if department is not None:
                resolved[alias_source_id] = department

        return resolved

    def _prepare_department_records(
        self,
        records: tuple[LdapDepartmentRecord, ...],
    ) -> tuple[
        tuple[LdapDepartmentRecord, ...],
        dict[str, str],
        dict[str, Department],
    ]:
        """把已合并的旧部门映射到人力资源部，避免 LDAP 再次创建旧部门。"""

        target_records = [
            record
            for record in records
            if record.name.strip() == DEPARTMENT_MERGE_TARGET
        ]
        local_targets = list(
            Department.objects.filter(name=DEPARTMENT_MERGE_TARGET).order_by("id")
        )
        target_source_id = target_records[0].source_id if target_records else None
        local_target = local_targets[0] if local_targets else None
        alias_to_source: dict[str, str] = {}
        alias_to_local: dict[str, Department] = {}

        for record in records:
            canonical_name = canonical_department_name(record.name)
            if canonical_name == record.name.strip():
                continue
            if target_source_id and record.source_id != target_source_id:
                alias_to_source[record.source_id] = target_source_id
            elif local_target is not None:
                alias_to_local[record.source_id] = local_target

        prepared = []
        for record in records:
            if record.source_id in alias_to_source or record.source_id in alias_to_local:
                continue
            parent_source_id = alias_to_source.get(
                record.parent_source_id,
                record.parent_source_id,
            )
            prepared.append(
                replace(
                    record,
                    parent_source_id=parent_source_id,
                )
            )
        return tuple(prepared), alias_to_source, alias_to_local

    def _match_legacy_department(
        self,
        record: LdapDepartmentRecord,
        parent: Department | None,
        used_department_ids: set[int],
    ) -> Department | None:
        candidates = Department.objects.filter(name=record.name).exclude(pk__in=used_department_ids)
        parent_id = parent.pk if parent else None
        candidates = [candidate for candidate in candidates if candidate.parent_id == parent_id]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _sync_employees(
        self,
        records: tuple[LdapEmployeeRecord, ...],
        departments: dict[str, Department],
        result: LdapSyncResult,
        dry_run: bool,
    ) -> None:
        profiles = list(EmployeeProfile.objects.select_related("user"))
        profile_by_ldap_uid = {
            profile.ldap_uid.casefold(): profile
            for profile in profiles
            if profile.ldap_uid
        }
        profile_by_employee_no = {profile.employee_no.casefold(): profile for profile in profiles}
        users_by_username = {
            user.username.casefold(): user
            for user in User.objects.all()
        }
        users_by_email: dict[str, list[User]] = defaultdict(list)
        for user in User.objects.exclude(email=""):
            users_by_email[user.email.casefold()].append(user)

        claimed_user_keys: set[object] = set()
        for employee in sorted(records, key=lambda item: (not item.active, item.uid.casefold())):
            profile = profile_by_ldap_uid.get(employee.uid.casefold())
            user = profile.user if profile else None
            if user is None:
                user = users_by_username.get(employee.uid.casefold())
                profile = self._profile_for_user(user)
            if user is None and employee.employee_number:
                profile = profile_by_employee_no.get(employee.employee_number.casefold())
                user = profile.user if profile else None
            if user is None and employee.email:
                email_matches = users_by_email.get(employee.email.casefold(), [])
                if len(email_matches) == 1:
                    user = email_matches[0]
                    profile = self._profile_for_user(user)
                elif len(email_matches) > 1:
                    result.warn(f"人员“{employee.display_name}”的邮箱匹配到多个本地用户，已跳过。")
                    result.employees_skipped += 1
                    continue

            if user is not None and user.is_superuser:
                result.warn(f"保护超级管理员“{user.username}”，未用 LDAP 覆盖。")
                result.employees_skipped += 1
                continue

            if user is None and not employee.active and not settings.LDAP_SYNC_CREATE_INACTIVE_USERS:
                result.employees_skipped += 1
                continue

            department = departments.get(employee.department_source_id)
            if employee.department_source_id and department is None:
                result.employees_without_department += 1
                result.warn(
                    f"人员“{employee.display_name}”引用了不存在的 LDAP 部门 {employee.department_source_id}，部门留空。"
                )

            employee_no = self._employee_no(employee.employee_number or employee.uid, user)
            if profile is not None and profile.user_id != (user.pk if user else None):
                result.warn(f"人员“{employee.display_name}”的本地档案归属冲突，已跳过。")
                result.employees_skipped += 1
                continue

            # xrxs2ldap 会为同邮箱的历史非启用员工保留带后缀 UID。启用记录优先，
            # 同一轮同步内一个本地用户只允许被一条 LDAP 记录认领，避免后来的历史记录覆盖当前人员。
            user_key = (
                user.pk
                if user is not None and user.pk is not None
                else ("new", employee.uid.casefold())
            )
            if user_key in claimed_user_keys:
                result.warn(
                    f"人员“{employee.display_name}”（uid={employee.uid}）与本轮已匹配的 LDAP 记录共用本地用户，已跳过。"
                )
                result.employees_skipped += 1
                continue
            claimed_user_keys.add(user_key)

            was_created = user is None
            was_active = user.is_active if user is not None else False
            if was_created:
                user = User(username=employee.uid)
                user.set_unusable_password()

            desired_user_fields = {
                "email": employee.email,
                "first_name": employee.display_name[:150],
                "last_name": "",
                "is_active": employee.active,
            }
            user_changed = any(
                getattr(user, field_name) != value
                for field_name, value in desired_user_fields.items()
            )
            profile_changed = profile is None or any(
                (
                    getattr(profile, field_name) != value
                    if field_name != "department"
                    else profile.department_id != (department.pk if department else None)
                )
                for field_name, value in {
                    "employee_no": employee_no,
                    "ldap_uid": employee.uid,
                    "ldap_dn": employee.dn[:512],
                    "department": department,
                    "phone": employee.phone[:32],
                }.items()
            )

            if not dry_run:
                if was_created:
                    for field_name, value in desired_user_fields.items():
                        setattr(user, field_name, value)
                    user.save()
                elif user_changed:
                    User.objects.filter(pk=user.pk).update(**desired_user_fields)
                    for field_name, value in desired_user_fields.items():
                        setattr(user, field_name, value)

            if was_created:
                result.employees_created += 1
            elif user_changed or profile_changed:
                result.employees_updated += 1
                if not employee.active and was_active:
                    result.employees_deactivated += 1

            if not dry_run:
                profile, _ = EmployeeProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "employee_no": employee_no,
                        "ldap_uid": employee.uid,
                        "ldap_dn": employee.dn[:512],
                        "department": department,
                        "phone": employee.phone[:32],
                    },
                )
                profile_by_ldap_uid[employee.uid.casefold()] = profile
                profile_by_employee_no[profile.employee_no.casefold()] = profile
                users_by_username[user.username.casefold()] = user

    @staticmethod
    def _profile_for_user(user: User | None) -> EmployeeProfile | None:
        if user is None:
            return None
        try:
            return user.employee_profile
        except EmployeeProfile.DoesNotExist:
            return None

    @staticmethod
    def _employee_no(value: str, user: User | None) -> str:
        candidate = value.strip()
        if len(candidate) <= 32:
            conflict = EmployeeProfile.objects.filter(employee_no=candidate)
            if user is not None:
                conflict = conflict.exclude(user=user)
            if not conflict.exists():
                return candidate

        suffix = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:7]
        return f"{candidate[:24]}-{suffix}"

def search_snapshot(snapshot: LdapSnapshot, query: str) -> tuple[list[LdapEmployeeRecord], list[LdapDepartmentRecord]]:
    """按姓名、UID、工号或部门 ID 查询快照，供运维核验使用。"""
    needle = re.sub(r"\s+", "", query).casefold()
    employees = [
        employee
        for employee in snapshot.employees
        if needle in re.sub(r"\s+", "", employee.display_name).casefold()
        or needle in employee.uid.casefold()
        or needle in employee.employee_number.casefold()
        or needle in (employee.department_source_id or "").casefold()
    ]
    departments = [
        department
        for department in snapshot.departments
        if needle in re.sub(r"\s+", "", department.name).casefold()
        or needle in department.source_id.casefold()
    ]
    return employees, departments
