const BANNED_CONCLUSION_PHRASES = [
  "一定要換",
  "不換一定違法",
  "消防隊一定會開罰",
  "系統判定不合格",
];

const BANNED_REVIEW_PHRASES = [...BANNED_CONCLUSION_PHRASES, "違法", "必須更換", "保證合格"];

const ALLOWED_IMPROVEMENT_CATEGORIES = ["消防燈類", "火警探測器類"];
const TRUST_BOUNDARY_TEXT = "候選依據需人工確認；實際處理仍看現場狀態。";

const improvementState = {
  items: [],
  selectedItem: null,
  basisResults: [],
  basisCache: new Map(),
  basisRequestToken: 0,
  sourceMeta: null,
  dataVersion: "未提供",
};

const improvementEls = {
  items: document.querySelector("#improvementItems"),
  version: document.querySelector("#improvementVersion"),
  status: document.querySelector("#improvementStatus"),
  selectedCategory: document.querySelector("#selectedCategory"),
  selectedTitle: document.querySelector("#selectedTitle"),
  selectedOriginalText: document.querySelector("#selectedOriginalText"),
  selectedScenario: document.querySelector("#selectedScenario"),
  selectedQuestion: document.querySelector("#selectedQuestion"),
  caseStatusLine: document.querySelector("#caseStatusLine"),
  basisSummaryStatus: document.querySelector("#basisSummaryStatus"),
  sourceVersionLabel: document.querySelector("#sourceVersionLabel"),
  boundaryLabels: document.querySelector("#boundaryLabels"),
  customerExplanation: document.querySelector("#customerExplanation"),
  equipmentCandidates: document.querySelector("#equipmentCandidates"),
  defectCandidates: document.querySelector("#defectCandidates"),
  siteChecks: document.querySelector("#siteChecks"),
  basisStatus: document.querySelector("#basisStatus"),
  primaryBasis: document.querySelector("#primaryBasis"),
  fullBasisDetails: document.querySelector("#fullBasisDetails"),
  fullBasisSummary: document.querySelector("#fullBasisSummary"),
  basisList: document.querySelector("#basisList"),
  copyConservativeButton: document.querySelector("#copyConservativeButton"),
  copyFormatMenuButton: document.querySelector("#copyFormatMenuButton"),
  copyFormatMenu: document.querySelector("#copyFormatMenu"),
  copyLineMenuItem: document.querySelector("#copyLineMenuItem"),
  copyProposalMenuItem: document.querySelector("#copyProposalMenuItem"),
  copyCalibrationButton: document.querySelector("#copyCalibrationButton"),
  calibrationNote: document.querySelector("#calibrationNote"),
  calibrationSummary: document.querySelector("#calibrationSummary"),
  copyFallback: document.querySelector("#improvementCopyFallback"),
  copyFallbackText: document.querySelector("#improvementCopyFallbackText"),
};

function fallbackText(value, fallback = "未提供") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function safeArray(value) {
  return Array.isArray(value) ? value.filter((item) => fallbackText(item, "").trim()) : [];
}

function sanitizeForCopy(value) {
  let output = fallbackText(value, "");
  const replacements = [
    ["一定要換", "是否需要處理"],
    ["不換一定違法", "未處理可能涉及風險，仍需人工確認"],
    ["消防隊一定會開罰", "需依主管機關查核結果確認"],
    ["系統判定不合格", "需人工判讀結果"],
    ["必須更換", "需確認處理方式"],
    ["保證合格", "合格與否需依檢修結果確認"],
    ["違法", "法規風險"],
  ];
  replacements.forEach(([phrase, replacement]) => {
    output = output.split(phrase).join(replacement);
  });
  return output;
}

