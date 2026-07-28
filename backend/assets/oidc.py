from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import EmployeeProfile


oauth = OAuth()
oauth.register(
    name="authelia",
    client_id=settings.OIDC_CLIENT_ID,
    client_secret=settings.OIDC_CLIENT_SECRET,
    server_metadata_url=f"{settings.OIDC_ISSUER.rstrip('/')}/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid profile email",
        "code_challenge_method": "S256",
    },
    token_endpoint_auth_method="client_secret_basic",
)


def sync_oidc_user(userinfo):
    username = str(
        userinfo.get("preferred_username") or userinfo.get("username") or ""
    ).strip()
    if not username or "@" in username:
        raise ValueError("OIDC 账号未提供有效的登录名。")

    User = get_user_model()
    user = User.objects.filter(username__iexact=username).first()
    if user is None:
        user = User(username=username)
        user.set_unusable_password()

    given_name = str(userinfo.get("given_name") or "").strip()
    family_name = str(userinfo.get("family_name") or "").strip()
    display_name = str(userinfo.get("name") or "").strip()
    if not given_name and not family_name and display_name:
        given_name = display_name

    user.username = username
    user.email = str(userinfo.get("email") or "").strip()
    user.first_name = given_name[:150]
    user.last_name = family_name[:150]
    user.is_active = True
    if username.casefold() == settings.DJANGO_SUPERUSER_USERNAME.casefold():
        user.is_staff = True
        user.is_superuser = True
    user.save()

    # OIDC 是用户的唯一来源。首次登录时建立最小人员档案，
    # 便于资产领用和管理员权限设置；邮箱只作为联系方式。
    EmployeeProfile.objects.get_or_create(
        user=user,
        defaults={"employee_no": username[:32]},
    )
    return user
