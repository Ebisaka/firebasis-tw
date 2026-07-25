from pathlib import Path

from firelaw_api.ingest import build_database
from firelaw_api.search_assist import assist_search
from firelaw_api.store import FirelawStore


FIXTURES = Path(__file__).parent / "fixtures"


def _store(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )
    return FirelawStore(db_path)


def test_assist_expands_plain_language_query_and_merges_results(tmp_path):
    response = assist_search(_store(tmp_path), "店面要放幾個滅火器", limit=5)

    assert response["normalized_query"] == "店面要放幾個滅火器"
    assert "各類場所" in response["expanded_terms"]
    assert response["applied_rules"][0]["id"] == "occupancy_plain_language"
    assert response["suggestions"]
    assert response["results"][0]["law_name"] == "各類場所消防安全設備設置標準"
    assert response["results"][0]["article_no"] == "第 31 條"


def test_assist_uses_loose_search_for_short_expanded_terms(tmp_path):
    response = assist_search(_store(tmp_path), "消防檢查", limit=5)

    assert "檢修" in response["expanded_terms"]
    assert any(result["article_no"] == "第 6 條" for result in response["results"])


def test_assist_empty_results_still_returns_next_query_suggestions(tmp_path):
    response = assist_search(_store(tmp_path), "完全不存在的白話", limit=5)

    assert response["results"] == []
    assert "滅火器" in response["suggestions"]
