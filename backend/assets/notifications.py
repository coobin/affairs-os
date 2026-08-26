import hashlib
import logging
from collections.abc import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (
    Asset,
    AssetEvent,
    AssetRequest,
    Contract,
    EmailNotification,
    InventoryTransaction,
    PurchaseRequest,
    Vehicle,
    VehicleDispatch,
)
from .permissions import HIDDEN_SYSTEM_USERNAME, user_can_manage


logger = logging.getLogger(__name__)
User = get_user_model()


def notification_manager_users(*modules):
    users = (
        User.objects.filter(is_active=True)
        .exclude(email="")
        .exclude(username__iexact=HIDDEN_SYSTEM_USERNAME)
        .select_related("asset_manager_role")
    )
    return [
        user
        for user in users
        if any(user_can_manage(user, module) for module in modules)
    ]


def _display_name(user):
    return user.get_full_name() or user.username


def _dispatch_notification(notification_id):
    try:
        from .tasks import send_email_notification

        send_email_notification.delay(notification_id)
    except Exception:
        logger.exception("Unable to enqueue email notification %s", notification_id)


def queue_email_notification(*, event_key, event_type, recipients: Iterable, subject, body):
    if not settings.EMAIL_NOTIFICATIONS_ENABLED or not settings.EMAIL_HOST:
        return []

    created_notifications = []
    seen_emails = set()
    footer = f"\n\n查看行政资产管理系统：{settings.FRONTEND_URL.rstrip('/')}"
    for recipient in recipients:
        email = str(getattr(recipient, "email", "") or "").strip().lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
        delivery_key = f"{event_key}:{email_hash}"[:255]
        notification, created = EmailNotification.objects.get_or_create(
            event_key=delivery_key,
            defaults={
                "event_type": event_type,
                "recipient_user": recipient if getattr(recipient, "pk", None) else None,
                "recipient_email": email,
                "subject": f"{settings.EMAIL_SUBJECT_PREFIX}{subject}"[:255],
                "body": f"{body.rstrip()}{footer}",
            },
        )
        if created:
            created_notifications.append(notification)
            transaction.on_commit(
                lambda notification_id=notification.pk: _dispatch_notification(notification_id)
            )
    return created_notifications


def queue_user_inactive_reminder(user, *, event_key, subject=None, require_open_items=False):
    """员工账号停用（疑似离职）时提醒管理员办理交接；未办结时可每日重复提醒。"""
    from .permissions import HIDDEN_SYSTEM_USERNAME

    if user.username and user.username.casefold() == HIDDEN_SYSTEM_USERNAME.casefold():
        return False

    display_name = _display_name(user)
    profile = getattr(user, "employee_profile", None)
    identity_parts = []
    if profile and profile.employee_no:
        identity_parts.append(f"工号：{profile.employee_no}")
    if profile and profile.department:
        identity_parts.append(f"部门：{profile.department.name}")
    identity = f"{display_name}（{' · '.join(identity_parts)}）" if identity_parts else display_name

    assets = Asset.objects.filter(assigned_to=user)
    held_assets = list(
        assets.exclude(status__in=[Asset.Status.AVAILABLE, Asset.Status.DISPOSED])
        .order_by("asset_tag")
    )
    contract_count = Contract.objects.filter(owner=user).count()
    vehicle_count = Vehicle.objects.filter(custodian=user).count()
    if require_open_items and not (held_assets or contract_count or vehicle_count):
        return False

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
        event_key=event_key,
        event_type="user_deactivated",
        recipients=notification_manager_users("assets", "inventory", "contracts", "vehicles"),
        subject=subject or f"员工离职提醒：{display_name}",
        body=(
            f"{identity} 的账号已停用，系统检测到该员工可能已离职，请及时办理交接。\n\n"
            f"名下资产共 {assets.count()} 件，其中未归还/未处理 {len(held_assets)} 件：\n"
            f"{asset_lines}\n\n"
            f"名下合同 {contract_count} 份，名下车辆 {vehicle_count} 辆。\n\n"
            "请检查以上事项，并在系统中完成资产归还、转交或负责人变更。"
        ),
    )
    return True


def notify_request_submitted(asset_request: AssetRequest):
    requester_name = _display_name(asset_request.requester)
    request_label = asset_request.get_request_type_display()
    return_date = (
        f"\n预计归还：{asset_request.expected_return_at:%Y-%m-%d}"
        if asset_request.expected_return_at
        else ""
    )
    needed_date = (
        f"\n领用时间：{asset_request.needed_at:%Y-%m-%d}"
        if asset_request.needed_at
        else ""
    )
    quantity = (
        f"\n申请数量：{asset_request.requested_quantity} {asset_request.inventory_item.unit}"
        if asset_request.requested_item_type == AssetRequest.ItemType.INVENTORY and asset_request.inventory_item
        else ""
    )
    item_label = "库存物品" if asset_request.requested_item_type == AssetRequest.ItemType.INVENTORY else "资产类型"
    queue_email_notification(
        event_key=f"asset-request:{asset_request.pk}:submitted:managers",
        event_type="request_pending",
        recipients=notification_manager_users("assets", "inventory"),
        subject=f"待处理{request_label}申请：{asset_request.requested_name}",
        body=(
            f"{requester_name} 提交了一条设备{request_label}申请。\n\n"
            f"{item_label}：{asset_request.requested_name}{quantity}{needed_date}{return_date}\n"
            f"用途说明：{asset_request.reason or '未填写'}\n"
            "请进入“领用借用”处理并分配具体设备。"
        ),
    )


