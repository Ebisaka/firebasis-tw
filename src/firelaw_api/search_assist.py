from __future__ import annotations

from typing import Any

from .store import FirelawStore

COMMON_SUGGESTIONS = [
    "滅火器",
    "檢修申報",
    "住宅警報器",
    "液化石油氣",
    "防火管理人",
    "室內消防栓",
]

ASSIST_RULES = [
    {
        "id": "occupancy_plain_language",
        "triggers": ["店面", "餐廳", "小吃店", "營業場所", "場所"],
        "terms": ["各類場所", "消防安全設備", "滅火器"],
    },
    {
        "id": "inspection_plain_language",
        "triggers": ["消防檢查", "消防安檢", "檢查申報", "多久消防檢查"],
        "terms": ["檢修", "申報", "消防安全設備"],
    },
    {
        "id": "alarm_plain_language",
        "triggers": ["火警警報器", "住警器", "住宅警報器", "警報器"],
        "terms": ["住宅用火災警報器", "火災警報器"],
    },
    {
        "id": "lpg_plain_language",
        "triggers": ["瓦斯桶", "瓦斯鋼瓶", "瓦斯罐", "桶裝瓦斯"],
        "terms": ["液化石油氣容器", "液化石油氣"],
    },
]


def assist_search(store: FirelawStore, query: str, law_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    normalized = normalize_query(query)
    expanded_terms, applied_rules = expand_query(normalized)
    suggestions = _suggestions(expanded_terms, normalized)
    variants = _query_variants(normalized, expanded_terms)
    results = _merged_results(store, variants, law_id=law_id, limit=limit)
    return {
        "query": query,
        "normalized_query": normalized,
        "expanded_terms": expanded_terms,
        "applied_rules": applied_rules,
        "suggestions": suggestions,
        "results": results,
    }


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def expand_query(query: str) -> tuple[list[str], list[dict[str, Any]]]:
    expanded_terms: list[str] = []
    applied_rules: list[dict[str, Any]] = []

    for suggestion in COMMON_SUGGESTIONS:
        if suggestion in query:
            expanded_terms.append(suggestion)

    for rule in ASSIST_RULES:
        matched_triggers = [trigger for trigger in rule["triggers"] if trigger in query]
        if not matched_triggers:
            continue
        expanded_terms.extend(rule["terms"])
        applied_rules.append(
            {
                "id": rule["id"],
                "triggers": matched_triggers,
                "terms": list(rule["terms"]),
            }
        )

    return _unique(expanded_terms), applied_rules


def _query_variants(query: str, expanded_terms: list[str]) -> list[str]:
    parts = [query, *expanded_terms]
    return [part for part in _unique(parts) if part]


def _merged_results(
    store: FirelawStore,
    query_variants: list[str],
    law_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    requested_limit = max(1, min(limit, 100))
    search_limit = min(100, max(requested_limit * 4, 20))

    for variant_index, variant in enumerate(query_variants):
        rows = []
        if len(variant.replace(" ", "")) >= 3:
            rows.extend(store.search(variant, law_id=law_id, limit=search_limit))
        rows.extend(store.search_loose(variant, law_id=law_id, limit=search_limit))

        for rank, row in enumerate(rows, start=1):
            article_id = row["article_id"]
            score = 1.0 / (variant_index + rank + 1)
            if article_id not in combined:
                combined[article_id] = dict(row)
                combined[article_id]["score"] = 0.0
            combined[article_id]["score"] += score
            if row.get("snippet") and not combined[article_id].get("snippet"):
                combined[article_id]["snippet"] = row["snippet"]

    ranked = sorted(combined.values(), key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item["score"] = round(float(item["score"]), 6)
    return ranked[:requested_limit]


def _suggestions(expanded_terms: list[str], query: str) -> list[str]:
    suggestions = [term for term in expanded_terms if term != query]
    suggestions.extend(COMMON_SUGGESTIONS)
    return _unique(suggestions)[:8]


def _unique(values: list[str]) -> list[str]:
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
