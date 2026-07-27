from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .schedule import create_manual_visit, create_series_with_visits, generate_visits_for_series, reschedule_visit
from .schedule_models import (
    InspectionSeriesCreate,
    InspectionSeriesUpdate,
    InspectionVisitCreate,
    InspectionVisitUpdate,
    ScheduleSiteCreate,
    ScheduleSiteUpdate,
    ScheduleTechnicianCreate,
    ScheduleTechnicianUpdate,
    VisitAssignRequest,
    VisitRescheduleRequest,
    VisitStatusRequest,
)
from .schedule_store import ScheduleStore


def create_schedule_router(schedule_store: ScheduleStore) -> APIRouter:
    router = APIRouter(prefix="/schedule", tags=["schedule"])

    @router.get("/health", summary="排程資料庫狀態")
    def health():
        return schedule_store.health()

    @router.get("/sites", summary="列出場所")
    def list_sites(q: str | None = None):
        return {"sites": _safe(lambda: schedule_store.list_sites(q=q))}

    @router.post("/sites", summary="建立場所")
    def create_site(request: ScheduleSiteCreate):
        return _write(lambda: schedule_store.create_site(request.model_dump()))

    @router.get("/sites/{site_id}", summary="取得場所")
    def get_site(site_id: str):
        site = _safe(lambda: schedule_store.get_site(site_id))
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        return site

    @router.patch("/sites/{site_id}", summary="更新場所")
    def update_site(site_id: str, request: ScheduleSiteUpdate):
        site = _write(lambda: schedule_store.update_site(site_id, request.model_dump(exclude_unset=True)))
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        return site

    @router.get("/technicians", summary="列出技師")
    def list_technicians(active: bool | None = None):
        return {"technicians": _safe(lambda: schedule_store.list_technicians(active=active))}

    @router.post("/technicians", summary="建立技師")
    def create_technician(request: ScheduleTechnicianCreate):
        return _write(lambda: schedule_store.create_technician(request.model_dump()))

    @router.get("/technicians/{technician_id}", summary="取得技師")
    def get_technician(technician_id: str):
        technician = _safe(lambda: schedule_store.get_technician(technician_id))
        if not technician:
            raise HTTPException(status_code=404, detail="technician not found")
        return technician

    @router.patch("/technicians/{technician_id}", summary="更新技師")
    def update_technician(technician_id: str, request: ScheduleTechnicianUpdate):
        technician = _write(
            lambda: schedule_store.update_technician(technician_id, request.model_dump(exclude_unset=True))
        )
        if not technician:
            raise HTTPException(status_code=404, detail="technician not found")
        return technician

    @router.get("/series", summary="列出定期檢查 series")
    def list_series(site_id: str | None = None, active: bool | None = None, inspection_type: str | None = None):
        return {
            "series": _safe(
                lambda: schedule_store.list_series(
                    site_id=site_id,
                    active=active,
                    inspection_type=inspection_type,
                )
            )
        }

    @router.post("/series", summary="建立定期檢查 series 並產生 visits")
    def create_series(request: InspectionSeriesCreate):
        return _write(lambda: create_series_with_visits(schedule_store, request))

    @router.get("/series/{series_id}", summary="取得定期檢查 series")
    def get_series(series_id: str):
        series = _safe(lambda: schedule_store.get_series(series_id))
        if not series:
            raise HTTPException(status_code=404, detail="series not found")
        return series

    @router.patch("/series/{series_id}", summary="更新定期檢查 series metadata")
    def update_series(series_id: str, request: InspectionSeriesUpdate):
        series = _write(lambda: schedule_store.update_series(series_id, request.model_dump(exclude_unset=True)))
        if not series:
            raise HTTPException(status_code=404, detail="series not found")
        return series

    @router.post("/series/{series_id}/generate", summary="補產生 series visits")
    def generate_series(series_id: str):
        series = _safe(lambda: schedule_store.get_series(series_id))
        if not series:
            raise HTTPException(status_code=404, detail="series not found")
        visits = _write(lambda: generate_visits_for_series(schedule_store, series))
        return {"series_id": series_id, "generated_visit_count": len(visits), "visits": visits}

    @router.get("/visits", summary="列出 visits")
    def list_visits(
        from_date: date | None = Query(default=None, alias="from"),
        to_date: date | None = Query(default=None, alias="to"),
        technician_id: str | None = None,
        status: str | None = None,
        site_id: str | None = None,
        q: str | None = None,
    ):
        visits = _safe(
            lambda: schedule_store.list_visits(
                from_iso=_date_start(from_date),
                to_iso=_date_end(to_date),
                technician_id=technician_id,
                status=status,
                site_id=site_id,
                q=q,
            )
        )
        return {"visits": visits}

    @router.get("/calendar", summary="排程行事曆資料")
    def calendar(
        from_date: date | None = Query(default=None, alias="from"),
        to_date: date | None = Query(default=None, alias="to"),
        view: str = "month",
    ):
        visits = _safe(lambda: schedule_store.list_visits(from_iso=_date_start(from_date), to_iso=_date_end(to_date)))
        return {"view": view, "from": from_date, "to": to_date, "visits": visits}

    @router.get("/dispatch-board", summary="派工看板資料")
    def dispatch_board(date: date, include_inactive: bool = False):
        visits = _safe(lambda: schedule_store.list_visits(from_iso=_date_start(date), to_iso=_date_end(date)))
        technicians = _safe(lambda: schedule_store.list_technicians(active=None if include_inactive else True))
        by_tech: dict[str, list[dict[str, Any]]] = {}
        unassigned: list[dict[str, Any]] = []
        for visit in visits:
            technician_id = visit.get("assigned_technician_id")
            if technician_id:
                by_tech.setdefault(technician_id, []).append(visit)
            else:
                unassigned.append(visit)
        return {
            "date": date.isoformat(),
            "technicians": [
                {**technician, "visit_count": len(by_tech.get(technician["technician_id"], [])), "visits": by_tech.get(technician["technician_id"], [])}
                for technician in technicians
            ],
            "unassigned": unassigned,
        }

    @router.get("/map", summary="地圖排程資料")
    def map_points(
        from_date: date | None = Query(default=None, alias="from"),
        to_date: date | None = Query(default=None, alias="to"),
    ):
        visits = _safe(lambda: schedule_store.list_visits(from_iso=_date_start(from_date), to_iso=_date_end(to_date)))
        points = []
        for visit in visits:
            site = visit.get("site") or {}
            if site.get("latitude") is None or site.get("longitude") is None:
                continue
            points.append(
                {
                    "visit_id": visit["visit_id"],
                    "title": visit["title"],
                    "scheduled_start": visit["scheduled_start"],
                    "status": visit["status"],
                    "technician": visit.get("assigned_technician"),
                    "site_id": site["site_id"],
                    "site_name": site["name"],
                    "latitude": site["latitude"],
                    "longitude": site["longitude"],
                }
            )
        return {"points": points}

    @router.post("/visits", summary="建立單次 visit")
    def create_visit(request: InspectionVisitCreate):
        return _write(lambda: create_manual_visit(schedule_store, request))

    @router.get("/visits/{visit_id}", summary="取得 visit")
    def get_visit(visit_id: str):
        visit = _safe(lambda: schedule_store.get_visit(visit_id))
        if not visit:
            raise HTTPException(status_code=404, detail="visit not found")
        return visit

    @router.patch("/visits/{visit_id}", summary="更新 visit metadata")
    def update_visit(visit_id: str, request: InspectionVisitUpdate):
        visit = _write(lambda: schedule_store.update_visit(visit_id, request.model_dump(exclude_unset=True)))
        if not visit:
            raise HTTPException(status_code=404, detail="visit not found")
        return visit

    @router.post("/visits/{visit_id}/assign", summary="指派 visit 給技師")
    def assign_visit(visit_id: str, request: VisitAssignRequest):
        return _write(lambda: schedule_store.assign_visit(visit_id, request.technician_id, request.note))

    @router.post("/visits/{visit_id}/status", summary="更新 visit 狀態")
    def update_status(visit_id: str, request: VisitStatusRequest):
        return _write(lambda: schedule_store.set_visit_status(visit_id, request.status, request.note))

    @router.post("/visits/{visit_id}/reschedule", summary="改期 visit")
    def reschedule(visit_id: str, request: VisitRescheduleRequest):
        return _write(lambda: reschedule_visit(schedule_store, visit_id, request))

    @router.get("/visits/{visit_id}/status-events", summary="列出 visit 狀態紀錄")
    def status_events(visit_id: str):
        _ensure_visit(schedule_store, visit_id)
        return {"events": _safe(lambda: schedule_store.list_status_events(visit_id))}

    @router.get("/visits/{visit_id}/reschedule-events", summary="列出 visit 改期紀錄")
    def reschedule_events(visit_id: str):
        _ensure_visit(schedule_store, visit_id)
        return {"events": _safe(lambda: schedule_store.list_reschedule_events(visit_id))}

    return router


def _safe(call):
    try:
        return call()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _write(call):
    try:
        return call()
    except PermissionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_visit(schedule_store: ScheduleStore, visit_id: str) -> None:
    if not _safe(lambda: schedule_store.get_visit(visit_id)):
        raise HTTPException(status_code=404, detail="visit not found")


def _date_start(value: date | None) -> str | None:
    if not value:
        return None
    return f"{value.isoformat()}T00:00:00+08:00"


def _date_end(value: date | None) -> str | None:
    if not value:
        return None
    return f"{value.isoformat()}T23:59:59+08:00"
