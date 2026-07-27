from pathlib import Path

from fastapi.testclient import TestClient

from firelaw_api.api import create_app
from firelaw_api.ingest import build_database


FIXTURES = Path(__file__).parent / "fixtures"


def _client(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )
    return TestClient(create_app(db_path))


def test_api_exposes_health_sources_laws_articles_and_search(tmp_path):
    client = _client(tmp_path)

    home = client.get("/")
    schedule = client.get("/schedule")
    ui = client.get("/ui")
    citation = client.get("/citation")
    improvement = client.get("/improvement")
    home_preview = client.get("/home-preview")
    react_asset = client.get("/react/assets/" + next((Path(__file__).parents[1] / "src" / "firelaw_api" / "static" / "react" / "assets").glob("*.js")).name)
    home_preview_js = client.get("/assets/home-preview.js")
    improvement_js = client.get("/assets/improvement.js")
    improvement_data = client.get("/assets/improvement-data.json")
    favicon = client.get("/favicon.ico")
    health = client.get("/health").json()
    sources = client.get("/meta/sources").json()
    laws = client.get("/laws").json()
    law = client.get(f"/laws/{laws[0]['law_id']}").json()
    article = client.get(f"/articles/{law['articles'][0]['article_id']}").json()
    search = client.get("/search", params={"q": "滅火器"}).json()
    assist = client.get("/search/assist", params={"q": "店面要放幾個滅火器"}).json()
    changes = client.get("/meta/changes").json()

    assert home.status_code == 200
    assert 'id="root"' in home.text
    assert "/react/assets/" in home.text
    assert schedule.status_code == 200
    assert 'id="root"' in schedule.text
    assert ui.status_code == 404
    assert citation.status_code == 404
    assert improvement.status_code == 404
    assert client.get("/improvement/items").status_code == 404
    assert client.post("/improvement/evidence-package/preview", json={}).status_code == 404
    assert home_preview.status_code == 200
    assert home_preview.text == home.text
    assert react_asset.status_code == 200
    assert "text/javascript" in react_asset.headers["content-type"]
    assert home_preview_js.status_code == 200
    assert "text/javascript" in home_preview_js.headers["content-type"]
    assert improvement_js.status_code == 404
    assert improvement_data.status_code == 404
    assert favicon.status_code == 200
    assert health["status"] == "ok"
    assert sources["license"]["name"] == "政府資料開放授權條款-第1版"
    assert changes["status"] == "baseline_created"
    assert changes["run"]["first_update"] is True
    assert changes["counts"]["article_modified"] == 0
    assert changes["sources"][0]["dataset_url"] == "https://data.gov.tw/dataset/18289"
    assert len(laws) == 2
    assert law["articles"][0]["article_no"] == "第 1 條"
    assert article["law_name"] == "消防法"
    assert search["results"][0]["article_no"] == "第 31 條"
    assert search["results"][0]["snippet"]
    assert assist["normalized_query"] == "店面要放幾個滅火器"
    assert "各類場所" in assist["expanded_terms"]
    assert assist["results"][0]["article_no"] == "第 31 條"


def test_api_missing_database_is_degraded_and_search_returns_service_error(tmp_path):
    client = TestClient(create_app(tmp_path / "missing.sqlite"))

    assert client.get("/").status_code == 200
    assert 'id="root"' in client.get("/").text
    improvement = client.get("/improvement")
    citation = client.get("/citation")
    assert improvement.status_code == 404
    assert citation.status_code == 404
    home_preview = client.get("/home-preview")
    assert home_preview.status_code == 200
    assert home_preview.text == client.get("/").text
    assert client.get("/health").json()["status"] == "degraded"
    assert client.get("/meta/changes").status_code == 503
    assert client.get("/search", params={"q": "滅火器"}).status_code == 503
    assert client.get("/search/assist", params={"q": "店面"}).status_code == 503
    assert client.get("/search/semantic", params={"q": "店面"}).status_code == 503
