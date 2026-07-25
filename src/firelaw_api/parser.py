from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections.abc import Iterable
from datetime import date
from xml.etree import ElementTree as ET

from .models import ArticleDocument, LawDocument

FIRE_LAW_ALLOWLIST = {
    "消防法",
    "消防法施行細則",
    "各類場所消防安全設備設置標準",
    "消防安全設備檢修及申報辦法",
}

LAW_CONTAINER_TAGS = {"法規", "Law", "LawData", "LawContent"}
ARTICLE_CONTAINER_TAGS = {"法規內容", "條文", "Articles", "LawArticles", "編章節"}
ARTICLE_TAGS = {"條", "條文", "Article", "LawArticle"}

FIELD_ALIASES = {
    "level": ("法規性質", "法規位階", "LawLevel", "Level", "LawType"),
    "name": ("法規名稱", "LawName", "Name"),
    "source_url": ("法規網址", "LawURL", "LawUrl", "URL", "Url"),
    "category": ("法規類別", "法規體系", "LawCategory", "Category"),
    "latest_amended_at": ("最新異動日期", "ModifiedDate", "LatestModifiedDate", "AmednDate"),
    "effective_at": ("生效日期", "EffectiveDate"),
    "abolished": ("廢止註記", "廢止日期", "Abolished", "IsAbrogated"),
}

ARTICLE_ALIASES = {
    "article_no": ("條號", "ArticleNo", "ArticleNumber", "No"),
    "text": ("條文內容", "ArticleContent", "Content", "Text"),
    "path": ("編章節", "章節", "Path", "Chapter"),
}


def parse_documents(raw_sources: Iterable[tuple[str, bytes]]) -> list[LawDocument]:
    documents: list[LawDocument] = []
    for source_kind, payload in raw_sources:
        for xml_payload in _iter_xml_payloads(payload):
            documents.extend(_parse_xml_document(source_kind, xml_payload))
    return [document for document in documents if _should_include(document)]


def _iter_xml_payloads(payload: bytes) -> Iterable[bytes]:
    buffer = io.BytesIO(payload)
    if zipfile.is_zipfile(buffer):
        with zipfile.ZipFile(buffer) as archive:
            for name in archive.namelist():
                if name.lower().endswith(".xml"):
                    yield archive.read(name)
        return
    yield payload


def _parse_xml_document(source_kind: str, payload: bytes) -> list[LawDocument]:
    root = ET.fromstring(payload)
    law_nodes = _find_law_nodes(root)
    if not law_nodes:
        law_nodes = [root]

    documents: list[LawDocument] = []
    for node in law_nodes:
        name = _field_text(node, FIELD_ALIASES["name"])
        if not name:
            continue
        articles = _parse_articles(node)
        if not articles:
            continue
        raw_xml = ET.tostring(node, encoding="utf-8")
        documents.append(
            LawDocument(
                source_kind=source_kind,
                name=name,
                source_url=_field_text(node, FIELD_ALIASES["source_url"]),
                category=_field_text(node, FIELD_ALIASES["category"]),
                level=_field_text(node, FIELD_ALIASES["level"]),
                latest_amended_at=normalize_date(_field_text(node, FIELD_ALIASES["latest_amended_at"])),
                effective_at=normalize_date(_field_text(node, FIELD_ALIASES["effective_at"])),
                abolished=_is_abolished(_field_text(node, FIELD_ALIASES["abolished"]), name),
                raw_hash=hashlib.sha256(raw_xml).hexdigest(),
                articles=articles,
            )
        )
    return documents


def _find_law_nodes(root: ET.Element) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag in LAW_CONTAINER_TAGS and _field_text(element, FIELD_ALIASES["name"]):
            nodes.append(element)
    return nodes


def _parse_articles(law_node: ET.Element) -> list[ArticleDocument]:
    article_nodes: list[ET.Element] = []
    for element in law_node.iter():
        tag = _local_name(element.tag)
        if tag in ARTICLE_TAGS and _direct_field_text(element, ARTICLE_ALIASES["article_no"]):
            article_nodes.append(element)

    articles = [_article_from_node(node) for node in article_nodes]
    articles = [article for article in articles if article.article_no and article.text]
    if articles:
        return articles

    text = _field_text(law_node, ARTICLE_ALIASES["text"]) or _container_text(law_node, ARTICLE_CONTAINER_TAGS)
    return _split_plain_articles(text)


def _article_from_node(node: ET.Element) -> ArticleDocument:
    text = _direct_field_text(node, ARTICLE_ALIASES["text"])
    if not text:
        parts = []
        for child in node:
            if _local_name(child.tag) not in set(ARTICLE_ALIASES["article_no"]) | set(ARTICLE_ALIASES["path"]):
                parts.append(_normalize_space("".join(child.itertext())))
        text = _normalize_space(" ".join(part for part in parts if part))
    return ArticleDocument(
        article_no=_direct_field_text(node, ARTICLE_ALIASES["article_no"]),
        text=text,
        path=_direct_field_text(node, ARTICLE_ALIASES["path"]),
    )


def _split_plain_articles(text: str) -> list[ArticleDocument]:
    text = _normalize_space(text)
    if not text:
        return []
    pattern = re.compile(r"(第\s*[一二三四五六七八九十百千零\d\-之]+\s*條(?:之\s*\d+)?)")
    pieces = pattern.split(text)
    if len(pieces) < 3:
        return [ArticleDocument(article_no="全文", text=text)]

    articles: list[ArticleDocument] = []
    for index in range(1, len(pieces), 2):
        article_no = _normalize_space(pieces[index])
        article_text = _normalize_space(pieces[index + 1] if index + 1 < len(pieces) else "")
        if article_text:
            articles.append(ArticleDocument(article_no=article_no, text=article_text))
    return articles


def _field_text(node: ET.Element, aliases: tuple[str, ...]) -> str:
    direct = _direct_field_text(node, aliases)
    if direct:
        return direct
    for child in node.iter():
        if child is not node and _local_name(child.tag) in set(aliases):
            return _normalize_space("".join(child.itertext()))
    return ""


def _direct_field_text(node: ET.Element, aliases: tuple[str, ...]) -> str:
    alias_set = set(aliases)
    for child in list(node):
        if _local_name(child.tag) in alias_set:
            return _normalize_space("".join(child.itertext()))
    return ""


def _container_text(node: ET.Element, tags: set[str]) -> str:
    for child in node.iter():
        if _local_name(child.tag) in tags:
            return _normalize_space("".join(child.itertext()))
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _is_abolished(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"y", "yes", "true", "1", "是", "廢止", "已廢止"} or name.startswith(("廢/", "廢止", "停止"))


def _should_include(document: LawDocument) -> bool:
    if document.abolished:
        return False
    category = document.category.replace(" ", "")
    if "地方" in category or "自治" in category:
        return False
    if document.name in FIRE_LAW_ALLOWLIST:
        return True
    return "內政部" in category and "消防目" in category


def normalize_date(raw: str) -> str | None:
    value = _normalize_space(raw)
    if not value:
        return None

    digits = re.sub(r"\D", "", value)
    if len(digits) == 8 and digits.startswith(("19", "20")):
        return _safe_iso(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    if len(digits) >= 6:
        year_digits = digits[:-4]
        month_digits = digits[-4:-2]
        day_digits = digits[-2:]
        year = int(year_digits)
        if year < 1911:
            year += 1911
        return _safe_iso(year, int(month_digits), int(day_digits))
    return None


def _safe_iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