def notify_request_processed(asset_request: AssetRequest):
    # 普通用户不接收领用、借用审批结果；仅借用超期时提醒用户。
    return []


def notify_request_cancelled(asset_request: AssetRequest):
    queue_email_notification(
        event_key=f"asset-request:{asset_request.pk}:cancelled:managers",
        event_type="request_cancelled",
        recipients=notification_manager_users("assets", "inventory"),
        subject=f"申请已取消：{asset_request.requested_name}",
        body=(
            f"{_display_name(asset_request.requester)} 已取消设备"
            f"{asset_request.get_request_type_display()}申请。\n\n"
            f"设备类型：{asset_request.requested_name}"
        ),
    )


def notify_asset_action(event: AssetEvent):
    # 资产领用、借用不向普通用户发送邮件；归还和借用延期向相关用户发送确认邮件。
    if event.action == AssetEvent.Action.RETURNED:
        previous_user = event.from_user
        if previous_user and previous_user.email:
            asset = event.asset
            return queue_email_notification(
                event_key=f"asset-returned:{event.pk}",
                event_type="asset_returned",
                recipients=[previous_user],
                subject=f"资产归还通知：{asset.asset_tag} · {asset.name}",
                body=(
                    f"{_display_name(previous_user)}，你之前使用的资产已办理归还。\n\n"
                    f"资产：{asset.asset_tag} · {asset.name}\n"
                    f"归还时间：{event.happened_at:%Y-%m-%d %H:%M}\n"
                    f"经办人：{_display_name(event.actor)}\n"
                    f"当前状态：{asset.get_status_display()}\n\n"
                    "如有疑问，请联系资产管理员。"
                ),
            )
    if event.action == AssetEvent.Action.EXTENDED:
        asset = event.asset
        borrower = asset.assigned_to
        if borrower and borrower.email:
            metadata = event.metadata or {}
            from_date = metadata.get("from_return_at") or "未设置"
            to_date = metadata.get("to_return_at")
            if not to_date and asset.expected_return_at:
                to_date = asset.expected_return_at.isoformat()
            return queue_email_notification(
                event_key=f"loan-extended:{event.pk}",
                event_type="loan_extended",
                recipients=[borrower],
                subject=f"借用延期提醒：{asset.asset_tag} · {asset.name}",
                body=(
                    f"{borrower.get_full_name() or borrower.username}，你借用的资产已办理延期。\n\n"
                    f"资产：{asset.asset_tag} · {asset.name}\n"
                    f"原预计归还：{from_date}\n"
                    f"新的预计归还：{to_date or '未设置'}"
                ),
            )
    return []


def notify_inventory_transaction(inventory_transaction: InventoryTransaction):
    # 库存领用和其他库存事务不向普通用户发送邮件。
    return []


def notify_vehicle_dispatch_submitted(dispatch: VehicleDispatch):
    queue_email_notification(
        event_key=f"vehicle-dispatch:{dispatch.pk}:submitted:managers",
        event_type="vehicle_dispatch_pending",
        recipients=notification_manager_users("vehicles"),
        subject=f"待处理用车申请：{dispatch.destination}",
        body=(
            f"{_display_name(dispatch.requester)} 提交了一条用车申请。\n\n"
            f"目的地：{dispatch.destination}\n"
            f"计划时间：{dispatch.planned_departure_at:%Y-%m-%d %H:%M} 至 {dispatch.planned_return_at:%Y-%m-%d %H:%M}\n"
            f"乘车人数：{dispatch.passenger_count}\n用车事由：{dispatch.purpose}\n"
            "请进入“车辆”处理审批和派车。"
        ),
    )


def notify_purchase_request_submitted(purchase_request: PurchaseRequest):
    queue_email_notification(
        event_key=f"purchase-request:{purchase_request.pk}:submitted:managers",
        event_type="purchase_request_pending",
        recipients=notification_manager_users("procurement"),
        subject=f"待审批采购申请：{purchase_request.request_no}",
        body=(
            f"{_display_name(purchase_request.requester)} 提交了一条采购申请。\n\n"
            f"采购用途：{purchase_request.reason}\n预计金额：¥{purchase_request.estimated_amount:.2f}\n"
            f"期望到货：{purchase_request.needed_on or '未指定'}\n"
            "请进入“采购”完成审批。"
        ),
    )
