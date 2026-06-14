const TOKEN_KEY = "witcher_larp_admin_token";

const els = {
  loginPanel: document.querySelector("#login-panel"),
  dashboard: document.querySelector("#dashboard"),
  form: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#role-token"),
  loginStatus: document.querySelector("#login-status"),
  dashboardStatus: document.querySelector("#dashboard-status"),
  masterName: document.querySelector("#master-name"),
  stageValue: document.querySelector("#stage-value"),
  snapshotValue: document.querySelector("#snapshot-value"),
  sectionsValue: document.querySelector("#sections-value"),
  attentionValue: document.querySelector("#attention-value"),
  refreshButton: document.querySelector("#refresh-button"),
  logoutButton: document.querySelector("#logout-button"),
  nav: document.querySelector("#section-nav"),
  workspace: document.querySelector("#workspace"),
};

const VIEWS = [
  { id: "setup", label: "Setup игры", status: "setup" },
  { id: "lords", label: "Пульт лордов", status: "watch" },
  { id: "orders", label: "Заказы", status: "attention" },
  { id: "game", label: "Пульт игры", status: "live" },
  { id: "players", label: "Игроки", status: "watch" },
  { id: "codes", label: "Коды", status: "setup" },
  { id: "review", label: "Ревью", status: "attention" },
  { id: "content", label: "Контент", status: "setup" },
];

const ADMIN_AUTO_REFRESH_MS = 10_000;
const REGISTRATION_ACT_ID = "registration";
const LORD_PATCH_LABELS = {
  gold: "Золото",
  current_mp: "MP сейчас",
  mp_cap: "Лимит MP",
  raid_tokens: "Жетоны рейда",
};

let session = null;
let overview = null;
let masterState = null;
let lordBattles = { items: [] };
let reviewQueue = null;
let playerCodes = { items: [], total: 0, enabled_count: 0 };
let contentState = null;
let activeViewId = "setup";
let autoRefreshId = null;
let refreshInFlight = false;
let queuedManualRefresh = false;
let pendingAutoRender = false;

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = els.tokenInput.value.trim();
  if (!token) return;
  await login(token);
});

els.refreshButton.addEventListener("click", async () => {
  if (!session) return;
  await refreshAll({ source: "manual" });
});

els.logoutButton.addEventListener("click", () => {
  stopAutoRefresh();
  localStorage.removeItem(TOKEN_KEY);
  session = null;
  overview = null;
  masterState = null;
  lordBattles = { items: [] };
  reviewQueue = null;
  playerCodes = { items: [], total: 0, enabled_count: 0 };
  contentState = null;
  activeViewId = "setup";
  queuedManualRefresh = false;
  pendingAutoRender = false;
  els.dashboard.hidden = true;
  els.loginPanel.hidden = false;
  els.tokenInput.value = "";
  els.nav.replaceChildren();
  els.workspace.replaceChildren();
  setLoginStatus("");
  setDashboardStatus("");
});

document.addEventListener("focusout", () => {
  window.setTimeout(renderPendingAutoRefresh, 0);
}, true);

document.addEventListener("visibilitychange", () => {
  if (!session || document.visibilityState !== "visible") return;
  refreshAll({ source: "auto", scope: "overview" });
});

const savedToken = localStorage.getItem(TOKEN_KEY);
if (savedToken) {
  els.tokenInput.value = savedToken;
  login(savedToken);
}

async function login(token) {
  setLoginStatus("Проверяю код");
  try {
    const response = await fetch("/api/auth/role-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (!response.ok) throw new Error("Код не принят");
    const auth = await response.json();
    if (auth.role_type !== "npc_master") throw new Error("Нужен код мастера");
    session = { token, auth };
    localStorage.setItem(TOKEN_KEY, token);
    els.masterName.textContent = auth.display_name || "Мастер игры";
    els.loginPanel.hidden = true;
    els.dashboard.hidden = false;
    await refreshAll({ source: "manual" });
    startAutoRefresh();
  } catch (error) {
    stopAutoRefresh();
    localStorage.removeItem(TOKEN_KEY);
    session = null;
    els.dashboard.hidden = true;
    els.loginPanel.hidden = false;
    setLoginStatus(error.message);
  }
}

async function refreshAll(options = {}) {
  const isAuto = options.source === "auto";
  const overviewOnly = options.scope === "overview";
  if (!session) return null;
  if (refreshInFlight) {
    if (!isAuto) queuedManualRefresh = true;
    return null;
  }
  refreshInFlight = true;
  if (!isAuto) setDashboardStatus("Обновляю состояние игры");
  try {
    if (overviewOnly) {
      overview = await apiJson("/api/master/admin/overview");
      return masterState;
    }

    const [overviewPayload, statePayload, battlesPayload, queuePayload, codesPayload] = await Promise.all([
      apiJson("/api/master/admin/overview"),
      apiJson("/api/master/state"),
      apiJson("/api/lord-battles").catch(() => ({ items: [] })),
      apiJson("/api/master/review-queue").catch(() => null),
      apiJson("/api/master/player-codes").catch(() => ({ items: [], total: 0, enabled_count: 0 })),
    ]);
    overview = overviewPayload;
    masterState = statePayload;
    lordBattles = battlesPayload || { items: [] };
    reviewQueue = queuePayload;
    playerCodes = codesPayload || { items: [], total: 0, enabled_count: 0 };
    renderFreshState({ deferActiveView: isAuto && isMasterEditing() });
    if (!isAuto) setDashboardStatus("Состояние игры обновлено");
  } catch (error) {
    if (!isAuto) setDashboardStatus(error.message);
    return null;
  } finally {
    refreshInFlight = false;
    if (queuedManualRefresh) {
      queuedManualRefresh = false;
      await refreshAll({ source: "manual" });
    }
  }
  return masterState;
}

function startAutoRefresh() {
  stopAutoRefresh();
  autoRefreshId = window.setInterval(() => {
    if (!session || document.visibilityState === "hidden") return;
    refreshAll({ source: "auto", scope: "overview" });
  }, ADMIN_AUTO_REFRESH_MS);
}

function stopAutoRefresh() {
  if (!autoRefreshId) return;
  window.clearInterval(autoRefreshId);
  autoRefreshId = null;
}

function renderFreshState({ deferActiveView = false } = {}) {
  renderTopSummary();
  renderNav();
  if (deferActiveView) {
    pendingAutoRender = true;
    setDashboardStatus("Новые данные получены, форма не сброшена");
    return;
  }
  pendingAutoRender = false;
  renderActiveView();
}

function renderPendingAutoRefresh() {
  if (!pendingAutoRender || isMasterEditing()) return;
  pendingAutoRender = false;
  renderShell();
}

function renderShell() {
  renderTopSummary();
  renderNav();
  renderActiveView();
}

function isMasterEditing() {
  if (document.querySelector(".modal-backdrop")) return true;
  const active = document.activeElement;
  if (!active || active === document.body || !(active instanceof HTMLElement)) return false;
  if (active.isContentEditable) return true;
  return Boolean(active.closest("input, select, textarea, form"));
}

function renderTopSummary() {
  const act = masterState?.acts?.state || {};
  const players = playersList();
  const lords = lordDomains();
  const reviewCount = reviewItems().length
    + rewardItems().length
    + activeBattles().length
    + lords.filter((domain) => lordAttention(domain).length).length;
  els.stageValue.textContent = actLabel(act.current_act_id || "not_started");
  els.snapshotValue.textContent = String(players.length);
  els.sectionsValue.textContent = String(lords.length);
  els.attentionValue.textContent = String(reviewCount);
}

function renderNav() {
  els.nav.replaceChildren();
  for (const view of VIEWS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-button";
    button.dataset.viewId = view.id;
    button.setAttribute("aria-pressed", String(view.id === activeViewId));
    button.innerHTML = `
      <span>${escapeHtml(view.label)}</span>
      <span class="status-badge ${viewBadgeClass(view.id)}">${escapeHtml(viewBadgeText(view.id))}</span>
    `;
    button.addEventListener("click", () => {
      activeViewId = view.id;
      renderShell();
    });
    els.nav.append(button);
  }
}

function renderActiveView() {
  els.workspace.replaceChildren();
  if (!masterState) {
    els.workspace.append(emptyLine("Состояние игры пока не загружено"));
    return;
  }
  const view = VIEWS.find((item) => item.id === activeViewId) || VIEWS[0];
  els.workspace.append(pageHeader(view.label, viewIntro(view.id)));
  if (view.id === "setup") renderSetupView();
  if (view.id === "game") renderGameView();
  if (view.id === "lords") renderLordsView();
  if (view.id === "orders") renderOrdersView();
  if (view.id === "players") renderPlayersView();
  if (view.id === "codes") renderPlayerCodesView();
  if (view.id === "review") renderReviewView();
  if (view.id === "content") renderContentView();
}

function renderGameView() {
  const act = masterState.acts?.state || {};
  const timers = masterState.timers || {};
  const elapsed = elapsedMinutes(act.active_started_at);
  const panel = sectionPanel("Ход игры", "main-panel");
  panel.append(
    heroBlock([
      ["Текущий акт", actLabel(act.current_act_id || "not_started")],
      ["Статус", humanStatus(act.status || "pending")],
      ["Прошло", formatMinutes(elapsed)],
      ["Тиков", timers.applied_tick_count || 0],
    ])
  );
  panel.append(startGameForm());
  panel.append(timeControlForm(elapsed));
  panel.append(actionBar([
    actionButton("Начислить тик лордам", () => applyLordTick()),
    actionButton("Обновить", () => refreshAll(), "secondary"),
    actionButton("Перейти в ревью", () => {
      activeViewId = "review";
      renderShell();
    }, "secondary"),
  ]));
  panel.append(simpleTable(
    ["Акт", "Статус", "Старт", "Объявление"],
    (masterState.acts?.history || []).map((row) => [
      actLabel(row.act_id),
      humanStatus(row.status),
      shortDate(row.started_at),
      humanStatus(row.physical_announcement_state),
    ]),
    "Акты ещё не запускались"
  ));
  els.workspace.append(panel);

  const overviewPanel = sectionPanel("Оперативная картина");
  overviewPanel.append(summaryCards([
    ["Лорды", lordDomains().length],
    ["Игроки", playersList().length],
    ["Активные бои", activeBattles().length],
    ["Проверки", reviewItems().length + rewardItems().length],
  ]));
  els.workspace.append(overviewPanel);
}

function renderSetupView() {
  const setupPlayers = setupPlayersList();
  const panel = sectionPanel("Предыгровая настройка", "main-panel");
  panel.append(summaryCards([
    ["Ведьмаки/чародейки", setupPlayers.length],
    ["Готовы", adminSetupSummary().ready_players || 0],
    ["Нужно внимание", adminSetupSummary().needs_attention || 0],
    ["Выдач", adminSetupGrants().length],
  ]));
  panel.append(actionBar([
    actionButton("Обновить", () => refreshAll(), "secondary"),
    actionButton("Коды игроков", () => switchView("codes"), "secondary"),
    actionButton("Редактировать цели", () => switchView("players"), "secondary"),
    actionButton("Заказы", () => switchView("orders"), "secondary"),
    actionButton("Хард-резет в регистрацию", () => hardResetToRegistration(), "danger"),
  ]));
  panel.append(playerGrantForm(setupPlayers));
  panel.append(blockTitle("Готовность ведьмаков и чародеек"));
  panel.append(readinessTable(setupPlayers));
  panel.append(blockTitle("Последние выдачи"));
  panel.append(setupGrantTable(adminSetupGrants()));
  els.workspace.append(panel);
}

function renderOrdersView() {
  const rows = masterOrderItems();
  const reviewRows = rows.filter((row) => ["P0", "P1"].includes(String(row.severity || "")));
  const panel = sectionPanel("Заказы и спорные решения", "main-panel");
  panel.append(summaryCards([
    ["Открытые заказы", rows.length],
    ["Требуют мастера", reviewRows.length],
    ["Награды ждут", rows.filter((row) => row.status === "pending_master_approval").length],
    ["Споры", rows.filter((row) => row.status === "contested_review").length],
  ]));
  panel.append(actionBar([
    actionButton("Обновить", () => refreshAll(), "secondary"),
    actionButton("Ревью", () => switchView("review"), "secondary"),
    actionButton("Лорды", () => switchView("lords"), "secondary"),
  ]));
  panel.append(orderReviewTable(rows));
  els.workspace.append(panel);
}

function startGameForm() {
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  form.innerHTML = `
    <label class="field">
      <span>Акт для запуска</span>
      <select id="start-act">${actOptions()}</select>
    </label>
    <label class="field">
      <span>Оператор</span>
      <input id="start-operator" autocomplete="off" value="master">
    </label>
    <button type="submit">Запустить акт</button>
  `;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const actId = form.querySelector("#start-act").value || "act1";
    const operator = form.querySelector("#start-operator").value.trim() || "master";
    const isRegistrationReset = actId === REGISTRATION_ACT_ID;
    const confirmed = await confirmAction({
      title: isRegistrationReset ? "Хард-резет в регистрацию?" : "Запустить акт?",
      body: isRegistrationReset
        ? "Состояние ведьмаков, чародеек, лордов, событий и таймеров будет очищено до предыгрового старта."
        : `Будет запущен ${actLabel(actId)}. Если это текущий акт, отсчет начнется заново с 0 минут.`,
      details: [
        ["Акт", actLabel(actId)],
        ["Оператор", operator],
        ...(isRegistrationReset ? [["Итог", "текущий этап станет Регистрация"]] : []),
      ],
      confirmLabel: isRegistrationReset ? "Сбросить в регистрацию" : "Запустить акт",
      danger: true,
    });
    if (!confirmed) return;
    await runAction(
      isRegistrationReset ? "Сбрасываю состояние в регистрацию" : "Запускаю акт",
      () => apiJson("/api/master/game/start-setup", {
        method: "POST",
        body: {
          act_id: actId,
          operator,
          source: isRegistrationReset ? "master_admin_registration_reset" : "master_start_setup",
          physical_announcement_state: "announced",
        },
      }),
      (result) => {
        if (isRegistrationReset) return "Хард-резет выполнен: этап Регистрация";
        if (result.status === "restarted") return `${actLabel(actId)} перезапущен, отсчет идет с 0 минут`;
        if (result.status === "switched") return `Игра переведена на ${actLabel(actId)}`;
        return `Игра запущена: ${actLabel(actId)}`;
      }
    );
  });
  return form;
}

