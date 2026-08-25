from datetime import date, timedelta


EXPIRY_REMINDER_DAYS = (45, 30, 15, 7)


def expiry_reminder_stage(end_date: date, today: date) -> str | None:
    """Return the one-day reminder stage for an expiring item, if applicable."""
    days_to_expiry = (end_date - today).days
    if days_to_expiry in EXPIRY_REMINDER_DAYS:
        return f"before-{days_to_expiry}"
    if days_to_expiry == 0:
        return "due-today"
    if days_to_expiry < 0:
        return f"overdue-{today:%Y-%m-%d}"
    return None


def expiry_reminder_dates(today: date):
    return [today + timedelta(days=days) for days in EXPIRY_REMINDER_DAYS]
