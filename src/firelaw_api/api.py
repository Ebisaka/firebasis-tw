from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .ingest import LEGAL_NOTICE
from .search_assist import assist_search
from .semantic import DEFAULT_SEMANTIC_MODEL, SemanticUnavailableError, semantic_search
from .store import FirelawStore

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    db_path: Path,
    semantic_model_name: str = DEFAULT_SEMANTIC_MODEL,
    semantic_provider_factory=None,
) -> FastAPI:
    store = FirelawStore(Path(db_path))
    app = FastAPI(
        title="台灣消防法規查詢 API",
        version="0.1.0",
        description=LEGAL_NOTICE,
    )

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "home-preview.html")

    @app.get("/ui", include_in_schema=False)
    def ui():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/citation", include_in_schema=False)
    def citation():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/improvement", include_in_schema=False)
    def improvement():
        return FileResponse(STATIC_DIR / "improvement.html")

    @app.get("/home-preview", include_in_schema=False)
    def home_preview():
        return FileResponse(STATIC_DIR / "home-preview.html")

    @app.get("/assets/{asset_name}", include_in_schema=False)
    def asset(asset_name: str):
        allowed_assets = {
            "app.js": "text/javascript; charset=utf-8",
            "home-preview.js": "text/javascript; charset=utf-8",
            "improvement.js": "text/javascript; charset=utf-8",
            "improvement-data.json": "application/json; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
        }
        if asset_name not in allowed_assets:
            raise HTTPException(status_code=404, detail="asset not found")
        return FileResponse(STATIC_DIR / asset_name, media_type=allowed_assets[asset_name])

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/health", summary="服務與資料庫狀態")
    def health():
        return store.health()

    @app.get("/meta/sources", summary="資料來源與授權資訊")
    def sources():
        try:
            return store.get_sources()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/meta/changes",
        summary="本機資料更新差異",
        description="回傳最近一次 firelaw-api update 的本機前後版差異；用於追溯引用資料版本，不提供法律結論。",
    )
    def changes(limit: int = Query(default=100, ge=1, le=500, examples=[100])):
        try:
            return store.get_changes(limit=limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/laws", summary="列出已索引的中央消防法規")
    def laws():
        try:
            return store.list_laws()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/laws/{law_id}", summary="取得單一法規與條文清單")
    def law(law_id: str):
        try:
            result = store.get_law(law_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="law not found")
        return result

    @app.get("/articles/{article_id}", summary="取得單一條文引用")
    def article(article_id: str):
        try:
            result = store.get_article(article_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="article not found")
        return result

    @app.get(
        "/search/assist",
        summary="白話查詢輔助",
        description="使用可控同義詞與俗稱字典展開查詢，仍只回傳官方條文引用。範例查詢：店面要放幾個滅火器。",
    )
    def search_assist(
        q: str = Query(min_length=1, examples=["店面要放幾個滅火器"]),
        law_id: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        try:
            return assist_search(store, q, law_id=law_id, limit=limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get(
        "/search/semantic",
        summary="語意搜尋官方條文引用 beta",
        description="使用本機 embedding beta 搜尋中央消防相關法規條文；不產生法律結論。需先執行 semantic-update。",
    )
    def search_semantic(
        q: str = Query(min_length=1, examples=["店面要放幾個滅火器"]),
        law_id: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        try:
            provider = semantic_provider_factory(semantic_model_name) if semantic_provider_factory else None
            results = semantic_search(
                store,
                q,
                law_id=law_id,
                limit=limit,
                model_name=semantic_model_name,
                provider=provider,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SemanticUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"query": q, "law_id": law_id, "limit": limit, "mode": "semantic_beta", "results": results}

    @app.get(
        "/search",
        summary="搜尋官方條文引用",
        description="使用 SQLite FTS5 trigram 搜尋中央消防相關法規條文。範例查詢：滅火器、消防安全設備。",
    )
    def search(
        q: str = Query(min_length=1, examples=["滅火器"]),
        law_id: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        try:
            results = store.search(q, law_id=law_id, limit=limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"query": q, "law_id": law_id, "limit": limit, "results": results}

    return app
