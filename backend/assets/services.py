from dataclasses import dataclass
from datetime import date
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Asset, AssetEvent, AssetNumberSequence, AssetStatus, Location

User = get_user_model()


@dataclass(frozen=True)
class AssetActionResult:
    asset: Asset
    event: AssetEvent


ACTION_RULES = {
    "accept": {
        "allowed": {Asset.Status.PENDING},
        "status": Asset.Status.AVAILABLE,
        "event": AssetEvent.Action.ACCEPTED,
    },
    "assign": {
        "allowed": {Asset.Status.AVAILABLE, Asset.Status.INSPECTION},
        "status": Asset.Status.ASSIGNED,
        "event": AssetEvent.Action.ASSIGNED,
    },
    "loan": {
        "allowed": {Asset.Status.AVAILABLE},
        "status": Asset.Status.LOANED,
        "event": AssetEvent.Action.LOANED,
    },
    "return": {
        "allowed": {Asset.Status.ASSIGNED, Asset.Status.LOANED},
        "status": Asset.Status.AVAILABLE,
        "event": AssetEvent.Action.RETURNED,
    },
    "dispose": {
        "allowed": None,
        "status": Asset.Status.DISPOSED,
        "event": AssetEvent.Action.DISPOSED,
    },
}


def _display_status(value):
    configured = AssetStatus.objects.filter(code=value).values_list("name", flat=True).first()
    return configured or dict(Asset.Status.choices).get(value, value)


def asset_tag_year(purchase_date=None, created_at=None):
    if purchase_date:
        return purchase_date.year
    if created_at:
        return created_at.year
    return date.today().year


def generate_asset_tag(category, purchase_date=None):
    year = asset_tag_year(purchase_date=purchase_date)
    sequence, _ = AssetNumberSequence.objects.select_for_update().get_or_create(
        category=category,
        defaults={"current_value": 0},
    )
    while True:
        sequence.current_value += 1
        prefix = "AD" if category.class_type == "ADMIN" else "IT"
        candidate = f"{prefix}-{category.code.upper()}-{year}-{sequence.current_value:03d}"
        if not Asset.objects.filter(asset_tag=candidate).exists():
            sequence.save(update_fields=["current_value"])
            return candidate


def align_asset_tag(asset, *, category_changed=False):
    old_tag = asset.asset_tag
    if category_changed:
        new_tag = generate_asset_tag(asset.category, asset.purchase_date)
    else:
        match = re.search(r"-(\d{3})$", old_tag)
        if match:
            prefix = "AD" if asset.category.class_type == "ADMIN" else "IT"
            year = asset_tag_year(asset.purchase_date, asset.created_at)
            new_tag = f"{prefix}-{asset.category.code.upper()}-{year}-{match.group(1)}"
            if Asset.objects.exclude(pk=asset.pk).filter(asset_tag=new_tag).exists():
                new_tag = generate_asset_tag(asset.category, asset.purchase_date)
        else:
            new_tag = generate_asset_tag(asset.category, asset.purchase_date)

    if new_tag == old_tag:
        return old_tag, new_tag

    custom_data = dict(asset.custom_data)
    previous_tags = list(custom_data.get("previous_asset_tags", []))
    if old_tag not in previous_tags:
        previous_tags.append(old_tag)
    custom_data["previous_asset_tags"] = previous_tags
    asset.asset_tag = new_tag
    asset.custom_data = custom_data
    asset.save(update_fields=["asset_tag", "custom_data", "updated_at"])
    return old_tag, new_tag


@transaction.atomic
def perform_asset_action(
    *,
    asset: Asset,
    action: str,
    actor: User,
    target_user: User | None = None,
    target_location: Location | None = None,
    expected_return_at: date | None = None,
    notes: str = "",
    requires_inspection: bool = False,
    send_notification: bool = True,
) -> AssetActionResult:
    locked = Asset.objects.select_for_update().get(pk=asset.pk)

    if action == "transfer":
        if locked.status in {Asset.Status.DISPOSED, Asset.Status.RETIRED}:
            raise ValidationError({"action": "报废资产不能调拨。"})
        if target_location is None:
            raise ValidationError({"target_location_id": "调拨时必须选择目标地点。"})
        event_action = AssetEvent.Action.TRANSFERRED
        next_status = locked.status
    else:
        rule = ACTION_RULES.get(action)
        if rule is None:
            raise ValidationError({"action": "不支持这个资产动作。"})
        if rule["allowed"] is not None and locked.status not in rule["allowed"]:
            raise ValidationError(
                {
                    "action": (
                        f"资产当前为“{_display_status(locked.status)}”，"
                        f"不能执行这个操作。"
                    )
                }
            )
        event_action = rule["event"]
        next_status = rule["status"]

    if action in {"assign", "loan"} and target_user is None:
        raise ValidationError({"target_user_id": "领用或借用时必须选择责任人。"})
    if action == "loan" and expected_return_at is None:
        raise ValidationError({"expected_return_at": "借用时必须填写预计归还日期。"})
    if expected_return_at and expected_return_at < date.today():
        raise ValidationError({"expected_return_at": "预计归还日期不能早于今天。"})

    before_status = locked.status
    before_user = locked.assigned_to
    before_location = locked.current_location

    if action in {"assign", "loan"}:
        locked.assigned_to = target_user
        locked.expected_return_at = expected_return_at if action == "loan" else None
        profile = getattr(target_user, "employee_profile", None)
        if profile and profile.department:
            locked.custodian_department = profile.department
    elif action in {"return", "dispose"}:
        locked.assigned_to = None
        locked.expected_return_at = None

    if action == "return" and requires_inspection:
        next_status = Asset.Status.INSPECTION
    if target_location is not None:
        locked.current_location = target_location

    locked.status = next_status
    locked.save()

    event = AssetEvent.objects.create(
        asset=locked,
        action=event_action,
        from_status=before_status,
        to_status=next_status,
        from_user=before_user,
        to_user=locked.assigned_to,
        from_location=before_location,
        to_location=locked.current_location,
        actor=actor,
        notes=notes,
        metadata={"requires_inspection": requires_inspection} if action == "return" else {},
    )
    if send_notification:
        from .notifications import notify_asset_action

        notify_asset_action(event)
    return AssetActionResult(asset=locked, event=event)
