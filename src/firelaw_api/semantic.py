from __future__ import annotations

import hashlib
import math
from typing import Any

from .store import FirelawStore

DEFAULT_SEMANTIC_MODEL = "intfloat/multilingual-e5-small"
SEMANTIC_MODE = "semantic_beta"


class SemanticUnavailableError(RuntimeError):
    pass


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SemanticUnavailableError(
                "semantic beta requires installing firelaw-api[semantic]"
            ) from exc
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
        except TypeError:
            embeddings = self.model.encode(texts)
        return [_as_float_list(vector) for vector in embeddings]


def build_semantic_index(
    store: FirelawStore,
    model_name: str = DEFAULT_SEMANTIC_MODEL,
    provider: Any | None = None,
) -> dict[str, Any]:
    articles = store.list_articles_for_embedding()
    if provider is None:
        provider = SentenceTransformerEmbeddingProvider(model_name)
    texts = [_format_passage(model_name, _embedding_text(article)) for article in articles]
    vectors = [_as_float_list(vector) for vector in provider.encode(texts)]
    if len(vectors) != len(articles):
        raise SemanticUnavailableError("embedding provider returned the wrong number of vectors")
    dimension = _vector_dimension(vectors)
    article_vectors = [
        {
            "article_id": article["article_id"],
            "text_hash": hashlib.sha256(_embedding_text(article).encode("utf-8")).hexdigest(),
            "vector": vector,
        }
        for article, vector in zip(articles, vectors, strict=True)
    ]
    return store.replace_semantic_embeddings(model_name, dimension, article_vectors)


def semantic_search(
    store: FirelawStore,
    query: str,
    law_id: str | None = None,
    limit: int = 20,
    model_name: str = DEFAULT_SEMANTIC_MODEL,
    provider: Any | None = None,
) -> list[dict[str, Any]]:
    metadata = store.get_semantic_metadata(model_name)
    if not metadata:
        raise SemanticUnavailableError(f"semantic beta index not found for model: {model_name}")
    rows = store.list_semantic_embeddings(model_name, law_id=law_id)
    if not rows:
        return []
    if provider is None:
        provider = SentenceTransformerEmbeddingProvider(model_name)

    query_vector = _as_float_list(provider.encode([_format_query(model_name, query)])[0])
    dense_results = _dense_results(query_vector, rows)
    fts_results = store.search(query, law_id=law_id, limit=min(100, max(limit * 4, 20)))
    return _rank_fusion(dense_results, fts_results, limit=max(1, min(limit, 100)))


def _dense_results(query_vector: list[float], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = _cosine_scores(query_vector, [row["vector"] for row in rows])
    results = []
    for row, score in zip(rows, scores, strict=True):
        item = _citation_item(row)
        item["snippet"] = row["text"][:48] + ("..." if len(row["text"]) > 48 else "")
        item["score"] = float(score)
        results.append(item)
    return sorted(results, key=lambda item: item["score"], reverse=True)


def _rank_fusion(
    dense_results: list[dict[str, Any]],
    fts_results: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for result_set in (dense_results, fts_results):
        for rank, item in enumerate(result_set, start=1):
            article_id = item["article_id"]
            if article_id not in combined:
                combined[article_id] = dict(item)
                combined[article_id]["score"] = 0.0
            combined[article_id]["score"] += 1.0 / (60 + rank)
            if item.get("snippet") and not combined[article_id].get("snippet"):
                combined[article_id]["snippet"] = item["snippet"]
    ranked = sorted(combined.values(), key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item["score"] = round(float(item["score"]), 6)
    return ranked[:limit]


def _cosine_scores(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
    try:
        import numpy as np
    except ImportError:
        return [_cosine(query_vector, vector) for vector in vectors]

    query_array = np.asarray(query_vector, dtype=np.float32)
    matrix = np.asarray(vectors, dtype=np.float32)
    query_norm = np.linalg.norm(query_array)
    vector_norms = np.linalg.norm(matrix, axis=1)
    denominator = vector_norms * query_norm
    denominator = np.where(denominator == 0, 1.0, denominator)
    return ((matrix @ query_array) / denominator).astype(float).tolist()


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _citation_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": row["article_id"],
        "article_no": row["article_no"],
        "text": row["text"],
        "law_id": row["law_id"],
        "law_name": row["law_name"],
        "source_url": row["source_url"],
        "latest_amended_at": row["latest_amended_at"],
        "effective_at": row["effective_at"],
    }


def _embedding_text(article: dict[str, Any]) -> str:
    return f"{article['law_name']} {article['article_no']} {article['text']}"


def _format_passage(model_name: str, text: str) -> str:
    if "e5" in model_name.lower():
        return f"passage: {text}"
    return text


def _format_query(model_name: str, query: str) -> str:
    if "e5" in model_name.lower():
        return f"query: {query}"
    return query


def _vector_dimension(vectors: list[list[float]]) -> int:
    if not vectors or not vectors[0]:
        raise SemanticUnavailableError("embedding provider returned empty vectors")
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise SemanticUnavailableError("embedding provider returned inconsistent vector dimensions")
    return dimension


def _as_float_list(vector: Any) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]
