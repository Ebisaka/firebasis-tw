from pathlib import Path

from fastapi.testclient import TestClient

from firelaw_api.api import create_app
from firelaw_api.ingest import build_database


FIXTURES = Path(__file__).parent / "fixtures"


def _client(tmp_path):
    law_db = tmp_path / "firelaw.sqlite"
    app_db = tmp_path / "firebasis.sqlite"
    build_database(
        law_db,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )
    return TestClient(create_app(law_db, app_db_path=app_db)), app_db


def _create_site(client):
    response = client.post(
        "/schedule/sites",
        json={
            "name": "A 工廠",
            "customer_name": "A 公司",
            "address": "台中市西屯區工業區一路 1 號",
            "latitude": 24.1477,
            "longitude": 120.6736,
        },
    )
    assert response.status_code == 200
    return response.json()


def _create_technician(client):
    response = client.post(
        "/schedule/technicians",
        json={"name": "陳技師", "phone": "0912-000-000", "role": "technician", "color": "#2563eb"},
    )
    assert response.status_code == 200
    return response.json()


def test_schedule_api_creates_series_generates_visits_and_supports_dispatch_flow(tmp_path):
    client, app_db = _client(tmp_path)

    site = _create_site(client)
    tech = _create_technician(client)
    series = client.post(
        "/schedule/series",
        json={
            "site_id": site["site_id"],
            "title": "A 工廠消防安全設備定期檢查",
            "inspection_type": "消防安全設備檢查",
            "recurrence_frequency": "semiannual",
            "recurrence_interval": 1,
            "start_date": "2026-08-01",
            "end_date": "2027-08-01",
            "preferred_start_time": "09:30",
            "duration_minutes": 180,
            "default_technician_id": tech["technician_id"],
        },
    )

    assert series.status_code == 200
    series_payload = series.json()
    assert series_payload["generated_visit_count"] == 3
    assert series_payload["next_visit"]["scheduled_start"] == "2026-08-01T09:30:00+08:00"

    visits = client.get("/schedule/visits", params={"from": "2026-08-01", "to": "2027-08-02"}).json()["visits"]
    assert [visit["scheduled_start"] for visit in visits] == [
        "2026-08-01T09:30:00+08:00",
        "2027-02-01T09:30:00+08:00",
        "2027-08-01T09:30:00+08:00",
    ]
    first_visit = visits[0]
    assert first_visit["site"]["name"] == "A 工廠"
    assert first_visit["assigned_technician"]["name"] == "陳技師"
    assert first_visit["status"] == "scheduled"

    assign = client.post(
        f"/schedule/visits/{first_visit['visit_id']}/assign",
        json={"technician_id": tech["technician_id"], "note": "上午先到 A 工廠"},
    )
    assert assign.status_code == 200
    assert assign.json()["status"] == "dispatched"

    status = client.post(
        f"/schedule/visits/{first_visit['visit_id']}/status",
        json={"status": "in_progress", "note": "現場檢查中"},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "in_progress"

    status_events = client.get(f"/schedule/visits/{first_visit['visit_id']}/status-events").json()["events"]
    assert [event["new_status"] for event in status_events] == ["dispatched", "in_progress"]
    assert status_events[-1]["note"] == "現場檢查中"

    health = client.get("/schedule/health").json()
    assert health["status"] == "ok"
    assert health["app_db"] == str(app_db)
    assert health["site_count"] == 1
    assert health["technician_count"] == 1
    assert health["visit_count"] == 3

    dispatch = client.get("/schedule/dispatch-board", params={"date": "2026-08-01"}).json()
    assert dispatch["date"] == "2026-08-01"
    assert dispatch["technicians"][0]["visit_count"] == 1

    map_payload = client.get("/schedule/map", params={"from": "2026-08-01", "to": "2026-08-02"}).json()
    assert map_payload["points"][0]["latitude"] == 24.1477
    assert map_payload["points"][0]["technician"]["name"] == "陳技師"

    filtered_visits = client.get(
        "/schedule/visits",
        params={"from": "2026-08-01", "to": "2026-08-02", "q": "A 工廠", "site_id": site["site_id"]},
    ).json()["visits"]
    assert len(filtered_visits) == 1
    assert client.get("/schedule/technicians", params={"active": True}).json()["technicians"][0]["name"] == "陳技師"
    assert client.get(f"/schedule/technicians/{tech['technician_id']}").json()["name"] == "陳技師"


def test_schedule_this_and_future_reschedule_shifts_open_future_visits_only(tmp_path):
    client, _ = _client(tmp_path)
    site = _create_site(client)
    tech = _create_technician(client)
    series = client.post(
        "/schedule/series",
        json={
            "site_id": site["site_id"],
            "title": "A 工廠消防安全設備定期檢查",
            "inspection_type": "消防安全設備檢查",
            "recurrence_frequency": "monthly",
            "start_date": "2026-08-01",
            "end_date": "2026-11-01",
            "preferred_start_time": "09:00",
            "duration_minutes": 120,
            "default_technician_id": tech["technician_id"],
        },
    ).json()
    visits = client.get("/schedule/visits", params={"from": "2026-08-01", "to": "2026-11-02"}).json()["visits"]
    client.post(f"/schedule/visits/{visits[-1]['visit_id']}/status", json={"status": "completed"})

    reschedule = client.post(
        f"/schedule/visits/{visits[1]['visit_id']}/reschedule",
        json={
            "scheduled_start": "2026-09-08T10:00:00+08:00",
            "scope": "this_and_future",
            "reason": "業主要求改期",
        },
    )

    assert reschedule.status_code == 200
    payload = reschedule.json()
    assert payload["affected_visit_count"] == 2
    assert payload["delta_days"] == 7
    reschedule_events = client.get(f"/schedule/visits/{visits[1]['visit_id']}/reschedule-events").json()["events"]
    assert reschedule_events[0]["scope"] == "this_and_future"
    assert reschedule_events[0]["affected_visit_count"] == 2
    assert reschedule_events[0]["reason"] == "業主要求改期"
    updated = client.get("/schedule/visits", params={"from": "2026-08-01", "to": "2026-12-01"}).json()["visits"]
    assert [visit["scheduled_start"] for visit in updated] == [
        "2026-08-01T09:00:00+08:00",
        "2026-09-08T10:00:00+08:00",
        "2026-10-08T09:00:00+08:00",
        "2026-11-01T09:00:00+08:00",
    ]
    assert updated[-1]["status"] == "completed"


def test_removed_improvement_bridge_routes_are_not_exposed(tmp_path):
    client, _ = _client(tmp_path)
    site = _create_site(client)
    visit = client.post(
        "/schedule/visits",
        json={
            "site_id": site["site_id"],
            "title": "單次消防檢查",
            "inspection_type": "消防安全設備檢查",
            "scheduled_start": "2026-08-01T09:00:00+08:00",
            "duration_minutes": 120,
        },
    ).json()

    assert client.get(f"/schedule/visits/{visit['visit_id']}/deficiencies").status_code == 404
    assert client.post(f"/schedule/visits/{visit['visit_id']}/deficiencies", json={}).status_code == 404
    assert client.post(f"/schedule/visits/{visit['visit_id']}/evidence-package/preview", json={}).status_code == 404


def test_schedule_read_only_mode_serves_health_and_rejects_writes(tmp_path):
    law_db = tmp_path / "firelaw.sqlite"
    build_database(law_db, [("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289")])
    client = TestClient(create_app(law_db, app_db_path=tmp_path / "readonly.sqlite", schedule_writable=False))

    health = client.get("/schedule/health")
    write = client.post("/schedule/sites", json={"name": "A 工廠"})

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["writable"] is False
    assert write.status_code == 503
