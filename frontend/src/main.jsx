import React, {useEffect, useMemo, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  Alert,
  Button,
  Card,
  Chip,
  Link,
  ScrollShadow,
  SearchField,
  Spinner,
  TextArea,
} from "@heroui/react";
import {
  Building2,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Clock3,
  MapPinned,
  Plus,
  RefreshCw,
  Route,
  Send,
  UserPlus,
  UsersRound,
} from "lucide-react";
import "./styles.css";

const STATUS_OPTIONS = [
  ["scheduled", "已排程"],
  ["dispatched", "已派工"],
  ["in_progress", "進行中"],
  ["waiting_review", "待複核"],
  ["completed", "已完成"],
  ["missed", "未完成"],
  ["cancelled", "取消"],
];

const RECURRENCE_OPTIONS = [
  ["weekly", "每週"],
  ["monthly", "每月"],
  ["quarterly", "每季"],
  ["semiannual", "每半年"],
  ["annual", "每年"],
];

const api = {
  async get(path) {
    const response = await fetch(path);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  },
  async post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  },
};

function App() {
  if (window.location.pathname.startsWith("/schedule")) return <SchedulePage />;
  return <HomePage />;
}

function PageShell({children, active = "home"}) {
  const nav = [
    ["home", "首頁", "/"],
    ["schedule", "排程派工", "/schedule"],
    ["docs", "開發者文件", "/docs"],
  ];
  return (
    <div className="min-h-screen bg-[var(--fb-muted-surface)] text-[var(--fb-text)]">
      <header className="sticky top-0 z-40 border-b border-[var(--fb-line)] bg-[var(--fb-surface)]/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-8">
          <Link className="flex flex-col gap-1 text-[var(--fb-text)] no-underline" href="/">
            <span className="text-lg font-black tracking-normal">FireBasis</span>
            <span className="text-xs text-[var(--fb-muted)]">消防公司營運流程</span>
          </Link>
          <nav className="flex flex-wrap gap-2" aria-label="主要頁面">
            {nav.map(([key, label, href]) => (
              <Link
                key={key}
                href={href}
                className={[
                  "inline-flex h-8 items-center rounded-md border px-3 text-sm font-bold no-underline transition-colors",
                  active === key
                    ? "border-[var(--fb-secondary)] bg-[var(--fb-primary)] text-[var(--fb-secondary)]"
                    : "border-transparent text-[var(--fb-muted)] hover:bg-[var(--fb-muted-surface)] hover:text-[var(--fb-text)]",
                ].join(" ")}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      {children}
    </div>
  );
}

function HomePage() {
  return (
    <PageShell active="home">
      <main className="mx-auto flex max-w-7xl flex-col gap-12 px-4 py-10 md:px-8 md:py-16">
        <section className="grid min-h-[calc(100vh-128px)] items-center gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="grid gap-8">
            <div className="flex flex-wrap gap-2">
              <Chip className="bg-[var(--fb-primary)] text-[var(--fb-secondary)]">排程</Chip>
              <Chip variant="bordered">派工</Chip>
              <Chip variant="bordered">檢查工單</Chip>
            </div>
            <div className="grid gap-5">
              <h1 className="max-w-4xl text-5xl font-black leading-tight tracking-normal md:text-6xl">
                消防公司排程派工與檢查工單追蹤
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-[var(--fb-muted)]">
                把場所、技師、定期檢查、行程狀態與改期紀錄集中在同一個操作頁。先讓每天的工作排出去、看得到、改得動。
              </p>
              <p className="max-w-2xl text-base leading-7 text-[var(--fb-muted)]">
                法規 API 保留為可信資料層；產品主線不承諾自動判斷法規適用。
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link className="inline-flex h-11 items-center justify-center rounded-md bg-[var(--fb-primary)] px-5 text-sm font-black text-[var(--fb-secondary)] no-underline transition-opacity hover:opacity-90" href="/schedule">
                開啟排程派工
              </Link>
              <Link className="inline-flex h-11 items-center justify-center rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] px-5 text-sm font-black text-[var(--fb-text)] no-underline transition-colors hover:border-[var(--fb-secondary)]" href="/docs">
                查看 API 文件
              </Link>
            </div>
          </div>

          <Card className="border border-[var(--fb-line)] shadow-none">
            <Card.Header>
              <Card.Title>今日工作概覽</Card.Title>
              <Card.Description>新的主流程以排程派工為核心。</Card.Description>
            </Card.Header>
            <Card.Content className="grid gap-3">
              {[
                ["1", "建立場所與客戶資料"],
                ["2", "建立定期檢查系列"],
                ["3", "產生檢查行程"],
                ["4", "指派技師與更新狀態"],
                ["5", "記錄單次或後續改期"],
              ].map(([number, label]) => (
                <div key={number} className="flex items-center gap-3 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-3">
                  <span className="grid size-8 place-items-center rounded-full bg-[var(--fb-secondary)] text-sm font-black text-[var(--fb-primary)]">{number}</span>
                  <span className="font-bold">{label}</span>
                </div>
              ))}
            </Card.Content>
          </Card>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <FeatureCard icon={CalendarClock} title="定期檢查" body="用週期規則產生未來行程，減少漏排與手動重建。" />
          <FeatureCard icon={UsersRound} title="狀態追蹤" body="把技師派工、進行中、完成與未完成狀態放在同一頁追蹤。" />
          <FeatureCard icon={Route} title="改期紀錄" body="單次改期或本次與未來一起改期，都留下可追溯紀錄。" />
        </section>
      </main>
    </PageShell>
  );
}

function SchedulePage() {
  const initialRange = useMemo(() => defaultRange(), []);
  const [range, setRange] = useState(initialRange);
  const [health, setHealth] = useState(null);
  const [calendar, setCalendar] = useState({visits: []});
  const [dispatch, setDispatch] = useState({technicians: [], unassigned: []});
  const [map, setMap] = useState({points: []});
  const [sites, setSites] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [series, setSeries] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedVisitId, setSelectedVisitId] = useState("");
  const [statusEvents, setStatusEvents] = useState([]);
  const [rescheduleEvents, setRescheduleEvents] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [siteDraft, setSiteDraft] = useState(emptySiteDraft);
  const [technicianDraft, setTechnicianDraft] = useState(emptyTechnicianDraft);
  const [seriesDraft, setSeriesDraft] = useState(() => emptySeriesDraft(initialRange.from));
  const [assignDraft, setAssignDraft] = useState({technician_id: "", note: ""});
  const [rescheduleDraft, setRescheduleDraft] = useState({
    scheduled_start: "",
    scope: "single",
    reason: "",
  });

  const visits = calendar.visits || [];
  const filteredVisits = useMemo(() => filterVisits(visits, query), [visits, query]);
  const selectedVisit = filteredVisits.find((visit) => visit.visit_id === selectedVisitId) || filteredVisits[0] || visits[0] || null;
  const writable = health?.writable !== false;
  const unassigned = dispatch.unassigned || [];
  const assignedCount = visits.filter((visit) => visit.assigned_technician_id).length;
  const openCount = visits.filter((visit) => !["completed", "cancelled"].includes(visit.status)).length;

  useEffect(() => {
    loadSchedule();
  }, [range.from, range.to, range.dispatchDate]);

  useEffect(() => {
    if (!selectedVisit) {
      setSelectedVisitId("");
      setStatusEvents([]);
      setRescheduleEvents([]);
      return;
    }
    if (selectedVisit.visit_id !== selectedVisitId) setSelectedVisitId(selectedVisit.visit_id);
    loadVisitEvents(selectedVisit.visit_id);
    setAssignDraft((draft) => ({
      ...draft,
      technician_id: draft.technician_id || selectedVisit.assigned_technician_id || technicians[0]?.technician_id || "",
    }));
    setRescheduleDraft((draft) => ({
      ...draft,
      scheduled_start: draft.scheduled_start || toDatetimeLocal(selectedVisit.scheduled_start),
    }));
  }, [selectedVisit?.visit_id, technicians.length]);

  async function loadSchedule() {
    setError("");
    try {
      const [healthPayload, calendarPayload, dispatchPayload, mapPayload, sitesPayload, techniciansPayload, seriesPayload] = await Promise.all([
        api.get("/schedule/health").catch(() => ({status: "degraded", writable: false})),
        api.get(`/schedule/calendar?from=${range.from}&to=${range.to}&view=week`).catch(() => ({visits: []})),
        api.get(`/schedule/dispatch-board?date=${range.dispatchDate}`).catch(() => ({technicians: [], unassigned: []})),
        api.get(`/schedule/map?from=${range.from}&to=${range.to}`).catch(() => ({points: []})),
        api.get("/schedule/sites").catch(() => ({sites: []})),
        api.get("/schedule/technicians").catch(() => ({technicians: []})),
        api.get("/schedule/series").catch(() => ({series: []})),
      ]);
      setHealth(healthPayload);
      setCalendar(calendarPayload);
      setDispatch(dispatchPayload);
      setMap(mapPayload);
      setSites(sitesPayload.sites || []);
      setTechnicians(techniciansPayload.technicians || []);
      setSeries(seriesPayload.series || []);
    } catch (exc) {
      setError(exc.message || "排程資料讀取失敗");
    }
  }

  async function loadVisitEvents(visitId) {
    const [statusPayload, reschedulePayload] = await Promise.all([
      api.get(`/schedule/visits/${visitId}/status-events`).catch(() => ({events: []})),
      api.get(`/schedule/visits/${visitId}/reschedule-events`).catch(() => ({events: []})),
    ]);
    setStatusEvents(statusPayload.events || []);
    setRescheduleEvents(reschedulePayload.events || []);
  }

  async function runAction(action, task) {
    setBusy(action);
    setError("");
    setToast("");
    try {
      const message = await task();
      setToast(message);
      await loadSchedule();
    } catch (exc) {
      setError(exc.message || "操作失敗");
    } finally {
      setBusy("");
    }
  }

  function createSite() {
    return runAction("site", async () => {
      if (!siteDraft.name.trim()) throw new Error("請輸入場所名稱");
      await api.post("/schedule/sites", numericLocation(siteDraft));
      setSiteDraft(emptySiteDraft);
      return "已建立場所";
    });
  }

  function createTechnician() {
    return runAction("technician", async () => {
      if (!technicianDraft.name.trim()) throw new Error("請輸入技師姓名");
      await api.post("/schedule/technicians", technicianDraft);
      setTechnicianDraft(emptyTechnicianDraft);
      return "已建立技師";
    });
  }

  function createSeries() {
    return runAction("series", async () => {
      const siteId = seriesDraft.site_id || sites[0]?.site_id;
      if (!siteId) throw new Error("請先建立場所");
      if (!seriesDraft.title.trim()) throw new Error("請輸入檢查名稱");
      const payload = {
        ...seriesDraft,
        site_id: siteId,
        recurrence_interval: Number(seriesDraft.recurrence_interval || 1),
        duration_minutes: Number(seriesDraft.duration_minutes || 120),
        default_technician_id: seriesDraft.default_technician_id || null,
      };
      const result = await api.post("/schedule/series", payload);
      setSeriesDraft(emptySeriesDraft(range.from));
      return `已建立定期檢查，產生 ${result.generated_visit_count || 0} 筆行程`;
    });
  }

  function assignSelectedVisit() {
    return runAction("assign", async () => {
      if (!selectedVisit) throw new Error("請先選取檢查");
      if (!assignDraft.technician_id) throw new Error("請選擇技師");
      await api.post(`/schedule/visits/${selectedVisit.visit_id}/assign`, assignDraft);
      return "已更新派工";
    });
  }

  function updateSelectedStatus(status) {
    return runAction(`status-${status}`, async () => {
      if (!selectedVisit) throw new Error("請先選取檢查");
      await api.post(`/schedule/visits/${selectedVisit.visit_id}/status`, {status, note: "從排程派工頁更新"});
      return `已更新狀態：${statusLabel(status)}`;
    });
  }

  function rescheduleSelectedVisit() {
    return runAction("reschedule", async () => {
      if (!selectedVisit) throw new Error("請先選取檢查");
      if (!rescheduleDraft.scheduled_start) throw new Error("請選擇新時間");
      const result = await api.post(`/schedule/visits/${selectedVisit.visit_id}/reschedule`, {
        scheduled_start: datetimeLocalToTaipeiIso(rescheduleDraft.scheduled_start),
        scope: rescheduleDraft.scope,
        reason: rescheduleDraft.reason,
      });
      return `已改期，影響 ${result.affected_visit_count || 1} 筆行程`;
    });
  }

  return (
    <PageShell active="schedule">
      <main className="mx-auto grid max-w-[1500px] gap-6 px-4 py-6 lg:px-8 xl:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card className="border border-[var(--fb-line)] shadow-none">
            <Card.Header>
              <Card.Title>排程派工</Card.Title>
              <Card.Description>場所、技師、行程與狀態。</Card.Description>
            </Card.Header>
            <Card.Content className="grid gap-2">
              <SidebarMetric icon={CalendarDays} label="本區間" value={`${filteredVisits.length} 筆`} />
              <SidebarMetric icon={Send} label="未派工" value={`${unassigned.length} 筆`} />
              <SidebarMetric icon={UsersRound} label="技師" value={`${technicians.length} 人`} />
              <SidebarMetric icon={Building2} label="場所" value={`${sites.length} 個`} />
              <SidebarMetric icon={ClipboardList} label="定期檢查" value={`${series.length} 組`} />
            </Card.Content>
          </Card>
        </aside>

        <section className="grid gap-6">
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <SearchField aria-label="搜尋排程" className="w-full" fullWidth>
              <SearchField.Group>
                <SearchField.SearchIcon />
                <SearchField.Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋場所、技師、檢查名稱或狀態" />
                <SearchField.ClearButton />
              </SearchField.Group>
            </SearchField>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <DateInput label="起日" value={range.from} onChange={(value) => setRange((current) => ({...current, from: value}))} />
              <DateInput label="迄日" value={range.to} onChange={(value) => setRange((current) => ({...current, to: value}))} />
              <DateInput label="派工日" value={range.dispatchDate} onChange={(value) => setRange((current) => ({...current, dispatchDate: value}))} />
              <Button isDisabled={!!busy} onPress={loadSchedule} variant="outline">
                <RefreshCw size={16} />
                重新整理
              </Button>
            </div>
          </section>

          <section className="grid gap-3">
            <p className="text-sm font-bold text-[var(--fb-muted)]">排程 / 派工 / 工單狀態</p>
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
              <div>
                <h1 className="text-4xl font-black leading-tight tracking-normal">排程與派工板</h1>
                <p className="mt-3 max-w-3xl leading-7 text-[var(--fb-muted)]">
                  從場所與定期檢查開始，選定技師、更新狀態、處理改期。這頁只處理營運流程。
                </p>
              </div>
              <Card className="border border-[var(--fb-line)] shadow-none">
                <Card.Content className="flex items-center justify-between gap-4 p-4">
                  <div>
                    <p className="text-sm font-black">保存狀態</p>
                    <p className="text-sm text-[var(--fb-muted)]">{health?.status === "ok" ? "本機排程資料可寫入" : "目前僅供查看"}</p>
                  </div>
                  <Chip className="bg-[var(--fb-primary)] text-[var(--fb-secondary)]">{writable ? "可寫入" : "只讀"}</Chip>
                </Card.Content>
              </Card>
            </div>
          </section>

          {!writable ? <Alert>部署版目前只供查看；要測試新增、派工和改期，請用本機服務開啟。</Alert> : null}
          {toast ? <Alert>{toast}</Alert> : null}
          {error ? <Alert className="border border-[var(--fb-danger)] text-[var(--fb-danger)]">{error}</Alert> : null}

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SummaryCard icon={Send} label="待派工" value={unassigned.length} helper="未指派技師" />
            <SummaryCard icon={UsersRound} label="已派工" value={assignedCount} helper="已有技師" />
            <SummaryCard icon={Clock3} label="待處理" value={openCount} helper="未完成行程" />
            <SummaryCard icon={MapPinned} label="有座標" value={map.points?.length || 0} helper="可用於地圖" />
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_420px]">
            <Card className="border border-[var(--fb-line)] shadow-none">
              <Card.Header>
                <Card.Title>新增資料</Card.Title>
                <Card.Description>先建立場所、技師，再建立定期檢查。</Card.Description>
              </Card.Header>
              <Card.Content className="grid gap-6">
                <FormSection title="場所" icon={Building2}>
                  <FormGrid>
                    <TextInput label="場所名稱" value={siteDraft.name} onChange={(value) => setSiteDraft({...siteDraft, name: value})} placeholder="例：A 工廠" />
                    <TextInput label="客戶名稱" value={siteDraft.customer_name} onChange={(value) => setSiteDraft({...siteDraft, customer_name: value})} />
                    <TextInput label="地址" value={siteDraft.address} onChange={(value) => setSiteDraft({...siteDraft, address: value})} />
                    <TextInput label="聯絡人" value={siteDraft.contact_name} onChange={(value) => setSiteDraft({...siteDraft, contact_name: value})} />
                    <TextInput label="電話" value={siteDraft.contact_phone} onChange={(value) => setSiteDraft({...siteDraft, contact_phone: value})} />
                    <TextInput label="緯度" value={siteDraft.latitude} onChange={(value) => setSiteDraft({...siteDraft, latitude: value})} />
                    <TextInput label="經度" value={siteDraft.longitude} onChange={(value) => setSiteDraft({...siteDraft, longitude: value})} />
                  </FormGrid>
                  <Button isDisabled={!!busy || !writable} onPress={createSite}>
                    <Plus size={16} />
                    {busy === "site" ? "建立中" : "建立場所"}
                  </Button>
                </FormSection>

                <FormSection title="技師" icon={UserPlus}>
                  <FormGrid>
                    <TextInput label="姓名" value={technicianDraft.name} onChange={(value) => setTechnicianDraft({...technicianDraft, name: value})} placeholder="例：陳技師" />
                    <TextInput label="電話" value={technicianDraft.phone} onChange={(value) => setTechnicianDraft({...technicianDraft, phone: value})} />
                    <TextInput label="角色" value={technicianDraft.role} onChange={(value) => setTechnicianDraft({...technicianDraft, role: value})} />
                    <TextInput label="顏色" value={technicianDraft.color} onChange={(value) => setTechnicianDraft({...technicianDraft, color: value})} />
                  </FormGrid>
                  <Button isDisabled={!!busy || !writable} onPress={createTechnician}>
                    <UserPlus size={16} />
                    {busy === "technician" ? "建立中" : "建立技師"}
                  </Button>
                </FormSection>

                <FormSection title="定期檢查" icon={CalendarClock}>
                  <FormGrid>
                    <SelectInput label="場所" value={seriesDraft.site_id || sites[0]?.site_id || ""} onChange={(value) => setSeriesDraft({...seriesDraft, site_id: value})} options={sites.map((site) => [site.site_id, site.name])} />
                    <TextInput label="檢查名稱" value={seriesDraft.title} onChange={(value) => setSeriesDraft({...seriesDraft, title: value})} />
                    <TextInput label="檢查類型" value={seriesDraft.inspection_type} onChange={(value) => setSeriesDraft({...seriesDraft, inspection_type: value})} />
                    <SelectInput label="週期" value={seriesDraft.recurrence_frequency} onChange={(value) => setSeriesDraft({...seriesDraft, recurrence_frequency: value})} options={RECURRENCE_OPTIONS} />
                    <TextInput label="間隔" type="number" value={seriesDraft.recurrence_interval} onChange={(value) => setSeriesDraft({...seriesDraft, recurrence_interval: value})} />
                    <DateInput label="開始日" value={seriesDraft.start_date} onChange={(value) => setSeriesDraft({...seriesDraft, start_date: value})} />
                    <DateInput label="結束日" value={seriesDraft.end_date} onChange={(value) => setSeriesDraft({...seriesDraft, end_date: value})} />
                    <TextInput label="偏好時間" type="time" value={seriesDraft.preferred_start_time} onChange={(value) => setSeriesDraft({...seriesDraft, preferred_start_time: value})} />
                    <TextInput label="分鐘" type="number" value={seriesDraft.duration_minutes} onChange={(value) => setSeriesDraft({...seriesDraft, duration_minutes: value})} />
                    <SelectInput label="預設技師" value={seriesDraft.default_technician_id} onChange={(value) => setSeriesDraft({...seriesDraft, default_technician_id: value})} options={[["", "未指定"], ...technicians.map((tech) => [tech.technician_id, tech.name])]} />
                  </FormGrid>
                  <Button isDisabled={!!busy || !writable} onPress={createSeries}>
                    <CalendarClock size={16} />
                    {busy === "series" ? "建立中" : "建立定期檢查"}
                  </Button>
                </FormSection>
              </Card.Content>
            </Card>

            <SelectedVisitPanel
              busy={busy}
              selectedVisit={selectedVisit}
              technicians={technicians}
              writable={writable}
              assignDraft={assignDraft}
              setAssignDraft={setAssignDraft}
              rescheduleDraft={rescheduleDraft}
              setRescheduleDraft={setRescheduleDraft}
              onAssign={assignSelectedVisit}
              onReschedule={rescheduleSelectedVisit}
              onStatus={updateSelectedStatus}
              statusEvents={statusEvents}
              rescheduleEvents={rescheduleEvents}
            />
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_420px]">
            <VisitList visits={filteredVisits} selectedVisit={selectedVisit} onSelect={setSelectedVisitId} />
            <DispatchPanel dispatch={dispatch} />
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_420px]">
            <MapPanel points={map.points || []} selectedVisit={selectedVisit} onSelect={setSelectedVisitId} />
            <SeriesPanel series={series} />
          </section>
        </section>
      </main>
    </PageShell>
  );
}

