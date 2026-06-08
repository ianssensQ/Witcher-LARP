const TOKEN_KEY = "witcher_larp_lord_token";
const SELECTED_TERRITORY_KEY = "witcher_larp_lord_selected_territory";
const ASSET_ROOT = "/static/lord/assets/generated";

const UNIT_ICONS = {
  infantry: `${ASSET_ROOT}/lords-home/units/unit-infantry-v1.png`,
  guard: `${ASSET_ROOT}/lords-home/units/unit-guard-v1.png`,
  ranged: `${ASSET_ROOT}/lords-home/units/unit-ranged-v1.png`,
  cavalry: `${ASSET_ROOT}/lords-home/units/unit-cavalry-v1.png`,
  heavy_siege: `${ASSET_ROOT}/lords-home/units/unit-heavy-siege-v1.png`,
  specialist: `${ASSET_ROOT}/lords-home/units/unit-specialist-v1.png`,
};

const TERRITORY_BACKGROUNDS = {
  castle: `${ASSET_ROOT}/castle-city-v2.png`,
  fort: `${ASSET_ROOT}/lords-home/territories/territory-home-north-fort-v1.png`,
  river: `${ASSET_ROOT}/lords-home/territories/territory-home-river-gate-v1.png`,
  mist: `${ASSET_ROOT}/lords-home/territories/territory-home-mist-lake-v1.png`,
};

const SURFACE_COPY = {
  map: ["Карта земель", "Маршруты и передвижение"],
  buildings: ["Постройки", "Дерево выбранного владения"],
  orders: ["Доска заказов", "Публичные и адресные поручения"],
  raids: ["Рейды", "Цели, эффекты и истечение"],
  battle: ["Захваты и бои", "Состояния претензий и 5x6 бой"],
  dev: ["Служебные действия", "Реальные mutations текущего runtime"],
};

const els = {
  loginPanel: document.querySelector("#login-panel"),
  dashboard: document.querySelector("#dashboard"),
  homeBackground: document.querySelector("#home-background"),
  surfaceDrawer: document.querySelector("#surface-drawer"),
  surfaceTitle: document.querySelector("#surface-title"),
  surfaceKicker: document.querySelector("#surface-kicker"),
  surfaceClose: document.querySelector("#surface-close"),
  surfaceButtons: document.querySelectorAll("[data-surface-button]"),
  surfacePanels: document.querySelectorAll("[data-surface]"),
  form: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#role-token"),
  loginStatus: document.querySelector("#login-status"),
  lordName: document.querySelector("#lord-name"),
  domainName: document.querySelector("#domain-name"),
  goldValue: document.querySelector("#gold-value"),
  incomeValue: document.querySelector("#income-value"),
  mpValue: document.querySelector("#mp-value"),
  ordersValue: document.querySelector("#orders-value"),
  territoryCount: document.querySelector("#territory-count"),
  selectedTerritoryName: document.querySelector("#selected-territory-name"),
  selectedTerritoryMeta: document.querySelector("#selected-territory-meta"),
  territoryBubbles: document.querySelector("#territory-bubbles"),
  activeArmyLane: document.querySelector("#active-army-lane"),
  activeArmySlots: document.querySelector("#active-army-slots"),
  armyLock: document.querySelector("#army-lock"),
  garrisonSlots: document.querySelector("#garrison-slots"),
  homeRecruitStock: document.querySelector("#home-recruit-stock"),
  mpOrbit: document.querySelector("#mp-orbit"),
  actLabel: document.querySelector("#act-label"),
  actTimer: document.querySelector("#act-timer"),
  activeOrders: document.querySelector("#active-orders"),
  buildingCount: document.querySelector("#building-count"),
  buildingList: document.querySelector("#building-list"),
  raidCount: document.querySelector("#raid-count"),
  raidList: document.querySelector("#raid-list"),
  battleCount: document.querySelector("#battle-count"),
  battlePanelCount: document.querySelector("#battle-panel-count"),
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
  mapViewport: document.querySelector("#lord-map-viewport"),
  lordMap: document.querySelector("#lord-map"),
  mapMinimapShell: document.querySelector("#map-minimap-shell"),
  lordMapMinimap: document.querySelector("#lord-map-minimap"),
  mapStatus: document.querySelector("#map-status"),
  mapResetButton: document.querySelector("#map-reset-button"),
  mapMoveButton: document.querySelector("#map-move-button"),
  mapSelectionCard: document.querySelector("#map-selection-card"),
  mapSelectionTitle: document.querySelector("#map-selection-title"),
  mapSelectionMeta: document.querySelector("#map-selection-meta"),
  mapSelectionDetail: document.querySelector("#map-selection-detail"),
  mapBattleButton: document.querySelector("#map-battle-button"),
  mapGarrisonButton: document.querySelector("#map-garrison-button"),
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
let selectedMapNodeId = null;
let selectedTerritoryId = localStorage.getItem(SELECTED_TERRITORY_KEY);
let activeSurface = null;
let mapViewBox = null;
let mapDrag = null;
let suppressNextMapClick = false;
let selectedRoutePreview = null;
let routePreviewSerial = 0;
let routePreviewPendingNodeId = null;

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
  selectedMapNodeId = valueOrNull(els.moveTarget.value);
  updateMoveRoutePreview(selectedMapNodeId);
  if (selectedMapNodeId) requestRoutePreview(selectedMapNodeId);
});

els.mapResetButton.addEventListener("click", () => {
  resetMapView(currentState);
  renderLordMap(currentState);
});

els.mapMoveButton.addEventListener("click", async () => {
  await moveSelectedMapTarget();
});

els.mapBattleButton.addEventListener("click", () => {
  const battle = battleForSelectedMapNode(currentState);
  if (battle) {
    selectedBattleId = battle.battle_id;
    openSurface("battle");
    return;
  }
  const claim = claimForSelectedMapNode(currentState);
  if (claim?.claimant_domain_id === currentState?.lord?.domain_id) {
    createBattleForClaim(claim);
    return;
  }
  openSurface("battle");
});

els.mapGarrisonButton.addEventListener("click", () => {
  const target = garrisonTargetForSelectedMapNode(currentState);
  if (target?.territory_id) els.garrisonTerritory.value = target.territory_id;
  openSurface("dev");
});

els.lordMap.addEventListener("pointerdown", startMapPan);
els.lordMap.addEventListener("pointermove", continueMapPan);
els.lordMap.addEventListener("pointerup", endMapPan);
els.lordMap.addEventListener("pointercancel", endMapPan);
els.lordMap.addEventListener("lostpointercapture", endMapPan);
els.mapMinimapShell.addEventListener("click", recenterMapFromMinimap);

window.addEventListener("resize", () => {
  if (activeSurface !== "map" || !currentState) return;
  resetMapView(currentState);
  renderLordMap(currentState);
});

for (const button of els.surfaceButtons) {
  button.addEventListener("click", () => {
    openSurface(button.dataset.surfaceButton);
  });
}

