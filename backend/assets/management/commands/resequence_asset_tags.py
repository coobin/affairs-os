import csv
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assets.models import Asset, AssetEvent, AssetNumberSequence
from assets.services import asset_tag_year


def build_mapping(assets):
    counters = defaultdict(int)
    mapping = []
    for asset in assets:
        counters[asset.category_id] += 1
        sequence = counters[asset.category_id]
        if sequence > 999:
            raise CommandError(
                f"资产类型“{asset.category.name}”超过 999 件，三位流水号不足。"
            )
        prefix = "AD" if asset.category.class_type == "ADMIN" else "IT"
        year = asset_tag_year(asset.purchase_date, asset.created_at)
        new_tag = f"{prefix}-{asset.category.code.upper()}-{year}-{sequence:03d}"
        mapping.append((asset, asset.asset_tag, new_tag))
    return mapping, counters


def write_mapping(output_path, mapping):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["资产ID", "资产名称", "原资产编号", "新资产编号"])
        for asset, old_tag, new_tag in mapping:
            writer.writerow([asset.pk, asset.name, old_tag, new_tag])


class Command(BaseCommand):
    help = "按系统规则重新生成全部资产编号，并同步编号流水。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--output", help="旧编号与新编号对照 CSV 的保存路径。")

    def handle(self, *args, **options):
        with transaction.atomic():
            assets = list(
                Asset.objects.select_for_update()
                .select_related("category")
                .order_by("category_id", "id")
            )
            assets.sort(
                key=lambda asset: (
                    asset.category_id,
                    asset.purchase_date is None,
                    asset.purchase_date or asset.created_at.date(),
                    asset.created_at,
                    asset.id,
                )
            )
            mapping, counters = build_mapping(assets)
            new_tags = [new_tag for _, _, new_tag in mapping]
            if len(new_tags) != len(set(new_tags)):
                raise CommandError("生成的新资产编号存在重复，已取消操作。")

            if not options["dry_run"]:
                for asset, _, _ in mapping:
                    Asset.objects.filter(pk=asset.pk).update(asset_tag=f"TMP-{uuid4().hex}")

                for asset, old_tag, new_tag in mapping:
                    custom_data = dict(asset.custom_data)
                    previous_tags = list(custom_data.get("previous_asset_tags", []))
                    if old_tag not in previous_tags:
                        previous_tags.append(old_tag)
                    custom_data["previous_asset_tags"] = previous_tags
                    asset.asset_tag = new_tag
                    asset.custom_data = custom_data
                    asset.save(update_fields=["asset_tag", "custom_data", "updated_at"])
                    AssetEvent.objects.create(
                        asset=asset,
                        action=AssetEvent.Action.UPDATED,
                        from_status=asset.status,
                        to_status=asset.status,
                        from_user=asset.assigned_to,
                        to_user=asset.assigned_to,
                        from_location=asset.current_location,
                        to_location=asset.current_location,
                        notes="系统统一调整资产编号",
                        metadata={"old_asset_tag": old_tag, "new_asset_tag": new_tag},
                    )

                AssetNumberSequence.objects.all().delete()
                AssetNumberSequence.objects.bulk_create(
                    [
                        AssetNumberSequence(
                            category_id=category_id,
                            current_value=current_value,
                        )
                        for category_id, current_value in counters.items()
                    ]
                )
                if options.get("output"):
                    write_mapping(Path(options["output"]), mapping)

        mode = "预演" if options["dry_run"] else "完成"
        self.stdout.write(self.style.SUCCESS(f"{mode}：共处理 {len(mapping)} 件资产。"))
        for _, old_tag, new_tag in mapping[:10]:
            self.stdout.write(f"{old_tag} -> {new_tag}")