function SelectedVisitPanel({
  busy,
  selectedVisit,
  technicians,
  writable,
  assignDraft,
  setAssignDraft,
  rescheduleDraft,
  setRescheduleDraft,
  onAssign,
  onReschedule,
  onStatus,
  statusEvents,
  rescheduleEvents,
}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Header>
        <Card.Title>檢查工單</Card.Title>
        <Card.Description>{selectedVisit ? "選取一筆行程後處理派工、狀態與改期。" : "尚未選取檢查。"}</Card.Description>
      </Card.Header>
      <Card.Content className="grid gap-5">
        {selectedVisit ? (
          <>
            <div className="grid gap-2">
              <p className="text-xs font-black text-[var(--fb-muted)]">目前選取</p>
              <h2 className="text-xl font-black leading-tight">{selectedVisit.title}</h2>
              <p className="text-sm leading-6 text-[var(--fb-muted)]">
                {selectedVisit.site?.name || "未提供場所"} / {formatDateTime(selectedVisit.scheduled_start)} / {selectedVisit.assigned_technician?.name || "未派工"}
              </p>
              <Chip variant="bordered">{statusLabel(selectedVisit.status)}</Chip>
            </div>

            <FormSection title="指派技師" icon={Send}>
              <SelectInput label="技師" value={assignDraft.technician_id} onChange={(value) => setAssignDraft({...assignDraft, technician_id: value})} options={technicians.map((tech) => [tech.technician_id, tech.name])} />
              <TextArea value={assignDraft.note} onChange={(event) => setAssignDraft({...assignDraft, note: event.target.value})} placeholder="派工備註" minRows={2} />
              <Button isDisabled={!!busy || !writable || !technicians.length} onPress={onAssign}>
                <Send size={16} />
                {busy === "assign" ? "派工中" : "指派選取檢查"}
              </Button>
            </FormSection>

            <FormSection title="更新狀態" icon={CheckCircle2}>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ["in_progress", "開始"],
                  ["waiting_review", "待複核"],
                  ["completed", "完成"],
                  ["missed", "未完成"],
                  ["cancelled", "取消"],
                ].map(([status, label]) => (
                  <Button key={status} isDisabled={!!busy || !writable} onPress={() => onStatus(status)} size="sm" variant="outline">
                    {label}
                  </Button>
                ))}
              </div>
            </FormSection>

            <FormSection title="改期" icon={CalendarDays}>
              <TextInput label="新時間" type="datetime-local" value={rescheduleDraft.scheduled_start} onChange={(value) => setRescheduleDraft({...rescheduleDraft, scheduled_start: value})} />
              <SelectInput label="範圍" value={rescheduleDraft.scope} onChange={(value) => setRescheduleDraft({...rescheduleDraft, scope: value})} options={[["single", "只改這一次"], ["this_and_future", "本次與未來一起改"]]} />
              <TextArea value={rescheduleDraft.reason} onChange={(event) => setRescheduleDraft({...rescheduleDraft, reason: event.target.value})} placeholder="改期原因" minRows={2} />
              <Button isDisabled={!!busy || !writable} onPress={onReschedule} variant="secondary">
                <CalendarDays size={16} />
                {busy === "reschedule" ? "改期中" : "套用改期"}
              </Button>
            </FormSection>

            <EventList title="狀態紀錄" events={statusEvents} render={(event) => `${statusLabel(event.previous_status) || "建立"} → ${statusLabel(event.new_status)}`} />
            <EventList title="改期紀錄" events={rescheduleEvents} render={(event) => `${formatDateTime(event.old_scheduled_start)} → ${formatDateTime(event.new_scheduled_start)}，${event.affected_visit_count} 筆`} />
          </>
        ) : (
          <p className="text-sm leading-6 text-[var(--fb-muted)]">建立或選取一筆檢查後，這裡會顯示可操作的工單資訊。</p>
        )}
      </Card.Content>
    </Card>
  );
}

