import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from firelaw_api.api import create_app


PROJECT_ROOT = Path(__file__).parents[1]
STATIC = PROJECT_ROOT / "src" / "firelaw_api" / "static"
DATA_PATH = STATIC / "improvement-data.json"

ALLOWED_CATEGORIES = {"消防燈類", "火警探測器類"}
BANNED_PHRASES = {"一定要換", "不換一定違法", "消防隊一定會開罰", "系統判定不合格"}
BANNED_REVIEW_PHRASES = BANNED_PHRASES | {"違法", "必須更換", "保證合格"}
IDENTITY_KEYS = {"customer_name", "company_name", "address", "phone", "email", "reviewer_name"}
REVIEWED_BASIS_FIELDS = {
    "law_name",
    "article_no",
    "candidate_query",
    "basis_reason",
    "basis_scope",
    "review_status",
}


def load_improvement_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def run_improvement_js_expression(expression: str, context: dict | None = None):
    if shutil.which("node") is None:
        pytest.skip("node is required for the static improvement UI tests")

    context = context or {}
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const code = fs.readFileSync({json.dumps(str(STATIC / "improvement.js"))}, "utf8")
          .replace(/\\ninit\\(\\);\\s*$/, "");
        const sandbox = {{
          document: {{ querySelector: () => null, querySelectorAll: () => [] }},
          window: {{ setTimeout: () => null }},
          navigator: {{}},
          fetch: async () => {{ throw new Error("fetch not mocked"); }},
          URLSearchParams,
          Date,
          ...{json.dumps(context)},
        }};
        vm.runInNewContext(code, sandbox);
        const result = vm.runInNewContext({json.dumps(expression)}, sandbox);
        console.log(JSON.stringify(result));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_improvement_data_has_exactly_ten_safe_seed_items():
    payload = load_improvement_data()
    items = payload["items"]

    assert payload["version"]
    assert len(items) == 10
    assert {item["category"] for item in items} <= ALLOWED_CATEGORIES
    assert len({item["item_id"] for item in items}) == 10

    display_names = {item["display_name"] for item in items}
    assert "出口標示燈更換 6 組" in display_names
    assert "避難方向指示燈更換 4 組" in display_names
    assert "緊急照明燈更換 4 組" in display_names
    assert "偵煙探測器更換 12 只" in display_names
    assert any("定溫探測器" in name for name in display_names)
    assert any("差動探測器" in name for name in display_names)

    for item in items:
        assert IDENTITY_KEYS.isdisjoint(item)
        assert "price" not in item
        assert item["scenario"]
        assert item["customer_question"]
        assert item["candidate_queries"]
        assert item["reviewed_basis_candidates"]
        assert item["customer_explanation_lines"]
        assert item["required_site_checks"]

        for basis in item["reviewed_basis_candidates"]:
            assert REVIEWED_BASIS_FIELDS <= set(basis)
            assert basis["review_status"] == "manual_seed"
            assert basis["candidate_query"] in item["candidate_queries"]
            assert basis["law_name"] == "各類場所消防安全設備設置標準"
            assert basis["article_no"].startswith("第 ")
            for phrase in BANNED_REVIEW_PHRASES:
                assert phrase not in basis["basis_reason"]

        joined_explanation = "\n".join(item["customer_explanation_lines"])
        for phrase in BANNED_PHRASES:
            assert phrase not in joined_explanation


def test_rate_of_rise_detector_has_reviewed_basis_for_article_114():
    payload = load_improvement_data()
    item = next(item for item in payload["items"] if item["item_id"] == "rate-of-rise-detector-replacement")

    assert "差動式" in item["candidate_queries"]
    assert any(
        basis["law_name"] == "各類場所消防安全設備設置標準"
        and basis["article_no"] == "第 114 條"
        and basis["candidate_query"] == "差動式"
        for basis in item["reviewed_basis_candidates"]
    )


def test_validate_improvement_data_rejects_bad_shape():
    result = run_improvement_js_expression(
        """
        ({
          valid: validateImprovementData({
            version: "test",
            items: [{
              item_id: "bad",
              display_name: "壞資料",
              category: "地方法規",
              field_terms: [],
              equipment_candidates: [],
              defect_candidates: [],
              required_site_checks: [],
              candidate_queries: [],
              customer_question: "",
              customer_explanation_lines: ["這個一定要換"],
              boundary_labels: [],
              avoid_phrases: ["一定要換"],
              reviewed_basis_candidates: [],
            }],
          })
        })
        """
    )

    assert result["valid"]["valid"] is False
    assert "items must contain exactly 10 entries" in result["valid"]["errors"]
    assert any("category" in error for error in result["valid"]["errors"])
    assert any("scenario" in error for error in result["valid"]["errors"])
    assert any("customer_question" in error for error in result["valid"]["errors"])
    assert any("banned phrase" in error for error in result["valid"]["errors"])
    assert any("reviewed_basis_candidates" in error for error in result["valid"]["errors"])


