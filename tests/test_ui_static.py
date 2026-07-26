import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


STATIC = Path(__file__).parents[1] / "src" / "firelaw_api" / "static"


def run_app_js_expression(expression: str, context: dict | None = None):
    if shutil.which("node") is None:
        pytest.skip("node is required for the static UI smoke test")

    context = context or {}

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const code = fs.readFileSync({json.dumps(str(STATIC / "app.js"))}, "utf8")
          .replace(/\\ninit\\(\\);\\s*$/, "");
        const sandbox = {{
          document: {{ querySelector: () => null }},
          URLSearchParams,
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


def run_law_text_segmenter(sample: str) -> list[str]:
    return run_app_js_expression("formatLawTextSegments(sample)", {"sample": sample})


def test_citation_page_is_positioned_without_default_search_or_workbench_label():
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "台灣消防法規引用" in index_html
    assert "工作台" not in index_html
    assert 'href="/improvement">改善依據反查</a>' in index_html
    assert 'href="/">改善依據反查</a>' not in index_html
    assert "資料版本" in index_html
    assert "本次更新" in index_html
    assert "法源附件包" in index_html
    assert "附件格式" in index_html
    assert "value=\"滅火器\"" not in index_html
    assert "檢修申報" in index_html
    assert "防火管理人" in index_html


def test_result_cards_include_law_text_reading_area_contract():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert "formatLawTextSegments" in app_js
    assert "條文全文" in app_js
    assert "law-text-panel" in app_js
    assert ".law-text-panel" in styles
    assert "border-left" in styles
    assert "複製正式引用" in app_js
    assert "加入法源附件包" in app_js
    assert "引用詳情" in app_js


def test_citation_url_params_are_parsed_for_detail_route():
    result = run_app_js_expression(
        'parseCitationUrlParams("?article_id=art-1&q=%E5%87%BA%E5%8F%A3%E6%A8%99%E7%A4%BA%E7%87%88&from=improvement&item_id=exit-sign")'
    )

    assert result == {
        "article_id": "art-1",
        "q": "出口標示燈",
        "from": "improvement",
        "item_id": "exit-sign",
    }


def test_citation_context_mapping_uses_improvement_seed_without_applicability_claim():
    result = run_app_js_expression(
        """
        const payload = {
          items: [
            {
              item_id: "exit-sign-replacement",
              display_name: "出口標示燈更換 6 組",
              category: "消防燈類",
              reviewed_basis_candidates: [
                {
                  law_name: "各類場所消防安全設備設置標準",
                  article_no: "第 154 條",
                  candidate_query: "出口標示燈",
                  basis_reason: "標示燈基準相關",
                  basis_scope: "標示燈基準相關",
                },
              ],
            },
            {
              item_id: "direction-sign-replacement",
              display_name: "避難方向指示燈更換 4 組",
              category: "消防燈類",
              reviewed_basis_candidates: [
                {
                  law_name: "各類場所消防安全設備設置標準",
                  article_no: "第 154 條",
                  candidate_query: "避難方向指示燈",
                  basis_reason: "方向標示品項查核方向",
                  basis_scope: "標示燈基準相關",
                },
              ],
            },
          ],
        };
        state.citationContexts = buildCitationContextMap(payload);
        const contexts = getCitationContextsForArticle({
          law_name: "各類場所消防安全設備設置標準",
          article_no: "第 154 條",
        }, "direction-sign-replacement");
        ({
          count: contexts.length,
          first: contexts[0].display_title,
          visible: visibleCitationContexts(contexts, 1),
        });
        """
    )

    assert result["count"] == 2
    assert result["first"] == "避難方向指示燈更換"
    assert result["visible"]["hiddenCount"] == 1

    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "可人工對照情境" in app_js
    assert "不代表本案適用結論" in app_js


def test_law_text_segmenter_handles_numbered_chinese_enumeration():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "： 一、" in app_js
    assert "； 二、" in app_js
    assert "。 （一）" in app_js
    assert "； 1." in app_js


def test_law_text_segmenter_splits_realistic_fire_extinguisher_article():
    segments = run_law_text_segmenter(
        "滅火器應依下列規定設置： 一、視各類場所； 二、每一百平方公尺。 （一）供第十二條使用； 1.測試"
    )

    assert segments == [
        "滅火器應依下列規定設置：",
        "一、視各類場所；",
        "二、每一百平方公尺。",
        "（一）供第十二條使用；",
        "1.測試",
    ]


def test_law_text_segmenter_keeps_plain_article_as_single_segment():
    segments = run_law_text_segmenter("沒有列舉符號的條文仍應完整顯示。")

    assert segments == ["沒有列舉符號的條文仍應完整顯示。"]


def test_format_official_citation_includes_required_fields():
    citation = run_app_js_expression(
        "formatOfficialCitation(item)",
        {
            "item": {
                "law_name": "各類場所消防安全設備設置標準",
                "article_no": "第 31 條",
                "latest_amended_at": "2025-09-15",
                "effective_at": "",
                "source_url": "https://law.moj.gov.tw/example",
                "text": "滅火器應依下列規定設置。",
            }
        },
    )

    assert citation == (
        "各類場所消防安全設備設置標準 第 31 條\n"
        "最新修正日：2025-09-15\n"
        "生效日：未提供\n"
        "官方來源：https://law.moj.gov.tw/example\n\n"
        "條文全文：\n"
        "滅火器應依下列規定設置。"
    )


def test_citation_package_dedupes_and_formats_items():
    result = run_app_js_expression(
        """
        const first = {
          article_id: "art-1",
          law_name: "消防法",
          article_no: "第 9 條",
          latest_amended_at: "2025-01-01",
          effective_at: null,
          source_url: "https://law.moj.gov.tw/a",
          text: "管理權人應定期檢修。",
        };
        const second = {
          article_id: "art-2",
          law_name: "消防法施行細則",
          article_no: "第 3 條",
          latest_amended_at: "",
          effective_at: "2025-02-01",
          source_url: "https://law.moj.gov.tw/b",
          text: "防火管理事項。",
        };
        addCitationPackageItem(first);
        addCitationPackageItem(first);
        addCitationPackageItem(second);
        ({
          count: getCitationPackageItems().length,
          text: formatCitationPackage(),
        });
        """
    )

    assert result["count"] == 2
    assert result["text"].count("消防法 第 9 條") == 1
    assert "---" in result["text"]


def test_citation_package_formats_report_material_with_source_metadata():
    result = run_app_js_expression(
        """
        state.sourceMeta = {
          updated_at: "2026-07-25T03:22:00+00:00",
          license: { name: "政府資料開放授權條款-第1版" },
          sources: [
            {
              kind: "law",
              dataset_url: "https://data.gov.tw/dataset/18289",
              bytes: 1234,
              sha256: "abcdef1234567890",
            },
          ],
        };
        addCitationPackageItem({
          article_id: "art-1",
          law_name: "各類場所消防安全設備設置標準",
          article_no: "第 31 條",
          latest_amended_at: "2025-09-15",
          effective_at: "",
          source_url: "https://law.moj.gov.tw/a",
          text: "滅火器應依下列規定設置。",
        });
        ({
          report: formatCitationPackage("report"),
          markdown: formatCitationPackage("markdown"),
        });
        """
    )

    assert "消防法規法源附件" in result["report"]
    assert "資料更新時間：2026/07/25" in result["report"]
    assert "授權：政府資料開放授權條款-第1版" in result["report"]
    assert "law https://data.gov.tw/dataset/18289 / 1,234 bytes / SHA-256 abcdef123456" in result["report"]
    assert "條文全文：\n滅火器應依下列規定設置。" in result["report"]
    assert "# 消防法規法源附件" in result["markdown"]
    assert "## 1. 各類場所消防安全設備設置標準 第 31 條" in result["markdown"]
