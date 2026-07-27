from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


ScheduleStatus = Literal[
    "draft",
    "scheduled",
    "dispatched",
    "in_progress",
    "waiting_review",
    "completed",
    "missed",
    "cancelled",
]
RecurrenceFrequency = Literal["weekly", "monthly", "quarterly", "semiannual", "annual"]
RescheduleScope = Literal["single", "this_and_future"]


class ScheduleSiteCreate(BaseModel):
    name: str = Field(min_length=1)
    customer_name: str = ""
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    latitude: float | None = None
    longitude: float | None = None
    notes: str = ""


class ScheduleSiteUpdate(BaseModel):
    name: str | None = None
    customer_name: str | None = None
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None


class ScheduleTechnicianCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""
    role: str = "technician"
    active: bool = True
    color: str = "#2563eb"


class ScheduleTechnicianUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    role: str | None = None
    active: bool | None = None
    color: str | None = None


class InspectionSeriesCreate(BaseModel):
    site_id: str
    title: str = Field(min_length=1)
    inspection_type: str = Field(min_length=1)
    recurrence_frequency: RecurrenceFrequency
    recurrence_interval: int = Field(default=1, ge=1)
    start_date: date
    end_date: date | None = None
    preferred_start_time: time = time(9, 0)
    duration_minutes: int = Field(default=120, ge=15, le=1440)
    default_technician_id: str | None = None
    shift_future_on_reschedule: bool = False
    notes: str = ""


class InspectionSeriesUpdate(BaseModel):
    title: str | None = None
    inspection_type: str | None = None
    active: bool | None = None
    notes: str | None = None


class InspectionVisitCreate(BaseModel):
    site_id: str
    title: str = Field(min_length=1)
    inspection_type: str = Field(min_length=1)
    scheduled_start: datetime
    duration_minutes: int = Field(default=120, ge=15, le=1440)
    assigned_technician_id: str | None = None
    notes: str = ""


class InspectionVisitUpdate(BaseModel):
    title: str | None = None
    inspection_type: str | None = None
    notes: str | None = None


class VisitAssignRequest(BaseModel):
    technician_id: str
    note: str = ""


class VisitStatusRequest(BaseModel):
    status: ScheduleStatus
    note: str = ""


class VisitRescheduleRequest(BaseModel):
    scheduled_start: datetime
    scope: RescheduleScope = "single"
    reason: str = ""
