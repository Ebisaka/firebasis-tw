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
    ui = client.get("/ui")
    improvement = client.get("/improvement")
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
    assert "台灣消防法規引用工作台" in home.text
    assert "不構成法律意見" in home.text
    assert "我想查" in home.text
    assert ui.status_code == 200
    assert "台灣消防法規引用工作台" in ui.text
    assert improvement.status_code == 200
    assert "改善缺失依據與報價說明工作台" in improvement.text
    assert "Beta" in improvement.text
    assert "僅提供候選官方依據與保守說明" in improvement.text
    assert improvement_js.status_code == 200
    assert "text/javascript" in improvement_js.headers["content-type"]
    assert improvement_data.status_code == 200
    assert "application/json" in improvement_data.headers["content-type"]
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
    improvement = client.get("/improvement")
    assert improvement.status_code == 200
    assert "改善缺失依據與報價說明工作台" in improvement.text
    assert client.get("/health").json()["status"] == "degraded"
    assert client.get("/meta/changes").status_code == 503
    assert client.get("/search", params={"q": "滅火器"}).status_code == 503
    assert client.get("/search/assist", params={"q": "店面"}).status_code == 503
    assert client.get("/search/semantic", params={"q": "店面"}).status_code == 503
