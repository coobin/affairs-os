from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

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

    from .notifications import queue_user_inactive_reminder

    queue_user_inactive_reminder(
        instance,
        event_key=f"user-inactive:{instance.pk}",
    )


@receiver(post_save, sender="assets.EmployeeProfile")
def sync_assigned_assets_department(sender, instance, **kwargs):
    """人员部门变化后，所有名下资产同步跟随，且允许同步清空。"""
    from .models import Asset

    Asset.objects.filter(assigned_to=instance.user).exclude(
        custodian_department_id=instance.department_id,
    ).update(custodian_department_id=instance.department_id)
