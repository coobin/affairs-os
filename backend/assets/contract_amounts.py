from decimal import Decimal, InvalidOperation
import re
import unicodedata


PURE_AMOUNT_PATTERN = re.compile(
    r"^[\s¥￥]*(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)[\s]*(?:元|人民币)?[\s]*$"
)


def amount_from_description(value: str | None) -> Decimal | None:
    """Return an amount only when the description contains one unqualified total."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    matched = PURE_AMOUNT_PATTERN.fullmatch(text)
    if not matched:
        return None
    try:
        amount = Decimal(matched.group("amount").replace(",", "")).quantize(
            Decimal("0.01")
        )
    except InvalidOperation:
        return None
    return amount if amount >= 0 else None