els.surfaceClose.addEventListener("click", closeSurface);

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
  if (window.location.pathname !== "/lords/login") {
    window.history.replaceState(null, "", "/lords/login");
  }
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
  setStatus("Проверяю токен");
  try {
    const response = await fetch("/api/auth/role-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (!response.ok) throw new Error("Токен не принят");
    const auth = await response.json();
    if (auth.role_type !== "lord" || !auth.lord_id) {
      throw new Error("Токен не привязан к панели графа");
    }
    session = { token, auth };
    localStorage.setItem(TOKEN_KEY, token);
    els.loginPanel.hidden = true;
    els.dashboard.hidden = false;
    if (window.location.pathname !== "/lords/home") {
      window.history.replaceState(null, "", "/lords/home");
    }
    await loadState(session);
  } catch (error) {
    localStorage.removeItem(TOKEN_KEY);
    setStatus(error.message);
  }
}

async function loadState(currentSession) {
  setStatus("Загружаю состояние");
  const response = await fetch(`/api/lords/${currentSession.auth.lord_id}/state`, {
    headers: { "X-Role-Token": currentSession.token },
  });
  if (!response.ok) {
    setStatus(`State request failed: ${response.status}`);
    return;
  }
  const state = await response.json();
  currentState = state;
  selectedRoutePreview = null;
  renderState(state);
  if (state.pending_move) {
    setStatus(`Армия в пути: ${routeLabel(state.pending_move.route_node_ids || state.pending_move.route || [])}, прибытие ${state.pending_move.arrival_at || "-"}`);
  } else {
    setStatus(`Слепок: ${state.snapshot_version || "не импортирован"}`);
  }
}

function renderState(state) {
  const selectedTerritory = selectedTerritoryForState(state);
  els.lordName.textContent = state.lord.display_name;
  els.domainName.textContent = state.domain.name || state.lord.domain_id;
  els.goldValue.textContent = `${state.domain.gold ?? state.domain.starting_gold ?? state.lord.gold}g`;
  els.incomeValue.textContent = `+${state.domain.base_income ?? state.domain.income ?? 0}/ч`;
  els.mpValue.textContent = state.movement
    ? `${state.movement.current_mp}/${state.movement.mp_cap}`
    : "-";
  els.ordersValue.textContent = `${state.summary.active_orders}`;
  els.territoryCount.textContent = `${state.summary.owned_territories}`;
  els.activeOrders.textContent = `${state.summary.active_orders} активных`;
  els.battleCount.textContent = `${state.summary.active_battles || 0}`;
  els.battlePanelCount.textContent = `${state.summary.active_battles || 0} боев`;
  els.raidCount.textContent = `${state.summary.active_raids || 0} активных`;

  renderHome(state, selectedTerritory);
  renderTerritories(state.territories);
  renderCaptures(state);
  renderBattles(state.battles || []);
  renderOrders(state.orders || []);
  renderRecruit(state.recruit_market);
  renderBuildings(state.building_catalog || []);
  renderRaids(state.raid_effects || []);
  renderActionOptions(state);
  renderLordMap(state);
  updateMoveRoutePreview(selectedMapNodeId);
  if (selectedMapNodeId && selectedMapNodeId !== state.movement?.current_node_id) {
    requestRoutePreview(selectedMapNodeId);
  }
}

function renderHome(state, selectedTerritory) {
  const background = territoryBackground(selectedTerritory);
  els.homeBackground.style.backgroundImage = `url("${background}")`;
  els.selectedTerritoryName.textContent = selectedTerritory?.name || "Владение не выбрано";
  els.selectedTerritoryMeta.textContent = selectedTerritory
    ? [
        selectedTerritory.node_name || selectedTerritory.node_id,
        `T${selectedTerritory.tier || "?"}`,
        bonusLabel(selectedTerritory.bonus_type),
        selectedTerritory.status || "controlled",
      ].filter(Boolean).join(" - ")
    : "Нет захваченных территорий";
  renderTerritoryBubbles(state, selectedTerritory);
  renderMovementMeter(state);
  renderHomeArmy(state, selectedTerritory);
  renderHomeRecruit(state);
  renderActWidget(state);
}

function selectedTerritoryForState(state) {
  const owned = state.territories || [];
  if (!owned.length) {
    selectedTerritoryId = null;
    localStorage.removeItem(SELECTED_TERRITORY_KEY);
    return null;
  }
  const activeNodeId = activeArmyNodeId(state) || state.movement?.current_node_id;
  const activeTerritory = owned.find((territory) => territory.node_id === activeNodeId);
  const savedTerritory = selectedTerritoryId
    ? owned.find((territory) => territory.territory_id === selectedTerritoryId)
    : null;
  const selected = savedTerritory || activeTerritory || owned[0];
  selectedTerritoryId = selected.territory_id;
  localStorage.setItem(SELECTED_TERRITORY_KEY, selectedTerritoryId);
  return selected;
}

function renderTerritoryBubbles(state, selectedTerritory) {
  const territories = state.territories || [];
  els.territoryBubbles.replaceChildren();
  if (!territories.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Нет владений";
    els.territoryBubbles.append(empty);
    return;
  }
  for (const territory of territories) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-pressed", territory.territory_id === selectedTerritory?.territory_id ? "true" : "false");
    button.setAttribute("aria-label", territory.name);
    button.innerHTML = `
      <img src="${escapeHtml(territoryBackground(territory))}" alt="" draggable="false">
      <strong>${escapeHtml(shortTerritoryName(territory.name))}</strong>
    `;
    button.addEventListener("click", () => {
      selectedTerritoryId = territory.territory_id;
      localStorage.setItem(SELECTED_TERRITORY_KEY, selectedTerritoryId);
      renderState(currentState);
    });
    els.territoryBubbles.append(button);
  }
}

function renderMovementMeter(state) {
  const current = Number(state.movement?.current_mp ?? 0);
  const max = Math.max(1, Number(state.movement?.mp_cap ?? (current || 1)));
  els.mpOrbit.replaceChildren();
  for (let index = 0; index < max; index += 1) {
    const dot = document.createElement("span");
    dot.className = `mp-dot${index < current ? " full" : ""}`;
    els.mpOrbit.append(dot);
  }
}

function renderActWidget(state) {
  const actId = state.act?.act_id || state.current_act?.act_id || "Акт";
  els.actLabel.textContent = String(actId).replaceAll("_", " ");
  els.actTimer.textContent = state.act?.status || state.current_act?.status || "runtime";
}

function renderHomeArmy(state, selectedTerritory) {
  const activeNodeId = activeArmyNodeId(state) || state.movement?.current_node_id;
  const selectedNodeId = selectedTerritory?.node_id;
  const heroHere = Boolean(selectedTerritory && (!activeNodeId || !selectedNodeId || activeNodeId === selectedNodeId));
  const activeStacks = heroHere ? activeArmyStacks(state) : [];
  const lockTarget = activeNodeId ? labelForNodeId(state, activeNodeId) : "другая локация";
  els.activeArmyLane.classList.toggle("is-locked", !heroHere);
  els.armyLock.hidden = heroHere;
  els.armyLock.textContent = heroHere ? "" : `Герой-армия сейчас в ${lockTarget}`;
  renderUnitSlots(els.activeArmySlots, activeStacks, { emptyCount: 8 });
  renderUnitSlots(els.garrisonSlots, selectedTerritory?.garrisons || [], { emptyCount: 8 });
}

