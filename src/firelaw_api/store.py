from __future__ import annotations

from array import array
from datetime import UTC, datetime
import json
import sqlite3
from pathlib import Path
from typing import Any


class FirelawStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def health(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"status": "degraded", "database": str(self.db_path), "reason": "database not found"}
        try:
            with self._connect() as conn:
                law_count = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
                article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        except sqlite3.Error as exc:
            return {"status": "degraded", "database": str(self.db_path), "reason": str(exc)}
        return {"status": "ok", "database": str(self.db_path), "law_count": law_count, "article_count": article_count}

    def get_sources(self) -> dict[str, Any]:
        self._require_database()
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM update_manifest WHERE id = 1").fetchone()
        if not row:
            raise LookupError("source manifest not found")
        return json.loads(row["payload"])

    def get_changes(self, limit: int = 100) -> dict[str, Any]:
        self._require_database()
        limit = max(1, min(limit, 500))
        with self._connect() as conn:
            manifest = _manifest_from_conn(conn)
            if not _table_exists(conn, "update_runs"):
                return _unavailable_changes(manifest, "change history not found")

            run = conn.execute(
                """
                SELECT run_id, updated_at, previous_updated_at, first_update, diff_status,
                       unavailable_reason, law_added, law_removed, law_modified,
                       article_added, article_removed, article_modified
                FROM update_runs
                ORDER BY run_id DESC
                LIMIT 1
                """
            ).fetchone()
            if not run:
                return _unavailable_changes(manifest, "change history not found")

            history_count = conn.execute("SELECT COUNT(*) FROM update_runs").fetchone()[0]
            rows = conn.execute(
                """
                SELECT change_type, law_id, law_name, article_id, article_no,
                       previous_text_hash, current_text_hash, details
                FROM update_changes
                WHERE run_id = ?
                ORDER BY change_id
                LIMIT ?
                """,
                (run["run_id"], limit),
            ).fetchall()

        run_dict = _dict(run)
        run_dict["first_update"] = bool(run_dict["first_update"])
        counts = _change_counts_from_run(run_dict)
        return {
            "status": run_dict["diff_status"],
            "updated_at": run_dict["updated_at"],
            "previous_updated_at": run_dict["previous_updated_at"],
            "sources": manifest.get("sources", []),
            "license": manifest.get("license"),
            "counts": counts,
            "history_count": history_count,
            "run": {
                "run_id": run_dict["run_id"],
                "updated_at": run_dict["updated_at"],
                "previous_updated_at": run_dict["previous_updated_at"],
                "first_update": run_dict["first_update"],
                "status": run_dict["diff_status"],
                "unavailable_reason": run_dict["unavailable_reason"],
                "counts": counts,
            },
            "changes": [_change_from_row(row) for row in rows],
        }

    def list_laws(self) -> list[dict[str, Any]]:
        self._require_database()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    l.law_id, l.source_kind, l.name, l.source_url, l.category, l.level,
                    l.latest_amended_at, l.effective_at, COUNT(a.article_id) AS article_count
                FROM laws l
                LEFT JOIN articles a ON a.law_id = l.law_id
                GROUP BY l.law_id
                ORDER BY l.sort_order
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def get_law(self, law_id: str) -> dict[str, Any] | None:
        self._require_database()
        with self._connect() as conn:
            law = conn.execute(
                """
                SELECT law_id, source_kind, name, source_url, category, level,
                       latest_amended_at, effective_at
                FROM laws
                WHERE law_id = ?
                """,
                (law_id,),
            ).fetchone()
            if not law:
                return None
            articles = conn.execute(
                """
                SELECT article_id, article_no, path
                FROM articles
                WHERE law_id = ?
                ORDER BY sort_order
                """,
                (law_id,),
            ).fetchall()
        result = _dict(law)
        result["articles"] = [_dict(row) for row in articles]
        return result

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        self._require_database()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    a.article_id, a.article_no, a.path, a.text,
                    l.law_id, l.name AS law_name, l.source_url, l.category, l.level,
                    l.latest_amended_at, l.effective_at
                FROM articles a
                JOIN laws l ON l.law_id = a.law_id
                WHERE a.article_id = ?
                """,
                (article_id,),
            ).fetchone()
        return _dict(row) if row else None

    def search(self, query: str, law_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        self._require_database()
        limit = max(1, min(limit, 100))
        fts_query = _fts_phrase(query)
        sql = """
            SELECT
                a.article_id, a.article_no, a.text,
                l.law_id, l.name AS law_name, l.source_url,
                l.latest_amended_at, l.effective_at,
                snippet(article_fts, 3, '', '', '...', 18) AS snippet,
                bm25(article_fts) AS rank
            FROM article_fts
            JOIN articles a ON a.article_id = article_fts.article_id
            JOIN laws l ON l.law_id = a.law_id
            WHERE article_fts MATCH ?
        """
        params: list[Any] = [fts_query]
        if law_id:
            sql += " AND l.law_id = ?"
            params.append(law_id)
        sql += " ORDER BY rank, l.sort_order, a.sort_order LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            item = _dict(row)
            item["score"] = float(-item.pop("rank"))
            results.append(item)
        return results

    def search_loose(self, query: str, law_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        self._require_database()
        cleaned = " ".join(query.strip().split())
        if not cleaned:
            return []
        limit = max(1, min(limit, 100))
        pattern = f"%{_escape_like(cleaned)}%"
        sql = """
            SELECT
                a.article_id, a.article_no, a.text,
                l.law_id, l.name AS law_name, l.source_url,
                l.latest_amended_at, l.effective_at,
                l.sort_order AS law_sort_order,
                a.sort_order AS article_sort_order
            FROM articles a
            JOIN laws l ON l.law_id = a.law_id
            WHERE (
                a.text LIKE ? ESCAPE '\\'
                OR l.name LIKE ? ESCAPE '\\'
                OR a.article_no LIKE ? ESCAPE '\\'
            )
        """
        params: list[Any] = [pattern, pattern, pattern]
        if law_id:
            sql += " AND l.law_id = ?"
            params.append(law_id)
        sql += " ORDER BY l.sort_order, a.sort_order LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            item = _dict(row)
            item.pop("law_sort_order", None)
            item.pop("article_sort_order", None)
            item["snippet"] = _text_snippet(item["text"], cleaned)
            item["score"] = 0.0
            results.append(item)
        return results

    def list_articles_for_embedding(self) -> list[dict[str, Any]]:
        self._require_database()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.article_id, a.article_no, a.path, a.text,
                    l.law_id, l.name AS law_name, l.source_url,
                    l.latest_amended_at, l.effective_at
                FROM articles a
                JOIN laws l ON l.law_id = a.law_id
                ORDER BY l.sort_order, a.sort_order
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def replace_semantic_embeddings(
        self,
        model_name: str,
        dimension: int,
        article_vectors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._require_database()
        created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _create_semantic_schema(conn)
            conn.execute("DELETE FROM semantic_embeddings WHERE model = ?", (model_name,))
            conn.execute("DELETE FROM semantic_index_metadata WHERE model = ?", (model_name,))
            conn.executemany(
                """
                INSERT INTO semantic_embeddings (
                    article_id, model, dimension, vector, text_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["article_id"],
                        model_name,
                        dimension,
                        _pack_float32(item["vector"]),
                        item["text_hash"],
                        created_at,
                    )
                    for item in article_vectors
                ],
            )
            conn.execute(
                """
                INSERT INTO semantic_index_metadata (
                    model, mode, dimension, article_count, created_at
                ) VALUES (?, 'semantic_beta', ?, ?, ?)
                """,
                (model_name, dimension, len(article_vectors), created_at),
            )
            conn.commit()
        return {
            "mode": "semantic_beta",
            "model": model_name,
            "dimension": dimension,
            "article_count": len(article_vectors),
            "created_at": created_at,
        }

    def get_semantic_metadata(self, model_name: str) -> dict[str, Any] | None:
        self._require_database()
        with self._connect() as conn:
            if not _table_exists(conn, "semantic_index_metadata"):
                return None
            row = conn.execute(
                """
                SELECT model, mode, dimension, article_count, created_at
                FROM semantic_index_metadata
                WHERE model = ?
                """,
                (model_name,),
            ).fetchone()
        return _dict(row) if row else None

    def list_semantic_embeddings(self, model_name: str, law_id: str | None = None) -> list[dict[str, Any]]:
        self._require_database()
        with self._connect() as conn:
            if not _table_exists(conn, "semantic_embeddings"):
                return []
            sql = """
                SELECT
                    e.dimension, e.vector, e.text_hash,
                    a.article_id, a.article_no, a.path, a.text,
                    l.law_id, l.name AS law_name, l.source_url,
                    l.latest_amended_at, l.effective_at,
                    l.sort_order AS law_sort_order,
                    a.sort_order AS article_sort_order
                FROM semantic_embeddings e
                JOIN articles a ON a.article_id = e.article_id
                JOIN laws l ON l.law_id = a.law_id
                WHERE e.model = ?
            """
            params: list[Any] = [model_name]
            if law_id:
                sql += " AND l.law_id = ?"
                params.append(law_id)
            sql += " ORDER BY l.sort_order, a.sort_order"
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            item = _dict(row)
            item["vector"] = _unpack_float32(item["vector"])
            results.append(item)
        return results

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _require_database(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"database not found: {self.db_path}")


