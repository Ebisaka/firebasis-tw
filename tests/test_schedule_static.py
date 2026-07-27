from pathlib import Path

from fastapi.testclient import TestClient

from firelaw_api.api import create_app


def test_schedule_static_page_and_asset_contract(tmp_path):
    client = TestClient(create_app(tmp_path / "missing-law.sqlite", app_db_path=tmp_path / "firebasis.sqlite"))

    page = client.get("/schedule")
    asset = client.get("/assets/schedule.js")
    react_index = Path(__file__).parents[1] / "src" / "firelaw_api" / "static" / "react" / "index.html"

    assert page.status_code == 200
    if react_index.exists():
        assert 'id="root"' in page.text
        assert "/react/assets/" in page.text
    else:
        assert "排程派工" in page.text
        assert "scheduleHealth" in page.text
    assert "Backend Core First" not in page.text
    assert "/improvement" not in page.text
    assert "/citation" not in page.text
    assert asset.status_code == 200
    assert "text/javascript" in asset.headers["content-type"]


def test_schedule_page_file_keeps_minimal_backend_smoke_positioning():
    html = (Path(__file__).parents[1] / "src" / "firelaw_api" / "static" / "schedule.html").read_text(encoding="utf-8")
    script = (Path(__file__).parents[1] / "src" / "firelaw_api" / "static" / "schedule.js").read_text(encoding="utf-8")

    assert "排程派工" in html
    assert "排程派工資料層已接上" in html
    assert "定期檢查、派工、狀態與改期紀錄" in html
    assert "完整行事曆介面另行設計" not in html
    assert "/improvement" not in html
    assert "/citation" not in html
    assert "app DB" not in html
    assert "Backend Core First" not in html
    assert "calendar API" not in html
    assert "缺失證據包" not in html
    assert "缺失資料" not in script
    assert "degraded" not in script
    assert "目前無法確認" in script
