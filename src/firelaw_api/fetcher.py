from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class DatasetConfig:
    kind: str
    dataset_id: str
    title: str
    page_url: str


DATASETS = (
    DatasetConfig("law", "18289", "中文法規_法律資料檔下載", "https://data.gov.tw/dataset/18289"),
    DatasetConfig("command", "18290", "中文法規_命令資料檔下載", "https://data.gov.tw/dataset/18290"),
)

METADATA_URL = "https://data.gov.tw/api/v2/rest/dataset/{dataset_id}"
USER_AGENT = "firelaw-api/0.1 (+https://data.gov.tw/license)"


def fetch_source_payloads(client: httpx.Client | None = None) -> list[tuple[str, bytes, str]]:
    close_client = client is None
    http = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        return [_fetch_dataset(http, dataset) for dataset in DATASETS]
    finally:
        if close_client:
            http.close()


def _fetch_dataset(http: httpx.Client, dataset: DatasetConfig) -> tuple[str, bytes, str]:
    candidates: list[str] = []
    metadata_response = http.get(METADATA_URL.format(dataset_id=dataset.dataset_id))
    if metadata_response.status_code < 400:
        try:
            candidates.extend(_extract_download_urls(metadata_response.json()))
        except ValueError:
            pass

    if not candidates:
        page = http.get(dataset.page_url)
        page.raise_for_status()
        candidates.extend(_extract_urls_from_html(page.text))

    download_url = _choose_download_url(candidates)
    response = http.get(download_url)
    response.raise_for_status()
    return dataset.kind, response.content, dataset.page_url


def _extract_download_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and _looks_like_download_key(key) and item.startswith(("http://", "https://")):
                urls.append(item)
            urls.extend(_extract_download_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_extract_download_urls(item))
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        if _looks_like_payload_url(value):
            urls.append(value)
    return _dedupe(urls)


def _extract_urls_from_html(html: str) -> list[str]:
    urls = re.findall(r'https?://[^"\'<>\s]+', html)
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    for href in hrefs:
        if href.startswith("//"):
            urls.append("https:" + href)
        elif href.startswith("http"):
            urls.append(href)
    return _dedupe(url for url in urls if _looks_like_payload_url(url))


def _choose_download_url(candidates: Iterable[str]) -> str:
    urls = list(_dedupe(candidates))
    if not urls:
        raise RuntimeError("No download URL found in data.gov.tw metadata")
    for url in urls:
        lower = url.lower()
        if "zip" in lower or lower.endswith(".zip"):
            return url
    return urls[0]


def _looks_like_download_key(key: str) -> bool:
    lowered = key.lower()
    return "download" in lowered or "url" in lowered


def _looks_like_payload_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "sendlaw.moj.gov.tw" in lowered
        or lowered.endswith(".zip")
        or lowered.endswith(".xml")
        or "dtype=xml" in lowered
    )


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