async function hardResetToRegistration(operator = "master") {
  const confirmed = await confirmAction({
    title: "Хард-резет в регистрацию?",
    body: "Админка очистит игровое состояние и вернет ведьмаков и чародеек в предыгровую готовность.",
    details: [
      ["Акт", actLabel(REGISTRATION_ACT_ID)],
      ["Игроков в setup", adminSetupSummary().field_players || 0],
      ["Оператор", operator],
    ],
    confirmLabel: "Сбросить",
    danger: true,
  });
  if (!confirmed) return;
  await runAction(
    "Сбрасываю состояние в регистрацию",
    () => apiJson("/api/master/game/start-setup", {
      method: "POST",
      body: {
        act_id: REGISTRATION_ACT_ID,
        operator,
        source: "master_admin_registration_reset",
        physical_announcement_state: "announced",
      },
    }),
    () => "Хард-резет выполнен: этап Регистрация"
  );
}

function timeControlForm(elapsed) {
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  form.innerHTML = `
    <label class="field">
      <span>Прошло минут акта</span>
      <input id="elapsed-minutes" type="number" min="0" step="1" value="${escapeHtml(elapsed)}">
    </label>
    <label class="field">
      <span>Оператор</span>
      <input id="elapsed-operator" autocomplete="off" value="master">
    </label>
    <button type="submit">Поставить время акта</button>
  `;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const minutes = Number(form.querySelector("#elapsed-minutes").value || 0);
    const operator = form.querySelector("#elapsed-operator").value.trim() || "master";
    const confirmed = await confirmAction({
      title: "Поставить время акта?",
      body: "Текущее время активного акта будет сдвинуто, а подходящие таймеры могут сработать сразу.",
      details: [
        ["Новое время", formatMinutes(minutes)],
        ["Оператор", operator],
      ],
      confirmLabel: "Поставить время",
      danger: true,
    });
    if (!confirmed) return;
    await runAction(
      "Ставлю время акта",
      () => apiJson("/api/master/acts/elapsed", {
        method: "POST",
        body: {
          elapsed_minutes: minutes,
          operator,
        },
      }),
      (result) => `Время акта: ${formatMinutes(result.elapsed_minutes)}`
    );
  });
  return form;
}

function renderLordsView() {
  const domains = lordDomains();
  const attentionDomains = domains.filter((domain) => lordAttention(domain).length);
  const panel = sectionPanel("Пульт наблюдения за лордами", "main-panel lord-command-panel");
  panel.append(heroBlock([
    ["Лордов", domains.length],
    ["Требуют внимания", attentionDomains.length],
    ["Активные бои", activeBattles().length],
    ["Всего войск", domains.reduce((sum, domain) => sum + domainArmyTotal(domain), 0)],
  ]));
  panel.append(actionBar([
    actionButton("Обновить", () => refreshAll(), "secondary"),
    actionButton("Начислить тик", () => applyLordTick()),
    actionButton("Коды игроков", () => switchView("codes"), "secondary"),
    actionButton("Пульт игры", () => switchView("game"), "secondary"),
  ]));
  panel.append(lordAttentionPanel(domains));
  const grid = document.createElement("div");
  grid.className = "lord-command-grid";
  grid.append(...domains.map((domain) => lordCommandCard(domain)));
  panel.append(grid);
  els.workspace.append(panel);

  const editPanel = sectionPanel("Точная правка выбранного лорда", "lord-edit-panel");
  editPanel.append(lordEditForm(domains));
  els.workspace.append(editPanel);
}

function lordAttentionPanel(domains) {
  const wrap = document.createElement("section");
  wrap.className = "lord-attention-board";
  const rows = domains.flatMap((domain) => lordAttention(domain).map((reason) => [
    domainTitle(domain),
    playerTitleById(domain.lord_player_id),
    reason,
  ]));
  wrap.innerHTML = `
    <div>
      <p class="eyebrow">Где смотреть сейчас</p>
      <h4>${rows.length ? "Есть точки внимания" : "Критичных проблем нет"}</h4>
    </div>
  `;
  wrap.append(simpleTable(
    ["Лорд", "Игрок", "Что проверить"],
    rows,
    "Сейчас нет лордов, которые требуют вмешательства"
  ));
  return wrap;
}

