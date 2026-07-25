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
  "smoke-home-preview",
);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function verifyHomePreview(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });

  await page.getByRole("heading", { name: /報價前，先把\s*消防缺失說清楚/ }).waitFor({
    state: "visible",
  });
  assert(await page.getByRole("link", { name: /開啟改善依據反查/ }).isVisible(), "Primary improvement CTA should be visible");
  assert(await page.locator(".home-workflow-hero").isVisible(), "Hero workflow diagram should be visible");
  assert(await page.locator(".home-preview-header").isVisible(), "Sticky preview header should be visible");

  const h1Top = await page.locator("h1").evaluate((node) => node.getBoundingClientRect().top);
  assert(h1Top >= 0 && h1Top < viewport.height, "Hero title should appear in the first viewport");

  await page.locator('[data-step="basis"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  const activeStep = await page.locator(".workflow-step.is-active").textContent();
  assert(activeStep && activeStep.includes("對照依據"), `Expected basis workflow step to be active, got ${activeStep}`);

  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  assert(!hasOverflow, `Horizontal overflow at ${viewport.width}px`);

  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  await page.waitForTimeout(120);

  fs.mkdirSync(screenshotDir, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotDir, viewport.width <= 390 ? "mobile-390.png" : "desktop.png"),
    fullPage: false,
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
    await verifyHomePreview(page, { width: 1366, height: 900 });
    await verifyHomePreview(page, { width: 390, height: 844 });
    assert(consoleErrors.length === 0, `Console errors found:\n${consoleErrors.join("\n")}`);
  } finally {
    await browser.close();
  }
  console.log("home preview smoke passed");
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
