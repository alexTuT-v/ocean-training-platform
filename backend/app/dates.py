from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_local(issued_at_utc: datetime, tenant_timezone: str) -> tuple[str, str]:
    if issued_at_utc.tzinfo is None:
        raise ValueError("issued_at_utc must be timezone-aware")
    local = issued_at_utc.astimezone(ZoneInfo(tenant_timezone))
    return local.strftime("%Y-%m-%d"), local.strftime("%Y-%m-%d %H:%M")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_text() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
