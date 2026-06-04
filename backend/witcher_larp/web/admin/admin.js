const TOKEN_KEY = "witcher_larp_admin_token";
const VISIBILITY_AUDIT_ENDPOINT = "/api/master/visibility-audit";

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

let session = null;
let overview = null;
let masterState = null;
let finalSummary = null;
let activeSectionId = "content";
let contentRenderId = 0;

const PAPER_FORM_TYPES = [
  ["paper_pve_result", "Paper PvE result"],
  ["paper_pvp_stake", "Paper PvP stake"],
  ["paper_lord_action", "Paper lord action"],
  ["paper_lord_battle", "Paper lord battle"],
  ["paper_order_resolution", "Paper order resolution"],
  ["paper_npc_deal", "Paper NPC deal"],
  ["paper_final_evidence", "Paper final evidence"],
];

const PAPER_CONFLICT_STATUSES = [
  ["clean", "clean"],
  ["needs_review", "needs review"],
  ["duplicate_conflict_needs_review", "duplicate/conflict review"],
];

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = els.tokenInput.value.trim();
  if (!token) return;
  await login(token);
});

els.refreshButton.addEventListener("click", async () => {
  if (!session) return;
  try {
    await loadOverview();
  } catch (error) {
    setDashboardStatus(error.message);
  }
});

els.logoutButton.addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  session = null;
  overview = null;
  masterState = null;
  finalSummary = null;
  activeSectionId = "content";
  els.dashboard.hidden = true;
  els.loginPanel.hidden = false;
  els.tokenInput.value = "";
  renderNav([]);
  els.workspace.replaceChildren();
  setStatus("");
  setDashboardStatus("");
});

const savedToken = localStorage.getItem(TOKEN_KEY);
if (savedToken) {
  els.tokenInput.value = savedToken;
  login(savedToken);
}

async function login(token) {
  setStatus("Checking token");
  try {
    const response = await fetch("/api/auth/role-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (!response.ok) throw new Error("Token rejected");
    const auth = await response.json();
    if (auth.role_type !== "npc_master") {
      throw new Error("Master role token required");
    }
    session = { token, auth };
    localStorage.setItem(TOKEN_KEY, token);
    els.masterName.textContent = auth.display_name || auth.owner_id || "Master";
    els.loginPanel.hidden = true;
    els.dashboard.hidden = false;
    await loadOverview();
  } catch (error) {
    localStorage.removeItem(TOKEN_KEY);
    session = null;
    overview = null;
    masterState = null;
    finalSummary = null;
    els.dashboard.hidden = true;
    els.loginPanel.hidden = false;
    setStatus(error.message);
  }
}

async function loadOverview() {
  setStatus("Loading overview");
  const data = await apiJson("/api/master/admin/overview");
  overview = data;
  try {
    masterState = await apiJson("/api/master/state");
  } catch (error) {
    masterState = null;
    setDashboardStatus(`Master state failed: ${error.message}`);
  }
  if (!overview.sections.some((section) => section.id === activeSectionId)) {
    activeSectionId = overview.sections[0]?.id || "content";
  }
  renderOverview(overview);
  const alertCount = masterState?.blocking_alerts?.length || 0;
  setDashboardStatus(
    alertCount
      ? `Overview loaded with ${alertCount} blocking alert(s)`
      : `Overview loaded: ${overview.snapshot_version || "not imported"}`
  );
}

function renderOverview(data) {
  const attention = data.sections.filter((section) => section.status === "needs_attention").length;
  els.stageValue.textContent = data.stage || "Stage 2";
  els.snapshotValue.textContent = data.snapshot_version || "not imported";
  els.sectionsValue.textContent = `${data.sections.length}`;
  els.attentionValue.textContent = `${attention}`;
  renderNav(data.sections);
  renderSection(data.sections.find((section) => section.id === activeSectionId) || data.sections[0]);
}

function renderNav(sections) {
  els.nav.replaceChildren();
  for (const section of sections) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-button";
    button.dataset.sectionId = section.id;
    button.setAttribute("aria-pressed", String(section.id === activeSectionId));
    button.textContent = section.label;
    const badge = document.createElement("span");
    badge.className = `status-badge ${statusClass(section.status)}`;
    badge.textContent = statusLabel(section.status);
    button.append(badge);
    button.addEventListener("click", () => {
      activeSectionId = section.id;
      renderOverview(overview);
    });
    els.nav.append(button);
  }
}

function renderSection(section) {
  els.workspace.replaceChildren();
  if (!section) return;

  const header = document.createElement("div");
  header.className = "workspace-heading";
  header.innerHTML = `
    <div>
      <p class="eyebrow">${escapeHtml(section.id)}</p>
      <h3>${escapeHtml(section.label)}</h3>
    </div>
    <span class="status-badge ${statusClass(section.status)}">${escapeHtml(statusLabel(section.status))}</span>
  `;
  els.workspace.append(header);

  renderMetrics(section);

  if (section.id === "content") {
    renderContentPanel(section);
    return;
  }
  if (section.id === "game-ops") {
    renderGameOpsPanel(section);
    return;
  }
  if (section.id === "events") {
    renderEventsPanel(section);
    return;
  }
  if (section.id === "npc") {
    renderNpcPanel(section);
    return;
  }
  if (section.id === "backups") {
    renderBackupsPanel(section);
    return;
  }
  if (section.id === "final") {
    renderFinalPanel(section);
    return;
  }

  renderActions(section);
}

function renderMetrics(section) {
  const metrics = document.createElement("section");
  metrics.className = "metric-strip";
  metrics.setAttribute("aria-label", `${section.label} metrics`);
  for (const metric of section.metrics || []) {
    const item = document.createElement("article");
    item.className = "mini-metric";
    item.innerHTML = `
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
    `;
    metrics.append(item);
  }
  els.workspace.append(metrics);
}

function renderActions(section) {
  const actions = document.createElement("section");
  actions.className = "action-list";
  actions.setAttribute("aria-label", `${section.label} endpoints`);
  for (const action of section.actions || []) {
    const item = document.createElement("article");
    item.className = "action-row";
    if (action.status !== "ready") item.classList.add("disabled");
    item.innerHTML = `
      <div>
        <strong>${escapeHtml(action.label)}</strong>
        <span>${escapeHtml(endpointLabel(action))}</span>
      </div>
      <span class="status-badge ${statusClass(action.status)}">${escapeHtml(statusLabel(action.status))}</span>
    `;
    actions.append(item);
  }
  els.workspace.append(actions);
}

function renderContentPanel(section) {
  renderActions(section);

  const panel = document.createElement("section");
  panel.className = "content-panel";
  panel.innerHTML = `
    <div class="content-controls">
      <form id="content-import-form" class="content-form">
        <label for="content-pack-select">Content pack</label>
        <select id="content-pack-select"></select>
        <label for="content-manifest-path">Manifest path</label>
        <input id="content-manifest-path" autocomplete="off" placeholder="data/seed default">
        <label class="check-row" for="content-export-snapshot">
          <input id="content-export-snapshot" type="checkbox" checked>
          <span>Export snapshot file</span>
        </label>
        <button type="submit">Import</button>
      </form>
      <form id="snapshot-export-form" class="content-form">
        <label for="snapshot-dir">Snapshot dir</label>
        <input id="snapshot-dir" autocomplete="off" placeholder="data/snapshots">
        <button type="submit">Export snapshot</button>
      </form>
    </div>
    <p class="status-line content-status" id="content-status" role="status"></p>
    <div class="content-results">
      <section class="report-block" id="import-report"></section>
      <section class="report-block" id="qr-checklist"></section>
      <section class="report-block" id="handout-checklist"></section>
    </div>
  `;
  els.workspace.append(panel);
  setupContentPanel(panel);
}

function renderGameOpsPanel(section) {
  renderActions(section);
  if (!masterState) {
    els.workspace.append(emptyLine("Master state is not available"));
    return;
  }
  const grid = document.createElement("section");
  grid.className = "ops-grid";
  grid.append(
    renderActOpsPanel(),
    renderPvpOpsPanel(),
    renderEventSyncPanel(),
    renderAntiSnowballPanel(),
    renderLordMapPanel(),
    renderEconomyRecoveryPanel(),
    renderVisibilityAuditPanel(),
    renderCorrectionPanel()
  );
  els.workspace.append(grid);
}

