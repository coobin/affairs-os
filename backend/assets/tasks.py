import logging
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Asset, Contract, EmailNotification, Vehicle
from .permissions import HIDDEN_SYSTEM_USERNAME


User = get_user_model()


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4)
def send_email_notification(self, notification_id):
    stale_before = timezone.now() - timedelta(minutes=15)
    with transaction.atomic():
        notification = EmailNotification.objects.select_for_update().get(pk=notification_id)
        if notification.status == EmailNotification.Status.SENT:
            return "already-sent"
        if (
            notification.status == EmailNotification.Status.PROCESSING
            and notification.updated_at >= stale_before
        ):
            return "already-processing"
        notification.status = EmailNotification.Status.PROCESSING
        notification.attempts += 1
        notification.last_error = ""
        notification.save(update_fields=["status", "attempts", "last_error", "updated_at"])

    try:
        send_mail(
            notification.subject,
            notification.body,
            settings.DEFAULT_FROM_EMAIL,
            [notification.recipient_email],
            fail_silently=False,
        )
    except Exception as exc:
        EmailNotification.objects.filter(pk=notification_id).update(
            status=EmailNotification.Status.FAILED,
            last_error=str(exc)[:2000],
            updated_at=timezone.now(),
        )
        logger.exception("Email notification %s failed", notification_id)
        raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 900))

    EmailNotification.objects.filter(pk=notification_id).update(
        status=EmailNotification.Status.SENT,
        sent_at=timezone.now(),
        last_error="",
        updated_at=timezone.now(),
    )
    return "sent"


@shared_task
def retry_pending_email_notifications():
    stale_before = timezone.now() - timedelta(minutes=15)
    notification_ids = list(
        EmailNotification.objects.filter(attempts__lt=5)
        .filter(
            Q(status__in=[EmailNotification.Status.PENDING, EmailNotification.Status.FAILED])
            | Q(status=EmailNotification.Status.PROCESSING, updated_at__lt=stale_before)
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:100]
    )
    for notification_id in notification_ids:
        send_email_notification.delay(notification_id)
    return len(notification_ids)


