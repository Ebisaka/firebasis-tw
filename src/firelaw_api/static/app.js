const state = {
  laws: [],
  citationPackage: [],
  sourceMeta: null,
  changeMeta: null,
};

const els = {
  form: document.querySelector("#searchForm"),
  query: document.querySelector("#queryInput"),
  law: document.querySelector("#lawSelect"),
  chips: document.querySelector("#queryChips"),
  assist: document.querySelector("#assistLine"),
  results: document.querySelector("#results"),
  status: document.querySelector("#statusLine"),
  serviceStatus: document.querySelector("#serviceStatus"),
  corpusCount: document.querySelector("#corpusCount"),
  updatedAt: document.querySelector("#updatedAt"),
  licenseLink: document.querySelector("#licenseLink"),
  versionSummary: document.querySelector("#versionSummary"),
  sourceList: document.querySelector("#sourceList"),
  changesSummary: document.querySelector("#changesSummary"),
  changesList: document.querySelector("#changesList"),
  citationPackageCount: document.querySelector("#citationPackageCount"),
  citationPackageList: document.querySelector("#citationPackageList"),
  packageFormat: document.querySelector("#packageFormat"),
  copyPackageButton: document.querySelector("#copyPackageButton"),
  clearPackageButton: document.querySelector("#clearPackageButton"),
  copyFallback: document.querySelector("#copyFallback"),
  copyFallbackText: document.querySelector("#copyFallbackText"),
};

function setStatus(message, kind = "") {
  els.status.textContent = message;
  els.status.className = kind ? `status-line ${kind}` : "status-line";
}

function setAssist(message) {
  if (!message) {
    els.assist.hidden = true;
    els.assist.textContent = "";
    return;
  }
  els.assist.hidden = false;
  els.assist.textContent = message;
}

function formatDate(value) {
  if (!value) return "未提供";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function text(value) {
  return value === null || value === undefined || value === "" ? "未提供" : String(value);
}

function formatOfficialCitation(item) {
  return [
    `${text(item.law_name)} ${text(item.article_no)}`,
    `最新修正日：${text(item.latest_amended_at)}`,
    `生效日：${text(item.effective_at)}`,
    `官方來源：${text(item.source_url)}`,
    "",
    "條文全文：",
    text(item.text),
  ].join("\n");
}

function shortHash(value) {
  return value ? String(value).slice(0, 12) : "未提供";
}

function sourceMetadataLines(meta = state.sourceMeta) {
  const sources = meta?.sources || [];
  if (!sources.length) return ["未取得"];
  return sources.map((source) => {
    const bytes = Number(source.bytes || 0).toLocaleString("zh-TW");
    return `${text(source.kind)} ${text(source.dataset_url)} / ${bytes} bytes / SHA-256 ${shortHash(source.sha256)}`;
  });
}

function formatReportCitationPackage(meta = state.sourceMeta) {
  const lines = [
    "消防法規報告素材包",
    `產生時間：${formatDate(new Date().toISOString())}`,
    `資料更新時間：${formatDate(meta?.updated_at)}`,
    `授權：${text(meta?.license?.name)}`,
    "資料來源：",
    ...sourceMetadataLines(meta).map((line) => `- ${line}`),
    "",
    "引用條文：",
  ];

  state.citationPackage.forEach((item, index) => {
    lines.push(
      `${index + 1}. ${text(item.law_name)} ${text(item.article_no)}`,
      `最新修正日：${text(item.latest_amended_at)}`,
      `生效日：${text(item.effective_at)}`,
      `官方來源：${text(item.source_url)}`,
      "",
      "條文全文：",
      text(item.text),
      "",
      "---",
    );
  });
  return lines.join("\n").replace(/\n---$/, "").trim();
}

function formatMarkdownCitationPackage(meta = state.sourceMeta) {
  const lines = [
    "# 消防法規引用包",
    "",
    `- 產生時間：${formatDate(new Date().toISOString())}`,
    `- 資料更新時間：${formatDate(meta?.updated_at)}`,
    `- 授權：${text(meta?.license?.name)}`,
    "- 資料來源：",
    ...sourceMetadataLines(meta).map((line) => `  - ${line}`),
    "",
  ];

  state.citationPackage.forEach((item, index) => {
    lines.push(
      `## ${index + 1}. ${text(item.law_name)} ${text(item.article_no)}`,
      "",
      `- 最新修正日：${text(item.latest_amended_at)}`,
      `- 生效日：${text(item.effective_at)}`,
      `- 官方來源：${text(item.source_url)}`,
      "",
      "### 條文全文",
      "",
      text(item.text),
      "",
    );
  });
  return lines.join("\n").trim();
}

function getCitationPackageItems() {
  return [...state.citationPackage];
}

function isInCitationPackage(articleId) {
  return state.citationPackage.some((item) => item.article_id === articleId);
}

function addCitationPackageItem(item) {
  if (!item || !item.article_id || isInCitationPackage(item.article_id)) {
    return false;
  }
  state.citationPackage.push({ ...item });
  return true;
}

function clearCitationPackage() {
  state.citationPackage = [];
}

function formatCitationPackage(format = "official") {
  if (format === "report") return formatReportCitationPackage();
  if (format === "markdown") return formatMarkdownCitationPackage();
  return state.citationPackage.map(formatOfficialCitation).join("\n\n---\n\n");
}

function setButtonFeedback(button, message, duration = 1400) {
  if (!button) return;
  const original = button.dataset.originalText || button.textContent;
  button.dataset.originalText = original;
  button.textContent = message;
  window.setTimeout(() => {
    button.textContent = original;
  }, duration);
}

function showCopyFallback(value) {
  if (!els.copyFallback || !els.copyFallbackText) return;
  els.copyFallback.hidden = false;
  els.copyFallbackText.value = value;
  els.copyFallbackText.focus();
  els.copyFallbackText.select();
}

async function copyText(value, button) {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      setButtonFeedback(button, "已複製");
      return true;
    }
  } catch (_error) {
    // Fall back to a selectable textarea below.
  }
  showCopyFallback(value);
  setButtonFeedback(button, "請手動複製");
  return false;
}

