const TOKEN_KEY = "witcher_larp_lord_token";

const els = {
  loginPanel: document.querySelector("#login-panel"),
  dashboard: document.querySelector("#dashboard"),
  form: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#role-token"),
  loginStatus: document.querySelector("#login-status"),
  lordName: document.querySelector("#lord-name"),
  domainName: document.querySelector("#domain-name"),
  goldValue: document.querySelector("#gold-value"),
  influenceValue: document.querySelector("#influence-value"),
  mpValue: document.querySelector("#mp-value"),
  ordersValue: document.querySelector("#orders-value"),
  territoryCount: document.querySelector("#territory-count"),
  activeOrders: document.querySelector("#active-orders"),
  recruitCount: document.querySelector("#recruit-count"),
  actionStatus: document.querySelector("#action-status"),
  territoryList: document.querySelector("#territory-list"),
  orderList: document.querySelector("#order-list"),
  recruitList: document.querySelector("#recruit-list"),
  refreshButton: document.querySelector("#refresh-button"),
  logoutButton: document.querySelector("#logout-button"),
  actionForms: document.querySelectorAll("[data-action-form]"),
  moveTarget: document.querySelector("#move-target"),
  moveRoutePreview: document.querySelector("#move-route-preview"),
  garrisonOperation: document.querySelector("#garrison-operation"),
  garrisonTerritory: document.querySelector("#garrison-territory"),
  garrisonCard: document.querySelector("#garrison-card"),
  garrisonCount: document.querySelector("#garrison-count"),
  buildingId: document.querySelector("#building-id"),
  recruitOffer: document.querySelector("#recruit-offer"),
  raidTarget: document.querySelector("#raid-target"),
  battleTerritory: document.querySelector("#battle-territory"),
};

let session = null;
let currentState = null;

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = els.tokenInput.value.trim();
  if (!token) return;
  await login(token);
});

els.refreshButton.addEventListener("click", async () => {
  if (session) await loadState(session);
});

els.moveTarget.addEventListener("change", () => {
  updateMoveRoutePreview();
});

els.logoutButton.addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  session = null;
  currentState = null;
  els.dashboard.hidden = true;
  els.loginPanel.hidden = false;
  els.tokenInput.value = "";
  setStatus("");
});

for (const form of els.actionForms) {
  form.addEventListener("submit", handleActionSubmit);
}

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
    if (auth.role_type !== "lord" || !auth.lord_id) {
      throw new Error("Token is not assigned to a lord panel");
    }
    session = { token, auth };
    localStorage.setItem(TOKEN_KEY, token);
    els.loginPanel.hidden = true;
    els.dashboard.hidden = false;
    await loadState(session);
  } catch (error) {
    localStorage.removeItem(TOKEN_KEY);
    setStatus(error.message);
  }
}

async function loadState(currentSession) {
  setStatus("Loading state");
  const response = await fetch(`/api/lords/${currentSession.auth.lord_id}/state`, {
    headers: { "X-Role-Token": currentSession.token },
  });
  if (!response.ok) {
    setStatus(`State request failed: ${response.status}`);
    return;
  }
  const state = await response.json();
  currentState = state;
  renderState(state);
  setStatus(`Snapshot ${state.snapshot_version || "not imported"}`);
}

function renderState(state) {
  els.lordName.textContent = state.lord.display_name;
  els.domainName.textContent = state.domain.name || state.lord.domain_id;
  els.goldValue.textContent = `${state.domain.gold ?? state.domain.starting_gold ?? state.lord.gold}g`;
  els.influenceValue.textContent = `${state.domain.influence ?? 0}`;
  els.mpValue.textContent = state.movement
    ? `${state.movement.current_mp}/${state.movement.mp_cap}`
    : "-";
  els.ordersValue.textContent = `${state.summary.active_orders}`;
  els.territoryCount.textContent = `${state.summary.owned_territories}`;
  els.activeOrders.textContent = `${state.summary.active_orders} active`;
  els.recruitCount.textContent = `${state.recruit_market.length} offers`;

  renderTerritories(state.territories);
  renderOrders(state.orders);
  renderRecruit(state.recruit_market);
  renderActionOptions(state);
  updateMoveRoutePreview();
}

