from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
STATIC = PROJECT_ROOT / "src" / "firelaw_api" / "static"

BANNED_PREVIEW_PHRASES = {
    "保證合法",
    "一定合格",
    "自動判斷是否該更換",
    "判定違法",
    "價格合理",
    "AI 法律回答",
    "智慧合規平台",
    "提升企業效率",
    "Deficiency",
    "Proposal",
    "Code References",
    "正式 demo",
    "工作台",
    "改善依據反查",
    "法源引用",
    "候選官方依據",
}


def test_home_preview_html_contract():
    html = (STATIC / "home-preview.html").read_text(encoding="utf-8")

    assert html.count("<main") == 1
    assert html.count("</main>") == 1
    assert "<title>FireBasis</title>" in html
    assert "首頁預覽" not in html
    assert "消防公司營運流程" in html
    assert "消防公司作業" in html
    assert "先從排程與派工穩住" in html
    assert "場所、技師、定期檢查、改期與行程狀態" in html
    assert "不再把法源反查當成主產品" in html
    assert "排程派工" in html
    assert "狀態追蹤" in html
    assert 'id="preview-flow"' in html
    assert 'id="preview-boundary"' in html
    assert 'id="preview-trial"' not in html
    assert html.count('<section class="home-section') == 2
    assert '<section class="home-hero"' in html
    assert 'href="/schedule"' in html
    assert "開啟排程派工" in html
    assert "開發者文件" in html
    assert 'href="/improvement"' not in html
    assert 'href="/citation"' not in html
    assert 'href="/docs"' in html
    assert "/ 與 /improvement" not in html
    assert "Step 1" not in html
    assert "Step 5" not in html
    assert "建立場所" in html
    assert "建立週期" in html
    assert "指派技師" in html
    assert "處理改期" in html
    assert "追蹤狀態" in html
    assert "home-heading-line" in html

    for phrase in BANNED_PREVIEW_PHRASES:
        assert phrase not in html


def test_home_preview_motion_and_scoped_css_contract():
    html = (STATIC / "home-preview.html").read_text(encoding="utf-8")
    js = (STATIC / "home-preview.js").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert '<script src="/assets/home-preview.js" defer></script>' in html
    assert 'document.querySelector(".home-preview")' in js
    assert "if (!page) return" in js
    assert "IntersectionObserver" in js
    assert "prefers-reduced-motion: reduce" in js
    assert "is-visible" in js
    assert "is-active" in js
    assert "is-condensed" in js
    assert ".home-preview .reveal" in css
    assert ".home-preview.has-motion .reveal.is-visible" in css
    assert ".workflow-step.is-active" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "position: sticky" in css
    assert "rotate(-1.5deg)" not in css
