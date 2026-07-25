from fastapi.testclient import TestClient

import app as vercel_entrypoint


def test_vercel_entrypoint_serves_packaged_demo_database():
    client = TestClient(vercel_entrypoint.app)

    health = client.get("/health").json()
    improvement = client.get("/improvement")
    search = client.get("/search", params={"q": "滅火器", "limit": 1}).json()

    assert health["status"] == "ok"
    assert health["law_count"] >= 1
    assert improvement.status_code == 200
    assert "改善缺失依據與報價說明工作台" in improvement.text
    assert search["results"]
