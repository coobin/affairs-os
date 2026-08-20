from django.contrib import admin

from .models import (
    Asset,
    AssetCategory,
    AssetEvent,
    AssetManagerRole,
    AssetRequest,
    AssetStatus,
    AdministrativeExpense,
    Contract,
    ContractChange,
    ContractType,
    Department,
    EmployeeProfile,
    EmailNotification,
    ExpenseCategory,
    InventoryItem,
    InventoryTransaction,
    Location,
    OperationLog,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    StocktakeRecord,
    StocktakeTask,
    Vehicle,
    VehicleDispatch,
    VehicleExpense,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "kingdee_code", "name", "category", "status", "assigned_to", "current_location")
    list_filter = ("status", "category", "current_location")
    search_fields = (
        "asset_tag",
        "kingdee_code",
        "name",
        "serial_number",
        "brand",
        "model_name",
        "cpu",
        "wired_mac",
        "wireless_mac",
    )
    readonly_fields = ("custodian_department", "created_at", "updated_at")


@admin.register(AssetEvent)
class AssetEventAdmin(admin.ModelAdmin):
    list_display = ("asset", "action", "actor", "happened_at")
    list_filter = ("action", "happened_at")
    search_fields = ("asset__asset_tag", "asset__name", "notes")
    readonly_fields = [field.name for field in AssetEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Department)
admin.site.register(Location)
admin.site.register(EmployeeProfile)
admin.site.register(AssetCategory)
admin.site.register(AssetStatus)
admin.site.register(InventoryItem)
admin.site.register(InventoryTransaction)
admin.site.register(StocktakeTask)
admin.site.register(StocktakeRecord)
admin.site.register(AssetManagerRole)
admin.site.register(AssetRequest)
admin.site.register(ExpenseCategory)
admin.site.register(Supplier)
admin.site.register(Contract)
admin.site.register(ContractType)
admin.site.register(ContractChange)
admin.site.register(Vehicle)
admin.site.register(VehicleDispatch)
admin.site.register(VehicleExpense)
admin.site.register(AdministrativeExpense)
admin.site.register(PurchaseRequest)
admin.site.register(PurchaseRequestItem)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "event_type", "subject", "status", "attempts", "sent_at", "created_at")
    list_filter = ("status", "event_type", "created_at")
    search_fields = ("recipient_email", "subject", "event_key")
    readonly_fields = [field.name for field in EmailNotification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "display_name", "module_label", "action_label", "target_label", "succeeded", "ip_address")
    list_filter = ("module", "action", "succeeded", "occurred_at")
    search_fields = ("username", "display_name", "target_label", "path")
    readonly_fields = [field.name for field in OperationLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "AffairsOS · 系统管理"
admin.site.site_title = "AffairsOS"