function VisitList({visits, selectedVisit, onSelect}) {
  const groups = groupVisitsByDate(visits);
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Header>
        <Card.Title>行程列表</Card.Title>
        <Card.Description>依日期檢視定期檢查與派工狀態。</Card.Description>
      </Card.Header>
      <Card.Content>
        <ScrollShadow className="max-h-[620px] pr-2">
          {groups.length ? (
            <div className="grid gap-5">
              {groups.map(([date, dateVisits]) => (
                <section key={date} className="grid gap-3">
                  <div className="flex items-center justify-between border-b border-[var(--fb-line)] pb-2">
                    <h2 className="text-lg font-black">{formatDate(date)}</h2>
                    <span className="text-sm font-bold text-[var(--fb-muted)]">{dateVisits.length} 筆</span>
                  </div>
                  <div className="grid gap-3">
                    {dateVisits.map((visit) => (
                      <Button
                        key={visit.visit_id}
                        className={[
                          "h-auto justify-start border p-4 text-left",
                          selectedVisit?.visit_id === visit.visit_id
                            ? "border-[var(--fb-secondary)] bg-[var(--fb-primary)] text-[var(--fb-secondary)]"
                            : "border-[var(--fb-line)] bg-[var(--fb-surface)]",
                        ].join(" ")}
                        fullWidth
                        onPress={() => onSelect(visit.visit_id)}
                        variant="ghost"
                      >
                        <span className="grid w-full gap-3 md:grid-cols-[96px_minmax(0,1fr)_190px] md:items-center">
                          <span className="text-sm font-black">{formatTime(visit.scheduled_start)}</span>
                          <span className="flex flex-col items-start gap-1">
                            <strong className="break-words text-base">{visit.title}</strong>
                            <span className="text-sm opacity-75">{visit.site?.name || "未提供場所"}</span>
                          </span>
                          <span className="flex flex-wrap gap-2 md:justify-end">
                            <Chip variant="bordered">{statusLabel(visit.status)}</Chip>
                            <Chip className="bg-[var(--fb-primary)] text-[var(--fb-secondary)]">{visit.assigned_technician?.name || "未派工"}</Chip>
                          </span>
                        </span>
                      </Button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <p className="border border-[var(--fb-line)] bg-[var(--fb-surface)] p-4 text-sm text-[var(--fb-muted)]">
              尚無排程資料。先建立場所、技師與定期檢查。
            </p>
          )}
        </ScrollShadow>
      </Card.Content>
    </Card>
  );
}

function DispatchPanel({dispatch}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Header>
        <Card.Title>派工看板</Card.Title>
        <Card.Description>同一天的技師工作量與未派工行程。</Card.Description>
      </Card.Header>
      <Card.Content className="grid gap-4">
        <div className="grid gap-2">
          <h3 className="text-sm font-black">未派工</h3>
          {(dispatch.unassigned || []).length ? dispatch.unassigned.map((visit) => <MiniVisit key={visit.visit_id} visit={visit} />) : <EmptyText>沒有未派工行程。</EmptyText>}
        </div>
        <div className="grid gap-2">
          <h3 className="text-sm font-black">技師</h3>
          {(dispatch.technicians || []).map((tech) => (
            <div key={tech.technician_id} className="rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-3">
              <div className="flex items-center justify-between gap-3">
                <strong>{tech.name}</strong>
                <Chip variant="bordered">{tech.visit_count || 0} 筆</Chip>
              </div>
              <div className="mt-2 grid gap-2">
                {(tech.visits || []).length ? tech.visits.map((visit) => <MiniVisit key={visit.visit_id} visit={visit} />) : <EmptyText>當天沒有行程。</EmptyText>}
              </div>
            </div>
          ))}
        </div>
      </Card.Content>
    </Card>
  );
}

function MapPanel({points, selectedVisit, onSelect}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Header>
        <Card.Title>地點與派工概覽</Card.Title>
        <Card.Description>使用已保存座標呈現檢查地點；目前不接外部地圖服務。</Card.Description>
      </Card.Header>
      <Card.Content className="grid gap-4">
        <div className="relative min-h-[360px] overflow-hidden rounded-md border border-[var(--fb-line)] bg-[var(--fb-muted-surface)]">
          <div className="absolute left-6 top-6 flex items-center gap-2 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] px-3 py-2 text-sm font-bold">
            <MapPinned size={16} />
            {points.length ? `${points.length} 個地點` : "尚無座標"}
          </div>
          {points.map((point, index) => (
            <button
              key={`${point.visit_id}-${index}`}
              aria-label={`選取 ${point.site_name}`}
              className="absolute grid size-10 place-items-center rounded-full border-2 border-[var(--fb-secondary)] bg-[var(--fb-primary)] text-[var(--fb-secondary)] shadow-sm"
              onClick={() => onSelect(point.visit_id)}
              style={{left: `${18 + (index * 19) % 62}%`, top: `${26 + (index * 23) % 54}%`}}
              type="button"
            >
              <MapPinned size={17} />
            </button>
          ))}
          {selectedVisit ? (
            <div className="absolute bottom-5 left-5 right-5 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-4">
              <p className="text-xs font-black text-[var(--fb-muted)]">目前選取</p>
              <strong className="mt-1 block">{selectedVisit.site?.name || "未提供場所"}</strong>
              <p className="mt-1 text-sm text-[var(--fb-muted)]">
                {formatDateTime(selectedVisit.scheduled_start)} / {selectedVisit.assigned_technician?.name || "未派工"}
              </p>
            </div>
          ) : null}
        </div>
      </Card.Content>
    </Card>
  );
}

function SeriesPanel({series}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Header>
        <Card.Title>定期檢查系列</Card.Title>
        <Card.Description>後端已保存的週期性檢查。</Card.Description>
      </Card.Header>
      <Card.Content className="grid gap-2">
        {series.length ? series.slice(0, 8).map((item) => (
          <div key={item.series_id} className="rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-3">
            <strong className="block">{item.title}</strong>
            <span className="text-sm text-[var(--fb-muted)]">{seriesLabel(item)}</span>
          </div>
        )) : <EmptyText>尚無定期檢查。</EmptyText>}
      </Card.Content>
    </Card>
  );
}

function FeatureCard({icon: Icon, title, body}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Content className="grid gap-3 p-5">
        <span className="grid size-10 place-items-center rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)]">
          <Icon size={18} />
        </span>
        <h2 className="text-xl font-black">{title}</h2>
        <p className="leading-7 text-[var(--fb-muted)]">{body}</p>
      </Card.Content>
    </Card>
  );
}

function SidebarMetric({icon: Icon, label, value}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] px-3 py-3">
      <span className="flex items-center gap-2 text-sm font-black">
        <Icon size={16} />
        {label}
      </span>
      <span className="text-xs font-bold text-[var(--fb-muted)]">{value}</span>
    </div>
  );
}