function renderTerritories(items) {
  renderList(els.territoryList, items, (item) => {
    const card = rowCard();
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.name)}</span>
        <span>T${escapeHtml(item.tier)}</span>
      </div>
      <div class="row-meta">${escapeHtml(item.node_name)} - ${escapeHtml(item.bonus_type)}</div>
      <div class="row-meta">Garrison: ${item.garrisons.length} - Pending: ${item.pending_rewards.length}</div>
    `;
    if (item.pending_rewards.length > 0) card.classList.add("warn");
    return card;
  });
}

function renderOrders(items) {
  renderList(els.orderList, items, (item) => {
    const card = rowCard();
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.object_id)}</span>
        <span>${escapeHtml(item.status)}</span>
      </div>
      <div class="row-meta">${escapeHtml(item.visibility)} - ${escapeHtml(item.target_player_id)}</div>
    `;
    if (item.status.includes("review")) card.classList.add("danger");
    return card;
  });
}

function renderRecruit(items) {
  renderList(els.recruitList, items, (item) => {
    const card = rowCard();
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.card_id)}</span>
        <span>${escapeHtml(item.cost)}g</span>
      </div>
      <div class="row-meta">${escapeHtml(item.status)}</div>
    `;
    if (item.status !== "available") card.classList.add("warn");
    return card;
  });
}

function renderActionOptions(state) {
  const allTerritories = [
    ...state.territories,
    ...state.neutral_territories,
    ...state.other_territories,
  ];
  setOptions(
    els.moveTarget,
    allTerritories.filter((item) => item.node_id),
    (item) => item.node_id,
    (item) => `${item.node_name} (${item.name})`,
    "No map nodes"
  );
  setOptions(
    els.garrisonTerritory,
    [...state.territories, ...state.neutral_territories],
    (item) => item.territory_id,
    (item) => `${item.name} (${item.status})`,
    "No valid territories"
  );
  setOptions(
    els.garrisonCard,
    state.army_reserve.filter((item) => Number(item.count) > 0),
    (item) => item.card_id,
    (item) => `${item.card_id} x${item.count}`,
    "No reserve units"
  );
  setOptions(
    els.buildingId,
    state.building_catalog.filter((item) => item.status !== "owned"),
    (item) => item.building_id,
    (item) => `${item.name} (${item.gold_cost}g)`,
    "No buildings"
  );
  setOptions(
    els.recruitOffer,
    state.recruit_market,
    (item) => item.offer_id,
    (item) => `${item.card_id} (${item.status}, ${item.cost}g)`,
    "Refresh offers"
  );
  setOptions(
    els.raidTarget,
    state.other_territories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.owner_domain_id})`,
    "No raid targets"
  );
  setOptions(
    els.battleTerritory,
    allTerritories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.status})`,
    "No territories"
  );
}

async function handleActionSubmit(event) {
  event.preventDefault();
  if (!session || !currentState) return;
  const form = event.currentTarget;
  const action = form.dataset.actionForm;
  try {
    setActionStatus("Sending");
    const result = await runAction(action, form, event.submitter);
    setActionStatus(`${action}: ${result.status || "ok"}`);
    await loadState(session);
  } catch (error) {
    setActionStatus(error.message || "Action failed");
  }
}

async function runAction(action, form, submitter) {
  const lordId = session.auth.lord_id;
  const formData = new FormData(form);
  if (action === "move") {
    const targetNodeId = valueOrNull(formData.get("to_node_id"));
    const route = buildRoute(currentState, targetNodeId);
    if (!route) {
      throw new Error("invalid_route: no weighted route");
    }
    return apiPost(`/api/lords/${lordId}/move`, {
      to_node_id: targetNodeId,
      route_node_ids: route.nodes,
    });
  }
  if (action === "garrison") {
    return apiPost(`/api/lords/${lordId}/garrisons/transfer`, {
      operation: valueOrNull(formData.get("operation")) || "garrison",
      territory_id: valueOrNull(formData.get("territory_id")),
      card_id: valueOrNull(formData.get("card_id")),
      count: Number(formData.get("count") || 1),
    });
  }
  if (action === "building") {
    return apiPost(`/api/lords/${lordId}/buildings`, {
      building_id: valueOrNull(formData.get("building_id")),
    });
  }
  if (action === "recruit") {
    const recruitAction = submitter?.dataset.recruitAction || "refresh";
    const payload = { action: recruitAction };
    if (recruitAction !== "refresh") payload.offer_id = valueOrNull(formData.get("offer_id"));
    return apiPost(`/api/lords/${lordId}/recruit`, payload);
  }
  if (action === "raid") {
    return apiPost(`/api/lords/${lordId}/raids`, {
      target_territory_id: valueOrNull(formData.get("target_territory_id")),
    });
  }
  if (action === "order") {
    return apiPost(`/api/lords/${lordId}/orders`, {
      action: "create",
      object_id: valueOrNull(formData.get("object_id")),
      target_player_id: valueOrNull(formData.get("target_player_id")),
      visibility: valueOrNull(formData.get("visibility")) || "public",
      escrow_reward_id: valueOrNull(formData.get("escrow_reward_id")),
    });
  }
  if (action === "battle-create") {
    return apiPost("/api/lord-battles", {
      battle_id: valueOrNull(formData.get("battle_id")),
      attacker_domain_id: currentState.lord.domain_id,
      defender_domain_id: valueOrNull(formData.get("defender_domain_id")),
      territory_id: valueOrNull(formData.get("territory_id")),
    });
  }
  if (action === "battle-action") {
    const battleId = valueOrNull(formData.get("battle_id"));
    const payloadJson = valueOrNull(formData.get("payload_json"));
    return apiPost(`/api/lord-battles/${encodeURIComponent(battleId)}/actions`, {
      action_type: valueOrNull(formData.get("action_type")),
      actor_side: valueOrNull(formData.get("actor_side")) || "attacker",
      payload: parsePayload(payloadJson),
    });
  }
  throw new Error(`Unknown action: ${action}`);
}

function renderList(target, items, factory) {
  target.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No records";
    target.append(empty);
    return;
  }
  for (const item of items) {
    target.append(factory(item));
  }
}

function rowCard() {
  const node = document.createElement("article");
  node.className = "row-card";
  return node;
}

function setStatus(message) {
  els.loginStatus.textContent = message;
}

function setActionStatus(message) {
  els.actionStatus.textContent = message;
}

function updateMoveRoutePreview() {
  if (!els.moveRoutePreview || !currentState) return;
  const targetNodeId = valueOrNull(els.moveTarget.value);
  const route = buildRoute(currentState, targetNodeId);
  els.moveRoutePreview.textContent = route
    ? `${route.nodes.join(" -> ")} (${route.cost} MP)`
    : "No route";
}

function buildRoute(state, targetNodeId) {
  const startNodeId = state?.movement?.current_node_id;
  if (!startNodeId || !targetNodeId) return null;
  if (startNodeId === targetNodeId) return null;

  const graph = new Map();
  for (const edge of state.map_edges || []) {
    addEdge(graph, edge.from_node_id, edge.to_node_id, Number(edge.mp_cost || 0));
    if (String(edge.bidirectional).toLowerCase() === "true" || edge.bidirectional === true) {
      addEdge(graph, edge.to_node_id, edge.from_node_id, Number(edge.mp_cost || 0));
    }
  }

  const distances = new Map([[startNodeId, 0]]);
  const previous = new Map();
  const pending = new Set(graph.keys());
  pending.add(startNodeId);
  pending.add(targetNodeId);

  while (pending.size) {
    let current = null;
    let best = Infinity;
    for (const nodeId of pending) {
      const distance = distances.get(nodeId) ?? Infinity;
      if (distance < best) {
        current = nodeId;
        best = distance;
      }
    }
    if (current === null || best === Infinity) break;
    pending.delete(current);
    if (current === targetNodeId) break;
    for (const edge of graph.get(current) || []) {
      const candidate = best + edge.cost;
      if (candidate < (distances.get(edge.to) ?? Infinity)) {
        distances.set(edge.to, candidate);
        previous.set(edge.to, current);
        pending.add(edge.to);
      }
    }
  }

  if (!distances.has(targetNodeId)) return null;
  const nodes = [targetNodeId];
  while (nodes[0] !== startNodeId) {
    const prior = previous.get(nodes[0]);
    if (!prior) return null;
    nodes.unshift(prior);
  }
  return { nodes, cost: distances.get(targetNodeId) };
}

function addEdge(graph, fromNodeId, toNodeId, cost) {
  if (!fromNodeId || !toNodeId || !Number.isFinite(cost)) return;
  if (!graph.has(fromNodeId)) graph.set(fromNodeId, []);
  graph.get(fromNodeId).push({ to: toNodeId, cost });
}

async function apiPost(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Role-Token": session.token,
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(errorMessage(data, response.status));
  }
  return data;
}

function setOptions(select, items, valueFor, labelFor, emptyLabel) {
  select.replaceChildren();
  if (!items.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyLabel;
    select.append(option);
    return;
  }
  for (const item of items) {
    const option = document.createElement("option");
    option.value = valueFor(item);
    option.textContent = labelFor(item);
    select.append(option);
  }
}

function valueOrNull(value) {
  const text = String(value ?? "").trim();
  return text ? text : null;
}

function parsePayload(value) {
  if (!value) return {};
  try {
    return JSON.parse(value);
  } catch {
    throw new Error("Payload JSON is invalid");
  }
}

function errorMessage(data, status) {
  const detail = data.detail;
  if (detail && typeof detail === "object") {
    return `${detail.code || status}: ${detail.message || "Action failed"}`;
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