function lordCommandCard(domain) {
  const status = lordStatus(domain);
  const alerts = lordAttention(domain);
  const ownedTerritories = territoriesForDomain(domain);
  const card = document.createElement("article");
  card.className = `lord-command-card ${alerts.length ? "attention" : ""}`.trim();
  card.innerHTML = `
    <header class="lord-card-header">
      <div>
        <p class="eyebrow">${escapeHtml(playerTitleById(domain.lord_player_id))}</p>
        <h4>${escapeHtml(domainTitle(domain))}</h4>
      </div>
      <span class="status-badge ${escapeHtml(status.className)}">${escapeHtml(status.label)}</span>
    </header>
    <div class="lord-stat-grid">
      <span><b>${escapeHtml(domain.gold ?? 0)}</b>Золото</span>
      <span><b>${escapeHtml(`${domain.current_mp ?? 0}/${domain.mp_cap ?? 0}`)}</b>MP</span>
      <span><b>${escapeHtml(domainArmyTotal(domain))}</b>Войско</span>
      <span><b>${escapeHtml(ownedBuildings(domain).length)}</b>Здания</span>
      <span><b>${escapeHtml(domain.active_order_count ?? activeOrders(domain).length)}</b>Активные заказы</span>
      <span><b>${escapeHtml(ownedTerritories.length)}</b>Территории</span>
    </div>
    <div class="lord-location-line">
      <b>Локация</b>
      <span>${escapeHtml(domainLocation(domain))}</span>
    </div>
    <div class="lord-alerts ${alerts.length ? "" : "clear"}">
      ${alerts.length
        ? alerts.map((alert) => `<span>${escapeHtml(alert)}</span>`).join("")
        : "<span>состояние стабильное</span>"}
    </div>
    <div class="lord-roster">
      <span><b>Армия</b>${escapeHtml(domainArmySummary(domain))}</span>
      <span><b>Здания</b>${escapeHtml(domainBuildingsSummary(domain))}</span>
      <span><b>Заказы</b>${escapeHtml(domainOrdersSummary(domain))}</span>
      <span><b>Перемещения</b>${escapeHtml(domainMovesSummary(domain))}</span>
    </div>
  `;
  card.append(actionBar([
    actionButton("+50 золота", () => quickPatchDomain(
      domain,
      { gold: Number(domain.gold || 0) + 50 },
      "+50 золота"
    )),
    actionButton("MP максимум", () => quickPatchDomain(
      domain,
      { current_mp: Number(domain.mp_cap || 0) },
      "MP максимум"
    ), "secondary"),
    actionButton("+1 рейд", () => quickPatchDomain(
      domain,
      { raid_tokens: Number(domain.raid_tokens || 0) + 1 },
      "+1 рейд"
    ), "secondary"),
    actionButton("Править", () => focusLordEdit(domain.domain_id), "secondary"),
  ]));
  return card;
}

function switchView(viewId) {
  activeViewId = viewId;
  renderShell();
}

async function quickPatchDomain(domain, patch, label) {
  await saveCorrection(
    "domain",
    domain.domain_id,
    patch,
    `быстрая правка лорда: ${label}`,
    `${domainTitle(domain)}: ${label}`,
    {
      title: `${label}: ${domainTitle(domain)}?`,
      details: changeDetails(patch, domain, LORD_PATCH_LABELS),
    }
  );
}

function focusLordEdit(domainId) {
  const select = els.workspace.querySelector("#lord-id");
  if (!select) return;
  select.value = domainId;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  select.scrollIntoView({ behavior: "smooth", block: "center" });
  select.focus();
}

function lordEditForm(domains) {
  const form = document.createElement("form");
  form.id = "lord-edit-form";
  form.className = "form-grid quick-form";
  form.innerHTML = `
    <label class="field wide">
      <span>Выбрать лорда</span>
      <select id="lord-id">${options(domains.map((domain) => [
        domain.domain_id,
        `${domainTitle(domain)} · золото ${domain.gold ?? 0}`,
      ]))}</select>
    </label>
    <label class="field">
      <span>Золото</span>
      <input id="lord-gold" type="number" min="0" step="1">
    </label>
    <label class="field">
      <span>MP сейчас</span>
      <input id="lord-current-mp" type="number" min="0" step="1">
    </label>
    <label class="field">
      <span>Лимит MP</span>
      <input id="lord-mp-cap" type="number" min="0" step="1">
    </label>
    <label class="field">
      <span>Жетоны рейда</span>
      <input id="lord-raid-tokens" type="number" min="0" step="1">
    </label>
    <button type="submit">Сохранить лорда</button>
  `;
  const select = form.querySelector("#lord-id");
  const fill = () => {
    const domain = domains.find((item) => item.domain_id === select.value);
    if (!domain) return;
    form.querySelector("#lord-gold").value = domain.gold ?? 0;
    form.querySelector("#lord-current-mp").value = domain.current_mp ?? 0;
    form.querySelector("#lord-mp-cap").value = domain.mp_cap ?? 0;
    form.querySelector("#lord-raid-tokens").value = domain.raid_tokens ?? 0;
  };
  select.addEventListener("change", fill);
  fill();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const domain = domains.find((item) => item.domain_id === select.value);
    const patch = numericPatch(form, {
      gold: "#lord-gold",
      current_mp: "#lord-current-mp",
      mp_cap: "#lord-mp-cap",
      raid_tokens: "#lord-raid-tokens",
    }, domain);
    await saveCorrection(
      "domain",
      select.value,
      patch,
      "ручная правка лорда",
      "Лорд сохранён",
      {
        title: `Сохранить правку лорда: ${domainTitle(domain || {})}?`,
        details: changeDetails(patch, domain, LORD_PATCH_LABELS),
      }
    );
  });
  return form;
}

function renderPlayersView() {
  const players = playersList();
  const setupPlayers = setupPlayersList();
  const panel = sectionPanel("Игроки", "main-panel");
  panel.append(summaryCards([
    ["Ведьмаки/чародейки", setupPlayers.length],
    ["Готовы", adminSetupSummary().ready_players || 0],
    ["Нужно внимание", adminSetupSummary().needs_attention || 0],
    ["Выдач", adminSetupGrants().length],
  ]));
  panel.append(filterTabs("player-role-filter", [
    ["all", "Все"],
    ["witcher", "Ведьмаки"],
    ["sorceress", "Чародейки"],
    ["lord", "Лорды"],
  ]));
  const grid = entityGrid(players.map((player) => playerCard(player)));
  grid.id = "players-grid";
  panel.append(grid);
  panel.append(playerEditForm(players));
  panel.append(playerChallengeTokenForm(players));
  panel.append(playerGrantForm(setupPlayers));
  panel.append(playerGoalEditForm(players));
  panel.append(blockTitle("Готовность ведьмаков и чародеек"));
  panel.append(readinessTable(setupPlayers));
  panel.append(blockTitle("Последние выдачи"));
  panel.append(setupGrantTable(adminSetupGrants()));
  els.workspace.append(panel);
  setupPlayerFilter(panel, players);
}

function playerCard(player) {
  const goal = playerGoalsFor(player.player_id)[0];
  const setup = setupPlayerById(player.player_id);
  return entityCard(playerTitle(player), [
    ["Роль", roleLabel(player.role_type)],
    ["Готовность", setup ? readinessLabel(setup) : "не требуется"],
    ["Уровень", player.level ?? 1],
    ["Золото", player.gold ?? 0],
    ["XP", player.xp ?? 0],
    ["Мана", `${player.mana ?? 0}/${player.max_mana ?? 0}`],
    ["Жетоны сражений", player.challenge_tokens ?? 0],
    ["Цель", goal?.public_text || "не задана"],
  ], { role: player.role_type });
}

function playerChallengeTokenForm(players) {
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  if (!players.length) {
    form.innerHTML = `
      <div class="field wide">
        <span>Жетоны сражений</span>
        <p class="status-line">Нет игроков для пополнения жетонов.</p>
      </div>
    `;
    return form;
  }
  form.innerHTML = `
    <label class="field wide">
      <span>Кому пополнить</span>
      <select id="challenge-token-player-id">${options(players.map((player) => [
        player.player_id,
        `${playerTitle(player)} · ${roleLabel(player.role_type)} · жетоны ${player.challenge_tokens ?? 0}`,
      ]))}</select>
    </label>
    <label class="field">
      <span>Добавить жетонов</span>
      <input id="challenge-token-quantity" type="number" min="1" step="1" value="3">
    </label>
    <label class="field wide">
      <span>Причина</span>
      <input id="challenge-token-reason" autocomplete="off" required value="ручное пополнение жетонов сражений">
    </label>
    <button type="submit">Пополнить жетоны</button>
  `;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const playerId = form.querySelector("#challenge-token-player-id").value;
    const player = players.find((item) => item.player_id === playerId);
    if (!player) {
      setDashboardStatus("Выберите игрока для пополнения");
      return;
    }
    const quantity = Number.parseInt(form.querySelector("#challenge-token-quantity").value || "0", 10);
    const reason = form.querySelector("#challenge-token-reason").value.trim();
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setDashboardStatus("Количество жетонов должно быть положительным");
      return;
    }
    if (!reason) {
      setDashboardStatus("Укажите причину пополнения");
      return;
    }
    const currentTokens = Number(player.challenge_tokens ?? 0);
    const nextTokens = currentTokens + quantity;
    const confirmed = await confirmAction({
      title: `Пополнить жетоны: ${playerTitle(player)}?`,
      body: "Жетоны сражений будут прибавлены к текущему балансу игрока.",
      details: [
        ["Игрок", playerTitle(player)],
        ["Сейчас", currentTokens],
        ["Добавить", quantity],
        ["Станет", nextTokens],
        ["Причина", reason],
      ],
      confirmLabel: "Пополнить",
      danger: true,
    });
    if (!confirmed) return;
    await runAction(
      "Пополняю жетоны",
      () => apiJson("/api/master/game-ops/corrections", {
        method: "POST",
        body: {
          target_type: "player",
          target_id: player.player_id,
          patch: { challenge_tokens: nextTokens },
          operator: "master",
          reason,
        },
      }),
      "Жетоны пополнены"
    );
  });
  return form;
}

