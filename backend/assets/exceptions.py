from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        message = str(detail["detail"])
        response.data = {"message": message, "errors": {}}
    else:
        response.data = {"message": "请检查填写内容。", "errors": detail}
    return response
