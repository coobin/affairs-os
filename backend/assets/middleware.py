import ipaddress
import json
import logging

from .models import OperationLog


logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

MODULES = {
    "assets": ("assets", "资产管理"),
    "asset": ("assets", "资产管理"),
    "requests": ("requests", "领用借用"),
    "asset-request": ("requests", "领用借用"),
    "inventory": ("inventory", "库存管理"),
    "stocktake": ("stocktake", "资产盘点"),
    "vehicles": ("vehicles", "车辆管理"),
    "vehicle": ("vehicles", "车辆管理"),
    "vehicle-dispatch": ("vehicles", "车辆管理"),
    "vehicle-expense": ("vehicles", "车辆管理"),
    "expenses": ("expenses", "费用台账"),
    "administrative-expense": ("expenses", "费用台账"),
    "procurement": ("procurement", "采购管理"),
    "purchase-request": ("procurement", "采购管理"),
    "purchase-order": ("procurement", "采购管理"),
    "supplier": ("procurement", "采购管理"),
    "contracts": ("contracts", "合同管理"),
    "contract": ("contracts", "合同管理"),
    "settings": ("settings", "系统设置"),
    "department": ("settings", "系统设置"),
    "location": ("settings", "系统设置"),
    "category": ("settings", "系统设置"),
    "asset-status": ("settings", "系统设置"),
    "expense-category": ("settings", "系统设置"),
    "contract-type": ("settings", "系统设置"),
    "account": ("account", "账号会话"),
}

ACTION_LABELS = {
    "create": "新增",
    "update": "编辑",
    "partial_update": "编辑",
    "destroy": "删除",
    "import_excel": "导入",
    "perform_action": "办理资产操作",
    "fulfill": "办结申请",
    "reject": "驳回",
    "cancel": "取消",
    "approve": "审批通过",
    "dispatch_vehicle": "派车",
    "depart": "确认出车",
    "complete": "完成",
    "scan": "登记盘点",
    "transactions": "登记库存流水",
    "renew": "续签合同",
    "changes": "登记合同变更",
    "login": "登录",
    "logout": "退出登录",
    "manager-settings": "调整管理员权限",
    "module-settings": "调整模块开关",
}

BUSINESS_ACTIONS = {
    ("perform_action", "accept"): ("asset_accept", "验收入库"),
    ("perform_action", "assign"): ("asset_assign", "领用资产"),
    ("perform_action", "loan"): ("asset_loan", "借用资产"),
    ("perform_action", "extend"): ("asset_extend", "借用延期"),
    ("perform_action", "return"): ("asset_return", "归还资产"),
    ("perform_action", "transfer"): ("asset_transfer", "调拨资产"),
    ("perform_action", "dispose"): ("asset_dispose", "报废资产"),
    ("transact", "inbound"): ("inventory_inbound", "库存入库"),
    ("transact", "issue"): ("inventory_issue", "库存发放"),
    ("transact", "return"): ("inventory_return", "库存退回"),
    ("transact", "writeoff"): ("inventory_writeoff", "库存报损"),
}

TARGET_FIELDS = (
    "asset_tag",
    "contract_no",
    "request_no",
    "order_no",
    "plate_number",
    "sku",
    "name",
    "title",
    "display_name",
    "original_name",
    "label",
    "code",
)


def mark_operation(request, *, user=None, action="", target_label=""):
    raw_request = getattr(request, "_request", request)
    if user is not None:
        raw_request.user = user
    if action:
        raw_request.operation_log_action = action
    if target_label:
        raw_request.operation_log_target_label = target_label


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip()
    candidate = forwarded or request.META.get("HTTP_X_REAL_IP", "").strip() or request.META.get("REMOTE_ADDR", "").strip()
    try:
        return str(ipaddress.ip_address(candidate)) if candidate else None
    except ValueError:
        return None


def _response_payload(response):
    payload = getattr(response, "data", None)
    return payload if isinstance(payload, dict) else {}


def _target_label(request, response):
    explicit = getattr(request, "operation_log_target_label", "")
    if explicit:
        return str(explicit)[:255]
    payload = _response_payload(response)
    nested_user = payload.get("user")
    if isinstance(nested_user, dict):
        payload = nested_user
    values = []
    for field in TARGET_FIELDS:
        value = payload.get(field)
        if value not in (None, "") and str(value) not in values:
            values.append(str(value))
        if len(values) == 2:
            break
    return " · ".join(values)[:255]


def _route_context(request):
    match = getattr(request, "resolver_match", None)
    view_func = getattr(match, "func", None)
    initkwargs = getattr(view_func, "initkwargs", {}) or {}
    basename = str(initkwargs.get("basename") or "")
    actions = getattr(view_func, "actions", {}) or {}
    view_name = str(getattr(match, "view_name", "") or "")
    action = str(
        getattr(request, "operation_log_action", "")
        or actions.get(request.method.lower())
        or view_name
        or request.method.lower()
    )
    business_action = str(getattr(request, "operation_log_business_action", ""))
    business_mapping = BUSINESS_ACTIONS.get((action, business_action))
    if business_mapping:
        action, business_action_label = business_mapping
    else:
        business_action_label = ""

    module_key = basename
    if not module_key:
        if view_name.startswith("manager-settings") or view_name.startswith("module-settings"):
            module_key = "settings"
        elif view_name in {"local-login", "oidc-complete", "logout"}:
            module_key = "account"
        else:
            parts = [part for part in request.path.strip("/").split("/") if part]
            module_key = parts[2] if len(parts) > 2 else "account"
    module, module_label = MODULES.get(module_key, (module_key or "other", module_key or "其他"))

    if business_action_label:
        action_label = business_action_label
    elif action in {"files", "images"}:
        action_label = {"POST": "上传文件", "DELETE": "删除文件"}.get(request.method, "管理文件")
    else:
        action_label = ACTION_LABELS.get(action)
    if not action_label:
        action_label = {
            "POST": "新增",
            "PUT": "编辑",
            "PATCH": "编辑",
            "DELETE": "删除",
        }.get(request.method, "操作")
    return basename or view_name, module, module_label, action, action_label, view_name


class OperationLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method not in SAFE_METHODS
            and request.content_type == "application/json"
            and request.path.rstrip("/").endswith(("/actions", "/transactions"))
        ):
            try:
                payload = json.loads(request.body or b"{}")
                if isinstance(payload, dict) and payload.get("action"):
                    request.operation_log_business_action = str(payload["action"])
            except (TypeError, ValueError, UnicodeDecodeError):
                pass
        response = self.get_response(request)
        if request.method in SAFE_METHODS or not request.path.startswith("/api/v1/"):
            return response
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return response
        try:
            target_type, module, module_label, action, action_label, view_name = _route_context(request)
            match = getattr(request, "resolver_match", None)
            kwargs = getattr(match, "kwargs", {}) or {}
            payload = _response_payload(response)
            target_id = kwargs.get("pk") or payload.get("id") or ""
            OperationLog.objects.create(
                user=user,
                username=user.get_username(),
                display_name=user.get_full_name() or user.get_username(),
                module=module,
                module_label=module_label,
                action=action[:64],
                action_label=action_label,
                target_type=target_type[:80],
                target_id=str(target_id)[:64],
                target_label=_target_label(request, response),
                method=request.method,
                path=request.path[:500],
                status_code=response.status_code,
                succeeded=response.status_code < 400,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                details={"view_name": view_name},
            )
        except Exception:
            logger.exception("Unable to write operation log for %s %s", request.method, request.path)
        return response
