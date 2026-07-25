from pathlib import Path

from firelaw_api.ingest import build_database
from firelaw_api.store import FirelawStore


FIXTURES = Path(__file__).parent / "fixtures"


def test_build_database_creates_stable_records_and_searchable_fts(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"

    build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )

    store = FirelawStore(db_path)
    laws = store.list_laws()
    results = store.search("滅火器")
    manifest = store.get_sources()

    assert [law["name"] for law in laws] == ["消防法", "各類場所消防安全設備設置標準"]
    assert results[0]["law_name"] == "各類場所消防安全設備設置標準"
    assert results[0]["article_no"] == "第 31 條"
    assert results[0]["source_url"].startswith("https://law.moj.gov.tw/")
    assert manifest["corpus"]["law_count"] == 2
    assert manifest["corpus"]["article_count"] == 4
    assert manifest["sources"][0]["sha256"]


def test_first_update_creates_change_baseline_without_added_records(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"

    manifest = build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )

    changes = FirelawStore(db_path).get_changes()

    assert manifest["changes"]["first_update"] is True
    assert changes["run"]["first_update"] is True
    assert changes["status"] == "baseline_created"
    assert changes["counts"] == {
        "law_added": 0,
        "law_removed": 0,
        "law_modified": 0,
        "article_added": 0,
        "article_removed": 0,
        "article_modified": 0,
    }
    assert changes["changes"] == []


def test_second_update_records_law_article_and_metadata_changes(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    law_payload = (FIXTURES / "law_sample.xml").read_text(encoding="utf-8")
    command_payload = (FIXTURES / "command_sample.xml").read_text(encoding="utf-8")

    build_database(
        db_path,
        [
            ("law", law_payload.encode("utf-8"), "https://data.gov.tw/dataset/18289"),
            ("command", command_payload.encode("utf-8"), "https://data.gov.tw/dataset/18290"),
        ],
    )

    updated_law_payload = law_payload.replace("1121221", "1130101", 1)
    updated_command_payload = (
        command_payload.replace(
            "<條文內容>滅火器應依下列規定設置：一、視各類場所潛在火災性質設置。</條文內容>",
            "<條文內容>滅火器應依下列規定設置：一、視各類場所潛在火災性質設置；二、應保持明顯標示。</條文內容>",
        )
        .replace(
            """
      <條>
        <條號>第 32 條</條號>
        <條文內容>室內消防栓設備應依規定配置水源、幫浦及消防栓箱。</條文內容>
      </條>""",
            """
      <條>
        <條號>第 33 條</條號>
        <條文內容>緊急照明設備應依規定設置。</條文內容>
      </條>""",
        )
    )

    manifest = build_database(
        db_path,
        [
            ("law", updated_law_payload.encode("utf-8"), "https://data.gov.tw/dataset/18289"),
            ("command", updated_command_payload.encode("utf-8"), "https://data.gov.tw/dataset/18290"),
        ],
    )
    changes = FirelawStore(db_path).get_changes(limit=10)

    assert manifest["changes"]["first_update"] is False
    assert changes["status"] == "available"
    assert changes["counts"] == {
        "law_added": 0,
        "law_removed": 0,
        "law_modified": 1,
        "article_added": 1,
        "article_removed": 1,
        "article_modified": 1,
    }
    assert {item["change_type"] for item in changes["changes"]} == {
        "law_modified",
        "article_added",
        "article_removed",
        "article_modified",
    }
    modified_article = next(item for item in changes["changes"] if item["change_type"] == "article_modified")
    assert modified_article["law_name"] == "各類場所消防安全設備設置標準"
    assert modified_article["article_no"] == "第 31 條"
    assert modified_article["previous_text_hash"] != modified_article["current_text_hash"]


def test_change_history_is_retained_for_latest_twenty_runs(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    law_payload = (FIXTURES / "law_sample.xml").read_text(encoding="utf-8")
    command_payload = (FIXTURES / "command_sample.xml").read_bytes()

    for index in range(22):
        payload = law_payload.replace("1121221", f"11301{index % 28 + 1:02d}", 1)
        build_database(
            db_path,
            [
                ("law", payload.encode("utf-8"), "https://data.gov.tw/dataset/18289"),
                ("command", command_payload, "https://data.gov.tw/dataset/18290"),
            ],
        )

    changes = FirelawStore(db_path).get_changes()

    assert changes["history_count"] == 20
    assert changes["run"]["run_id"] == 22


def test_unreadable_previous_database_does_not_block_rebuild(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    db_path.write_text("not sqlite", encoding="utf-8")

    manifest = build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )
    changes = FirelawStore(db_path).get_changes()

    assert manifest["changes"]["status"] == "unavailable"
    assert changes["status"] == "unavailable"
    assert changes["changes"] == []
    assert FirelawStore(db_path).health()["status"] == "ok"


def test_missing_database_reports_degraded_health(tmp_path):
    store = FirelawStore(tmp_path / "missing.sqlite")

    assert store.health()["status"] == "degraded"
