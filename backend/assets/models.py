from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(TimeStampedModel):
    name = models.CharField("部门名称", max_length=100)
    code = models.CharField("部门编码", max_length=32, unique=True)
    parent = models.ForeignKey(
        "self",
        verbose_name="上级部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "部门"
        verbose_name_plural = "部门"

    def __str__(self):
        return self.name


class Location(TimeStampedModel):
    class Kind(models.TextChoices):
        OFFICE = "office", "办公室"
        WAREHOUSE = "warehouse", "库房"
        REPAIR = "repair", "维修点"
        OTHER = "other", "其他"

    name = models.CharField("地点名称", max_length=100)
    code = models.CharField("地点编码", max_length=32, unique=True)
    kind = models.CharField("地点类型", max_length=20, choices=Kind.choices, default=Kind.OFFICE)
    address = models.CharField("地址", max_length=255, blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "地点"
        verbose_name_plural = "地点"

    def __str__(self):
        return self.name


class EmployeeProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_no = models.CharField("工号", max_length=32, unique=True)
    department = models.ForeignKey(
        Department,
        verbose_name="部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="employees",
    )
    phone = models.CharField("联系电话", max_length=32, blank=True)

    class Meta:
        ordering = ["employee_no"]
        verbose_name = "员工档案"
        verbose_name_plural = "员工档案"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} · {self.employee_no}"


class AssetManagerRole(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="管理员",
        on_delete=models.CASCADE,
        related_name="asset_manager_role",
    )
    scopes = models.JSONField("可管理板块", default=list, blank=True)

    class Meta:
        ordering = ["user__username"]
        verbose_name = "资产管理员权限"
        verbose_name_plural = "资产管理员权限"

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class AssetCategory(TimeStampedModel):
    class ClassType(models.TextChoices):
        IT = "IT", "IT资产"
        ADMIN = "ADMIN", "行政资产"

    class_type = models.CharField(
        "资产分类",
        max_length=12,
        choices=ClassType.choices,
        default=ClassType.IT,
        db_index=True,
    )
    name = models.CharField("分类名称", max_length=100)
    code = models.CharField("分类编码", max_length=12, unique=True)
    icon = models.CharField("图标", max_length=32, default="laptop")
    description = models.CharField("说明", max_length=255, blank=True)
    custom_fields = models.JSONField("分类字段模板", default=list, blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "资产类型"
        verbose_name_plural = "资产类型"

    def __str__(self):
        return self.name


class AssetStatus(TimeStampedModel):
    code = models.CharField("状态编码", max_length=32, unique=True)
    name = models.CharField("状态名称", max_length=40, unique=True)
    sort_order = models.PositiveSmallIntegerField("排序", default=100)
    is_system = models.BooleanField("系统状态", default=False)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "资产状态"
        verbose_name_plural = "资产状态"

    def __str__(self):
        return self.name


class Asset(TimeStampedModel):
    class Status:
        AVAILABLE = "available"
        LOANED = "loaned"
        ASSIGNED = "assigned"
        DISPOSED = "disposed"
        choices = (
            (AVAILABLE, "在库"),
            (LOANED, "借用中"),
            (ASSIGNED, "使用中"),
            (DISPOSED, "报废"),
        )

        # 兼容旧业务动作和历史迁移；这些旧状态统一折叠到四种基础状态。
        PENDING = AVAILABLE
        INSPECTION = AVAILABLE
        TRANSFER = AVAILABLE
        REPAIR = AVAILABLE
        LOST = DISPOSED
        RETIRED = DISPOSED

    asset_tag = models.CharField("资产编号", max_length=64, unique=True, db_index=True)
    kingdee_code = models.CharField("金蝶编码", max_length=64, blank=True, db_index=True)
    name = models.CharField("资产名称", max_length=120)
    category = models.ForeignKey(
        AssetCategory,
        verbose_name="资产类型",
        on_delete=models.PROTECT,
        related_name="assets",
    )
    brand = models.CharField("品牌", max_length=80, blank=True)
    model_name = models.CharField("型号", max_length=120, blank=True)
    serial_number = models.CharField("序列号", max_length=120, blank=True, db_index=True)
    specification = models.CharField("主要配置", max_length=255, blank=True)
    cpu = models.CharField("CPU", max_length=120, blank=True)
    memory = models.CharField("内存", max_length=80, blank=True)
    storage = models.CharField("硬盘", max_length=120, blank=True)
    wired_mac = models.CharField("有线 MAC 地址", max_length=255, blank=True)
    wireless_mac = models.CharField("无线 MAC 地址", max_length=255, blank=True)
    status = models.CharField(
        "状态",
        max_length=32,
        default=Status.AVAILABLE,
        db_index=True,
    )
    is_requestable = models.BooleanField("允许员工申请", default=True, db_index=True)
    current_location = models.ForeignKey(
        Location,
        verbose_name="当前地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_assets",
    )
    custodian_department = models.ForeignKey(
        Department,
        verbose_name="归属部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    purchase_date = models.DateField("采购日期", null=True, blank=True)
    purchase_cost = models.DecimalField(
        "采购金额",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    warranty_expires_at = models.DateField("保修到期", null=True, blank=True, db_index=True)
    expected_return_at = models.DateField("预计归还", null=True, blank=True, db_index=True)
    notes = models.TextField("备注", blank=True)
    custom_data = models.JSONField("扩展信息", default=dict, blank=True)
    last_audited_at = models.DateTimeField("最后盘点时间", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"], name="asset_status_cat_idx"),
            models.Index(fields=["assigned_to", "status"], name="asset_user_status_idx"),
            models.Index(fields=["current_location", "status"], name="asset_loc_status_idx"),
        ]
        verbose_name = "资产"
        verbose_name_plural = "资产"

    def build_display_name(self):
        brand = self.brand.strip()
        model_name = self.model_name.strip()
        if brand and model_name:
            if model_name.casefold().startswith(brand.casefold()):
                return model_name[:120]
            return f"{brand} {model_name}"[:120]
        if brand or model_name:
            return (brand or model_name)[:120]
        category = self._state.fields_cache.get("category")
        category_name = category.name if category else ""
        if not category_name and self.category_id:
            category_name = (
                AssetCategory.objects.filter(pk=self.category_id)
                .values_list("name", flat=True)
                .first()
                or ""
            )
        return category_name[:120] or "待完善资产"

    def save(self, *args, **kwargs):
        self.name = self.build_display_name()
        if isinstance(self.custom_data, dict) and "responsible_person" in self.custom_data:
            self.custom_data = dict(self.custom_data)
            self.custom_data.pop("responsible_person", None)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"name", "custom_data"}
        return super().save(*args, **kwargs)

    def get_status_display(self):
        configured = AssetStatus.objects.filter(code=self.status).values_list("name", flat=True).first()
        return configured or dict(self.Status.choices).get(self.status, self.status)

    def __str__(self):
        return f"{self.asset_tag} · {self.name}"


class RemoteFileBase(TimeStampedModel):
    remote_path = models.CharField("Nextcloud 路径", max_length=512, unique=True)
    original_name = models.CharField("原文件名", max_length=255)
    content_type = models.CharField("文件类型", max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField("文件大小", default=0)
    sha256 = models.CharField("SHA-256", max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class AssetImage(RemoteFileBase):
    asset = models.ForeignKey(
        Asset,
        verbose_name="资产",
        on_delete=models.CASCADE,
        related_name="images",
    )
    is_cover = models.BooleanField("封面", default=False)
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name = "资产图片"
        verbose_name_plural = "资产图片"


class AssetRequest(TimeStampedModel):
    class ItemType(models.TextChoices):
        ASSET = "asset", "资产"
        INVENTORY = "inventory", "库存物品"

    class RequestType(models.TextChoices):
        ASSIGN = "assign", "领用"
        LOAN = "loan", "借用"

    class Status(models.TextChoices):
        PENDING = "pending", "待分配"
        FULFILLED = "fulfilled", "已分配"
        REJECTED = "rejected", "已驳回"
        CANCELLED = "cancelled", "已取消"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="申请人",
        on_delete=models.PROTECT,
        related_name="asset_requests",
    )
    request_type = models.CharField("申请类型", max_length=12, choices=RequestType.choices)
    requested_item_type = models.CharField(
        "申请物品类型",
        max_length=16,
        choices=ItemType.choices,
        default=ItemType.ASSET,
        db_index=True,
    )
    requested_name = models.CharField("设备名称", max_length=120, db_index=True)
    reason = models.CharField("用途说明", max_length=500, blank=True)
    needed_at = models.DateField("领用时间", null=True, blank=True, db_index=True)
    expected_return_at = models.DateField("预计归还", null=True, blank=True)
    requested_quantity = models.PositiveIntegerField("申请数量", default=1)
    inventory_item = models.ForeignKey(
        "InventoryItem",
        verbose_name="申请库存物品",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    assigned_asset = models.ForeignKey(
        Asset,
        verbose_name="已分配资产",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fulfilled_requests",
    )
    issued_inventory_transaction = models.ForeignKey(
        "InventoryTransaction",
        verbose_name="库存发放流水",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fulfilled_requests",
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handled_asset_requests",
    )
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)
    manager_notes = models.CharField("处理说明", max_length=500, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["requester", "status"], name="asset_req_user_status_idx"),
            models.Index(fields=["requested_name", "status"], name="asset_req_name_status_idx"),
        ]
        verbose_name = "资产领用借用申请"
        verbose_name_plural = "资产领用借用申请"

    def __str__(self):
        return f"{self.get_request_type_display()} · {self.requested_name}"


class AssetNumberSequence(models.Model):
    category = models.ForeignKey(
        AssetCategory,
        verbose_name="资产类型",
        on_delete=models.CASCADE,
        related_name="+",
    )
    year = models.PositiveSmallIntegerField("兼容年份", default=0, editable=False)
    current_value = models.PositiveIntegerField("当前流水号", default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("category",),
                name="asset_sequence_category_unique",
            )
        ]
        verbose_name = "资产编号流水"
        verbose_name_plural = "资产编号流水"


class InventoryItem(TimeStampedModel):
    class Kind(models.TextChoices):
        ACCESSORY = "accessory", "配件"
        CONSUMABLE = "consumable", "耗材"
        LICENSE = "license", "软件许可"
        OTHER = "other", "其他"

    class PurchaseChannel(models.TextChoices):
        SUPPLIER = "supplier", "合作供应商"
        ECOMMERCE = "ecommerce", "电商"
        OTHER = "other", "其他"

    sku = models.CharField("物品编码", max_length=64, unique=True, db_index=True)
    name = models.CharField("物品名称", max_length=120)
    kind = models.CharField("类型", max_length=20, choices=Kind.choices)
    brand = models.CharField("品牌", max_length=80, blank=True)
    model_name = models.CharField("型号", max_length=120, blank=True)
    unit = models.CharField("单位", max_length=16, default="个")
    unit_price = models.DecimalField(
        "单价",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    purchase_channel = models.CharField(
        "采购途径",
        max_length=20,
        choices=PurchaseChannel.choices,
        blank=True,
        default="",
    )
    quantity = models.PositiveIntegerField("当前库存", default=0)
    minimum_quantity = models.PositiveIntegerField("保障数量", default=0)
    location = models.ForeignKey(
        Location,
        verbose_name="存放地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    notes = models.CharField("备注", max_length=255, blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["kind", "sku"]
        verbose_name = "库存品"
        verbose_name_plural = "库存品"

    def __str__(self):
        return f"{self.sku} · {self.name}"


class InventoryTransaction(models.Model):
    class Action(models.TextChoices):
        INBOUND = "inbound", "入库"
        ISSUE = "issue", "发放"
        RETURN = "return", "退回"
        WRITEOFF = "writeoff", "报损"

    item = models.ForeignKey(
        InventoryItem,
        verbose_name="库存品",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    action = models.CharField("动作", max_length=20, choices=Action.choices)
    quantity = models.PositiveIntegerField("数量")
    balance_after = models.PositiveIntegerField("操作后库存")
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="领用人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_transactions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="经办人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.CharField("说明", max_length=255, blank=True)
    happened_at = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-happened_at", "-id"]
        verbose_name = "库存流水"
        verbose_name_plural = "库存流水"


class StocktakeTask(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "盘点中"
        COMPLETED = "completed", "已完成"

    name = models.CharField("任务名称", max_length=120)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )
    scope_location = models.ForeignKey(
        Location,
        verbose_name="盘点地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stocktake_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="stocktake_tasks",
    )
    snapshot_count = models.PositiveIntegerField("应盘数量", default=0)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "盘点任务"
        verbose_name_plural = "盘点任务"


class StocktakeRecord(models.Model):
    class Result(models.TextChoices):
        PENDING = "pending", "待盘"
        MATCHED = "matched", "正常"
        LOCATION_MISMATCH = "location_mismatch", "位置不符"
        MISSING = "missing", "未盘到"

    task = models.ForeignKey(
        StocktakeTask,
        verbose_name="盘点任务",
        on_delete=models.CASCADE,
        related_name="records",
    )
    asset = models.ForeignKey(
        Asset,
        verbose_name="资产",
        on_delete=models.PROTECT,
        related_name="stocktake_records",
    )
    expected_location = models.ForeignKey(
        Location,
        verbose_name="账面地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    expected_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="账面责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    result = models.CharField(
        "结果",
        max_length=24,
        choices=Result.choices,
        default=Result.PENDING,
        db_index=True,
    )
    scanned_at = models.DateTimeField("盘点时间", null=True, blank=True)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="盘点人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("task", "asset"),
                name="stocktake_task_asset_unique",
            )
        ]
        ordering = ["result", "asset__asset_tag"]
        verbose_name = "盘点记录"
        verbose_name_plural = "盘点记录"


class AssetEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "登记"
        ACCEPTED = "accepted", "验收入库"
        ASSIGNED = "assigned", "领用"
        LOANED = "loaned", "借用"
        RETURNED = "returned", "归还"
        TRANSFERRED = "transferred", "调拨"
        REPAIR_STARTED = "repair_started", "送修"
        REPAIR_COMPLETED = "repair_completed", "维修完成"
        LOST = "lost", "报失"
        FOUND = "found", "找回"
        RETIRED = "retired", "退役"
        DISPOSED = "disposed", "处置"
        UPDATED = "updated", "信息更新"

    asset = models.ForeignKey(Asset, verbose_name="资产", on_delete=models.PROTECT, related_name="events")
    action = models.CharField("动作", max_length=32, choices=Action.choices)
    from_status = models.CharField("原状态", max_length=20, blank=True)
    to_status = models.CharField("新状态", max_length=20, blank=True)
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="原责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="新责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    from_location = models.ForeignKey(
        Location,
        verbose_name="原地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    to_location = models.ForeignKey(
        Location,
        verbose_name="新地点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="经办人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="asset_events",
    )
    happened_at = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)
    notes = models.TextField("说明", blank=True)
    metadata = models.JSONField("附加信息", default=dict, blank=True)

    class Meta:
        ordering = ["-happened_at", "-id"]
        verbose_name = "资产事件"
        verbose_name_plural = "资产事件"

    def __str__(self):
        return f"{self.asset.asset_tag} · {self.get_action_display()}"


class EmailNotification(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待发送"
        PROCESSING = "processing", "发送中"
        SENT = "sent", "已发送"
        FAILED = "failed", "发送失败"

    event_key = models.CharField("事件标识", max_length=255, unique=True)
    event_type = models.CharField("通知类型", max_length=48, db_index=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="收件人账号",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="email_notifications",
    )
    recipient_email = models.EmailField("收件邮箱")
    subject = models.CharField("邮件主题", max_length=255)
    body = models.TextField("邮件正文")
    status = models.CharField(
        "发送状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField("尝试次数", default=0)
    last_error = models.TextField("最后错误", blank=True)
    sent_at = models.DateTimeField("发送时间", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "邮件通知"
        verbose_name_plural = "邮件通知"
        indexes = [
            models.Index(fields=["status", "created_at"], name="email_notice_status_idx"),
        ]

    def __str__(self):
        return f"{self.recipient_email} · {self.subject}"


class ExpenseCategory(TimeStampedModel):
    name = models.CharField("费用类别", max_length=80)
    code = models.CharField("类别编码", max_length=32, unique=True)
    budget_code = models.CharField("预算科目编码", max_length=64, blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "行政费用类别"
        verbose_name_plural = "行政费用类别"

    def __str__(self):
        return self.name


class Supplier(TimeStampedModel):
    class Channel(models.TextChoices):
        COOPERATIVE = "cooperative", "合作供应商"
        ECOMMERCE = "ecommerce", "电商"
        OTHER = "other", "其他"

    code = models.CharField("供应商编码", max_length=32, unique=True)
    name = models.CharField("供应商名称", max_length=160)
    channel = models.CharField("采购途径", max_length=20, choices=Channel.choices, default=Channel.COOPERATIVE)
    contact_name = models.CharField("联系人", max_length=80, blank=True)
    contact_phone = models.CharField("联系电话", max_length=40, blank=True)
    contact_email = models.EmailField("联系邮箱", blank=True)
    tax_number = models.CharField("税号", max_length=80, blank=True)
    bank_account = models.CharField("银行账号", max_length=120, blank=True)
    address = models.CharField("地址", max_length=255, blank=True)
    notes = models.TextField("备注", blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "供应商"
        verbose_name_plural = "供应商"

    def __str__(self):
        return self.name


class ContractType(TimeStampedModel):
    name = models.CharField("合同类型", max_length=80, unique=True)
    code = models.CharField("类型编码", max_length=32, unique=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "合同类型"
        verbose_name_plural = "合同类型"

    def __str__(self):
        return self.name


class Contract(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ACTIVE = "active", "履行中"
        EXPIRED = "expired", "已到期未处理"
        COMPLETED = "completed", "已完成"
        TERMINATED = "terminated", "已终止"

    contract_no = models.CharField("合同编号", max_length=64, unique=True)
    name = models.CharField("合同名称", max_length=180)
    contract_type = models.ForeignKey(ContractType, verbose_name="合同类型", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    supplier = models.ForeignKey(Supplier, verbose_name="供应商", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    category = models.ForeignKey(ExpenseCategory, verbose_name="费用类别", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    department = models.ForeignKey(Department, verbose_name="归属部门", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="负责人", null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_admin_contracts")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    start_date = models.DateField("开始日期", null=True, blank=True)
    end_date = models.DateField("结束日期", null=True, blank=True, db_index=True)
    amount = models.DecimalField("合同金额", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    renewal_notice_days = models.PositiveSmallIntegerField("到期提醒天数", default=30)
    auto_renew = models.BooleanField("自动续签", default=False)
    previous_contract = models.ForeignKey("self", verbose_name="上一期合同", null=True, blank=True, on_delete=models.SET_NULL, related_name="renewal_contracts")
    supplement_of = models.ForeignKey("self", verbose_name="母合同", null=True, blank=True, on_delete=models.CASCADE, related_name="supplement_contracts")
    kingdee_code = models.CharField("金蝶编码", max_length=64, blank=True, db_index=True)
    external_id = models.CharField("外部系统标识", max_length=100, blank=True, db_index=True)
    notes = models.TextField("备注", blank=True)

    class Meta:
        ordering = ["-end_date", "contract_no"]
        verbose_name = "行政合同"
        verbose_name_plural = "行政合同"

    def __str__(self):
        return f"{self.contract_no} · {self.name}"


class ContractChange(TimeStampedModel):
    class ChangeType(models.TextChoices):
        EXTENSION = "extension", "延期续约"
        SUPPLEMENT = "supplement", "补充协议"
        AMOUNT = "amount", "金额调整"
        TERMINATION = "termination", "提前终止"
        OTHER = "other", "其他变更"

    contract = models.ForeignKey(Contract, verbose_name="合同", on_delete=models.CASCADE, related_name="changes")
    change_type = models.CharField("变更类型", max_length=20, choices=ChangeType.choices)
    changed_on = models.DateField("生效日期", default=date.today)
    old_start_date = models.DateField("原开始日期", null=True, blank=True)
    new_start_date = models.DateField("新开始日期", null=True, blank=True)
    old_end_date = models.DateField("原结束日期", null=True, blank=True)
    new_end_date = models.DateField("新结束日期", null=True, blank=True)
    old_amount = models.DecimalField("原合同金额", max_digits=14, decimal_places=2, null=True, blank=True)
    new_amount = models.DecimalField("新合同金额", max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField("变更说明")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="登记人", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_contract_changes")

    class Meta:
        ordering = ["-changed_on", "-created_at"]
        verbose_name = "合同变更记录"
        verbose_name_plural = "合同变更记录"


class ContractAttachment(RemoteFileBase):
    class DocumentType(models.TextChoices):
        ORIGINAL = "original", "合同原件"
        SIGNED = "signed", "盖章扫描件"
        SUPPLEMENT = "supplement", "补充协议"
        QUOTATION = "quotation", "报价单"
        INVOICE = "invoice", "发票"
        OTHER = "other", "其他"

    contract = models.ForeignKey(
        Contract,
        verbose_name="合同",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    change = models.ForeignKey(
        ContractChange,
        verbose_name="所属变更",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    document_type = models.CharField(
        "文件类别",
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.ORIGINAL,
    )

    class Meta:
        ordering = ["document_type", "-created_at"]
        verbose_name = "合同文件"
        verbose_name_plural = "合同文件"


class Vehicle(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "可用"
        IN_USE = "in_use", "出车中"
        MAINTENANCE = "maintenance", "维修保养"
        SUSPENDED = "suspended", "停用"
        RETIRED = "retired", "已处置"

    class EnergyType(models.TextChoices):
        GASOLINE = "gasoline", "汽油"
        DIESEL = "diesel", "柴油"
        ELECTRIC = "electric", "纯电"
        HYBRID = "hybrid", "混动"
        OTHER = "other", "其他"

    plate_number = models.CharField("车牌号", max_length=24, unique=True)
    name = models.CharField("车辆名称", max_length=120)
    brand = models.CharField("品牌", max_length=80, blank=True)
    model_name = models.CharField("型号", max_length=120, blank=True)
    vin = models.CharField("车架号", max_length=64, blank=True, db_index=True)
    engine_number = models.CharField("发动机号", max_length=64, blank=True)
    energy_type = models.CharField("能源类型", max_length=16, choices=EnergyType.choices, default=EnergyType.GASOLINE)
    seats = models.PositiveSmallIntegerField("座位数", default=5)
    status = models.CharField("车辆状态", max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    department = models.ForeignKey(Department, verbose_name="管理部门", null=True, blank=True, on_delete=models.PROTECT, related_name="vehicles")
    custodian = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="车辆负责人", null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_vehicles")
    purchase_date = models.DateField("购置日期", null=True, blank=True)
    purchase_cost = models.DecimalField("购置金额", max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    current_mileage = models.PositiveIntegerField("当前里程（公里）", default=0)
    insurance_expires_at = models.DateField("保险到期", null=True, blank=True, db_index=True)
    inspection_expires_at = models.DateField("年检到期", null=True, blank=True, db_index=True)
    notes = models.TextField("备注", blank=True)

    class Meta:
        ordering = ["plate_number"]
        verbose_name = "车辆"
        verbose_name_plural = "车辆"

    def __str__(self):
        return f"{self.plate_number} · {self.name}"


class VehicleDispatch(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已批准"
        DISPATCHED = "dispatched", "已派车"
        IN_PROGRESS = "in_progress", "出车中"
        COMPLETED = "completed", "已完成"
        REJECTED = "rejected", "已驳回"
        CANCELLED = "cancelled", "已取消"

    request_no = models.CharField("派车单号", max_length=32, unique=True, db_index=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="申请人", on_delete=models.PROTECT, related_name="vehicle_dispatches")
    department = models.ForeignKey(Department, verbose_name="申请部门", null=True, blank=True, on_delete=models.PROTECT, related_name="vehicle_dispatches")
    purpose = models.CharField("用车事由", max_length=500)
    destination = models.CharField("目的地", max_length=255)
    passenger_count = models.PositiveSmallIntegerField("乘车人数", default=1)
    planned_departure_at = models.DateTimeField("计划出发", db_index=True)
    planned_return_at = models.DateTimeField("计划返回")
    vehicle = models.ForeignKey(Vehicle, verbose_name="分配车辆", null=True, blank=True, on_delete=models.PROTECT, related_name="dispatches")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="驾驶员", null=True, blank=True, on_delete=models.PROTECT, related_name="driving_dispatches")
    driver_name = models.CharField("外部驾驶员", max_length=80, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    start_mileage = models.PositiveIntegerField("出车里程", null=True, blank=True)
    end_mileage = models.PositiveIntegerField("返回里程", null=True, blank=True)
    actual_departure_at = models.DateTimeField("实际出发", null=True, blank=True)
    actual_return_at = models.DateTimeField("实际返回", null=True, blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="调度人", null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_vehicle_dispatches")
    notes = models.TextField("调度说明", blank=True)

    class Meta:
        ordering = ["status", "-planned_departure_at"]
        verbose_name = "派车申请"
        verbose_name_plural = "派车申请"

    def __str__(self):
        return f"{self.request_no} · {self.destination}"


class AdministrativeExpense(TimeStampedModel):
    class AmountType(models.TextChoices):
        ESTIMATED = "estimated", "预计"
        APPROVED = "approved", "已批准"
        COMMITTED = "committed", "已承诺"
        ACTUAL = "actual", "实际发生"
        REVERSAL = "reversal", "冲销"

    class InvoiceStatus(models.TextChoices):
        NONE = "none", "无需发票"
        PENDING = "pending", "待收票"
        RECEIVED = "received", "已收票"
        VERIFIED = "verified", "已核验"

    occurred_on = models.DateField("发生日期", db_index=True)
    fiscal_year = models.PositiveSmallIntegerField("年度", db_index=True)
    category = models.ForeignKey(ExpenseCategory, verbose_name="费用类别", on_delete=models.PROTECT, related_name="expenses")
    department = models.ForeignKey(Department, verbose_name="归属部门", null=True, blank=True, on_delete=models.PROTECT, related_name="administrative_expenses")
    supplier = models.ForeignKey(Supplier, verbose_name="供应商", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses")
    contract = models.ForeignKey(Contract, verbose_name="合同", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses")
    amount_type = models.CharField("金额类型", max_length=16, choices=AmountType.choices, default=AmountType.ACTUAL, db_index=True)
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    title = models.CharField("费用事项", max_length=180)
    source_type = models.CharField("来源类型", max_length=32, default="manual", db_index=True)
    source_id = models.PositiveBigIntegerField("来源记录ID", null=True, blank=True)
    source_no = models.CharField("来源单号", max_length=64, blank=True, db_index=True)
    object_label = models.CharField("费用对象", max_length=160, blank=True)
    invoice_status = models.CharField("发票状态", max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING)
    invoice_number = models.CharField("发票号码", max_length=80, blank=True)
    kingdee_code = models.CharField("金蝶编码", max_length=64, blank=True, db_index=True)
    external_id = models.CharField("预算系统标识", max_length=100, blank=True, db_index=True)
    sync_status = models.CharField("同步状态", max_length=16, default="pending", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="登记人", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_admin_expenses")
    notes = models.TextField("备注", blank=True)

    class Meta:
        ordering = ["-occurred_on", "-id"]
        indexes = [models.Index(fields=["fiscal_year", "category", "amount_type"], name="admin_exp_year_cat_idx")]
        verbose_name = "行政费用"
        verbose_name_plural = "行政费用"

    def save(self, *args, **kwargs):
        if self.occurred_on:
            self.fiscal_year = self.occurred_on.year
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.occurred_on} · {self.title}"


class VehicleExpense(TimeStampedModel):
    class ExpenseType(models.TextChoices):
        MAINTENANCE = "maintenance", "保养"
        REPAIR = "repair", "维修"
        INSURANCE = "insurance", "保险"
        INSPECTION = "inspection", "年检"
        FUEL = "fuel", "加油"
        CHARGE = "charge", "充电"
        VIOLATION = "violation", "违章"
        ACCIDENT = "accident", "事故"
        PARKING = "parking", "停车通行"
        OTHER = "other", "其他"

    vehicle = models.ForeignKey(Vehicle, verbose_name="车辆", on_delete=models.PROTECT, related_name="expenses")
    expense_type = models.CharField("事项类型", max_length=20, choices=ExpenseType.choices, db_index=True)
    occurred_on = models.DateField("发生日期", db_index=True)
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    supplier = models.ForeignKey(Supplier, verbose_name="服务商", null=True, blank=True, on_delete=models.PROTECT, related_name="vehicle_expenses")
    odometer = models.PositiveIntegerField("发生时里程", null=True, blank=True)
    next_due_on = models.DateField("下次到期日期", null=True, blank=True, db_index=True)
    next_due_mileage = models.PositiveIntegerField("下次保养里程", null=True, blank=True)
    expense = models.OneToOneField(AdministrativeExpense, verbose_name="费用台账", null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicle_record")
    notes = models.TextField("事项说明", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="登记人", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_vehicle_expenses")

    class Meta:
        ordering = ["-occurred_on", "-id"]
        verbose_name = "车辆费用与事项"
        verbose_name_plural = "车辆费用与事项"


class PurchaseRequest(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已批准"
        REJECTED = "rejected", "已驳回"
        ORDERED = "ordered", "已下单"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    request_no = models.CharField("采购申请单号", max_length=32, unique=True, db_index=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="申请人", on_delete=models.PROTECT, related_name="purchase_requests")
    department = models.ForeignKey(Department, verbose_name="申请部门", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_requests")
    needed_on = models.DateField("期望到货日期", null=True, blank=True)
    reason = models.CharField("采购用途", max_length=500)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    estimated_amount = models.DecimalField("预计金额", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    category = models.ForeignKey(ExpenseCategory, verbose_name="费用类别", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_requests")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="审批人", null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_purchase_requests")
    handled_at = models.DateTimeField("审批时间", null=True, blank=True)
    manager_notes = models.CharField("审批说明", max_length=500, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        verbose_name = "采购申请"
        verbose_name_plural = "采购申请"


class PurchaseRequestItem(models.Model):
    request = models.ForeignKey(PurchaseRequest, verbose_name="采购申请", on_delete=models.CASCADE, related_name="items")
    name = models.CharField("物品或服务", max_length=160)
    specification = models.CharField("规格说明", max_length=255, blank=True)
    quantity = models.DecimalField("数量", max_digits=12, decimal_places=2, default=1, validators=[MinValueValidator(0.01)])
    unit = models.CharField("单位", max_length=20, default="件")
    estimated_unit_price = models.DecimalField("预计单价", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["id"]


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ORDERED = "ordered", "已下单"
        PARTIAL = "partial", "部分到货"
        RECEIVED = "received", "已到货"
        CLOSED = "closed", "已关闭"
        CANCELLED = "cancelled", "已取消"

    order_no = models.CharField("采购订单号", max_length=32, unique=True, db_index=True)
    request = models.ForeignKey(PurchaseRequest, verbose_name="采购申请", null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    supplier = models.ForeignKey(Supplier, verbose_name="供应商", on_delete=models.PROTECT, related_name="purchase_orders")
    contract = models.ForeignKey(Contract, verbose_name="关联合同", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    ordered_on = models.DateField("下单日期", null=True, blank=True)
    expected_on = models.DateField("预计到货", null=True, blank=True)
    received_on = models.DateField("实际到货", null=True, blank=True)
    total_amount = models.DecimalField("订单金额", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    kingdee_code = models.CharField("金蝶编码", max_length=64, blank=True, db_index=True)
    external_id = models.CharField("外部系统标识", max_length=100, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="经办人", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_purchase_orders")
    notes = models.TextField("备注", blank=True)

    class Meta:
        ordering = ["-ordered_on", "-id"]
        verbose_name = "采购订单"
        verbose_name_plural = "采购订单"


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, verbose_name="采购订单", on_delete=models.CASCADE, related_name="items")
    name = models.CharField("物品或服务", max_length=160)
    specification = models.CharField("规格说明", max_length=255, blank=True)
    quantity = models.DecimalField("数量", max_digits=12, decimal_places=2, default=1, validators=[MinValueValidator(0.01)])
    unit = models.CharField("单位", max_length=20, default="件")
    unit_price = models.DecimalField("含税单价", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["id"]