function renderActOpsPanel() {
  const panel = opsPanel("Act controls");
  const acts = masterState.acts?.acts || [];
  const state = masterState.acts?.state || {};
  const history = masterState.acts?.history || [];
  panel.innerHTML += `
    <p>Current: ${escapeHtml(state.current_act_id || "not started")} / ${escapeHtml(state.status || "not_started")}</p>
    <div class="form-grid">
      <label class="field">
        <span>Act</span>
        <select id="ops-act-id">${actOptions(acts, state.current_act_id)}</select>
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="ops-act-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Announcement</span>
        <select id="ops-act-announcement">
          <option value="pending">pending</option>
          <option value="announced">announced</option>
        </select>
      </label>
    </div>
    <div class="inline-actions">
      <button type="button" id="ops-start-act">Start</button>
      <button type="button" class="secondary" id="ops-announce-act">Announce</button>
      <button type="button" class="secondary" id="ops-reveal-unlock">Reveal code</button>
    </div>
  `;
  panel.querySelector("#ops-start-act").addEventListener("click", async () => {
    const actId = panel.querySelector("#ops-act-id").value;
    const operator = panel.querySelector("#ops-act-operator").value.trim() || "master";
    const physical = panel.querySelector("#ops-act-announcement").value;
    await runOpsAction(
      "Start act",
      () =>
        apiJson(`/api/master/acts/${encodeURIComponent(actId)}/start`, {
          method: "POST",
          body: { operator, physical_announcement_state: physical },
        }),
      (result) => `Act started: ${result.state?.current_act_id || actId}`
    );
  });
  panel.querySelector("#ops-announce-act").addEventListener("click", async () => {
    const actId = panel.querySelector("#ops-act-id").value;
    const operator = panel.querySelector("#ops-act-operator").value.trim() || "master";
    await runOpsAction(
      "Record announcement",
      () =>
        apiJson(`/api/master/acts/${encodeURIComponent(actId)}/physical-announcement`, {
          method: "POST",
          body: { operator, state: "announced" },
        }),
      (result) => `Announcement recorded: ${result.act_id || actId}`
    );
  });
  panel.querySelector("#ops-reveal-unlock").addEventListener("click", async () => {
    const actId = panel.querySelector("#ops-act-id").value;
    const operator = encodeURIComponent(panel.querySelector("#ops-act-operator").value.trim() || "master");
    await runOpsAction(
      "Reveal unlock code",
      () => apiJson(`/api/master/acts/${encodeURIComponent(actId)}/unlock-code?operator=${operator}`),
      (result) => `Unlock code for ${result.act_id || actId}: ${result.code || "hidden"}`
    );
  });
  panel.append(
    objectTable(
      ["act_id", "status", "physical_announcement_state", "unlock_revealed_at", "operator"],
      history,
      ["Act", "Status", "Announcement", "Unlock", "Operator"]
    )
  );
  return panel;
}

function renderPvpOpsPanel() {
  const panel = opsPanel("PvP throttle");
  const pvp = masterState.pvp || {};
  const throttle = pvp.throttle || {};
  panel.innerHTML += `
    <p>Mode: ${escapeHtml(throttle.mode || "normal")} / tables ${escapeHtml(throttle.max_tables ?? "-")}</p>
    <label class="field">
      <span>Operator</span>
      <input id="ops-pvp-operator" autocomplete="off" value="master">
    </label>
    <div class="inline-actions">
      <button type="button" id="pvp-normal">Normal</button>
      <button type="button" class="secondary" id="pvp-limited">Limited</button>
      <button type="button" class="danger" id="pvp-paused">Paused</button>
    </div>
  `;
  for (const [id, mode] of [
    ["#pvp-normal", "normal"],
    ["#pvp-limited", "limited"],
    ["#pvp-paused", "paused"],
  ]) {
    panel.querySelector(id).addEventListener("click", async () => {
      const operator = panel.querySelector("#ops-pvp-operator").value.trim() || "master";
      await runOpsAction(
        "Set PvP throttle",
        () =>
          apiJson("/api/master/pvp-throttle", {
            method: "POST",
            body: { mode, operator },
          }),
        (result) => `PvP throttle: ${result.throttle?.mode || mode}`
      );
    });
  }
  panel.append(
    objectTable(
      ["challenge_id", "challenger_id", "target_id", "status", "review_reason"],
      pvp.queued_challenges || [],
      ["Challenge", "From", "To", "Status", "Review"]
    )
  );
  return panel;
}

function renderEventSyncPanel() {
  const panel = opsPanel("Recent event log and sync status");
  const events = masterState.events || {};
  const recent = recentEventRows(events.recent || []);
  const syncStatuses = events.sync_statuses || [];
  panel.append(
    summaryGrid([
      ["Recent events", recent.length],
      ["Sync clients", syncStatuses.length],
      ["Open reviews", events.review?.open_count || 0],
      ["Critical", events.review?.critical_open_count || 0],
    ])
  );
  panel.append(blockTitle("Recent event log"));
  panel.append(
    objectTable(
      ["id", "event_type", "source", "actor", "paper_form_id", "created_at"],
      recent.slice(0, 12),
      ["ID", "Type", "Source", "Actor", "Paper form", "Created"]
    )
  );
  panel.append(blockTitle("Sync status"));
  panel.append(
    objectTable(
      ["client_id", "player_id", "snapshot_version", "last_seen_at", "last_event_sequence"],
      syncStatuses,
      ["Client", "Player", "Snapshot", "Last seen", "Seq"]
    )
  );
  return panel;
}

function renderAntiSnowballPanel() {
  const panel = opsPanel("Anti-snowball state");
  const rows = (masterState.lord_map?.domains || []).map((domain) => {
    const state = domain.anti_snowball || {};
    return {
      domain_id: domain.domain_id,
      gold: domain.gold,
      army_power: state.army_power ?? 0,
      average_army_power: roundNumber(state.average_army_power),
      army_power_ratio: `${state.army_power_ratio ?? 0}%`,
      income_cut_percent: `${state.income_cut_percent ?? 0}%`,
    };
  });
  panel.append(
    summaryGrid([
      ["Domains", rows.length],
      ["With cut", rows.filter((row) => row.income_cut_percent !== "0%").length],
      ["Max ratio", maxPercent(rows.map((row) => row.army_power_ratio))],
      ["Max cut", maxPercent(rows.map((row) => row.income_cut_percent))],
    ])
  );
  panel.append(
    objectTable(
      ["domain_id", "gold", "army_power", "average_army_power", "army_power_ratio", "income_cut_percent"],
      rows,
      ["Domain", "Gold", "Army", "Avg army", "Ratio", "Income cut"]
    )
  );
  return panel;
}

function renderLordMapPanel() {
  const panel = opsPanel("Lord map state");
  const map = masterState.lord_map || {};
  const domains = map.domains || [];
  const territories = map.territories || [];
  const contested = map.contested_claims || [];
  panel.append(
    summaryGrid([
      ["Domains", domains.length],
      ["Territories", territories.length],
      ["Contested", contested.length],
      ["Raids", (map.raid_effects || []).length],
    ])
  );
  panel.append(
    objectTable(
      ["territory_id", "name", "owner_domain_id", "status", "contested_by_domain_id"],
      territories.slice(0, 10),
      ["Territory", "Name", "Owner", "Status", "Contested by"]
    )
  );
  panel.append(
    objectTable(
      ["domain_id", "gold", "current_mp", "mp_cap", "raid_tokens"],
      domains,
      ["Domain", "Gold", "MP", "Cap", "Raids"]
    )
  );
  return panel;
}

