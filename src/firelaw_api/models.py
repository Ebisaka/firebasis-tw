from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArticleDocument:
    article_no: str
    text: str
    path: str = ""


@dataclass(frozen=True)
class LawDocument:
    source_kind: str
    name: str
    source_url: str
    category: str = ""
    level: str = ""
    latest_amended_at: str | None = None
    effective_at: str | None = None
    abolished: bool = False
    raw_hash: str = ""
    articles: list[ArticleDocument] = field(default_factory=list)