function SummaryCard({icon: Icon, label, value, helper}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Content className="flex items-center justify-between gap-4 p-4">
        <div>
          <p className="text-3xl font-black">{value ?? 0}</p>
          <p className="mt-1 text-sm font-bold text-[var(--fb-muted)]">{label}</p>
          {helper ? <p className="mt-1 text-xs text-[var(--fb-muted)]">{helper}</p> : null}
        </div>
        <span className="grid size-10 place-items-center rounded-md border border-[var(--fb-line)] bg-[var(--fb-muted-surface)]">
          <Icon size={18} />
        </span>
      </Card.Content>
    </Card>
  );
}

function FormSection({title, icon: Icon, children}) {
  return (
    <section className="grid gap-3 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-4">
      <h2 className="flex items-center gap-2 text-base font-black">
        <Icon size={18} />
        {title}
      </h2>
      {children}
    </section>
  );
}

function FormGrid({children}) {
  return <div className="grid gap-3 md:grid-cols-2">{children}</div>;
}

function TextInput({label, value, onChange, placeholder = "", type = "text"}) {
  return (
    <label className="grid gap-1 text-sm font-bold text-[var(--fb-muted)]">
      {label}
      <input
        className="h-10 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] px-3 text-[var(--fb-text)]"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value || ""}
      />
    </label>
  );
}

