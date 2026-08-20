from django.core.management.base import BaseCommand
from django.db import transaction

from assets.contract_amounts import amount_from_description
from assets.models import Contract


class Command(BaseCommand):
    help = "将仅含单一明确金额的费用说明补录到合同金额"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="统计后回滚，不修改数据")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        skipped = 0
        with transaction.atomic():
            contracts = Contract.objects.select_for_update().filter(amount=0).exclude(
                amount_description=""
            )
            for contract in contracts.iterator():
                amount = amount_from_description(contract.amount_description)
                if amount is None:
                    skipped += 1
                    continue
                contract.amount = amount
                contract.save(update_fields=["amount", "updated_at"])
                updated += 1
            if dry_run:
                transaction.set_rollback(True)

        mode = "预演" if dry_run else "完成"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}：补录 {updated} 份合同；保留 {skipped} 份含单价、周期、比例或不确定说明的合同。"
            )
        )