function renderEconomyRecoveryPanel() {
  const panel = opsPanel("Potion and trade recovery");
  const economy = masterState.economy || {};
  const markets = economy.potion_markets || [];
  const transfers = economy.trade_transfers || [];
  const players = economy.player_economy || [];
  panel.append(
    summaryGrid([
      ["Potion markets", markets.length],
      ["Potion inventory", economy.summary?.potion_inventory_rows || 0],
      ["Trade transfers", transfers.length],
      ["Pending trades", economy.summary?.pending_trade_transfers || 0],
    ])
  );
  panel.innerHTML += `
    <div class="form-grid">
      <label class="field">
        <span>Operator</span>
        <input id="economy-correction-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Reason</span>
        <input id="economy-correction-reason" autocomplete="off" placeholder="paper trade or potion log checked">
      </label>
    </div>

    <form id="potion-market-correction-form" class="form-grid typed-correction">
      <label class="field wide">
        <span>Potion market correction</span>
        <select id="potion-market-id">${optionTags(markets.map((row) => [
          row.market_id,
          `${row.market_id} / ${row.potion_id} / stock ${row.stock}`,
        ]))}</select>
      </label>
      <label class="field">
        <span>Stock</span>
        <input id="potion-market-stock" type="number" min="0" step="1" placeholder="12">
      </label>
      <label class="field">
        <span>Refresh rule</span>
        <input id="potion-market-refresh" autocomplete="off" placeholder="per_act">
      </label>
      <button type="submit">Apply potion correction</button>
    </form>

    <form id="trade-transfer-correction-form" class="form-grid typed-correction">
      <label class="field wide">
        <span>Trade transfer correction</span>
        <select id="trade-transfer-id">${optionTags(transfers.map((row) => [
          row.transfer_id,
          `${row.transfer_id} / ${row.asset_type}:${row.asset_id} / ${row.status}`,
        ]))}</select>
      </label>
      <label class="field">
        <span>Status</span>
        <select id="trade-transfer-status">
          <option value="">keep</option>
          <option value="pending_locked">pending locked</option>
          <option value="accepted">accepted</option>
          <option value="declined">declined</option>
          <option value="contested_review">contested review</option>
          <option value="cancelled">cancelled</option>
        </select>
      </label>
      <label class="field">
        <span>Quantity</span>
        <input id="trade-transfer-quantity" type="number" min="1" step="1" placeholder="1">
      </label>
      <label class="field">
        <span>Price gold</span>
        <input id="trade-transfer-price" type="number" min="0" step="1" placeholder="0">
      </label>
      <label class="field">
        <span>Mode</span>
        <select id="trade-transfer-mode">
          <option value="">keep</option>
          <option value="gift">gift</option>
          <option value="sell">sell</option>
          <option value="exchange">exchange</option>
          <option value="paper_recovered">paper recovered</option>
        </select>
      </label>
      <button type="submit">Apply trade correction</button>
    </form>

    <form id="player-economy-correction-form" class="form-grid typed-correction">
      <label class="field wide">
        <span>Player economy correction</span>
        <select id="player-economy-id">${optionTags(players.map((row) => [
          row.player_id,
          `${row.player_id} / gold ${row.gold} / xp ${row.xp}`,
        ]))}</select>
      </label>
      <label class="field">
        <span>Gold</span>
        <input id="player-economy-gold" type="number" min="0" step="1" placeholder="30">
      </label>
      <label class="field">
        <span>XP</span>
        <input id="player-economy-xp" type="number" min="0" step="1" placeholder="4">
      </label>
      <label class="field">
        <span>Challenge tokens</span>
        <input id="player-economy-tokens" type="number" min="0" step="1" placeholder="1">
      </label>
      <button type="submit">Apply economy correction</button>
    </form>
  `;
  attachEconomyCorrectionHandlers(panel);
  panel.append(blockTitle("Potion markets"));
  panel.append(
    objectTable(
      ["market_id", "seller_role", "potion_id", "stock", "refresh_rule"],
      markets,
      ["Market", "Seller", "Potion", "Stock", "Refresh"]
    )
  );
  panel.append(blockTitle("Trade transfers"));
  panel.append(
    objectTable(
      ["transfer_id", "from_player_id", "to_player_id", "asset_type", "asset_id", "quantity", "price_gold", "status"],
      transfers,
      ["Transfer", "From", "To", "Type", "Asset", "Qty", "Gold", "Status"]
    )
  );
  return panel;
}

function attachEconomyCorrectionHandlers(panel) {
  panel.querySelector("#potion-market-correction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const patch = {};
    setPatchNumber(patch, "stock", panel.querySelector("#potion-market-stock").value);
    setPatchText(patch, "refresh_rule", panel.querySelector("#potion-market-refresh").value);
    await submitCorrectionFromPanel(
      panel,
      "Potion market correction",
      {
        target_type: "potion_market",
        target_id: panel.querySelector("#potion-market-id").value,
        patch,
      },
      (result) => `Potion market corrected: ${result.target_id}`
    );
  });

  panel.querySelector("#trade-transfer-correction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const patch = {};
    setPatchText(patch, "status", panel.querySelector("#trade-transfer-status").value);
    setPatchNumber(patch, "quantity", panel.querySelector("#trade-transfer-quantity").value);
    setPatchNumber(patch, "price_gold", panel.querySelector("#trade-transfer-price").value);
    setPatchText(patch, "mode", panel.querySelector("#trade-transfer-mode").value);
    await submitCorrectionFromPanel(
      panel,
      "Trade transfer correction",
      {
        target_type: "trade_transfer",
        target_id: panel.querySelector("#trade-transfer-id").value,
        patch,
      },
      (result) => `Trade transfer corrected: ${result.target_id}`
    );
  });

  panel.querySelector("#player-economy-correction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const patch = {};
    setPatchNumber(patch, "gold", panel.querySelector("#player-economy-gold").value);
    setPatchNumber(patch, "xp", panel.querySelector("#player-economy-xp").value);
    setPatchNumber(patch, "challenge_tokens", panel.querySelector("#player-economy-tokens").value);
    await submitCorrectionFromPanel(
      panel,
      "Player economy correction",
      {
        target_type: "player",
        target_id: panel.querySelector("#player-economy-id").value,
        patch,
      },
      (result) => `Player economy corrected: ${result.target_id}`
    );
  });
}

async function submitCorrectionFromPanel(panel, label, request, formatter) {
  if (!request.target_id) {
    setDashboardStatus("Correction target is required");
    return null;
  }
  if (!Object.keys(request.patch || {}).length) {
    setDashboardStatus("Correction field is required");
    return null;
  }
  return runOpsAction(
    label,
    () =>
      apiJson("/api/master/game-ops/corrections", {
        method: "POST",
        body: {
          target_type: request.target_type,
          target_id: request.target_id,
          operator: panel.querySelector("#economy-correction-operator").value.trim(),
          reason: panel.querySelector("#economy-correction-reason").value.trim(),
          patch: request.patch,
        },
      }),
    formatter
  );
}

function renderVisibilityAuditPanel() {
  const panel = opsPanel("Visibility audit");
  const audit = masterState.visibility_audit || {};
  const summary = audit.summary || {};
  const actions = document.createElement("div");
  actions.className = "inline-actions";
  const refresh = document.createElement("button");
  refresh.type = "button";
  refresh.className = "secondary";
  refresh.textContent = "Refresh visibility audit";
  refresh.addEventListener("click", refreshVisibilityAudit);
  actions.append(refresh);
  panel.append(actions);
  panel.append(
    summaryGrid([
      ["Hidden garrisons", summary.hidden_garrisons || 0],
      ["Raid effects", summary.raid_effects || 0],
      ["Artifacts", summary.artifacts || 0],
      ["Revealed", summary.revealed_artifacts || 0],
    ])
  );
  panel.append(blockTitle("Lord visibility audit"));
  panel.append(
    objectTable(
      ["domain_id", "foreign_garrisons", "raid_effects", "artifact_numbers"],
      audit.lord_view_boundaries || [],
      ["Domain", "Garrisons", "Raids", "Artifacts"]
    )
  );
  panel.append(blockTitle("Hidden garrison audit"));
  panel.append(
    objectTable(
      ["garrison_id", "territory_id", "domain_id", "card_id", "count", "lord_redaction"],
      audit.hidden_garrisons || [],
      ["Garrison", "Territory", "Owner", "Card", "Count", "Lord view"]
    )
  );
  panel.append(blockTitle("Raid effect visibility"));
  panel.append(
    objectTable(
      ["raid_effect_id", "source_domain_id", "target_domain_id", "target_territory_id", "status"],
      audit.raid_effects || [],
      ["Raid", "Source", "Target", "Territory", "Status"]
    )
  );
  panel.append(blockTitle("Artifact visibility audit"));
  panel.append(
    objectTable(
      ["artifact_id", "visibility", "player_visibility", "revealed", "owner_count"],
      artifactAuditRows(audit.artifacts || []),
      ["Artifact", "Seed visibility", "Player view", "Revealed", "Owners"]
    )
  );
  return panel;
}

async function refreshVisibilityAudit() {
  setDashboardStatus("Loading visibility audit");
  try {
    const audit = await apiJson(VISIBILITY_AUDIT_ENDPOINT);
    masterState = {
      ...(masterState || {}),
      visibility_audit: audit,
    };
    renderOverview(overview);
    setDashboardStatus("Visibility audit loaded");
  } catch (error) {
    setDashboardStatus(error.message);
  }
}

