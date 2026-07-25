from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from firelaw_api.api import create_app
from firelaw_api.cli import app
from firelaw_api.ingest import build_database
from firelaw_api.semantic import SemanticUnavailableError, build_semantic_index, semantic_search
from firelaw_api.store import FirelawStore


FIXTURES = Path(__file__).parent / "fixtures"


class FakeEmbeddingProvider:
    def __init__(self, model_name="fake-model"):
        self.model_name = model_name

    def encode(self, texts):
        return [_fake_vector(text) for text in texts]


def _fake_vector(text):
    if "滅火器" in text or "各類場所" in text or "店面" in text:
        return [1.0, 0.0, 0.0]
    if "檢修" in text or "消防檢查" in text:
        return [0.0, 1.0, 0.0]
    if "消防栓" in text:
        return [0.0, 0.0, 1.0]
    return [0.1, 0.1, 0.1]


def _db_path(tmp_path):
    db_path = tmp_path / "firelaw.sqlite"
    build_database(
        db_path,
        [
            ("law", (FIXTURES / "law_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18289"),
            ("command", (FIXTURES / "command_sample.xml").read_bytes(), "https://data.gov.tw/dataset/18290"),
        ],
    )
    return db_path


def test_build_semantic_index_and_search_with_fake_provider(tmp_path):
    store = FirelawStore(_db_path(tmp_path))

    manifest = build_semantic_index(store, model_name="fake-model", provider=FakeEmbeddingProvider())
    results = semantic_search(
        store,
        "店面要放幾個滅火器",
        model_name="fake-model",
        provider=FakeEmbeddingProvider(),
        limit=3,
    )

    assert manifest["mode"] == "semantic_beta"
    assert manifest["model"] == "fake-model"
    assert manifest["article_count"] == 4
    assert manifest["dimension"] == 3
    assert results[0]["law_name"] == "各類場所消防安全設備設置標準"
    assert results[0]["article_no"] == "第 31 條"


def test_semantic_search_requires_a_built_index(tmp_path):
    store = FirelawStore(_db_path(tmp_path))

    with pytest.raises(SemanticUnavailableError):
        semantic_search(store, "店面要放幾個滅火器", model_name="fake-model", provider=FakeEmbeddingProvider())


def test_semantic_search_api_returns_beta_mode_with_fake_provider(tmp_path):
    db_path = _db_path(tmp_path)
    build_semantic_index(FirelawStore(db_path), model_name="fake-model", provider=FakeEmbeddingProvider())
    client = TestClient(
        create_app(db_path, semantic_model_name="fake-model", semantic_provider_factory=FakeEmbeddingProvider)
    )

    response = client.get("/search/semantic", params={"q": "店面要放幾個滅火器"}).json()

    assert response["mode"] == "semantic_beta"
    assert response["results"][0]["article_no"] == "第 31 條"


def test_semantic_update_command_builds_local_index(monkeypatch, tmp_path):
    db_path = _db_path(tmp_path)
    monkeypatch.setattr("firelaw_api.semantic.SentenceTransformerEmbeddingProvider", FakeEmbeddingProvider)

    result = CliRunner().invoke(app, ["semantic-update", "--db", str(db_path), "--model", "fake-model"])

    assert result.exit_code == 0
    assert "semantic beta index" in result.output
    assert FirelawStore(db_path).get_semantic_metadata("fake-model")["article_count"] == 4
