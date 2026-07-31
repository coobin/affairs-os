from django.db import migrations, models


def migrate_frozen_assets(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    AssetStatus = apps.get_model("assets", "AssetStatus")
    Asset.objects.filter(status="frozen").update(
        status="available",
        is_requestable=False,
    )
    AssetStatus.objects.filter(code="frozen").delete()


def restore_frozen_assets(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    AssetStatus = apps.get_model("assets", "AssetStatus")
    AssetStatus.objects.get_or_create(
        code="frozen",
        defaults={
            "name": "冻结",
            "sort_order": 15,
            "is_system": True,
            "is_active": True,
        },
    )
    Asset.objects.filter(status="available", is_requestable=False).update(
        status="frozen",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0020_contracttype_contract_previous_contract_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="is_requestable",
            field=models.BooleanField(
                db_index=True,
                default=True,
                verbose_name="允许员工申请",
            ),
        ),
        migrations.RunPython(migrate_frozen_assets, restore_frozen_assets),
        migrations.AlterField(
            model_name="contractattachment",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("original", "合同原件"),
                    ("signed", "盖章扫描件"),
                    ("supplement", "补充协议"),
                    ("quotation", "报价单"),
                    ("invoice", "发票"),
                    ("other", "其他"),
                ],
                default="original",
                max_length=20,
                verbose_name="文件类别",
            ),
        ),
    ]