function formatDisplayDate(value) {
  if (!value) return "未取得";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function displayItemTitle(value) {
  const raw = fallbackText(value, "未命名改善品項").trim();
  const stripped = raw.replace(/\s+\d+\s*(組|盞|顆|只|具|支|台|個|片|處|座|套)\s*$/u, "").trim();
  return stripped || raw;
}

function formatSeedVersionForDisplay(value) {
  const raw = fallbackText(value, "未提供");
  const matchedDate = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (!matchedDate) return raw;
  return `${matchedDate[1]}/${matchedDate[2]}/${matchedDate[3]}`;
}

function isNonEmptyArray(value) {
  return Array.isArray(value) && value.length > 0;
}

function containsBannedPhrase(value, bannedPhrases = BANNED_CONCLUSION_PHRASES) {
  const candidate = fallbackText(value, "");
  return bannedPhrases.some((phrase) => candidate.includes(phrase));
}

function validateImprovementData(payload) {
  const errors = [];
  const items = Array.isArray(payload?.items) ? payload.items : [];

  if (!payload || typeof payload !== "object") {
    errors.push("payload must be an object");
  }
  if (!fallbackText(payload?.version, "")) {
    errors.push("version is required");
  }
  if (items.length !== 10) {
    errors.push("items must contain exactly 10 entries");
  }

  items.forEach((item, index) => {
    const prefix = `items[${index}]`;
    if (!fallbackText(item.item_id, "")) errors.push(`${prefix}.item_id is required`);
    if (!fallbackText(item.display_name, "")) errors.push(`${prefix}.display_name is required`);
    if (!fallbackText(item.scenario, "")) errors.push(`${prefix}.scenario is required`);
    if (!fallbackText(item.customer_question, "")) errors.push(`${prefix}.customer_question is required`);
    if (!ALLOWED_IMPROVEMENT_CATEGORIES.includes(item.category)) {
      errors.push(`${prefix}.category must be 消防燈類 or 火警探測器類`);
    }

    [
      "field_terms",
      "equipment_candidates",
      "defect_candidates",
      "required_site_checks",
      "candidate_queries",
      "reviewed_basis_candidates",
      "customer_explanation_lines",
      "boundary_labels",
      "avoid_phrases",
    ].forEach((field) => {
      if (!isNonEmptyArray(item[field])) errors.push(`${prefix}.${field} must be a non-empty array`);
    });

    ["customer_name", "company_name", "address", "phone", "email", "reviewer_name"].forEach((field) => {
      if (Object.prototype.hasOwnProperty.call(item, field)) {
        errors.push(`${prefix}.${field} identity field is not allowed`);
      }
    });
    if (Object.prototype.hasOwnProperty.call(item, "price")) {
      errors.push(`${prefix}.price is not allowed`);
    }

    (item.customer_explanation_lines || []).forEach((line) => {
      if (containsBannedPhrase(line)) {
        errors.push(`${prefix}.customer_explanation_lines contains banned phrase`);
      }
    });

    const candidateQueries = Array.isArray(item.candidate_queries) ? item.candidate_queries : [];
    (item.reviewed_basis_candidates || []).forEach((basis, basisIndex) => {
      const basisPrefix = `${prefix}.reviewed_basis_candidates[${basisIndex}]`;
      [
        "law_name",
        "article_no",
        "candidate_query",
        "basis_reason",
        "basis_scope",
        "review_status",
      ].forEach((field) => {
        if (!fallbackText(basis?.[field], "")) errors.push(`${basisPrefix}.${field} is required`);
      });
      if (basis?.review_status !== "manual_seed") {
        errors.push(`${basisPrefix}.review_status must be manual_seed`);
      }
      if (basis?.candidate_query && !candidateQueries.includes(basis.candidate_query)) {
        errors.push(`${basisPrefix}.candidate_query must be listed in candidate_queries`);
      }
      if (containsBannedPhrase(basis?.basis_reason, BANNED_REVIEW_PHRASES)) {
        errors.push(`${basisPrefix}.basis_reason contains banned phrase`);
      }
    });
  });

  return { valid: errors.length === 0, errors };
}

function buildDeficiencyCaseViewModel(item = {}) {
  const displayName = fallbackText(item.display_name, "未命名改善品項");
  return {
    item_id: fallbackText(item.item_id, ""),
    display_name: displayName,
    display_title: displayItemTitle(displayName),
    category: fallbackText(item.category, "未分類"),
    scenario: fallbackText(item.scenario, "未提供使用情境，需人工補充。"),
    customer_question: fallbackText(item.customer_question, "未提供業主常見問題，需人工補充。"),
    field_terms: safeArray(item.field_terms),
    equipment_candidates: safeArray(item.equipment_candidates),
    defect_candidates: safeArray(item.defect_candidates),
    required_site_checks: safeArray(item.required_site_checks),
    candidate_queries: safeArray(item.candidate_queries),
    reviewed_basis_candidates: safeArray(item.reviewed_basis_candidates),
    customer_explanation_lines: safeArray(item.customer_explanation_lines),
    boundary_labels: safeArray(item.boundary_labels),
    avoid_phrases: safeArray(item.avoid_phrases),
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadImprovementData() {
  const payload = await fetchJson("/assets/improvement-data.json");
  const validation = validateImprovementData(payload);
  if (!validation.valid) {
    throw new Error(validation.errors.join("; "));
  }
  improvementState.items = payload.items;
  improvementState.dataVersion = payload.version;
  return payload;
}

function basisKey(lawName, articleNo) {
  return `${fallbackText(lawName, "").trim()}|${fallbackText(articleNo, "").trim()}`;
}

function buildReviewedBasisMap(reviewedCandidates = []) {
  const reviewed = new Map();
  (reviewedCandidates || []).forEach((candidate) => {
    const key = basisKey(candidate?.law_name, candidate?.article_no);
    if (key === "|") return;
    reviewed.set(key, { ...candidate, reviewed_basis_key: key });
  });
  return reviewed;
}

function annotateReviewedBasis(result, reviewedBasisMap = new Map()) {
  const key = basisKey(result?.law_name, result?.article_no);
  const reviewed = reviewedBasisMap.get(key);
  if (!reviewed) return { ...result, reviewed_basis_key: key };
  return {
    ...result,
    reviewed_basis: true,
    reviewed_basis_key: key,
    basis_reason: reviewed.basis_reason,
    basis_scope: reviewed.basis_scope,
    review_status: reviewed.review_status,
  };
}

function missingReviewedBasisCandidates(reviewedBasisMap = new Map(), results = []) {
  const resultKeys = new Set((results || []).map((result) => result.reviewed_basis_key || basisKey(result.law_name, result.article_no)));
  return Array.from(reviewedBasisMap.values()).filter((candidate) => !resultKeys.has(candidate.reviewed_basis_key));
}

function mergeBasisResults(searchPayloads, reviewedBasisMap = new Map()) {
  const seen = new Map();
  const merged = [];
  let sortIndex = 0;

  (searchPayloads || []).forEach((payload) => {
    const matchedQuery = fallbackText(payload?.query || payload?.matched_query, "");
    (payload?.results || []).forEach((result) => {
      if (!result?.article_id && !result?.law_name && !result?.article_no) return;
      const resultKey = result.article_id || basisKey(result.law_name, result.article_no);
      const annotated = annotateReviewedBasis({ ...result, matched_query: matchedQuery }, reviewedBasisMap);

      if (seen.has(resultKey)) {
        const existing = merged[seen.get(resultKey)];
        if (!existing.reviewed_basis && annotated.reviewed_basis) {
          merged[seen.get(resultKey)] = { ...annotated, _sort_index: existing._sort_index };
        }
        return;
      }

      seen.set(resultKey, merged.length);
      merged.push({ ...annotated, _sort_index: sortIndex });
      sortIndex += 1;
    });
  });

  return merged
    .sort((first, second) => {
      const reviewedDelta = Number(Boolean(second.reviewed_basis)) - Number(Boolean(first.reviewed_basis));
      return reviewedDelta || first._sort_index - second._sort_index;
    })
    .map(({ _sort_index: _sortIndex, ...item }) => item);
}

function formatBasisLine(result) {
  if (!result) return "- 未取得候選條文，需人工確認。";
  return `- ${fallbackText(result.law_name)} ${fallbackText(result.article_no)}`;
}

function primaryBasisResult(results = []) {
  return Array.isArray(results) && results.length ? results[0] : null;
}

function buildEvidenceViewModel(results = [], errors = [], warnings = []) {
  const safeResults = Array.isArray(results) ? results : [];
  const safeErrors = Array.isArray(errors) ? errors.filter(Boolean) : [];
  const safeWarnings = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
  const primaryBasis = primaryBasisResult(safeResults);
  const hasBasis = Boolean(primaryBasis);
  let statusText = "未取得候選依據，需人工確認";
  let statusKind = "warning";
  let summaryText = "待人工確認";

  if (safeErrors.length) {
    statusText = "資料庫未連線，仍可查看保守說明";
    statusKind = "warning";
    summaryText = "未取得";
  } else if (hasBasis) {
    statusText = "已取得候選依據";
    statusKind = "";
    summaryText = `候選 ${safeResults.length} 筆`;
  }

  return {
    primaryBasis,
    otherBasis: hasBasis ? safeResults.slice(1) : [],
    allBasis: safeResults,
    hasBasis,
    hasMoreBasis: safeResults.length > 1,
    statusText,
    statusKind,
    summaryText,
    trustBoundaryText: TRUST_BOUNDARY_TEXT,
    errors: safeErrors,
    warnings: safeWarnings,
  };
}

function formatConservativeExplanation(
  item,
  primaryBasis = null,
  sourceMeta = null,
  dataVersion = improvementState.dataVersion,
  hasMoreBasis = false,
) {
  const viewModel = buildDeficiencyCaseViewModel(item);
  const lines = [
    "改善品項：",
    sanitizeForCopy(viewModel.display_name),
    "",
    "業主常見問題：",
    sanitizeForCopy(viewModel.customer_question),
    "",
    "保守說明：",
  ];

  if (viewModel.customer_explanation_lines.length) {
    viewModel.customer_explanation_lines.forEach((line) => lines.push(`- ${sanitizeForCopy(line)}`));
  } else {
    lines.push("- 未提供，需人工補充。");
  }

  lines.push("", "主要候選官方依據：");
  if (primaryBasis) {
    lines.push(formatProposalBasisLine(primaryBasis));
  } else {
    lines.push("- 未取得候選條文，需人工確認。");
  }

  if (hasMoreBasis) {
    lines.push("", "另有其他候選依據，需人工確認。");
  }

  lines.push(
    "",
    "資料版本：",
    `官方資料更新時間：${fallbackText(sourceMeta?.updated_at, "未取得")}`,
    `Seed 版本：${fallbackText(dataVersion, "未提供")}`,
    "",
    "提醒：",
    "本說明僅供改善/報價前溝通使用，僅提供候選官方依據與保守說明，不構成法律意見、最終檢修判定或處理結論。",
  );

  return lines.map((line) => sanitizeForCopy(line)).join("\n").trim();
}

function formatLineExplanation(item, basisResults = [], sourceMeta = null) {
  const viewModel = buildDeficiencyCaseViewModel(item);
  const lines = [
    `關於「${viewModel.display_name}」：`,
    ...viewModel.customer_explanation_lines.map((line) => sanitizeForCopy(line)),
    "",
    "候選官方依據：",
  ];

  if (basisResults.length) {
    basisResults.slice(0, 5).forEach((result) => lines.push(formatBasisLine(result)));
  } else {
    lines.push("- 未取得候選條文，需人工確認。");
  }

  lines.push("", "需現場確認：");
  viewModel.required_site_checks.forEach((check) => lines.push(`- ${sanitizeForCopy(check)}`));
  lines.push("");
  lines.push(`資料更新時間：${fallbackText(sourceMeta?.updated_at, "未取得")}`);
  lines.push("以上僅提供候選官方依據與保守說明，不代表最終合格、不合格或必然需更換之判定。");
  return lines.join("\n").trim();
}

function formatProposalBasisLine(result) {
  if (!result) return "- 未取得候選條文，需人工確認。";
  const lines = [
    `- ${fallbackText(result.law_name)} ${fallbackText(result.article_no)}`,
    `  查核方向：${fallbackText(result.matched_query || result.candidate_query, "未提供")}`,
    `  依據範圍：${fallbackText(result.basis_scope, "未提供")}`,
    `  人工確認理由：${fallbackText(result.basis_reason, "未提供")}`,
    `  官方來源：${fallbackText(result.source_url, "未提供")}`,
  ];
  return lines.map((line) => sanitizeForCopy(line)).join("\n");
}

function formatProposalSupport(item, basisResults = [], sourceMeta = null, dataVersion = improvementState.dataVersion) {
  const viewModel = buildDeficiencyCaseViewModel(item);
  const lines = [
    "改善項目：",
    sanitizeForCopy(viewModel.display_name),
    "",
    "使用情境：",
    sanitizeForCopy(viewModel.scenario),
    "",
    "業主常見問題：",
    sanitizeForCopy(viewModel.customer_question),
    "",
    "保守說明：",
  ];

  if (viewModel.customer_explanation_lines.length) {
    viewModel.customer_explanation_lines.forEach((line) => lines.push(`- ${sanitizeForCopy(line)}`));
  } else {
    lines.push("- 未提供，需人工補充。");
  }

  lines.push("", "需現場確認：");
  if (viewModel.required_site_checks.length) {
    viewModel.required_site_checks.forEach((check) => lines.push(`- ${sanitizeForCopy(check)}`));
  } else {
    lines.push("- 未提供，需人工確認。");
  }

  lines.push("", "候選官方依據：");
  if (basisResults.length) {
    basisResults.slice(0, 5).forEach((result) => lines.push(formatProposalBasisLine(result)));
  } else {
    lines.push("- 未取得候選條文，需人工確認。");
  }

  lines.push(
    "",
    "資料版本：",
    `官方資料更新時間：${fallbackText(sourceMeta?.updated_at, "未取得")}`,
    `Seed 版本：${fallbackText(dataVersion, "未提供")}`,
    "",
    "提醒：",
    "本素材僅供改善/報價前溝通使用，僅提供候選官方依據與保守說明，不構成法律意見、最終檢修判定或必然需更換之結論。",
  );

  return lines.map((line) => sanitizeForCopy(line)).join("\n").trim();
}

function formatCalibrationSummary(item, selectedFlags = [], note = "") {
  const flags = Array.from(selectedFlags || []).filter(Boolean);
  const trimmedNote = fallbackText(note, "").trim();
  if (!flags.length && !trimmedNote) {
    return "尚未校閱。";
  }

  const lines = [];
  if (flags.length) {
    lines.push(`已標記：${flags.join("、")}。`);
  }
  if (trimmedNote) {
    lines.push(`備註：${trimmedNote}`);
  }
  return lines.join("\n");
}

function buildCalibrationExport(
  item,
  selectedFlags = [],
  note = "",
  basisResults = [],
  sourceMeta = null,
  dataVersion = improvementState.dataVersion,
) {
  const reviewedBasisKeys = [];
  const basisReasons = {};
  (basisResults || []).forEach((result) => {
    if (!result?.basis_reason) return;
    const key = result.reviewed_basis_key || basisKey(result.law_name, result.article_no);
    if (!key || key === "|" || reviewedBasisKeys.includes(key)) return;
    reviewedBasisKeys.push(key);
    basisReasons[key] = result.basis_reason;
  });

  return {
    reviewed_at: new Date().toISOString(),
    item_id: fallbackText(item?.item_id, ""),
    display_name: fallbackText(item?.display_name, ""),
    category: fallbackText(item?.category, ""),
    selected_flags: Array.from(selectedFlags || []),
    note: fallbackText(note, ""),
    basis_article_ids: (basisResults || []).map((result) => result.article_id).filter(Boolean),
    reviewed_basis_keys: reviewedBasisKeys,
    basis_reasons: basisReasons,
    source_updated_at: fallbackText(sourceMeta?.updated_at, "未取得"),
    data_version: fallbackText(dataVersion, "未提供"),
  };
}

function setImprovementStatus(message, kind = "") {
  if (!improvementEls.status) return;
  improvementEls.status.textContent = message;
  improvementEls.status.className = kind
    ? `status-line improvement-live-status ${kind}`
    : "status-line improvement-live-status";
}

function setCaseStatus(message, kind = "") {
  if (!improvementEls.caseStatusLine) return;
  improvementEls.caseStatusLine.textContent = message;
  improvementEls.caseStatusLine.className = kind ? `case-status-line ${kind}` : "case-status-line";
}

function createListItems(values) {
  return (values || []).map((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    return item;
  });
}

function renderSeedItems() {
  if (!improvementEls.items) return;
  improvementEls.items.replaceChildren();

  ALLOWED_IMPROVEMENT_CATEGORIES.forEach((category) => {
    const categoryItems = improvementState.items.filter((item) => item.category === category);
    if (!categoryItems.length) return;

    const group = document.createElement("section");
    group.className = "improvement-item-group";

    const heading = document.createElement("h3");
    heading.textContent = category;
    group.append(heading);

    categoryItems.forEach((item) => {
      const viewModel = buildDeficiencyCaseViewModel(item);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "improvement-item";
      button.dataset.itemId = viewModel.item_id;
      button.setAttribute("aria-pressed", improvementState.selectedItem?.item_id === item.item_id ? "true" : "false");

      const title = document.createElement("span");
      title.className = "improvement-item-title";
      title.textContent = viewModel.display_title;

      const categoryLabel = document.createElement("span");
      categoryLabel.className = "improvement-item-category";
      categoryLabel.textContent = viewModel.category;

      const evidenceStatus = document.createElement("span");
      evidenceStatus.className = "improvement-item-evidence";
      evidenceStatus.textContent = viewModel.reviewed_basis_candidates.length ? "有候選依據" : "待確認";

      button.append(title, categoryLabel, evidenceStatus);
      button.addEventListener("click", () => selectImprovementItem(item.item_id));
      group.append(button);
    });

    improvementEls.items.append(group);
  });
}

function renderCalibrationSummary() {
  if (!improvementEls.calibrationSummary || !improvementState.selectedItem) return;
  improvementEls.calibrationSummary.textContent = formatCalibrationSummary(
    improvementState.selectedItem,
    selectedCalibrationFlags(),
    improvementEls.calibrationNote?.value || "",
  );
}

function renderSelectedItem() {
  const item = improvementState.selectedItem;
  if (!item) return;
  const viewModel = buildDeficiencyCaseViewModel(item);

  if (improvementEls.selectedCategory) improvementEls.selectedCategory.textContent = "目前品項";
  if (improvementEls.selectedTitle) improvementEls.selectedTitle.textContent = viewModel.display_title;
  if (improvementEls.selectedOriginalText) improvementEls.selectedOriginalText.textContent = viewModel.display_name;
  if (improvementEls.selectedScenario) improvementEls.selectedScenario.textContent = viewModel.scenario;
  if (improvementEls.selectedQuestion) improvementEls.selectedQuestion.textContent = viewModel.customer_question;

  if (improvementEls.boundaryLabels) {
    const boundary = document.createElement("span");
    boundary.textContent = TRUST_BOUNDARY_TEXT;
    improvementEls.boundaryLabels.replaceChildren(boundary);
  }

  if (improvementEls.customerExplanation) {
    const explanationLines = viewModel.customer_explanation_lines.length
      ? viewModel.customer_explanation_lines.map((line) => `- ${sanitizeForCopy(line)}`)
      : ["- 未提供，需人工補充。"];
    improvementEls.customerExplanation.textContent = explanationLines.join("\n");
  }

  [
    [improvementEls.equipmentCandidates, viewModel.equipment_candidates],
    [improvementEls.defectCandidates, viewModel.defect_candidates],
    [improvementEls.siteChecks, viewModel.required_site_checks],
  ].forEach(([element, values]) => {
    if (!element) return;
    element.replaceChildren(...createListItems(values));
  });

  renderSeedItems();
  renderCalibrationSummary();
}

function renderBasisLoading() {
  if (improvementEls.basisSummaryStatus) {
    improvementEls.basisSummaryStatus.textContent = "查詢中";
  }
  setCaseStatus("候選依據查詢中");
  if (improvementEls.basisStatus) {
    improvementEls.basisStatus.textContent = "候選依據查詢中";
    improvementEls.basisStatus.className = "basis-status";
  }
  if (improvementEls.primaryBasis) {
    improvementEls.primaryBasis.replaceChildren(createBasisPlaceholder("候選依據查詢中"));
  }
  if (improvementEls.fullBasisSummary) {
    improvementEls.fullBasisSummary.textContent = "查看完整候選依據";
  }
  if (improvementEls.basisList) improvementEls.basisList.replaceChildren();
}

function createBasisPlaceholder(message) {
  const card = document.createElement("article");
  card.className = "basis-card basis-placeholder";
  const marker = document.createElement("span");
  marker.className = "basis-marker";
  marker.textContent = "需人工確認";
  const text = document.createElement("p");
  text.className = "basis-snippet";
  text.textContent = message;
  card.append(marker, text);
  return card;
}

function createBasisCard(result, variant = "") {
  const card = document.createElement("article");
  card.className = [
    result.reviewed_basis ? "basis-card reviewed-basis" : "basis-card",
    variant,
  ].filter(Boolean).join(" ");

  const marker = document.createElement("span");
  marker.className = result.reviewed_basis ? "basis-marker reviewed" : "basis-marker";
  marker.textContent = "候選依據";

  const title = document.createElement("h3");
  title.textContent = `${fallbackText(result.law_name)} ${fallbackText(result.article_no)}`;

  const scope = document.createElement("p");
  scope.className = "basis-scope";
  scope.textContent = `範圍：${fallbackText(result.basis_scope, "未提供")}`;

  const review = document.createElement("p");
  review.className = "basis-review-reason";
  review.textContent = `校閱理由：${fallbackText(result.basis_reason, "未提供")}`;

  const snippet = document.createElement("p");
  snippet.className = "basis-snippet";
  snippet.textContent = fallbackText(result.snippet || result.text, "");

  const matched = document.createElement("p");
  matched.className = "basis-matched-query";
  matched.textContent = `對照方向：${fallbackText(result.matched_query, "未提供")}`;

  const source = document.createElement("a");
  source.href = result.source_url || "#";
  source.target = "_blank";
  source.rel = "noreferrer";
  source.textContent = "官方來源";

  const cardMeta = document.createElement("div");
  cardMeta.className = "basis-card-meta";
  cardMeta.append(matched, source);

  card.append(marker, title, scope, review, snippet, cardMeta);
  return card;
}

function renderBasisResults(results, errors = [], warnings = []) {
  if (!improvementEls.basisStatus || !improvementEls.basisList || !improvementEls.primaryBasis) return;

  const viewModel = buildEvidenceViewModel(results, errors, warnings);
  improvementEls.primaryBasis.replaceChildren();
  improvementEls.basisList.replaceChildren();
  if (improvementEls.basisSummaryStatus) {
    improvementEls.basisSummaryStatus.textContent = viewModel.summaryText;
  }
  setCaseStatus(viewModel.hasBasis ? "已取得主要依據，可複製對外說明。" : viewModel.statusText, viewModel.statusKind);
  improvementEls.basisStatus.textContent = viewModel.warnings.length
    ? `${viewModel.trustBoundaryText} ${viewModel.warnings.length} 筆候選依據需復核。`
    : viewModel.hasBasis
      ? viewModel.trustBoundaryText
      : viewModel.statusText;
  improvementEls.basisStatus.className = viewModel.statusKind ? `basis-status ${viewModel.statusKind}` : "basis-status";

  if (!viewModel.hasBasis) {
    improvementEls.primaryBasis.append(
      createBasisPlaceholder(viewModel.errors.length ? "資料庫未連線，仍可查看保守說明。" : "未取得候選條文，需人工確認。"),
    );
    if (improvementEls.fullBasisSummary) {
      improvementEls.fullBasisSummary.textContent = "查看完整候選依據";
    }
    return;
  }

  improvementEls.primaryBasis.append(createBasisCard(viewModel.primaryBasis, "primary-basis-card"));
  if (improvementEls.fullBasisSummary) {
    improvementEls.fullBasisSummary.textContent = viewModel.hasMoreBasis
      ? `查看完整候選依據（${viewModel.allBasis.length} 筆）`
      : "查看完整候選依據";
  }
  viewModel.allBasis.forEach((result) => {
    improvementEls.basisList.append(createBasisCard(result));
  });
}

async function fetchBasisForItem(item, requestToken = improvementState.basisRequestToken) {
  const reviewedBasis = buildReviewedBasisMap(item.reviewed_basis_candidates || []);
  if (improvementState.basisCache.has(item.item_id)) {
    const results = improvementState.basisCache.get(item.item_id);
    return {
      token: requestToken,
      results,
      errors: [],
      warnings: missingReviewedBasisCandidates(reviewedBasis, results),
    };
  }

  const payloads = [];
  const errors = [];
  for (const query of item.candidate_queries || []) {
    try {
      const params = new URLSearchParams({ q: query, limit: "5" });
      const payload = await fetchJson(`/search/assist?${params.toString()}`);
      payloads.push({ ...payload, query });
    } catch (error) {
      errors.push(error.message);
    }
  }

  const results = mergeBasisResults(payloads, reviewedBasis).slice(0, 5);
  const warnings = missingReviewedBasisCandidates(reviewedBasis, results);
  if (results.length) {
    improvementState.basisCache.set(item.item_id, results);
  }
  return { token: requestToken, results, errors, warnings };
}

function selectImprovementItem(itemId) {
  const item = improvementState.items.find((candidate) => candidate.item_id === itemId);
  if (!item) return;

  improvementState.selectedItem = item;
  improvementState.basisResults = improvementState.basisCache.get(item.item_id) || [];
  renderSelectedItem();
  if (improvementState.basisResults.length) {
    renderBasisResults(improvementState.basisResults);
  } else {
    renderBasisLoading();
  }
  setImprovementStatus("已選取品項，已準備對外說明與候選依據。");

  const requestToken = ++improvementState.basisRequestToken;
  fetchBasisForItem(item, requestToken)
    .then(({ token, results, errors, warnings }) => {
      if (token !== improvementState.basisRequestToken) return;
      improvementState.basisResults = results;
      renderSelectedItem();
      renderBasisResults(results, errors, warnings);
      if (!results.length && errors.length) {
        setImprovementStatus("候選官方依據未取得，仍可先複製保守說明、完整報價素材與校閱 JSON。", "warning");
      }
    })
    .catch((error) => {
      if (requestToken !== improvementState.basisRequestToken) return;
      improvementState.basisResults = [];
      renderSelectedItem();
      renderBasisResults([], [error.message]);
      setImprovementStatus(`候選官方依據未取得：${error.message}`, "warning");
    });
}

function selectedCalibrationFlags() {
  return Array.from(document.querySelectorAll('input[name="calibrationFlag"]:checked')).map((input) => input.value);
}

function showCopyFallback(value) {
  if (!improvementEls.copyFallback || !improvementEls.copyFallbackText) return;
  improvementEls.copyFallback.hidden = false;
  improvementEls.copyFallbackText.value = value;
  improvementEls.copyFallbackText.focus();
  improvementEls.copyFallbackText.select();
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

async function copyText(value, button, successMessage = "已複製") {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      setButtonFeedback(button, successMessage);
      return true;
    }
  } catch (_error) {
    // Fall through to the visible textarea fallback.
  }
  showCopyFallback(value);
  setButtonFeedback(button, "請手動複製");
  return false;
}

async function loadImprovementSources() {
  try {
    const meta = await fetchJson("/meta/sources");
    improvementState.sourceMeta = meta;
    if (improvementEls.sourceVersionLabel) {
      improvementEls.sourceVersionLabel.textContent = formatDisplayDate(meta.updated_at);
    }
    setImprovementStatus(`資料版本：${formatDisplayDate(meta.updated_at)}`);
    renderSelectedItem();
  } catch (error) {
    improvementState.sourceMeta = null;
    if (improvementEls.sourceVersionLabel) {
      improvementEls.sourceVersionLabel.textContent = "未取得";
    }
    setImprovementStatus(`資料版本未取得：${error.message}`, "warning");
    renderSelectedItem();
  }
}

function setupImprovementEvents() {
  improvementEls.copyConservativeButton?.addEventListener("click", () => {
    if (!improvementState.selectedItem) return;
    const primaryBasis = primaryBasisResult(improvementState.basisResults);
    const value = formatConservativeExplanation(
      improvementState.selectedItem,
      primaryBasis,
      improvementState.sourceMeta,
      improvementState.dataVersion,
      improvementState.basisResults.length > 1,
    );
    copyText(value, improvementEls.copyConservativeButton);
  });

  improvementEls.copyFormatMenuButton?.addEventListener("click", () => {
    if (!improvementEls.copyFormatMenu || !improvementEls.copyFormatMenuButton) return;
    const willOpen = improvementEls.copyFormatMenu.hidden;
    improvementEls.copyFormatMenu.hidden = !willOpen;
    improvementEls.copyFormatMenuButton.setAttribute("aria-expanded", String(willOpen));
  });

  improvementEls.copyLineMenuItem?.addEventListener("click", () => {
    if (!improvementState.selectedItem) return;
    const value = formatLineExplanation(
      improvementState.selectedItem,
      improvementState.basisResults,
      improvementState.sourceMeta,
    );
    if (improvementEls.copyFormatMenu) improvementEls.copyFormatMenu.hidden = true;
    if (improvementEls.copyFormatMenuButton) improvementEls.copyFormatMenuButton.setAttribute("aria-expanded", "false");
    copyText(value, improvementEls.copyFormatMenuButton, "已複製 LINE 簡版");
  });

  improvementEls.copyProposalMenuItem?.addEventListener("click", () => {
    if (!improvementState.selectedItem) return;
    const value = formatProposalSupport(
      improvementState.selectedItem,
      improvementState.basisResults,
      improvementState.sourceMeta,
      improvementState.dataVersion,
    );
    if (improvementEls.copyFormatMenu) improvementEls.copyFormatMenu.hidden = true;
    if (improvementEls.copyFormatMenuButton) improvementEls.copyFormatMenuButton.setAttribute("aria-expanded", "false");
    copyText(value, improvementEls.copyFormatMenuButton, "已複製報價素材");
  });

  improvementEls.copyCalibrationButton?.addEventListener("click", () => {
    if (!improvementState.selectedItem) return;
    const payload = buildCalibrationExport(
      improvementState.selectedItem,
      selectedCalibrationFlags(),
      improvementEls.calibrationNote?.value || "",
      improvementState.basisResults,
      improvementState.sourceMeta,
      improvementState.dataVersion,
    );
    copyText(JSON.stringify(payload, null, 2), improvementEls.copyCalibrationButton);
  });

  document.querySelectorAll('input[name="calibrationFlag"]').forEach((input) => {
    input.addEventListener("change", renderCalibrationSummary);
  });
  improvementEls.calibrationNote?.addEventListener("input", renderCalibrationSummary);
}

async function init() {
  if (!improvementEls.items) return;
  setupImprovementEvents();
  try {
    const payload = await loadImprovementData();
    if (improvementEls.version) improvementEls.version.textContent = `資料版本：${formatSeedVersionForDisplay(payload.version)}`;
    renderSeedItems();
    selectImprovementItem(payload.items[0].item_id);
  } catch (error) {
    if (improvementEls.items) improvementEls.items.textContent = "改善品項載入失敗";
    setImprovementStatus(`改善品項載入失敗：${error.message}`, "error");
  }
  loadImprovementSources();
}

init();