function renderCorrectionPanel() {
  const panel = opsPanel("Audited correction");
  panel.innerHTML += `
    <form id="ops-correction-form" class="form-grid">
      <label class="field">
        <span>Target type</span>
        <select id="ops-correction-type">
          <option value="territory">territory</option>
          <option value="domain">domain</option>
          <option value="player">player economy</option>
          <option value="garrison">garrison</option>
          <option value="pending_reward">pending reward</option>
          <option value="domain_building">building</option>
          <option value="recruit_offer">recruit offer</option>
          <option value="reserve">reserve</option>
          <option value="raid">raid</option>
          <option value="potion_market">potion market</option>
          <option value="potion_inventory">potion inventory</option>
          <option value="trade_transfer">trade transfer</option>
          <option value="pvp_review">pvp timeout/review</option>
        </select>
      </label>
      <label class="field">
        <span>Target id</span>
        <input id="ops-correction-id" autocomplete="off" placeholder="territory_fort_east">
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="ops-correction-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Reason</span>
        <input id="ops-correction-reason" autocomplete="off" placeholder="paper fallback checked">
      </label>
      <label class="field wide">
        <span>Patch JSON</span>
        <textarea id="ops-correction-patch">{"owner_domain_id":"domain_north","status":"controlled"}</textarea>
      </label>
      <button type="submit">Apply correction</button>
    </form>
  `;
  panel.querySelector("#ops-correction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const targetType = panel.querySelector("#ops-correction-type").value;
    const targetId = panel.querySelector("#ops-correction-id").value.trim();
    const operator = panel.querySelector("#ops-correction-operator").value.trim();
    const reason = panel.querySelector("#ops-correction-reason").value.trim();
    let patch;
    try {
      patch = parseJsonObject(panel.querySelector("#ops-correction-patch").value);
    } catch (error) {
      setDashboardStatus(error.message);
      return;
    }
    await runOpsAction(
      "Apply correction",
      () =>
        apiJson("/api/master/game-ops/corrections", {
          method: "POST",
          body: { target_type: targetType, target_id: targetId, operator, reason, patch },
        }),
      (result) => `Correction recorded: ${result.correction_id}`
    );
  });
  panel.append(
    objectTable(
      ["correction_id", "target_type", "target_id", "operator", "reason"],
      masterState.corrections || [],
      ["Correction", "Type", "Target", "Operator", "Reason"]
    )
  );
  return panel;
}

function renderEventsPanel(section) {
  renderActions(section);
  if (!masterState) {
    els.workspace.append(emptyLine("Master state is not available"));
    return;
  }
  const grid = document.createElement("section");
  grid.className = "ops-grid";
  grid.append(renderPaperRecoveryPanel(), renderReviewPanel(), renderRewardPanel());
  els.workspace.append(grid);
}

function renderPaperRecoveryPanel() {
  const panel = opsPanel("Paper recovery intake");
  const recentPaper = recentEventRows(masterState.events?.recent || []).filter(
    (row) => row.event_type === "paper_recovered"
  );
  panel.innerHTML += `
    <form id="paper-recovery-form" class="form-grid paper-recovery-form">
      <label class="field">
        <span>Form type</span>
        <select id="paper-source-form-type">${optionTags(PAPER_FORM_TYPES)}</select>
      </label>
      <label class="field">
        <span>Paper form id</span>
        <input id="paper-form-id" autocomplete="off" placeholder="paper-pve-001" required>
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="paper-operator" autocomplete="off" value="master" required>
      </label>
      <label class="field">
        <span>Timestamp</span>
        <input id="paper-timestamp" type="datetime-local" required>
      </label>
      <label class="field">
        <span>Conflict status</span>
        <select id="paper-conflict-status">${optionTags(PAPER_CONFLICT_STATUSES, "clean")}</select>
      </label>
      <label class="field wide">
        <span>Reason</span>
        <input id="paper-reason" autocomplete="off" placeholder="phone outage during scene" required>
      </label>

      <div class="paper-fieldset wide" data-paper-type="paper_pve_result">
        <label class="field">
          <span>Player id</span>
          <input id="paper-pve-player-id" autocomplete="off" placeholder="p_witcher_1">
        </label>
        <label class="field">
          <span>QR id</span>
          <input id="paper-pve-qr-id" autocomplete="off" placeholder="qr_a1_001">
        </label>
        <label class="field">
          <span>Result</span>
          <select id="paper-pve-result">
            <option value="success">success</option>
            <option value="failure">failure</option>
          </select>
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_pvp_stake" hidden>
        <label class="field">
          <span>Match id</span>
          <input id="paper-pvp-match-id" autocomplete="off" placeholder="match-paper-1">
        </label>
        <label class="field">
          <span>Stake asset type</span>
          <select id="paper-pvp-stake-type">
            <option value="item">item</option>
            <option value="card">card</option>
            <option value="artifact">artifact</option>
            <option value="potion">potion</option>
            <option value="gold">gold</option>
          </select>
        </label>
        <label class="field">
          <span>Stake asset id</span>
          <input id="paper-pvp-stake-id" autocomplete="off" placeholder="item_order_seal">
        </label>
        <label class="field">
          <span>Quantity</span>
          <input id="paper-pvp-stake-quantity" type="number" min="1" step="1" placeholder="1">
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_lord_action" hidden>
        <label class="field">
          <span>Lord id</span>
          <input id="paper-lord-action-lord-id" autocomplete="off" placeholder="p_lord_1">
        </label>
        <label class="field">
          <span>Territory id</span>
          <input id="paper-lord-action-territory-id" autocomplete="off" placeholder="territory_north_keep">
        </label>
        <label class="field">
          <span>Action</span>
          <select id="paper-lord-action">
            <option value="garrison">garrison</option>
            <option value="move">move</option>
            <option value="raid">raid</option>
            <option value="battle">battle</option>
          </select>
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_lord_battle" hidden>
        <label class="field">
          <span>Battle id</span>
          <input id="paper-battle-id" autocomplete="off" placeholder="battle-paper-1">
        </label>
        <label class="field">
          <span>Result</span>
          <select id="paper-battle-result">
            <option value="attacker_won">attacker won</option>
            <option value="defender_won">defender won</option>
            <option value="draw">draw</option>
          </select>
        </label>
        <label class="field">
          <span>Attacker losses</span>
          <input id="paper-battle-attacker-losses" type="number" min="0" step="1" placeholder="0">
        </label>
        <label class="field">
          <span>Defender losses</span>
          <input id="paper-battle-defender-losses" type="number" min="0" step="1" placeholder="0">
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_order_resolution" hidden>
        <label class="field">
          <span>Order id</span>
          <input id="paper-order-id" autocomplete="off" placeholder="order_river_review">
        </label>
        <label class="field">
          <span>Result</span>
          <select id="paper-order-result">
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_npc_deal" hidden>
        <label class="field">
          <span>NPC role</span>
          <select id="paper-npc-role">
            <option value="king">king</option>
            <option value="wanderer">wanderer</option>
          </select>
        </label>
        <label class="field">
          <span>Target id</span>
          <input id="paper-npc-target-id" autocomplete="off" placeholder="p_sorc_1">
        </label>
        <label class="field">
          <span>Price gold</span>
          <input id="paper-npc-price-gold" type="number" min="0" step="1" placeholder="2">
        </label>
        <label class="field">
          <span>Hidden price</span>
          <input id="paper-npc-hidden-price" autocomplete="off" placeholder="owed_at_final">
        </label>
      </div>

      <div class="paper-fieldset wide" data-paper-type="paper_final_evidence" hidden>
        <label class="field">
          <span>Evidence category</span>
          <input id="paper-final-category" autocomplete="off" placeholder="artifact">
        </label>
        <label class="field">
          <span>Target id</span>
          <input id="paper-final-target-id" autocomplete="off" placeholder="p_witcher_1">
        </label>
        <label class="field wide">
          <span>Summary text</span>
          <input id="paper-final-summary" autocomplete="off" placeholder="Recovered final evidence from paper.">
        </label>
      </div>

      <button type="submit">Submit paper recovery</button>
    </form>
  `;
  const form = panel.querySelector("#paper-recovery-form");
  panel.querySelector("#paper-timestamp").value = localDateTimeValue();
  panel.querySelector("#paper-source-form-type").addEventListener("change", () => {
    updatePaperFieldsets(panel);
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = buildPaperRecoveryPayload(panel);
    await runOpsAction(
      "Submit paper recovery",
      () =>
        apiJson("/api/events/sync", {
          method: "POST",
          body: {
            device_id: "admin-studio-paper-terminal",
            actor_id: session.auth?.owner_id || "master",
            actor_type: "master",
            events: [
              {
                event_id: `paper_admin_${Date.now()}_${Math.random().toString(16).slice(2)}`,
                client_sequence: Date.now(),
                created_at: new Date().toISOString(),
                event_type: "paper_recovered",
                payload,
              },
            ],
          },
        }),
      (result) => `Paper recovery: ${result.results?.[0]?.status || "submitted"}`
    );
  });
  panel.append(blockTitle("Recent paper recovery"));
  panel.append(
    objectTable(
      ["id", "paper_form_id", "source", "created_at"],
      recentPaper,
      ["Event", "Paper form", "Source", "Created"]
    )
  );
  return panel;
}

function updatePaperFieldsets(panel) {
  const selected = panel.querySelector("#paper-source-form-type").value;
  for (const fieldset of panel.querySelectorAll(".paper-fieldset")) {
    fieldset.hidden = fieldset.dataset.paperType !== selected;
  }
}