@shared_task
def send_daily_operational_notifications():
    today = timezone.localdate()
    Contract.objects.filter(
        status=Contract.Status.ACTIVE,
        end_date__lt=today,
    ).update(status=Contract.Status.EXPIRED, updated_at=timezone.now())
    if not settings.EMAIL_NOTIFICATIONS_ENABLED or not settings.EMAIL_HOST:
        return {"overdue": 0, "low_stock": 0, "vehicle_due": 0, "contract_due": 0, "user_inactive": 0}

    from .notifications import notification_manager_users, queue_email_notification, queue_user_inactive_reminder

    inactive_users = User.objects.filter(is_active=False).exclude(
        username__iexact=HIDDEN_SYSTEM_USERNAME,
    )
    user_inactive_count = 0
    for user in inactive_users:
        display_name = user.get_full_name() or user.username
        if queue_user_inactive_reminder(
            user,
            event_key=f"daily-user-inactive:{today}:{user.pk}",
            subject=f"离职交接提醒：{display_name}（未完成）",
            require_open_items=True,
        ):
            user_inactive_count += 1

    due_assets = list(
        Asset.objects.filter(
            status=Asset.Status.LOANED,
            expected_return_at__lt=today + timedelta(days=1),
            assigned_to__isnull=False,
        ).select_related("assigned_to", "category", "current_location")
    )
    due_today_by_user = defaultdict(list)
    overdue_by_user = defaultdict(list)
    for asset in due_assets:
        bucket = (
            due_today_by_user
            if asset.expected_return_at == today
            else overdue_by_user
        )
        bucket[asset.assigned_to].append(asset)
    due_today_assets = [asset for group in due_today_by_user.values() for asset in group]
    overdue_assets = [asset for group in overdue_by_user.values() for asset in group]

    for user, assets in due_today_by_user.items():
        lines = "\n".join(
            f"- {asset.asset_tag} · {asset.name}，应于 {asset.expected_return_at:%Y-%m-%d} 归还"
            for asset in assets
        )
        queue_email_notification(
            event_key=f"daily-due-today:{today}:user:{user.pk}",
            event_type="loan_due_today",
            recipients=[user],
            subject=f"你有 {len(assets)} 件借用资产今天到期",
            body=(
                f"{user.get_full_name() or user.username}，以下借用资产今天到期：\n\n"
                f"{lines}\n\n请按时归还或联系管理员办理续借。"
            ),
        )

    if due_today_assets:
        manager_lines = "\n".join(
            f"- {asset.asset_tag} · {asset.name} · "
            f"{asset.assigned_to.get_full_name() or asset.assigned_to.username} · "
            f"应还 {asset.expected_return_at:%Y-%m-%d}"
            for asset in due_today_assets
        )
        queue_email_notification(
            event_key=f"daily-due-today:{today}:managers",
            event_type="loan_due_today_summary",
            recipients=notification_manager_users("assets", "inventory"),
            subject=f"借用到期提醒：今天共 {len(due_today_assets)} 件到期",
            body=f"当前有以下借用资产今天到期：\n\n{manager_lines}\n\n请提醒相关责任人按时归还或办理续借。",
        )

    for user, assets in overdue_by_user.items():
        lines = "\n".join(
            f"- {asset.asset_tag} · {asset.name}，应于 {asset.expected_return_at:%Y-%m-%d} 归还"
            for asset in assets
        )
        queue_email_notification(
            event_key=f"daily-overdue:{today}:user:{user.pk}",
            event_type="loan_overdue",
            recipients=[user],
            subject=f"你有 {len(assets)} 件借用资产已经超期",
            body=(
                f"{user.get_full_name() or user.username}，以下借用资产已经超过预计归还日期：\n\n"
                f"{lines}\n\n请尽快联系管理员办理归还。"
            ),
        )

    if overdue_assets:
        manager_lines = "\n".join(
            f"- {asset.asset_tag} · {asset.name} · "
            f"{asset.assigned_to.get_full_name() or asset.assigned_to.username} · "
            f"应还 {asset.expected_return_at:%Y-%m-%d}"
            for asset in overdue_assets
        )
        queue_email_notification(
            event_key=f"daily-overdue:{today}:managers",
            event_type="loan_overdue_summary",
            recipients=notification_manager_users("assets", "inventory"),
            subject=f"借用超期提醒：共 {len(overdue_assets)} 件",
            body=f"当前有以下借用资产超期：\n\n{manager_lines}\n\n请联系相关责任人处理。",
        )

    vehicle_due = list(
        Vehicle.objects.filter(
            Q(insurance_expires_at__lte=today + timedelta(days=30))
            | Q(inspection_expires_at__lte=today + timedelta(days=30))
        ).exclude(status=Vehicle.Status.RETIRED).select_related("custodian")
    )
    for vehicle in vehicle_due:
        recipients = notification_manager_users("vehicles")
        if vehicle.custodian:
            recipients = [*recipients, vehicle.custodian]
        due_parts = []
        if vehicle.insurance_expires_at and vehicle.insurance_expires_at <= today + timedelta(days=30):
            due_parts.append(f"保险到期：{vehicle.insurance_expires_at:%Y-%m-%d}")
        if vehicle.inspection_expires_at and vehicle.inspection_expires_at <= today + timedelta(days=30):
            due_parts.append(f"年检到期：{vehicle.inspection_expires_at:%Y-%m-%d}")
        queue_email_notification(
            event_key=f"daily-vehicle-due:{today}:{vehicle.pk}",
            event_type="vehicle_document_due",
            recipients=recipients,
            subject=f"车辆证照到期提醒：{vehicle.plate_number}",
            body=f"{vehicle.plate_number} · {vehicle.name}\n\n" + "\n".join(due_parts) + "\n\n请及时办理续保或年检。",
        )

    contract_due = [
        contract
        for contract in Contract.objects.filter(
            status__in=[Contract.Status.ACTIVE, Contract.Status.EXPIRED],
            end_date__isnull=False,
        ).select_related("owner", "supplier")
        if contract.end_date <= today + timedelta(days=contract.renewal_notice_days)
    ]
    for contract in contract_due:
        recipients = notification_manager_users("contracts")
        if contract.owner:
            recipients = [*recipients, contract.owner]
        queue_email_notification(
            event_key=f"daily-contract-due:{today}:{contract.pk}",
            event_type="contract_expiry",
            recipients=recipients,
            subject=f"合同到期提醒：{contract.name}",
            body=(
                f"合同编号：{contract.contract_no}\n合同名称：{contract.name}\n"
                f"供应商：{contract.supplier.name if contract.supplier else '未设置'}\n"
                f"到期日期：{contract.end_date:%Y-%m-%d}\n\n请确认续签、结束或终止处理。"
            ),
        )

    return {
        "overdue": len(overdue_assets),
        "low_stock": 0,
        "vehicle_due": len(vehicle_due),
        "contract_due": len(contract_due),
        "user_inactive": user_inactive_count,
    }