function renderHomeRecruit(state) {
  const offers = state.recruit_market || [];
  els.homeRecruitStock.replaceChildren();
  if (!offers.length) {
    for (let index = 0; index < 6; index += 1) {
      const empty = document.createElement("button");
      empty.type = "button";
      empty.className = "recruit-card empty";
      empty.disabled = true;
      els.homeRecruitStock.append(empty);
    }
    return;
  }
  for (const offer of offers.slice(0, 8)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `recruit-card${offer.status !== "available" ? " locked" : ""}`;
    button.title = `${offer.card_id}: ${offer.status}`;
    button.innerHTML = `
      <img src="${escapeHtml(unitIcon(offer))}" alt="" draggable="false">
      <small>${escapeHtml(offer.status || "offer")}</small>
      <b>${escapeHtml(offer.cost ?? "-")}g</b>
    `;
    button.addEventListener("click", () => {
      openSurface("dev");
      if ([...els.recruitOffer.options].some((option) => option.value === offer.offer_id)) {
        els.recruitOffer.value = offer.offer_id;
      }
    });
    els.homeRecruitStock.append(button);
  }
}

function renderUnitSlots(target, stacks, { emptyCount }) {
  target.replaceChildren();
  const normalized = (stacks || []).filter((stack) => Number(stack.count || stack.count_alive || 0) > 0);
  const total = Math.max(emptyCount, normalized.length);
  for (let index = 0; index < total; index += 1) {
    const stack = normalized[index];
    const slot = document.createElement("button");
    slot.type = "button";
    slot.className = `unit-slot${stack ? "" : " empty"}`;
    slot.disabled = !stack;
    if (stack) {
      const count = stack.count ?? stack.count_alive ?? 0;
      slot.innerHTML = `
        <img src="${escapeHtml(unitIcon(stack))}" alt="" draggable="false">
        <b>${escapeHtml(count)}</b>
      `;
      slot.title = `${stack.card_id || stack.unit_class || "unit"} x${count}`;
    }
    target.append(slot);
  }
}

function renderBuildings(items) {
  els.buildingCount.textContent = `${items.length}`;
  renderList(els.buildingList, items, (item) => {
    const card = document.createElement("article");
    const status = item.status || "locked";
    card.className = `building-card ${status}`;
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.name || item.building_id)}</span>
        <span>${escapeHtml(status)}</span>
      </div>
      <div class="row-meta">Стоимость: ${escapeHtml(item.gold_cost ?? "-")}g</div>
      <div class="row-meta">Требования: ${escapeHtml(item.prerequisite_ids || "нет")}</div>
      <div class="row-meta">Открывает: ${escapeHtml(item.recruit_unlock_ids || item.effect || "-")}</div>
    `;
    if (status !== "owned") {
      card.addEventListener("click", () => {
        openSurface("dev");
        if ([...els.buildingId.options].some((option) => option.value === item.building_id)) {
          els.buildingId.value = item.building_id;
        }
      });
    }
    return card;
  });
}

function renderRaids(items) {
  renderList(els.raidList, items, (item) => {
    const card = rowCard();
    card.classList.toggle("warn", item.status === "active");
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.target_territory_id)}</span>
        <span>${escapeHtml(item.status)}</span>
      </div>
      <div class="row-meta">${escapeHtml(item.raid_effect_id || item.rule_id || "raid")}</div>
      <div class="row-meta">Источник: ${escapeHtml(item.source_domain_id)} - до ${escapeHtml(item.expires_at || "-")}</div>
    `;
    return card;
  });
}

function activeArmyStacks(state) {
  return (state.active_army || []).filter((item) => item.status === "active" && Number(item.count) > 0);
}

function activeArmyNodeId(state) {
  return activeArmyStacks(state).find((item) => item.location_node_id)?.location_node_id || null;
}

function labelForNodeId(state, nodeId) {
  const territory = allTerritories(state).find((item) => item.node_id === nodeId);
  if (territory?.name) return territory.name;
  return seedNodesById(state).get(nodeId)?.name || nodeId;
}

function territoryBackground(territory) {
  if (!territory) return TERRITORY_BACKGROUNDS.castle;
  const text = `${territory.territory_id || ""} ${territory.name || ""} ${territory.bonus_type || ""}`.toLowerCase();
  if (text.includes("residence")) return TERRITORY_BACKGROUNDS.castle;
  if (text.includes("fort") || text.includes("defense") || text.includes("zastava") || text.includes("ostrog")) {
    return TERRITORY_BACKGROUNDS.fort;
  }
  if (text.includes("river") || text.includes("field") || text.includes("gold") || text.includes("order") || text.includes("village")) {
    return TERRITORY_BACKGROUNDS.river;
  }
  return TERRITORY_BACKGROUNDS.mist;
}

function shortTerritoryName(name) {
  const words = String(name || "Владение").split(/\s+/).filter(Boolean);
  return words.slice(0, 2).join(" ");
}

function bonusLabel(value) {
  return String(value || "без бонуса").replaceAll("_", " ");
}

function unitIcon(item) {
  const cardId = String(item.card_id || "").toLowerCase();
  const unitClass = String(item.unit_class || "").toLowerCase();
  if (cardId.includes("guard") || unitClass.includes("guard")) return UNIT_ICONS.guard;
  if (cardId.includes("ranged") || unitClass.includes("ranged")) return UNIT_ICONS.ranged;
  if (cardId.includes("cavalry") || unitClass.includes("cavalry")) return UNIT_ICONS.cavalry;
  if (cardId.includes("siege") || unitClass.includes("siege")) return UNIT_ICONS.heavy_siege;
  if (cardId.includes("specialist") || unitClass.includes("specialist")) return UNIT_ICONS.specialist;
  return UNIT_ICONS.infantry;
}

function openSurface(surface) {
  if (!SURFACE_COPY[surface]) return;
  activeSurface = surface;
  els.surfaceDrawer.hidden = false;
  els.surfaceDrawer.dataset.activeSurface = surface;
  els.dashboard.dataset.activeSurface = surface;
  const [title, kicker] = SURFACE_COPY[surface];
  els.surfaceTitle.textContent = title;
  els.surfaceKicker.textContent = kicker;
  for (const panel of els.surfacePanels) {
    panel.hidden = panel.dataset.surface !== surface;
  }
  if (surface === "map" && currentState) {
    resetMapView(currentState);
    renderLordMap(currentState);
  }
}

function closeSurface() {
  activeSurface = null;
  els.surfaceDrawer.hidden = true;
  delete els.surfaceDrawer.dataset.activeSurface;
  delete els.dashboard.dataset.activeSurface;
}

