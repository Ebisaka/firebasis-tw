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
    improvement = client.get("/improvement")
    home_preview = client.get("/home-preview")
    search = client.get("/search", params={"q": "滅火器", "limit": 1}).json()

    assert health["status"] == "ok"
    assert health["law_count"] >= 1
    assert home.status_code == 200
    assert "消防公司 / 檢修人員 / 報價前溝通" in home.text
    assert "開啟改善依據反查" in home.text
    assert improvement.status_code == 200
    assert "消防改善依據反查" in improvement.text
    assert "工作台" not in improvement.text
    assert home_preview.status_code == 200
    assert "消防公司 / 檢修人員 / 報價前溝通" in home_preview.text
    assert "依據素材預覽" in home_preview.text
    assert search["results"]
