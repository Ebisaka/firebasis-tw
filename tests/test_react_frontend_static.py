import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
FRONTEND = PROJECT_ROOT / "frontend"
STATIC_REACT = PROJECT_ROOT / "src" / "firelaw_api" / "static" / "react"


def test_react_frontend_uses_heroui_tailwind_and_product_language():
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    main = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

    assert "@heroui/react" in package["dependencies"]
    assert "@heroui/styles" in package["dependencies"]
    assert "lucide-react" in package["dependencies"]
    assert "tailwindcss" in package["dependencies"]
    assert 'from "@heroui/react"' in main
    assert 'from "lucide-react"' in main
    assert '@import "tailwindcss";' in styles
    assert '@import "@heroui/styles";' in styles
    assert "--fb-primary: #fece14" in styles
    assert "--fb-secondary: #000000" in styles
    assert "--fb-text: #111827" in styles
    assert "工作台" not in main
    assert "linear-gradient" not in main
    assert "gradient" not in main.lower()
    assert "render={(props) => <a" not in main


def test_react_home_keeps_long_scroll_product_story():
    main = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")

    assert "消防公司排程派工與檢查工單追蹤" in main
    assert "新的主流程以排程派工為核心" in main
    assert "場所與客戶" in main
    assert "技師派工" in main
    assert "定期檢查" in main
    assert "狀態追蹤" in main
    assert "href=\"/schedule\"" in main
    assert "API 保留為可信資料層" in main


def test_react_click_regressions_have_navigation_links_and_copy_feedback():
    main = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")

    assert 'href="/schedule"' in main
    assert 'href="/docs"' in main
    assert 'href="/improvement"' not in main
    assert 'href="/citation"' not in main
    assert "copyOfficialCitation" not in main
    assert "已建立場所" in main
    assert "已更新派工" in main


def test_react_schedule_keeps_minimal_clickable_operations():
    main = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")

    assert "排程與派工板" in main
    assert "地點與派工概覽" in main
    assert "狀態紀錄" in main
    assert "改期紀錄" in main
    assert "待派工" in main
    assert "檢查行程" in main
    assert "檢查工單" in main
    assert "指派選取檢查" in main
    assert "套用改期" in main
    assert "function groupVisitsByDate" in main
    assert "function statusLabel" in main
    assert 'api.post("/schedule/sites"' in main
    assert 'api.post("/schedule/technicians"' in main
    assert 'api.post("/schedule/series"' in main
    assert 'api.get("/schedule/sites")' in main
    assert 'api.get("/schedule/technicians")' in main
    assert 'api.get("/schedule/series")' in main
    assert "/schedule/visits/${visitId}/status-events" in main
    assert "/schedule/visits/${visitId}/reschedule-events" in main
    assert "/schedule/dispatch-board" in main
    assert "/schedule/map" in main


def test_react_build_is_packaged_as_static_shell():
    index = STATIC_REACT / "index.html"
    assets = STATIC_REACT / "assets"

    assert index.exists()
    assert 'id="root"' in index.read_text(encoding="utf-8")
    assert any(path.suffix == ".js" for path in assets.iterdir())
    assert any(path.suffix == ".css" for path in assets.iterdir())