function playerGrantForm(players) {
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  if (!players.length) {
    form.innerHTML = `
      <div class="field wide">
        <span>Выдача ресурсов</span>
        <p class="status-line">Нет ведьмаков или чародеек для предыгровой выдачи.</p>
      </div>
    `;
    return form;
  }
  form.innerHTML = `
    <label class="field wide">
      <span>Кому выдать</span>
      <select id="grant-player-id">${options(players.map((player) => [
        player.player_id,
        `${playerTitleById(player.player_id, player.display_name)} · ${roleLabel(player.role_type)}`,
      ]))}</select>
    </label>
    <label class="field">
      <span>Тип</span>
      <select id="grant-type">
        <option value="gold">Золото</option>
        <option value="card">Карта</option>
        <option value="item">Предмет</option>
        <option value="artifact">Артефакт</option>
      </select>
    </label>
    <label class="field wide">
      <span>Что выдать</span>
      <select id="grant-asset-id"></select>
    </label>
    <label class="field">
      <span>Количество</span>
      <input id="grant-quantity" type="number" min="1" step="1" value="1">
    </label>
    <label class="field">
      <span>Оператор</span>
      <input id="grant-operator" autocomplete="off" value="master">
    </label>
    <label class="field wide">
      <span>Причина</span>
      <input id="grant-reason" autocomplete="off" required value="предыгровая выдача">
    </label>
    <button type="submit">Выдать ресурс</button>
  `;
  const typeSelect = form.querySelector("#grant-type");
  const assetSelect = form.querySelector("#grant-asset-id");
  const fillAssetOptions = () => {
    const grantType = typeSelect.value;
    const catalog = setupAssetCatalog(grantType);
    assetSelect.disabled = grantType === "gold";
    assetSelect.replaceChildren(...catalog.map((asset) => {
      const option = document.createElement("option");
      option.value = asset.asset_id;
      option.textContent = assetLabel(asset);
      return option;
    }));
    if (grantType === "gold") {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Золото";
      assetSelect.replaceChildren(option);
    }
  };
  typeSelect.addEventListener("change", fillAssetOptions);
  fillAssetOptions();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const playerId = form.querySelector("#grant-player-id").value;
    const grantType = typeSelect.value;
    const quantity = Number(form.querySelector("#grant-quantity").value || 1);
    const assetId = grantType === "gold" ? null : assetSelect.value;
    const operator = form.querySelector("#grant-operator").value.trim() || "master";
    const reason = form.querySelector("#grant-reason").value.trim();
    if (!reason) {
      setDashboardStatus("Укажите причину выдачи");
      return;
    }
    const confirmed = await confirmAction({
      title: `Выдать ресурс: ${playerTitleById(playerId)}?`,
      body: "Выдача попадёт в журнал и обновит состояние игрока.",
      details: [
        ["Игрок", playerTitleById(playerId)],
        ["Тип", grantTypeLabel(grantType)],
        ["Ресурс", grantType === "gold" ? "золото" : assetId],
        ["Количество", quantity],
        ["Оператор", operator],
        ["Причина", reason],
      ],
      confirmLabel: "Выдать",
      danger: true,
    });
    if (!confirmed) return;
    await runAction(
      "Выдаю ресурс",
      () => apiJson("/api/master/admin-setup/grants", {
        method: "POST",
        body: {
          player_id: playerId,
          grant_type: grantType,
          asset_id: assetId,
          quantity,
          operator,
          reason,
        },
      }),
      "Ресурс выдан"
    );
  });
  return form;
}

function playerEditForm(players) {
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  form.innerHTML = `
    <label class="field wide">
      <span>Выбрать игрока</span>
      <select id="player-id">${options(players.map((player) => [
        player.player_id,
        `${playerTitle(player)} · ${roleLabel(player.role_type)} · золото ${player.gold ?? 0}`,
      ]))}</select>
    </label>
    <label class="field">
      <span>Золото</span>
      <input id="player-gold" type="number" min="0" step="1">
    </label>
    <label class="field">
      <span>Уровень</span>
      <input id="player-level" type="number" min="1" step="1">
    </label>
    <label class="field">
      <span>XP</span>
      <input id="player-xp" type="number" min="0" step="1">
    </label>
    <label class="field">
      <span>Мана</span>
      <input id="player-mana" type="number" min="0" step="1">
    </label>
    <button type="submit">Сохранить игрока</button>
  `;
  const select = form.querySelector("#player-id");
  const fill = () => {
    const player = players.find((item) => item.player_id === select.value);
    if (!player) return;
    form.querySelector("#player-gold").value = player.gold ?? 0;
    form.querySelector("#player-level").value = player.level ?? 1;
    form.querySelector("#player-xp").value = player.xp ?? 0;
    form.querySelector("#player-mana").value = player.mana ?? 0;
  };
  select.addEventListener("change", fill);
  fill();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const player = players.find((item) => item.player_id === select.value);
    const patch = numericPatch(form, {
      gold: "#player-gold",
      level: "#player-level",
      xp: "#player-xp",
      mana: "#player-mana",
    }, player);
    await saveCorrection(
      "player",
      select.value,
      patch,
      "ручная правка игрока",
      "Игрок сохранён",
      {
        title: `Сохранить правку игрока: ${playerTitle(player)}?`,
        details: changeDetails(patch, player, {
          gold: "Золото",
          level: "Уровень",
          xp: "XP",
          mana: "Мана",
        }),
      }
    );
  });
  return form;
}

function playerGoalEditForm(players) {
  const goals = playerGoalsList();
  const playersWithGoals = players.filter((player) => playerGoalsFor(player.player_id).length);
  const form = document.createElement("form");
  form.className = "form-grid quick-form";
  if (!playersWithGoals.length || !goals.length) {
    form.innerHTML = `
      <div class="field wide">
        <span>Цели</span>
        <p class="status-line">Для игроков пока нет заведённых целей.</p>
      </div>
    `;
    return form;
  }
  form.innerHTML = `
    <label class="field wide">
      <span>Игрок для цели</span>
      <select id="goal-player-id">${options(playersWithGoals.map((player) => [
        player.player_id,
        `${playerTitle(player)} · ${roleLabel(player.role_type)}`,
      ]))}</select>
    </label>
    <label class="field">
      <span>Цель</span>
      <select id="goal-id"></select>
    </label>
    <label class="field wide">
      <span>Текст цели</span>
      <textarea id="goal-public-text" maxlength="600" required></textarea>
    </label>
    <button type="submit">Сохранить цель</button>
  `;
  const playerSelect = form.querySelector("#goal-player-id");
  const goalSelect = form.querySelector("#goal-id");
  const textArea = form.querySelector("#goal-public-text");
  const fillGoalText = () => {
    const goal = goals.find((item) => item.goal_id === goalSelect.value);
    textArea.value = goal?.public_text || "";
  };
  const fillGoalOptions = () => {
    const playerGoals = playerGoalsFor(playerSelect.value);
    goalSelect.replaceChildren(...playerGoals.map((goal) => {
      const option = document.createElement("option");
      option.value = goal.goal_id;
      option.textContent = `${actLabel(goal.act_id)} · ${goal.public_text || goal.goal_id}`;
      return option;
    }));
    fillGoalText();
  };
  playerSelect.addEventListener("change", fillGoalOptions);
  goalSelect.addEventListener("change", fillGoalText);
  fillGoalOptions();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const goal = goals.find((item) => item.goal_id === goalSelect.value);
    if (!goal) {
      setDashboardStatus("Выберите цель для правки");
      return;
    }
    const nextText = textArea.value.trim();
    if (!nextText) {
      setDashboardStatus("Текст цели не должен быть пустым");
      return;
    }
    const previousText = String(goal.public_text || "");
    const patch = nextText === previousText ? {} : { public_text: nextText };
    await saveCorrection(
      "personal_goal",
      goal.goal_id,
      patch,
      "ручная правка текста цели",
      "Цель сохранена",
      {
        title: `Сохранить цель: ${playerTitleById(goal.player_id)}?`,
        details: [["Текст цели", `${previousText || "-"} -> ${nextText}`]],
      }
    );
  });
  return form;
}

