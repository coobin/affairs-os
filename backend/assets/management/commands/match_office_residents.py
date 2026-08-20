import re

from django.core.management.base import BaseCommand
from django.db import transaction

from assets.models import Office


def normalize(value):
    return re.sub(r"\s+", "", str(value or "")).casefold()


class Command(BaseCommand):
    help = "按在职员工姓名、账号或工号自动匹配办事处原始居住人名单"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="统计后回滚，不修改数据")

    def handle(self, *args, **options):
        users = []
        for user in self._users():
            profile = getattr(user, "employee_profile", None)
            if profile:
                users.append((user, {normalize(user.get_full_name()), normalize(user.username), normalize(profile.employee_no)}))
        matched_links = 0
        changed_offices = 0
        unmatched = set()
        with transaction.atomic():
            for office in Office.objects.all().order_by("code"):
                tokens = [token for token in re.split(r"[、,，;；\s]+", office.residents or "") if token]
                matches = []
                for token in tokens:
                    key = normalize(token)
                    user = next((candidate for candidate, aliases in users if key and key in aliases), None)
                    if user:
                        if user not in matches:
                            matches.append(user)
                    elif "流动" not in token:
                        unmatched.add(token)
                previous = set(office.resident_users.values_list("pk", flat=True))
                current = {user.pk for user in matches}
                if previous != current:
                    office.resident_users.set(matches)
                    changed_offices += 1
                matched_links += len(matches)
            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "预演" if options["dry_run"] else "完成"
        unmatched_text = "、".join(sorted(unmatched)) or "无"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}：检查 {Office.objects.count()} 个办事处，更新 {changed_offices} 个，匹配 {matched_links} 条员工关系；未匹配：{unmatched_text}。"
            )
        )

    @staticmethod
    def _users():
        from django.contrib.auth import get_user_model

        return get_user_model().objects.filter(
            is_active=True,
            employee_profile__isnull=False,
        ).select_related("employee_profile")
