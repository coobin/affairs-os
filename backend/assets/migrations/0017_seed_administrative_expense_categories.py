from django.db import migrations


DEFAULT_CATEGORIES = (
    ("VEHICLE", "车辆费用"),
    ("PURCHASE", "行政采购"),
    ("OFFICE", "办公费用"),
    ("PROPERTY", "物业与租赁"),
    ("SERVICE", "行政服务"),
    ("CONTRACT", "合同费用"),
    ("OTHER", "其他行政费用"),
)


def seed_categories(apps, schema_editor):
    category_model = apps.get_model("assets", "ExpenseCategory")
    for code, name in DEFAULT_CATEGORIES:
        category_model.objects.get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("assets", "0016_expensecategory_supplier_contract_purchaseorder_and_more")]

    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
