from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="specification",
            field=models.CharField(blank=True, max_length=255, verbose_name="主要配置"),
        ),
        migrations.AddField(
            model_name="asset",
            name="cpu",
            field=models.CharField(blank=True, max_length=120, verbose_name="CPU"),
        ),
        migrations.AddField(
            model_name="asset",
            name="memory",
            field=models.CharField(blank=True, max_length=80, verbose_name="内存"),
        ),
        migrations.AddField(
            model_name="asset",
            name="storage",
            field=models.CharField(blank=True, max_length=120, verbose_name="硬盘"),
        ),
        migrations.AddField(
            model_name="asset",
            name="wired_mac",
            field=models.CharField(blank=True, max_length=32, verbose_name="有线 MAC 地址"),
        ),
        migrations.AddField(
            model_name="asset",
            name="wireless_mac",
            field=models.CharField(blank=True, max_length=32, verbose_name="无线 MAC 地址"),
        ),
    ]
