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
  "smoke-improvement-workbench",
);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function verifyImprovementDemo(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseUrl}/improvement`, { waitUntil: "networkidle" });
  await page.locator("#copyConservativeButton").waitFor({ state: "visible" });

  assert(await page.locator(".improvement-task-flow").isVisible(), "Missing long-scroll task flow");
  assert(await page.locator(".item-switcher").isVisible(), "Missing compact item switcher");
  assert(await page.locator("#selectedQuestion").isVisible(), "Missing owner question");
  assert(await page.locator("#customerExplanation").isVisible(), "Missing conservative explanation");
  assert(await page.locator("#copyConservativeButton").isVisible(), "Missing primary conservative copy button");
  assert(await page.locator("#copyFormatMenuButton").isVisible(), "Missing format menu button");
  assert(!(await page.locator("#fullBasisDetails").evaluate((node) => node.open)), "Full basis details should start collapsed");
  assert(!(await page.locator("#calibrationDetails").evaluate((node) => node.open)), "Review notes should start collapsed");

  const firstViewportReady = await page.evaluate(() => {
    return ["#selectedTitle", "#selectedQuestion", "#customerExplanation", "#copyConservativeButton"].every((selector) => {
      const element = document.querySelector(selector);
      if (!element) return false;
      const rect = element.getBoundingClientRect();
      return rect.top < window.innerHeight && rect.bottom > 0;
    });
  });
  assert(firstViewportReady, "First viewport should show selected item, question, explanation, and copy action");

  await page.click("#copyFormatMenuButton");
  const menuClipped = await page.locator("#copyFormatMenu").evaluate((menu) => {
    const menuBox = menu.getBoundingClientRect();
    let node = menu.parentElement;
    while (node && node !== document.body) {
      const style = getComputedStyle(node);
      const clips = /(hidden|auto|scroll|clip)/.test(`${style.overflow} ${style.overflowX} ${style.overflowY}`);
      if (clips) {
        const box = node.getBoundingClientRect();
        if (menuBox.left < box.left - 1 || menuBox.right > box.right + 1 || menuBox.bottom > box.bottom + 1) {
          return true;
        }
      }
      node = node.parentElement;
    }
    return false;
  });
  assert(!menuClipped, "Format menu is clipped by an ancestor container");
  await page.click("#copyFormatMenuButton");

  await page.click("#copyConservativeButton");
  await page.waitForFunction(() => document.querySelector("#copyConservativeButton")?.textContent.includes("已複製"));

  await page.locator(".item-switcher-menu summary").click();
  await page.getByText("差動探測器更換", { exact: false }).first().click();
  await page.locator("#primaryBasis").getByText("各類場所消防安全設備設置標準 第 114 條").waitFor({
    state: "visible",
    timeout: 10000,
  });
  const citationLink = page.locator("#primaryBasis").getByRole("link", { name: "查看引用頁" });
  await citationLink.waitFor({ state: "visible", timeout: 10000 });
  const citationHref = await citationLink.getAttribute("href");
  assert(citationHref && citationHref.includes("/citation?article_id="), "Primary basis action should link to citation detail");
  assert(citationHref.includes("from=improvement"), "Citation detail link should preserve improvement origin");
  assert(await page.locator("#primaryBasis").getByRole("link", { name: "官方來源" }).isVisible(), "Official source should remain visible as secondary action");
  await page.click("#copyFormatMenuButton");
  await page.click("#copyLineMenuItem");
  await page.waitForFunction(() => document.querySelector("#copyFormatMenuButton")?.textContent.includes("已複製 LINE 簡版"));
  const copiedText = await page.evaluate(() => window.__lastClipboardText || "");
  assert(copiedText.includes("差動探測器更換"), "Line copy should write selected item text to clipboard");
  await page.waitForTimeout(1500);

  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  assert(!hasOverflow, `Horizontal overflow at ${viewport.width}px`);

  fs.mkdirSync(screenshotDir, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotDir, viewport.width <= 390 ? "mobile-390.png" : "desktop.png"),
    fullPage: true,
  });
}

(async () => {
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
    await verifyImprovementDemo(page, { width: 1366, height: 900 });
    await verifyImprovementDemo(page, { width: 390, height: 844 });
    assert(consoleErrors.length === 0, `Console errors found:\n${consoleErrors.join("\n")}`);
  } finally {
    await browser.close();
  }
  console.log("improvement demo smoke passed");
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