def _dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _manifest_from_conn(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT payload FROM update_manifest WHERE id = 1").fetchone()
    return json.loads(row["payload"]) if row else {}


def _unavailable_changes(manifest: dict[str, Any], reason: str) -> dict[str, Any]:
    counts = _empty_change_counts()
    return {
        "status": "unavailable",
        "updated_at": manifest.get("updated_at"),
        "previous_updated_at": None,
        "sources": manifest.get("sources", []),
        "license": manifest.get("license"),
        "counts": counts,
        "history_count": 0,
        "run": {
            "run_id": None,
            "updated_at": manifest.get("updated_at"),
            "previous_updated_at": None,
            "first_update": False,
            "status": "unavailable",
            "unavailable_reason": reason,
            "counts": counts,
        },
        "changes": [],
    }


def _empty_change_counts() -> dict[str, int]:
    return {
        "law_added": 0,
        "law_removed": 0,
        "law_modified": 0,
        "article_added": 0,
        "article_removed": 0,
        "article_modified": 0,
    }


def _change_counts_from_run(run: dict[str, Any]) -> dict[str, int]:
    return {key: int(run[key]) for key in _empty_change_counts()}


def _change_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = _dict(row)
    item["details"] = json.loads(item["details"] or "{}")
    return item


def _fts_phrase(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    escaped = cleaned.replace('"', '""')
    return f'"{escaped}"'


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _text_snippet(text: str, query: str, radius: int = 24) -> str:
    candidates = [query, *query.split()]
    index = -1
    matched = ""
    for candidate in candidates:
        if not candidate:
            continue
        index = text.find(candidate)
        if index >= 0:
            matched = candidate
            break
    if index < 0:
        return text[: radius * 2] + ("..." if len(text) > radius * 2 else "")
    start = max(0, index - radius)
    end = min(len(text), index + len(matched) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _create_semantic_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS semantic_embeddings (
            article_id TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            vector BLOB NOT NULL,
            text_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (article_id, model)
        );

        CREATE TABLE IF NOT EXISTS semantic_index_metadata (
            model TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            article_count INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _pack_float32(values: list[float]) -> bytes:
    return array("f", [float(value) for value in values]).tobytes()


def _unpack_float32(payload: bytes) -> list[float]:
    values = array("f")
    values.frombytes(payload)
    return [float(value) for value in values]