function setupPlayerFilter(panel, players) {
  for (const button of panel.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      for (const item of panel.querySelectorAll("[data-filter]")) {
        item.setAttribute("aria-pressed", String(item === button));
      }
      const role = button.dataset.filter;
      const filtered = role === "all" ? players : players.filter((player) => player.role_type === role);
      const grid = panel.querySelector("#players-grid");
      grid.replaceChildren(...filtered.map((player) => playerCard(player)));
    });
  }
}

function readinessTable(players) {
  return simpleTable(
    ["Игрок", "Роль", "Код", "Цели", "Карты", "Предметы", "Статус"],
    players.map((player) => [
      playerTitleById(player.player_id, player.display_name),
      roleLabel(player.role_type),
      player.player_code_enabled ? "активен" : "нет кода",
      player.goal_count || 0,
      player.asset_counts?.card?.quantity || 0,
      player.asset_counts?.item?.quantity || 0,
      readinessLabel(player),
    ]),
    "Готовность ещё не рассчитана"
  );
}

function setupGrantTable(rows) {
  return simpleTable(
    ["Время", "Игрок", "Тип", "Ресурс", "Количество", "Оператор", "Причина"],
    rows.map((row) => [
      shortDate(row.created_at),
      playerTitleById(row.player_id),
      grantTypeLabel(row.grant_type),
      row.asset_id || "золото",
      row.quantity,
      row.operator,
      row.reason,
    ]),
    "Выдач пока нет"
  );
}

function renderPlayerCodesView() {
  const panel = sectionPanel("Коды игроков", "main-panel");
  panel.append(heroBlock([
    ["Продакшен-сервер", playerServerUrl()],
    ["Вход лордов", playerLoginUrl()],
    ["Всего кодов", playerCodes.total || 0],
    ["Активные", playerCodes.enabled_count || 0],
  ]));
  panel.append(actionBar([
    actionButton("Скопировать все коды", () => copyAllPlayerCodes()),
    actionButton("Обновить", () => refreshAll(), "secondary"),
  ]));
  const grid = document.createElement("div");
  grid.className = "code-grid";
  grid.append(...(playerCodes.items || []).map((item) => playerCodeCard(item)));
  panel.append(grid);
  els.workspace.append(panel);
}

function playerCodeCard(item) {
  const card = document.createElement("article");
  card.className = "code-card";
  card.innerHTML = `
    <div>
      <h5>${escapeHtml(item.display_name || item.player_id)}</h5>
      <p>${escapeHtml(roleLabel(item.role_type))}</p>
    </div>
    <code>${escapeHtml(item.code)}</code>
    <span class="status-badge ${item.enabled ? "ready" : "warn"}">${item.enabled ? "активен" : "выключен"}</span>
  `;
  card.append(actionBar([
    actionButton("Копировать код", () => copyText(item.code, "Код скопирован"), "secondary"),
    actionButton("Скопировать сообщение", () => copyText(playerCodeMessage(item), "Сообщение скопировано")),
  ]));
  return card;
}

function playerCodeMessage(item) {
  return [
    `${item.display_name || item.player_id}, твой код входа: ${item.code}`,
    `Вход лордов на продакшен-сервере: ${playerLoginUrl()}`,
    "Открой ссылку и введи этот код.",
  ].join("\n");
}

function playerServerUrl() {
  return playerCodes.server_url || location.origin;
}

function playerLoginUrl() {
  return playerCodes.player_login_url || `${location.origin}/lords/login`;
}

function copyAllPlayerCodes() {
  const lines = [
    `Продакшен-сервер: ${playerServerUrl()}`,
    `Вход лордов: ${playerLoginUrl()}`,
    "",
    ...(playerCodes.items || []).map((item) => {
    return `${item.display_name || item.player_id} — ${roleLabel(item.role_type)} — ${item.code}`;
    }),
  ];
  copyText(lines.join("\n"), "Все коды скопированы");
}

function renderReviewView() {
  const panel = sectionPanel("Ревью и бои", "main-panel");
  panel.append(summaryCards([
    ["Активные бои", activeBattles().length],
    ["События", eventReviewItems().length],
    ["Заказы", orderReviewItems().length],
    ["Награды", rewardItems().length],
    ["Критичные", criticalReviewCount()],
  ]));
  panel.append(blockTitle("Бои лордов"));
  panel.append(simpleTable(
    ["Бой", "Территория", "Атакует", "Защищает", "Статус"],
    activeBattles().map((battle) => [
      battle.battle_id,
      battle.territory_id || "-",
      domainTitleById(battle.attacker_domain_id),
      battle.defender_domain_id ? domainTitleById(battle.defender_domain_id) : "нейтрально",
      humanStatus(battle.status),
    ]),
    "Активных боёв нет"
  ));
  panel.append(blockTitle("Заказы на проверке"));
  panel.append(orderReviewTable(orderReviewItems()));
  panel.append(blockTitle("События на проверке"));
  panel.append(reviewTable(eventReviewItems()));
  panel.append(blockTitle("Сценарные решения"));
  panel.append(npcReviewTable(npcReviewItems()));
  panel.append(blockTitle("Награды на подтверждении"));
  panel.append(rewardTable(rewardItems()));
  els.workspace.append(panel);
}

function reviewTable(rows) {
  const table = actionTable(
    ["Событие", "Важность", "Причина", "Действие"],
    rows,
    (row) => [
      row.event_id,
      row.severity,
      row.reason || "-",
      actionBar([
        actionButton("Одобрить", () => decideEvent(row, "approve"), "secondary"),
        actionButton("Отклонить", () => decideEvent(row, "reject"), "danger"),
      ]),
    ],
    "Событий на проверке нет"
  );
  return table;
}

function orderReviewTable(rows) {
  return actionTable(
    ["Заказ", "Лорд", "Игрок", "Статус", "Причина", "Действие"],
    rows,
    (row) => [
      row.order_id,
      domainTitleById(row.domain_id) || playerTitleById(row.lord_id),
      playerTitleById(row.submitted_by_player_id || row.accepted_by_player_id || row.target_player_id),
      humanStatus(row.status),
      row.reason || "-",
      orderActions(row),
    ],
    "Заказов на проверке нет"
  );
}

function npcReviewTable(rows) {
  return simpleTable(
    ["NPC", "Событие", "Важность", "Статус", "Причина"],
    rows.map((row) => [
      row.npc_role,
      row.event_type,
      row.severity,
      humanStatus(row.status),
      row.reason || row.meaning || "-",
    ]),
    "NPC-решений на проверке нет"
  );
}

function orderActions(row) {
  const hints = row.action_hints || [];
  const buttons = [];
  if (hints.includes("complete")) {
    buttons.push(actionButton("Завершить", () => decideOrder(row, "complete"), "secondary"));
  }
  if (hints.includes("fail_retryable")) {
    buttons.push(actionButton("Повторить", () => decideOrder(row, "fail_retryable"), "secondary"));
  }
  if (hints.includes("contested_review")) {
    buttons.push(actionButton("Оспорить", () => decideOrder(row, "contested_review"), "secondary"));
  }
  if (hints.includes("fail_closed")) {
    buttons.push(actionButton("Закрыть", () => decideOrder(row, "fail_closed"), "danger"));
  }
  return buttons.length ? actionBar(buttons) : document.createTextNode("нет действий");
}

function rewardTable(rows) {
  return actionTable(
    ["Награда", "Игрок", "Важность", "Действие"],
    rows,
    (row) => [
      row.reward_id,
      playerTitleById(row.player_id),
      row.severity,
      actionBar([
        actionButton("Одобрить", () => decideReward(row, "approve"), "secondary"),
        actionButton("Отклонить", () => decideReward(row, "reject"), "danger"),
      ]),
    ],
    "Наград на подтверждении нет"
  );
}

function renderContentView() {
  const panel = sectionPanel("Генерация и подготовка контента", "main-panel");
  panel.append(heroBlock([
    ["Статус контента", overview?.snapshot_version ? "готов" : "не загружен"],
    ["QR", contentState?.qr?.total ?? "-"],
    ["Памятки", contentState?.handouts?.items?.length ?? "-"],
    ["Ошибки", contentState?.report?.error_count ?? "-"],
  ]));
  panel.append(actionBar([
    actionButton("Обновить игровой контент", () => importDefaultContent()),
    actionButton("Проверить готовность", () => loadContentState(), "secondary"),
  ]));
  const result = document.createElement("section");
  result.id = "content-result";
  result.className = "content-result";
  panel.append(result);
  els.workspace.append(panel);
  renderContentResult(result);
  if (!contentState) loadContentState();
}

async function loadContentState() {
  await runAction(
    "Проверяю контент",
    async () => {
      const [report, qr, handouts] = await Promise.all([
        apiJson("/api/master/content/import-report/latest"),
        apiJson("/api/master/content/qr-checklist"),
        apiJson("/api/master/content/handout-checklist"),
      ]);
      contentState = { report, qr, handouts };
      return contentState;
    },
    "Контент проверен",
    { rerender: false }
  );
  const result = els.workspace.querySelector("#content-result");
  if (result) renderContentResult(result);
  renderTopSummary();
}