def test_merge_basis_results_dedupes_and_keeps_query_source():
    result = run_improvement_js_expression(
        """
        mergeBasisResults([
          {
            query: "出口標示燈",
            results: [
              { article_id: "a1", law_name: "各類場所消防安全設備設置標準", article_no: "第 1 條", score: 2 },
              { article_id: "a2", law_name: "消防法", article_no: "第 9 條", score: 1 },
            ],
          },
          {
            query: "緊急照明",
            results: [
              { article_id: "a1", law_name: "各類場所消防安全設備設置標準", article_no: "第 1 條", score: 9 },
              { article_id: "a3", law_name: "消防法施行細則", article_no: "第 3 條", score: 5 },
            ],
          },
        ])
        """
    )

    assert [item["article_id"] for item in result] == ["a1", "a2", "a3"]
    assert result[0]["matched_query"] == "出口標示燈"
    assert result[2]["matched_query"] == "緊急照明"


def test_merge_basis_results_annotates_and_prioritizes_reviewed_basis():
    result = run_improvement_js_expression(
        """
        const reviewed = buildReviewedBasisMap([
          {
            law_name: "各類場所消防安全設備設置標準",
            article_no: "第 114 條",
            candidate_query: "差動式",
            basis_reason: "探測器種類與裝置場所高度相關。",
            basis_scope: "設備型式相關",
            review_status: "manual_seed",
          },
        ]);
        mergeBasisResults([
          {
            query: "火警探測器",
            results: [
              { article_id: "broad", law_name: "各類場所消防安全設備設置標準", article_no: "第 91 條", score: 9 },
            ],
          },
          {
            query: "差動式",
            results: [
              { article_id: "reviewed", law_name: "各類場所消防安全設備設置標準", article_no: "第 114 條", score: 1 },
            ],
          },
        ], reviewed)
        """
    )

    assert [item["article_id"] for item in result] == ["reviewed", "broad"]
    assert result[0]["matched_query"] == "差動式"
    assert result[0]["basis_reason"] == "探測器種類與裝置場所高度相關。"
    assert result[0]["basis_scope"] == "設備型式相關"
    assert result[0]["review_status"] == "manual_seed"
    assert result[0]["reviewed_basis"] is True


def test_line_explanation_and_calibration_export_are_safe():
    result = run_improvement_js_expression(
        """
        const item = {
          item_id: "exit-sign-replacement",
          display_name: "出口標示燈更換 6 組",
          required_site_checks: ["確認設置位置", "確認燈具是否能正常點亮"],
          customer_explanation_lines: [
            "此品項可能涉及避難指標或消防安全設備維護。",
            "實際是否需更換，仍需依現場檢修結果與設備狀態確認。",
          ],
        };
        const basis = [
          {
            article_id: "art-1",
            law_name: "各類場所消防安全設備設置標準",
            article_no: "第 146 條",
            matched_query: "出口標示燈",
            basis_reason: "標示設備之構造與基準相關。",
            basis_scope: "標示燈基準相關",
            review_status: "manual_seed",
          },
        ];
        const sourceMeta = { updated_at: "2026-07-25T00:00:00Z" };
        ({
          line: formatLineExplanation(item, basis, sourceMeta),
          calibration: buildCalibrationExport(item, ["說明講太滿"], "需補現場條件", basis, sourceMeta, "2026-07-25-beta-seed"),
          banned: containsBannedPhrase("不換一定違法", ["一定違法"]),
        })
        """
    )

    assert "關於「出口標示燈更換 6 組」：" in result["line"]
    assert "需現場確認：" in result["line"]
    assert "- 各類場所消防安全設備設置標準 第 146 條" in result["line"]
    assert "不代表最終合格、不合格或必然需更換之判定" in result["line"]
    assert "一定要換" not in result["line"]
    assert result["calibration"]["item_id"] == "exit-sign-replacement"
    assert result["calibration"]["selected_flags"] == ["說明講太滿"]
    assert result["calibration"]["basis_article_ids"] == ["art-1"]
    assert result["calibration"]["reviewed_basis_keys"] == ["各類場所消防安全設備設置標準|第 146 條"]
    assert result["calibration"]["basis_reasons"] == {
        "各類場所消防安全設備設置標準|第 146 條": "標示設備之構造與基準相關。"
    }
    assert result["calibration"]["source_updated_at"] == "2026-07-25T00:00:00Z"
    assert result["calibration"]["data_version"] == "2026-07-25-beta-seed"
    assert not (IDENTITY_KEYS & set(result["calibration"].keys()))
    assert result["banned"] is True