function buildPaperRecoveryPayload(panel) {
  const type = fieldValue(panel, "#paper-source-form-type");
  const payload = {
    paper_form_id: fieldValue(panel, "#paper-form-id"),
    source_form_type: type,
    operator: fieldValue(panel, "#paper-operator"),
    timestamp: fieldValue(panel, "#paper-timestamp"),
    reason: fieldValue(panel, "#paper-reason"),
    conflict_status: fieldValue(panel, "#paper-conflict-status"),
  };

  if (type === "paper_pve_result") {
    payload.player_id = fieldValue(panel, "#paper-pve-player-id");
    payload.qr_id = fieldValue(panel, "#paper-pve-qr-id");
    payload.result = fieldValue(panel, "#paper-pve-result");
  }
  if (type === "paper_pvp_stake") {
    payload.match_id = fieldValue(panel, "#paper-pvp-match-id");
    payload.stake_json = compactObject({
      asset_type: fieldValue(panel, "#paper-pvp-stake-type"),
      asset_id: fieldValue(panel, "#paper-pvp-stake-id"),
      quantity: numberOrNull(panel.querySelector("#paper-pvp-stake-quantity").value) || 1,
    });
  }
  if (type === "paper_lord_action") {
    payload.lord_id = fieldValue(panel, "#paper-lord-action-lord-id");
    payload.territory_id = fieldValue(panel, "#paper-lord-action-territory-id");
    payload.action = fieldValue(panel, "#paper-lord-action");
  }
  if (type === "paper_lord_battle") {
    payload.battle_id = fieldValue(panel, "#paper-battle-id");
    payload.result = fieldValue(panel, "#paper-battle-result");
    payload.losses = compactObject({
      attacker: numberOrNull(panel.querySelector("#paper-battle-attacker-losses").value) || 0,
      defender: numberOrNull(panel.querySelector("#paper-battle-defender-losses").value) || 0,
    });
  }
  if (type === "paper_order_resolution") {
    payload.order_id = fieldValue(panel, "#paper-order-id");
    payload.result = fieldValue(panel, "#paper-order-result");
  }
  if (type === "paper_npc_deal") {
    payload.npc_role = fieldValue(panel, "#paper-npc-role");
    payload.target_id = fieldValue(panel, "#paper-npc-target-id");
    payload.price_json = compactObject({
      gold: numberOrNull(panel.querySelector("#paper-npc-price-gold").value),
      hidden_price: fieldValue(panel, "#paper-npc-hidden-price"),
    });
  }
  if (type === "paper_final_evidence") {
    payload.evidence_category = fieldValue(panel, "#paper-final-category");
    payload.target_id = fieldValue(panel, "#paper-final-target-id");
    payload.summary_text = fieldValue(panel, "#paper-final-summary");
  }
  return payload;
}

function renderReviewPanel() {
  const panel = opsPanel("Review queue");
  const review = masterState.events?.review || {};
  panel.innerHTML += `
    <p>Open: ${escapeHtml(review.open_count || 0)} / critical ${escapeHtml(review.critical_open_count || 0)}</p>
    <div class="form-grid">
      <label class="field">
        <span>Operator</span>
        <input id="review-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Reason</span>
        <input id="review-reason" autocomplete="off" placeholder="checked at master table">
      </label>
      <label class="field wide">
        <span>Correction JSON</span>
        <textarea id="review-correction">{}</textarea>
      </label>
    </div>
  `;
  panel.append(reviewActionTable(panel, review.open_items || []));
  return panel;
}

function reviewActionTable(panel, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr><th>Event</th><th>Severity</th><th>Status</th><th>Reason</th><th>Action</th></tr>
    </thead>
  `;
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5">No open reviews</td></tr>`;
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.event_id)}</td>
      <td>${escapeHtml(row.severity)}</td>
      <td>${escapeHtml(row.status)}</td>
      <td>${escapeHtml(row.reason)}</td>
      <td><div class="inline-actions"></div></td>
    `;
    const actions = tr.querySelector(".inline-actions");
    for (const action of ["approve", "reject", "correct"]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = action === "reject" ? "danger" : "secondary";
      button.textContent = action;
      button.addEventListener("click", async () => {
        let correction = {};
        try {
          correction = parseJsonObject(panel.querySelector("#review-correction").value);
        } catch (error) {
          setDashboardStatus(error.message);
          return;
        }
        await runOpsAction(
          "Resolve review",
          () =>
            apiJson(`/api/events/${encodeURIComponent(row.event_id)}/review`, {
              method: "POST",
              body: {
                action,
                operator: panel.querySelector("#review-operator").value.trim() || "master",
                reason: panel.querySelector("#review-reason").value.trim(),
                severity: row.severity,
                correction,
              },
            }),
          (result) => `Review ${result.review?.event_id || row.event_id}: ${result.review?.status || action}`
        );
      });
      actions.append(button);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  wrapper.append(table);
  return wrapper;
}

function renderRewardPanel() {
  const panel = opsPanel("Reward approvals");
  const rewards = masterState.reward_approvals || {};
  panel.innerHTML += `
    <p>Pending: ${escapeHtml(rewards.pending_count || 0)}</p>
    <div class="form-grid">
      <label class="field">
        <span>Operator</span>
        <input id="reward-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Reason</span>
        <input id="reward-reason" autocomplete="off" placeholder="roll log checked">
      </label>
      <label class="field wide">
        <span>Correction JSON</span>
        <textarea id="reward-correction">{}</textarea>
      </label>
    </div>
  `;
  panel.append(rewardActionTable(panel, rewards.pending || []));
  return panel;
}

function rewardActionTable(panel, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr><th>Approval</th><th>Reward</th><th>Player</th><th>Severity</th><th>Action</th></tr>
    </thead>
  `;
  const tbody = document.createElement("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5">No pending rewards</td></tr>`;
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.approval_id)}</td>
      <td>${escapeHtml(row.reward_id)}</td>
      <td>${escapeHtml(row.player_id)}</td>
      <td>${escapeHtml(row.severity)}</td>
      <td><div class="inline-actions"></div></td>
    `;
    const actions = tr.querySelector(".inline-actions");
    for (const action of ["approve", "reject", "correct"]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = action === "reject" ? "danger" : "secondary";
      button.textContent = action;
      button.addEventListener("click", async () => {
        let correction = {};
        try {
          correction = parseJsonObject(panel.querySelector("#reward-correction").value);
        } catch (error) {
          setDashboardStatus(error.message);
          return;
        }
        await runOpsAction(
          "Resolve reward",
          () =>
            apiJson(`/api/master/reward-approvals/${encodeURIComponent(row.approval_id)}`, {
              method: "POST",
              body: {
                action,
                operator: panel.querySelector("#reward-operator").value.trim() || "master",
                reason: panel.querySelector("#reward-reason").value.trim(),
                correction,
              },
            }),
          (result) => `Reward ${result.approval_id || row.approval_id}: ${result.status || action}`
        );
      });
      actions.append(button);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  wrapper.append(table);
  return wrapper;
}

function renderNpcPanel(section) {
  renderActions(section);
  const grid = document.createElement("section");
  grid.className = "ops-grid";
  grid.append(renderKingNpcPanel(), renderWandererNpcPanel(), renderReputationPanel(), renderNpcListsPanel());
  els.workspace.append(grid);
  loadNpcPanelData();
}

function renderKingNpcPanel() {
  const panel = opsPanel("King rulings");
  panel.innerHTML += `
    <form id="king-event-form" class="form-grid">
      <label class="field">
        <span>Event</span>
        <select id="king-event-type">
          <option value="king_ruling">king ruling</option>
          <option value="influence_grant">influence grant</option>
          <option value="dispute_judgment">dispute judgment</option>
          <option value="major_order">major order</option>
        </select>
      </label>
      <label class="field">
        <span>Targets</span>
        <input id="king-targets" autocomplete="off" placeholder="domain_north, p_lord_1">
      </label>
      <label class="field">
        <span>Reputation delta</span>
        <input id="king-reputation-delta" type="number" value="0">
      </label>
      <label class="field">
        <span>Severity</span>
        <select id="king-severity">
          <option value="P1">P1</option>
          <option value="P0">P0</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="king-operator" autocomplete="off" value="master">
      </label>
      <label class="field check-row" for="king-final-flag">
        <input id="king-final-flag" type="checkbox">
        <span>Final flag</span>
      </label>
      <label class="field wide">
        <span>Consequence JSON</span>
        <textarea id="king-consequence">{"influence_delta":1}</textarea>
      </label>
      <button type="submit">Record King event</button>
    </form>
  `;
  panel.querySelector("#king-event-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    let consequence;
    try {
      consequence = parseJsonObject(panel.querySelector("#king-consequence").value);
    } catch (error) {
      setDashboardStatus(error.message);
      return;
    }
    await submitNpcEvent({
      npc_role: "npc_king",
      event_type: panel.querySelector("#king-event-type").value,
      target_ids: splitIds(panel.querySelector("#king-targets").value),
      reputation_delta: Number(panel.querySelector("#king-reputation-delta").value || 0),
      severity: panel.querySelector("#king-severity").value,
      consequence,
      final_flag: panel.querySelector("#king-final-flag").checked,
      operator: panel.querySelector("#king-operator").value.trim() || "master",
    });
  });
  return panel;
}