async function importDefaultContent() {
  const confirmed = await confirmAction({
    title: "Обновить игровой контент?",
    body: "Будет загружен основной набор контента и создан свежий игровой снимок.",
    details: [
      ["Текущий статус", overview?.snapshot_version ? "контент уже загружен" : "контент не загружен"],
      ["После действия", "контент будет перечитан"],
    ],
    confirmLabel: "Обновить контент",
    danger: true,
  });
  if (!confirmed) return;
  await runAction(
    "Обновляю контент",
    () => apiJson("/api/master/content/import", {
      method: "POST",
      body: { manifest_path: null, export_snapshot: true },
    }),
    (result) => result.error_count ? `Есть ошибки: ${result.error_count}` : "Контент обновлён"
  );
  await loadContentState();
}

function renderContentResult(root) {
  root.replaceChildren();
  if (!contentState) {
    root.append(emptyLine("Нажмите «Проверить готовность», чтобы увидеть состояние контента."));
    return;
  }
  root.append(summaryCards([
    ["Статус", humanStatus(contentState.report?.status || "not_imported")],
    ["Ошибки", contentState.report?.error_count || 0],
    ["QR готовы", contentState.qr?.total || 0],
    ["Памятки", contentState.handouts?.items?.length || 0],
  ]));
  root.append(simpleTable(
    ["Проверка", "Состояние"],
    [
      ["QR и ручные коды", contentState.qr?.status === "ready" ? "готово" : "нужно внимание"],
      ["Памятки игрокам", contentState.handouts?.status === "ready" ? "готово" : "нужно внимание"],
      ["Последнее обновление", shortDate(contentState.report?.finished_at || contentState.report?.started_at)],
    ],
    "Проверок пока нет"
  ));
  if (contentState.report?.errors?.length) {
    root.append(blockTitle("Что исправить"));
    root.append(simpleTable(
      ["Раздел", "Запись", "Проблема"],
      contentState.report.errors.slice(0, 8).map((error) => [
        contentSourceName(error.file),
        error.record_id || "-",
        error.message || error.code,
      ]),
      "Ошибок нет"
    ));
  }
}

async function applyLordTick() {
  const confirmed = await confirmAction({
    title: "Начислить тик лордам?",
    body: "Доход, мана и MP лордов будут начислены прямо сейчас.",
    details: [
      ["Лордов", lordDomains().length],
      ["Текущий акт", actLabel(masterState?.acts?.state?.current_act_id || "not_started")],
    ],
    confirmLabel: "Начислить тик",
    danger: true,
  });
  if (!confirmed) return;
  await runAction(
    "Начисляю доход лордам",
    () => apiJson("/api/master/timers/lord-income-tick", {
      method: "POST",
      body: { operator: "master" },
    }),
    (result) => {
      const tick = (result.applied_now || [])[0] || {};
      return `Доход начислен: ${(tick.domain_updates || []).length} лордов`;
    }
  );
}

async function saveCorrection(targetType, targetId, patch, reason, successText, confirmation = {}) {
  if (!targetId) {
    setDashboardStatus("Выберите запись для правки");
    return;
  }
  if (!Object.keys(patch).length) {
    setDashboardStatus("Нет изменений для сохранения");
    return;
  }
  const confirmed = await confirmAction({
    title: confirmation.title || "Сохранить правку?",
    body: "Будут изменены только перечисленные поля.",
    details: confirmation.details || Object.entries(patch),
    confirmLabel: "Сохранить",
    danger: true,
  });
  if (!confirmed) return;
  await runAction(
    "Сохраняю правку",
    () => apiJson("/api/master/game-ops/corrections", {
      method: "POST",
      body: {
        target_type: targetType,
        target_id: targetId,
        patch,
        operator: "master",
        reason,
      },
    }),
    successText
  );
}

async function decideEvent(row, action) {
  const confirmed = await confirmAction({
    title: action === "approve" ? "Одобрить событие?" : "Отклонить событие?",
    body: "Решение уйдёт в журнал ревью и обновит состояние очереди.",
    details: [
      ["Событие", row.event_id],
      ["Важность", row.severity],
      ["Причина", row.reason || "-"],
    ],
    confirmLabel: action === "approve" ? "Одобрить" : "Отклонить",
    danger: action !== "approve",
  });
  if (!confirmed) return;
  await runAction(
    action === "approve" ? "Одобряю событие" : "Отклоняю событие",
    () => apiJson(`/api/events/${encodeURIComponent(row.event_id)}/review`, {
      method: "POST",
      body: {
        action,
        operator: "master",
        reason: action === "approve" ? "проверено мастером" : "отклонено мастером",
        severity: row.severity,
        correction: {},
      },
    }),
    "Ревью события обновлено"
  );
}

async function decideReward(row, action) {
  const confirmed = await confirmAction({
    title: action === "approve" ? "Одобрить награду?" : "Отклонить награду?",
    body: "Решение изменит статус награды игрока.",
    details: [
      ["Награда", row.reward_id],
      ["Игрок", playerTitleById(row.player_id)],
      ["Важность", row.severity],
    ],
    confirmLabel: action === "approve" ? "Одобрить" : "Отклонить",
    danger: action !== "approve",
  });
  if (!confirmed) return;
  await runAction(
    action === "approve" ? "Одобряю награду" : "Отклоняю награду",
    () => apiJson(`/api/master/reward-approvals/${encodeURIComponent(row.approval_id)}`, {
      method: "POST",
      body: {
        action,
        operator: "master",
        reason: action === "approve" ? "проверено мастером" : "отклонено мастером",
        correction: {},
      },
    }),
    "Решение по награде сохранено"
  );
}

async function decideOrder(row, action) {
  const labels = {
    complete: "Завершить заказ",
    fail_retryable: "Вернуть в повтор",
    contested_review: "Отправить в спор",
    fail_closed: "Закрыть провалом",
  };
  const reason = labels[action] || "решение мастера";
  const confirmed = await confirmAction({
    title: `${reason}?`,
    body: "Решение изменит состояние заказа на общей доске.",
    details: [
      ["Заказ", row.order_id],
      ["Лорд", domainTitleById(row.domain_id) || playerTitleById(row.lord_id)],
      ["Игрок", playerTitleById(row.submitted_by_player_id || row.accepted_by_player_id || row.target_player_id)],
      ["Текущий статус", humanStatus(row.status)],
    ],
    confirmLabel: reason,
    danger: action === "fail_closed",
  });
  if (!confirmed) return;
  await runAction(
    "Сохраняю решение по заказу",
    () => apiJson(`/api/master/orders/${encodeURIComponent(row.order_id)}/resolve`, {
      method: "POST",
      body: {
        action,
        player_id: row.submitted_by_player_id || row.accepted_by_player_id || row.target_player_id || null,
        result_event_id: row.result_event_id || null,
        operator: "master",
        reason: reason.toLowerCase(),
      },
    }),
    "Решение по заказу сохранено"
  );
}

async function runAction(label, task, formatter = null, options = {}) {
  setDashboardStatus(label);
  try {
    const result = await task();
    if (options.rerender !== false) await refreshAll();
    const message = typeof formatter === "function" ? formatter(result) : formatter;
    setDashboardStatus(message || "Готово");
    return result;
  } catch (error) {
    setDashboardStatus(error.message);
    return null;
  }
}

function pageHeader(title, subtitle) {
  const header = document.createElement("div");
  header.className = "workspace-heading";
  header.innerHTML = `
    <div>
      <p class="eyebrow">${escapeHtml(subtitle)}</p>
      <h3>${escapeHtml(title)}</h3>
    </div>
  `;
  return header;
}

function sectionPanel(title, extraClass = "") {
  const panel = document.createElement("section");
  panel.className = `ops-panel ${extraClass}`.trim();
  const heading = document.createElement("h4");
  heading.textContent = title;
  panel.append(heading);
  return panel;
}

function heroBlock(items) {
  const hero = document.createElement("div");
  hero.className = "control-hero";
  hero.append(...items.map(([label, value]) => {
    const item = document.createElement("span");
    item.innerHTML = `<b>${escapeHtml(value)}</b>${escapeHtml(label)}`;
    return item;
  }));
  return hero;
}

function summaryCards(items) {
  const grid = document.createElement("div");
  grid.className = "compact-summary";
  for (const [label, value] of items) {
    const item = document.createElement("span");
    item.innerHTML = `<b>${escapeHtml(label)}</b>${escapeHtml(value)}`;
    grid.append(item);
  }
  return grid;
}

function entityGrid(cards) {
  const grid = document.createElement("div");
  grid.className = "entity-grid";
  grid.append(...cards);
  return grid;
}

function entityCard(title, rows, dataset = {}) {
  const card = document.createElement("article");
  card.className = "entity-card";
  for (const [key, value] of Object.entries(dataset)) {
    card.dataset[key] = value;
  }
  card.innerHTML = `
    <h5>${escapeHtml(title)}</h5>
    <div class="entity-facts">
      ${rows.map(([label, value]) => `
        <span><b>${escapeHtml(label)}</b>${escapeHtml(value)}</span>
      `).join("")}
    </div>
  `;
  return card;
}

function filterTabs(name, items) {
  const wrapper = document.createElement("div");
  wrapper.className = "filter-tabs";
  for (const [id, label] of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.dataset.filter = id;
    button.setAttribute("aria-pressed", String(id === "all"));
    button.textContent = label;
    wrapper.append(button);
  }
  return wrapper;
}

