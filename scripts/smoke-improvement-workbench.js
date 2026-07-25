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

  assert(await page.locator("#copyConservativeButton").isVisible(), "Missing primary conservative copy button");
  assert(await page.locator("#copyFormatMenuButton").isVisible(), "Missing format menu button");
  assert(!(await page.locator("#fullBasisDetails").evaluate((node) => node.open)), "Full basis details should start collapsed");
  assert(!(await page.locator("#siteCheckDetails").evaluate((node) => node.open)), "Site check details should start collapsed");
  assert(!(await page.locator("#calibrationDetails").evaluate((node) => node.open)), "Review notes should start collapsed");
  await page.click("#copyFormatMenuButton");
  const menuClipped = await page.locator("#copyFormatMenu").evaluate((menu) => {
    const menuBox = menu.getBoundingClientRect();
    const panelBox = menu.closest(".improvement-case-panel").getBoundingClientRect();
    return menuBox.bottom > panelBox.bottom && getComputedStyle(menu.closest(".improvement-case-panel")).overflow !== "visible";
  });
  assert(!menuClipped, "Format menu is clipped by the case panel");
  await page.click("#copyFormatMenuButton");
  if (viewport.width >= 960) {
    const sideHeightRatio = await page.evaluate(() => {
      const left = document.querySelector(".improvement-list-panel").getBoundingClientRect().height;
      const right = document.querySelector(".evidence-panel").getBoundingClientRect().height;
      return left / right;
    });
    assert(sideHeightRatio < 1.4, `Left queue is visually too tall compared with evidence panel (${sideHeightRatio.toFixed(2)}x)`);
  }

  await page.getByText("差動探測器更換", { exact: false }).first().click();
  await page.locator("#primaryBasis").getByText("各類場所消防安全設備設置標準 第 114 條").waitFor({
    state: "visible",
    timeout: 10000,
  });

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