def test_deficiency_view_model_proposal_support_and_calibration_summary_are_safe():
    result = run_improvement_js_expression(
        """
        const item = {
          item_id: "rate-of-rise-detector-replacement",
          display_name: "差動探測器更換",
          category: "火警探測器類",
          scenario: "報價單出現差動探測器更換時，業主想知道為什麼要處理。",
          customer_question: "這個探測器一定要換嗎？依據在哪裡？",
          field_terms: ["差動探測器", "差動式"],
          equipment_candidates: ["差動式探測器"],
          defect_candidates: ["動作異常"],
          required_site_checks: ["確認差動式探測器型式", "確認測試動作與復歸狀態"],
          candidate_queries: ["差動式"],
          reviewed_basis_candidates: [],
          customer_explanation_lines: [
            "此品項可能涉及自動火警設備中熱感探測器的動作功能。",
            "是否需處理仍需依測試反應、回路狀態與現場條件確認。",
          ],
          boundary_labels: ["候選依據", "需現場確認", "不作最終判定"],
          avoid_phrases: [],
        };
        const basis = [
          {
            article_id: "article-114",
            law_name: "各類場所消防安全設備設置標準",
            article_no: "第 114 條",
            matched_query: "差動式",
            basis_reason: "探測器種類與裝置場所高度相關，條文文字直接包含差動式探測器類型。",
            basis_scope: "探測器型式相關",
            source_url: "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0120029",
          },
        ];
        const sourceMeta = { updated_at: "2026-07-25T00:00:00Z" };
        ({
          viewModel: buildDeficiencyCaseViewModel(item),
          proposal: formatProposalSupport(item, basis, sourceMeta, "improvement-beta-2026-07-25"),
          emptyProposal: formatProposalSupport(item, [], null, "improvement-beta-2026-07-25"),
          summaryDefault: formatCalibrationSummary(item, [], ""),
          summaryFilled: formatCalibrationSummary(item, ["說明講太滿", "缺少現場確認"], "先確認型式與測試結果。"),
        })
        """
    )

    assert result["viewModel"]["scenario"] == "報價單出現差動探測器更換時，業主想知道為什麼要處理。"
    assert result["viewModel"]["customer_question"] == "這個探測器一定要換嗎？依據在哪裡？"
    assert "改善項目：" in result["proposal"]
    assert "差動探測器更換" in result["proposal"]
    assert "使用情境：" in result["proposal"]
    assert "業主常見問題：" in result["proposal"]
    assert "保守說明：" in result["proposal"]
    assert "需現場確認：" in result["proposal"]
    assert "候選官方依據：" in result["proposal"]
    assert "各類場所消防安全設備設置標準 第 114 條" in result["proposal"]
    assert "官方資料更新時間：2026-07-25T00:00:00Z" in result["proposal"]
    assert "Seed 版本：improvement-beta-2026-07-25" in result["proposal"]
    assert "不構成法律意見" in result["proposal"]
    assert "未取得候選條文，需人工確認" in result["emptyProposal"]
    for phrase in BANNED_REVIEW_PHRASES:
      assert phrase not in result["proposal"]
    assert result["summaryDefault"] == "尚未校閱。"
    assert "已標記：說明講太滿、缺少現場確認。" in result["summaryFilled"]
    assert "備註：先確認型式與測試結果。" in result["summaryFilled"]