function DateInput({label, value, onChange}) {
  return <TextInput label={label} type="date" value={value} onChange={onChange} />;
}

function SelectInput({label, value, onChange, options}) {
  return (
    <label className="grid gap-1 text-sm font-bold text-[var(--fb-muted)]">
      {label}
      <select
        className="h-10 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] px-3 text-[var(--fb-text)]"
        onChange={(event) => onChange(event.target.value)}
        value={value || ""}
      >
        {options.length ? options.map(([optionValue, optionLabel]) => <option key={optionValue || "empty"} value={optionValue}>{optionLabel}</option>) : <option value="">尚無資料</option>}
      </select>
    </label>
  );
}

function EventList({title, events, render}) {
  return (
    <div className="grid gap-2 rounded-md border border-[var(--fb-line)] bg-[var(--fb-surface)] p-3">
      <h3 className="text-sm font-black">{title}</h3>
      {events.length ? events.map((event) => (
        <div key={event.event_id || event.change_id} className="grid gap-1 border-t border-[var(--fb-line)] pt-2 text-sm">
          <span className="font-bold">{render(event)}</span>
          <span className="text-xs text-[var(--fb-muted)]">{formatDateTime(event.created_at)} {event.note || event.reason ? ` / ${event.note || event.reason}` : ""}</span>
        </div>
      )) : <EmptyText>尚無紀錄。</EmptyText>}
    </div>
  );
}

