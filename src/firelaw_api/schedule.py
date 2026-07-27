from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from .schedule_models import (
    InspectionSeriesCreate,
    InspectionVisitCreate,
    VisitRescheduleRequest,
)
from .schedule_recurrence import TAIPEI_TZ, generate_visit_starts
from .schedule_store import ScheduleStore


def create_series_with_visits(store: ScheduleStore, request: InspectionSeriesCreate) -> dict[str, Any]:
    series = store.create_series(
        {
            "site_id": request.site_id,
            "title": request.title,
            "inspection_type": request.inspection_type,
            "recurrence_frequency": request.recurrence_frequency,
            "recurrence_interval": request.recurrence_interval,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat() if request.end_date else None,
            "preferred_start_time": request.preferred_start_time.strftime("%H:%M"),
            "duration_minutes": request.duration_minutes,
            "default_technician_id": request.default_technician_id,
            "shift_future_on_reschedule": request.shift_future_on_reschedule,
            "notes": request.notes,
        }
    )
    visits = generate_visits_for_series(store, series)
    return {
        **series,
        "generated_visit_count": len(visits),
        "next_visit": _next_visit_summary(visits),
    }


def generate_visits_for_series(store: ScheduleStore, series: dict[str, Any]) -> list[dict[str, Any]]:
    starts = generate_visit_starts(
        start_date=date.fromisoformat(series["start_date"]),
        preferred_start_time=time.fromisoformat(series["preferred_start_time"]),
        frequency=series["recurrence_frequency"],
        interval=int(series["recurrence_interval"]),
        end_date=date.fromisoformat(series["end_date"]) if series.get("end_date") else None,
    )
    visits: list[dict[str, Any]] = []
    for start in starts:
        end = start + timedelta(minutes=int(series["duration_minutes"]))
        visit = store.create_visit(
            {
                "series_id": series["series_id"],
                "site_id": series["site_id"],
                "title": series["title"],
                "inspection_type": series["inspection_type"],
                "scheduled_start": _iso(start),
                "scheduled_end": _iso(end),
                "original_scheduled_start": _iso(start),
                "assigned_technician_id": series.get("default_technician_id"),
                "status": "scheduled",
                "source_kind": "series",
                "notes": series.get("notes") or "",
            }
        )
        if visit:
            visits.append(visit)
    return visits


def create_manual_visit(store: ScheduleStore, request: InspectionVisitCreate) -> dict[str, Any]:
    start = _ensure_taipei(request.scheduled_start)
    end = start + timedelta(minutes=request.duration_minutes)
    return store.create_visit(
        {
            "site_id": request.site_id,
            "title": request.title,
            "inspection_type": request.inspection_type,
            "scheduled_start": _iso(start),
            "scheduled_end": _iso(end),
            "original_scheduled_start": _iso(start),
            "assigned_technician_id": request.assigned_technician_id,
            "status": "scheduled",
            "source_kind": "manual",
            "notes": request.notes,
        }
    )


def reschedule_visit(store: ScheduleStore, visit_id: str, request: VisitRescheduleRequest) -> dict[str, Any]:
    visit = store.get_visit(visit_id)
    if not visit:
        raise LookupError("visit not found")
    old_start = datetime.fromisoformat(visit["scheduled_start"])
    old_end = datetime.fromisoformat(visit["scheduled_end"])
    duration = old_end - old_start
    new_start = _ensure_taipei(request.scheduled_start)
    new_end = new_start + duration
    return store.reschedule_visit(
        visit_id,
        new_start=_iso(new_start),
        new_end=_iso(new_end),
        scope=request.scope,
        reason=request.reason,
    )


def _next_visit_summary(visits: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not visits:
        return None
    visit = sorted(visits, key=lambda item: item["scheduled_start"])[0]
    return {
        "visit_id": visit["visit_id"],
        "scheduled_start": visit["scheduled_start"],
        "status": visit["status"],
    }


def _ensure_taipei(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TAIPEI_TZ)
    return value.astimezone(TAIPEI_TZ)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()
