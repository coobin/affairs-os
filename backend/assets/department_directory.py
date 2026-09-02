"""部门主数据的统一规则和安全创建辅助方法。"""

from __future__ import annotations

import re
from uuid import uuid4

from django.db import transaction


DEPARTMENT_CODE_PREFIX = "263-"
DEPARTMENT_CODE_PATTERN = re.compile(r"^263-(?P<number>[0-9]+)$")

# 这些名称在当前系统中都代表已经并入人力资源部的旧部门。
DEPARTMENT_MERGE_TARGET = "人力资源部"
DEPARTMENT_MERGE_SOURCE_NAMES = ("行政部", "信息管理部", "信息技术部")
DEPARTMENT_NAME_ALIASES = {
    source: DEPARTMENT_MERGE_TARGET
    for source in DEPARTMENT_MERGE_SOURCE_NAMES
}


def canonical_department_name(name: str) -> str:
    """返回部门的规范名称；未配置别名的名称只做首尾空白清理。"""

    normalized = str(name or "").strip()
    return DEPARTMENT_NAME_ALIASES.get(normalized, normalized)


def is_standard_department_code(code: str | None) -> bool:
    return bool(DEPARTMENT_CODE_PATTERN.fullmatch(str(code or "").strip()))


def department_code_number(code: str | None) -> int | None:
    match = DEPARTMENT_CODE_PATTERN.fullmatch(str(code or "").strip())
    return int(match.group("number")) if match else None


def next_department_code(existing_codes) -> str:
    """根据已有部门编码计算下一个 263-数字编码。"""

    numbers = [
        number
        for code in existing_codes
        if (number := department_code_number(code)) is not None
    ]
    return f"{DEPARTMENT_CODE_PREFIX}{max(numbers, default=0) + 1}"


def allocate_department_code() -> str:
    """在当前事务中锁定部门行并分配一个不会复用的标准编码。"""

    from .models import Department

    existing_codes = Department.objects.select_for_update().values_list("code", flat=True)
    return next_department_code(existing_codes)


@transaction.atomic
def create_department(**validated_data):
    """创建部门并在拿到数据库主键后写入标准编码。"""

    from .models import Department

    # Department.code 非空且唯一，因此先放入一个短期占位编码，再换成标准编码。
    temporary_code = f"TMP-{uuid4().hex[:20]}"
    department = Department.objects.create(code=temporary_code, **validated_data)
    department.code = allocate_department_code()
    department.save(update_fields=["code", "updated_at"])
    return department