function renderWandererNpcPanel() {
  const panel = opsPanel("Wanderer hidden price");
  panel.innerHTML += `
    <form id="wanderer-event-form" class="form-grid">
      <label class="field">
        <span>Event</span>
        <select id="wanderer-event-type">
          <option value="stranger_deal">stranger deal</option>
          <option value="wanderer_deal">wanderer deal</option>
          <option value="dark_artifact">dark artifact</option>
          <option value="alternate_victory_hook">alternate victory hook</option>
          <option value="field_intervention">field intervention</option>
        </select>
      </label>
      <label class="field">
        <span>Targets</span>
        <input id="wanderer-targets" autocomplete="off" placeholder="p_witcher_4">
      </label>
      <label class="field">
        <span>Hidden price</span>
        <input id="wanderer-hidden-price" autocomplete="off" placeholder="owed_at_final">
      </label>
      <label class="field">
        <span>Reputation delta</span>
        <input id="wanderer-reputation-delta" type="number" value="-1">
      </label>
      <label class="field">
        <span>Severity</span>
        <select id="wanderer-severity">
          <option value="P1">P1</option>
          <option value="P0">P0</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="wanderer-operator" autocomplete="off" value="master">
      </label>
      <label class="field check-row" for="wanderer-final-flag">
        <input id="wanderer-final-flag" type="checkbox" checked>
        <span>Final flag</span>
      </label>
      <label class="field wide">
        <span>Condition JSON</span>
        <textarea id="wanderer-condition">{"accepted_mark":true}</textarea>
      </label>
      <label class="field wide">
        <span>Consequence JSON</span>
        <textarea id="wanderer-consequence">{"effect":"alternate_victory_hook","artifact":"dark_token"}</textarea>
      </label>
      <button type="submit">Capture NPC deal</button>
    </form>
  `;
  panel.querySelector("#wanderer-event-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    let condition;
    let consequence;
    try {
      condition = parseJsonObject(panel.querySelector("#wanderer-condition").value);
      consequence = parseJsonObject(panel.querySelector("#wanderer-consequence").value);
    } catch (error) {
      setDashboardStatus(error.message);
      return;
    }
    const hiddenPrice = panel.querySelector("#wanderer-hidden-price").value.trim();
    await submitNpcEvent({
      npc_role: "npc_wanderer",
      event_type: panel.querySelector("#wanderer-event-type").value,
      target_ids: splitIds(panel.querySelector("#wanderer-targets").value),
      price: hiddenPrice ? { hidden_price: hiddenPrice } : {},
      condition,
      consequence,
      reputation_delta: Number(panel.querySelector("#wanderer-reputation-delta").value || 0),
      severity: panel.querySelector("#wanderer-severity").value,
      final_flag: panel.querySelector("#wanderer-final-flag").checked,
      operator: panel.querySelector("#wanderer-operator").value.trim() || "master",
    });
  });
  return panel;
}

function renderReputationPanel() {
  const panel = opsPanel("Master reputation");
  panel.innerHTML += `
    <form id="reputation-form" class="form-grid">
      <label class="field">
        <span>Player</span>
        <input id="reputation-player-id" autocomplete="off" placeholder="p_witcher_1">
      </label>
      <label class="field">
        <span>Delta</span>
        <input id="reputation-delta" type="number" value="0">
      </label>
      <label class="field wide">
        <span>Reason</span>
        <input id="reputation-reason" autocomplete="off" placeholder="public contract accepted">
      </label>
      <button type="button" class="secondary" id="reputation-load">Load exact value</button>
      <button type="submit">Apply reputation</button>
    </form>
    <section id="reputation-result" class="report-block"></section>
  `;
  panel.querySelector("#reputation-load").addEventListener("click", async () => {
    const playerId = panel.querySelector("#reputation-player-id").value.trim();
    if (!playerId) {
      setDashboardStatus("Player id is required");
      return;
    }
    await loadReputation(panel, playerId);
  });
  panel.querySelector("#reputation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const playerId = panel.querySelector("#reputation-player-id").value.trim();
    if (!playerId) {
      setDashboardStatus("Player id is required");
      return;
    }
    await runOpsAction(
      "Apply reputation",
      () =>
        apiJson(`/api/master/reputation/${encodeURIComponent(playerId)}/change`, {
          method: "POST",
          body: {
            delta: Number(panel.querySelector("#reputation-delta").value || 0),
            reason: panel.querySelector("#reputation-reason").value.trim(),
          },
        }),
      (result) => `Reputation ${playerId}: ${result.change?.value_after}`
    );
    await loadReputation(panel, playerId);
  });
  renderReputationResult(panel.querySelector("#reputation-result"), null);
  return panel;
}

function renderNpcListsPanel() {
  const panel = opsPanel("NPC runtime log");
  panel.innerHTML += `
    <div class="inline-actions">
      <button type="button" class="secondary" id="npc-refresh">Refresh NPC log</button>
    </div>
    <section id="npc-events-log" class="report-block"></section>
    <section id="npc-deals-log" class="report-block"></section>
  `;
  panel.querySelector("#npc-refresh").addEventListener("click", loadNpcPanelData);
  return panel;
}

async function submitNpcEvent(body) {
  await runOpsAction(
    "Record NPC event",
    () =>
      apiJson("/api/master/npc/events", {
        method: "POST",
        body,
      }),
    (result) => `NPC event ${result.npc_runtime_event_id} recorded`
  );
  await loadNpcPanelData();
}

async function loadReputation(panel, playerId) {
  setDashboardStatus(`Loading reputation: ${playerId}`);
  try {
    const reputation = await apiJson(`/api/master/reputation/${encodeURIComponent(playerId)}`);
    renderReputationResult(panel.querySelector("#reputation-result"), reputation);
    setDashboardStatus(`Reputation ${playerId}: ${reputation.value}`);
  } catch (error) {
    setDashboardStatus(error.message);
  }
}

function renderReputationResult(root, reputation) {
  root.replaceChildren();
  root.append(blockTitle("Exact reputation view"));
  if (!reputation) {
    root.append(emptyLine("No player loaded"));
    return;
  }
  root.append(
    summaryGrid([
      ["Player", reputation.player_id],
      ["Value", reputation.value],
      ["State", reputation.canonical_label],
      ["Descriptor", reputation.player_descriptor],
    ])
  );
  root.append(
    objectTable(
      ["change_id", "delta", "value_before", "value_after", "reason", "created_at"],
      reputation.change_log || [],
      ["Change", "Delta", "Before", "After", "Reason", "Created"]
    )
  );
}

async function loadNpcPanelData() {
  const eventsRoot = els.workspace.querySelector("#npc-events-log");
  const dealsRoot = els.workspace.querySelector("#npc-deals-log");
  if (!eventsRoot || !dealsRoot) return;
  eventsRoot.replaceChildren(emptyLine("Loading NPC events"));
  dealsRoot.replaceChildren(emptyLine("Loading NPC deals"));
  try {
    const [events, deals] = await Promise.all([
      apiJson("/api/master/npc/events"),
      apiJson("/api/master/npc/deals"),
    ]);
    eventsRoot.replaceChildren(
      blockTitle("King/Wanderer events"),
      objectTable(
        ["npc_runtime_event_id", "npc_role", "event_type", "target_scope", "severity", "review_route", "final_flag"],
        events.items || [],
        ["ID", "NPC", "Event", "Scope", "Severity", "Route", "Final"]
      )
    );
    dealsRoot.replaceChildren(
      blockTitle("NPC deals"),
      objectTable(
        ["deal_id", "npc_role", "target_ids", "hidden_price", "final_flag", "status"],
        deals.items || [],
        ["Deal", "NPC", "Targets", "Hidden price", "Final", "Status"]
      )
    );
  } catch (error) {
    eventsRoot.replaceChildren(emptyLine(error.message));
    dealsRoot.replaceChildren(emptyLine(error.message));
  }
}

