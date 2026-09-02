from django.core.management.base import BaseCommand, CommandError

from assets.ldap_directory import (
    LdapDirectoryClient,
    LdapDirectoryError,
    LdapDirectorySyncService,
    search_snapshot,
)


class Command(BaseCommand):
    help = "从 xrxs2ldap 写入的 LDAP 同步部门和人员；默认会写入本地数据库"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只读取并计算变化，不写入本地数据库",
        )
        parser.add_argument(
            "--search",
            help="只查询 LDAP 中匹配的人员或部门，不执行同步，例如：--search 沈敦彬",
        )

    def handle(self, *args, **options):
        try:
            snapshot = LdapDirectoryClient().fetch_snapshot()
        except LdapDirectoryError as exc:
            raise CommandError(str(exc)) from exc

        if options.get("search"):
            employees, departments = search_snapshot(snapshot, options["search"])
            self.stdout.write(
                f"LDAP 快照：人员 {len(snapshot.employees)} 人，部门 {len(snapshot.departments)} 个。"
            )
            self.stdout.write(f"匹配人员 {len(employees)} 人：")
            for employee in employees:
                self.stdout.write(
                    f"- {employee.display_name} / uid={employee.uid} / "
                    f"工号={employee.employee_number or '未填写'} / "
                    f"部门ID={employee.department_source_id or '未填写'} / "
                    f"状态={'启用' if employee.active else '非启用'}"
                )
            self.stdout.write(f"匹配部门 {len(departments)} 个：")
            for department in departments:
                self.stdout.write(
                    f"- {department.name} / id={department.source_id} / "
                    f"上级={department.parent_source_id or '无'}"
                )
            return

        result = LdapDirectorySyncService(snapshot).sync(dry_run=options["dry_run"])
        prefix = "LDAP 同步预览完成" if options["dry_run"] else "LDAP 同步完成"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}：部门新增 {result.departments_created} 个，部门更新 {result.departments_updated} 个，"
                f"人员新增 {result.employees_created} 人，人员更新 {result.employees_updated} 人，"
                f"人员停用 {result.employees_deactivated} 人，跳过 {result.employees_skipped} 人。"
            )
        )
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"提示：{warning}"))
