from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_asset_configuration_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="kingdee_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                verbose_name="金蝶编码",
            ),
        ),
        migrations.CreateModel(
            name="AssetNumberSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveSmallIntegerField(verbose_name="年份")),
                (
                    "current_value",
                    models.PositiveIntegerField(default=0, verbose_name="当前流水号"),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="assets.assetcategory",
                        verbose_name="资产分类",
                    ),
                ),
            ],
            options={
                "verbose_name": "资产编号流水",
                "verbose_name_plural": "资产编号流水",
            },
        ),
        migrations.AddConstraint(
            model_name="assetnumbersequence",
            constraint=models.UniqueConstraint(
                fields=("category", "year"),
                name="asset_sequence_category_year_unique",
            ),
        ),
    ]
