import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from assets.models import Asset, AssetCategory, AssetEvent, Department, EmployeeProfile, Location

User = get_user_model()


class Command(BaseCommand):
    help = "创建可重复执行的演示账号和资产数据"

    @transaction.atomic
    def handle(self, *args, **options):
        admin_username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        admin, _ = User.objects.update_or_create(
            username=admin_username,
            defaults={
                "email": os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com"),
                "first_name": "资产",
                "last_name": "管理员",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        admin.set_password(os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123"))
        admin.save()

        departments = {}
        for code, name in [
            ("ADM", "行政部"),
            ("IT", "信息技术部"),
            ("MKT", "市场部"),
            ("FIN", "财务部"),
        ]:
            departments[code], _ = Department.objects.get_or_create(code=code, defaults={"name": name})

        employees = [
            ("E1001", "linxia", "林", "夏", "MKT"),
            ("E1002", "chenmo", "陈", "默", "FIN"),
            ("E1003", "zhouyu", "周", "宇", "IT"),
        ]
        users = {}
        for employee_no, username, last_name, first_name, department_code in employees:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "last_name": last_name,
                    "first_name": first_name,
                    "is_active": True,
                },
            )
            user.set_password("demo123")
            user.save()
            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults={
                    "employee_no": employee_no,
                    "department": departments[department_code],
                },
            )
            users[username] = user

        locations = {}
        for code, name, kind, address in [
            ("SH-OFFICE", "上海办公室", "office", "12F · A 区"),
            ("SH-WH", "上海 IT 库房", "warehouse", "12F · 储物间"),
            ("SZ-OFFICE", "深圳办公室", "office", "8F · 开放办公区"),
            ("REPAIR", "外部维修", "repair", "服务商保管"),
        ]:
            locations[code], _ = Location.objects.get_or_create(
                code=code,
                defaults={"name": name, "kind": kind, "address": address},
            )

        categories = {}
        for code, name, icon in [
            ("LT", "笔记本电脑", "laptop"),
            ("MN", "显示器", "monitor"),
            ("PH", "手机", "smartphone"),
            ("NW", "网络设备", "router"),
            ("OT", "其他设备", "box"),
        ]:
            categories[code], _ = AssetCategory.objects.get_or_create(
                code=code,
                defaults={"name": name, "icon": icon},
            )

        today = date.today()
        assets = [
            {
                "asset_tag": "IT-LT-2026-123",
                "name": "MacBook Pro 14",
                "category": categories["LT"],
                "brand": "Apple",
                "model_name": "MacBook Pro M4",
                "serial_number": "C02DEMO123",
                "status": Asset.Status.ASSIGNED,
                "assigned_to": users["linxia"],
                "custodian_department": departments["MKT"],
                "current_location": locations["SH-OFFICE"],
                "purchase_date": today - timedelta(days=180),
                "purchase_cost": Decimal("14999.00"),
                "warranty_expires_at": today + timedelta(days=185),
            },
            {
                "asset_tag": "IT-MN-2026-088",
                "name": "27 英寸显示器",
                "category": categories["MN"],
                "brand": "Dell",
                "model_name": "U2723QE",
                "serial_number": "DELL-DEMO-88",
                "status": Asset.Status.AVAILABLE,
                "current_location": locations["SH-WH"],
                "purchase_date": today - timedelta(days=400),
                "purchase_cost": Decimal("3299.00"),
                "warranty_expires_at": today + timedelta(days=45),
            },
            {
                "asset_tag": "IT-LT-2025-071",
                "name": "ThinkPad X1 Carbon",
                "category": categories["LT"],
                "brand": "Lenovo",
                "model_name": "X1 Carbon Gen 12",
                "serial_number": "LEN-DEMO-71",
                "status": Asset.Status.LOANED,
                "assigned_to": users["chenmo"],
                "custodian_department": departments["FIN"],
                "current_location": locations["SH-OFFICE"],
                "expected_return_at": today - timedelta(days=2),
                "purchase_date": today - timedelta(days=520),
                "purchase_cost": Decimal("11999.00"),
                "warranty_expires_at": today + timedelta(days=20),
            },
            {
                "asset_tag": "IT-PH-2025-039",
                "name": "iPhone 15",
                "category": categories["PH"],
                "brand": "Apple",
                "model_name": "iPhone 15 256GB",
                "serial_number": "IPH-DEMO-39",
                "status": Asset.Status.REPAIR,
                "current_location": locations["REPAIR"],
                "custodian_department": departments["IT"],
                "purchase_date": today - timedelta(days=330),
                "purchase_cost": Decimal("6999.00"),
                "warranty_expires_at": today + timedelta(days=35),
            },
            {
                "asset_tag": "IT-NW-2024-012",
                "name": "会议室无线接入点",
                "category": categories["NW"],
                "brand": "Ubiquiti",
                "model_name": "U6 Pro",
                "serial_number": "UBNT-DEMO-12",
                "status": Asset.Status.INSPECTION,
                "current_location": locations["SZ-OFFICE"],
                "custodian_department": departments["IT"],
                "purchase_date": today - timedelta(days=760),
                "purchase_cost": Decimal("1399.00"),
            },
        ]

        for payload in assets:
            asset, created = Asset.objects.update_or_create(
                asset_tag=payload["asset_tag"],
                defaults=payload,
            )
            if created:
                AssetEvent.objects.create(
                    asset=asset,
                    action=AssetEvent.Action.CREATED,
                    to_status=asset.status,
                    to_user=asset.assigned_to,
                    to_location=asset.current_location,
                    actor=admin,
                    notes="演示数据初始化",
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"演示数据已就绪。管理员账号：{admin_username}；密码使用环境变量中的设置。"
            )
        )
