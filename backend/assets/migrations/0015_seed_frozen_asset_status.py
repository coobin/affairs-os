from django.db import migrations


def seed_frozen_status(apps, schema_editor):
    AssetStatus = apps.get_model("assets", "AssetStatus")
    AssetStatus.objects.update_or_create(
        code="frozen",
        defaults={
            "name": "冻结",
            "sort_order": 15,
            "is_system": True,
            "is_active": True,
        },
    )


def remove_frozen_status(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    AssetStatus = apps.get_model("assets", "AssetStatus")
    if not Asset.objects.filter(status="frozen").exists():
        AssetStatus.objects.filter(code="frozen").delete()


class Migration(migrations.Migration):
    dependencies = [("assets", "0014_assetrequest_inventory_item_and_more")]

    operations = [
        migrations.RunPython(seed_frozen_status, remove_frozen_status),
    ]