const LAW_TEXT_BREAK_EXAMPLES = ["： 一、", "； 二、", "。 （一）", "； 1."];
const LAW_TEXT_MARKER = "(?:[一二三四五六七八九十百]+、|（[一二三四五六七八九十百]+）|\\d+\\.)";
const LAW_TEXT_MARKER_AFTER_PUNCTUATION = new RegExp(`([：；。])\\s*(${LAW_TEXT_MARKER})`, "g");
const LAW_TEXT_INLINE_MARKER = new RegExp(`\\s+(${LAW_TEXT_MARKER})`, "g");

function formatLawTextSegments(value) {
  const rawText = text(value);
  if (rawText === "未提供") return [rawText];
  const segmented = rawText
    .replace(LAW_TEXT_MARKER_AFTER_PUNCTUATION, "$1\n$2")
    .replace(LAW_TEXT_INLINE_MARKER, "\n$1");
  const segments = segmented
    .split("\n")
    .map((segment) => segment.trim())
    .filter(Boolean);
  return segments.length ? segments : [rawText];
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadHealth() {
  try {
    const health = await fetchJson("/health");
    if (health.status === "ok") {
      els.serviceStatus.textContent = "正常";
      if (health.law_count && health.article_count) {
        els.corpusCount.textContent = `${health.law_count} 部法規 / ${health.article_count} 條條文`;
      }
      return;
    }
    els.serviceStatus.textContent = "資料庫未就緒";
    setStatus(health.reason || "資料庫未就緒，請先執行 update。", "warning");
  } catch (error) {
    els.serviceStatus.textContent = "無法連線";
    setStatus(error.message, "error");
  }
}

async function loadSources() {
  try {
    const meta = await fetchJson("/meta/sources");
    state.sourceMeta = meta;
    if (meta.corpus) {
      els.corpusCount.textContent = `${meta.corpus.law_count} 部法規 / ${meta.corpus.article_count} 條條文`;
    }
    els.updatedAt.textContent = formatDate(meta.updated_at);
    if (meta.license) {
      els.licenseLink.textContent = meta.license.name || "政府資料開放授權條款第 1 版";
      els.licenseLink.href = meta.license.url || "https://data.gov.tw/license";
    }
    renderSourceVersion(meta);
  } catch (error) {
    els.updatedAt.textContent = "未取得";
    if (els.versionSummary) els.versionSummary.textContent = "資料版本未取得";
    setStatus(`資料來源資訊未取得：${error.message}`, "warning");
  }
}

async function loadChanges() {
  try {
    const changes = await fetchJson("/meta/changes?limit=100");
    state.changeMeta = changes;
    renderChanges(changes);
  } catch (error) {
    state.changeMeta = null;
    renderChangesUnavailable(`變更資料未取得：${error.message}`);
  }
}

function renderSourceVersion(meta) {
  if (!els.versionSummary || !els.sourceList) return;
  const corpus = meta.corpus
    ? `${meta.corpus.law_count} 部法規 / ${meta.corpus.article_count} 條條文`
    : "語料數未提供";
  els.versionSummary.textContent = `${formatDate(meta.updated_at)}，${corpus}`;
  els.sourceList.replaceChildren();

  for (const source of meta.sources || []) {
    const item = document.createElement("div");
    item.className = "source-item";

    const title = document.createElement("a");
    title.href = source.dataset_url;
    title.target = "_blank";
    title.rel = "noreferrer";
    title.textContent = `${source.kind} dataset`;

    const detail = document.createElement("span");
    const hash = source.sha256 ? source.sha256.slice(0, 12) : "未提供";
    detail.textContent = `${Number(source.bytes || 0).toLocaleString("zh-TW")} bytes / SHA-256 ${hash}`;

    item.append(title, detail);
    els.sourceList.append(item);
  }
}

function renderChanges(payload) {
  if (!els.changesSummary || !els.changesList) return;
  const counts = payload.counts || {};
  if (payload.status === "baseline_created") {
    els.changesSummary.textContent = "已建立基準，尚無前次差異";
  } else if (payload.status === "unavailable") {
    els.changesSummary.textContent = payload.run?.unavailable_reason ? "差異比對未取得" : "尚無差異資料";
  } else {
    els.changesSummary.textContent =
      `新增 ${changeTotal(counts, "added")} / 修改 ${changeTotal(counts, "modified")} / 刪除 ${changeTotal(counts, "removed")}`;
  }

  els.changesList.replaceChildren();
  const changes = payload.changes || [];
  if (!changes.length) {
    const empty = document.createElement("li");
    empty.textContent = payload.status === "available" ? "本次無新增、修改或刪除。" : els.changesSummary.textContent;
    els.changesList.append(empty);
    return;
  }

  for (const item of changes) {
    const row = document.createElement("li");
    row.textContent = `${changeTypeLabel(item.change_type)}：${text(item.law_name)}${item.article_no ? ` ${item.article_no}` : ""}`;
    els.changesList.append(row);
  }
}

function renderChangesUnavailable(message) {
  if (!els.changesSummary || !els.changesList) return;
  els.changesSummary.textContent = message;
  els.changesList.replaceChildren();
  const item = document.createElement("li");
  item.textContent = message;
  els.changesList.append(item);
}

function changeTotal(counts, suffix) {
  return Number(counts[`law_${suffix}`] || 0) + Number(counts[`article_${suffix}`] || 0);
}

function changeTypeLabel(changeType) {
  return (
    {
      law_added: "新增法規",
      law_removed: "移除法規",
      law_modified: "法規資料修改",
      article_added: "新增條文",
      article_removed: "移除條文",
      article_modified: "條文修改",
    }[changeType] || changeType
  );
}

async function loadLaws() {
  try {
    state.laws = await fetchJson("/laws");
    for (const law of state.laws) {
      const option = document.createElement("option");
      option.value = law.law_id;
      option.textContent = `${law.name} (${law.article_count})`;
      els.law.append(option);
    }
  } catch (error) {
    els.law.disabled = true;
    setStatus(`法規清單未取得：${error.message}`, "warning");
  }
}

function resultNode(item) {
  const article = document.createElement("article");
  article.className = "result";

  const header = document.createElement("div");
  header.className = "result-header";

  const citation = document.createElement("div");
  citation.className = "citation";

  const lawName = document.createElement("span");
  lawName.className = "law-name";
  lawName.textContent = item.law_name;

  const articleNo = document.createElement("span");
  articleNo.className = "article-no";
  articleNo.textContent = item.article_no;

  citation.append(lawName, articleNo);

  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `分數 ${Number(item.score || 0).toFixed(2)}`;

  header.append(citation, score);

  const actions = document.createElement("div");
  actions.className = "result-actions";

  const copyCitation = document.createElement("button");
  copyCitation.type = "button";
  copyCitation.className = "primary-inline-action";
  copyCitation.textContent = "複製正式引用";
  copyCitation.addEventListener("click", () => copyText(formatOfficialCitation(item), copyCitation));

  const addToPackage = document.createElement("button");
  addToPackage.type = "button";
  addToPackage.className = "secondary-action";
  addToPackage.textContent = isInCitationPackage(item.article_id) ? "已在引用包" : "加入引用包";
  addToPackage.disabled = isInCitationPackage(item.article_id);
  addToPackage.addEventListener("click", () => {
    const added = addCitationPackageItem(item);
    renderCitationPackage();
    addToPackage.textContent = added ? "已加入" : "已在引用包";
    addToPackage.disabled = true;
  });

  actions.append(copyCitation, addToPackage);

  const snippet = document.createElement("p");
  snippet.className = "snippet";
  snippet.textContent = item.snippet || "";

  const lawTextPanel = document.createElement("section");
  lawTextPanel.className = "law-text-panel";
  lawTextPanel.setAttribute("aria-label", "條文全文");

  const lawTextLabel = document.createElement("div");
  lawTextLabel.className = "law-text-label";
  lawTextLabel.textContent = "條文全文";

  const lawText = document.createElement("div");
  lawText.className = "full-text";
  lawText.append(
    ...formatLawTextSegments(item.text).map((segment) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = segment;
      return paragraph;
    }),
  );

  lawTextPanel.append(lawTextLabel, lawText);

  const meta = document.createElement("div");
  meta.className = "meta-row";

  const amended = document.createElement("span");
  amended.textContent = `最新修正日：${text(item.latest_amended_at)}`;

  const effective = document.createElement("span");
  effective.textContent = `生效日：${text(item.effective_at)}`;

  const source = document.createElement("a");
  source.href = item.source_url;
  source.target = "_blank";
  source.rel = "noreferrer";
  source.textContent = "官方來源";

  meta.append(amended, effective, source);
  article.append(header, actions, snippet, lawTextPanel, meta);
  return article;
}

