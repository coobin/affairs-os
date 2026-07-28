from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    AssetStatusViewSet,
    AdministrativeExpenseViewSet,
    CategoryViewSet,
    ContractViewSet,
    DashboardView,
    DepartmentViewSet,
    InventoryItemViewSet,
    ExpenseCategoryViewSet,
    LocationViewSet,
    PurchaseOrderViewSet,
    PurchaseRequestViewSet,
    SupplierViewSet,
    LocalLoginView,
    LookupView,
    LogoutView,
    ManagerSettingsView,
    MeView,
    OIDCCallbackView,
    OIDCCompleteView,
    OIDCLoginView,
    ReportsView,
    ReportAssetDetailView,
    AssetRequestViewSet,
    StocktakeTaskViewSet,
    VehicleDispatchViewSet,
    VehicleExpenseViewSet,
    VehicleViewSet,
    health,
)

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("requests", AssetRequestViewSet, basename="asset-request")
router.register("inventory", InventoryItemViewSet, basename="inventory")
router.register("stocktakes", StocktakeTaskViewSet, basename="stocktake")
router.register("departments", DepartmentViewSet, basename="department")
router.register("locations", LocationViewSet, basename="location")
router.register("categories", CategoryViewSet, basename="category")
router.register("asset-statuses", AssetStatusViewSet, basename="asset-status")
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("contracts", ContractViewSet, basename="contract")
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("vehicle-dispatches", VehicleDispatchViewSet, basename="vehicle-dispatch")
router.register("vehicle-expenses", VehicleExpenseViewSet, basename="vehicle-expense")
router.register("administrative-expenses", AdministrativeExpenseViewSet, basename="administrative-expense")
router.register("purchase-requests", PurchaseRequestViewSet, basename="purchase-request")
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-order")

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/oidc/login/", OIDCLoginView.as_view(), name="oidc-login"),
    path("auth/oidc/callback/", OIDCCallbackView.as_view(), name="oidc-callback"),
    path("auth/oidc/complete/", OIDCCompleteView.as_view(), name="oidc-complete"),
    path("auth/local/login/", LocalLoginView.as_view(), name="local-login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("settings/managers/", ManagerSettingsView.as_view(), name="manager-settings"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("lookups/", LookupView.as_view(), name="lookups"),
    path("reports/", ReportsView.as_view(), name="reports"),
    path("reports/assets/", ReportAssetDetailView.as_view(), name="report-asset-details"),
    path("", include(router.urls)),
]
