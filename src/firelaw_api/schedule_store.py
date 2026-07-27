from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import secrets
import sqlite3
from typing import Any


TERMINAL_STATUSES = {"completed", "cancelled"}


class ScheduleStore:
    def __init__(self, db_path: Path, writable: bool = True):
        self.db_path = Path(db_path)
        self.writable = writable

    def migrate(self) -> None:
        self.ensure_writable()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def ensure_writable(self) -> None:
        if not self.writable:
            raise PermissionError("schedule database is read-only in this environment")

    def health(self) -> dict[str, Any]:
        if not self.writable and not self.db_path.exists():
            return {
                "status": "degraded",
                "app_db": str(self.db_path),
                "writable": False,
                "reason": "schedule database missing in read-only mode",
            }
        if not self.db_path.exists():
            return {
                "status": "degraded",
                "app_db": str(self.db_path),
                "writable": self.writable,
                "reason": "schedule database missing",
            }
        try:
            with self._connect() as conn:
                site_count = conn.execute("SELECT COUNT(*) FROM schedule_sites").fetchone()[0]
                technician_count = conn.execute("SELECT COUNT(*) FROM schedule_technicians").fetchone()[0]
                visit_count = conn.execute("SELECT COUNT(*) FROM inspection_visits").fetchone()[0]
        except sqlite3.Error as exc:
            return {"status": "degraded", "app_db": str(self.db_path), "writable": self.writable, "reason": str(exc)}
        return {
            "status": "ok" if self.writable else "read_only",
            "app_db": str(self.db_path),
            "writable": self.writable,
            "site_count": site_count,
            "technician_count": technician_count,
            "visit_count": visit_count,
        }

    def create_site(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        site_id = _new_id("site")
        row = {
            "site_id": site_id,
            "name": payload["name"],
            "customer_name": payload.get("customer_name") or "",
            "address": payload.get("address") or "",
            "contact_name": payload.get("contact_name") or "",
            "contact_phone": payload.get("contact_phone") or "",
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "notes": payload.get("notes") or "",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedule_sites (
                    site_id, name, customer_name, address, contact_name, contact_phone,
                    latitude, longitude, notes, created_at, updated_at
                ) VALUES (
                    :site_id, :name, :customer_name, :address, :contact_name, :contact_phone,
                    :latitude, :longitude, :notes, :created_at, :updated_at
                )
                """,
                row,
            )
        return row

    def list_sites(self, q: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM schedule_sites WHERE 1 = 1"
        params: list[Any] = []
        if q:
            like = f"%{q.lower()}%"
            sql += " AND (lower(name) LIKE ? OR lower(customer_name) LIKE ? OR lower(address) LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY name, site_id"
        with self._connect_existing() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def get_site(self, site_id: str) -> dict[str, Any] | None:
        with self._connect_existing() as conn:
            row = conn.execute("SELECT * FROM schedule_sites WHERE site_id = ?", (site_id,)).fetchone()
        return _dict(row) if row else None

    def update_site(self, site_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self._update_row("schedule_sites", "site_id", site_id, payload)

    def create_technician(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        row = {
            "technician_id": _new_id("tech"),
            "name": payload["name"],
            "phone": payload.get("phone") or "",
            "role": payload.get("role") or "technician",
            "active": 1 if payload.get("active", True) else 0,
            "color": payload.get("color") or "#2563eb",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedule_technicians (
                    technician_id, name, phone, role, active, color, created_at, updated_at
                ) VALUES (
                    :technician_id, :name, :phone, :role, :active, :color, :created_at, :updated_at
                )
                """,
                row,
            )
        return _normalize_technician(row)

    def list_technicians(self, active: bool | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM schedule_technicians WHERE 1 = 1"
        params: list[Any] = []
        if active is not None:
            sql += " AND active = ?"
            params.append(1 if active else 0)
        sql += " ORDER BY active DESC, name"
        with self._connect_existing() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_normalize_technician(_dict(row)) for row in rows]

    def get_technician(self, technician_id: str) -> dict[str, Any] | None:
        with self._connect_existing() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_technicians WHERE technician_id = ?",
                (technician_id,),
            ).fetchone()
        return _normalize_technician(_dict(row)) if row else None

    def update_technician(self, technician_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self._update_row("schedule_technicians", "technician_id", technician_id, _bool_payload(payload, ["active"]))
        return _normalize_technician(row) if row else None

    def create_series(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        row = {
            "series_id": _new_id("series"),
            "site_id": payload["site_id"],
            "title": payload["title"],
            "inspection_type": payload["inspection_type"],
            "recurrence_frequency": payload["recurrence_frequency"],
            "recurrence_interval": payload.get("recurrence_interval") or 1,
            "start_date": payload["start_date"],
            "end_date": payload.get("end_date"),
            "preferred_start_time": payload.get("preferred_start_time") or "09:00",
            "duration_minutes": payload.get("duration_minutes") or 120,
            "default_technician_id": payload.get("default_technician_id"),
            "shift_future_on_reschedule": 1 if payload.get("shift_future_on_reschedule", False) else 0,
            "active": 1,
            "notes": payload.get("notes") or "",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inspection_series (
                    series_id, site_id, title, inspection_type, recurrence_frequency,
                    recurrence_interval, start_date, end_date, preferred_start_time,
                    duration_minutes, default_technician_id, shift_future_on_reschedule,
                    active, notes, created_at, updated_at
                ) VALUES (
                    :series_id, :site_id, :title, :inspection_type, :recurrence_frequency,
                    :recurrence_interval, :start_date, :end_date, :preferred_start_time,
                    :duration_minutes, :default_technician_id, :shift_future_on_reschedule,
                    :active, :notes, :created_at, :updated_at
                )
                """,
                row,
            )
        return _normalize_series(row)

    def list_series(
        self,
        *,
        site_id: str | None = None,
        active: bool | None = None,
        inspection_type: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM inspection_series WHERE 1 = 1"
        params: list[Any] = []
        if site_id:
            sql += " AND site_id = ?"
            params.append(site_id)
        if active is not None:
            sql += " AND active = ?"
            params.append(1 if active else 0)
        if inspection_type:
            sql += " AND inspection_type = ?"
            params.append(inspection_type)
        sql += " ORDER BY start_date, title"
        with self._connect_existing() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_normalize_series(_dict(row)) for row in rows]

    def get_series(self, series_id: str) -> dict[str, Any] | None:
        with self._connect_existing() as conn:
            row = conn.execute("SELECT * FROM inspection_series WHERE series_id = ?", (series_id,)).fetchone()
        return _normalize_series(_dict(row)) if row else None

    def update_series(self, series_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self._update_row("inspection_series", "series_id", series_id, _bool_payload(payload, ["active"]))
        return _normalize_series(row) if row else None

    def create_visit(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_writable()
        visit_id = _new_id("visit")
        now = _now()
        row = {
            "visit_id": visit_id,
            "series_id": payload.get("series_id"),
            "site_id": payload["site_id"],
            "title": payload["title"],
            "inspection_type": payload["inspection_type"],
            "scheduled_start": payload["scheduled_start"],
            "scheduled_end": payload["scheduled_end"],
            "original_scheduled_start": payload.get("original_scheduled_start") or payload["scheduled_start"],
            "status": payload.get("status") or "scheduled",
            "assigned_technician_id": payload.get("assigned_technician_id"),
            "source_kind": payload.get("source_kind") or "manual",
            "notes": payload.get("notes") or "",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO inspection_visits (
                    visit_id, series_id, site_id, title, inspection_type, scheduled_start,
                    scheduled_end, original_scheduled_start, status, assigned_technician_id,
                    source_kind, notes, created_at, updated_at
                ) VALUES (
                    :visit_id, :series_id, :site_id, :title, :inspection_type, :scheduled_start,
                    :scheduled_end, :original_scheduled_start, :status, :assigned_technician_id,
                    :source_kind, :notes, :created_at, :updated_at
                )
                """,
                row,
            )
            inserted = conn.execute("SELECT changes()").fetchone()[0]
        return self.get_visit(visit_id) if inserted else self.get_visit_by_original(row["series_id"], row["original_scheduled_start"])

    def get_visit_by_original(self, series_id: str | None, original_scheduled_start: str) -> dict[str, Any] | None:
        if not series_id:
            return None
        with self._connect_existing() as conn:
            row = conn.execute(
                """
                SELECT visit_id
                FROM inspection_visits
                WHERE series_id = ? AND original_scheduled_start = ?
                """,
                (series_id, original_scheduled_start),
            ).fetchone()
        return self.get_visit(row["visit_id"]) if row else None

    def list_visits(
        self,
        *,
        from_iso: str | None = None,
        to_iso: str | None = None,
        technician_id: str | None = None,
        status: str | None = None,
        site_id: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                v.*,
                s.name AS site_name, s.customer_name, s.address, s.latitude, s.longitude,
                t.name AS technician_name, t.color AS technician_color
            FROM inspection_visits v
            JOIN schedule_sites s ON s.site_id = v.site_id
            LEFT JOIN schedule_technicians t ON t.technician_id = v.assigned_technician_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if from_iso:
            sql += " AND v.scheduled_start >= ?"
            params.append(from_iso)
        if to_iso:
            sql += " AND v.scheduled_start <= ?"
            params.append(to_iso)
        if technician_id:
            sql += " AND v.assigned_technician_id = ?"
            params.append(technician_id)
        if status:
            sql += " AND v.status = ?"
            params.append(status)
        if site_id:
            sql += " AND v.site_id = ?"
            params.append(site_id)
        if q:
            like = f"%{q.lower()}%"
            sql += """
                AND (
                    lower(v.title) LIKE ?
                    OR lower(v.inspection_type) LIKE ?
                    OR lower(v.status) LIKE ?
                    OR lower(s.name) LIKE ?
                    OR lower(s.customer_name) LIKE ?
                    OR lower(t.name) LIKE ?
                )
            """
            params.extend([like] * 6)
        sql += " ORDER BY v.scheduled_start, v.title"
        with self._connect_existing() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_visit_from_row(row) for row in rows]

    def get_visit(self, visit_id: str) -> dict[str, Any] | None:
        with self._connect_existing() as conn:
            row = conn.execute(
                """
                SELECT
                    v.*,
                    s.name AS site_name, s.customer_name, s.address, s.latitude, s.longitude,
                    t.name AS technician_name, t.color AS technician_color
                FROM inspection_visits v
                JOIN schedule_sites s ON s.site_id = v.site_id
                LEFT JOIN schedule_technicians t ON t.technician_id = v.assigned_technician_id
                WHERE v.visit_id = ?
                """,
                (visit_id,),
            ).fetchone()
        return _visit_from_row(row) if row else None

    def update_visit(self, visit_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self._update_row("inspection_visits", "visit_id", visit_id, payload)
        return self.get_visit(row["visit_id"]) if row else None

    def assign_visit(self, visit_id: str, technician_id: str, note: str = "") -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        assignment_id = _new_id("assign")
        with self._connect() as conn:
            visit = conn.execute("SELECT status FROM inspection_visits WHERE visit_id = ?", (visit_id,)).fetchone()
            if not visit:
                raise LookupError("visit not found")
            technician = conn.execute(
                "SELECT technician_id FROM schedule_technicians WHERE technician_id = ?",
                (technician_id,),
            ).fetchone()
            if not technician:
                raise LookupError("technician not found")
            conn.execute(
                "UPDATE visit_assignments SET unassigned_at = ? WHERE visit_id = ? AND unassigned_at IS NULL",
                (now, visit_id),
            )
            conn.execute(
                """
                INSERT INTO visit_assignments (assignment_id, visit_id, technician_id, assigned_at, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (assignment_id, visit_id, technician_id, now, note),
            )
            conn.execute(
                """
                UPDATE inspection_visits
                SET assigned_technician_id = ?, status = 'dispatched', updated_at = ?
                WHERE visit_id = ?
                """,
                (technician_id, now, visit_id),
            )
            self._insert_status_event(conn, visit_id, visit["status"], "dispatched", note)
        return {
            "visit_id": visit_id,
            "assigned_technician_id": technician_id,
            "status": "dispatched",
            "assignment_id": assignment_id,
        }

    def set_visit_status(self, visit_id: str, status: str, note: str = "") -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        with self._connect() as conn:
            visit = conn.execute("SELECT status FROM inspection_visits WHERE visit_id = ?", (visit_id,)).fetchone()
            if not visit:
                raise LookupError("visit not found")
            conn.execute(
                "UPDATE inspection_visits SET status = ?, updated_at = ? WHERE visit_id = ?",
                (status, now, visit_id),
            )
            self._insert_status_event(conn, visit_id, visit["status"], status, note)
        return self.get_visit(visit_id)

    def reschedule_visit(self, visit_id: str, new_start: str, new_end: str, scope: str, reason: str = "") -> dict[str, Any]:
        self.ensure_writable()
        now = _now()
        change_id = _new_id("change")
        with self._connect() as conn:
            visit = conn.execute("SELECT * FROM inspection_visits WHERE visit_id = ?", (visit_id,)).fetchone()
            if not visit:
                raise LookupError("visit not found")

            old_start = visit["scheduled_start"]
            delta_days = (_parse_iso(new_start).date() - _parse_iso(old_start).date()).days
            affected = 1
            conn.execute(
                """
                UPDATE inspection_visits
                SET scheduled_start = ?, scheduled_end = ?, updated_at = ?
                WHERE visit_id = ?
                """,
                (new_start, new_end, now, visit_id),
            )
            if scope == "this_and_future" and visit["series_id"]:
                future_rows = conn.execute(
                    """
                    SELECT visit_id, scheduled_start, scheduled_end
                    FROM inspection_visits
                    WHERE series_id = ?
                      AND visit_id != ?
                      AND scheduled_start > ?
                      AND status NOT IN ('completed', 'cancelled')
                    ORDER BY scheduled_start
                    """,
                    (visit["series_id"], visit_id, old_start),
                ).fetchall()
                for future in future_rows:
                    shifted_start = _parse_iso(future["scheduled_start"]) + timedelta(days=delta_days)
                    shifted_end = _parse_iso(future["scheduled_end"]) + timedelta(days=delta_days)
                    conn.execute(
                        """
                        UPDATE inspection_visits
                        SET scheduled_start = ?, scheduled_end = ?, updated_at = ?
                        WHERE visit_id = ?
                        """,
                        (_iso(shifted_start), _iso(shifted_end), now, future["visit_id"]),
                    )
                affected += len(future_rows)
            conn.execute(
                """
                INSERT INTO schedule_change_events (
                    change_id, visit_id, series_id, old_scheduled_start, new_scheduled_start,
                    scope, affected_visit_count, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (change_id, visit_id, visit["series_id"], old_start, new_start, scope, affected, reason, now),
            )
        return {
            "change_id": change_id,
            "visit_id": visit_id,
            "scope": scope,
            "old_scheduled_start": old_start,
            "new_scheduled_start": new_start,
            "delta_days": delta_days,
            "affected_visit_count": affected,
        }

    def list_status_events(self, visit_id: str) -> list[dict[str, Any]]:
        with self._connect_existing() as conn:
            rows = conn.execute(
                """
                SELECT event_id, visit_id, previous_status, new_status, note, created_at
                FROM visit_status_events
                WHERE visit_id = ?
                ORDER BY rowid
                """,
                (visit_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_reschedule_events(self, visit_id: str) -> list[dict[str, Any]]:
        with self._connect_existing() as conn:
            rows = conn.execute(
                """
                SELECT
                    change_id, visit_id, series_id, old_scheduled_start,
                    new_scheduled_start, scope, affected_visit_count, reason, created_at
                FROM schedule_change_events
                WHERE visit_id = ?
                ORDER BY rowid
                """,
                (visit_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _insert_status_event(
        self,
        conn: sqlite3.Connection,
        visit_id: str,
        previous_status: str | None,
        new_status: str,
        note: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO visit_status_events (event_id, visit_id, previous_status, new_status, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_new_id("event"), visit_id, previous_status, new_status, note, _now()),
        )

    def _update_row(self, table: str, id_column: str, row_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self.ensure_writable()
        allowed = {
            key: value
            for key, value in payload.items()
            if value is not None and key not in {id_column, "created_at", "updated_at"}
        }
        if not allowed:
            return getattr(self, f"get_{id_column.removesuffix('_id')}")(row_id)
        allowed["updated_at"] = _now()
        assignments = ", ".join(f"{key} = :{key}" for key in allowed)
        allowed[id_column] = row_id
        with self._connect() as conn:
            conn.execute(f"UPDATE {table} SET {assignments} WHERE {id_column} = :{id_column}", allowed)
            changed = conn.execute("SELECT changes()").fetchone()[0]
        if not changed:
            return None
        with self._connect_existing() as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (row_id,)).fetchone()
        return _dict(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _connect_existing(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"schedule database not found: {self.db_path}")
        return self._connect()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schedule_sites (
  site_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  customer_name TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  contact_name TEXT NOT NULL DEFAULT '',
  contact_phone TEXT NOT NULL DEFAULT '',
  latitude REAL,
  longitude REAL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_technicians (
  technician_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT 'technician',
  active INTEGER NOT NULL DEFAULT 1,
  color TEXT NOT NULL DEFAULT '#2563eb',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inspection_series (
  series_id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  title TEXT NOT NULL,
  inspection_type TEXT NOT NULL,
  recurrence_frequency TEXT NOT NULL,
  recurrence_interval INTEGER NOT NULL DEFAULT 1,
  start_date TEXT NOT NULL,
  end_date TEXT,
  preferred_start_time TEXT NOT NULL DEFAULT '09:00',
  duration_minutes INTEGER NOT NULL DEFAULT 120,
  default_technician_id TEXT,
  shift_future_on_reschedule INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(site_id) REFERENCES schedule_sites(site_id),
  FOREIGN KEY(default_technician_id) REFERENCES schedule_technicians(technician_id),
  CHECK(recurrence_frequency IN ('weekly','monthly','quarterly','semiannual','annual')),
  CHECK(recurrence_interval >= 1),
  CHECK(duration_minutes BETWEEN 15 AND 1440)
);

CREATE TABLE IF NOT EXISTS inspection_visits (
  visit_id TEXT PRIMARY KEY,
  series_id TEXT,
  site_id TEXT NOT NULL,
  title TEXT NOT NULL,
  inspection_type TEXT NOT NULL,
  scheduled_start TEXT NOT NULL,
  scheduled_end TEXT NOT NULL,
  original_scheduled_start TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  assigned_technician_id TEXT,
  source_kind TEXT NOT NULL DEFAULT 'series',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(series_id) REFERENCES inspection_series(series_id),
  FOREIGN KEY(site_id) REFERENCES schedule_sites(site_id),
  FOREIGN KEY(assigned_technician_id) REFERENCES schedule_technicians(technician_id),
  CHECK(status IN ('draft','scheduled','dispatched','in_progress','waiting_review','completed','missed','cancelled')),
  CHECK(source_kind IN ('series','manual'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inspection_visits_series_original
ON inspection_visits(series_id, original_scheduled_start)
WHERE series_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_inspection_visits_scheduled_start
ON inspection_visits(scheduled_start);

CREATE INDEX IF NOT EXISTS idx_inspection_visits_technician_time
ON inspection_visits(assigned_technician_id, scheduled_start);

CREATE INDEX IF NOT EXISTS idx_inspection_visits_status_time
ON inspection_visits(status, scheduled_start);

CREATE TABLE IF NOT EXISTS visit_status_events (
  event_id TEXT PRIMARY KEY,
  visit_id TEXT NOT NULL,
  previous_status TEXT,
  new_status TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY(visit_id) REFERENCES inspection_visits(visit_id)
);

CREATE TABLE IF NOT EXISTS visit_assignments (
  assignment_id TEXT PRIMARY KEY,
  visit_id TEXT NOT NULL,
  technician_id TEXT NOT NULL,
  assigned_at TEXT NOT NULL,
  unassigned_at TEXT,
  note TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(visit_id) REFERENCES inspection_visits(visit_id),
  FOREIGN KEY(technician_id) REFERENCES schedule_technicians(technician_id)
);

CREATE TABLE IF NOT EXISTS schedule_change_events (
  change_id TEXT PRIMARY KEY,
  visit_id TEXT NOT NULL,
  series_id TEXT,
  old_scheduled_start TEXT NOT NULL,
  new_scheduled_start TEXT NOT NULL,
  scope TEXT NOT NULL,
  affected_visit_count INTEGER NOT NULL DEFAULT 1,
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY(visit_id) REFERENCES inspection_visits(visit_id),
  FOREIGN KEY(series_id) REFERENCES inspection_series(series_id),
  CHECK(scope IN ('single','this_and_future'))
);
"""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dict(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _normalize_technician(row: dict[str, Any]) -> dict[str, Any]:
    if row:
        row["active"] = bool(row["active"])
    return row


def _normalize_series(row: dict[str, Any]) -> dict[str, Any]:
    if row:
        row["active"] = bool(row["active"])
        row["shift_future_on_reschedule"] = bool(row["shift_future_on_reschedule"])
    return row


def _visit_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = _dict(row)
    technician = None
    if payload.get("assigned_technician_id"):
        technician = {
            "technician_id": payload["assigned_technician_id"],
            "name": payload.pop("technician_name") or "",
            "color": payload.pop("technician_color") or "#2563eb",
        }
    else:
        payload.pop("technician_name", None)
        payload.pop("technician_color", None)
    site = {
        "site_id": payload.pop("site_id"),
        "name": payload.pop("site_name"),
        "customer_name": payload.pop("customer_name"),
        "address": payload.pop("address"),
        "latitude": payload.pop("latitude"),
        "longitude": payload.pop("longitude"),
    }
    payload["site"] = site
    payload["site_id"] = site["site_id"]
    payload["assigned_technician"] = technician
    return payload


def _bool_payload(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    output = dict(payload)
    for key in keys:
        if key in output and output[key] is not None:
            output[key] = 1 if output[key] else 0
    return output


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()
