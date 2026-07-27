from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone


TAIPEI_TZ = timezone(timedelta(hours=8))
MONTH_FREQUENCIES = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}


def generate_visit_starts(
    *,
    start_date: date,
    preferred_start_time: time,
    frequency: str,
    interval: int,
    end_date: date | None,
    months_ahead: int = 18,
) -> list[datetime]:
    if interval < 1:
        raise ValueError("interval must be at least 1")
    window_end = _add_months(start_date, months_ahead, start_date.day)
    if end_date and end_date < window_end:
        window_end = end_date

    starts: list[datetime] = []
    if frequency == "weekly":
        step_days = 7 * interval
        current = start_date
        while current <= window_end:
            starts.append(_combine(current, preferred_start_time))
            current = current + timedelta(days=step_days)
        return starts

    if frequency not in MONTH_FREQUENCIES:
        raise ValueError(f"unsupported recurrence frequency: {frequency}")

    month_step = MONTH_FREQUENCIES[frequency] * interval
    occurrence = 0
    while True:
        current = _add_months(start_date, month_step * occurrence, start_date.day)
        if current > window_end:
            break
        starts.append(_combine(current, preferred_start_time))
        occurrence += 1
    return starts


def _add_months(value: date, months: int, anchor_day: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor_day, monthrange(year, month)[1])
    return date(year, month, day)


def _combine(value: date, value_time: time) -> datetime:
    if value_time.tzinfo is None:
        value_time = value_time.replace(tzinfo=TAIPEI_TZ)
    return datetime.combine(value, value_time)
