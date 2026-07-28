from django.db import migrations


def normalize_asset_names(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    AssetRequest = apps.get_model("assets", "AssetRequest")

    old_name_categories = {}
    for asset in Asset.objects.select_related("category").order_by("id"):
        old_name_categories.setdefault(asset.name, set()).add(asset.category.name)

    for request in AssetRequest.objects.select_related("assigned_asset__category"):
        if request.assigned_asset_id:
            request.requested_name = request.assigned_asset.category.name
            request.save(update_fields=["requested_name"])
            continue
        categories = old_name_categories.get(request.requested_name, set())
        if len(categories) == 1:
            request.requested_name = next(iter(categories))
            request.save(update_fields=["requested_name"])

    for asset in Asset.objects.select_related("category"):
        brand = asset.brand.strip()
        model_name = asset.model_name.strip()
        if brand and model_name:
            display_name = (
                model_name
                if model_name.casefold().startswith(brand.casefold())
                else f"{brand} {model_name}"
            )
        else:
            display_name = brand or model_name or asset.category.name or "待完善资产"
        Asset.objects.filter(pk=asset.pk).update(name=display_name[:120])


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0006_assetmanagerrole_assetrequest"),
    ]

    operations = [
        migrations.RunPython(normalize_asset_names, migrations.RunPython.noop),
    ]
