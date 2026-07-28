import hashlib
import json
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assets.models import Department, EmployeeProfile

User = get_user_model()


def employee_number(username):
    if len(username) <= 32:
        return username
    suffix = hashlib.sha1(username.encode("utf-8")).hexdigest()[:7]
    return f"{username[:24]}-{suffix}"


class Command(BaseCommand):
    help = "从标准 JSON 导入公司部门和人员；不会修改已有超级管理员"

    def add_arguments(self, parser):
        parser.add_argument("--input", default="-", help="JSON 文件路径；- 表示标准输入")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            if options["input"] == "-":
                payload = json.load(sys.stdin)
            else:
                with open(options["input"], encoding="utf-8") as source:
                    payload = json.load(source)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"无法读取人员数据：{exc}") from exc

        departments = {
            str(item["source_id"]): item for item in payload.get("departments", [])
        }
        department_mapping = {}
        remaining = dict(departments)
        while remaining:
            progressed = False
            for source_id, item in list(remaining.items()):
                parent_source_id = str(item.get("parent_source_id") or "")
                if parent_source_id and parent_source_id not in department_mapping:
                    if parent_source_id in remaining:
                        continue
                    parent_source_id = ""
                department, _ = Department.objects.update_or_create(
                    code=f"263-{source_id}"[:32],
                    defaults={
                        "name": str(item["name"]).strip()[:100],
                        "parent": department_mapping.get(parent_source_id),
                        "is_active": True,
                    },
                )
                department_mapping[source_id] = department
                del remaining[source_id]
                progressed = True
            if not progressed:
                raise CommandError("部门层级存在循环，无法导入。")

        created = 0
        updated = 0
        skipped_admins = 0
        for item in payload.get("users", []):
            username = str(item.get("username") or "").strip()
            full_name = str(item.get("full_name") or "").strip()
            if not username or not full_name:
                continue

            user = User.objects.filter(username=username).first()
            if user and user.is_superuser:
                skipped_admins += 1
                continue

            was_created = user is None
            if was_created:
                user = User(username=username)
                user.set_unusable_password()

            user.email = str(item.get("email") or "").strip()
            user.first_name = full_name[:150]
            user.last_name = ""
            user.is_active = bool(item.get("active", True))
            user.is_staff = False
            user.is_superuser = False
            user.save()

            department_ids = [
                str(value) for value in item.get("department_source_ids", []) if value
            ]
            department = next(
                (
                    department_mapping[source_id]
                    for source_id in department_ids
                    if source_id in department_mapping
                ),
                None,
            )
            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults={
                    "employee_no": employee_number(username),
                    "department": department,
                    "phone": str(item.get("mobile") or "").strip()[:32],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "人员同步完成："
                f"部门 {len(department_mapping)} 个，新增人员 {created} 人，"
                f"更新人员 {updated} 人，保护管理员 {skipped_admins} 人。"
            )
        )
