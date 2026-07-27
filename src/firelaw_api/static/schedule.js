const scheduleEls = {
  health: document.querySelector("#scheduleHealth"),
  healthDetail: document.querySelector("#scheduleHealthDetail"),
  visitCount: document.querySelector("#scheduleVisitCount"),
  calendarDetail: document.querySelector("#scheduleCalendarDetail"),
};

async function fetchScheduleJson(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function todayRange() {
  const now = new Date();
  const start = new Date(now);
  const end = new Date(now);
  end.setMonth(end.getMonth() + 3);
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  };
}

async function initScheduleSmoke() {
  try {
    const health = await fetchScheduleJson("/schedule/health");
    scheduleEls.health.textContent = health.status === "ok" ? "可保存排程資料" : "目前僅供查看";
    scheduleEls.healthDetail.textContent = health.reason ? `原因：${health.reason}` : "場所、技師、定期檢查、派工與改期紀錄可寫入本機資料庫。";
  } catch (error) {
    scheduleEls.health.textContent = "目前無法確認";
    scheduleEls.healthDetail.textContent = error.message;
  }

  try {
    const range = todayRange();
    const calendar = await fetchScheduleJson(`/schedule/calendar?from=${range.from}&to=${range.to}`);
    const visits = calendar.visits || [];
    scheduleEls.visitCount.textContent = `${visits.length} 筆`;
    scheduleEls.calendarDetail.textContent = visits.length
      ? "已取得近期定期檢查資料。"
      : "目前沒有近期排程資料。";
  } catch (error) {
    scheduleEls.visitCount.textContent = "無法讀取";
    scheduleEls.calendarDetail.textContent = error.message;
  }
}

initScheduleSmoke();
