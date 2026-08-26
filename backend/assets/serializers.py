from datetime import date
import re
import uuid
from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import (
    Asset,
    AssetCategory,
    AssetEvent,
    AssetImage,
    AssetManagerRole,
    AssetRequest,
    AssetStatus,
    AdministrativeExpense,
    Contract,
    ContractAttachment,
    ContractChange,
    ContractType,
    Department,
    EmployeeProfile,
    ExpenseCategory,
    EmailNotification,
    InventoryItem,
    InventoryTransaction,
    Location,
    Office,
    OperationLog,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    SupplierAttachment,
    StocktakeRecord,
    StocktakeTask,
    Vehicle,
    VehicleDispatch,
    VehicleExpense,
)
from .permissions import HIDDEN_SYSTEM_USERNAME, is_hidden_superuser, management_scopes
from .services import align_asset_tag, generate_asset_tag, perform_asset_action

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("账号或密码不正确。")
        if not user.is_active:
            raise serializers.ValidationError("账号已停用。")
        attrs["user"] = user
        return attrs


class UserOptionSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    employee_no = serializers.CharField(source="employee_profile.employee_no", default="")
    department = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="employee_profile.department.name", default="")
    management_scopes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "employee_no",
            "department",
            "department_name",
            "is_staff",
            "is_superuser",
            "management_scopes",
        )

    def get_display_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_department(self, obj):
        profile = getattr(obj, "employee_profile", None)
        return profile.department_id if profile else None

    def get_management_scopes(self, obj):
        return management_scopes(obj)


class AssetManagerRoleSerializer(serializers.ModelSerializer):
    user = UserOptionSerializer(read_only=True)

    class Meta:
        model = AssetManagerRole
        fields = ("id", "user", "scopes", "updated_at")


class OperationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLog
        fields = (
            "id",
            "username",
            "display_name",
            "module",
            "module_label",
            "action",
            "action_label",
            "target_type",
            "target_id",
            "target_label",
            "method",
            "path",
            "status_code",
            "succeeded",
            "ip_address",
            "occurred_at",
        )
        read_only_fields = fields


EMAIL_EVENT_LABELS = {
    "asset_returned": "资产归还通知",
    "request_pending": "待处理申请",
    "request_cancelled": "申请取消",
    "loan_extended": "借用延期",
    "loan_due_today": "借用当天到期",
    "loan_due_today_summary": "借用当天到期汇总",
    "loan_overdue": "借用超期",
    "loan_overdue_summary": "借用超期汇总",
    "vehicle_document_due": "车辆证照到期",
    "contract_expiry": "合同到期",
    "user_deactivated": "离职交接",
    "vehicle_dispatch_pending": "待处理用车申请",
    "purchase_request_pending": "待审批采购申请",
}


class EmailNotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()
    event_type_label = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EmailNotification
        fields = (
            "id",
            "event_type",
            "event_type_label",
            "recipient_name",
            "recipient_email",
            "subject",
            "body",
            "status",
            "status_label",
            "attempts",
            "last_error",
            "created_at",
            "sent_at",
        )
        read_only_fields = fields

    def get_recipient_name(self, obj):
        if not obj.recipient_user:
            return ""
        return obj.recipient_user.get_full_name() or obj.recipient_user.username

    def get_event_type_label(self, obj):
        return EMAIL_EVENT_LABELS.get(obj.event_type, obj.event_type)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "code", "parent_id", "is_active")


class LocationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Location
        fields = ("id", "name", "code", "kind", "kind_label", "address", "is_active")


class CategorySerializer(serializers.ModelSerializer):
    class_type_label = serializers.CharField(source="get_class_type_display", read_only=True)

    class Meta:
        model = AssetCategory
        fields = ("id", "name", "code", "class_type", "class_type_label", "icon", "description", "custom_fields", "is_active")


class AssetStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetStatus
        fields = ("id", "name", "code", "sort_order", "is_system", "is_active")
        read_only_fields = ("is_system",)

    def validate_code(self, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", value):
            raise serializers.ValidationError("编码需使用 2–32 位小写英文、数字、下划线或短横线。")
        if self.instance and self.instance.is_system and value != self.instance.code:
            raise serializers.ValidationError("系统内置状态的编码不能修改。")
        return value

    def validate(self, attrs):
        if self.instance and self.instance.is_system and attrs.get("is_active") is False:
            raise serializers.ValidationError({"is_active": "系统内置状态不能停用。"})
        return attrs


class InventoryTransactionSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    recipient_name = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryTransaction
        fields = (
            "id",
            "action",
            "action_label",
            "quantity",
            "balance_after",
            "recipient",
            "recipient_name",
            "actor_name",
            "notes",
            "happened_at",
        )

    def get_recipient_name(self, obj):
        return (obj.recipient.get_full_name() or obj.recipient.username) if obj.recipient else ""

    def get_actor_name(self, obj):
        return (obj.actor.get_full_name() or obj.actor.username) if obj.actor else "系统"


class InventoryItemSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    purchase_channel_label = serializers.CharField(
        source="get_purchase_channel_display",
        read_only=True,
    )
    location_name = serializers.CharField(source="location.name", read_only=True, default="")
    low_stock = serializers.SerializerMethodField()
    transactions = InventoryTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "sku",
            "name",
            "kind",
            "kind_label",
            "brand",
            "model_name",
            "unit",
            "unit_price",
            "purchase_channel",
            "purchase_channel_label",
            "quantity",
            "minimum_quantity",
            "location",
            "location_name",
            "notes",
            "is_active",
            "low_stock",
            "transactions",
        )
        read_only_fields = ("quantity",)

    def get_low_stock(self, obj):
        return obj.quantity < obj.minimum_quantity

    @transaction.atomic
    def create(self, validated_data):
        initial_quantity = int(self.initial_data.get("initial_quantity") or 0)
        item = InventoryItem.objects.create(quantity=initial_quantity, **validated_data)
        if initial_quantity:
            InventoryTransaction.objects.create(
                item=item,
                action=InventoryTransaction.Action.INBOUND,
                quantity=initial_quantity,
                balance_after=initial_quantity,
                actor=self.context["request"].user,
                notes="建立库存品时录入期初库存",
            )
        return item


class InventoryActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=InventoryTransaction.Action.choices)
    quantity = serializers.IntegerField(min_value=1)
    recipient_id = serializers.PrimaryKeyRelatedField(
        source="recipient",
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class StocktakeRecordSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    expected_location_name = serializers.CharField(source="expected_location.name", read_only=True, default="")
    expected_user_name = serializers.SerializerMethodField()
    result_label = serializers.CharField(source="get_result_display", read_only=True)

    class Meta:
        model = StocktakeRecord
        fields = (
            "id",
            "asset",
            "asset_tag",
            "asset_name",
            "expected_location_name",
            "expected_user_name",
            "result",
            "result_label",
            "scanned_at",
        )

    def get_expected_user_name(self, obj):
        return (obj.expected_user.get_full_name() or obj.expected_user.username) if obj.expected_user else ""


class StocktakeTaskSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    location_name = serializers.CharField(source="scope_location.name", read_only=True, default="")
    created_by_name = serializers.SerializerMethodField()
    scanned_count = serializers.IntegerField(read_only=True)
    missing_count = serializers.IntegerField(read_only=True)
    records = StocktakeRecordSerializer(many=True, read_only=True)

    class Meta:
        model = StocktakeTask
        fields = (
            "id",
            "name",
            "status",
            "status_label",
            "scope_location",
            "location_name",
            "created_by_name",
            "snapshot_count",
            "scanned_count",
            "missing_count",
            "created_at",
            "completed_at",
            "records",
        )
        read_only_fields = (
            "status",
            "snapshot_count",
            "created_at",
            "completed_at",
        )

    def get_created_by_name(self, obj):
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by else "系统"


class AssetEventSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    actor_name = serializers.SerializerMethodField()
    from_user_name = serializers.SerializerMethodField()
    to_user_name = serializers.SerializerMethodField()
    from_location_name = serializers.CharField(source="from_location.name", default="")
    to_location_name = serializers.CharField(source="to_location.name", default="")

    class Meta:
        model = AssetEvent
        fields = (
            "id",
            "action",
            "action_label",
            "from_status",
            "to_status",
            "actor_name",
            "from_user_name",
            "to_user_name",
            "from_location_name",
            "to_location_name",
            "happened_at",
            "notes",
            "metadata",
        )

    def _user_name(self, user):
        return (user.get_full_name() or user.username) if user else ""

    def get_actor_name(self, obj):
        return self._user_name(obj.actor)

    def get_from_user_name(self, obj):
        return self._user_name(obj.from_user)

    def get_to_user_name(self, obj):
        return self._user_name(obj.to_user)


class AssetImageSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()

    class Meta:
        model = AssetImage
        fields = (
            "id",
            "original_name",
            "content_type",
            "size_bytes",
            "sha256",
            "is_cover",
            "sort_order",
            "uploaded_by_name",
            "content_url",
            "created_at",
        )

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return "系统"
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

    def get_content_url(self, obj):
        return f"/assets/{obj.asset_id}/images/{obj.id}/"


class AssetSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_class_type = serializers.CharField(source="category.class_type", read_only=True)
    category_class_type_label = serializers.CharField(source="category.get_class_type_display", read_only=True)
    location_name = serializers.CharField(source="current_location.name", read_only=True, default="")
    assignee_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="custodian_department.name", read_only=True, default="")
    events = AssetEventSerializer(many=True, read_only=True)
    images = AssetImageSerializer(many=True, read_only=True)
    is_warranty_due = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            "id",
            "asset_tag",
            "kingdee_code",
            "name",
            "category",
            "category_name",
            "category_code",
            "category_class_type",
            "category_class_type_label",
            "brand",
            "model_name",
            "serial_number",
            "specification",
            "cpu",
            "memory",
            "storage",
            "wired_mac",
            "wireless_mac",
            "status",
            "status_label",
            "is_requestable",
            "current_location",
            "location_name",
            "assigned_to",
            "assignee_name",
            "custodian_department",
            "department_name",
            "purchase_date",
            "purchase_cost",
            "warranty_expires_at",
            "expected_return_at",
            "notes",
            "custom_data",
            "last_audited_at",
            "created_at",
            "updated_at",
            "events",
            "images",
            "is_warranty_due",
        )
        read_only_fields = (
            "asset_tag",
            "name",
            "custodian_department",
            "expected_return_at",
        )

    def get_status_label(self, obj):
        labels = self.context.get("_asset_status_labels")
        if labels is None:
            labels = dict(AssetStatus.objects.values_list("code", "name"))
            self.context["_asset_status_labels"] = labels
        return labels.get(obj.status) or dict(Asset.Status.choices).get(obj.status, obj.status)

    def get_assignee_name(self, obj):
        if not obj.assigned_to:
            return ""
        return obj.assigned_to.get_full_name() or obj.assigned_to.username

    def get_is_warranty_due(self, obj):
        if not obj.warranty_expires_at:
            return False
        return 0 <= (obj.warranty_expires_at - date.today()).days <= 90

    def validate_serial_number(self, value):
        value = value.strip()
        if not value:
            return value
        queryset = Asset.objects.filter(serial_number__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("已有资产使用这个序列号。")
        return value

    def validate_status(self, value):
        value = value.strip().lower()
        if not AssetStatus.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("请选择设置中已启用的资产状态。")
        return value

    def validate(self, attrs):
        if "custodian_department" in self.initial_data:
            raise serializers.ValidationError(
                {"custodian_department": "归属部门由责任人自动确定，不允许单独设置。"}
            )
        purchase_date = attrs.get("purchase_date", getattr(self.instance, "purchase_date", None))
        warranty = attrs.get(
            "warranty_expires_at",
            getattr(self.instance, "warranty_expires_at", None),
        )
        if purchase_date and warranty and warranty < purchase_date:
            raise serializers.ValidationError({"warranty_expires_at": "保修到期日不能早于采购日期。"})
        status = attrs.get("status", getattr(self.instance, "status", Asset.Status.AVAILABLE))
        assignee = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        if "assigned_to" in attrs and not assignee and status in {
            Asset.Status.ASSIGNED,
            Asset.Status.LOANED,
        }:
            status = Asset.Status.AVAILABLE
            attrs["status"] = status
        if status in {Asset.Status.ASSIGNED, Asset.Status.LOANED} and not assignee:
            raise serializers.ValidationError({"assigned_to": "使用中或借用中的资产必须选择责任人。"})
        if status in {Asset.Status.AVAILABLE, Asset.Status.DISPOSED}:
            attrs["assigned_to"] = None
            attrs["expected_return_at"] = None
            assignee = None
        profile = getattr(assignee, "employee_profile", None) if assignee else None
        attrs["custodian_department"] = profile.department if profile else None
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        actor = self.context["request"].user
        validated_data["asset_tag"] = generate_asset_tag(
            validated_data["category"],
            validated_data.get("purchase_date"),
        )
        asset = Asset.objects.create(**validated_data)
        AssetEvent.objects.create(
            asset=asset,
            action=AssetEvent.Action.CREATED,
            to_status=asset.status,
            to_location=asset.current_location,
            actor=actor,
            notes="新增资产台账",
        )
        return asset

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["request"].user
        before_status = instance.status
        before_user = instance.assigned_to
        before_location = instance.current_location
        before_category_id = instance.category_id
        before_purchase_date = instance.purchase_date
        before_asset_tag = instance.asset_tag
        changed_fields = {
            field: {"from": getattr(instance, field), "to": value}
            for field, value in validated_data.items()
            if getattr(instance, field) != value
        }
        asset = super().update(instance, validated_data)
        if asset.category_id != before_category_id or asset.purchase_date != before_purchase_date:
            _, new_asset_tag = align_asset_tag(
                asset,
                category_changed=asset.category_id != before_category_id,
            )
            if new_asset_tag != before_asset_tag:
                changed_fields["asset_tag"] = {
                    "from": before_asset_tag,
                    "to": new_asset_tag,
                }
        if changed_fields:
            safe_changes = {
                field: {
                    "from": str(change["from"]) if change["from"] is not None else None,
                    "to": str(change["to"]) if change["to"] is not None else None,
                }
                for field, change in changed_fields.items()
            }
            AssetEvent.objects.create(
                asset=asset,
                action=AssetEvent.Action.UPDATED,
                from_status=before_status,
                to_status=asset.status,
                from_user=before_user,
                to_user=asset.assigned_to,
                from_location=before_location,
                to_location=asset.current_location,
                actor=actor,
                notes=f"更新了 {len(safe_changes)} 项资产信息",
                metadata={"changed_fields": safe_changes},
            )
        return asset


class AssetListSerializer(AssetSerializer):
    class Meta(AssetSerializer.Meta):
        fields = tuple(
            field
            for field in AssetSerializer.Meta.fields
            if field not in {"events", "images", "notes", "custom_data"}
        )


class AssetRequestSerializer(serializers.ModelSerializer):
    request_type_label = serializers.CharField(source="get_request_type_display", read_only=True)
    requested_item_type_label = serializers.CharField(source="get_requested_item_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    requester_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(
        source="requester.employee_profile.department.name",
        read_only=True,
        default="",
    )
    assigned_asset_tag = serializers.CharField(source="assigned_asset.asset_tag", read_only=True, default="")
    assigned_asset_name = serializers.CharField(source="assigned_asset.name", read_only=True, default="")
    handled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AssetRequest
        fields = (
            "id",
            "requester",
            "requester_name",
            "department_name",
            "request_type",
            "request_type_label",
            "requested_item_type",
            "requested_item_type_label",
            "requested_name",
            "reason",
            "needed_at",
            "expected_return_at",
            "requested_quantity",
            "inventory_item",
            "status",
            "status_label",
            "assigned_asset",
            "assigned_asset_tag",
            "assigned_asset_name",
            "issued_inventory_transaction",
            "handled_by_name",
            "handled_at",
            "manager_notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "requester",
            "status",
            "assigned_asset",
            "issued_inventory_transaction",
            "handled_by_name",
            "handled_at",
            "manager_notes",
        )

    def get_requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.username

    def get_handled_by_name(self, obj):
        if not obj.handled_by:
            return ""
        return obj.handled_by.get_full_name() or obj.handled_by.username

    def validate(self, attrs):
        request_type = attrs.get("request_type")
        item_type = attrs.get("requested_item_type", AssetRequest.ItemType.ASSET)
        reason = str(attrs.get("reason") or "").strip()
        needed_at = attrs.get("needed_at")
        required_errors = {}
        if request_type == AssetRequest.RequestType.LOAN and not reason:
            required_errors["reason"] = "请填写用途说明。"
        attrs["reason"] = reason
        if not needed_at:
            required_errors["needed_at"] = "请填写领用时间。"
        if required_errors:
            raise serializers.ValidationError(required_errors)
        if needed_at < date.today():
            raise serializers.ValidationError({"needed_at": "领用时间不能早于今天。"})
        if request_type == AssetRequest.RequestType.LOAN and not attrs.get("expected_return_at"):
            raise serializers.ValidationError({"expected_return_at": "借用设备请填写预计归还日期。"})
        if attrs.get("expected_return_at") and attrs["expected_return_at"] < date.today():
            raise serializers.ValidationError({"expected_return_at": "预计归还日期不能早于今天。"})
        if attrs.get("expected_return_at") and attrs["expected_return_at"] < needed_at:
            raise serializers.ValidationError({"expected_return_at": "预计归还日期不能早于领用时间。"})

        if item_type == AssetRequest.ItemType.INVENTORY:
            if request_type != AssetRequest.RequestType.ASSIGN:
                raise serializers.ValidationError({"requested_item_type": "库存物品只能领用，不能借用。"})
            item = attrs.get("inventory_item")
            if not item or not item.is_active:
                raise serializers.ValidationError({"inventory_item": "请选择有效的库存物品。"})
            quantity = attrs.get("requested_quantity", 1)
            if quantity < 1:
                raise serializers.ValidationError({"requested_quantity": "领用数量至少为 1。"})
            if quantity > item.quantity:
                raise serializers.ValidationError({"requested_quantity": "申请数量不能超过当前库存。"})
            attrs["requested_name"] = item.name
            attrs["expected_return_at"] = None
        else:
            requested_name = str(attrs.get("requested_name") or "").strip()
            if not Asset.objects.filter(
                category__name=requested_name,
                status=Asset.Status.AVAILABLE,
                is_requestable=True,
            ).exists():
                raise serializers.ValidationError({"requested_name": "这种资产当前没有可分配库存。"})
            attrs["requested_name"] = requested_name
            attrs["inventory_item"] = None
            attrs["requested_quantity"] = 1
        return attrs


class AssetActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            "accept",
            "assign",
            "loan",
            "extend",
            "return",
            "transfer",
            "dispose",
        ]
    )
    target_user_id = serializers.PrimaryKeyRelatedField(
        source="target_user",
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    target_location_id = serializers.PrimaryKeyRelatedField(
        source="target_location",
        queryset=Location.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    expected_return_at = serializers.DateField(required=False, allow_null=True)
    requires_inspection = serializers.BooleanField(default=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def save(self, **kwargs):
        return perform_asset_action(
            asset=self.context["asset"],
            actor=self.context["request"].user,
            **self.validated_data,
        )


def _document_no(prefix):
    return f"{prefix}-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "name", "code", "budget_code", "is_active")


class SupplierAttachmentSerializer(serializers.ModelSerializer):
    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()

    class Meta:
        model = SupplierAttachment
        fields = (
            "id", "document_type", "document_type_label", "original_name",
            "content_type", "size_bytes", "sha256", "uploaded_by_name",
            "content_url", "created_at",
        )

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return "系统"
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

    def get_content_url(self, obj):
        return f"/suppliers/{obj.supplier_id}/files/{obj.id}/"


class SupplierSerializer(serializers.ModelSerializer):
    channel_label = serializers.CharField(source="get_channel_display", read_only=True)
    business_license_status_label = serializers.CharField(
        source="get_business_license_status_display", read_only=True
    )
    files = SupplierAttachmentSerializer(source="attachments", many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = (
            "id", "code", "name", "category", "brand_name", "business_scope",
            "cooperation_status", "evaluation", "cooperation_started", "channel",
            "channel_label", "contact_name", "contact_phone", "contact_email",
            "tax_number", "bank_account", "address", "business_license_status",
            "business_license_status_label", "external_id", "notes", "is_active",
            "files", "created_at", "updated_at",
        )


class OfficeSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    contracts = serializers.SerializerMethodField()
    resident_users = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=User.objects.filter(
            is_active=True,
            employee_profile__isnull=False,
        ).exclude(username__iexact=HIDDEN_SYSTEM_USERNAME),
    )
    resident_user_details = UserOptionSerializer(
        source="resident_users", many=True, read_only=True
    )
    resident_warnings = serializers.SerializerMethodField()

    class Meta:
        model = Office
        fields = (
            "id", "code", "name", "status", "status_label", "region", "city",
            "address", "room_layout", "area_sqm", "sales_project", "cost_attribution",
            "landlord_name", "landlord_phone", "intermediary_name", "intermediary_phone",
            "intermediary_fee", "intermediary_invoice_status", "monthly_rent",
            "rent_description", "deposit", "deposit_status", "payment_frequency",
            "payment_method", "payment_terms", "latest_payment_period", "paid_period_start",
            "paid_period_end", "latest_payment_date", "next_payment_date",
            "latest_payment_amount", "responsible_name", "responsible_phone", "residents",
            "resident_users", "resident_user_details", "resident_warnings",
            "resident_capacity", "resident_count", "renewal_status", "lease_summary", "current_lease_period",
            "lease_start", "lease_end", "expected_move_out_date", "feedback", "notes",
            "external_id", "contracts", "created_at", "updated_at",
        )

    def get_resident_warnings(self, obj):
        warnings = []
        for user in obj.resident_users.all():
            other_offices = Office.objects.filter(
                resident_users=user,
            ).exclude(pk=obj.pk).exclude(
                status__in=[Office.Status.INACTIVE, Office.Status.CLOSED]
            ).order_by("city", "code")
            if not other_offices.exists():
                continue
            display_name = user.get_full_name() or user.username
            places = "、".join(
                f"{office.city or office.region or '未设置城市'}·{office.name}"
                for office in other_offices
            )
            warnings.append(f"{display_name} 还居住在：{places}")
        return warnings

    def get_contracts(self, obj):
        queryset = obj.contracts.select_related("owner", "contract_type").all()
        request = self.context.get("request")
        if request and not is_hidden_superuser(request.user):
            queryset = queryset.filter(owner=request.user)
        return [
            {
                "id": item.id,
                "contract_no": item.contract_no,
                "name": item.name,
                "contract_type_name": item.contract_type.name if item.contract_type else "",
                "status": item.status,
                "status_label": item.get_status_display(),
                "start_date": item.start_date,
                "end_date": item.end_date,
                "owner_name": (item.owner.get_full_name() or item.owner.username) if item.owner else "",
            }
            for item in queryset
        ]


class ContractTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractType
        fields = ("id", "name", "code", "is_active")


class ContractSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    office_name = serializers.CharField(source="office.name", read_only=True, default="")
    contract_type_name = serializers.CharField(source="contract_type.name", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    owner_name = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    previous_contract_no = serializers.CharField(source="previous_contract.contract_no", read_only=True, default="")
    renewal_contracts = serializers.SerializerMethodField()
    supplement_of = serializers.PrimaryKeyRelatedField(read_only=True)
    supplement_of_no = serializers.CharField(source="supplement_of.contract_no", read_only=True, default="")
    supplement_contracts = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ("id", "contract_no", "name", "contract_type", "contract_type_name", "supplier", "supplier_name", "office", "office_name", "category", "category_name", "department", "department_name", "owner", "owner_name", "status", "status_label", "start_date", "end_date", "amount", "total_amount", "amount_description", "cooperation_duration", "cooperation_type", "party_a", "party_a_contact", "party_a_address", "party_b_contact", "party_b_address", "payment_method", "payment_terms", "invoice_type", "invoice_tax_rate", "service_content", "renewal_notice_days", "auto_renew", "previous_contract", "previous_contract_no", "renewal_contracts", "supplement_of", "supplement_of_no", "supplement_contracts", "kingdee_code", "external_id", "notes", "days_to_expiry", "attachments", "changes", "created_at", "updated_at")
        read_only_fields = ("previous_contract",)

    def get_owner_name(self, obj):
        return (obj.owner.get_full_name() or obj.owner.username) if obj.owner else ""

    def get_days_to_expiry(self, obj):
        return (obj.end_date - date.today()).days if obj.end_date else None

    def _visible_related_contracts(self, related_manager):
        items = list(related_manager.all())
        request = self.context.get("request")
        if request and not is_hidden_superuser(request.user):
            return [item for item in items if item.owner_id == request.user.id]
        return items

    def get_attachments(self, obj):
        return ContractAttachmentSerializer(obj.attachments.all(), many=True).data

    def get_changes(self, obj):
        return ContractChangeSerializer(obj.changes.all(), many=True).data

    def get_renewal_contracts(self, obj):
        return [
            {
                "id": item.id,
                "contract_no": item.contract_no,
                "name": item.name,
                "status": item.status,
                "status_label": item.get_status_display(),
                "start_date": item.start_date,
                "end_date": item.end_date,
            }
            for item in self._visible_related_contracts(obj.renewal_contracts)
        ]

    def get_supplement_contracts(self, obj):
        return [
            {
                "id": item.id,
                "contract_no": item.contract_no,
                "name": item.name,
                "amount": item.amount,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "status": item.status,
                "status_label": item.get_status_display(),
            }
            for item in self._visible_related_contracts(obj.supplement_contracts)
        ]

    def get_total_amount(self, obj):
        total = obj.amount + sum(
            (
                item.amount
                for item in self._visible_related_contracts(obj.supplement_contracts)
            ),
            Decimal("0"),
        )
        return str(total)

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "结束日期不能早于开始日期。"})
        return attrs


class ContractAttachmentSerializer(serializers.ModelSerializer):
    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()
    change_label = serializers.SerializerMethodField()

    class Meta:
        model = ContractAttachment
        fields = (
            "id",
            "document_type",
            "document_type_label",
            "change",
            "change_label",
            "original_name",
            "content_type",
            "size_bytes",
            "sha256",
            "uploaded_by_name",
            "content_url",
            "created_at",
        )

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return "系统"
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

    def get_content_url(self, obj):
        return f"/contracts/{obj.contract_id}/files/{obj.id}/"

    def get_change_label(self, obj):
        if not obj.change:
            return "初始合同"
        return f"{obj.change.changed_on:%Y-%m-%d} · {obj.change.get_change_type_display()}"


class ContractChangeSerializer(serializers.ModelSerializer):
    change_type_label = serializers.CharField(source="get_change_type_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ContractChange
        fields = (
            "id", "change_type", "change_type_label", "changed_on",
            "old_start_date", "new_start_date", "old_end_date", "new_end_date",
            "old_amount", "new_amount", "notes", "created_by_name", "created_at",
        )
        read_only_fields = ("old_start_date", "old_end_date", "old_amount")

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return "系统"
        return obj.created_by.get_full_name() or obj.created_by.username

    def validate(self, attrs):
        change_type = attrs.get("change_type")
        new_start = attrs.get("new_start_date")
        new_end = attrs.get("new_end_date")
        new_amount = attrs.get("new_amount")
        if change_type == ContractChange.ChangeType.SUPPLEMENT:
            if new_amount is None:
                raise serializers.ValidationError({"new_amount": "补充协议必须填写补充金额。"})
            if not new_start or not new_end:
                raise serializers.ValidationError("补充协议必须填写补充合同的开始日期和结束日期。")
            if new_end < new_start:
                raise serializers.ValidationError({"new_end_date": "补充协议结束日期不能早于开始日期。"})
            return attrs
        if change_type == ContractChange.ChangeType.EXTENSION and not new_end:
            raise serializers.ValidationError({"new_end_date": "延期续约必须填写新的结束日期。"})
        if change_type == ContractChange.ChangeType.AMOUNT and new_amount is None:
            raise serializers.ValidationError({"new_amount": "金额调整必须填写新的合同金额。"})
        if not any((new_start, new_end, new_amount is not None, change_type == ContractChange.ChangeType.TERMINATION)):
            raise serializers.ValidationError("请至少填写一项实际变更内容。")
        if new_start and new_end and new_end < new_start:
            raise serializers.ValidationError({"new_end_date": "新结束日期不能早于新开始日期。"})
        return attrs


class VehicleSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    energy_type_label = serializers.CharField(source="get_energy_type_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    custodian_name = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = ("id", "plate_number", "name", "brand", "model_name", "vin", "engine_number", "energy_type", "energy_type_label", "seats", "status", "status_label", "department", "department_name", "custodian", "custodian_name", "purchase_date", "registration_date", "purchase_cost", "company", "use_scope", "insurance_started_at", "current_mileage", "insurance_expires_at", "insurer_name", "inspection_expires_at", "asset_card_code", "asset_number", "handler_name", "supervisor_name", "notes", "created_at", "updated_at")

    def get_custodian_name(self, obj):
        return (obj.custodian.get_full_name() or obj.custodian.username) if obj.custodian else ""


class VehicleDispatchSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    vehicle_label = serializers.SerializerMethodField()
    driver_display = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    handled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VehicleDispatch
        fields = ("id", "request_no", "requester", "requester_name", "department", "department_name", "purpose", "destination", "passenger_count", "planned_departure_at", "planned_return_at", "vehicle", "vehicle_label", "driver", "driver_name", "driver_display", "status", "status_label", "start_mileage", "end_mileage", "actual_departure_at", "actual_return_at", "handled_by", "handled_by_name", "notes", "created_at", "updated_at")
        read_only_fields = ("request_no", "requester", "department", "vehicle", "driver", "driver_name", "status", "start_mileage", "end_mileage", "actual_departure_at", "actual_return_at", "handled_by", "notes")

    def get_requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.username

    def get_vehicle_label(self, obj):
        return str(obj.vehicle) if obj.vehicle else ""

    def get_driver_display(self, obj):
        if obj.driver:
            return obj.driver.get_full_name() or obj.driver.username
        return obj.driver_name

    def get_handled_by_name(self, obj):
        return (obj.handled_by.get_full_name() or obj.handled_by.username) if obj.handled_by else ""

    def validate(self, attrs):
        departure = attrs.get("planned_departure_at")
        returned = attrs.get("planned_return_at")
        if departure and returned and returned <= departure:
            raise serializers.ValidationError({"planned_return_at": "计划返回时间必须晚于出发时间。"})
        if attrs.get("passenger_count", 1) < 1:
            raise serializers.ValidationError({"passenger_count": "乘车人数至少为 1。"})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        profile = getattr(user, "employee_profile", None)
        return VehicleDispatch.objects.create(
            request_no=_document_no("PC"),
            requester=user,
            department=getattr(profile, "department", None),
            **validated_data,
        )


class AdministrativeExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    contract_name = serializers.CharField(source="contract.name", read_only=True, default="")
    amount_type_label = serializers.CharField(source="get_amount_type_display", read_only=True)
    invoice_status_label = serializers.CharField(source="get_invoice_status_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AdministrativeExpense
        fields = ("id", "occurred_on", "fiscal_year", "category", "category_name", "department", "department_name", "supplier", "supplier_name", "contract", "contract_name", "amount_type", "amount_type_label", "amount", "title", "source_type", "source_id", "source_no", "object_label", "invoice_status", "invoice_status_label", "invoice_number", "kingdee_code", "external_id", "sync_status", "created_by", "created_by_name", "notes", "created_at", "updated_at")
        read_only_fields = ("fiscal_year", "source_type", "source_id", "source_no", "created_by", "sync_status")

    def get_created_by_name(self, obj):
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by else "系统"

    def create(self, validated_data):
        return AdministrativeExpense.objects.create(created_by=self.context["request"].user, **validated_data)


class VehicleExpenseSerializer(serializers.ModelSerializer):
    vehicle_label = serializers.CharField(source="vehicle.__str__", read_only=True)
    expense_type_label = serializers.CharField(source="get_expense_type_display", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")

    class Meta:
        model = VehicleExpense
        fields = ("id", "vehicle", "vehicle_label", "expense_type", "expense_type_label", "occurred_on", "amount", "supplier", "supplier_name", "odometer", "next_due_on", "next_due_mileage", "expense", "notes", "created_by", "created_at", "updated_at")
        read_only_fields = ("expense", "created_by")

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        record = VehicleExpense.objects.create(created_by=user, **validated_data)
        category, _ = ExpenseCategory.objects.get_or_create(code="VEHICLE", defaults={"name": "车辆费用"})
        record.expense = AdministrativeExpense.objects.create(
            occurred_on=record.occurred_on,
            fiscal_year=record.occurred_on.year,
            category=category,
            department=record.vehicle.department,
            supplier=record.supplier,
            amount_type=AdministrativeExpense.AmountType.ACTUAL,
            amount=record.amount,
            title=f"{record.get_expense_type_display()} · {record.vehicle.plate_number}",
            source_type="vehicle",
            source_id=record.pk,
            source_no=record.vehicle.plate_number,
            object_label=str(record.vehicle),
            created_by=user,
            notes=record.notes,
        )
        record.save(update_fields=["expense", "updated_at"])
        if record.odometer and record.odometer > record.vehicle.current_mileage:
            record.vehicle.current_mileage = record.odometer
            record.vehicle.save(update_fields=["current_mileage", "updated_at"])
        return record

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.expense:
            expense = instance.expense
            expense.occurred_on = instance.occurred_on
            expense.fiscal_year = instance.occurred_on.year
            expense.amount = instance.amount
            expense.department = instance.vehicle.department
            expense.supplier = instance.supplier
            expense.title = f"{instance.get_expense_type_display()} · {instance.vehicle.plate_number}"
            expense.object_label = str(instance.vehicle)
            expense.notes = instance.notes
            expense.save()
        return instance


class PurchaseRequestItemSerializer(serializers.ModelSerializer):
    line_amount = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequestItem
        fields = ("id", "name", "specification", "quantity", "unit", "estimated_unit_price", "line_amount")

    def get_line_amount(self, obj):
        return obj.quantity * obj.estimated_unit_price


class PurchaseRequestSerializer(serializers.ModelSerializer):
    items = PurchaseRequestItemSerializer(many=True)
    requester_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    handled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = ("id", "request_no", "requester", "requester_name", "department", "department_name", "needed_on", "reason", "status", "status_label", "estimated_amount", "category", "category_name", "handled_by", "handled_by_name", "handled_at", "manager_notes", "items", "created_at", "updated_at")
        read_only_fields = ("request_no", "requester", "department", "status", "estimated_amount", "handled_by", "handled_at", "manager_notes")

    def get_requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.username

    def get_handled_by_name(self, obj):
        return (obj.handled_by.get_full_name() or obj.handled_by.username) if obj.handled_by else ""

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("请至少填写一项采购内容。")
        return value

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items")
        user = self.context["request"].user
        profile = getattr(user, "employee_profile", None)
        instance = PurchaseRequest.objects.create(
            request_no=_document_no("CGSQ"), requester=user,
            department=getattr(profile, "department", None), **validated_data,
        )
        for item in items:
            PurchaseRequestItem.objects.create(request=instance, **item)
        instance.estimated_amount = sum(item.quantity * item.estimated_unit_price for item in instance.items.all())
        instance.save(update_fields=["estimated_amount", "updated_at"])
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items is not None:
            instance.items.all().delete()
            for item in items:
                PurchaseRequestItem.objects.create(request=instance, **item)
            instance.estimated_amount = sum(item.quantity * item.estimated_unit_price for item in instance.items.all())
            instance.save(update_fields=["estimated_amount", "updated_at"])
        return instance


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    line_amount = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderItem
        fields = ("id", "name", "specification", "quantity", "unit", "unit_price", "line_amount")

    def get_line_amount(self, obj):
        return obj.quantity * obj.unit_price


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    contract_name = serializers.CharField(source="contract.name", read_only=True, default="")
    request_no = serializers.CharField(source="request.request_no", read_only=True, default="")
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = ("id", "order_no", "request", "request_no", "supplier", "supplier_name", "contract", "contract_name", "status", "status_label", "ordered_on", "expected_on", "received_on", "total_amount", "kingdee_code", "external_id", "created_by", "created_by_name", "notes", "items", "created_at", "updated_at")
        read_only_fields = ("order_no", "total_amount", "created_by")

    def get_created_by_name(self, obj):
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by else ""

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items")
        instance = PurchaseOrder.objects.create(order_no=_document_no("CGDD"), created_by=self.context["request"].user, **validated_data)
        for item in items:
            PurchaseOrderItem.objects.create(order=instance, **item)
        instance.total_amount = sum(item.quantity * item.unit_price for item in instance.items.all())
        instance.save(update_fields=["total_amount", "updated_at"])
        if instance.request and instance.request.status == PurchaseRequest.Status.APPROVED:
            instance.request.status = PurchaseRequest.Status.ORDERED
            instance.request.save(update_fields=["status", "updated_at"])
        category = instance.request.category if instance.request and instance.request.category else ExpenseCategory.objects.get_or_create(code="PURCHASE", defaults={"name": "行政采购"})[0]
        AdministrativeExpense.objects.create(
            occurred_on=instance.ordered_on or date.today(), fiscal_year=(instance.ordered_on or date.today()).year,
            category=category, department=instance.request.department if instance.request else None,
            supplier=instance.supplier, contract=instance.contract,
            amount_type=AdministrativeExpense.AmountType.COMMITTED, amount=instance.total_amount,
            title=f"采购订单 · {instance.order_no}", source_type="purchase_order", source_id=instance.pk,
            source_no=instance.order_no, object_label="；".join(item.name for item in instance.items.all())[:160],
            kingdee_code=instance.kingdee_code, external_id=instance.external_id,
            created_by=instance.created_by, notes=instance.notes,
        )
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        instance = super().update(instance, validated_data)
        if items is not None:
            instance.items.all().delete()
            for item in items:
                PurchaseOrderItem.objects.create(order=instance, **item)
            instance.total_amount = sum(item.quantity * item.unit_price for item in instance.items.all())
            instance.save(update_fields=["total_amount", "updated_at"])
        expense = AdministrativeExpense.objects.filter(source_type="purchase_order", source_id=instance.pk).order_by("id").first()
        if expense:
            expense.occurred_on = instance.received_on or instance.ordered_on or expense.occurred_on
            expense.amount = instance.total_amount
            expense.amount_type = AdministrativeExpense.AmountType.ACTUAL if instance.status in {PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CLOSED} else AdministrativeExpense.AmountType.COMMITTED
            expense.supplier = instance.supplier
            expense.contract = instance.contract
            expense.kingdee_code = instance.kingdee_code
            expense.external_id = instance.external_id
            expense.notes = instance.notes
            expense.save()
        return instance
