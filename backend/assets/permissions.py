from django.conf import settings
from rest_framework.permissions import BasePermission


MANAGEMENT_MODULES = (
    ("assets", "资产台账"),
    ("inventory", "库存"),
    ("stocktake", "盘点"),
    ("vehicles", "车辆管理"),
    ("expenses", "费用台账"),
    ("procurement", "采购管理"),
    ("contracts", "合同管理"),
    ("reports", "报表"),
    ("settings", "设置"),
)
MANAGEMENT_SCOPE_KEYS = {value for value, _ in MANAGEMENT_MODULES}
HIDDEN_SYSTEM_USERNAME = settings.LOCAL_LOGIN_USERNAME


def is_hidden_superuser(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.username.casefold() == settings.DJANGO_SUPERUSER_USERNAME.casefold()
        )
    )


def management_scopes(user):
    if not user or not user.is_authenticated:
        return []
    if is_hidden_superuser(user):
        return [value for value, _ in MANAGEMENT_MODULES]
    try:
        scopes = user.asset_manager_role.scopes
    except AttributeError:
        return []
    return [scope for scope in scopes if scope in MANAGEMENT_SCOPE_KEYS]


def user_can_manage(user, module):
    return module in management_scopes(user)


def user_can_manage_requests(user):
    return user_can_manage(user, "assets") or user_can_manage(user, "inventory")


class IsModuleManager(BasePermission):
    message = "当前账号没有管理这个板块的权限。"

    def has_permission(self, request, view):
        module = getattr(view, "management_module", "")
        return request.user.is_authenticated and user_can_manage(request.user, module)


class IsSuperAdministrator(BasePermission):
    message = "只有超级管理员可以设置管理员权限。"

    def has_permission(self, request, view):
        return request.user.is_authenticated and is_hidden_superuser(request.user)