function renderBackupsPanel(section) {
  renderActions(section);
  const backups = masterState?.backups || {};
  const panel = opsPanel("Manual backup");
  panel.innerHTML += `
    <form id="backup-form" class="form-grid">
      <label class="field">
        <span>Operator</span>
        <input id="backup-operator" autocomplete="off" value="master">
      </label>
      <label class="field">
        <span>Trigger</span>
        <select id="backup-trigger">
          <option value="manual">manual</option>
          <option value="pre_act_transition">pre act transition</option>
          <option value="pre_final_lock">pre final lock</option>
        </select>
      </label>
      <button type="submit">Run backup</button>
      <button type="button" class="secondary" id="backup-refresh">Refresh status</button>
    </form>
  `;
  panel.querySelector("#backup-refresh").addEventListener("click", async () => {
    setDashboardStatus("Loading backup status");
    try {
      const status = await apiJson("/api/master/backups/status");
      masterState = { ...(masterState || {}), backups: status };
      renderOverview(overview);
      setDashboardStatus("Backup status loaded");
    } catch (error) {
      setDashboardStatus(error.message);
    }
  });
  panel.querySelector("#backup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runOpsAction(
      "Run backup",
      () =>
        apiJson("/api/backups/run", {
          method: "POST",
          body: {
            operator: panel.querySelector("#backup-operator").value.trim() || "master",
            trigger_type: panel.querySelector("#backup-trigger").value,
          },
        }),
      (result) => `Backup ${result.status}: ${result.backup_id}`
    );
  });
  panel.append(
    summaryGrid([
      ["Jobs", backups.configured_jobs || 0],
      ["Runs", backups.run_count || 0],
      ["Last", backups.last_run?.status || "none"],
      ["Alerts", backups.blocking_alerts?.length || 0],
    ])
  );
  panel.append(
    objectTable(
      ["backup_id", "trigger_type", "status", "operator", "error"],
      backups.runs || [],
      ["Backup", "Trigger", "Status", "Operator", "Error"]
    )
  );
  els.workspace.append(panel);
}

function renderFinalPanel(section) {
  renderActions(section);
  const grid = document.createElement("section");
  grid.className = "ops-grid";
  grid.append(renderFinalToolsPanel(), renderFinalNotePanel());
  els.workspace.append(grid);

  const result = document.createElement("section");
  result.id = "final-summary-result";
  result.className = "report-block";
  els.workspace.append(result);
  if (finalSummary) {
    renderFinalSummary(result, finalSummary);
  } else {
    result.append(emptyLine("Final summary is not loaded"));
  }
}

function renderFinalToolsPanel() {
  const panel = opsPanel("Final summary tools");
  panel.innerHTML += `
    <div class="inline-actions">
      <button type="button" id="final-load">Open final summary</button>
      <button type="button" class="secondary" id="final-export">Export final summary</button>
    </div>
  `;
  panel.querySelector("#final-load").addEventListener("click", loadFinalSummary);
  panel.querySelector("#final-export").addEventListener("click", async () => {
    const summary = finalSummary || (await loadFinalSummary());
    if (summary) downloadJson(`final-summary-${summary.snapshot_version || "latest"}.json`, summary);
  });
  return panel;
}

function renderFinalNotePanel() {
  const panel = opsPanel("Final master note");
  panel.innerHTML += `
    <form id="final-note-form" class="form-grid">
      <label class="field">
        <span>Category</span>
        <select id="final-note-category">
          <option value="ruling">ruling</option>
          <option value="trial">trial</option>
          <option value="personal_hook">personal hook</option>
          <option value="epilogue">epilogue</option>
        </select>
      </label>
      <label class="field">
        <span>Target</span>
        <input id="final-note-target" autocomplete="off" placeholder="p_witcher_5">
      </label>
      <label class="field">
        <span>Operator</span>
        <input id="final-note-operator" autocomplete="off" value="master">
      </label>
      <label class="field wide">
        <span>Note</span>
        <textarea id="final-note-text" placeholder="Manual ruling input"></textarea>
      </label>
      <button type="submit">Record final note</button>
    </form>
  `;
  panel.querySelector("#final-note-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runOpsAction(
      "Record final note",
      () =>
        apiJson("/api/master/final-summary/notes", {
          method: "POST",
          body: {
            category: panel.querySelector("#final-note-category").value,
            target_id: valueOrNull(panel.querySelector("#final-note-target").value),
            note_text: panel.querySelector("#final-note-text").value,
            operator: panel.querySelector("#final-note-operator").value.trim() || "master",
          },
        }),
      (result) => `Final note recorded: ${result.note_id}`
    );
    await loadFinalSummary();
  });
  return panel;
}

async function loadFinalSummary() {
  setDashboardStatus("Loading final summary");
  try {
    finalSummary = await apiJson("/api/master/final-summary");
    const root = els.workspace.querySelector("#final-summary-result");
    if (root) renderFinalSummary(root, finalSummary);
    setDashboardStatus(`Final summary loaded: ${finalSummary.snapshot_version || "no snapshot"}`);
    return finalSummary;
  } catch (error) {
    setDashboardStatus(error.message);
    return null;
  }
}

function renderFinalSummary(root, summary) {
  root.replaceChildren();
  root.append(blockTitle("Final summary"));
  root.append(
    summaryGrid([
      ["Snapshot", summary.snapshot_version || "not imported"],
      ["Missing locks", (summary.missing_locks || []).length],
      ["Pending disputes", (summary.pending_disputes || []).length],
      ["Personal hooks", (summary.personal_hooks || []).length],
    ])
  );
  root.append(
    policyStrip([
      ["No auto winner", !summary.decision_policy?.automatic_winner_calculation],
      ["JSON export", summary.export?.json_ready],
      ["Post-game review", summary.export?.post_game_review],
    ])
  );
  root.append(blockTitle("Bracket/trials/personal final inputs"));
  root.append(
    objectTable(
      ["procedure_id", "final_act_window", "start_offset_min", "end_offset_min", "master_role"],
      summary.final_procedures || [],
      ["Procedure", "Window", "Start", "End", "Master"]
    )
  );
  root.append(blockTitle("Missing or disputed evidence"));
  root.append(
    objectTable(
      ["evidence_category", "source_type", "reason", "record_id", "severity"],
      summary.missing_locks || [],
      ["Category", "Source", "Reason", "Record", "Severity"]
    )
  );
  root.append(blockTitle("Sorceress evidence"));
  root.append(
    objectTable(
      ["player_id", "locked_intent", "alignment", "favorites"],
      sorceressEvidenceRows(summary.evidence_by_role?.sorceresses || []),
      ["Sorceress", "Intent", "Alignment", "Favorites"]
    )
  );
  root.append(blockTitle("Personal hooks"));
  root.append(
    objectTable(
      ["goal_id", "player_id", "evidence_category", "public_flag_count"],
      summary.personal_hooks || [],
      ["Goal", "Player", "Category", "Public flags"]
    )
  );
  root.append(blockTitle("Master final notes"));
  root.append(
    objectTable(
      ["note_id", "category", "target_id", "note_text", "operator"],
      summary.master_final_notes || [],
      ["Note", "Category", "Target", "Text", "Operator"]
    )
  );
}

function opsPanel(title) {
  const panel = document.createElement("section");
  panel.className = "ops-panel";
  const heading = document.createElement("h4");
  heading.textContent = title;
  panel.append(heading);
  return panel;
}

async function runOpsAction(label, task, formatter = null) {
  setDashboardStatus(`${label} running`);
  try {
    const result = await task();
    await loadOverview();
    setDashboardStatus(formatter ? formatter(result) : `${label} done`);
    return result;
  } catch (error) {
    setDashboardStatus(error.message);
    return null;
  }
}

function actOptions(acts, selectedId) {
  return acts
    .map((act) => {
      const selected = act.act_id === selectedId ? " selected" : "";
      return `<option value="${escapeHtml(act.act_id)}"${selected}>${escapeHtml(act.name || act.act_id)}</option>`;
    })
    .join("");
}

function parseJsonObject(value) {
  const text = String(value || "").trim();
  if (!text) return {};
  const parsed = JSON.parse(text);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("JSON patch must be an object");
  }
  return parsed;
}

function setupContentPanel(panel) {
  const renderId = ++contentRenderId;
  const packSelect = panel.querySelector("#content-pack-select");
  const manifestInput = panel.querySelector("#content-manifest-path");
  const importForm = panel.querySelector("#content-import-form");
  const exportForm = panel.querySelector("#snapshot-export-form");
  const status = panel.querySelector("#content-status");

  packSelect.addEventListener("change", () => {
    manifestInput.value = packSelect.value;
  });
  importForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runContentImport(panel);
  });
  exportForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runSnapshotExport(panel);
  });

  status.textContent = "Loading content tools";
  loadContentPanelData(panel, renderId);
}

async function loadContentPanelData(panel, renderId) {
  try {
    const [packs, report, qrChecklist, handoutChecklist] = await Promise.all([
      apiJson("/api/master/content/packs"),
      apiJson("/api/master/content/import-report/latest"),
      apiJson("/api/master/content/qr-checklist"),
      apiJson("/api/master/content/handout-checklist"),
    ]);
    if (!panel.isConnected || renderId !== contentRenderId) return;
    renderPackOptions(panel.querySelector("#content-pack-select"), packs);
    renderImportReport(panel.querySelector("#import-report"), report);
    renderQrChecklist(panel.querySelector("#qr-checklist"), qrChecklist);
    renderHandoutChecklist(panel.querySelector("#handout-checklist"), handoutChecklist);
    panel.querySelector("#content-status").textContent = "Content tools loaded";
  } catch (error) {
    if (!panel.isConnected || renderId !== contentRenderId) return;
    panel.querySelector("#content-status").textContent = error.message;
  }
}

