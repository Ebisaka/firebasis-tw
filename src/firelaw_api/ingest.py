from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import LawDocument
from .parser import parse_documents

LICENSE = {
    "name": "政府資料開放授權條款-第1版",
    "url": "https://data.gov.tw/license",
    "attribution": "資料來源：全國法規資料庫、政府資料開放平臺；提供機關：法務部資訊處。",
}

LEGAL_NOTICE = "本 API 僅提供官方法規引用查詢，不提供法律諮詢、法律意見或 AI 摘要結論。"

CHANGE_TYPES = (
    "law_added",
    "law_removed",
    "law_modified",
    "article_added",
    "article_removed",
    "article_modified",
)


@dataclass
class PreviousState:
    status: str
    reason: str | None = None
    manifest: dict[str, Any] | None = None
    laws: dict[str, dict[str, Any]] = field(default_factory=dict)
    articles: dict[str, dict[str, Any]] = field(default_factory=dict)
    history_runs: list[dict[str, Any]] = field(default_factory=list)
    history_changes: list[dict[str, Any]] = field(default_factory=list)


def build_database(db_path: Path, raw_sources: Iterable[tuple[str, bytes, str]]) -> dict:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    source_payloads = list(raw_sources)
    parsed_inputs = [(kind, payload) for kind, payload, _url in source_payloads]
    documents = parse_documents(parsed_inputs)
    manifest = _manifest(source_payloads, documents)
    previous_state = _read_previous_state(db_path)
    update_run, changes = _build_update_changes(previous_state, documents, manifest)
    manifest["changes"] = _public_run(update_run, changes)

    fd, temp_name = tempfile.mkstemp(prefix=f"{db_path.name}.", suffix=".tmp", dir=str(db_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        _write_database(temp_path, documents, manifest, previous_state, update_run, changes)
        os.replace(temp_path, db_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return manifest


def _write_database(
    db_path: Path,
    documents: list[LawDocument],
    manifest: dict,
    previous_state: PreviousState,
    update_run: dict[str, Any],
    changes: list[dict[str, Any]],
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA foreign_keys=ON")
        _create_schema(conn)
        for sort_order, document in enumerate(documents):
            law_id = stable_law_id(document)
            conn.execute(
                """
                INSERT INTO laws (
                    law_id, source_kind, name, source_url, category, level,
                    latest_amended_at, effective_at, abolished, raw_hash, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    law_id,
                    document.source_kind,
                    document.name,
                    document.source_url,
                    document.category,
                    document.level,
                    document.latest_amended_at,
                    document.effective_at,
                    int(document.abolished),
                    document.raw_hash,
                    sort_order,
                ),
            )
            for article_order, article in enumerate(document.articles):
                article_id = stable_article_id(law_id, article.article_no)
                conn.execute(
                    """
                    INSERT INTO articles (
                        article_id, law_id, article_no, path, text, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (article_id, law_id, article.article_no, article.path, article.text, article_order),
                )
                conn.execute(
                    "INSERT INTO article_fts (article_id, law_name, article_no, text) VALUES (?, ?, ?, ?)",
                    (article_id, document.name, article.article_no, article.text),
                )
        conn.execute(
            "INSERT INTO update_manifest (id, payload) VALUES (1, ?)",
            (json.dumps(manifest, ensure_ascii=False),),
        )
        _write_update_history(conn, previous_state, update_run, changes)
        conn.commit()
    finally:
        conn.close()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE laws (
            law_id TEXT PRIMARY KEY,
            source_kind TEXT NOT NULL,
            name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            category TEXT NOT NULL,
            level TEXT NOT NULL,
            latest_amended_at TEXT,
            effective_at TEXT,
            abolished INTEGER NOT NULL DEFAULT 0,
            raw_hash TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );

        CREATE TABLE articles (
            article_id TEXT PRIMARY KEY,
            law_id TEXT NOT NULL REFERENCES laws(law_id) ON DELETE CASCADE,
            article_no TEXT NOT NULL,
            path TEXT NOT NULL,
            text TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );

        CREATE VIRTUAL TABLE article_fts USING fts5(
            article_id UNINDEXED,
            law_name,
            article_no,
            text,
            tokenize='trigram'
        );

        CREATE TABLE update_manifest (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            payload TEXT NOT NULL
        );

        CREATE TABLE update_runs (
            run_id INTEGER PRIMARY KEY,
            updated_at TEXT NOT NULL,
            previous_updated_at TEXT,
            first_update INTEGER NOT NULL,
            diff_status TEXT NOT NULL,
            unavailable_reason TEXT,
            law_added INTEGER NOT NULL DEFAULT 0,
            law_removed INTEGER NOT NULL DEFAULT 0,
            law_modified INTEGER NOT NULL DEFAULT 0,
            article_added INTEGER NOT NULL DEFAULT 0,
            article_removed INTEGER NOT NULL DEFAULT 0,
            article_modified INTEGER NOT NULL DEFAULT 0,
            manifest_payload TEXT NOT NULL
        );

        CREATE TABLE update_changes (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES update_runs(run_id) ON DELETE CASCADE,
            change_type TEXT NOT NULL,
            law_id TEXT,
            law_name TEXT,
            article_id TEXT,
            article_no TEXT,
            previous_text_hash TEXT,
            current_text_hash TEXT,
            details TEXT NOT NULL DEFAULT '{}'
        );
        """
    )


def _manifest(raw_sources: list[tuple[str, bytes, str]], documents: list[LawDocument]) -> dict:
    article_count = sum(len(document.articles) for document in documents)
    return {
        "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "license": LICENSE,
        "notice": LEGAL_NOTICE,
        "sources": [
            {
                "kind": kind,
                "dataset_url": url,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
            for kind, payload, url in raw_sources
        ],
        "corpus": {
            "law_count": len(documents),
            "article_count": article_count,
        },
    }


def stable_law_id(document: LawDocument) -> str:
    return "law-" + hashlib.sha1(f"{document.source_kind}:{document.name}".encode("utf-8")).hexdigest()[:16]


def stable_article_id(law_id: str, article_no: str) -> str:
    return "art-" + hashlib.sha1(f"{law_id}:{article_no}".encode("utf-8")).hexdigest()[:16]


def _read_previous_state(db_path: Path) -> PreviousState:
    if not db_path.exists():
        return PreviousState(status="missing")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            manifest_row = conn.execute("SELECT payload FROM update_manifest WHERE id = 1").fetchone()
            manifest = json.loads(manifest_row["payload"]) if manifest_row else None
            laws = {
                row["law_id"]: dict(row)
                for row in conn.execute(
                    """
                    SELECT law_id, source_kind, name, source_url, category, level,
                           latest_amended_at, effective_at, abolished
                    FROM laws
                    """
                )
            }
            articles = {}
            for row in conn.execute(
                """
                SELECT a.article_id, a.law_id, l.name AS law_name, a.article_no, a.path, a.text
                FROM articles a
                JOIN laws l ON l.law_id = a.law_id
                """
            ):
                item = dict(row)
                item["text_hash"] = _sha256_text(item.pop("text"))
                articles[item["article_id"]] = item

            history_runs, history_changes = _read_update_history(conn)
            return PreviousState(
                status="available",
                manifest=manifest,
                laws=laws,
                articles=articles,
                history_runs=history_runs,
                history_changes=history_changes,
            )
        finally:
            conn.close()
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        return PreviousState(status="unavailable", reason=str(exc))


def _read_update_history(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not _table_exists(conn, "update_runs"):
        return [], []

    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT run_id, updated_at, previous_updated_at, first_update, diff_status,
                   unavailable_reason, law_added, law_removed, law_modified,
                   article_added, article_removed, article_modified, manifest_payload
            FROM update_runs
            ORDER BY run_id DESC
            LIMIT 19
            """
        )
    ]
    rows.reverse()
    run_ids = [row["run_id"] for row in rows]
    if not run_ids or not _table_exists(conn, "update_changes"):
        return rows, []

    placeholders = ",".join("?" for _ in run_ids)
    changes = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT run_id, change_type, law_id, law_name, article_id, article_no,
                   previous_text_hash, current_text_hash, details
            FROM update_changes
            WHERE run_id IN ({placeholders})
            ORDER BY run_id, change_id
            """,
            run_ids,
        )
    ]
    return rows, changes


def _build_update_changes(
    previous_state: PreviousState,
    documents: list[LawDocument],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    new_laws, new_articles = _document_snapshots(documents)
    run_id = max((row["run_id"] for row in previous_state.history_runs), default=0) + 1
    counts = _empty_counts()
    changes: list[dict[str, Any]] = []

    if previous_state.status == "missing":
        diff_status = "baseline_created"
        first_update = True
        previous_updated_at = None
        unavailable_reason = None
    elif previous_state.status == "unavailable":
        diff_status = "unavailable"
        first_update = False
        previous_updated_at = None
        unavailable_reason = previous_state.reason
    else:
        diff_status = "available"
        first_update = False
        previous_updated_at = (previous_state.manifest or {}).get("updated_at")
        changes = _diff_snapshots(previous_state.laws, previous_state.articles, new_laws, new_articles)
        counts = _counts_for_changes(changes)
        unavailable_reason = None

    update_run = {
        "run_id": run_id,
        "updated_at": manifest["updated_at"],
        "previous_updated_at": previous_updated_at,
        "first_update": first_update,
        "diff_status": diff_status,
        "unavailable_reason": unavailable_reason,
        "counts": counts,
        "manifest_payload": json.dumps(manifest, ensure_ascii=False),
    }
    return update_run, changes


def _document_snapshots(
    documents: list[LawDocument],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    laws: dict[str, dict[str, Any]] = {}
    articles: dict[str, dict[str, Any]] = {}

    for document in documents:
        law_id = stable_law_id(document)
        laws[law_id] = {
            "law_id": law_id,
            "source_kind": document.source_kind,
            "name": document.name,
            "source_url": document.source_url,
            "category": document.category,
            "level": document.level,
            "latest_amended_at": document.latest_amended_at,
            "effective_at": document.effective_at,
            "abolished": int(document.abolished),
        }
        for article in document.articles:
            article_id = stable_article_id(law_id, article.article_no)
            articles[article_id] = {
                "article_id": article_id,
                "law_id": law_id,
                "law_name": document.name,
                "article_no": article.article_no,
                "path": article.path,
                "text_hash": _sha256_text(article.text),
            }
    return laws, articles


def _diff_snapshots(
    old_laws: dict[str, dict[str, Any]],
    old_articles: dict[str, dict[str, Any]],
    new_laws: dict[str, dict[str, Any]],
    new_articles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    for law_id in sorted(new_laws.keys() - old_laws.keys()):
        changes.append(_change("law_added", new_laws[law_id]))
    for law_id in sorted(old_laws.keys() - new_laws.keys()):
        changes.append(_change("law_removed", old_laws[law_id]))
    for law_id in sorted(old_laws.keys() & new_laws.keys()):
        if _law_metadata_hash(old_laws[law_id]) != _law_metadata_hash(new_laws[law_id]):
            changes.append(
                _change(
                    "law_modified",
                    new_laws[law_id],
                    details={"previous": _law_metadata(old_laws[law_id]), "current": _law_metadata(new_laws[law_id])},
                )
            )

    for article_id in sorted(new_articles.keys() - old_articles.keys()):
        changes.append(_change("article_added", new_laws[new_articles[article_id]["law_id"]], new_articles[article_id]))
    for article_id in sorted(old_articles.keys() - new_articles.keys()):
        old_law = old_laws.get(old_articles[article_id]["law_id"], {"law_id": old_articles[article_id]["law_id"], "name": old_articles[article_id]["law_name"]})
        changes.append(_change("article_removed", old_law, old_articles[article_id]))
    for article_id in sorted(old_articles.keys() & new_articles.keys()):
        if old_articles[article_id]["text_hash"] != new_articles[article_id]["text_hash"]:
            changes.append(
                _change(
                    "article_modified",
                    new_laws[new_articles[article_id]["law_id"]],
                    new_articles[article_id],
                    previous_text_hash=old_articles[article_id]["text_hash"],
                    current_text_hash=new_articles[article_id]["text_hash"],
                )
            )

    return changes


def _change(
    change_type: str,
    law: dict[str, Any],
    article: dict[str, Any] | None = None,
    *,
    previous_text_hash: str | None = None,
    current_text_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "change_type": change_type,
        "law_id": law.get("law_id"),
        "law_name": law.get("name"),
        "article_id": article.get("article_id") if article else None,
        "article_no": article.get("article_no") if article else None,
        "previous_text_hash": previous_text_hash or (article.get("text_hash") if article and change_type == "article_removed" else None),
        "current_text_hash": current_text_hash or (article.get("text_hash") if article and change_type == "article_added" else None),
        "details": details or {},
    }


def _write_update_history(
    conn: sqlite3.Connection,
    previous_state: PreviousState,
    update_run: dict[str, Any],
    changes: list[dict[str, Any]],
) -> None:
    if previous_state.history_runs:
        conn.executemany(
            """
            INSERT INTO update_runs (
                run_id, updated_at, previous_updated_at, first_update, diff_status,
                unavailable_reason, law_added, law_removed, law_modified,
                article_added, article_removed, article_modified, manifest_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["run_id"],
                    row["updated_at"],
                    row["previous_updated_at"],
                    row["first_update"],
                    row["diff_status"],
                    row["unavailable_reason"],
                    row["law_added"],
                    row["law_removed"],
                    row["law_modified"],
                    row["article_added"],
                    row["article_removed"],
                    row["article_modified"],
                    row["manifest_payload"],
                )
                for row in previous_state.history_runs
            ],
        )
    if previous_state.history_changes:
        conn.executemany(
            """
            INSERT INTO update_changes (
                run_id, change_type, law_id, law_name, article_id, article_no,
                previous_text_hash, current_text_hash, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["run_id"],
                    row["change_type"],
                    row["law_id"],
                    row["law_name"],
                    row["article_id"],
                    row["article_no"],
                    row["previous_text_hash"],
                    row["current_text_hash"],
                    row["details"],
                )
                for row in previous_state.history_changes
            ],
        )

    counts = update_run["counts"]
    conn.execute(
        """
        INSERT INTO update_runs (
            run_id, updated_at, previous_updated_at, first_update, diff_status,
            unavailable_reason, law_added, law_removed, law_modified,
            article_added, article_removed, article_modified, manifest_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            update_run["run_id"],
            update_run["updated_at"],
            update_run["previous_updated_at"],
            int(update_run["first_update"]),
            update_run["diff_status"],
            update_run["unavailable_reason"],
            counts["law_added"],
            counts["law_removed"],
            counts["law_modified"],
            counts["article_added"],
            counts["article_removed"],
            counts["article_modified"],
            update_run["manifest_payload"],
        ),
    )
    conn.executemany(
        """
        INSERT INTO update_changes (
            run_id, change_type, law_id, law_name, article_id, article_no,
            previous_text_hash, current_text_hash, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                update_run["run_id"],
                item["change_type"],
                item["law_id"],
                item["law_name"],
                item["article_id"],
                item["article_no"],
                item["previous_text_hash"],
                item["current_text_hash"],
                json.dumps(item["details"], ensure_ascii=False),
            )
            for item in changes
        ],
    )


def _public_run(update_run: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_id": update_run["run_id"],
        "updated_at": update_run["updated_at"],
        "previous_updated_at": update_run["previous_updated_at"],
        "first_update": update_run["first_update"],
        "status": update_run["diff_status"],
        "unavailable_reason": update_run["unavailable_reason"],
        "counts": update_run["counts"],
        "change_count": len(changes),
    }


def _counts_for_changes(changes: list[dict[str, Any]]) -> dict[str, int]:
    counts = _empty_counts()
    for item in changes:
        counts[item["change_type"]] += 1
    return counts


def _empty_counts() -> dict[str, int]:
    return {change_type: 0 for change_type in CHANGE_TYPES}


def _law_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": value.get("source_kind"),
        "name": value.get("name"),
        "source_url": value.get("source_url"),
        "category": value.get("category"),
        "level": value.get("level"),
        "latest_amended_at": value.get("latest_amended_at"),
        "effective_at": value.get("effective_at"),
        "abolished": int(value.get("abolished") or 0),
    }


def _law_metadata_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_law_metadata(value), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
