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
}


def test_home_preview_html_contract():
    html = (STATIC / "home-preview.html").read_text(encoding="utf-8")

    assert html.count("<main") == 1
    assert html.count("</main>") == 1
    assert "<title>FireBasis</title>" in html
    assert "首頁預覽" not in html
    assert "消防公司 / 檢修人員 / 報價前溝通" in html
    assert "消防改善依據說明" in html
    assert "報價前，先把" in html
    assert "消防缺失說清楚" in html
    assert "給消防公司與檢修人員使用" in html
    assert "把缺失原因、現場確認點與候選官方依據" in html
    assert "報價前可溝通的素材" in html
    assert "只提供候選依據與溝通素材；不作法律、檢修或價格判斷" in html
    assert "依據素材預覽" in html
    assert "缺失品項" in html
    assert "保守說明" in html
    assert "現場確認點" in html
    assert "候選官方依據" in html
    assert "報價前溝通素材" in html
    assert 'id="preview-flow"' in html
    assert 'id="preview-boundary"' in html
    assert 'id="preview-trial"' in html
    assert html.count('<section class="home-section') == 4
    assert '<section class="home-hero"' in html
    assert 'href="/improvement"' in html
    assert "開啟改善依據反查" in html
    assert "進入改善依據反查" in html
    assert 'href="/citation"' not in html
    assert 'href="/docs"' not in html
    assert "/ 與 /improvement" not in html
    assert "Step 1" not in html
    assert "Step 5" not in html
    assert "先看品項" in html
    assert "收斂說法" in html
    assert "確認現場" in html
    assert "對照依據" in html
    assert "整理素材" in html
    assert "home-heading-line" in html
    assert "home-phrase" in html

    for phrase in BANNED_PREVIEW_PHRASES:
        assert phrase not in html


def test_home_preview_does_not_appear_in_existing_demo_navigation():
    improvement_html = (STATIC / "improvement.html").read_text(encoding="utf-8")
    citation_html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "/home-preview" not in improvement_html
    assert "/home-preview" not in citation_html


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