function suggestionButton(query) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "suggestion";
  button.textContent = query;
  button.addEventListener("click", () => submitQuery(query));
  return button;
}

function renderResults(results, suggestions = []) {
  els.results.replaceChildren();
  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    const message = document.createElement("p");
    message.textContent = "查無符合條文";
    empty.append(message);
    if (suggestions.length) {
      const actions = document.createElement("div");
      actions.className = "empty-actions";
      actions.append(...suggestions.map(suggestionButton));
      empty.append(actions);
    }
    els.results.append(empty);
    return;
  }
  els.results.append(...results.map(resultNode));
}

function renderCitationPackage() {
  if (!els.citationPackageCount || !els.citationPackageList) return;
  const items = getCitationPackageItems();
  els.citationPackageCount.textContent = `${items.length} 筆引用`;
  els.citationPackageList.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "citation-package-empty";
    empty.textContent = "尚未加入引用。搜尋條文後可把官方引用加入這裡，再一次複製。";
    els.citationPackageList.append(empty);
  } else {
    for (const item of items) {
      const row = document.createElement("li");
      row.textContent = `${item.law_name} ${item.article_no}`;
      els.citationPackageList.append(row);
    }
  }

  if (els.copyPackageButton) els.copyPackageButton.disabled = !items.length;
  if (els.clearPackageButton) els.clearPackageButton.disabled = !items.length;
}

