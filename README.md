# FireBasis

FireBasis is a local FastAPI service and HeroUI React demo for Taiwan fire-company operations.

The current product direction is scheduling, dispatch, recurring inspections, visit status, and reschedule tracking. The central fire-law API remains as an internal trustworthy data layer, but the retired improvement lookup and citation UI pages are no longer product surfaces.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
npm install
npm run build
```

Run `npm run build` after changing files under `frontend/`. The built React shell is packaged under `src/firelaw_api/static/react`.

## Update The Law Database

```powershell
.\.venv\Scripts\firelaw-api.exe update --db data/firelaw.sqlite
```

The update command downloads the official open-data datasets from data.gov.tw, filters current central fire-related laws and regulations, and rebuilds the SQLite law database atomically.

## Run Locally

```powershell
.\.venv\Scripts\firelaw-api.exe serve --db data/firelaw.sqlite --app-db data/firebasis.sqlite --host 127.0.0.1 --port 8000
```

Open:

- `http://127.0.0.1:8000/` for the product homepage
- `http://127.0.0.1:8000/schedule` for the scheduling and dispatch demo
- `http://127.0.0.1:8000/docs` for developer API documentation

Retired routes:

- `/improvement`
- `/citation`
- `/ui`

These are intentionally not exposed as product pages.

## Scheduling / Dispatch API

The operations workflow uses a separate app database, usually `data/firebasis.sqlite`. It is intentionally separate from the official law database so law updates cannot overwrite product workflow data.

Core endpoints:

- `GET /schedule/health`
- `GET /schedule/sites?q=...`
- `POST /schedule/sites`
- `PATCH /schedule/sites/{site_id}`
- `GET /schedule/technicians?active=true`
- `POST /schedule/technicians`
- `PATCH /schedule/technicians/{technician_id}`
- `GET /schedule/series?site_id=...&active=true`
- `POST /schedule/series`
- `POST /schedule/series/{series_id}/generate-visits`
- `GET /schedule/visits?from=2026-08-01&to=2026-08-31&q=...`
- `POST /schedule/visits`
- `POST /schedule/visits/{visit_id}/assign`
- `POST /schedule/visits/{visit_id}/status`
- `POST /schedule/visits/{visit_id}/reschedule`
- `GET /schedule/visits/{visit_id}/status-events`
- `GET /schedule/visits/{visit_id}/reschedule-events`
- `GET /schedule/dispatch-board?date=2026-08-01`
- `GET /schedule/calendar?from=2026-08-01&to=2026-08-31`
- `GET /schedule/map?from=2026-08-01&to=2026-08-31`

Supported recurrence frequencies:

- weekly
- monthly
- quarterly
- semiannual
- yearly

Reschedule scopes:

- `single`
- `this_and_future`

## Law API Data Layer

The law API is still available for internal reference and developer use. It does not provide legal advice, AI legal answers, price judgment, or final applicability decisions.

Useful endpoints:

- `GET /health`
- `GET /meta/sources`
- `GET /meta/changes?limit=100`
- `GET /laws`
- `GET /laws/{law_id}`
- `GET /articles/{article_id}`
- `GET /search?q=滅火器`
- `GET /search/assist?q=店面要放幾個滅火器`
- `GET /search/semantic?q=店面要放幾個滅火器`

Semantic search remains optional:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[semantic]
.\.venv\Scripts\firelaw-api.exe semantic-update --db data/firelaw.sqlite --model intfloat/multilingual-e5-small
```

## Deploy To Vercel

The Vercel entrypoint is `api/index.py`, with routing in `vercel.json`.

The deployed demo uses the committed SQLite snapshot. For a newer law snapshot, run `firelaw-api update --db data/firelaw.sqlite`, verify locally, then commit the refreshed database.

Vercel scheduling data is read-only by default unless a durable writable app database is configured. Use the local server for create/update scheduling workflows.

## Sources And License

Main law data sources:

- 中文法規_法律資料檔下載: https://data.gov.tw/dataset/18289
- 中文法規_命令資料檔下載: https://data.gov.tw/dataset/18290
- Government Open Data License v1: https://data.gov.tw/license

Attribution: law data is provided by 法務部資訊處 through the Government Open Data Platform.
