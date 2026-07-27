from pathlib import Path

from typer.testing import CliRunner

from firelaw_api.cli import app


FIXTURES = Path(__file__).parent / "fixtures"


def test_update_command_builds_database_from_downloaded_payloads(monkeypatch, tmp_path):
    def fake_fetch_source_payloads():
        return [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ]

    monkeypatch.setattr("firelaw_api.cli.fetch_source_payloads", fake_fetch_source_payloads)
    db_path = tmp_path / "firelaw.sqlite"

    result = CliRunner().invoke(app, ["update", "--db", str(db_path)])

    assert result.exit_code == 0
    assert db_path.exists()
    assert "2 laws, 4 articles" in result.output
    assert "Change baseline created" in result.output


def test_update_command_reports_change_counts(monkeypatch, tmp_path):
    law_payload = (FIXTURES / "law_sample.xml").read_text(encoding="utf-8")
    command_payload = (FIXTURES / "command_sample.xml").read_text(encoding="utf-8")
    calls = {"count": 0}

    def fake_fetch_source_payloads():
        calls["count"] += 1
        if calls["count"] == 1:
            return [
                ("law", law_payload.encode("utf-8"), "https://data.gov.tw/dataset/18289"),
                ("command", command_payload.encode("utf-8"), "https://data.gov.tw/dataset/18290"),
            ]
        updated_command = command_payload.replace(
            "<條文內容>滅火器應依下列規定設置：一、視各類場所潛在火災性質設置。</條文內容>",
            "<條文內容>滅火器應依下列規定設置：一、視各類場所潛在火災性質設置；二、應保持明顯標示。</條文內容>",
        )
        return [
            ("law", law_payload.encode("utf-8"), "https://data.gov.tw/dataset/18289"),
            ("command", updated_command.encode("utf-8"), "https://data.gov.tw/dataset/18290"),
        ]

    monkeypatch.setattr("firelaw_api.cli.fetch_source_payloads", fake_fetch_source_payloads)
    db_path = tmp_path / "firelaw.sqlite"

    CliRunner().invoke(app, ["update", "--db", str(db_path)])
    result = CliRunner().invoke(app, ["update", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Changes: laws +0 ~0 -0; articles +0 ~1 -0" in result.output


def test_serve_command_accepts_app_db(monkeypatch, tmp_path):
    calls = {}

    def fake_run(app_instance, host, port):
        calls["app"] = app_instance
        calls["host"] = host
        calls["port"] = port

    monkeypatch.setattr("firelaw_api.cli.uvicorn.run", fake_run)
    db_path = tmp_path / "firelaw.sqlite"
    app_db_path = tmp_path / "firebasis.sqlite"

    result = CliRunner().invoke(
        app,
        [
            "serve",
            "--db",
            str(db_path),
            "--app-db",
            str(app_db_path),
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
        ],
    )

    assert result.exit_code == 0
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8010
    assert app_db_path.exists()
