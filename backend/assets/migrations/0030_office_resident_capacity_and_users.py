import re

from django.conf import settings
from django.db import migrations, models


def match_existing_residents(apps, schema_editor):
    Office = apps.get_model("assets", "Office")
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".")[0], settings.AUTH_USER_MODEL.split(".")[1])
    users = list(User.objects.filter(is_active=True, employee_profile__isnull=False))
    by_name = {}
    for user in users:
        full_name = user.get_full_name() or ""
        for value in (full_name, user.username, getattr(user.employee_profile, "employee_no", "")):
            key = re.sub(r"\s+", "", value or "").casefold()
            if key:
                by_name[key] = user

    for office in Office.objects.all():
        tokens = [
            token for token in re.split(r"[、,，;；\s]+", office.residents or "") if token
        ]
        matched = []
        for token in tokens:
            user = by_name.get(re.sub(r"\s+", "", token).casefold())
            if user and user not in matched:
                matched.append(user)
        office.resident_users.set(matched)
        if tokens and "流动" not in (office.residents or ""):
            office.resident_count = len(tokens)
            office.save(update_fields=["resident_count", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0029_office_contract_amount_description_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="office",
            old_name="resident_count",
            new_name="resident_capacity",
        ),
        migrations.AlterField(
            model_name="office",
            name="resident_capacity",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="可住人数"
            ),
        ),
        migrations.AddField(
            model_name="office",
            name="resident_count",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="实际居住人数"
            ),
        ),
        migrations.AddField(
            model_name="office",
            name="resident_users",
            field=models.ManyToManyField(
                blank=True,
                related_name="residential_offices",
                to=settings.AUTH_USER_MODEL,
                verbose_name="居住员工",
            ),
        ),
        migrations.RunPython(match_existing_residents, migrations.RunPython.noop),
    ]
