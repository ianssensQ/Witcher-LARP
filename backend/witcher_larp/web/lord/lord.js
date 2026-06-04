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
  battleCount: document.querySelector("#battle-count"),
  actionStatus: document.querySelector("#action-status"),
  territoryList: document.querySelector("#territory-list"),
  captureList: document.querySelector("#capture-list"),
  battleList: document.querySelector("#battle-list"),
  battleBoardShell: document.querySelector("#battle-board-shell"),
  battleTitle: document.querySelector("#battle-title"),
  battleTurn: document.querySelector("#battle-turn"),
  battleBoard: document.querySelector("#battle-board"),
  battleStatus: document.querySelector("#battle-status"),
  battleCommands: document.querySelectorAll("[data-battle-command]"),
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
let selectedBattleId = null;
let selectedBattleTarget = null;

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

els.garrisonOperation.addEventListener("change", () => {
  updateGarrisonCardOptions();
});

els.garrisonTerritory.addEventListener("change", () => {
  updateGarrisonCardOptions();
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

for (const button of els.battleCommands) {
  button.addEventListener("click", handleBattleCommand);
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
  els.battleCount.textContent = `${state.summary.active_battles || 0} active`;

  renderTerritories(state.territories);
  renderCaptures(state.garrison_targets || []);
  renderBattles(state.battles || []);
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

function renderCaptures(items) {
  const pending = items.filter(
    (item) => item.garrison_target_reason === "capture_pending_garrison"
  );
  renderList(els.captureList, pending, (item) => {
    const card = rowCard();
    card.classList.add("warn");
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.name)}</span>
        <span>Garrison required</span>
      </div>
      <div class="row-meta">${escapeHtml(item.status)} - ${escapeHtml(item.node_name)}</div>
      <div class="row-meta">Use active army to complete ownership resolution.</div>
    `;
    return card;
  });
}

function renderBattles(items) {
  const battles = [...items].sort((left, right) => {
    if (left.status === right.status) return String(left.battle_id).localeCompare(String(right.battle_id));
    return left.status === "active" ? -1 : 1;
  });
  if (!selectedBattleId || !battles.some((battle) => battle.battle_id === selectedBattleId)) {
    selectedBattleId = battles[0]?.battle_id || null;
    selectedBattleTarget = null;
  }
  renderList(els.battleList, battles, (battle) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-list-item";
    button.dataset.battleId = battle.battle_id;
    button.setAttribute("aria-pressed", battle.battle_id === selectedBattleId ? "true" : "false");
    button.innerHTML = `
      <span>${escapeHtml(battle.battle_id)}</span>
      <small>${escapeHtml(battle.status)} - ${escapeHtml(battle.territory_id)}</small>
    `;
    button.addEventListener("click", () => {
      selectedBattleId = battle.battle_id;
      selectedBattleTarget = null;
      renderBattles(currentState.battles || []);
    });
    return button;
  });
  renderSelectedBattle();
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
    state.garrison_targets || state.territories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.status}${item.garrison_target_reason === "capture_pending_garrison" ? ", capture pending" : ""})`,
    "No valid territories"
  );
  updateGarrisonCardOptions();
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

function updateGarrisonCardOptions() {
  if (!currentState) return;
  const operation = els.garrisonOperation.value || "active_to_fort";
  const territoryId = els.garrisonTerritory.value;
  if (operation === "reserve_to_active") {
    setOptions(
      els.garrisonCard,
      currentState.army_reserve.filter((item) => Number(item.count) > 0),
      (item) => item.card_id,
      (item) => `${item.card_id} x${item.count}`,
      "No reserve units"
    );
    return;
  }
  if (operation === "fort_to_active") {
    const territory = (currentState.garrison_targets || currentState.territories)
      .find((item) => item.territory_id === territoryId);
    const garrisons = territory ? territory.garrisons.filter((item) => Number(item.count) > 0) : [];
    setOptions(
      els.garrisonCard,
      garrisons,
      (item) => item.card_id,
      (item) => `${item.card_id} x${item.count}`,
      "No fort units"
    );
    return;
  }
  setOptions(
    els.garrisonCard,
    currentState.active_army.filter((item) => item.status === "active" && Number(item.count) > 0),
    (item) => item.card_id,
    (item) => `${item.card_id} x${item.count}`,
    "No active units"
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
      attacker_domain_id: currentState.lord.domain_id,
      territory_id: valueOrNull(formData.get("territory_id")),
    });
  }
  throw new Error(`Unknown action: ${action}`);
}

function renderSelectedBattle() {
  const battle = (currentState?.battles || []).find((item) => item.battle_id === selectedBattleId);
  if (!battle) {
    els.battleBoardShell.hidden = true;
    return;
  }
  els.battleBoardShell.hidden = false;
  const ownSide = sideForBattle(battle);
  const activeStack = stackById(battle, battle.active_stack_id);
  els.battleTitle.textContent = `${battle.battle_id}`;
  els.battleTurn.textContent = battle.status === "active"
    ? `${battle.active_side || "no side"} turn - ${activeStack?.card_id || "no active stack"}`
    : `${battle.status} - ${battle.result?.outcome || "resolved"}`;

  els.battleBoard.style.gridTemplateColumns = `repeat(${battle.board.width}, minmax(0, 1fr))`;
  els.battleBoard.replaceChildren();
  for (let y = 0; y < Number(battle.board.height || 0); y += 1) {
    for (let x = 0; x < Number(battle.board.width || 0); x += 1) {
      const stack = stackAt(battle, x, y);
      const heroSide = heroSideAt(battle, x, y);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "battle-cell";
      cell.dataset.x = String(x);
      cell.dataset.y = String(y);
      if (stack) {
        cell.dataset.stackId = stack.stack_id;
        cell.classList.add(`side-${stack.side}`);
        if (stack.stack_id === battle.active_stack_id) cell.classList.add("active");
        cell.innerHTML = `
          <strong>${escapeHtml(stack.stack_id)}</strong>
          <span>${escapeHtml(stack.card_id)}</span>
          <small>${escapeHtml(stack.count_alive)}/${escapeHtml(stack.initial_count)}</small>
        `;
      } else if (heroSide) {
        cell.dataset.heroSide = heroSide;
        cell.classList.add("hero-cell", `side-${heroSide}`);
        cell.innerHTML = `
          <strong>${heroSide === "attacker" ? "A" : "D"} Hero</strong>
          <span>${escapeHtml(battle.hero_hp[heroSide]?.current)}/${escapeHtml(battle.hero_hp[heroSide]?.max)}</span>
        `;
      } else {
        cell.innerHTML = "<span></span>";
      }
      if (isSelectedBattleTarget(x, y, stack, heroSide)) cell.classList.add("selected");
      cell.addEventListener("click", () => {
        if (stack) {
          selectedBattleTarget = {
            type: "stack",
            stack_id: stack.stack_id,
            side: stack.side,
            x,
            y,
          };
        } else if (heroSide) {
          selectedBattleTarget = { type: "hero", side: heroSide, x, y };
        } else {
          selectedBattleTarget = { type: "cell", x, y };
        }
        renderSelectedBattle();
      });
      els.battleBoard.append(cell);
    }
  }
  updateBattleCommandState(battle, ownSide);
}

function updateBattleCommandState(battle, ownSide) {
  const canAct = battle.status === "active" && ownSide && battle.active_side === ownSide;
  const target = selectedBattleTarget;
  const enemyTarget = target && target.side && target.side !== ownSide;
  for (const button of els.battleCommands) {
    const command = button.dataset.battleCommand;
    let enabled = false;
    if (command === "auto_resolve") enabled = battle.status === "active" && Boolean(ownSide);
    if (command === "defend" || command === "surrender") enabled = Boolean(canAct);
    if (command === "move") enabled = Boolean(canAct && target?.type === "cell");
    if (command === "attack") enabled = Boolean(canAct && enemyTarget);
    button.disabled = !enabled;
  }
  if (!ownSide) {
    setBattleStatus("This battle is visible to masters only.");
  } else if (battle.status !== "active") {
    setBattleStatus(resultSummary(battle));
  } else if (!canAct) {
    setBattleStatus(`Waiting for ${battle.active_side || "next side"}.`);
  } else if (target) {
    setBattleStatus(`Selected ${target.type}.`);
  } else {
    setBattleStatus("Select a cell, enemy unit, or enemy hero.");
  }
}

async function handleBattleCommand(event) {
  if (!session || !currentState || !selectedBattleId) return;
  const battle = currentState.battles.find((item) => item.battle_id === selectedBattleId);
  if (!battle) return;
  const actorSide = sideForBattle(battle);
  if (!actorSide) return;
  const actionType = event.currentTarget.dataset.battleCommand;
  const payload = battlePayloadFor(actionType, battle, actorSide);
  try {
    setBattleStatus("Sending battle action");
    const result = await apiPost(
      `/api/lord-battles/${encodeURIComponent(battle.battle_id)}/actions`,
      {
        action_type: actionType,
        actor_side: actorSide,
        payload,
      }
    );
    selectedBattleTarget = null;
    selectedBattleId = result.battle?.battle_id || selectedBattleId;
    setBattleStatus(`${actionType}: ${result.status || "ok"}`);
    await loadState(session);
  } catch (error) {
    setBattleStatus(error.message || "Battle action failed");
  }
}

function battlePayloadFor(actionType, battle, actorSide) {
  if (actionType === "move") {
    if (selectedBattleTarget?.type !== "cell") throw new Error("Select an empty cell.");
    return {
      stack_id: battle.active_stack_id,
      to: { x: selectedBattleTarget.x, y: selectedBattleTarget.y },
    };
  }
  if (actionType === "attack") {
    if (selectedBattleTarget?.type === "stack" && selectedBattleTarget.side !== actorSide) {
      return {
        stack_id: battle.active_stack_id,
        target_stack_id: selectedBattleTarget.stack_id,
      };
    }
    if (selectedBattleTarget?.type === "hero" && selectedBattleTarget.side !== actorSide) {
      return {
        stack_id: battle.active_stack_id,
        target_type: "hero",
        target_side: selectedBattleTarget.side,
      };
    }
    throw new Error("Select an enemy unit or hero.");
  }
  return {};
}

function sideForBattle(battle) {
  const domainId = currentState?.lord?.domain_id;
  if (battle.attacker_domain_id === domainId) return "attacker";
  if (battle.defender_domain_id === domainId) return "defender";
  return null;
}

function stackAt(battle, x, y) {
  return (battle.board.stacks || []).find(
    (stack) => Number(stack.x) === x && Number(stack.y) === y && Number(stack.count_alive) > 0
  );
}

function stackById(battle, stackId) {
  return (battle.board.stacks || []).find((stack) => stack.stack_id === stackId) || null;
}

function heroSideAt(battle, x, y) {
  for (const [side, cell] of Object.entries(battle.board.hero_cells || {})) {
    if (Number(cell.x) === x && Number(cell.y) === y) return side;
  }
  return null;
}

function isSelectedBattleTarget(x, y, stack, heroSide) {
  const target = selectedBattleTarget;
  if (!target) return false;
  if (stack && target.type === "stack") return target.stack_id === stack.stack_id;
  if (heroSide && target.type === "hero") return target.side === heroSide;
  return target.type === "cell" && target.x === x && target.y === y;
}

function resultSummary(battle) {
  const result = battle.result || {};
  const capture = result.capture || {};
  if (capture.status === "capture_pending_garrison") {
    return "Capture pending: move an active unit into garrison.";
  }
  return result.winner_side
    ? `Finished: ${result.winner_side} won by ${result.outcome || "resolution"}.`
    : `Battle status: ${battle.status}.`;
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

function setBattleStatus(message) {
  els.battleStatus.textContent = message;
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