function actionBar(buttons) {
  const bar = document.createElement("div");
  bar.className = "inline-actions";
  bar.append(...buttons);
  return bar;
}

function actionButton(label, handler, variant = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  if (variant) button.className = variant;
  button.addEventListener("click", handler);
  return button;
}

async function copyText(text, successMessage) {
  let copied = false;
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      copied = false;
    }
  }
  if (!copied) copied = copyTextFallback(text);
  setDashboardStatus(copied ? successMessage : text);
}

function copyTextFallback(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}

function confirmAction({ title, body, details = [], confirmLabel = "Подтвердить", danger = false }) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-backdrop";
    overlay.innerHTML = `
      <section class="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div>
          <p class="eyebrow">Подтверждение</p>
          <h3 id="confirm-title">${escapeHtml(title)}</h3>
        </div>
        <p>${escapeHtml(body || "Подтвердите действие.")}</p>
        ${details.length ? `
          <dl class="confirm-details">
            ${details.map(([label, value]) => `
              <div>
                <dt>${escapeHtml(label)}</dt>
                <dd>${escapeHtml(value)}</dd>
              </div>
            `).join("")}
          </dl>
        ` : ""}
        <div class="modal-actions">
          <button type="button" class="secondary" data-confirm="cancel">Отмена</button>
          <button type="button" class="${danger ? "danger" : ""}" data-confirm="ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </section>
    `;
    const finish = (value) => {
      overlay.remove();
      document.removeEventListener("keydown", onKeydown);
      resolve(value);
    };
    const onKeydown = (event) => {
      if (event.key === "Escape") finish(false);
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) finish(false);
      const action = event.target?.dataset?.confirm;
      if (action === "cancel") finish(false);
      if (action === "ok") finish(true);
    });
    document.addEventListener("keydown", onKeydown);
    document.body.append(overlay);
    overlay.querySelector("[data-confirm='cancel']").focus();
  });
}

function blockTitle(title) {
  const heading = document.createElement("h4");
  heading.textContent = title;
  return heading;
}

function simpleTable(headers, rows, emptyText) {
  return actionTable(headers, rows, (row) => row, emptyText);
}

function actionTable(headers, rows, mapper, emptyText) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>`;
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = headers.length;
    cell.textContent = emptyText;
    row.append(cell);
    tbody.append(row);
  } else {
    for (const sourceRow of rows) {
      const tr = document.createElement("tr");
      for (const value of mapper(sourceRow)) {
        const td = document.createElement("td");
        if (value instanceof Node) {
          td.append(value);
        } else {
          td.textContent = value ?? "-";
        }
        tr.append(td);
      }
      tbody.append(tr);
    }
  }
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}

function emptyLine(text) {
  const line = document.createElement("p");
  line.className = "muted-line";
  line.textContent = text;
  return line;
}

function playersList() {
  return masterState?.economy?.player_economy || [];
}

function adminSetupState() {
  return masterState?.admin_setup || {};
}

function adminSetupSummary() {
  return adminSetupState().summary || {};
}

function setupPlayersList() {
  return adminSetupState().players || [];
}

function setupPlayerById(playerId) {
  return setupPlayersList().find((player) => player.player_id === playerId);
}

function setupAssetCatalog(type) {
  return adminSetupState().asset_catalog?.[type] || [];
}

function adminSetupGrants() {
  return adminSetupState().recent_grants || [];
}

function playerGoalsList() {
  return masterState?.economy?.personal_goals || [];
}

function playerGoalsFor(playerId) {
  return playerGoalsList().filter((goal) => goal.player_id === playerId);
}

function lordDomains() {
  return masterState?.lord_map?.domains || [];
}

function activeBattles() {
  return (lordBattles?.items || []).filter((battle) => !["finished", "cancelled"].includes(String(battle.status)));
}

function activeBattlesForDomain(domain) {
  return activeBattles().filter((battle) => {
    return battle.attacker_domain_id === domain.domain_id || battle.defender_domain_id === domain.domain_id;
  });
}

function territoriesList() {
  return masterState?.lord_map?.territories || [];
}

function territoriesForDomain(domain) {
  return territoriesList().filter((territory) => territory.owner_domain_id === domain.domain_id);
}

function territoryByNode(nodeId) {
  return territoriesList().find((territory) => territory.node_id === nodeId);
}

function contestedClaimsForDomain(domain) {
  return (masterState?.lord_map?.contested_claims || []).filter((claim) => {
    return claim.claimant_domain_id === domain.domain_id || claim.defender_domain_id === domain.domain_id;
  });
}

function pendingMoves(domain) {
  return (domain.pending_moves || []).filter((move) => {
    return !["completed", "cancelled", "failed"].includes(String(move.status || ""));
  });
}

function stalledMoves(domain) {
  const now = Date.now();
  return pendingMoves(domain).filter((move) => {
    const arrival = Date.parse(move.arrival_at);
    return Number.isFinite(arrival) && arrival < now;
  });
}

function activeOrders(domain) {
  const activeStatuses = new Set([
    "published",
    "addressed_pending",
    "accepted",
    "in_progress",
    "claimed_at_prop",
    "submitted_pending_sync",
    "pending_master_approval",
    "failed_retryable",
    "contested_review",
  ]);
  return (domain.orders || []).filter((order) => activeStatuses.has(String(order.status || "")));
}

function lordAttention(domain) {
  const alerts = [];
  if (stalledMoves(domain).length) alerts.push("переход просрочен, проверьте локацию армии");
  if (activeBattlesForDomain(domain).length) alerts.push("идёт бой");
  if (contestedClaimsForDomain(domain).length) alerts.push("есть спорная территория");
  if (!domain.current_node_id) alerts.push("не задана текущая локация");
  if (Number(domain.current_mp || 0) <= 0 && Number(domain.mp_cap || 0) > 0) alerts.push("MP закончились");
  if (domainArmyTotal(domain) <= 0 && masterState?.acts?.state?.current_act_id !== "registration") {
    alerts.push("нет войск на карте и в резерве");
  }
  if (Number(domain.gold || 0) < 0) alerts.push("золото ушло в минус");
  return alerts;
}

function lordStatus(domain) {
  if (lordAttention(domain).length) return { label: "внимание", className: "warn" };
  if (pendingMoves(domain).length) return { label: "в пути", className: "pending" };
  return { label: "стабильно", className: "ready" };
}

function ownedBuildings(domain) {
  return domain.buildings?.owned || [];
}

function buildingCatalogById(domain) {
  return new Map((domain.buildings?.catalog || []).map((building) => [building.building_id, building]));
}

function buildingTitle(building) {
  return building?.name || building?.building_id || "-";
}

function unitTitle(row) {
  return row?.card_name || row?.name || row?.card_id || "-";
}

function domainLocation(domain) {
  if (domain.current_node?.name) return domain.current_node.name;
  const territory = territoryByNode(domain.current_node_id);
  return territory?.node_name || domain.current_node_id || "локация не задана";
}

function domainArmySummary(domain) {
  const rows = [
    ...(domain.active_army || []).map((row) => `${unitTitle(row)} x${row.count || 0} в поле`),
    ...(domain.reserve || []).map((row) => `${unitTitle(row)} x${row.count || 0} в резерве`),
    ...(domain.garrisons || []).map((row) => `${unitTitle(row)} x${row.count || 0} гарнизон`),
  ].filter(Boolean);
  return previewText(rows, "войск нет");
}

function domainBuildingsSummary(domain) {
  const catalog = buildingCatalogById(domain);
  const rows = ownedBuildings(domain).map((row) => buildingTitle(catalog.get(row.building_id) || row));
  return previewText(rows, "зданий нет");
}

function domainOrdersSummary(domain) {
  const active = activeOrders(domain);
  const rows = active.map((order) => `${order.object_id || order.order_id}: ${humanStatus(order.status)}`);
  if (!rows.length) return "активных заказов нет";
  return `${active.length} активных; ${previewText(rows, "")}`;
}

function domainMovesSummary(domain) {
  const moves = pendingMoves(domain);
  const rows = moves.map((move) => {
    const from = nodeTitle(move.from_node_id);
    const to = nodeTitle(move.to_node_id);
    return `${from} -> ${to}`;
  });
  return previewText(rows, "на месте");
}

function nodeTitle(nodeId) {
  const territory = territoryByNode(nodeId);
  return territory?.node_name || nodeId || "-";
}

function previewText(rows, emptyText) {
  if (!rows.length) return emptyText;
  const visible = rows.slice(0, 3);
  const rest = rows.length - visible.length;
  return rest > 0 ? `${visible.join(", ")} +${rest}` : visible.join(", ");
}

function reviewItems() {
  if (Array.isArray(reviewQueue?.items)) return reviewQueue.items;
  return masterState?.events?.review?.open_items || [];
}

function eventReviewItems() {
  return reviewItems().filter((item) => !item.queue_type || item.queue_type === "event_review");
}

function orderReviewItems() {
  return reviewItems().filter((item) => item.queue_type === "lord_order");
}

function masterOrderItems() {
  const queued = orderReviewItems();
  if (queued.length) return queued;
  return lordDomains().flatMap((domain) => {
    return activeOrders(domain).map((order) => ({
      queue_type: "lord_order",
      order_id: order.order_id,
      lord_id: order.lord_id,
      domain_id: domain.domain_id,
      target_player_id: order.target_player_id,
      accepted_by_player_id: order.accepted_by_player_id,
      submitted_by_player_id: order.submitted_by_player_id,
      object_id: order.object_id,
      visibility: order.visibility,
      status: order.status,
      escrow_reward_id: order.escrow_reward_id,
      result_event_id: order.result_event_id,
      reason: order.reason,
      severity: ["pending_master_approval", "contested_review", "submitted_pending_sync"].includes(String(order.status))
        ? "P1"
        : "P2",
      action_hints: orderActionHints(String(order.status)),
      created_at: order.created_at,
      updated_at: order.updated_at,
    }));
  });
}

function npcReviewItems() {
  return reviewItems().filter((item) => item.queue_type === "npc_event");
}

function criticalReviewCount() {
  return reviewItems().filter((item) => ["P0", "P1"].includes(String(item.severity || ""))).length;
}

function rewardItems() {
  return masterState?.reward_approvals?.pending || [];
}

function actOptions() {
  const current = masterState?.acts?.state?.current_act_id || "act1";
  const acts = [...(masterState?.acts?.acts || [])];
  if (!acts.some((act) => act.act_id === REGISTRATION_ACT_ID)) {
    acts.unshift({ act_id: REGISTRATION_ACT_ID });
  }
  return acts
    .map((act) => `<option value="${escapeHtml(act.act_id)}"${act.act_id === current ? " selected" : ""}>${escapeHtml(actLabel(act.act_id))}</option>`)
    .join("");
}

function options(items) {
  if (!items.length) return `<option value="">Нет записей</option>`;
  return items.map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join("");
}

function numericPatch(root, fields, source = {}) {
  const patch = {};
  for (const [field, selector] of Object.entries(fields)) {
    const raw = root.querySelector(selector).value;
    if (raw === "") continue;
    const next = Number(raw);
    const previous = Number(source?.[field] ?? 0);
    if (Number.isFinite(next) && next !== previous) patch[field] = next;
  }
  return patch;
}

function changeDetails(patch, source, labels) {
  return Object.entries(patch).map(([field, value]) => [
    labels[field] || field,
    `${source?.[field] ?? "-"} -> ${value}`,
  ]);
}

function elapsedMinutes(startedAt) {
  if (!startedAt) return 0;
  const started = Date.parse(startedAt);
  if (!Number.isFinite(started)) return 0;
  return Math.max(0, Math.floor((Date.now() - started) / 60000));
}

function formatMinutes(value) {
  const minutes = Math.max(0, Number(value || 0));
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} ч ${rest} мин` : `${rest} мин`;
}

