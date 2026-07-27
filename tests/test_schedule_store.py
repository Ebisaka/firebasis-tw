import sqlite3

import pytest

from firelaw_api.schedule_store import ScheduleStore


def test_schedule_store_migrates_separate_app_database_without_touching_law_database(tmp_path):
    law_db = tmp_path / "firelaw.sqlite"
    law_db.write_text("official law artifact", encoding="utf-8")
    app_db = tmp_path / "firebasis.sqlite"

    store = ScheduleStore(app_db)
    store.migrate()

    assert app_db.exists()
    assert law_db.read_text(encoding="utf-8") == "official law artifact"
    health = store.health()
    assert health["status"] == "ok"
    assert health["site_count"] == 0
    assert health["technician_count"] == 0
    assert health["visit_count"] == 0


def test_schedule_store_enforces_foreign_keys_on_every_connection(tmp_path):
    store = ScheduleStore(tmp_path / "firebasis.sqlite")
    store.migrate()

    with pytest.raises(sqlite3.IntegrityError):
        store.create_series(
            {
                "site_id": "missing-site",
                "title": "不存在場所定期檢查",
                "inspection_type": "消防安全設備檢查",
                "recurrence_frequency": "monthly",
                "recurrence_interval": 1,
                "start_date": "2026-08-01",
                "preferred_start_time": "09:00",
                "duration_minutes": 120,
            }
        )


def test_schedule_store_read_only_mode_reports_degraded_and_rejects_writes(tmp_path):
    store = ScheduleStore(tmp_path / "missing-firebasis.sqlite", writable=False)

    health = store.health()

    assert health["status"] == "degraded"
    assert health["writable"] is False
    assert "read-only" in health["reason"]
    with pytest.raises(PermissionError):
        store.ensure_writable()