def test_evidence_view_model_and_conservative_explanation_prioritize_primary_basis():
    result = run_improvement_js_expression(
        """
        const item = {
          item_id: "rate-of-rise-detector-replacement",
          display_name: "差動探測器更換",
          category: "火警探測器類",
          scenario: "報價單出現差動探測器更換時，業主想知道為什麼要處理。",
          customer_question: "這個探測器一定要換嗎？依據在哪裡？",
          required_site_checks: ["確認差動式探測器型式"],
          customer_explanation_lines: [
            "此品項可能涉及自動火警設備中熱感探測器的動作功能。",
            "是否需處理仍需依測試反應、回路狀態與現場條件確認。",
          ],
        };
        const basis = [
          {
            article_id: "article-114",
            law_name: "各類場所消防安全設備設置標準",
            article_no: "第 114 條",
            matched_query: "差動式",
            basis_reason: "探測器種類與裝置場所高度相關。",
            basis_scope: "探測器型式相關",
            source_url: "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0120029",
          },
          {
            article_id: "article-91",
            law_name: "各類場所消防安全設備設置標準",
            article_no: "第 91 條",
            matched_query: "火警探測器",
            basis_reason: "自動火警設備章節相關。",
            basis_scope: "火警設備通則相關",
            source_url: "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0120029",
          },
        ];
        const viewModel = buildEvidenceViewModel(basis, [], ["人工確認候選未命中"]);
        ({
          primary: primaryBasisResult(basis),
          emptyPrimary: primaryBasisResult([]),
          viewModel,
          conservative: formatConservativeExplanation(
            item,
            viewModel.primaryBasis,
            { updated_at: "2026-07-25T00:00:00Z" },
            "improvement-beta-2026-07-25",
            viewModel.hasMoreBasis,
          ),
          unavailable: buildEvidenceViewModel([], ["HTTP 503"], []),
        })
        """
    )

    assert result["primary"]["article_id"] == "article-114"
    assert result["emptyPrimary"] is None
    assert result["viewModel"]["primaryBasis"]["article_id"] == "article-114"
    assert [item["article_id"] for item in result["viewModel"]["otherBasis"]] == ["article-91"]
    assert result["viewModel"]["hasMoreBasis"] is True
    assert result["viewModel"]["statusText"] == "已取得候選依據，可複製保守說明"
    assert result["viewModel"]["statusKind"] == ""
    assert result["unavailable"]["statusText"] == "資料庫未連線，仍可查看保守說明"
    assert result["unavailable"]["statusKind"] == "warning"
    assert "改善品項：" in result["conservative"]
    assert "業主常見問題：" in result["conservative"]
    assert "保守說明：" in result["conservative"]
    assert "主要候選官方依據：" in result["conservative"]
    assert "各類場所消防安全設備設置標準 第 114 條" in result["conservative"]
    assert "第 91 條" not in result["conservative"]
    assert "另有其他候選依據，需人工確認" in result["conservative"]
    assert "不構成法律意見" in result["conservative"]
    for phrase in BANNED_REVIEW_PHRASES:
        assert phrase not in result["conservative"]


def test_reviewed_basis_candidates_match_local_database_smoke():
    db_path = PROJECT_ROOT / "data" / "firelaw.sqlite"
    if not db_path.exists():
        pytest.skip("local firelaw.sqlite is required for reviewed basis smoke")

    client = TestClient(create_app(db_path))
    payload = load_improvement_data()
    misses = []

    for item in payload["items"]:
        for basis in item["reviewed_basis_candidates"]:
            response = client.get("/search/assist", params={"q": basis["candidate_query"], "limit": 20})
            assert response.status_code == 200
            results = response.json()["results"]
            if not any(
                result["law_name"] == basis["law_name"] and result["article_no"] == basis["article_no"]
                for result in results
            ):
                misses.append(f"{item['item_id']}:{basis['candidate_query']} -> {basis['article_no']}")

    assert misses == []


def test_improvement_html_accessibility_contract():
    html = (STATIC / "improvement.html").read_text(encoding="utf-8")

    assert "消防改善依據反查" in html
    assert "Beta" in html
    assert "僅提供候選官方依據與保守說明" in html
    assert "工作台" not in html
    assert 'aria-label="缺失品項佇列"' in html
    assert 'aria-label="目前缺失案例"' in html
    assert 'aria-label="候選官方依據"' in html
    assert 'id="caseStatusLine"' in html
    assert 'id="basisList"' in html
    assert 'id="primaryBasis"' in html
    assert 'id="fullBasisDetails"' in html
    assert 'id="copyConservativeButton"' in html
    assert "複製保守說明" in html
    assert 'id="copyFormatMenu"' in html
    assert "LINE 簡版" in html
    assert "完整報價素材" in html
    assert "校閱備註" in html
    assert "高手校正" not in html
    assert 'id="calibrationSummary"' in html
    assert 'aria-live="polite"' in html
    assert 'href="/citation"' in html
    assert 'href="/docs"' in html
    assert "搜尋" not in html.split("<main", 1)[0]
