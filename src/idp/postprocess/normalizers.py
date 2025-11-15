from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def normalize_amount(value: str | float | int | Decimal | None) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    cleaned = value.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_date(value: str | datetime | None) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