function renderTerritories(items) {
  if (!els.territoryList) return;
  renderList(els.territoryList, items, (item) => {
    const card = rowCard();
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.name)}</span>
        <span>T${escapeHtml(item.tier)}</span>
      </div>
      <div class="row-meta">${escapeHtml(item.node_name)} - ${escapeHtml(item.bonus_type)}</div>
      <div class="row-meta">Гарнизон: ${(item.garrisons || []).length} - Награды: ${(item.pending_rewards || []).length}</div>
    `;
    if ((item.pending_rewards || []).length > 0) card.classList.add("warn");
    return card;
  });
}

function renderCaptures(state) {
  const claims = (state?.claims || []).filter(
    (item) => item.claimant_domain_id === state.lord.domain_id
      && item.status !== "awaiting_garrison"
      && !battleForClaim(state, item)
  );
  const pending = (state?.garrison_targets || []).filter(
    (item) => item.garrison_target_reason === "capture_pending_garrison"
  );
  renderList(els.captureList, [...claims, ...pending], (item) => {
    const card = rowCard();
    card.classList.add("warn");
    if (item.claim_id) {
      card.innerHTML = `
        <div class="row-main">
          <span>${escapeHtml(item.territory_name || item.territory_id)}</span>
          <span>Нужен бой</span>
        </div>
        <div class="row-meta">${escapeHtml(item.status)} - ${escapeHtml(item.node_name || item.node_id)}</div>
      `;
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Создать бой";
      button.addEventListener("click", async () => {
        await createBattleForClaim(item);
      });
      card.append(button);
      return card;
    }
    card.innerHTML = `
      <div class="row-main">
        <span>${escapeHtml(item.name)}</span>
        <span>Нужен гарнизон</span>
      </div>
      <div class="row-meta">${escapeHtml(item.status)} - ${escapeHtml(item.node_name)}</div>
      <div class="row-meta">Переведите активный отряд в гарнизон, чтобы завершить захват.</div>
    `;
    return card;
  });
}

function battleForClaim(state, claim) {
  return (state?.battles || []).find(
    (battle) => battle.claim_id === claim.claim_id
      || battle.territory_id === claim.territory_id && battle.status === "active"
  ) || null;
}

async function createBattleForClaim(claim) {
  if (!session || !currentState || !claim?.claim_id) return;
  try {
    setActionStatus("Создаю бой");
    const battle = await apiPost("/api/lord-battles", {
      attacker_domain_id: currentState.lord.domain_id,
      territory_id: claim.territory_id,
      claim_id: claim.claim_id,
    });
    selectedBattleId = battle.battle_id;
    await loadState(session);
    openSurface("battle");
  } catch (error) {
    setActionStatus(error.message || "Бой не создан");
  }
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
  if (!els.recruitList) return;
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
    "Нет узлов карты"
  );
  setOptions(
    els.garrisonTerritory,
    state.garrison_targets || state.territories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.status}${item.garrison_target_reason === "capture_pending_garrison" ? ", capture pending" : ""})`,
    "Нет доступных территорий"
  );
  updateGarrisonCardOptions();
  setOptions(
    els.buildingId,
    state.building_catalog.filter((item) => item.status !== "owned"),
    (item) => item.building_id,
    (item) => `${item.name} (${item.gold_cost}g)`,
    "Нет построек"
  );
  setOptions(
    els.recruitOffer,
    state.recruit_market,
    (item) => item.offer_id,
    (item) => `${item.card_id} (${item.status}, ${item.cost}g)`,
    "Обновите предложения"
  );
  setOptions(
    els.raidTarget,
    state.other_territories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.owner_domain_id})`,
    "Нет целей рейда"
  );
  setOptions(
    els.battleTerritory,
    allTerritories,
    (item) => item.territory_id,
    (item) => `${item.name} (${item.status})`,
    "Нет территорий"
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
      "Нет отрядов в резерве"
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
      "Нет отрядов в форте"
    );
    return;
  }
  setOptions(
    els.garrisonCard,
    currentState.active_army.filter((item) => item.status === "active" && Number(item.count) > 0),
    (item) => item.card_id,
    (item) => `${item.card_id} x${item.count}`,
    "Нет активных отрядов"
  );
}

async function handleActionSubmit(event) {
  event.preventDefault();
  if (!session || !currentState) return;
  const form = event.currentTarget;
  const action = form.dataset.actionForm;
  try {
    setActionStatus("Отправляю");
    const result = await runAction(action, form, event.submitter);
    setActionStatus(`${action}: ${result.status || "ok"}`);
    await loadState(session);
  } catch (error) {
    setActionStatus(error.message || "Действие не выполнено");
  }
}

async function runAction(action, form, submitter) {
  const lordId = session.auth.lord_id;
  const formData = new FormData(form);
  if (action === "move") {
    const targetNodeId = valueOrNull(formData.get("to_node_id"));
    const preview = await ensureRoutePreview(targetNodeId);
    const route = previewRoute(preview);
    if (!preview?.can_move || !route) {
      throw new Error("invalid_route: нет маршрута по графу");
    }
    return apiPost(`/api/lords/${lordId}/move`, {
      to_node_id: targetNodeId,
      route_node_ids: route.nodes,
      expected_cost: route.cost,
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
    ? `Ход: ${battle.active_side || "нет стороны"} - ${activeStack?.card_id || "нет активного отряда"}`
    : `${battle.status} - ${battle.result?.outcome || "решено"}`;

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
    setBattleStatus("Этот бой полностью виден только мастерам.");
  } else if (battle.status !== "active") {
    setBattleStatus(resultSummary(battle));
  } else if (!canAct) {
    setBattleStatus(`Ожидание стороны: ${battle.active_side || "следующая"}.`);
  } else if (target) {
    setBattleStatus(`Выбрано: ${target.type}.`);
  } else {
    setBattleStatus("Выберите клетку, вражеский отряд или героя.");
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
    setBattleStatus("Отправляю действие боя");
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
    setBattleStatus(error.message || "Действие боя не выполнено");
  }
}

function battlePayloadFor(actionType, battle, actorSide) {
  if (actionType === "move") {
    if (selectedBattleTarget?.type !== "cell") throw new Error("Выберите пустую клетку.");
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
    throw new Error("Выберите вражеский отряд или героя.");
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
    return "Захват ожидает гарнизон: переведите активный отряд в форт.";
  }
  return result.winner_side
    ? `Завершено: ${result.winner_side} победил, исход ${result.outcome || "resolution"}.`
    : `Статус боя: ${battle.status}.`;
}

function renderList(target, items, factory) {
  if (!target) return;
  target.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Нет записей";
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
  if (!els.dashboard.hidden) {
    setActionStatus(message);
  }
}

function setActionStatus(message) {
  els.actionStatus.textContent = message;
}

function setBattleStatus(message) {
  els.battleStatus.textContent = message;
}

function setMapStatus(message) {
  els.mapStatus.textContent = message;
}

function updateMoveRoutePreview(requestedTargetNodeId = undefined) {
  if (!els.moveRoutePreview || !currentState) return;
  const targetNodeId = requestedTargetNodeId !== undefined
    ? requestedTargetNodeId
    : selectedMapNodeId;
  const preview = matchingRoutePreview(targetNodeId);
  const route = previewRoute(preview) || buildRoute(currentState, targetNodeId);
  els.moveRoutePreview.textContent = route
    ? `${route.nodes.join(" -> ")} (${route.cost} MP)`
    : "Нет маршрута";
  selectedMapNodeId = targetNodeId;
  if ([...els.moveTarget.options].some((option) => option.value === targetNodeId)) {
    els.moveTarget.value = targetNodeId;
  }
  if (preview?.reason) {
    els.moveRoutePreview.textContent = `${els.moveRoutePreview.textContent} - ${preview.reason}`;
  }
  if (!preview && isRoutePreviewPending(targetNodeId)) {
    els.moveRoutePreview.textContent = `${els.moveRoutePreview.textContent} - проверяю`;
  }
  renderLordMap(currentState);
}

function matchingRoutePreview(targetNodeId) {
  if (!targetNodeId || !selectedRoutePreview) return null;
  return selectedRoutePreview.requested_to_node_id === targetNodeId ? selectedRoutePreview : null;
}

function isRoutePreviewPending(targetNodeId) {
  return Boolean(targetNodeId && routePreviewPendingNodeId === targetNodeId);
}

function previewRoute(preview) {
  if (!preview?.route?.length || preview.route.length < 2) return null;
  return {
    nodes: preview.route,
    cost: Number(preview.mp_cost || 0),
  };
}

async function requestRoutePreview(targetNodeId) {
  if (!session || !currentState || !targetNodeId || currentState.pending_move?.status === "pending") {
    return null;
  }
  const serial = routePreviewSerial + 1;
  routePreviewSerial = serial;
  routePreviewPendingNodeId = targetNodeId;
  selectedRoutePreview = null;
  updateMoveRoutePreview();
  try {
    const preview = await apiPost(`/api/lords/${session.auth.lord_id}/route-preview`, {
      to_node_id: targetNodeId,
    });
    if (serial !== routePreviewSerial || selectedMapNodeId !== targetNodeId) return preview;
    routePreviewPendingNodeId = null;
    selectedRoutePreview = preview;
    updateMoveRoutePreview();
    return preview;
  } catch (error) {
    if (serial === routePreviewSerial && selectedMapNodeId === targetNodeId) {
      routePreviewPendingNodeId = null;
      selectedRoutePreview = {
        status: "blocked",
        can_move: false,
        requested_to_node_id: targetNodeId,
        route: [],
        mp_cost: 0,
        reason: error.message || "Маршрут недоступен",
      };
      updateMoveRoutePreview();
    }
    return selectedRoutePreview;
  }
}

async function ensureRoutePreview(targetNodeId) {
  const preview = matchingRoutePreview(targetNodeId);
  if (preview) return preview;
  return requestRoutePreview(targetNodeId);
}

function renderLordMap(state) {
  const layout = state?.lord_map_layout;
  if (!layout?.canvas || !els.lordMap) {
    setMapStatus("Слой карты недоступен");
    els.mapMoveButton.disabled = true;
    return;
  }
  const width = Number(layout.canvas.width || 0);
  const height = Number(layout.canvas.height || 0);
  if (!width || !height) {
    setMapStatus("Слой карты поврежден");
    els.mapMoveButton.disabled = true;
    return;
  }
  if (!mapViewBox) resetMapView(state);

  const svg = els.lordMap;
  svg.dataset.mapMode = layout.mode || "";
  svg.setAttribute("viewBox", viewBoxString(mapViewBox));
  svg.replaceChildren();
  svg.append(svgNode("rect", { class: "map-canvas", x: 0, y: 0, width, height }));
  const territoryByNode = territoriesByNodeId(state);
  const seedNodeById = seedNodesById(state);
  svg.append(renderMapOwnershipSockets(state, layout, territoryByNode, seedNodeById));
  const background = renderMapBackground(layout, width, height);
  if (background) svg.append(background);
  if (layout.visibility?.socket_rims_visible !== false) {
    svg.append(renderMapSocketRims(layout));
  }
  if (layout.visibility?.central_house_overlay_visible !== false) {
    svg.append(renderCentralHouse(layout.central_house));
  }

  if (layout.visibility?.svg_edges_visible !== false) {
    const edgeLayer = svgNode("g", { class: "map-edge-layer" });
    for (const edge of state.map_edges || []) {
      const edgeLayout = layout.edges?.[edge.edge_id];
      if (!edgeLayout?.points?.length) continue;
      edgeLayer.append(svgNode("path", {
        class: "map-road-bed",
        d: pathFromPoints(edgeLayout.points),
      }));
      edgeLayer.append(svgNode("path", {
        class: "map-edge",
        d: pathFromPoints(edgeLayout.points),
      }));
      edgeLayer.append(renderEdgeCost(edge, edgeLayout.points));
    }
    svg.append(edgeLayer);
  }

  const zoneLayer = svgNode("g", { class: "map-zone-layer" });
  for (const [nodeId, node] of Object.entries(layout.nodes || {})) {
    const seedNode = seedNodeById.get(nodeId) || {};
    const territory = territoryByNode.get(nodeId);
    const shape = hitZoneShape(node.hit_zone);
    if (!shape) continue;
    shape.classList.add("map-zone", mapNodeClass(state, seedNode, territory, node));
    if (nodeId === selectedMapNodeId) shape.classList.add("selected");
    shape.dataset.nodeId = nodeId;
    shape.append(svgNode("title", {}, mapNodeTitle(seedNode, territory)));
    if (node.ui_target) {
      shape.addEventListener("click", () => selectMapNode(nodeId));
    }
    zoneLayer.append(shape);
  }
  svg.append(zoneLayer);

  const route = previewRoute(matchingRoutePreview(selectedMapNodeId)) || buildRoute(state, selectedMapNodeId);
  const routePoints = route ? routePointsForRoute(state, layout, route.nodes) : [];
  if (routePoints.length >= 2) {
    svg.append(svgNode("path", {
      class: "map-route",
      d: pathFromPoints(routePoints),
    }));
  }

  const nodeLayer = svgNode("g", { class: "map-node-layer" });
  const labelLayer = svgNode("g", { class: "map-label-layer" });
  const activeNodeId = activeArmyNodeId(state) || state.movement?.current_node_id;
  for (const [nodeId, node] of Object.entries(layout.nodes || {})) {
    const seedNode = seedNodeById.get(nodeId) || {};
    const territory = territoryByNode.get(nodeId);
    const nodeClass = mapNodeClass(state, seedNode, territory, node);
    nodeLayer.append(svgNode("circle", {
      class: `map-node-dot ${nodeClass}`,
      cx: node.x,
      cy: node.y,
      r: node.ui_target ? 20 : 12,
    }));
    const label = labelForMapNode(seedNode, territory);
    if (label && (nodeId === selectedMapNodeId || nodeId === activeNodeId)) {
      labelLayer.append(svgNode(
        "text",
        {
          class: "map-label",
          x: node.label_anchor?.x ?? node.x,
          y: node.label_anchor?.y ?? node.y,
          "text-anchor": "middle",
        },
        label,
      ));
    }
  }
  if (layout.visibility?.svg_node_markers_visible !== false) {
    svg.append(nodeLayer);
  }
  svg.append(labelLayer);
  svg.append(renderArmyMarker(state, layout));

  updateMapStatus(state, route);
  renderMinimap(state, layout, route);
}

function renderMapOwnershipSockets(state, layout, territoryByNode, seedNodeById) {
  const layer = svgNode("g", { class: "map-owner-socket-layer" });
  for (const [nodeId, node] of Object.entries(layout.nodes || {})) {
    const socket = node.ownership_socket;
    const territory = territoryByNode.get(nodeId);
    if (!socket || !territory) continue;
    const seedNode = seedNodeById.get(nodeId) || {};
    layer.append(svgNode("circle", {
      class: `map-owner-socket ${mapNodeClass(state, seedNode, territory, node)}`,
      cx: socket.cx,
      cy: socket.cy,
      r: socket.r,
    }));
  }
  return layer;
}

function renderMapSocketRims(layout) {
  const layer = svgNode("g", { class: "map-socket-rim-layer" });
  for (const node of Object.values(layout.nodes || {})) {
    const socket = node.ownership_socket;
    if (!socket) continue;
    layer.append(svgNode("circle", {
      class: "map-socket-rim",
      cx: socket.cx,
      cy: socket.cy,
      r: socket.r,
    }));
  }
  return layer;
}

function renderCentralHouse(centralHouse) {
  if (!centralHouse) return svgNode("g");
  return svgNode("rect", {
    class: "map-central-house",
    x: centralHouse.x,
    y: centralHouse.y,
    width: centralHouse.w,
    height: centralHouse.h,
    rx: 10,
  });
}

function renderMapBackground(layout, width, height) {
  const asset = valueOrNull(layout.art_asset) || valueOrNull(layout.future_art_asset);
  if (!asset) return null;
  return svgNode("image", {
    class: "map-background",
    href: resolveLordAssetHref(asset),
    x: 0,
    y: 0,
    width,
    height,
    preserveAspectRatio: "none",
  });
}

function renderEdgeCost(edge, points) {
  const middle = points[Math.floor(points.length / 2)];
  return svgNode(
    "text",
    {
      class: "map-cost-label",
      x: middle[0],
      y: middle[1] - 10,
      "text-anchor": "middle",
    },
    String(edge.mp_cost ?? ""),
  );
}

function renderArmyMarker(state, layout) {
  const anchor = armyMarkerAnchor(state, layout);
  if (!anchor) return svgNode("g");
  const scale = mapUiScale(layout);
  const marker = svgNode("g", {
    class: "map-army-marker",
    transform: `translate(${anchor.x} ${anchor.y}) scale(${scale})`,
  });
  marker.append(svgNode("circle", { cx: 0, cy: 0, r: 28 }));
  marker.append(svgNode("path", { d: "M -10 10 L 0 -16 L 12 10 Z" }));
  marker.append(svgNode("text", { x: 0, y: 48 }, "Армия"));
  return marker;
}

function mapUiScale(layout) {
  return Math.max(1, Number(layout?.canvas?.width || 2400) / 2400);
}

function armyMarkerAnchor(state, layout) {
  const pending = state?.pending_move;
  if (pending?.status === "pending") {
    const points = routePointsForRoute(state, layout, pending.route || []);
    if (points.length >= 2) return pointAlongPolyline(points, pendingProgress(pending));
    const target = layout.nodes?.[pending.to_node_id];
    if (target) return target.marker_anchor || target;
  }
  const nodeId = state?.movement?.current_node_id;
  const node = nodeId ? layout.nodes?.[nodeId] : null;
  return node ? node.marker_anchor || node : null;
}

function pendingProgress(pending) {
  const started = Date.parse(pending.started_at || "");
  const arrival = Date.parse(pending.arrival_at || "");
  const now = Date.now();
  if (!Number.isFinite(started) || !Number.isFinite(arrival) || arrival <= started) {
    return 1;
  }
  return Math.max(0, Math.min(1, (now - started) / (arrival - started)));
}

function pointAlongPolyline(points, progress) {
  const segments = [];
  let total = 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    const from = points[index];
    const to = points[index + 1];
    const length = Math.hypot(to[0] - from[0], to[1] - from[1]);
    segments.push({ from, to, length });
    total += length;
  }
  let remaining = total * progress;
  for (const segment of segments) {
    if (remaining <= segment.length) {
      const ratio = segment.length ? remaining / segment.length : 0;
      return {
        x: segment.from[0] + (segment.to[0] - segment.from[0]) * ratio,
        y: segment.from[1] + (segment.to[1] - segment.from[1]) * ratio,
      };
    }
    remaining -= segment.length;
  }
  const last = points[points.length - 1];
  return { x: last[0], y: last[1] };
}

function selectMapNode(nodeId) {
  if (suppressNextMapClick) {
    suppressNextMapClick = false;
    return;
  }
  selectedMapNodeId = nodeId;
  if ([...els.moveTarget.options].some((option) => option.value === nodeId)) {
    els.moveTarget.value = nodeId;
  }
  updateMoveRoutePreview(nodeId);
  requestRoutePreview(nodeId);
}

async function moveSelectedMapTarget() {
  if (!session || !currentState || !selectedMapNodeId) return;
  try {
    const preview = await ensureRoutePreview(selectedMapNodeId);
    const route = previewRoute(preview);
    if (!preview?.can_move || !route) {
      setActionStatus(preview?.reason || "Маршрут недоступен");
      return;
    }
    setActionStatus("Отправляю передвижение");
    const result = await apiPost(`/api/lords/${session.auth.lord_id}/move`, {
      to_node_id: selectedMapNodeId,
      route_node_ids: route.nodes,
      expected_cost: route.cost,
    });
    setActionStatus(`move: ${result.status || "ok"}`);
    await loadState(session);
  } catch (error) {
    setActionStatus(error.message || "Передвижение не выполнено");
  }
}

function updateMapStatus(state, route) {
  if (state.pending_move?.status === "pending") {
    renderMapSelection(state, matchingRoutePreview(selectedMapNodeId), route);
    const target = seedNodesById(state).get(state.pending_move.to_node_id)?.name || state.pending_move.to_node_id;
    setMapStatus(`Армия в пути к ${target} - прибытие ${state.pending_move.arrival_at}`);
    els.mapMoveButton.disabled = true;
    return;
  }
  const nodeId = selectedMapNodeId;
  const territory = nodeId ? territoriesByNodeId(state).get(nodeId) : null;
  const preview = matchingRoutePreview(nodeId);
  renderMapSelection(state, preview, route);
  const label = territory?.name || seedNodesById(state).get(nodeId)?.name || "Нет цели";
  if (!nodeId || !route) {
    setMapStatus(`${label} - нет маршрута`);
    els.mapMoveButton.disabled = true;
    return;
  }
  if (!preview) {
    setMapStatus(`${label} - проверяю маршрут`);
    els.mapMoveButton.disabled = true;
    return;
  }
  setMapStatus(`${label} - ${route.cost} MP`);
  els.mapMoveButton.disabled = !preview.can_move;
}

function renderMapSelection(state, preview, route) {
  if (!els.mapSelectionCard) return;
  const nodeId = selectedMapNodeId;
  const seedNode = nodeId ? seedNodesById(state).get(nodeId) : null;
  const territory = selectedMapTerritory(state);
  if (!nodeId || (!seedNode && !territory)) {
    els.mapSelectionCard.hidden = true;
    return;
  }
  const battle = battleForSelectedMapNode(state);
  const claim = claimForSelectedMapNode(state);
  const garrisonTarget = garrisonTargetForSelectedMapNode(state);
  els.mapSelectionCard.hidden = false;
  els.mapSelectionTitle.textContent = territory?.name || seedNode?.name || nodeId;
  els.mapSelectionMeta.textContent = [
    territory?.status || seedNode?.zone_status,
    ownerLabel(state, territory?.owner_domain_id),
    territory?.fort ? `форт ${territory.fort.garrison_capacity}` : null,
  ].filter(Boolean).join(" - ");
  const routeText = route
    ? `Маршрут: ${route.nodes.join(" -> ")} (${route.cost} MP)`
    : "Маршрут не выбран";
  const outcome = preview?.outcome?.kind === "will_create_claim"
    ? "После прибытия появится претензия и бой."
    : preview?.outcome?.kind === "existing_claim"
      ? "На территории уже есть активная претензия."
      : preview?.outcome?.kind === "controlled"
        ? "Территория под вашим контролем."
        : "";
  els.mapSelectionDetail.textContent = [
    routeText,
    !preview && route ? "Проверяю маршрут на сервере." : null,
    preview?.reason,
    outcome,
    battle ? `Активный бой: ${battle.battle_id}` : null,
    garrisonTarget ? "Захват ожидает гарнизон." : null,
  ].filter(Boolean).join(" ");

  els.mapBattleButton.hidden = !battle && !(claim?.claimant_domain_id === state.lord.domain_id);
  els.mapBattleButton.textContent = battle ? "Открыть бой" : "Создать бой";
  els.mapGarrisonButton.hidden = !garrisonTarget;
}

function selectedMapTerritory(state) {
  return selectedMapNodeId ? territoriesByNodeId(state).get(selectedMapNodeId) || null : null;
}

function claimForSelectedMapNode(state) {
  const territory = selectedMapTerritory(state);
  if (!territory) return null;
  return (state?.claims || []).find((claim) => claim.territory_id === territory.territory_id) || null;
}

function battleForSelectedMapNode(state) {
  const territory = selectedMapTerritory(state);
  if (!territory) return null;
  return (state?.battles || []).find(
    (battle) => battle.territory_id === territory.territory_id && battle.status === "active"
  ) || null;
}

function garrisonTargetForSelectedMapNode(state) {
  const territory = selectedMapTerritory(state);
  if (!territory) return null;
  return (state?.garrison_targets || []).find(
    (item) => item.territory_id === territory.territory_id
      && item.garrison_target_reason === "capture_pending_garrison"
  ) || null;
}

function ownerLabel(state, ownerDomainId) {
  if (!ownerDomainId) return "нейтрально";
  if (ownerDomainId === state?.lord?.domain_id) return "ваше";
  return "чужое";
}

function routeLabel(routeNodes) {
  return (routeNodes || []).join(" -> ") || "маршрут";
}

function renderMinimap(state, layout, route) {
  if (!els.lordMapMinimap || !layout?.canvas || !mapViewBox) return;
  const width = Number(layout.canvas.width || 0);
  const height = Number(layout.canvas.height || 0);
  const minimap = els.lordMapMinimap;
  minimap.dataset.mapMode = layout.mode || "";
  minimap.setAttribute("viewBox", `0 0 ${width} ${height}`);
  minimap.replaceChildren();
  const territoryByNode = territoriesByNodeId(state);
  const seedNodeById = seedNodesById(state);
  minimap.append(svgNode("rect", {
    class: "minimap-canvas",
    x: 0,
    y: 0,
    width,
    height,
  }));
  minimap.append(renderMapOwnershipSockets(state, layout, territoryByNode, seedNodeById));
  const background = renderMapBackground(layout, width, height);
  if (background) minimap.append(background);

  const edgeLayer = svgNode("g", { class: "minimap-edge-layer" });
  for (const edge of state.map_edges || []) {
    const edgeLayout = layout.edges?.[edge.edge_id];
    if (!edgeLayout?.points?.length) continue;
    edgeLayer.append(svgNode("path", {
      class: "minimap-edge",
      d: pathFromPoints(edgeLayout.points),
    }));
  }
  minimap.append(edgeLayer);

  const routePoints = route ? routePointsForRoute(state, layout, route.nodes) : [];
  if (routePoints.length >= 2) {
    minimap.append(svgNode("path", {
      class: "minimap-route",
      d: pathFromPoints(routePoints),
    }));
  }

  const dotLayer = svgNode("g", { class: "minimap-dot-layer" });
  for (const [nodeId, node] of Object.entries(layout.nodes || {})) {
    const seedNode = seedNodeById.get(nodeId) || {};
    const territory = territoryByNode.get(nodeId);
    dotLayer.append(svgNode("circle", {
      class: `minimap-dot ${mapNodeClass(state, seedNode, territory, node)}`,
      cx: node.x,
      cy: node.y,
      r: node.ui_target ? 24 : 18,
    }));
  }
  minimap.append(dotLayer);
  minimap.append(minimapViewportRect());
}

function minimapViewportRect() {
  return svgNode("rect", {
    class: "minimap-viewport",
    x: mapViewBox.x,
    y: mapViewBox.y,
    width: mapViewBox.w,
    height: mapViewBox.h,
    rx: 12,
  });
}

function updateMinimapViewport() {
  if (!els.lordMapMinimap || !mapViewBox) return;
  const existing = els.lordMapMinimap.querySelector(".minimap-viewport");
  if (existing) existing.remove();
  els.lordMapMinimap.append(minimapViewportRect());
}

function recenterMapFromMinimap(event) {
  if (!currentState?.lord_map_layout?.canvas || !mapViewBox) return;
  const point = minimapClientPointToCanvas(event);
  if (!point) return;
  mapViewBox = clampViewBox(
    {
      ...mapViewBox,
      x: point.x - mapViewBox.w / 2,
      y: point.y - mapViewBox.h / 2,
    },
    currentState.lord_map_layout.canvas,
  );
  els.lordMap.setAttribute("viewBox", viewBoxString(mapViewBox));
  updateMinimapViewport();
}

function minimapClientPointToCanvas(event) {
  const layout = currentState?.lord_map_layout;
  const rect = els.lordMapMinimap.getBoundingClientRect();
  const width = Number(layout?.canvas?.width || 0);
  const height = Number(layout?.canvas?.height || 0);
  if (!rect.width || !rect.height || !width || !height) return null;
  return {
    x: ((event.clientX - rect.left) / rect.width) * width,
    y: ((event.clientY - rect.top) / rect.height) * height,
  };
}

function startMapPan(event) {
  if (!mapViewBox) return;
  const rect = els.lordMap.getBoundingClientRect();
  mapDrag = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    startX: mapViewBox.x,
    startY: mapViewBox.y,
    scaleX: mapViewBox.w / Math.max(1, rect.width),
    scaleY: mapViewBox.h / Math.max(1, rect.height),
    moved: false,
  };
  els.lordMap.setPointerCapture(event.pointerId);
  els.mapViewport.classList.add("dragging");
}

function continueMapPan(event) {
  if (!mapDrag || mapDrag.pointerId !== event.pointerId || !currentState) return;
  const dx = event.clientX - mapDrag.clientX;
  const dy = event.clientY - mapDrag.clientY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) mapDrag.moved = true;
  const layout = currentState.lord_map_layout;
  mapViewBox = clampViewBox(
    {
      ...mapViewBox,
      x: mapDrag.startX - dx * mapDrag.scaleX,
      y: mapDrag.startY - dy * mapDrag.scaleY,
    },
    layout.canvas,
  );
  els.lordMap.setAttribute("viewBox", viewBoxString(mapViewBox));
  updateMinimapViewport();
}

function endMapPan(event) {
  if (!mapDrag || mapDrag.pointerId !== event.pointerId) return;
  suppressNextMapClick = Boolean(mapDrag.moved);
  mapDrag = null;
  els.mapViewport.classList.remove("dragging");
}

function resetMapView(state) {
  const layout = state?.lord_map_layout;
  if (!layout?.canvas) return;
  const canvas = layout.canvas;
  const mobile = window.matchMedia("(max-width: 820px)").matches;
  const zoom = Number(mobile ? layout.viewport?.mobile_zoom : layout.viewport?.desktop_zoom) || 1;
  const canvasWidth = Number(canvas.width);
  const canvasHeight = Number(canvas.height);
  const aspect = mapViewportAspect(canvas);
  let width = Math.min(canvasWidth, canvasWidth * zoom);
  let height = width / aspect;
  if (height > canvasHeight) {
    height = canvasHeight;
    width = height * aspect;
  }
  if (width > canvasWidth) {
    width = canvasWidth;
    height = width / aspect;
  }
  mapViewBox = clampViewBox(
    {
      x: canvasWidth * Number(layout.viewport?.default_x ?? 0.5) - width / 2,
      y: canvasHeight * Number(layout.viewport?.default_y ?? 0.5) - height / 2,
      w: width,
      h: height,
    },
    canvas,
  );
}

function mapViewportAspect(canvas) {
  const fallback = Number(canvas.width || 1) / Number(canvas.height || 1);
  const rect = els.mapViewport?.getBoundingClientRect();
  if (!rect?.width || !rect?.height) return fallback;
  return rect.width / rect.height;
}

function clampViewBox(viewBox, canvas) {
  const width = Number(canvas.width || 0);
  const height = Number(canvas.height || 0);
  const w = Math.min(width, Math.max(1, Number(viewBox.w)));
  const h = Math.min(height, Math.max(1, Number(viewBox.h)));
  return {
    x: Math.max(0, Math.min(width - w, Number(viewBox.x))),
    y: Math.max(0, Math.min(height - h, Number(viewBox.y))),
    w,
    h,
  };
}

function viewBoxString(viewBox) {
  return `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`;
}

function hitZoneShape(hitZone) {
  if (!hitZone) return null;
  if (hitZone.type === "circle") {
    return svgNode("circle", {
      cx: hitZone.cx,
      cy: hitZone.cy,
      r: hitZone.r,
    });
  }
  if (hitZone.type === "polygon") {
    return svgNode("polygon", {
      points: hitZone.points.map((point) => point.join(",")).join(" "),
    });
  }
  return null;
}

function routePointsForRoute(state, layout, routeNodes) {
  const allPoints = [];
  for (let index = 0; index < routeNodes.length - 1; index += 1) {
    const fromNodeId = routeNodes[index];
    const toNodeId = routeNodes[index + 1];
    const edge = (state.map_edges || []).find((item) =>
      item.from_node_id === fromNodeId && item.to_node_id === toNodeId
      || (
        item.from_node_id === toNodeId
        && item.to_node_id === fromNodeId
        && (String(item.bidirectional).toLowerCase() === "true" || item.bidirectional === true)
      )
    );
    const edgePoints = edge ? layout.edges?.[edge.edge_id]?.points : null;
    if (!edgePoints?.length) continue;
    const oriented = edge.from_node_id === fromNodeId ? edgePoints : [...edgePoints].reverse();
    if (!allPoints.length) {
      allPoints.push(...oriented);
    } else {
      allPoints.push(...oriented.slice(1));
    }
  }
  return allPoints;
}

function pathFromPoints(points) {
  return points.map((point, index) =>
    `${index === 0 ? "M" : "L"} ${point[0]} ${point[1]}`
  ).join(" ");
}

function mapNodeClass(state, seedNode, territory, layoutNode) {
  if (layoutNode.layer === "excluded" || seedNode.zone_status === "no_play_excluded") return "excluded";
  if (territory?.owner_domain_id) return ownerDomainClass(territory.owner_domain_id);
  if (!territory) {
    return layoutNode.layer === "residence" || seedNode.node_type === "residence" ? "residence" : "neutral";
  }
  return ownerDomainClass(territory.owner_domain_id);
}

function ownerDomainClass(ownerDomainId) {
  const classes = {
    domain_north: "domain-north",
    domain_river: "domain-river",
    domain_forest: "domain-forest",
    domain_hill: "domain-hill",
  };
  return classes[ownerDomainId] || "neutral";
}

function labelForMapNode(seedNode, territory) {
  if (territory?.name) return territory.name;
  if (seedNode.node_type === "residence") return "Резиденция";
  if (seedNode.zone_status === "no_play_excluded") return seedNode.name || "";
  return seedNode.name || "";
}

function mapNodeTitle(seedNode, territory) {
  if (territory) {
    return `${territory.name} - ${territory.status || "neutral"} - ${territory.bonus_type || ""}`;
  }
  return seedNode.name || seedNode.node_id || "Map node";
}

function territoriesByNodeId(state) {
  return new Map(allTerritories(state).map((territory) => [territory.node_id, territory]));
}

function seedNodesById(state) {
  return new Map((state.map_nodes || []).map((node) => [node.node_id, node]));
}

function allTerritories(state) {
  return [
    ...(state?.territories || []),
    ...(state?.neutral_territories || []),
    ...(state?.other_territories || []),
  ];
}

function svgNode(tagName, attributes = {}, text = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tagName);
  for (const [name, value] of Object.entries(attributes)) {
    node.setAttribute(name, value);
  }
  if (text !== null) node.textContent = text;
  return node;
}

function buildRoute(state, targetNodeId) {
  if (state?.pending_move?.status === "pending") return null;
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

function resolveLordAssetHref(asset) {
  if (asset.startsWith("/") || asset.startsWith("http://") || asset.startsWith("https://")) {
    return asset;
  }
  return `/static/lord/${asset.replace(/^\.?\//, "")}`;
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
    return `${detail.code || status}: ${detail.message || "Действие не выполнено"}`;
  }
  return detail || `Запрос не выполнен: ${status}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
