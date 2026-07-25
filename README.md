# 台灣消防法規查詢 API v1

Local FastAPI service for Taiwan central fire-law citation lookup. It returns official source references only; it does not provide legal advice or AI-generated legal conclusions.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

## Update The Local Database

```powershell
.\.venv\Scripts\firelaw-api.exe update --db data/firelaw.sqlite
```

The update command downloads the official open-data datasets from data.gov.tw, filters current central fire-related laws and regulations, and rebuilds the SQLite database atomically.
On the first update it creates a change baseline. On later updates it reports local law/article changes, for example:

```text
Updated data\firelaw.sqlite: 80 laws, 1591 articles.
Changes: laws +0 ~1 -0; articles +2 ~3 -1
```

## Run The API

```powershell
.\.venv\Scripts\firelaw-api.exe serve --db data/firelaw.sqlite --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the local citation lookup page.
Open `http://127.0.0.1:8000/docs` for developer API documentation.

Useful endpoints:

- `GET /`
- `GET /ui`
- `GET /health`
- `GET /meta/sources`
- `GET /meta/changes?limit=100`
- `GET /laws`
- `GET /laws/{law_id}`
- `GET /articles/{article_id}`
- `GET /search?q=滅火器`
- `GET /search/assist?q=店面要放幾個滅火器`
- `GET /search/semantic?q=店面要放幾個滅火器`

## Deploy To Vercel

This repository includes a Vercel entrypoint at `app.py`.
It creates the FastAPI app with the packaged demo database at `data/firelaw.sqlite`, so the GitHub-connected Vercel project can deploy the current workbench without running a live data update during build.

Recommended flow:

1. Push `main` to GitHub.
2. Let the Vercel project `firebasis-tw` deploy from the connected GitHub repository.
3. Open the deployed `/improvement` page for the guided trial demo.

The deployed demo uses the committed SQLite snapshot. Run `firelaw-api update --db data/firelaw.sqlite`, verify locally, then commit the refreshed database when you want to publish a newer official-source snapshot.

## Local Semantic Search Beta

The default API remains SQLite FTS citation lookup. To try the local semantic beta:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[semantic]
.\.venv\Scripts\firelaw-api.exe semantic-update --db data/firelaw.sqlite --model intfloat/multilingual-e5-small
```

Semantic beta uses local embeddings and returns official citation results only.

## Citation Workbench

The local page at `http://127.0.0.1:8000/` is a professional citation workbench for building official-source references. Search results can be copied as a single formal citation or added to an in-memory citation package.

Citation package formats:

- `正式引用`: plain official citation blocks.
- `報告素材`: plain text with generated time, data update time, license, source hashes, and full article text.
- `Markdown`: markdown report-friendly citation blocks.

The workbench also reads `GET /meta/changes` to show the latest local update diff. This is a local before/after comparison between `firelaw-api update` runs, not real-time legal monitoring.

## 改善缺失依據與報價說明工作台

Open `http://127.0.0.1:8000/improvement` for the separate deficiency/proposal-support workbench.

This beta starts from a small packaged JSON seed list of fire-light and fire-detector deficiency or quote items, then uses the existing official-citation API to find candidate official references. It is designed for cautious customer-facing wording, internal site-check prompts, proposal-support copy text, and expert calibration JSON export.

It does not store customer data, prices, history, or final pass/fail conclusions.

Smoke flow:

1. Start the API:

   ```powershell
   .\.venv\Scripts\firelaw-api.exe serve --db data/firelaw.sqlite --host 127.0.0.1 --port 8000
   ```

2. Open `http://127.0.0.1:8000/improvement`.
3. Pick `差動探測器更換`.
4. Confirm the evidence panel includes `各類場所消防安全設備設置標準 第 114 條`.
5. Click `複製保守說明` and confirm the copied text includes the primary candidate official reference, data version, and safety reminder.

Optional repeatable smoke:

```powershell
node scripts\smoke-improvement-workbench.js
```

The smoke checks desktop and 390px mobile width, verifies the primary Article 114 evidence, and fails on horizontal overflow. It uses Playwright from the Codex bundled runtime when available; otherwise install Playwright in a dev environment before running it.

To add a packaged deficiency case, edit `src/firelaw_api/static/improvement-data.json` and keep exactly 10 trial items for the current beta. Each item must include:

- `item_id`
- `display_name`
- `category`
- `scenario`
- `customer_question`
- `field_terms`
- `equipment_candidates`
- `defect_candidates`
- `required_site_checks`
- `candidate_queries`
- `reviewed_basis_candidates`
- `customer_explanation_lines`
- `boundary_labels`
- `avoid_phrases`

Use conservative wording such as `可能涉及`, `需現場確認`, `候選官方依據`, and `不作最終判定`. Do not use conclusion phrases such as `一定要換`, `不換一定違法`, `消防隊一定會開罰`, `系統判定不合格`, `必須更換`, or `保證合格`.

`reviewed_basis_candidates` records manually checked candidate citations. Its `review_status` should be `manual_seed`, meaning it is a seed hint reviewed for this demo, not a final legal conclusion. A local DB smoke test is optional but recommended before showing the workbench to trial users.

## Sources And License

Main data sources:

- 中文法規_法律資料檔下載: https://data.gov.tw/dataset/18289
- 中文法規_命令資料檔下載: https://data.gov.tw/dataset/18290
- Government Open Data License v1: https://data.gov.tw/license

Attribution: data is provided by 法務部資訊處 through the Government Open Data Platform.
