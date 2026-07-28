from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0003_asset_kingdee_code_and_number_sequence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sku", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="物品编码")),
                ("name", models.CharField(max_length=120, verbose_name="物品名称")),
                ("kind", models.CharField(choices=[("accessory", "配件"), ("consumable", "耗材"), ("license", "软件许可"), ("other", "其他")], max_length=20, verbose_name="类型")),
                ("unit", models.CharField(default="个", max_length=16, verbose_name="单位")),
                ("quantity", models.PositiveIntegerField(default=0, verbose_name="当前库存")),
                ("minimum_quantity", models.PositiveIntegerField(default=0, verbose_name="最低库存")),
                ("notes", models.CharField(blank=True, max_length=255, verbose_name="备注")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_items", to="assets.location", verbose_name="存放地点")),
            ],
            options={"verbose_name": "库存品", "verbose_name_plural": "库存品", "ordering": ["kind", "sku"]},
        ),
        migrations.CreateModel(
            name="StocktakeTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, verbose_name="任务名称")),
                ("status", models.CharField(choices=[("in_progress", "盘点中"), ("completed", "已完成")], db_index=True, default="in_progress", max_length=20, verbose_name="状态")),
                ("snapshot_count", models.PositiveIntegerField(default=0, verbose_name="应盘数量")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="完成时间")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stocktake_tasks", to=settings.AUTH_USER_MODEL, verbose_name="创建人")),
                ("scope_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stocktake_tasks", to="assets.location", verbose_name="盘点地点")),
            ],
            options={"verbose_name": "盘点任务", "verbose_name_plural": "盘点任务", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="InventoryTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("inbound", "入库"), ("issue", "发放"), ("return", "退回"), ("writeoff", "报损")], max_length=20, verbose_name="动作")),
                ("quantity", models.PositiveIntegerField(verbose_name="数量")),
                ("balance_after", models.PositiveIntegerField(verbose_name="操作后库存")),
                ("notes", models.CharField(blank=True, max_length=255, verbose_name="说明")),
                ("happened_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="发生时间")),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="经办人")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="assets.inventoryitem", verbose_name="库存品")),
                ("recipient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to=settings.AUTH_USER_MODEL, verbose_name="领用人")),
            ],
            options={"verbose_name": "库存流水", "verbose_name_plural": "库存流水", "ordering": ["-happened_at", "-id"]},
        ),
        migrations.CreateModel(
            name="StocktakeRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result", models.CharField(choices=[("pending", "待盘"), ("matched", "正常"), ("location_mismatch", "位置不符"), ("missing", "未盘到")], db_index=True, default="pending", max_length=24, verbose_name="结果")),
                ("scanned_at", models.DateTimeField(blank=True, null=True, verbose_name="盘点时间")),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stocktake_records", to="assets.asset", verbose_name="资产")),
                ("expected_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="assets.location", verbose_name="账面地点")),
                ("expected_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="账面使用人")),
                ("scanned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="盘点人")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="records", to="assets.stocktaketask", verbose_name="盘点任务")),
            ],
            options={"verbose_name": "盘点记录", "verbose_name_plural": "盘点记录", "ordering": ["result", "asset__asset_tag"]},
        ),
        migrations.AddConstraint(
            model_name="stocktakerecord",
            constraint=models.UniqueConstraint(fields=("task", "asset"), name="stocktake_task_asset_unique"),
        ),
    ]
