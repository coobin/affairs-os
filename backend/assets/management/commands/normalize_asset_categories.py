from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assets.models import Asset, AssetCategory


FINAL_CATEGORY_CODES = {
    "笔记本电脑": "LT",
    "台式机": "DT",
    "显示屏": "MN",
    "会议设备": "AV",
    "网络设备": "NW",
    "服务器": "SV",
}


class Command(BaseCommand):
    help = "合并现有 IT 资产分类，统一分类编码，并按采购日期重新生成资产编号。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def _category(self, name):
        try:
            return AssetCategory.objects.select_for_update().get(name=name)
        except AssetCategory.DoesNotExist as exc:
            raise CommandError(f"缺少资产分类“{name}”，已取消操作。") from exc

    def _already_normalized(self):
        for name, code in FINAL_CATEGORY_CODES.items():
            if not AssetCategory.objects.filter(
                name=name,
                code=code,
                is_active=True,
            ).exists():
                return False
        return not AssetCategory.objects.filter(
            name__in=["AP", "交换机", "显示器", "录像机"]
        ).exists()

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with transaction.atomic():
            if self._already_normalized():
                self.stdout.write(self.style.SUCCESS("资产分类已经完成规范化，无需重复处理。"))
                return

            notebook = self._category("笔记本电脑")
            desktop = self._category("台式机")
            display = self._category("显示屏")
            monitor = self._category("显示器")
            meeting = self._category("会议设备")
            server = self._category("服务器")
            recorder = self._category("录像机")
            access_point = self._category("AP")
            network = AssetCategory.objects.select_for_update().filter(
                name__in=["网络设备", "交换机"]
            ).first()
            if network is None:
                raise CommandError("缺少资产分类“交换机”，已取消操作。")

            targets = [notebook, desktop, display, meeting, network, server]
            for category in targets:
                category.code = f"TMP{category.pk}"
                category.save(update_fields=["code", "updated_at"])

            network.name = "网络设备"
            normalized_targets = {
                notebook: "LT",
                desktop: "DT",
                display: "MN",
                meeting: "AV",
                network: "NW",
                server: "SV",
            }
            for category, code in normalized_targets.items():
                category.code = code
                category.is_active = True
                category.save(update_fields=["name", "code", "is_active", "updated_at"])

            merge_pairs = [
                (access_point, network),
                (monitor, display),
                (recorder, server),
            ]
            merge_counts = []
            for source, target in merge_pairs:
                count = Asset.objects.filter(category=source).update(category=target)
                source_name = source.name
                source.delete()
                merge_counts.append((source_name, target.name, count))

            call_command(
                "resequence_asset_tags",
                dry_run=dry_run,
                discard_old_tags=True,
                stdout=self.stdout,
            )

            if dry_run:
                transaction.set_rollback(True)

        mode = "预演" if dry_run else "完成"
        summary = "；".join(
            f"{source} → {target}（{count} 件）"
            for source, target, count in merge_counts
        )
        self.stdout.write(self.style.SUCCESS(f"{mode}：{summary}。"))