function MiniVisit({visit}) {
  return (
    <div className="rounded-md border border-[var(--fb-line)] bg-[var(--fb-muted-surface)] p-2 text-sm">
      <strong className="block">{formatTime(visit.scheduled_start)} {visit.title}</strong>
      <span className="text-[var(--fb-muted)]">{visit.site?.name || "未提供場所"} / {statusLabel(visit.status)}</span>
    </div>
  );
}

function EmptyText({children}) {
  return <p className="text-sm leading-6 text-[var(--fb-muted)]">{children}</p>;
}

function LoadingCard({label}) {
  return (
    <Card className="border border-[var(--fb-line)] shadow-none">
      <Card.Content className="flex items-center gap-3 p-4">
        <Spinner size="sm" />
        <span>{label}</span>
      </Card.Content>
    </Card>
  );
}

function emptySiteDraft() {
  return {name: "", customer_name: "", address: "", contact_name: "", contact_phone: "", latitude: "", longitude: "", notes: ""};
}

function emptyTechnicianDraft() {
  return {name: "", phone: "", role: "technician", active: true, color: "#2563eb"};
}

function emptySeriesDraft(startDate) {
  return {
    site_id: "",
    title: "消防安全設備定期檢查",
    inspection_type: "消防安全設備檢查",
    recurrence_frequency: "semiannual",
    recurrence_interval: 1,
    start_date: startDate,
    end_date: "",
    preferred_start_time: "09:00",
    duration_minutes: 120,
    default_technician_id: "",
    notes: "",
  };
}