function domainTitle(domain) {
  return domain.display_name || domain.name || domain.domain_id || "Домен";
}

function domainTitleById(domainId) {
  const domain = lordDomains().find((item) => item.domain_id === domainId);
  return domain ? domainTitle(domain) : domainId || "-";
}

function playerTitle(player) {
  if (!player) return "-";
  return playerTitleById(player.player_id, player.display_name);
}

function playerTitleById(playerId, displayName = "") {
  const player = playersList().find((item) => item.player_id === playerId);
  return player?.display_name || displayName || playerId || "-";
}

function armyTotal(domain) {
  return domainArmyTotal(domain);
}

function domainArmyTotal(domain) {
  return sumRows(domain.reserve) + sumRows(domain.active_army) + sumRows(domain.garrisons);
}

function sumRows(rows) {
  return (rows || []).reduce((sum, row) => sum + Number(row.count || 0), 0);
}

function readinessLabel(player) {
  if (!player) return "-";
  if (player.readiness_status === "ready") return "готов";
  const missing = player.readiness_missing || [];
  if (!missing.length) return "нужно внимание";
  const labels = {
    player_code_enabled: "код",
    runtime_ready: "runtime",
    snapshot_ready: "снапшот",
    goals_ready: "цель",
  };
  return `нет: ${missing.map((item) => labels[item] || item).join(", ")}`;
}

function grantTypeLabel(type) {
  const labels = {
    gold: "золото",
    card: "карта",
    item: "предмет",
    artifact: "артефакт",
  };
  return labels[type] || type || "-";
}

function orderActionHints(status) {
  if (["pending_master_approval", "submitted_pending_sync"].includes(status)) {
    return ["complete", "fail_retryable", "contested_review"];
  }
  if (status === "contested_review") return ["fail_closed", "fail_retryable"];
  if (status === "failed_retryable") return ["contested_review", "fail_closed"];
  return ["contested_review", "fail_closed"];
}

function assetLabel(asset) {
  if (!asset) return "-";
  const bits = [asset.label || asset.asset_id];
  if (asset.tier) bits.push(`T${asset.tier}`);
  if (asset.item_type) bits.push(asset.item_type);
  return bits.filter(Boolean).join(" · ");
}

function roleLabel(role) {
  const labels = {
    lord: "лорд",
    sorceress: "чародейка",
    witcher: "ведьмак",
    npc_master: "мастер",
  };
  return labels[role] || role || "-";
}

function humanStatus(status) {
  const labels = {
    active: "активно",
    pending: "ожидает",
    announced: "объявлено",
    ready: "готово",
    success: "готово",
    not_imported: "не загружено",
    pending_master_approval: "ждёт мастера",
    needs_attention: "нужно внимание",
    needs_master_review: "нужен мастер",
    not_started: "игра не начата",
    published: "на доске",
    addressed_pending: "адресный",
    accepted: "принят",
    in_progress: "в работе",
    claimed_at_prop: "у объекта",
    submitted_pending_sync: "сдан, ждёт",
    failed_retryable: "можно повторить",
    contested_review: "спор",
    completed: "выполнен",
    failed_closed: "закрыт провалом",
  };
  return labels[status] || status || "-";
}

function actLabel(actId) {
  const labels = {
    not_started: "не начата",
    registration: "Регистрация",
    act1: "Акт 1",
    act2: "Акт 2",
    act3: "Акт 3",
    final_lock: "Подготовка финала",
    final_act: "Финал",
    debrief: "Разбор игры",
  };
  return labels[actId] || actId || "не начата";
}

function shortDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function contentSourceName(value) {
  if (!value) return "-";
  const normalized = String(value).replaceAll("\\", "/");
  const name = normalized.split("/").pop() || normalized;
  return name.replace(/\.[^.]+$/, "") || name;
}

function viewIntro(viewId) {
  const intros = {
    setup: "выдача карт, предметов, золота и готовность игроков",
    orders: "заказы лордов, награды и спорные решения",
    game: "запуск, время и общий ход игры",
    lords: "наблюдение и быстрые правки лордов",
    players: "наблюдение и быстрые правки игроков",
    codes: "коды входа для отправки игрокам",
    review: "бои, спорные события и награды",
    content: "подготовка игрового контента",
  };
  return intros[viewId] || "мастерский раздел";
}

function viewBadgeText(viewId) {
  if (viewId === "setup") {
    const summary = adminSetupSummary();
    return summary.needs_attention ? `${summary.needs_attention}!` : "готово";
  }
  if (viewId === "orders") return String(masterOrderItems().length || 0);
  if (viewId === "review") {
    const total = reviewItems().length + rewardItems().length + activeBattles().length;
    return total ? String(total) : "чисто";
  }
  if (viewId === "lords") {
    const attention = lordDomains().filter((domain) => lordAttention(domain).length).length;
    return attention ? `${attention}!` : String(lordDomains().length || 0);
  }
  if (viewId === "players") return String(playersList().length || 0);
  if (viewId === "codes") return String(playerCodes.enabled_count || playerCodes.total || playersList().length || 0);
  if (viewId === "content") return overview?.snapshot_version ? "готово" : "нет";
  return actLabel(masterState?.acts?.state?.current_act_id || "not_started");
}

function viewBadgeClass(viewId) {
  if (viewId === "setup") return adminSetupSummary().needs_attention ? "warn" : "ready";
  if (viewId === "orders") return masterOrderItems().length ? "warn" : "ready";
  if (viewId === "review") {
    return reviewItems().length + rewardItems().length + activeBattles().length ? "warn" : "ready";
  }
  if (viewId === "lords") {
    return lordDomains().some((domain) => lordAttention(domain).length) ? "warn" : "ready";
  }
  if (viewId === "content" && !overview?.snapshot_version) return "warn";
  return "ready";
}

function setLoginStatus(message) {
  els.loginStatus.textContent = message || "";
}

function setDashboardStatus(message) {
  els.dashboardStatus.textContent = message || "";
}

async function apiJson(url, options = {}) {
  const requestOptions = {
    method: options.method || "GET",
    headers: {
      "X-Role-Token": session?.token || "",
    },
  };
  if (options.body !== undefined) {
    requestOptions.headers["Content-Type"] = "application/json";
    requestOptions.body = JSON.stringify(options.body);
  }
  const response = await fetch(url, requestOptions);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorMessage(data, response.status));
  return data;
}

function errorMessage(data, status) {
  const detail = data.detail;
  if (detail && typeof detail === "object") {
    return detail.message || detail.code || `Ошибка запроса: ${status}`;
  }
  return detail || `Ошибка запроса: ${status}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
