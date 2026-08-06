from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
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
