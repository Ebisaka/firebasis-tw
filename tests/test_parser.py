from pathlib import Path

from firelaw_api.parser import parse_documents


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_documents_filters_to_current_central_fire_laws():
    documents = parse_documents(
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes()),
            ("command", (FIXTURES / "command_sample.xml").read_bytes()),
        ]
    )

    names = [document.name for document in documents]

    assert names == ["消防法", "各類場所消防安全設備設置標準"]
    assert documents[0].latest_amended_at == "2023-12-21"
    assert documents[1].effective_at == "2024-07-01"
    assert documents[1].articles[0].article_no == "第 31 條"
    assert "滅火器" in documents[1].articles[0].text


def test_parse_documents_accepts_zip_payloads():
    import io
    import zipfile

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("command.xml", (FIXTURES / "command_sample.xml").read_text(encoding="utf-8"))

    documents = parse_documents([("command", payload.getvalue())])

    assert [document.name for document in documents] == ["各類場所消防安全設備設置標準"]


def test_parse_documents_handles_official_law_content_article_nodes():
    documents = parse_documents([("command", (FIXTURES / "official_shape_sample.xml").read_bytes())])

    assert documents[0].articles[0].article_no == "第 31 條"
    assert documents[0].articles[1].article_no == "第 32 條"
    assert "滅火器" in documents[0].articles[0].text
