import type {
  LordActiveBattleUiState,
  LordBackendBattleSummary,
  LordBackendStatePayload,
  LordMpUiState,
  LordStateAdapterOptions,
  LordUiConnectionState,
  LordUiMode,
  LordUiState
} from "./types";

const finalBattleStatuses = new Set(["finished", "needs_master_review", "cancelled", "closed", "resolved"]);

const offlineReason = "Связь с канцелярией потеряна. Экран открыт только для чтения.";
const staleReason = "Связь с канцелярией потеряна. Показаны последние данные, действия временно закрыты.";
const loadingReason = "Ждем ответ канцелярии. Действия пока закрыты.";
const demoReason = "Демо-режим. Данные не являются состоянием игры.";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toMetric = (value: unknown): number | null => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? Math.max(0, Math.floor(numericValue)) : null;
};

const normalizeMp = (payload: LordBackendStatePayload | null): LordMpUiState => {
  const movement = isRecord(payload?.movement) ? payload?.movement : null;
  const domain = isRecord(payload?.domain) ? payload?.domain : null;
  const currentMp = toMetric(movement?.current_mp ?? domain?.current_mp);
  const rawMpCap = toMetric(movement?.mp_cap ?? domain?.mp_cap);
  const mpCap = rawMpCap === null ? null : Math.max(1, rawMpCap);

  if (currentMp === null || mpCap === null) {
    return { currentMp: null, mpCap: null, isKnown: false };
  }

  return {
    currentMp: Math.min(currentMp, mpCap),
    mpCap,
    isKnown: true
  };
};

const getBattleId = (battle: LordBackendBattleSummary | null | undefined) => {
  const battleId = battle?.battle_id;
  return typeof battleId === "string" && battleId.trim() ? battleId : null;
};

const isActiveBattleSummary = (battle: LordBackendBattleSummary) => {
  const status = String(battle.status ?? "").trim().toLowerCase();
  if (!status) {
    return Boolean(getBattleId(battle));
  }
  return !finalBattleStatuses.has(status);
};

const isReadyBattleSummary = (battle: LordBackendBattleSummary) => {
  const queueState = String(battle.queue_state ?? "ready").trim().toLowerCase();
  return isActiveBattleSummary(battle) && queueState !== "waiting";
};

const normalizeActiveBattle = (payload: LordBackendStatePayload | null): LordActiveBattleUiState => {
  const battles = Array.isArray(payload?.battles) ? payload?.battles : [];
  const battle = battles.find(isReadyBattleSummary) ?? null;
  const battleId = getBattleId(battle);

  return {
    active: Boolean(battleId),
    battleId,
    battle
  };
};

const getReadonlyReason = (connection: LordUiConnectionState, mode: LordUiMode) => {
  if (mode === "demo") return demoReason;
  if (connection === "stale") return staleReason;
  if (connection === "loading") return loadingReason;
  return offlineReason;
};

export const getLordRuntimeMode = (routeParams: URLSearchParams): LordUiMode => {
  if (routeParams.get("demo") === "1") return "demo";
  if (routeParams.get("tutorial") === "1" || routeParams.get("training") === "1") return "tutorial";
  return "production";
};

export const createLordUiState = (
  connection: LordUiConnectionState,
  options: LordStateAdapterOptions = {}
): LordUiState => {
  const mode = options.mode ?? "production";
  const isDemo = mode === "demo";
  const effectiveConnection = isDemo ? "demo" : connection;
  const hasAuthoritativeState = effectiveConnection === "ready";
  return {
    mode,
    connection: effectiveConnection,
    hasAuthoritativeState,
    isDemo,
    isReadOnly: mode === "production",
    readonlyReason: getReadonlyReason(effectiveConnection, mode),
    mp: { currentMp: null, mpCap: null, isKnown: false },
    activeBattle: { active: false, battleId: null, battle: null }
  };
};

export const adaptLordState = (
  payload: LordBackendStatePayload | null | undefined,
  options: LordStateAdapterOptions = {}
): LordUiState => {
  const mode = options.mode ?? "production";
  const isDemo = mode === "demo";
  if (!isRecord(payload)) {
    return createLordUiState("offline", { mode });
  }

  return {
    mode,
    connection: isDemo ? "demo" : "ready",
    hasAuthoritativeState: mode === "production",
    isDemo,
    isReadOnly: false,
    readonlyReason: isDemo ? demoReason : "",
    mp: normalizeMp(payload),
    activeBattle: normalizeActiveBattle(payload)
  };
};

export const markLordUiStateOffline = (current: LordUiState): LordUiState => {
  if (current.mode === "demo") {
    return createLordUiState("demo", { mode: current.mode });
  }

  if (current.hasAuthoritativeState) {
    return {
      ...current,
      connection: "stale",
      isReadOnly: true,
      readonlyReason: staleReason
    };
  }

  return createLordUiState("offline", { mode: "production" });
};