async function runContentImport(panel) {
  const status = panel.querySelector("#content-status");
  const manifestPath = panel.querySelector("#content-manifest-path").value.trim();
  const exportSnapshot = panel.querySelector("#content-export-snapshot").checked;
  status.textContent = "Importing content";
  try {
    const report = await apiJson("/api/master/content/import", {
      method: "POST",
      body: {
        manifest_path: manifestPath || null,
        export_snapshot: exportSnapshot,
      },
    });
    status.textContent = `Import ${report.status}: ${report.error_count || 0} errors`;
    await loadOverview();
  } catch (error) {
    status.textContent = error.message;
  }
}

async function runSnapshotExport(panel) {
  const status = panel.querySelector("#content-status");
  const targetDir = panel.querySelector("#snapshot-dir").value.trim();
  status.textContent = "Exporting snapshot";
  try {
    const result = await apiJson("/api/master/content/snapshot/export", {
      method: "POST",
      body: { target_dir: targetDir || null },
    });
    status.textContent = `Snapshot exported: ${result.path}`;
  } catch (error) {
    status.textContent = error.message;
  }
}

function renderPackOptions(select, data) {
  select.replaceChildren();
  for (const pack of data.packs || []) {
    const option = document.createElement("option");
    option.value = pack.manifest_path || "";
    option.textContent = `${pack.label} (${pack.expected_result || pack.kind})`;
    select.append(option);
  }
}

function renderImportReport(root, report) {
  root.replaceChildren();
  const title = report.status === "not_imported" ? "Import report" : `Import report: ${report.status}`;
  root.append(blockTitle(title));
  root.append(
    summaryGrid([
      ["Run", report.run_id || "none"],
      ["Snapshot", report.snapshot_version || "not imported"],
      ["Files", (report.files || []).length],
      ["Errors", report.error_count || 0],
    ])
  );
  if (!report.errors || !report.errors.length) {
    root.append(emptyLine("No validation errors"));
    return;
  }
  root.append(
    objectTable(
      ["file", "row", "record_id", "code", "message"],
      report.errors,
      ["File", "Row", "ID", "Code", "Message"]
    )
  );
}

function renderQrChecklist(root, checklist) {
  root.replaceChildren();
  root.append(blockTitle("QR/manual checklist"));
  root.append(
    summaryGrid([
      ["Snapshot", checklist.snapshot_version || "not imported"],
      ["Total QR", checklist.total || 0],
      ["Repeatable", (checklist.by_mode || {}).repeatable_scene || 0],
      ["Unique", (checklist.by_mode || {}).unique_object || 0],
    ])
  );
  root.append(
    policyStrip([
      ["QR honesty", checklist.policy?.qr_honesty],
      ["Single d20", checklist.policy?.single_d20_no_reroll],
    ])
  );
  root.append(
    objectTable(
      ["qr_id", "manual_code", "mode", "act_id", "location_node_id", "print_ready"],
      checklist.items || [],
      ["QR", "Manual", "Mode", "Act", "Location", "Print"]
    )
  );
}

function renderHandoutChecklist(root, checklist) {
  root.replaceChildren();
  root.append(blockTitle("Handout checklist"));
  root.append(
    summaryGrid([
      ["Snapshot", checklist.snapshot_version || "not imported"],
      ["Handouts", (checklist.items || []).length],
      ["Policy checks", (checklist.policy_checks || []).length],
      ["Ops items", (checklist.ops_items || []).length],
    ])
  );
  root.append(
    policyStrip((checklist.policy_checks || []).map((check) => [check.label, check.ready]))
  );
  root.append(
    objectTable(
      ["handout_id", "audience", "topics", "missing_topics", "ready"],
      checklist.items || [],
      ["Handout", "Audience", "Topics", "Missing", "Ready"]
    )
  );
}

function blockTitle(text) {
  const title = document.createElement("h4");
  title.textContent = text;
  return title;
}

function emptyLine(text) {
  const line = document.createElement("p");
  line.className = "muted-line";
  line.textContent = text;
  return line;
}

function summaryGrid(items) {
  const grid = document.createElement("div");
  grid.className = "compact-summary";
  for (const [label, value] of items) {
    const item = document.createElement("span");
    item.innerHTML = `<b>${escapeHtml(label)}</b>${escapeHtml(value)}`;
    grid.append(item);
  }
  return grid;
}

function policyStrip(items) {
  const strip = document.createElement("div");
  strip.className = "policy-strip";
  for (const [label, ready] of items) {
    const badge = document.createElement("span");
    badge.className = `status-badge ${ready ? "ready" : "warn"}`;
    badge.textContent = `${label}: ${ready ? "ready" : "missing"}`;
    strip.append(badge);
  }
  return strip;
}

function objectTable(keys, rows, labels) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of labels) {
    const cell = document.createElement("th");
    cell.textContent = label;
    headRow.append(cell);
  }
  thead.append(headRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = keys.length;
    cell.textContent = "No rows";
    row.append(cell);
    tbody.append(row);
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const key of keys) {
      const cell = document.createElement("td");
      const value = row[key];
      cell.textContent = Array.isArray(value) ? value.join(", ") : String(value ?? "");
      tr.append(cell);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  wrapper.append(table);
  return wrapper;
}

function artifactAuditRows(artifacts) {
  return artifacts.map((item) => ({
    ...item,
    owner_count: (item.owners || []).length,
  }));
}

function sorceressEvidenceRows(rows) {
  return rows.map((item) => ({
    player_id: item.player?.player_id || "",
    locked_intent: (item.locked_magical_intent || [])
      .map((intent) => intent.status)
      .join(", "),
    alignment: (item.alignment_evidence || []).length,
    favorites: (item.favorites || []).length,
  }));
}

function recentEventRows(rows) {
  return rows.map((item) => {
    const payload = item.payload || {};
    return {
      ...item,
      actor: payload.actor_id || payload.player_id || payload.operator || "",
      paper_form_id: payload.paper_form_id || "",
    };
  });
}

function optionTags(pairs, selected = "") {
  if (!pairs.length) {
    return '<option value="">No rows</option>';
  }
  return pairs
    .map(([value, label]) => {
      const stringValue = String(value ?? "");
      const selectedAttr = stringValue === String(selected) ? " selected" : "";
      return `<option value="${escapeHtml(stringValue)}"${selectedAttr}>${escapeHtml(label ?? value)}</option>`;
    })
    .join("");
}

function fieldValue(root, selector) {
  return String(root.querySelector(selector)?.value || "").trim();
}

function setPatchText(patch, field, value) {
  const text = String(value || "").trim();
  if (text) patch[field] = text;
}

function setPatchNumber(patch, field, value) {
  const parsed = numberOrNull(value);
  if (parsed !== null) patch[field] = parsed;
}

function numberOrNull(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  const parsed = Number.parseInt(text, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function compactObject(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== null && value !== "")
  );
}

function roundNumber(value) {
  const numeric = Number(value || 0);
  return Number.isInteger(numeric) ? numeric : numeric.toFixed(1);
}

function maxPercent(values) {
  const max = values.reduce((highest, value) => {
    const parsed = Number.parseInt(String(value || "0").replace("%", ""), 10);
    return Number.isNaN(parsed) ? highest : Math.max(highest, parsed);
  }, 0);
  return `${max}%`;
}

function localDateTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function splitIds(value) {
  return String(value || "")
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function valueOrNull(value) {
  const text = String(value || "").trim();
  return text || null;
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function apiJson(url, options = {}) {
  const requestOptions = {
    method: options.method || "GET",
    headers: {
      "X-Role-Token": session.token,
      ...(options.headers || {}),
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

function endpointLabel(action) {
  if (!action.endpoint) return "Pending backend endpoint";
  return `${action.method || "GET"} ${action.endpoint}`;
}

function setStatus(message) {
  els.loginStatus.textContent = message;
  if (!els.dashboard.hidden) {
    setDashboardStatus(message);
  }
}

function setDashboardStatus(message) {
  if (els.dashboardStatus) {
    els.dashboardStatus.textContent = message;
  }
}

function statusLabel(status) {
  return String(status || "unknown").replaceAll("_", " ");
}

function statusClass(status) {
  if (status === "ready") return "ready";
  if (status === "needs_attention") return "warn";
  if (status === "not_imported") return "warn";
  return "pending";
}

function errorMessage(data, status) {
  const detail = data.detail;
  if (detail && typeof detail === "object") {
    return `${detail.code || status}: ${detail.message || "Request failed"}`;
  }
  return detail || `Request failed: ${status}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
