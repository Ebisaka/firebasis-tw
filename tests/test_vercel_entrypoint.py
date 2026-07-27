import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).parents[1]


def load_vercel_entrypoint():
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", PROJECT_ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_vercel_entrypoint_serves_packaged_demo_database():
    vercel_entrypoint = load_vercel_entrypoint()
    client = TestClient(vercel_entrypoint.app)

    health = client.get("/health").json()
    home = client.get("/")
    schedule = client.get("/schedule")
    improvement = client.get("/improvement")
    citation = client.get("/citation")
    home_preview = client.get("/home-preview")
    schedule_health = client.get("/schedule/health").json()
    search = client.get("/search", params={"q": "滅火器", "limit": 1}).json()

    assert health["status"] == "ok"
    assert health["law_count"] >= 1
    assert home.status_code == 200
    assert 'id="root"' in home.text
    assert "/react/assets/" in home.text
    assert schedule.status_code == 200
    assert 'id="root"' in schedule.text
    assert improvement.status_code == 404
    assert citation.status_code == 404
    assert home_preview.status_code == 200
    assert home_preview.text == home.text
    assert schedule_health["status"] in {"degraded", "read_only"}
    assert schedule_health["writable"] is False
    assert search["results"]
