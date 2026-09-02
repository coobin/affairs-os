from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from assets.department_directory import (
    DEPARTMENT_CODE_PREFIX,
    DEPARTMENT_MERGE_SOURCE_NAMES,
    DEPARTMENT_MERGE_TARGET,
    department_code_number,
    is_standard_department_code,
)
from assets.models import Department


class Command(BaseCommand):
    help = "将旧部门并入人力资源部，并把所有部门编码统一为 263-数字。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只预览合并和编码调整，不写入数据库",
        )

    @staticmethod
    def _single_department(departments, name):
        matches = [department for department in departments if department.name == name]
        if len(matches) > 1:
            raise CommandError(f"部门“{name}”存在 {len(matches)} 条记录，无法安全合并。")
        return matches[0] if matches else None

    @staticmethod
    def _is_descendant(departments_by_id, candidate, ancestor):
        current = candidate
        seen = set()
        while current.parent_id:
            if current.parent_id == ancestor.pk:
                return True
            if current.parent_id in seen:
                return False
            seen.add(current.parent_id)
            current = departments_by_id.get(current.parent_id)
            if current is None:
                return False
        return False

    @staticmethod
    def _department_relations():
        for model in apps.get_models():
            if model is Department:
                continue
            for field in model._meta.get_fields():
                if (
                    getattr(field, "many_to_one", False)
                    and getattr(field.remote_field, "model", None) is Department
                ):
                    yield model, field

    def _merge_sources(self, target, sources):
        department_updates = {
            "reparented_children": 0,
            "related_records": 0,
            "deactivated_sources": 0,
        }
        for source in sources:
            children = Department.objects.filter(parent_id=source.pk).exclude(
                pk=target.pk
            )
            department_updates["reparented_children"] += children.update(
                parent_id=target.pk,
                updated_at=timezone.now(),
            )

            for model, field in self._department_relations():
                count = model.objects.filter(**{field.attname: source.pk}).update(
                    **{field.attname: target.pk}
                )
                department_updates["related_records"] += count

            if source.is_active:
                source.is_active = False
                source.save(update_fields=["is_active", "updated_at"])
                department_updates["deactivated_sources"] += 1

        return department_updates

    def _normalize_codes(self, departments):
        used_numbers = {
            number
            for department in departments
            if (number := department_code_number(department.code)) is not None
        }
        next_number = max(used_numbers, default=0) + 1
        changed = []
        for department in departments:
            if is_standard_department_code(department.code):
                continue
            while next_number in used_numbers:
                next_number += 1
            code = f"{DEPARTMENT_CODE_PREFIX}{next_number}"
            used_numbers.add(next_number)
            next_number += 1
            department.code = code
            department.save(update_fields=["code", "updated_at"])
            changed.append((department.name, code))
        return changed

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with transaction.atomic():
            departments = list(Department.objects.select_for_update().order_by("id"))
            departments_by_id = {department.pk: department for department in departments}
            target = self._single_department(departments, DEPARTMENT_MERGE_TARGET)
            if target is None:
                raise CommandError(f"缺少目标部门“{DEPARTMENT_MERGE_TARGET}”，已取消操作。")

            sources = []
            missing_names = []
            for name in DEPARTMENT_MERGE_SOURCE_NAMES:
                department = self._single_department(departments, name)
                if department is None:
                    missing_names.append(name)
                elif department.pk != target.pk:
                    sources.append(department)

            for source in sources:
                if self._is_descendant(departments_by_id, target, source):
                    raise CommandError(
                        f"目标部门“{target.name}”位于源部门“{source.name}”下级，无法安全合并。"
                    )

            merge_updates = self._merge_sources(target, sources)
            code_updates = self._normalize_codes(departments)

            source_summary = "、".join(
                f"{source.name}（ID {source.pk}）" for source in sources
            ) or "无"
            self.stdout.write(
                f"合并目标：{target.name}（ID {target.pk}）；源部门：{source_summary}。"
            )
            if missing_names:
                self.stdout.write(
                    self.style.WARNING(
                        "未找到部门：" + "、".join(missing_names) + "。"
                    )
                )
            self.stdout.write(
                "合并影响："
                f"下级部门 {merge_updates['reparented_children']} 个，"
                f"业务记录 {merge_updates['related_records']} 条，"
                f"停用旧部门 {merge_updates['deactivated_sources']} 个。"
            )
            if code_updates:
                self.stdout.write(
                    "编码调整："
                    + "；".join(f"{name} → {code}" for name, code in code_updates)
                    + "。"
                )
            else:
                self.stdout.write("编码调整：所有部门已经符合 263-数字规则。")

            if dry_run:
                transaction.set_rollback(True)

        mode = "预览完成" if dry_run else "完成"
        self.stdout.write(self.style.SUCCESS(f"部门合并与编码规范化{mode}。"))