function numericLocation(payload) {
  return {
    ...payload,
    latitude: payload.latitude === "" ? null : Number(payload.latitude),
    longitude: payload.longitude === "" ? null : Number(payload.longitude),
  };
}

function defaultRange() {
  const now = new Date();
  const day = now.getDay() || 7;
  const start = new Date(now);
  start.setDate(now.getDate() - day + 1);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return {from: isoDate(start), to: isoDate(end), dispatchDate: isoDate(now)};
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function filterVisits(visits, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return visits;
  return visits.filter((visit) => [
    visit.title,
    visit.inspection_type,
    visit.status,
    statusLabel(visit.status),
    visit.site?.name,
    visit.site?.customer_name,
    visit.assigned_technician?.name,
  ].some((value) => String(value || "").toLowerCase().includes(needle)));
}

function groupVisitsByDate(visits) {
  const groups = new Map();
  for (const visit of visits || []) {
    const key = String(visit.scheduled_start || "").slice(0, 10) || "未提供日期";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(visit);
  }
  return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
}

function statusLabel(status) {
  return Object.fromEntries(STATUS_OPTIONS)[status] || status || "未提供";
}

function seriesLabel(series) {
  const frequency = Object.fromEntries(RECURRENCE_OPTIONS)[series?.recurrence_frequency] || "定期";
  const interval = series?.recurrence_interval && series.recurrence_interval > 1 ? `，間隔 ${series.recurrence_interval}` : "";
  return `${frequency}${interval} / ${series?.preferred_start_time || "09:00"} / ${series?.duration_minutes || 120} 分鐘`;
}

function formatDateTime(value) {
  if (!value) return "未提供時間";
  try {
    return new Intl.DateTimeFormat("zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatDate(value) {
  if (!value) return "未提供日期";
  try {
    return new Intl.DateTimeFormat("zh-TW", {year: "numeric", month: "2-digit", day: "2-digit", weekday: "short"}).format(new Date(`${value}T00:00:00+08:00`));
  } catch {
    return value;
  }
}

function formatTime(value) {
  if (!value) return "未提供";
  try {
    return new Intl.DateTimeFormat("zh-TW", {hour: "2-digit", minute: "2-digit", hour12: false}).format(new Date(value));
  } catch {
    return value;
  }
}

function toDatetimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date).reduce((memo, part) => {
    if (part.type !== "literal") memo[part.type] = part.value;
    return memo;
  }, {});
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function datetimeLocalToTaipeiIso(value) {
  return `${value}:00+08:00`;
}

createRoot(document.getElementById("root")).render(<App />);