function renderAssist(payload) {
  const terms = payload.expanded_terms || [];
  if (!terms.length) {
    setAssist("");
    return;
  }
  setAssist(`已協助搜尋：${terms.join("、")}`);
}

function submitQuery(query) {
  els.query.value = query;
  els.form.requestSubmit();
}

async function search(event) {
  event.preventDefault();
  setAssist("");
  const query = els.query.value.trim();
  if (!query) {
    setStatus("請輸入關鍵字", "warning");
    els.query.focus();
    return;
  }

  const button = els.form.querySelector("button");
  button.disabled = true;
  setStatus("查詢中");
  els.results.replaceChildren();

  try {
    const params = new URLSearchParams({ q: query, limit: "20" });
    if (els.law.value) params.set("law_id", els.law.value);
    const payload = await fetchJson(`/search/assist?${params.toString()}`);
    renderAssist(payload);
    renderResults(payload.results || [], payload.suggestions || []);
    setStatus(`「${payload.query}」找到 ${(payload.results || []).length} 筆引用`);
  } catch (error) {
    setStatus(`查詢失敗：${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
}

async function init() {
  els.form.addEventListener("submit", search);
  els.chips.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-query]");
    if (!button) return;
    submitQuery(button.dataset.query);
  });
  els.copyPackageButton?.addEventListener("click", () => {
    copyText(formatCitationPackage(els.packageFormat?.value || "official"), els.copyPackageButton);
  });
  els.clearPackageButton?.addEventListener("click", () => {
    clearCitationPackage();
    renderCitationPackage();
    setStatus("引用包已清空");
  });
  renderCitationPackage();
  await Promise.all([loadHealth(), loadSources(), loadChanges(), loadLaws()]);
}

init();
