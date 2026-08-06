from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Asset, Contract, Vehicle

User = get_user_model()


@receiver(pre_save, sender=User)
def notify_user_deactivated(sender, instance, **kwargs):
    """账号由启用变为停用时，立即提醒管理员该员工可能离职并需办理交接。"""
    if instance.pk is None or instance.is_active:
        return
    try:
        previous = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return
    if not previous.is_active:
        return

    from .notifications import notification_manager_users, queue_email_notification

    profile = getattr(instance, "employee_profile", None)
    display_name = instance.get_full_name() or instance.username
    identity_parts = []
    if profile and profile.employee_no:
        identity_parts.append(f"工号：{profile.employee_no}")
    if profile and profile.department:
        identity_parts.append(f"部门：{profile.department.name}")
    identity = f"{display_name}（{' · '.join(identity_parts)}）" if identity_parts else display_name

    assets = Asset.objects.filter(assigned_to=instance)
    held_assets = list(
        assets.exclude(status__in=[Asset.Status.AVAILABLE, Asset.Status.DISPOSED])
        .order_by("asset_tag")
    )
    contract_count = Contract.objects.filter(owner=instance).count()
    vehicle_count = Vehicle.objects.filter(custodian=instance).count()

    if held_assets:
        asset_lines = "\n".join(
            f"- {asset.asset_tag} · {asset.name}（{asset.get_status_display()}"
            + (f"，应还 {asset.expected_return_at:%Y-%m-%d}" if asset.expected_return_at else "")
            + "）"
            for asset in held_assets
        )
    else:
        asset_lines = "名下没有未归还的资产。"

    queue_email_notification(
        event_key=f"user-inactive:{instance.pk}",
        event_type="user_deactivated",
        recipients=notification_manager_users("assets", "inventory", "contracts", "vehicles"),
        subject=f"员工离职提醒：{display_name}",
        body=(
            f"{identity} 的账号已停用，系统检测到该员工可能已离职，请及时办理交接。\n\n"
            f"名下资产共 {assets.count()} 件，其中未归还/未处理 {len(held_assets)} 件：\n"
            f"{asset_lines}\n\n"
            f"名下合同 {contract_count} 份，名下车辆 {vehicle_count} 辆。\n\n"
            "请检查以上事项，并在系统中完成资产归还、转交或负责人变更。"
        ),
    )
