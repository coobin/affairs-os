# Generated for the initial AffairsOS schema.
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, verbose_name="分类名称")),
                ("code", models.CharField(max_length=12, unique=True, verbose_name="分类编码")),
                ("icon", models.CharField(default="laptop", max_length=32, verbose_name="图标")),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="说明")),
                ("custom_fields", models.JSONField(blank=True, default=list, verbose_name="分类字段模板")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
            ],
            options={
                "verbose_name": "资产分类",
                "verbose_name_plural": "资产分类",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, verbose_name="部门名称")),
                ("code", models.CharField(max_length=32, unique=True, verbose_name="部门编码")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="assets.department",
                        verbose_name="上级部门",
                    ),
                ),
            ],
            options={
                "verbose_name": "部门",
                "verbose_name_plural": "部门",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, verbose_name="地点名称")),
                ("code", models.CharField(max_length=32, unique=True, verbose_name="地点编码")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("office", "办公室"),
                            ("warehouse", "库房"),
                            ("repair", "维修点"),
                            ("other", "其他"),
                        ],
                        default="office",
                        max_length=20,
                        verbose_name="地点类型",
                    ),
                ),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="地址")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
            ],
            options={
                "verbose_name": "地点",
                "verbose_name_plural": "地点",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="EmployeeProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employee_no", models.CharField(max_length=32, unique=True, verbose_name="工号")),
                ("phone", models.CharField(blank=True, max_length=32, verbose_name="联系电话")),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employees",
                        to="assets.department",
                        verbose_name="部门",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="employee_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "员工档案",
                "verbose_name_plural": "员工档案",
                "ordering": ["employee_no"],
            },
        ),
        migrations.CreateModel(
            name="Asset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("asset_tag", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="资产编号")),
                ("name", models.CharField(max_length=120, verbose_name="资产名称")),
                ("brand", models.CharField(blank=True, max_length=80, verbose_name="品牌")),
                ("model_name", models.CharField(blank=True, max_length=120, verbose_name="型号")),
                ("serial_number", models.CharField(blank=True, db_index=True, max_length=120, verbose_name="序列号")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "待验收"),
                            ("available", "在库可用"),
                            ("inspection", "待检"),
                            ("assigned", "在用"),
                            ("loaned", "借用中"),
                            ("transfer", "调拨中"),
                            ("repair", "维修中"),
                            ("lost", "遗失"),
                            ("retired", "已退役"),
                            ("disposed", "已处置"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="状态",
                    ),
                ),
                ("purchase_date", models.DateField(blank=True, null=True, verbose_name="采购日期")),
                (
                    "purchase_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="采购金额",
                    ),
                ),
                ("warranty_expires_at", models.DateField(blank=True, db_index=True, null=True, verbose_name="保修到期")),
                ("expected_return_at", models.DateField(blank=True, db_index=True, null=True, verbose_name="预计归还")),
                ("notes", models.TextField(blank=True, verbose_name="备注")),
                ("custom_data", models.JSONField(blank=True, default=dict, verbose_name="扩展信息")),
                ("last_audited_at", models.DateTimeField(blank=True, null=True, verbose_name="最后盘点时间")),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assigned_assets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="使用人",
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="assets.assetcategory",
                        verbose_name="资产分类",
                    ),
                ),
                (
                    "current_location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="assets.location",
                        verbose_name="当前地点",
                    ),
                ),
                (
                    "custodian_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="assets.department",
                        verbose_name="保管部门",
                    ),
                ),
            ],
            options={
                "verbose_name": "资产",
                "verbose_name_plural": "资产",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "category"], name="asset_status_cat_idx"),
                    models.Index(fields=["assigned_to", "status"], name="asset_user_status_idx"),
                    models.Index(fields=["current_location", "status"], name="asset_loc_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AssetEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "登记"),
                            ("accepted", "验收入库"),
                            ("assigned", "领用"),
                            ("loaned", "借用"),
                            ("returned", "归还"),
                            ("transferred", "调拨"),
                            ("repair_started", "送修"),
                            ("repair_completed", "维修完成"),
                            ("lost", "报失"),
                            ("found", "找回"),
                            ("retired", "退役"),
                            ("disposed", "处置"),
                            ("updated", "信息更新"),
                        ],
                        max_length=32,
                        verbose_name="动作",
                    ),
                ),
                ("from_status", models.CharField(blank=True, max_length=20, verbose_name="原状态")),
                ("to_status", models.CharField(blank=True, max_length=20, verbose_name="新状态")),
                ("happened_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="发生时间")),
                ("notes", models.TextField(blank=True, verbose_name="说明")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="附加信息")),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="asset_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="经办人",
                    ),
                ),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="assets.asset",
                        verbose_name="资产",
                    ),
                ),
                (
                    "from_location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="assets.location",
                        verbose_name="原地点",
                    ),
                ),
                (
                    "from_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="原使用人",
                    ),
                ),
                (
                    "to_location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="assets.location",
                        verbose_name="新地点",
                    ),
                ),
                (
                    "to_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="新使用人",
                    ),
                ),
            ],
            options={
                "verbose_name": "资产事件",
                "verbose_name_plural": "资产事件",
                "ordering": ["-happened_at", "-id"],
            },
        ),
    ]
