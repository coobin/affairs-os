from datetime import date

from django.db import migrations, models


def consolidate_sequences(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    AssetNumberSequence = apps.get_model("assets", "AssetNumberSequence")
    category_ids = list(
        AssetNumberSequence.objects.values_list("category_id", flat=True).distinct()
    )
    for category_id in category_ids:
        rows = list(
            AssetNumberSequence.objects.filter(category_id=category_id).order_by("id")
        )
        keeper = rows[0]
        previous_total = sum(row.current_value for row in rows)
        asset_count = Asset.objects.filter(category_id=category_id).count()
        AssetNumberSequence.objects.filter(category_id=category_id).exclude(
            pk=keeper.pk
        ).delete()
        keeper.year = 0
        keeper.current_value = max(previous_total, asset_count)
        keeper.save(update_fields=["year", "current_value"])


def restore_year_value(apps, schema_editor):
    AssetNumberSequence = apps.get_model("assets", "AssetNumberSequence")
    AssetNumberSequence.objects.update(year=date.today().year)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0021_separate_asset_requestability_and_invoice"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="assetnumbersequence",
            name="asset_sequence_category_year_unique",
        ),
        migrations.RunPython(consolidate_sequences, restore_year_value),
        migrations.AlterField(
            model_name="assetnumbersequence",
            name="year",
            field=models.PositiveSmallIntegerField(
                default=0,
                editable=False,
                verbose_name="兼容年份",
            ),
        ),
        migrations.AddConstraint(
            model_name="assetnumbersequence",
            constraint=models.UniqueConstraint(
                fields=("category",),
                name="asset_sequence_category_unique",
            ),
        ),
    ]
