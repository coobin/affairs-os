from django.db import migrations, models


def sync_asset_departments(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    EmployeeProfile = apps.get_model("assets", "EmployeeProfile")
    department_by_user = dict(
        EmployeeProfile.objects.values_list("user_id", "department_id")
    )
    assets = list(Asset.objects.only("id", "assigned_to_id", "custodian_department_id"))
    changed = []
    for asset in assets:
        expected_department_id = department_by_user.get(asset.assigned_to_id)
        if asset.custodian_department_id != expected_department_id:
            asset.custodian_department_id = expected_department_id
            changed.append(asset)
    if changed:
        Asset.objects.bulk_update(changed, ["custodian_department"])


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0026_alter_assetevent_action"),
    ]

    operations = [
        migrations.RunPython(sync_asset_departments, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(assigned_to__isnull=False)
                    | models.Q(custodian_department__isnull=True)
                ),
                name="asset_department_requires_user",
            ),
        ),
    ]
