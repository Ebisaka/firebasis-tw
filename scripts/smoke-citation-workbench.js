#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const os = require("os");
const Module = require("module");

const bundledNodeModules = path.join(
  os.homedir(),
  ".cache",
  "codex-runtimes",
  "codex-primary-runtime",
  "dependencies",
  "node",
  "node_modules",
);

if (fs.existsSync(bundledNodeModules)) {
  process.env.NODE_PATH = [process.env.NODE_PATH, bundledNodeModules].filter(Boolean).join(path.delimiter);
  Module._initPaths();
}

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error("Playwright is required for this smoke check.");
  console.error("Use the Codex bundled runtime or install Playwright in a dev environment.");
  console.error(error.message);
  process.exit(2);
}

const baseUrl = (process.env.FIRELAW_SMOKE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const screenshotDir = process.env.FIRELAW_SMOKE_SCREENSHOT_DIR || path.join(
  process.cwd(),
  "outputs",
  "smoke-citation-workbench",
);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function discoverArticleId() {
  const response = await fetch(`${baseUrl}/search/assist?q=${encodeURIComponent("出口標示燈")}&limit=10`);
  assert(response.ok, `Could not discover article_id: HTTP ${response.status}`);
  const payload = await response.json();
  const result = (payload.results || []).find((item) => item.article_id);
  assert(result?.article_id, "No article_id discovered from search/assist");
  return result.article_id;
}

async function verifyCitationPage(page, viewport, articleId) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseUrl}/citation`, { waitUntil: "networkidle" });
  const improvementHref = await page.getByRole("link", { name: "改善依據反查" }).getAttribute("href");
  assert(improvementHref === "/improvement", "Citation top navigation should link to /improvement");
  await page.locator("#queryInput").fill("出口標示燈");
  await page.locator("#searchForm button[type='submit']").click();
  await page.getByText("複製正式引用").first().waitFor({ state: "visible", timeout: 10000 });
  await page.getByText("加入法源附件包").first().click();
  await page.getByText("1 筆條文").waitFor({ state: "visible", timeout: 10000 });
  await page.locator("#packageFormat").selectOption("report");
  await page.locator("#copyPackageButton").click();
  await page.waitForFunction(() => (window.__lastClipboardText || "").includes("消防法規法源附件"));

  await page.goto(
    `${baseUrl}/citation?article_id=${encodeURIComponent(articleId)}&q=${encodeURIComponent("出口標示燈")}&from=improvement&item_id=exit-sign-replacement`,
    { waitUntil: "networkidle" },
  );
  await page.getByText("引用詳情").first().waitFor({ state: "visible", timeout: 10000 });
  await page.getByText("可人工對照情境").waitFor({ state: "visible", timeout: 10000 });
  await page.getByText("不代表本案適用結論").waitFor({ state: "visible", timeout: 10000 });

  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  assert(!hasOverflow, `Horizontal overflow at ${viewport.width}px`);

  fs.mkdirSync(screenshotDir, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotDir, viewport.width <= 390 ? "mobile-390.png" : "desktop.png"),
    fullPage: true,
  });
}

(async () => {
  const articleId = await discoverArticleId();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text) => {
          window.__lastClipboardText = text;
        },
      },
    });
  });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => {
    consoleErrors.push(error.message);
  });
  try {
    await verifyCitationPage(page, { width: 1366, height: 900 }, articleId);
    await verifyCitationPage(page, { width: 390, height: 844 }, articleId);
    assert(consoleErrors.length === 0, `Console errors found:\n${consoleErrors.join("\n")}`);
  } finally {
    await browser.close();
  }
  console.log("citation workbench smoke passed");
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
