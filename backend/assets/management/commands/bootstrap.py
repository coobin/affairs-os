import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from assets.department_directory import create_department
from assets.models import AssetCategory, Department, Location

User = get_user_model()


class Command(BaseCommand):
    help = "创建或更新正式管理员，并初始化最小化基础资料（不创建演示资产）"

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        admin, created = User.objects.get_or_create(username=username)
        admin.email = os.getenv("DJANGO_SUPERUSER_EMAIL", admin.email)
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        if password:
            admin.set_password(password)
        elif created:
            admin.set_unusable_password()
        admin.save()

        human_resources = Department.objects.filter(name="人力资源部").order_by("id").first()
        if human_resources is None:
            create_department(name="人力资源部", is_active=True)
        elif not human_resources.is_active:
            human_resources.is_active = True
            human_resources.save(update_fields=["is_active", "updated_at"])

        for code, name, kind, address in [
            ("MAIN-OFFICE", "总部办公室", "office", ""),
            ("MAIN-WH", "IT 资产库房", "warehouse", ""),
            ("REPAIR", "外部维修", "repair", "服务商保管"),
        ]:
            Location.objects.update_or_create(
                code=code,
                defaults={"name": name, "kind": kind, "address": address},
            )

        for code, name, icon in [
            ("LT", "笔记本电脑", "laptop"),
            ("DT", "台式电脑", "computer"),
            ("MN", "显示器", "monitor"),
            ("PH", "手机与平板", "smartphone"),
            ("NW", "网络设备", "router"),
            ("PR", "打印与办公设备", "printer"),
            ("SV", "服务器与存储", "server"),
            ("OT", "其他设备", "box"),
        ]:
            AssetCategory.objects.update_or_create(
                code=code,
                defaults={"name": name, "icon": icon},
            )

        state = "已创建" if created else "已更新"
        self.stdout.write(
            self.style.SUCCESS(
                f"正式环境初始化完成：管理员 {username} {state}，基础资料已就绪，未创建演示资产。"
            )
        )
