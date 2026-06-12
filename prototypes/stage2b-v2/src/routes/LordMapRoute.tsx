import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, PointerEvent as ReactPointerEvent } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  Castle,
  Clock3,
  Coins,
  Crown,
  Gavel,
  Hammer,
  Layers,
  Map as MapIcon,
  Maximize2,
  Minimize2,
  Route,
  ScrollText,
  Shield,
  Sparkles,
  Swords,
  Users
} from "lucide-react";
import lordHomeActionBattleIcon from "../assets/generated/lords-home/actions/action-battle-v1.png";
import lordHomeActionBuildingsIcon from "../assets/generated/lords-home/actions/action-buildings-v1.png";
import lordHomeActionCastleIcon from "../assets/generated/lords-home/actions/action-castle-v1.png";
import lordHomeActionMapIcon from "../assets/generated/lords-home/actions/action-map-v1.png";
import lordHomeActionOrdersIcon from "../assets/generated/lords-home/actions/action-orders-v1.png";
import lordHomeActionRaidsIcon from "../assets/generated/lords-home/actions/action-raids-v1.png";
import unitCavalryIcon from "../assets/generated/lords-home/units/unit-cavalry-v1.jpg";
import unitGuardIcon from "../assets/generated/lords-home/units/unit-guard-v1.jpg";
import unitHeavySiegeIcon from "../assets/generated/lords-home/units/unit-heavy-siege-v1.jpg";
import unitInfantryIcon from "../assets/generated/lords-home/units/unit-infantry-v1.jpg";
import unitRangedIcon from "../assets/generated/lords-home/units/unit-ranged-v1.jpg";
import unitSpecialistIcon from "../assets/generated/lords-home/units/unit-specialist-v1.jpg";
import lordMapStrictV6BakedRoads from "../assets/generated/lords-map/lord-map-ai-strict-v6-baked-roads.webp";
import lordMapStrictV6RoadlessBase from "../assets/generated/lords-map/lord-map-ai-strict-v6-roadless-base.webp";
import { LordMpHud } from "../LordMpHud";
import { adaptLordState, createLordUiState, getLordApiErrorMessage, getLordClientErrorMessage, getLordRuntimeMode, markLordUiStateOffline } from "../lordState";
import type { LordBackendStatePayload, LordUiState } from "../lordState";
import {
  clearLordRuntimeSession,
  getLordRuntimeApiBaseUrl,
  getLordRuntimeCurrentPathWithoutSensitiveParams,
  getLordRuntimeLoginPath,
  isLordRuntimeAuthResponse,
  isLordRuntimeProductionOrigin,
  lordRuntimeRequestTimeoutMs,
  lordRuntimeStateCachePrefix,
  normalizeLordRuntimeApiBaseUrl,
  persistLordRuntimeSession,
  readLordRuntimeSession,
  stripLordRuntimeSensitiveQueryParams,
  withLordRuntimeQuery
} from "../lordRuntime";

type Tone = "gold" | "green" | "blue" | "red" | "violet" | "muted";
type LordHomeUnitId = "infantry" | "guard" | "ranged" | "cavalry" | "heavy-siege" | "specialist";
type LordHomeStack = { stackId?: string; unitId: LordHomeUnitId; count: number };
type LordHomeBackendStack = {
  army_id?: string;
  garrison_id?: string;
  card_id?: string;
  count?: number;
  status?: string;
  hidden?: boolean;
};
type LordMapTerritoryBonus = {
  bonus_id?: string;
  territory_id?: string;
  effect_type?: string;
  effect_value?: string | number;
  effect_value_int?: number;
  public_label?: string;
  strategic_role?: string;
  stacking_rule?: string;
};
type LordHomeBackendTerritory = {
  territory_id?: string;
  name?: string;
  owner_domain_id?: string | null;
  owner?: {
    domain_id?: string | null;
    name?: string;
    relation?: string;
    status?: string;
  };
  bonus_type?: string;
  tier?: number | string;
  node_id?: string;
  node_name?: string;
  node_type?: string;
  status?: string;
  contested_by_domain_id?: string | null;
  income_per_hour?: number;
  bonus_label?: string;
  bonuses?: LordMapTerritoryBonus[] | "" | null;
  fort?: {
    garrison_capacity?: number;
    garrison_slots_used?: number;
    garrison_slots_free?: number;
  } | null;
  garrisons?: LordHomeBackendStack[] | "" | null;
};
type LordHomeBackendTimerSummary = {
  server_time?: string;
  status?: string;
  current_act_id?: string | null;
  active_started_at?: string | null;
  applied_tick_count?: number;
  next_tick?: {
    timer_id?: string;
    act_id?: string;
    effect_type?: string;
    due_at?: string;
    seconds_until?: number;
    minutes_until?: number;
  } | null;
};
type LordHomeDomainStats = {
  incomePerHour: number;
  rawIncomePerHour: number;
  territoryIncomePerHour: number;
  currentMp: number;
  mpCap: number;
  activeArmyCapacity: number;
  activeArmySlotsUsed: number;
  raidTokenCap: number;
};
type LordHomeUnitCard = {
  name: string;
  role: string;
  icon: string;
  backendCardId: string;
  attack: number;
  defense: number;
  hp: number;
  initiative: number;
  moveRange: number;
  attackRange: number;
  cost: number;
  tone: Tone;
};
type LordMapBattleCta = {
  action?: string;
  label?: string;
  territory_id?: string;
  claim_id?: string;
  battle_id?: string;
  actor?: string;
};
type LordMapClaimPayload = {
  claim_id?: string;
  territory_id?: string;
  claimant_domain_id?: string;
  defender_domain_id?: string | null;
  status?: string;
  battle_required?: boolean;
  cta?: LordMapBattleCta;
};
type LordMapBattleAlertPayload = {
  type?: string;
  severity?: string;
  territory_id?: string;
  territory_name?: string;
  claim_id?: string;
  battle_id?: string;
  status?: string;
  cta?: LordMapBattleCta;
};
type LordHomeBackendState = LordBackendStatePayload & {
  lord?: { domain_id?: string };
  domain?: {
    domain_id?: string;
    gold?: number;
    income_per_hour?: number;
    raw_income_per_hour?: number;
    territory_income_per_hour?: number;
    current_node_id?: string;
    current_mp?: number;
    mp_cap?: number;
    active_army_capacity?: number;
    active_army_slots_used?: number;
    raid_token_cap?: number;
  };
  resources?: {
    gold?: number;
    income_per_hour?: number;
    raw_income_per_hour?: number;
    territory_income_per_hour?: number;
    current_mp?: number;
    mp_cap?: number;
  };
  movement?: {
    current_node_id?: string;
    current_mp?: number;
    mp_cap?: number;
  };
  summary?: Record<string, unknown>;
  timer_summary?: LordHomeBackendTimerSummary;
  territories?: LordHomeBackendTerritory[];
  territory_views?: LordHomeBackendTerritory[];
  neutral_territories?: LordHomeBackendTerritory[];
  other_territories?: LordHomeBackendTerritory[];
  active_army?: LordHomeBackendStack[] | "" | null;
  active_army_location?: {
    node_id?: string;
    node_name?: string;
    territory_id?: string;
    pending_move_active?: boolean;
  };
  battles?: Array<Record<string, unknown> & { battle_id?: string; status?: string }>;
  active_battles?: Array<Record<string, unknown> & { battle_id?: string; status?: string }>;
  claims?: LordMapClaimPayload[];
  battle_alerts?: LordMapBattleAlertPayload[];
  route_options?: unknown;
};

const lordHomeDemoLordId = "demo_lord";
const lordHomeDemoRoleToken = "DEMO-LORD-SESSION";
const lordHomeClockTickMs = 1000;
const lordHomeStatePollMs = 10_000;
const lordRuntimeStateCacheTtlMs = 12 * 60 * 60 * 1000;

const getLordRuntimeStateCacheKey = (apiBaseUrl: string, lordId: string) =>
  `${lordRuntimeStateCachePrefix}:${normalizeLordRuntimeApiBaseUrl(apiBaseUrl) || "same-origin"}:${lordId}`;

function readLordRuntimeCachedState<T>(apiBaseUrl: string, lordId: string): T | null {
  try {
    const raw = localStorage.getItem(getLordRuntimeStateCacheKey(apiBaseUrl, lordId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { cachedAt?: unknown; state?: unknown };
    const cachedAt = Number(parsed.cachedAt);
    if (!Number.isFinite(cachedAt) || Date.now() - cachedAt > lordRuntimeStateCacheTtlMs) return null;
    if (!parsed.state || typeof parsed.state !== "object") return null;
    return parsed.state as T;
  } catch {
    return null;
  }
}

const writeLordRuntimeCachedState = (apiBaseUrl: string, lordId: string, state: unknown) => {
  try {
    localStorage.setItem(getLordRuntimeStateCacheKey(apiBaseUrl, lordId), JSON.stringify({ cachedAt: Date.now(), state }));
  } catch {
    // Cache writes are best-effort; the server remains authoritative.
  }
};

const mergeLordRuntimeSummaryState = <T extends LordHomeBackendState>(current: T | null, summary: LordHomeBackendState): T => ({
  ...(current ?? {}),
  ...summary,
  lord: {
    ...((current as LordMapBackendState | null)?.lord ?? {}),
    ...((summary as LordMapBackendState).lord ?? {})
  },
  domain: {
    ...(current?.domain ?? {}),
    ...(summary.domain ?? {})
  },
  resources: {
    ...(current?.resources ?? {}),
    ...(summary.resources ?? {})
  },
  movement: {
    ...(current?.movement ?? {}),
    ...(summary.movement ?? {})
  },
  summary: {
    ...(current?.summary ?? {}),
    ...(summary.summary ?? {})
  },
  battles: summary.battles ?? current?.battles,
  pending_move: (summary as LordMapBackendState).pending_move ?? null,
  route_options:
    (summary as Record<string, unknown>).route_options ??
    (current as Record<string, unknown> | null)?.route_options
}) as unknown as T;

const lordHomeUnitCatalog: Record<LordHomeUnitId, LordHomeUnitCard> = {
  infantry: {
    name: "Мечники",
    role: "пехота",
    icon: unitInfantryIcon,
    backendCardId: "unit_infantry_t1",
    attack: 3,
    defense: 1,
    hp: 5,
    initiative: 3,
    moveRange: 2,
    attackRange: 1,
    cost: 1,
    tone: "gold"
  },
  guard: {
    name: "Стража",
    role: "гарнизон",
    icon: unitGuardIcon,
    backendCardId: "unit_guard_t1",
    attack: 2,
    defense: 3,
    hp: 6,
    initiative: 2,
    moveRange: 1,
    attackRange: 1,
    cost: 2,
    tone: "blue"
  },
  ranged: {
    name: "Лучники",
    role: "стрелки",
    icon: unitRangedIcon,
    backendCardId: "unit_ranged_t1",
    attack: 3,
    defense: 1,
    hp: 4,
    initiative: 4,
    moveRange: 1,
    attackRange: 3,
    cost: 2,
    tone: "green"
  },
  cavalry: {
    name: "Кавалерия",
    role: "конница",
    icon: unitCavalryIcon,
    backendCardId: "unit_cavalry_t2",
    attack: 5,
    defense: 2,
    hp: 6,
    initiative: 5,
    moveRange: 3,
    attackRange: 1,
    cost: 5,
    tone: "red"
  },
  "heavy-siege": {
    name: "Осадники",
    role: "осада",
    icon: unitHeavySiegeIcon,
    backendCardId: "unit_heavy_siege_t3",
    attack: 7,
    defense: 2,
    hp: 8,
    initiative: 1,
    moveRange: 1,
    attackRange: 4,
    cost: 8,
    tone: "gold"
  },
  specialist: {
    name: "Инженеры",
    role: "специалисты",
    icon: unitSpecialistIcon,
    backendCardId: "unit_specialist_t3",
    attack: 4,
    defense: 3,
    hp: 6,
    initiative: 4,
    moveRange: 2,
    attackRange: 2,
    cost: 6,
    tone: "violet"
  }
};
const lordHomeUnitOrder = Object.keys(lordHomeUnitCatalog) as LordHomeUnitId[];
const lordHomeUnitIdByBackendCardId = Object.fromEntries(
  lordHomeUnitOrder.map((unitId) => [lordHomeUnitCatalog[unitId].backendCardId, unitId])
) as Record<string, LordHomeUnitId>;
const lordHomeInitialArmy: LordHomeStack[] = [
  { unitId: "infantry", count: 1 },
  { unitId: "ranged", count: 1 }
];
const lordHomeInitialDomainStats: LordHomeDomainStats = {
  incomePerHour: 0,
  rawIncomePerHour: 0,
  territoryIncomePerHour: 0,
  currentMp: 0,
  mpCap: 0,
  activeArmyCapacity: 6,
  activeArmySlotsUsed: 0,
  raidTokenCap: 0
};
const lordHomeBaseActionDock = [
  { id: "buildings", label: "Здания", icon: lordHomeActionBuildingsIcon, tone: "gold" },
  { id: "map", label: "Карта", icon: lordHomeActionMapIcon, tone: "blue" },
  { id: "orders", label: "Заказы", icon: lordHomeActionOrdersIcon, tone: "green" },
  { id: "raids", label: "Рейды", icon: lordHomeActionRaidsIcon, tone: "red" },
  { id: "battle", label: "Бой", icon: lordHomeActionBattleIcon, tone: "red", alert: true }
] as const;

const lordHomeActionDock = [
  { id: "castle", label: "Главный замок", icon: lordHomeActionCastleIcon, tone: "blue" },
  ...lordHomeBaseActionDock
] as const;

const getLordHomeApiErrorMessage = (payload: unknown, fallback: string) => getLordApiErrorMessage(payload, fallback);
const getLordHomeCaughtErrorMessage = (error: unknown, fallback: string) => getLordClientErrorMessage(error, fallback);

const getLordHomeStacksFromBackend = (rows: LordHomeBackendStack[] | "" | null | undefined): LordHomeStack[] => {
  return (Array.isArray(rows) ? rows : []).flatMap((row) => {
    if (row.hidden || (row.status && row.status !== "active")) return [];
    const unitId = row.card_id ? lordHomeUnitIdByBackendCardId[row.card_id] : undefined;
    const count = Number(row.count ?? 0);
    if (!unitId || !Number.isFinite(count) || count <= 0) return [];
    return [{ stackId: row.army_id ?? row.garrison_id, unitId, count }];
  });
};

const lordHomeActLabelById: Record<string, string> = {
  act1: "Акт I",
  act2: "Акт II",
  act3: "Акт III",
  final: "Финал"
};
const getLordHomeActLabel = (timerSummary: LordHomeBackendTimerSummary | null) => {
  const actId = timerSummary?.current_act_id ?? "";
  return lordHomeActLabelById[actId] ?? (actId ? actId : "Ожидание");
};
const formatLordHomeTimerCountdown = (seconds: number) => {
  const safeSeconds = Math.max(0, Math.ceil(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;
  return hours > 0 ? `${hours}ч ${String(minutes).padStart(2, "0")}м` : `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
};
const getLordHomeTimerRemainingSeconds = (timerSummary: LordHomeBackendTimerSummary | null, nowMs: number) => {
  const nextTick = timerSummary?.next_tick;
  if (!nextTick) return null;
  const dueAtMs = nextTick.due_at ? Date.parse(nextTick.due_at) : Number.NaN;
  if (Number.isFinite(dueAtMs)) return Math.max(0, Math.ceil((dueAtMs - nowMs) / 1000));
  const secondsUntil = Number(nextTick.seconds_until ?? 0);
  return Number.isFinite(secondsUntil) ? Math.max(0, Math.ceil(secondsUntil)) : null;
};
const getLordHomeTimerShortLabel = (timerSummary: LordHomeBackendTimerSummary | null, nowMs = Date.now()) => {
  const nextTick = timerSummary?.next_tick;
  if (!nextTick) return timerSummary?.status === "active" ? "тики завершены" : "нет акта";
  const secondsUntil = getLordHomeTimerRemainingSeconds(timerSummary, nowMs);
  return secondsUntil === null ? "нет времени" : formatLordHomeTimerCountdown(secondsUntil);
};
function LordHomeTimerChip({ timerSummary, nowMs }: { timerSummary: LordHomeBackendTimerSummary | null; nowMs: number }) {
  const actLabel = getLordHomeActLabel(timerSummary);
  const timerLabel = getLordHomeTimerShortLabel(timerSummary, nowMs);
  const isActive = timerSummary?.status === "active";
  return (
    <div className={`lord-home-timer-chip${isActive ? " is-active" : ""}`} aria-label={`${actLabel}: ${timerLabel}`}>
      <Clock3 size={14} aria-hidden="true" />
      <b>{actLabel}</b>
      <span>{timerLabel}</span>
    </div>
  );
}

function LordHomeActionIcon({ src }: { src: string }) {
  return (
    <span className="lord-home-action-medallion" aria-hidden="true">
      <img className="lord-home-action-icon" src={src} alt="" draggable={false} />
    </span>
  );
}

type LordMapBackendMovement = {
  domain_id?: string;
  current_node_id?: string;
  current_mp?: number;
  mp_cap?: number;
};

type LordMapBackendPendingMove = {
  move_id?: string;
  status?: string;
  domain_id?: string;
  lord_id?: string;
  from_node_id?: string;
  to_node_id?: string;
  requested_to_node_id?: string;
  route?: string[];
  route_node_ids?: string[];
  mp_cost?: number;
  mp_spent?: number;
  current_mp?: number;
  started_at?: string;
  arrival_at?: string;
};

type LordMapBackendRoutePreview = {
  status?: "ready" | "stopped" | "blocked";
  can_move?: boolean;
  from_node_id?: string;
  to_node_id?: string;
  requested_to_node_id?: string;
  route?: string[];
  mp_cost?: number;
  mp_available?: number;
  arrival_at?: string;
  reason?: string;
  reason_code?: string;
};

type LordMapBackendMoveResponse = {
  status?: string;
  to_node_id?: string;
  requested_to_node_id?: string;
  route?: string[];
  mp_spent?: number;
  current_mp?: number;
  pending_move?: LordMapBackendPendingMove;
};

type LordMapBackendMapNode = {
  node_id?: string;
  name?: string;
  node_type?: string;
  zone_status?: string;
  territory_id?: string;
};

type LordMapBackendMapEdge = {
  edge_id?: string;
  from_node_id?: string;
  to_node_id?: string;
  mp_cost?: number | string;
  bidirectional?: boolean | string;
};

type LordMapBackendLayoutPoint = {
  x?: number;
  y?: number;
};

type LordMapBackendLayoutNode = {
  x?: number;
  y?: number;
  ui_target?: boolean | string | number;
  label_anchor?: LordMapBackendLayoutPoint;
  marker_anchor?: LordMapBackendLayoutPoint;
  layer?: string;
};

type LordMapBackendLayoutEdge = {
  points?: Array<readonly [number, number]>;
};

type LordMapBackendLayout = {
  layout_id?: string;
  art_asset?: string;
  road_asset?: string;
  future_art_asset?: string;
  canvas?: {
    width?: number;
    height?: number;
  };
  nodes?: Record<string, LordMapBackendLayoutNode>;
  edges?: Record<string, LordMapBackendLayoutEdge>;
};

const lordMapLayoutImageAssets: Record<string, string> = {
  "assets/lord-map-ai-strict-v6-roadless-base.webp": lordMapStrictV6RoadlessBase,
  "lord-map-ai-strict-v6-roadless-base.webp": lordMapStrictV6RoadlessBase
};

const lordMapLayoutRoadImageAssets: Record<string, string> = {
  "assets/lord-map-ai-strict-v6-baked-roads.webp": lordMapStrictV6BakedRoads,
  "lord-map-ai-strict-v6-baked-roads.webp": lordMapStrictV6BakedRoads
};

const getLordMapLayoutImageAsset = (layout: LordMapBackendLayout | undefined) => {
  const assetId = layout?.art_asset ?? layout?.future_art_asset ?? "";
  return lordMapLayoutImageAssets[assetId] ?? lordMapStrictV6RoadlessBase;
};

const getLordMapLayoutRoadImageAsset = (layout: LordMapBackendLayout | undefined) =>
  lordMapLayoutRoadImageAssets[layout?.road_asset ?? ""] ?? lordMapStrictV6BakedRoads;

type LordMapEnemyArmyIntel = {
  target_id?: string;
  target_type?: string;
  node_id?: string;
  territory_id?: string | null;
  territory_name?: string;
  owner_domain_name?: string;
  intel_level?: string;
  presence?: boolean;
  detail_redacted?: boolean;
  rough_strength?: string;
  total_count?: number;
  stack_count?: number;
};

type LordMapBackendIntel = {
  graph_visible?: boolean;
  hidden_detail_policy?: string;
  enemy_armies?: LordMapEnemyArmyIntel[];
  revealed?: Array<Record<string, unknown>>;
};

type LordMapBackendState = LordHomeBackendState & {
  lord?: { domain_id?: string };
  domain?: LordHomeBackendState["domain"] & LordMapBackendMovement;
  movement?: LordMapBackendMovement;
  pending_move?: LordMapBackendPendingMove | null;
  map_nodes?: LordMapBackendMapNode[];
  map_edges?: LordMapBackendMapEdge[];
  lord_map_layout?: LordMapBackendLayout;
  lord_map_intel?: LordMapBackendIntel;
};

type LordMapSocketTone = "neutral" | "domain-north" | "domain-river" | "domain-forest" | "domain-hill";
type LordMapLordId = "north" | "river" | "forest" | "hill";
type LordMapRoutePreviewStatus = "idle" | "ready" | "stopped" | "blocked";
type LordMapRouteLord = { tone: LordMapSocketTone; homeSocketId: string };
type LordMapMovementDraft = {
  pathIds: string[];
  targetSocketId: string;
  startedAt: number;
  durationMs: number;
};
type LordMapMode = "march" | "info";
type LordMapLayerId = "roads" | "territories" | "costs";
type LordMapLayerState = Record<LordMapLayerId, boolean>;
type LordMapRoadPoint = readonly [number, number];
type LordMapSocket = {
  id: string;
  name: string;
  x: number;
  y: number;
  tone: LordMapSocketTone;
  owner: string;
  route: string;
  nodeType?: string;
  zoneStatus?: string;
  territoryId?: string;
  status?: string;
  ownerDomainId?: string | null;
  contestedByDomainId?: string | null;
  uiTarget?: boolean;
  tier?: number;
  bonusLabel?: string;
  bonuses?: LordMapTerritoryBonus[];
  incomePerHour?: number;
  garrisonCapacity?: number;
  garrisonSlotsUsed?: number;
  garrisonSlotsFree?: number;
};
type LordMapTravelEdge = {
  id: string;
  from: string;
  to: string;
  cost: number;
  points: readonly LordMapRoadPoint[];
};

type LordMapTerritoryProfile = {
  tier: string;
  control: string;
  bonuses: string[];
  income?: string;
  garrison?: string;
};

type LordMapTerritoryInfoRow = {
  label: string;
  value: string;
};

const lordMapModeButtons = [
  { id: "march", label: "Поход", icon: Route },
  { id: "info", label: "Сведения", icon: ScrollText }
] as const satisfies ReadonlyArray<{ id: LordMapMode; label: string; icon: typeof Route }>;

const lordMapLayerButtons = [
  { id: "roads", label: "Дороги", icon: Route },
  { id: "territories", label: "Террит.", icon: MapIcon },
  { id: "costs", label: "MP", icon: Layers }
] as const satisfies ReadonlyArray<{ id: LordMapLayerId; label: string; icon: typeof Route }>;

const lordMapSockets: LordMapSocket[] = [
  { id: "node_fort_east", name: "Северная застава", x: 50.13, y: 15.12, tone: "neutral", owner: "нейтрально", route: "2 MP до центра" },
  { id: "node_res_north", name: "Северная резиденция", x: 39.72, y: 37.3, tone: "domain-north", owner: "Север", route: "резиденция, рейды" },
  { id: "node_res_river", name: "Речная резиденция", x: 54.22, y: 37.3, tone: "domain-river", owner: "Река", route: "резиденция, рейды" },
  { id: "node_res_forest", name: "Лесная резиденция", x: 39.72, y: 48.89, tone: "domain-forest", owner: "Лес", route: "резиденция, рейды" },
  { id: "node_res_hill", name: "Холмовая резиденция", x: 54.22, y: 48.89, tone: "domain-hill", owner: "Холм", route: "резиденция, рейды" },
  { id: "node_field_oats", name: "Северные овсы", x: 32, y: 25.2, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_mountain_north_alpine", name: "Северный кряж", x: 67.62, y: 18.4, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_well_city", name: "Колодезный торг", x: 71.09, y: 27.97, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_field_west_large", name: "Левобережные пашни", x: 14.82, y: 29.23, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_village_east_shed", name: "Восточная слобода", x: 75.5, y: 42.84, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_lake_mist", name: "Зеркальный пруд", x: 80.71, y: 40.57, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_fort_west", name: "Западный острог", x: 27.59, y: 16.63, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_mountain_gray", name: "Серый дозор", x: 64.79, y: 61.24, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_field_east_large", name: "Правые пашни", x: 82.91, y: 63.51, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_fort_southwest", name: "Южная крепь", x: 20.49, y: 73.59, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_village_barn", name: "Сенной посад", x: 48.87, y: 65.02, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_swamp_black", name: "Черная топь", x: 18.28, y: 59.98, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_forest_dark", name: "Травничья роща", x: 19.7, y: 49.65, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_spanish_magic", name: "Чародейский угол", x: 44.45, y: 86.44, tone: "neutral", owner: "нейтрально", route: "спор, 2 MP" },
  { id: "node_mountain_west_alpine", name: "Волчий утес", x: 32.79, y: 81.91, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_science_barn", name: "Двухъярусная мануфактура", x: 62.26, y: 77.37, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_forest_south_garden", name: "Нижний сад", x: 72.04, y: 78.38, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_lake_south_pond", name: "Лунная заводь", x: 85.12, y: 84.43, tone: "neutral", owner: "нейтрально", route: "1 MP" }
];

const lordMapTerritoryBonus = (
  territoryId: string,
  effectType: string,
  publicLabel: string,
  effectValue: string | number = 0
): LordMapTerritoryBonus => ({
  territory_id: territoryId,
  effect_type: effectType,
  effect_value: effectValue,
  public_label: publicLabel
});

const lordMapFallbackTerritoryBonusesBySocketId: Record<string, LordMapTerritoryBonus[]> = {
  node_res_north: [lordMapTerritoryBonus("territory_res_north", "home_base", "Дом Севера")],
  node_res_river: [lordMapTerritoryBonus("territory_res_river", "home_base", "Речные ворота")],
  node_res_forest: [lordMapTerritoryBonus("territory_res_forest", "home_base", "Лесной марш")],
  node_res_hill: [lordMapTerritoryBonus("territory_res_hill", "home_base", "Холмовая корона")],
  node_fort_east: [lordMapTerritoryBonus("territory_fort_east", "raid_defense_flat", "Укрепленная застава +1 к защите от рейдов", 1)],
  node_fort_west: [lordMapTerritoryBonus("territory_fort_west", "raid_token_cap", "Западный плацдарм +1 предел жетонов рейда", 1)],
  node_fort_southwest: [lordMapTerritoryBonus("territory_fort_southwest", "raid_defense_flat", "Южный редут +2 к защите от рейдов", 2)],
  node_field_oats: [lordMapTerritoryBonus("territory_field_oats", "income_flat", "Овсяные поля +3 золота в час", 3)],
  node_field_west_large: [lordMapTerritoryBonus("territory_field_west_large", "income_flat", "Левобережные пашни +4 золота в час", 4)],
  node_field_east_large: [lordMapTerritoryBonus("territory_field_east_large", "recruit_card_unlock", "Восточные сборы открывают пехоту", "unit_infantry_t1")],
  node_village_barn: [lordMapTerritoryBonus("territory_village_barn", "influence_flat", "Сенной посад +1 влияние в час", 1)],
  node_village_east_shed: [lordMapTerritoryBonus("territory_village_east_shed", "recruit_card_unlock", "Восточная слобода открывает стражу", "unit_guard_t1")],
  node_well_city: [lordMapTerritoryBonus("territory_well_city", "income_flat", "Колодезный торг +5 золота в час", 5)],
  node_spanish_magic: [lordMapTerritoryBonus("territory_magic_corner", "recruit_card_unlock", "Чародейский угол открывает специалистов", "unit_specialist_t3")],
  node_science_barn: [lordMapTerritoryBonus("territory_science_barn", "influence_flat", "Мануфактура +2 влияния в час", 2)],
  node_forest_dark: [lordMapTerritoryBonus("territory_forest_dark", "raid_token_cap", "Травничья роща +1 предел жетонов рейда", 1)],
  node_forest_south_garden: [lordMapTerritoryBonus("territory_forest_south_garden", "income_flat", "Нижний сад +2 золота в час", 2)],
  node_lake_mist: [lordMapTerritoryBonus("territory_lake_mist", "mp_refill_flat", "Зеркальный пруд +1 MP при тике", 1)],
  node_lake_south_pond: [lordMapTerritoryBonus("territory_lake_south_pond", "influence_flat", "Лунная заводь +1 влияние в час", 1)],
  node_swamp_black: [lordMapTerritoryBonus("territory_swamp_black", "raid_defense_flat", "Черная топь +2 к защите от рейдов", 2)],
  node_mountain_north_alpine: [lordMapTerritoryBonus("territory_mountain_north_alpine", "raid_defense_flat", "Северный кряж +3 к защите от рейдов", 3)],
  node_mountain_gray: [lordMapTerritoryBonus("territory_mountain_gray", "influence_flat", "Серый дозор +2 влияния в час", 2)],
  node_mountain_west_alpine: [lordMapTerritoryBonus("territory_mountain_west_alpine", "raid_token_cap", "Волчий утес +1 предел жетонов рейда", 1)]
};

function normalizeLordMapTerritoryBonuses(
  bonuses: LordMapTerritoryBonus[] | "" | null | undefined
): LordMapTerritoryBonus[] {
  return (Array.isArray(bonuses) ? bonuses : []).filter((bonus) =>
    Boolean(String(bonus.public_label || bonus.effect_type || "").trim())
  );
}

const getLordMapTerritoryBonuses = (socket: LordMapSocket) => {
  const socketBonuses = normalizeLordMapTerritoryBonuses(socket.bonuses);
  return socketBonuses.length > 0 ? socketBonuses : lordMapFallbackTerritoryBonusesBySocketId[socket.id] ?? [];
};

const getLordMapTerritoryBonusLabels = (socket: LordMapSocket) => {
  const labels = getLordMapTerritoryBonuses(socket)
    .map((bonus) => String(bonus.public_label || "").trim())
    .filter(Boolean);

  return [...new Set(labels)];
};

const getLordMapTerritoryControlLabel = (socket: LordMapSocket) => {
  if (socket.contestedByDomainId) {
    return "оспаривается";
  }

  const status = String(socket.status || "").toLowerCase();
  if (status === "controlled") return "под контролем";
  if (status === "neutral") return "нейтральная";
  if (status === "contested") return "оспаривается";
  if (status) return status;
  return socket.ownerDomainId ? "под контролем" : "нейтральная";
};

const getLordMapGarrisonSummary = (socket: LordMapSocket) => {
  const capacity = Number(socket.garrisonCapacity);
  if (!Number.isFinite(capacity) || capacity <= 0) {
    return undefined;
  }

  const used = Number(socket.garrisonSlotsUsed);
  if (Number.isFinite(used)) {
    return `${Math.max(0, used)}/${capacity} слотов занято`;
  }

  const free = Number(socket.garrisonSlotsFree);
  if (Number.isFinite(free)) {
    return `${Math.max(0, free)} свободно из ${capacity}`;
  }

  return `${capacity} слотов`;
};

const getLordMapTerritoryProfile = (socket: LordMapSocket): LordMapTerritoryProfile => {
  const tier = Number(socket.tier);
  const incomePerHour = Number(socket.incomePerHour);
  const bonusLabels = getLordMapTerritoryBonusLabels(socket);

  return {
    tier: Number.isFinite(tier) && tier > 0 ? `T${tier}` : isLordMapResidenceSocket(socket) ? "T3" : "T1",
    control: getLordMapTerritoryControlLabel(socket),
    bonuses: bonusLabels.length > 0 ? bonusLabels : ["нет открытого бонуса"],
    income: Number.isFinite(incomePerHour) ? `+${incomePerHour} золота в час` : undefined,
    garrison: getLordMapGarrisonSummary(socket)
  };
};

const getLordMapTerritoryInfoRows = (socket: LordMapSocket): LordMapTerritoryInfoRow[] => {
  const profile = getLordMapTerritoryProfile(socket);
  const rows: Array<LordMapTerritoryInfoRow | null> = [
    { label: "Владелец", value: socket.owner || "нейтрально" },
    { label: "Состояние", value: profile.control },
    { label: "Уровень", value: profile.tier },
    { label: profile.bonuses.length > 1 ? "Бонусы" : "Бонус", value: profile.bonuses.join("; ") },
    profile.income ? { label: "Доход", value: profile.income } : null,
    profile.garrison ? { label: "Форт", value: profile.garrison } : null
  ];

  return rows.filter((row): row is LordMapTerritoryInfoRow => Boolean(row?.value.trim()));
};

const lordMapRoadViewBox = { width: 3172, height: 1984 } as const;

const lordMapLordMeta: Record<LordMapLordId, { name: string; armyName: string; homeSocketId: string; tone: LordMapSocketTone }> = {
  north: { name: "Север", armyName: "Северное войско", homeSocketId: "node_res_north", tone: "domain-north" },
  river: { name: "Река", armyName: "Речное войско", homeSocketId: "node_res_river", tone: "domain-river" },
  forest: { name: "Лес", armyName: "Лесное войско", homeSocketId: "node_res_forest", tone: "domain-forest" },
  hill: { name: "Холм", armyName: "Холмовое войско", homeSocketId: "node_res_hill", tone: "domain-hill" }
};

const lordMapTravelEdges = [
  { id: "edge_north_field", from: "node_res_north", to: "node_field_oats", cost: 1, points: [[1260, 740], [1205, 650], [1125, 570], [1015, 500]] },
  { id: "edge_north_fort_east", from: "node_res_north", to: "node_fort_east", cost: 2, points: [[1260, 740], [1320, 600], [1450, 450], [1590, 300]] },
  { id: "edge_fort_east_mountain_north", from: "node_fort_east", to: "node_mountain_north_alpine", cost: 2, points: [[1590, 300], [1790, 315], [1990, 320], [2145, 365]] },
  { id: "edge_mountain_north_lake", from: "node_mountain_north_alpine", to: "node_lake_mist", cost: 2, points: [[2145, 365], [2325, 460], [2505, 625], [2560, 805]] },
  { id: "edge_fort_west_field_north", from: "node_fort_west", to: "node_field_oats", cost: 1, points: [[875, 330], [925, 405], [1015, 500]] },
  { id: "edge_fort_west_field_west", from: "node_fort_west", to: "node_field_west_large", cost: 1, points: [[875, 330], [720, 395], [560, 500], [470, 580]] },
  { id: "edge_fort_west_fort_east", from: "node_fort_west", to: "node_fort_east", cost: 2, points: [[875, 330], [1080, 285], [1330, 265], [1590, 300]] },
  { id: "edge_field_west_forest_dark", from: "node_field_west_large", to: "node_forest_dark", cost: 2, points: [[470, 580], [515, 760], [625, 985]] },
  { id: "edge_forest_dark_field_oats", from: "node_forest_dark", to: "node_field_oats", cost: 2, points: [[625, 985], [735, 815], [860, 650], [1015, 500]] },
  { id: "edge_swamp_forest_west", from: "node_swamp_black", to: "node_forest_dark", cost: 2, points: [[580, 1190], [595, 1085], [625, 985]] },
  { id: "edge_swamp_fort_southwest", from: "node_swamp_black", to: "node_fort_southwest", cost: 2, points: [[580, 1190], [605, 1325], [650, 1460]] },
  { id: "edge_forest_fort_southwest", from: "node_res_forest", to: "node_fort_southwest", cost: 1, points: [[1260, 970], [1075, 1115], [880, 1265], [705, 1385], [650, 1460]] },
  { id: "edge_fort_southwest_mountain_west", from: "node_fort_southwest", to: "node_mountain_west_alpine", cost: 2, points: [[650, 1460], [800, 1560], [1040, 1625]] },
  { id: "edge_mountain_west_magic", from: "node_mountain_west_alpine", to: "node_spanish_magic", cost: 1, points: [[1040, 1625], [1210, 1690], [1410, 1715]] },
  { id: "edge_forest_village", from: "node_res_forest", to: "node_village_barn", cost: 1, points: [[1260, 970], [1385, 1125], [1550, 1290]] },
  { id: "edge_village_magic", from: "node_village_barn", to: "node_spanish_magic", cost: 2, points: [[1550, 1290], [1500, 1490], [1410, 1715]] },
  { id: "edge_village_mountain_gray", from: "node_village_barn", to: "node_mountain_gray", cost: 2, points: [[1550, 1290], [1735, 1265], [1905, 1235], [2055, 1215]] },
  { id: "edge_magic_science", from: "node_spanish_magic", to: "node_science_barn", cost: 2, points: [[1410, 1715], [1620, 1645], [1975, 1535]] },
  { id: "edge_science_forest_south", from: "node_science_barn", to: "node_forest_south_garden", cost: 2, points: [[1975, 1535], [2110, 1545], [2285, 1555]] },
  { id: "edge_forest_south_lake_south", from: "node_forest_south_garden", to: "node_lake_south_pond", cost: 1, points: [[2285, 1555], [2510, 1590], [2700, 1675]] },
  { id: "edge_field_east_science", from: "node_field_east_large", to: "node_science_barn", cost: 2, points: [[2630, 1260], [2440, 1370], [2210, 1480], [1975, 1535]] },
  { id: "edge_hill_field_east", from: "node_res_hill", to: "node_field_east_large", cost: 1, points: [[1720, 970], [1960, 1030], [2300, 1120], [2630, 1260]] },
  { id: "edge_hill_mountain", from: "node_res_hill", to: "node_mountain_gray", cost: 2, points: [[1720, 970], [1845, 1090], [2055, 1215]] },
  { id: "edge_village_east_well", from: "node_village_east_shed", to: "node_well_city", cost: 1, points: [[2395, 850], [2330, 715], [2255, 555]] },
  { id: "edge_village_east_lake", from: "node_village_east_shed", to: "node_lake_mist", cost: 1, points: [[2395, 850], [2485, 835], [2560, 805]] },
  { id: "edge_lake_field_east", from: "node_lake_mist", to: "node_field_east_large", cost: 1, points: [[2560, 805], [2570, 1010], [2630, 1260]] },
  { id: "edge_river_well", from: "node_res_river", to: "node_well_city", cost: 1, points: [[1720, 740], [1900, 690], [2105, 620], [2255, 555]] },
  { id: "edge_river_village_east", from: "node_res_river", to: "node_village_east_shed", cost: 1, points: [[1720, 740], [1910, 770], [2160, 815], [2395, 850]] },
  { id: "edge_fort_east_well", from: "node_fort_east", to: "node_well_city", cost: 2, points: [[1590, 300], [1800, 350], [2055, 450], [2255, 555]] },
] as const satisfies ReadonlyArray<LordMapTravelEdge>;

const lordMapStrictV6LayoutId = "venue_map_v3_strict_v6";
const lordMapStrictV6BaseAsset = "assets/lord-map-ai-strict-v6-roadless-base.webp";
const lordMapStrictV6RoadAsset = "assets/lord-map-ai-strict-v6-baked-roads.webp";

const lordMapStrictV6RuntimeLayout: LordMapBackendLayout = {
  layout_id: lordMapStrictV6LayoutId,
  art_asset: lordMapStrictV6BaseAsset,
  road_asset: lordMapStrictV6RoadAsset,
  future_art_asset: lordMapStrictV6BaseAsset,
  canvas: lordMapRoadViewBox,
  nodes: Object.fromEntries(
    lordMapSockets.map((socket) => [
      socket.id,
      {
        x: Math.round(socket.x * lordMapRoadViewBox.width / 100),
        y: Math.round(socket.y * lordMapRoadViewBox.height / 100),
        ui_target: socket.uiTarget ?? true,
        layer: socket.nodeType === "residence" || socket.id.startsWith("node_res_") ? "residence" : "territory"
      }
    ])
  ),
  edges: Object.fromEntries(
    lordMapTravelEdges.map((edge) => [
      edge.id,
      { points: edge.points.map(([x, y]) => [x, y] as const) }
    ])
  )
};

const getLordMapEffectiveLayout = (layout: LordMapBackendLayout | undefined) => {
  if (
    !layout ||
    layout.layout_id !== lordMapStrictV6LayoutId ||
    layout.art_asset === "assets/lord_map_playable_v1_display.webp"
  ) {
    return lordMapStrictV6RuntimeLayout;
  }
  return layout;
};

const lordMapMovementPoints = 6;

const getLordMapSocketById = (socketId: string, sockets: readonly LordMapSocket[] = lordMapSockets) =>
  sockets.find((socket) => socket.id === socketId) ?? sockets[0] ?? lordMapSockets[0];

const getLordMapDomainTone = (domainId: string | null | undefined): LordMapSocketTone => {
  if (domainId === "domain_north") return "domain-north";
  if (domainId === "domain_river") return "domain-river";
  if (domainId === "domain_forest") return "domain-forest";
  if (domainId === "domain_hill") return "domain-hill";
  return "neutral";
};

const getLordMapDomainFallbackLabel = (domainId: string | null | undefined) => {
  const lordId = getLordMapLordIdFromValue(domainId);
  return lordId ? lordMapLordMeta[lordId].name : domainId || "нейтрально";
};

const toLordMapNumber = (value: unknown, fallback = 0) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : fallback;
};

const toLordMapBoolean = (value: unknown) => value === true || String(value).toLowerCase() === "true";

const normalizeLordMapLayoutPoint = (
  point: LordMapBackendLayoutPoint | undefined,
  fallbackX: number,
  fallbackY: number,
  viewBox: { width: number; height: number }
): LordMapRoadPoint => [
  toLordMapNumber(point?.x, fallbackX) * viewBox.width / 100,
  toLordMapNumber(point?.y, fallbackY) * viewBox.height / 100
];

const getLordMapRuntimeViewBox = (layout: LordMapBackendLayout | undefined) => {
  const width = Math.max(1, toLordMapNumber(layout?.canvas?.width, lordMapRoadViewBox.width));
  const height = Math.max(1, toLordMapNumber(layout?.canvas?.height, lordMapRoadViewBox.height));
  return { width, height };
};

const buildLordMapRuntimeSockets = (
  state: LordMapBackendState | null,
  fallbackSockets: readonly LordMapSocket[]
): LordMapSocket[] => {
  const layout = getLordMapEffectiveLayout(state?.lord_map_layout);
  const viewBox = getLordMapRuntimeViewBox(layout);
  const layoutNodes = layout?.nodes ?? {};
  const mapNodes = Array.isArray(state?.map_nodes) ? state.map_nodes : [];

  if (!mapNodes.length || !Object.keys(layoutNodes).length) {
    return [];
  }

  const territoryViews = [
    ...(state?.territory_views ?? []),
    ...(state?.territories ?? []),
    ...(state?.neutral_territories ?? []),
    ...(state?.other_territories ?? [])
  ];
  const territoryById = new globalThis.Map<string, LordHomeBackendTerritory>(
    territoryViews
      .filter((territory) => territory.territory_id)
      .map((territory) => [String(territory.territory_id), territory])
  );

  return mapNodes
    .map<LordMapSocket | null>((node) => {
      const nodeId = String(node.node_id || "");
      const layoutNode = layoutNodes[nodeId];
      const isUiTarget = layoutNode?.ui_target !== false && layoutNode?.ui_target !== "false" && layoutNode?.ui_target !== 0;
      if (!nodeId || !layoutNode || !isUiTarget) {
        return null;
      }

      const fallbackSocket = fallbackSockets.find((socket) => socket.id === nodeId);
      const territory = node.territory_id ? territoryById.get(String(node.territory_id)) : undefined;
      const ownerDomainId = territory?.owner_domain_id ?? territory?.owner?.domain_id ?? null;
      const ownerLabel = territory?.owner?.name || getLordMapDomainFallbackLabel(ownerDomainId);
      const ownerTone = getLordMapDomainTone(ownerDomainId);
      const x = (toLordMapNumber(layoutNode.x, fallbackSocket?.x ?? 0) / viewBox.width) * 100;
      const y = (toLordMapNumber(layoutNode.y, fallbackSocket?.y ?? 0) / viewBox.height) * 100;
      const costLabel = fallbackSocket?.route ?? "";
      const contestedByDomainId = territory?.contested_by_domain_id ?? null;

      return {
        id: nodeId,
        name: territory?.node_name || territory?.name || node.name || fallbackSocket?.name || nodeId,
        x,
        y,
        tone: contestedByDomainId ? "neutral" : ownerTone,
        owner: ownerLabel,
        route: costLabel,
        nodeType: node.node_type || territory?.node_type || fallbackSocket?.nodeType,
        zoneStatus: node.zone_status || fallbackSocket?.zoneStatus,
        territoryId: node.territory_id || territory?.territory_id || fallbackSocket?.territoryId,
        status: territory?.status || fallbackSocket?.status,
        ownerDomainId,
        contestedByDomainId,
        uiTarget: isUiTarget,
        tier: Number.isFinite(Number(territory?.tier)) ? Number(territory?.tier) : fallbackSocket?.tier,
        bonusLabel: territory?.bonus_label || fallbackSocket?.bonusLabel,
        bonuses: normalizeLordMapTerritoryBonuses(territory?.bonuses),
        incomePerHour: Number.isFinite(Number(territory?.income_per_hour))
          ? Number(territory?.income_per_hour)
          : fallbackSocket?.incomePerHour,
        garrisonCapacity: Number.isFinite(Number(territory?.fort?.garrison_capacity))
          ? Number(territory?.fort?.garrison_capacity)
          : fallbackSocket?.garrisonCapacity,
        garrisonSlotsUsed: Number.isFinite(Number(territory?.fort?.garrison_slots_used))
          ? Number(territory?.fort?.garrison_slots_used)
          : fallbackSocket?.garrisonSlotsUsed,
        garrisonSlotsFree: Number.isFinite(Number(territory?.fort?.garrison_slots_free))
          ? Number(territory?.fort?.garrison_slots_free)
          : fallbackSocket?.garrisonSlotsFree
      } satisfies LordMapSocket;
    })
    .filter((socket): socket is LordMapSocket => socket !== null);
};

const buildLordMapRuntimeEdges = (
  state: LordMapBackendState | null,
  sockets: readonly LordMapSocket[],
  fallbackEdges: readonly LordMapTravelEdge[]
): LordMapTravelEdge[] => {
  const layout = getLordMapEffectiveLayout(state?.lord_map_layout);
  const viewBox = getLordMapRuntimeViewBox(layout);
  const layoutEdges = layout?.edges ?? {};
  const mapEdges = Array.isArray(state?.map_edges) ? state.map_edges : [];
  const socketIds = new Set(sockets.map((socket) => socket.id));

  if (!mapEdges.length) {
    return [];
  }

  return mapEdges
    .map((edge) => {
      const edgeId = String(edge.edge_id || `${edge.from_node_id || ""}-${edge.to_node_id || ""}`);
      const from = String(edge.from_node_id || "");
      const to = String(edge.to_node_id || "");
      const cost = Math.max(0, Math.floor(toLordMapNumber(edge.mp_cost, 0)));
      if (!edgeId || !from || !to || cost <= 0 || !socketIds.has(from) || !socketIds.has(to)) {
        return null;
      }

      const fallbackEdge = fallbackEdges.find((item) => item.id === edgeId || (item.from === from && item.to === to));
      const rawPoints = layoutEdges[edgeId]?.points;
      const points = Array.isArray(rawPoints) && rawPoints.length >= 2
        ? rawPoints.map(([x, y]) => [toLordMapNumber(x), toLordMapNumber(y)] as LordMapRoadPoint)
        : fallbackEdge?.points ?? [
            normalizeLordMapLayoutPoint(undefined, getLordMapSocketById(from, sockets).x, getLordMapSocketById(from, sockets).y, viewBox),
            normalizeLordMapLayoutPoint(undefined, getLordMapSocketById(to, sockets).x, getLordMapSocketById(to, sockets).y, viewBox)
          ];

      return {
        id: edgeId,
        from,
        to,
        cost,
        points
      } satisfies LordMapTravelEdge;
    })
    .filter((edge): edge is LordMapTravelEdge => Boolean(edge));
};

const getLordMapLordIdFromValue = (value: string | null | undefined): LordMapLordId | null => {
  if (value === "north" || value === "domain_north") return "north";
  if (value === "river" || value === "domain_river") return "river";
  if (value === "forest" || value === "domain_forest") return "forest";
  if (value === "hill" || value === "domain_hill") return "hill";
  return null;
};

type LordMapPendingBattleClaim = {
  claimId: string;
  territoryId: string;
  battleId?: string;
};

const lordMapBattleClaimStatuses = new Set(["in_battle", "contested", "contested_pending_tick"]);
const lordMapGarrisonClaimStatuses = new Set(["awaiting_garrison", "capture_pending_garrison"]);
const lordMapFinalBattleStatuses = new Set(["finished", "needs_master_review", "cancelled", "closed", "resolved"]);

const getLordMapActiveBattleId = (state: LordMapBackendState | null | undefined) => {
  const battle = [...(state?.active_battles ?? []), ...(state?.battles ?? [])].find((item) => {
    const battleId = String(item.battle_id ?? "").trim();
    const status = String(item.status ?? "").trim().toLowerCase();
    return Boolean(battleId) && !lordMapFinalBattleStatuses.has(status);
  });
  if (battle?.battle_id) {
    return String(battle.battle_id);
  }

  const alertBattle = (state?.battle_alerts ?? []).find((item) => {
    const battleId = item.cta?.battle_id ?? item.battle_id;
    const status = String(item.status ?? "").trim().toLowerCase();
    return item.type === "active_battle" && Boolean(battleId) && !lordMapFinalBattleStatuses.has(status);
  });
  return alertBattle ? String(alertBattle.cta?.battle_id ?? alertBattle.battle_id) : null;
};

const getLordMapPendingBattleClaim = (state: LordMapBackendState | null): LordMapPendingBattleClaim | null => {
  if (!state) return null;
  const domainId = state.domain?.domain_id ?? state.lord?.domain_id ?? "";
  const activeBattleAlert = (state.battle_alerts ?? []).find((item) => {
    const cta = item.cta;
    const battleId = cta?.battle_id ?? item.battle_id;
    return item.type === "active_battle" && cta?.action === "open_battle" && Boolean(battleId);
  });
  if (activeBattleAlert) {
    const cta = activeBattleAlert.cta;
    return {
      claimId: String(cta?.claim_id ?? activeBattleAlert.claim_id ?? cta?.battle_id ?? activeBattleAlert.battle_id),
      territoryId: String(cta?.territory_id ?? activeBattleAlert.territory_id ?? ""),
      battleId: String(cta?.battle_id ?? activeBattleAlert.battle_id)
    };
  }

  const alert = (state.battle_alerts ?? []).find((item) => {
    const cta = item.cta;
    const claimId = cta?.claim_id ?? item.claim_id;
    const territoryId = cta?.territory_id ?? item.territory_id;
    return (
      item.type === "claim" &&
      cta?.action === "open_battle" &&
      Boolean(claimId) &&
      Boolean(territoryId) &&
      (cta.actor === "claimant" || !cta.actor)
    );
  });
  if (alert) {
    return {
      claimId: String(alert.cta?.claim_id ?? alert.claim_id),
      territoryId: String(alert.cta?.territory_id ?? alert.territory_id)
    };
  }

  const claim = (state.claims ?? []).find((item) => {
    const claimId = item.cta?.claim_id ?? item.claim_id;
    const territoryId = item.cta?.territory_id ?? item.territory_id;
    const status = String(item.status ?? "").trim().toLowerCase();
    const ctaAction = String(item.cta?.action ?? "").trim();
    return (
      Boolean(claimId) &&
      Boolean(territoryId) &&
      !lordMapGarrisonClaimStatuses.has(status) &&
      ctaAction !== "open_garrison" &&
      ((item.battle_required && (!ctaAction || ctaAction === "open_battle")) ||
        lordMapBattleClaimStatuses.has(status)) &&
      (!item.claimant_domain_id || item.claimant_domain_id === domainId)
    );
  });
  if (!claim) return null;

  return {
    claimId: String(claim.cta?.claim_id ?? claim.claim_id),
    territoryId: String(claim.cta?.territory_id ?? claim.territory_id)
  };
};

const getLordMapCurrentLordId = (): LordMapLordId => {
  const routeParams = new URLSearchParams(window.location.search);

  return (
    getLordMapLordIdFromValue(routeParams.get("map_lord")) ??
    getLordMapLordIdFromValue(routeParams.get("domain")) ??
    getLordMapLordIdFromValue(routeParams.get("lord")) ??
    "north"
  );
};

const getLordMapInitialSelectedSocketId = (fallbackSocketId: string) => {
  const targetParam = new URLSearchParams(window.location.search).get("target");

  if (targetParam && lordMapSockets.some((socket) => socket.id === targetParam)) {
    return targetParam;
  }

  return fallbackSocketId;
};

const getLordMapKnownRouteIds = (
  routeIds: string[] | undefined,
  sockets: readonly LordMapSocket[] = lordMapSockets
) =>
  (Array.isArray(routeIds) ? routeIds : []).filter((socketId) =>
    sockets.some((socket) => socket.id === socketId)
  );

const getLordMapPendingRouteIds = (
  pendingMove: LordMapBackendPendingMove | null | undefined,
  sockets: readonly LordMapSocket[] = lordMapSockets
) =>
  getLordMapKnownRouteIds(pendingMove?.route_node_ids ?? pendingMove?.route, sockets);

const formatLordMapArrivalTime = (value: string | undefined) => {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const formatLordMapRemainingSeconds = (seconds: number) =>
  seconds <= 0 ? "сейчас" : `${seconds} сек.`;

const getLordMapMoveTiming = (
  pendingMove: LordMapBackendPendingMove | null | undefined,
  nowMs: number
) => {
  const startedAt = new Date(pendingMove?.started_at ?? "").getTime();
  const arrivalAt = new Date(pendingMove?.arrival_at ?? "").getTime();

  if (!Number.isFinite(startedAt) || !Number.isFinite(arrivalAt) || arrivalAt <= startedAt) {
    return {
      progress: 0.35,
      remainingSeconds: 0,
      isArrivalDue: false
    };
  }

  return {
    progress: Math.min(Math.max((nowMs - startedAt) / (arrivalAt - startedAt), 0), 1),
    remainingSeconds: Math.max(0, Math.ceil((arrivalAt - nowMs) / 1000)),
    isArrivalDue: nowMs >= arrivalAt
  };
};

const getLordMapDirectCost = (
  fromId: string,
  toId: string,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) => {
  const edge = edges.find(
    (travelEdge) =>
      (travelEdge.from === fromId && travelEdge.to === toId) ||
      (travelEdge.from === toId && travelEdge.to === fromId)
  );

  return edge?.cost ?? null;
};

const getLordMapTravelEdge = (
  fromId: string,
  toId: string,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) =>
  edges.find(
    (travelEdge) =>
      (travelEdge.from === fromId && travelEdge.to === toId) ||
      (travelEdge.from === toId && travelEdge.to === fromId)
  );

const getLordMapEdgePoints = (
  fromId: string,
  toId: string,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) => {
  const edge = getLordMapTravelEdge(fromId, toId, edges);

  if (!edge) {
    return [];
  }

  return edge.from === fromId ? edge.points : [...edge.points].reverse();
};

const formatLordMapSvgPoints = (points: readonly LordMapRoadPoint[]) =>
  points.map(([x, y]) => `${x},${y}`).join(" ");

const getLordMapPolylineMidpoint = (points: readonly LordMapRoadPoint[]) => {
  if (points.length === 0) {
    return { x: 0, y: 0 };
  }

  if (points.length === 1) {
    const [x, y] = points[0];
    return { x, y };
  }

  const segments = points.slice(1).map((point, index) => {
    const previous = points[index];
    const length = Math.hypot(point[0] - previous[0], point[1] - previous[1]);
    return { from: previous, to: point, length };
  });
  const totalLength = segments.reduce((total, segment) => total + segment.length, 0);
  let remaining = totalLength / 2;

  for (const segment of segments) {
    if (remaining <= segment.length) {
      const ratio = segment.length === 0 ? 0 : remaining / segment.length;
      return {
        x: segment.from[0] + (segment.to[0] - segment.from[0]) * ratio,
        y: segment.from[1] + (segment.to[1] - segment.from[1]) * ratio
      };
    }

    remaining -= segment.length;
  }

  const [x, y] = points[points.length - 1];
  return { x, y };
};

const getLordMapPointStyle = (
  point: { x: number; y: number },
  viewBox: { width: number; height: number } = lordMapRoadViewBox
) => ({
  left: `${(point.x / viewBox.width) * 100}%`,
  top: `${(point.y / viewBox.height) * 100}%`
});

const getLordMapRouteSegments = (
  pathIds: string[],
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) =>
  pathIds.slice(1).map((socketId, index) => {
    const fromId = pathIds[index];
    const points = getLordMapEdgePoints(fromId, socketId, edges);
    return {
      id: `${fromId}-${socketId}`,
      points
    };
  }).filter((segment) => segment.points.length > 1);

const isLordMapResidenceSocket = (socket: LordMapSocket) =>
  socket.nodeType === "residence" || socket.id.startsWith("node_res_");

const isLordMapForeignResidence = (socket: LordMapSocket, currentLord: LordMapRouteLord) =>
  isLordMapResidenceSocket(socket) && socket.tone !== currentLord.tone;

const isLordMapRouteStopSocket = (socket: LordMapSocket, currentLord: LordMapRouteLord) =>
  socket.tone !== currentLord.tone;

type LordMapTravelNeighbor = { id: string; cost: number };

const getLordMapNeighbors = (
  socketId: string,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) => {
  const neighbors: LordMapTravelNeighbor[] = [];

  edges.forEach((travelEdge) => {
    if (travelEdge.from === socketId) {
      neighbors.push({ id: travelEdge.to, cost: travelEdge.cost });
      return;
    }

    if (travelEdge.to === socketId) {
      neighbors.push({ id: travelEdge.from, cost: travelEdge.cost });
    }
  });

  return neighbors;
};

const getLordMapTravelState = (
  startSocketId: string,
  currentLord: LordMapRouteLord,
  sockets: readonly LordMapSocket[] = lordMapSockets,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) => {
  const distances: Record<string, number> = {};
  const previous: Record<string, string | null> = {};
  const unsettled = sockets.map((socket) => socket.id);

  sockets.forEach((socket) => {
    distances[socket.id] = Number.POSITIVE_INFINITY;
    previous[socket.id] = null;
  });
  distances[startSocketId] = 0;

  while (unsettled.length > 0) {
    let currentIndex = -1;
    let currentDistance = Number.POSITIVE_INFINITY;

    unsettled.forEach((socketId, index) => {
      if (distances[socketId] < currentDistance) {
        currentDistance = distances[socketId];
        currentIndex = index;
      }
    });

    if (currentIndex === -1) {
      break;
    }

    const [currentId] = unsettled.splice(currentIndex, 1);

    getLordMapNeighbors(currentId, edges).forEach((neighbor) => {
      const neighborSocket = getLordMapSocketById(neighbor.id, sockets);

      if (isLordMapForeignResidence(neighborSocket, currentLord)) {
        return;
      }

      const nextDistance = currentDistance + neighbor.cost;

      if (nextDistance < distances[neighbor.id]) {
        distances[neighbor.id] = nextDistance;
        previous[neighbor.id] = currentId;
      }
    });
  }

  return { distances, previous };
};

const getLordMapTravelPath = (startSocketId: string, targetSocketId: string, previous: Record<string, string | null>) => {
  if (startSocketId === targetSocketId) {
    return [startSocketId];
  }

  const path = [targetSocketId];
  let cursor = targetSocketId;

  while (previous[cursor]) {
    cursor = previous[cursor] ?? startSocketId;
    path.unshift(cursor);
  }

  return path[0] === startSocketId ? path : [];
};

type LordMapRoutePreview = {
  requestedSocketId: string;
  targetSocketId: string;
  contactSocketId: string | null;
  pathIds: string[];
  cost: number;
  status: LordMapRoutePreviewStatus;
  canMove: boolean;
  reason: string;
};

const getLordMapPathCost = (
  pathIds: string[],
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) =>
  pathIds.slice(1).reduce((totalCost, socketId, index) => {
    const previousSocketId = pathIds[index];
    return totalCost + (getLordMapDirectCost(previousSocketId, socketId, edges) ?? 0);
  }, 0);

const getLordMapFirstContactSocketId = (
  pathIds: string[],
  currentLord: LordMapRouteLord,
  sockets: readonly LordMapSocket[] = lordMapSockets
) =>
  pathIds.slice(1).find((socketId) => isLordMapRouteStopSocket(getLordMapSocketById(socketId, sockets), currentLord)) ?? null;

const getLordMapRoutePreview = (
  startSocketId: string,
  requestedSocketId: string,
  currentLord: LordMapRouteLord,
  movementPoints = lordMapMovementPoints,
  sockets: readonly LordMapSocket[] = lordMapSockets,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
): LordMapRoutePreview => {
  const requestedSocket = getLordMapSocketById(requestedSocketId, sockets);

  if (startSocketId === requestedSocketId) {
    return {
      requestedSocketId,
      targetSocketId: requestedSocketId,
      contactSocketId: null,
      pathIds: [startSocketId],
      cost: 0,
      status: "idle",
      canMove: false,
      reason: "Армия уже здесь."
    };
  }

  if (isLordMapForeignResidence(requestedSocket, currentLord)) {
    return {
      requestedSocketId,
      targetSocketId: requestedSocketId,
      contactSocketId: null,
      pathIds: [],
      cost: Number.POSITIVE_INFINITY,
      status: "blocked",
      canMove: false,
      reason: "В чужую резиденцию ход закрыт."
    };
  }

  const travelState = getLordMapTravelState(startSocketId, currentLord, sockets, edges);
  const fullPathIds = getLordMapTravelPath(startSocketId, requestedSocketId, travelState.previous);

  if (fullPathIds.length < 2) {
    return {
      requestedSocketId,
      targetSocketId: requestedSocketId,
      contactSocketId: null,
      pathIds: [],
      cost: Number.POSITIVE_INFINITY,
      status: "blocked",
      canMove: false,
      reason: "Нет открытой дороги."
    };
  }

  const targetSocketId = requestedSocketId;
  const cost = getLordMapPathCost(fullPathIds, edges);
  const contactSocketId = getLordMapFirstContactSocketId(fullPathIds, currentLord, sockets);
  const canMove = fullPathIds.length > 1 && cost <= movementPoints;
  const reason =
    cost > movementPoints
      ? `Не хватает MP: нужно ${cost}, доступно ${movementPoints}.`
      : "Маршрут открыт.";

  return {
    requestedSocketId,
    targetSocketId,
    contactSocketId,
    pathIds: fullPathIds,
    cost,
    status: "ready",
    canMove,
    reason
  };
};

const getLordMapPointAlongPath = (
  pathIds: string[],
  progress: number,
  sockets: readonly LordMapSocket[] = lordMapSockets,
  edges: readonly LordMapTravelEdge[] = lordMapTravelEdges
) => {
  if (pathIds.length === 0) {
    return { x: 0, y: 0 };
  }

  if (pathIds.length === 1) {
    const socket = getLordMapSocketById(pathIds[0], sockets);
    return { x: socket.x, y: socket.y };
  }

  const normalizedProgress = Math.min(Math.max(progress, 0), 1);
  const pathCost = getLordMapPathCost(pathIds, edges);
  const totalCost = pathCost > 0 ? pathCost : pathIds.length - 1;
  let coveredCost = normalizedProgress * totalCost;

  for (let index = 0; index < pathIds.length - 1; index += 1) {
    const fromSocket = getLordMapSocketById(pathIds[index], sockets);
    const toSocket = getLordMapSocketById(pathIds[index + 1], sockets);
    const edgeCost = getLordMapDirectCost(fromSocket.id, toSocket.id, edges) ?? 1;

    if (coveredCost <= edgeCost) {
      const localProgress = edgeCost > 0 ? coveredCost / edgeCost : 1;
      return {
        x: fromSocket.x + (toSocket.x - fromSocket.x) * localProgress,
        y: fromSocket.y + (toSocket.y - fromSocket.y) * localProgress
      };
    }

    coveredCost -= edgeCost;
  }

  const lastSocket = getLordMapSocketById(pathIds[pathIds.length - 1], sockets);
  return { x: lastSocket.x, y: lastSocket.y };
};

const castleBranchTabs = [
  { id: "all", label: "Все", icon: Castle, tone: "blue" },
  { id: "barracks", label: "Казармы", icon: Shield, tone: "red" },
  { id: "treasury", label: "Казна", icon: Coins, tone: "gold" },
  { id: "council", label: "Совет", icon: ScrollText, tone: "green" },
  { id: "mage", label: "Башня мага", icon: Sparkles, tone: "violet" }
] as const;

const castleBuildings = [
  {
    id: "residence",
    branch: "all",
    name: "Резиденция",
    state: "built",
    x: 72,
    y: 30,
    icon: Crown,
    cost: "построено",
    unlock: "Доход владения, резерв и управление домом.",
    detail: "Главная башня хранит казну, влияние и право строить ветки резиденции.",
    action: "Смотреть владение",
    tone: "blue"
  },
  {
    id: "barracks",
    branch: "barracks",
    name: "Казармы I",
    state: "built",
    x: 22,
    y: 66,
    icon: Shield,
    cost: "построено",
    unlock: "Пехота, стража и базовый гарнизон.",
    detail: "Отсюда открывается найм земных отрядов. Улучшение даст доступ к тяжелой пехоте.",
    action: "Открыть найм",
    tone: "red"
  },
  {
    id: "market",
    branch: "treasury",
    name: "Рынок",
    state: "built",
    x: 34,
    y: 62,
    icon: Coins,
    cost: "построено",
    unlock: "+25 золота за тик и удержание предложения найма.",
    detail: "Казна стабилизирует доход и помогает не проседать после дорогих построек.",
    action: "Смотреть казну",
    tone: "gold"
  },
  {
    id: "notice-board",
    branch: "council",
    name: "Доска заказов",
    state: "built",
    x: 54,
    y: 64,
    icon: ScrollText,
    cost: "построено",
    unlock: "2 публичных и 1 адресный активный заказ.",
    detail: "Через Совет лорд направляет ведьмаков и чародеек, не делая их единственным путем прогресса.",
    action: "Открыть заказы",
    tone: "green"
  },
  {
    id: "mage-study",
    branch: "mage",
    name: "Кабинет мага",
    state: "available",
    x: 62,
    y: 53,
    icon: Sparkles,
    cost: "40 золота",
    unlock: "Поддержка чародейки, разведка и защита от рейдов.",
    detail: "Первый магический узел дает лорду видимые стратегические эффекты, но не вмешивается прямо в бой.",
    action: "Построить",
    tone: "violet"
  },
  {
    id: "war-council",
    branch: "council",
    name: "Военный совет",
    state: "locked",
    x: 46,
    y: 58,
    icon: Gavel,
    cost: "нужна Доска заказов",
    unlock: "Рейды, коалиции и дипломатические сигналы.",
    detail: "Совет закрыт до развития базовой доски поручений.",
    action: "Закрыто",
    tone: "green"
  },
  {
    id: "barracks-2",
    branch: "barracks",
    name: "Казармы II",
    state: "available",
    x: 29,
    y: 62,
    icon: Hammer,
    cost: "75 золота",
    unlock: "Тяжелая пехота и +1 слот резерва.",
    detail: "Улучшение казарм усиливает набор, но может приблизить штраф анти-снежного кома.",
    action: "Улучшить",
    tone: "red"
  }
] as const;

function LordMapScreen() {
  const mapRouteParams = new URLSearchParams(window.location.search);
  stripLordRuntimeSensitiveQueryParams();
  const lordRuntimeMode = getLordRuntimeMode(mapRouteParams);
  const useDemoState = lordRuntimeMode !== "production";
  const apiBaseUrl = getLordRuntimeApiBaseUrl(mapRouteParams);
  const runtimeSession = useDemoState ? { lordId: lordHomeDemoLordId, roleToken: lordHomeDemoRoleToken } : readLordRuntimeSession(mapRouteParams);
  const isMissingLordRuntimeSession = !useDemoState && !runtimeSession;
  const backendLordId = runtimeSession?.lordId ?? "";
  const backendRoleToken = runtimeSession?.roleToken ?? "";
  const loginRedirectPath = getLordRuntimeLoginPath(apiBaseUrl, getLordRuntimeCurrentPathWithoutSensitiveParams());
  const initialMapBackendStateRef = useRef<LordMapBackendState | null>(
    useDemoState ? null : readLordRuntimeCachedState<LordMapBackendState>(apiBaseUrl, backendLordId)
  );
  const [currentLordId, setCurrentLordId] = useState<LordMapLordId>(() => getLordMapCurrentLordId());
  const currentLord = lordMapLordMeta[currentLordId];
  const initialSelectedSocketId = getLordMapInitialSelectedSocketId(currentLord.homeSocketId);
  const [armySocketId, setArmySocketId] = useState(currentLord.homeSocketId);
  const [routeStartSocketId, setRouteStartSocketId] = useState(currentLord.homeSocketId);
  const [selectedSocketId, setSelectedSocketId] = useState(initialSelectedSocketId);
  const [hoveredSocketId, setHoveredSocketId] = useState<string | null>(null);
  const [movementDraft, setMovementDraft] = useState<LordMapMovementDraft | null>(null);
  const [armyTravelProgress, setArmyTravelProgress] = useState(0);
  const [backendState, setBackendState] = useState<LordMapBackendState | null>(() => initialMapBackendStateRef.current);
  const backendStateRef = useRef<LordMapBackendState | null>(initialMapBackendStateRef.current);
  const [lordUiState, setLordUiState] = useState<LordUiState>(() =>
    initialMapBackendStateRef.current
      ? markLordUiStateOffline(adaptLordState(initialMapBackendStateRef.current, { mode: lordRuntimeMode }))
      : createLordUiState(useDemoState ? "demo" : "loading", { mode: lordRuntimeMode })
  );
  const [mapApiState, setMapApiState] = useState<"unknown" | "online" | "offline">("unknown");
  const [serverRoutePreview, setServerRoutePreview] = useState<LordMapBackendRoutePreview | null>(null);
  const [routePreviewState, setRoutePreviewState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [mapActionStatus, setMapActionStatus] = useState("");
  const [mapMode, setMapMode] = useState<LordMapMode>("march");
  const [isMapInspectorCollapsed, setIsMapInspectorCollapsed] = useState(false);
  const [isMoveSubmitting, setIsMoveSubmitting] = useState(false);
  const [arrivalBattleOpenRequestId, setArrivalBattleOpenRequestId] = useState<string | null>(null);
  const [pendingRenderNowMs, setPendingRenderNowMs] = useState(() => Date.now());
  const [mapTimerNowMs, setMapTimerNowMs] = useState(() => Date.now());
  const [mapLayers, setMapLayers] = useState<LordMapLayerState>({
    roads: true,
    territories: true,
    costs: true
  });
  const lordHomePath = useDemoState ? "/lords/home?demo=1" : "/lords/home";
  const lordBuildingsPath = useDemoState ? "/lords/home?demo=1&view=buildings" : "/lords/home?view=buildings";
  const routePreviewSerialRef = useRef(0);
  const stateFetchInFlightRef = useRef(false);
  const battleClaimOpenRef = useRef<string | null>(null);
  const lastPendingMoveRef = useRef<LordMapBackendPendingMove | null>(null);

  useEffect(() => {
    if (!isMissingLordRuntimeSession) {
      return;
    }
    clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
    window.location.replace(loginRedirectPath);
  }, [isMissingLordRuntimeSession, loginRedirectPath]);

  useEffect(() => {
    backendStateRef.current = backendState;
  }, [backendState]);
  const prefersReducedMotion = useReducedMotion();
  const backendPendingMove = backendState?.pending_move?.status === "pending" ? backendState.pending_move : null;
  const effectiveMapLayout = useMemo(
    () => getLordMapEffectiveLayout(backendState?.lord_map_layout),
    [backendState?.lord_map_layout]
  );
  const mapRoadViewBox = useMemo(
    () => useDemoState ? lordMapRoadViewBox : getLordMapRuntimeViewBox(effectiveMapLayout),
    [effectiveMapLayout, useDemoState]
  );
  const mapSockets = useMemo(
    () => useDemoState ? [...lordMapSockets] : buildLordMapRuntimeSockets(backendState, lordMapSockets),
    [backendState, useDemoState]
  );
  const mapTravelEdges = useMemo(
    () => useDemoState ? [...lordMapTravelEdges] : buildLordMapRuntimeEdges(backendState, mapSockets, lordMapTravelEdges),
    [backendState, mapSockets, useDemoState]
  );
  const mapBaseImage = useMemo(
    () => useDemoState ? lordMapStrictV6RoadlessBase : getLordMapLayoutImageAsset(effectiveMapLayout),
    [effectiveMapLayout, useDemoState]
  );
  const mapRoadImage = useMemo(
    () => useDemoState ? lordMapStrictV6BakedRoads : getLordMapLayoutRoadImageAsset(effectiveMapLayout),
    [effectiveMapLayout, useDemoState]
  );
  const hasMapModel = mapSockets.length > 0;
  const getMapSocket = useCallback((socketId: string) => getLordMapSocketById(socketId, mapSockets), [mapSockets]);
  const hasMapSocket = useCallback((socketId: string | null | undefined) =>
    Boolean(socketId && mapSockets.some((socket) => socket.id === socketId)),
    [mapSockets]
  );
  const pendingPathIds = getLordMapPendingRouteIds(backendPendingMove, mapSockets);
  const isBackendPendingMove = Boolean(backendPendingMove);
  const isMarching = movementDraft !== null || isBackendPendingMove || isMoveSubmitting;
  const mapMovementPoints = lordUiState.mp.isKnown && lordUiState.mp.currentMp !== null
    ? lordUiState.mp.currentMp
    : useDemoState ? lordMapMovementPoints : 0;
  const mapMovementCap = lordUiState.mp.isKnown && lordUiState.mp.mpCap !== null
    ? Math.max(mapMovementPoints, lordUiState.mp.mpCap)
    : useDemoState ? lordMapMovementPoints : 1;
  const isMarchMode = mapMode === "march";
  const isMapReadOnly = lordUiState.mode === "production" && lordUiState.isReadOnly;
  const syncAuthoritativeArmyNode = useCallback((nodeId: string, currentMp?: number) => {
    const normalizedNodeId = nodeId.trim();
    if (!normalizedNodeId || !hasMapSocket(normalizedNodeId)) {
      return false;
    }

    const hasCurrentMp = Number.isFinite(currentMp);
    setArmySocketId(normalizedNodeId);
    setRouteStartSocketId(normalizedNodeId);
    setBackendState((currentState) => {
      if (!currentState) {
        return currentState;
      }

      const nextState = {
        ...currentState,
        pending_move: null,
        movement: currentState.movement
          ? {
              ...currentState.movement,
              current_node_id: normalizedNodeId,
              ...(hasCurrentMp ? { current_mp: currentMp } : {})
            }
          : currentState.movement,
        domain: currentState.domain
          ? {
              ...currentState.domain,
              current_node_id: normalizedNodeId,
              ...(hasCurrentMp ? { current_mp: currentMp } : {})
            }
          : currentState.domain
      };
      backendStateRef.current = nextState;
      return nextState;
    });
    return true;
  }, [hasMapSocket]);

  const fetchLordMapState = useCallback(async (options?: { silent?: boolean; summaryOnly?: boolean }) => {
    if (useDemoState) {
      setMapApiState("offline");
      return null;
    }

    if (!backendLordId || !backendRoleToken) {
      return null;
    }

    if (stateFetchInFlightRef.current) {
      return null;
    }

    stateFetchInFlightRef.current = true;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), lordRuntimeRequestTimeoutMs);
    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (backendRoleToken) {
        headers["X-Role-Token"] = backendRoleToken;
      }

      const endpoint = options?.summaryOnly ? "summary" : "state";
      const response = await fetch(`${apiBaseUrl}/api/lords/${backendLordId}/${endpoint}`, {
        headers,
        signal: controller.signal
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        if (isLordRuntimeAuthResponse(response)) {
          clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
          window.location.replace(loginRedirectPath);
          return null;
        }
        throw new Error(getLordHomeApiErrorMessage(payload, "Приказная не отвечает"));
      }

      const nextState = options?.summaryOnly
        ? mergeLordRuntimeSummaryState(backendStateRef.current, payload as LordMapBackendState)
        : payload as LordMapBackendState;
      setBackendState(nextState);
      backendStateRef.current = nextState;
      if (!options?.summaryOnly) {
        writeLordRuntimeCachedState(apiBaseUrl, backendLordId, nextState);
      }
      setLordUiState(adaptLordState(nextState, { mode: lordRuntimeMode }));
      setMapApiState("online");
      if (!options?.silent) {
        setMapActionStatus("");
      }

      const nextLordId = getLordMapLordIdFromValue(
        nextState.domain?.domain_id ?? nextState.lord?.domain_id ?? nextState.movement?.domain_id
      );
      if (nextLordId) {
        setCurrentLordId(nextLordId);
      }

      const currentNodeId = nextState.movement?.current_node_id ?? nextState.domain?.current_node_id;
      if (currentNodeId) {
        setArmySocketId(currentNodeId);
        setRouteStartSocketId(currentNodeId);
      }

      const pendingMove = nextState.pending_move?.status === "pending" ? nextState.pending_move : null;
      const pendingTargetId = pendingMove?.requested_to_node_id ?? pendingMove?.to_node_id;
      if (pendingTargetId) {
        setSelectedSocketId(pendingTargetId);
      }
      return nextState;
    } catch (error) {
      setBackendState((currentState) => currentState);
      setLordUiState((current) => markLordUiStateOffline(current));
      setMapApiState("offline");
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      if (!options?.silent) {
        setMapActionStatus(getLordHomeCaughtErrorMessage(error, "Приказная не отвечает"));
      }
      return null;
    } finally {
      window.clearTimeout(timeoutId);
      stateFetchInFlightRef.current = false;
    }
  }, [apiBaseUrl, backendLordId, backendRoleToken, loginRedirectPath, lordRuntimeMode, useDemoState]);

  useEffect(() => {
    if (!useDemoState && backendLordId && backendRoleToken) {
      persistLordRuntimeSession({ lordId: backendLordId, roleToken: backendRoleToken });
    }
  }, [backendLordId, backendRoleToken, useDemoState]);

  useEffect(() => {
    void fetchLordMapState({ silent: true });
  }, [fetchLordMapState]);

  useEffect(() => {
    if (useDemoState || !backendLordId || !backendRoleToken) {
      return undefined;
    }

    const refreshVisibleMapState = () => {
      if (document.visibilityState === "hidden") {
        return;
      }
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      void fetchLordMapState({ silent: true });
    };

    window.addEventListener("focus", refreshVisibleMapState);
    window.addEventListener("pageshow", refreshVisibleMapState);
    document.addEventListener("visibilitychange", refreshVisibleMapState);
    return () => {
      window.removeEventListener("focus", refreshVisibleMapState);
      window.removeEventListener("pageshow", refreshVisibleMapState);
      document.removeEventListener("visibilitychange", refreshVisibleMapState);
    };
  }, [backendLordId, backendRoleToken, fetchLordMapState, useDemoState]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setMapTimerNowMs(Date.now());
    }, lordHomeClockTickMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void fetchLordMapState({ silent: true, summaryOnly: true });
    }, lordHomeStatePollMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [fetchLordMapState]);

  useEffect(() => {
    if (!backendPendingMove) {
      return undefined;
    }

    setPendingRenderNowMs(Date.now());
    const intervalMs = prefersReducedMotion ? 1000 : 180;
    const intervalId = window.setInterval(() => {
      setPendingRenderNowMs(Date.now());
    }, intervalMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [backendPendingMove?.arrival_at, backendPendingMove?.move_id, backendPendingMove?.started_at, prefersReducedMotion]);

  useEffect(() => {
    if (mapApiState !== "online" || !backendPendingMove) {
      return undefined;
    }

    const pollIntervalId = window.setInterval(() => {
      void fetchLordMapState({ silent: true, summaryOnly: true });
    }, 700);
    const timing = getLordMapMoveTiming(backendPendingMove, Date.now());
    const arrivalDelayMs = Math.max(160, timing.remainingSeconds * 1000 + 180);
    const arrivalTimeoutId = window.setTimeout(() => {
      void fetchLordMapState({ silent: true, summaryOnly: true });
    }, arrivalDelayMs);

    return () => {
      window.clearInterval(pollIntervalId);
      window.clearTimeout(arrivalTimeoutId);
    };
  }, [
    backendPendingMove?.arrival_at,
    backendPendingMove?.move_id,
    backendPendingMove?.started_at,
    fetchLordMapState,
    mapApiState
  ]);

  useEffect(() => {
    if (backendPendingMove) {
      lastPendingMoveRef.current = backendPendingMove;
      return;
    }

    if (!backendState || !lastPendingMoveRef.current) {
      return;
    }

    const arrivedMove = lastPendingMoveRef.current;
    lastPendingMoveRef.current = null;
    const arrivalRequestId = arrivedMove.move_id ?? `${arrivedMove.to_node_id ?? "move"}:${Date.now()}`;
    setArrivalBattleOpenRequestId(arrivalRequestId);
    const arrivedSocketId = backendState.movement?.current_node_id ?? backendState.domain?.current_node_id ?? arrivedMove.to_node_id;
    if (arrivedSocketId && hasMapSocket(arrivedSocketId)) {
      setMapActionStatus(`Армия прибыла: ${getMapSocket(arrivedSocketId).name}.`);
    }
    void fetchLordMapState({ silent: true }).then((nextState) => {
      if (!getLordMapPendingBattleClaim(nextState)) {
        setArrivalBattleOpenRequestId((current) => current === arrivalRequestId ? null : current);
      }
    });
  }, [backendPendingMove, backendState, fetchLordMapState, getMapSocket, hasMapSocket]);

  useEffect(() => {
    if (backendState) {
      return;
    }

    setArmySocketId(currentLord.homeSocketId);
    setRouteStartSocketId(currentLord.homeSocketId);
    setSelectedSocketId(getLordMapInitialSelectedSocketId(currentLord.homeSocketId));
    setHoveredSocketId(null);
    setMovementDraft(null);
    setArmyTravelProgress(0);
  }, [backendState, currentLord.homeSocketId]);

  useEffect(() => {
    if (!movementDraft) {
      return undefined;
    }

    if (prefersReducedMotion) {
      setArmySocketId(movementDraft.targetSocketId);
      setRouteStartSocketId(movementDraft.targetSocketId);
      setSelectedSocketId(movementDraft.targetSocketId);
      setMovementDraft(null);
      setArmyTravelProgress(0);
      return undefined;
    }

    let frameId = 0;

    const tick = () => {
      const nextProgress = Math.min((window.performance.now() - movementDraft.startedAt) / movementDraft.durationMs, 1);
      setArmyTravelProgress(nextProgress);

      if (nextProgress >= 1) {
        setArmySocketId(movementDraft.targetSocketId);
        setRouteStartSocketId(movementDraft.targetSocketId);
        setSelectedSocketId(movementDraft.targetSocketId);
        setMovementDraft(null);
        setArmyTravelProgress(0);
        return;
      }

      frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);

    return () => {
      window.cancelAnimationFrame(frameId);
    };
  }, [movementDraft, prefersReducedMotion]);

  const selectedSocket = getMapSocket(selectedSocketId);
  const pendingDisplaySocketId = backendPendingMove?.requested_to_node_id ?? backendPendingMove?.to_node_id;
  const displaySocketId = movementDraft?.targetSocketId ?? pendingDisplaySocketId ?? (isMarchMode ? hoveredSocketId : null) ?? selectedSocketId;
  const displaySocket = getMapSocket(displaySocketId);
  const armySocket = getMapSocket(armySocketId);
  const routeStartSocket = getMapSocket(routeStartSocketId);
  const requestedPreviewSocketId = displaySocket.id;
  const serverPreviewForDisplay =
    serverRoutePreview &&
    serverRoutePreview.requested_to_node_id === requestedPreviewSocketId &&
    (!serverRoutePreview.from_node_id || serverRoutePreview.from_node_id === armySocketId)
      ? serverRoutePreview
      : null;
  const serverRouteIds = getLordMapKnownRouteIds(serverPreviewForDisplay?.route, mapSockets);
  const serverMoveCost = Number(serverPreviewForDisplay?.mp_cost);
  const localRoutePreview = useDemoState
    ? getLordMapRoutePreview(routeStartSocketId, requestedPreviewSocketId, currentLord, mapMovementPoints, mapSockets, mapTravelEdges)
    : null;
  const displayRoutePreview: LordMapRoutePreview = useDemoState
    ? localRoutePreview ?? getLordMapRoutePreview(routeStartSocketId, requestedPreviewSocketId, currentLord)
    : {
        requestedSocketId: requestedPreviewSocketId,
        targetSocketId: serverPreviewForDisplay?.to_node_id ?? requestedPreviewSocketId,
        contactSocketId:
          serverPreviewForDisplay?.to_node_id && serverPreviewForDisplay.to_node_id !== requestedPreviewSocketId
            ? serverPreviewForDisplay.to_node_id
            : null,
        pathIds: serverRouteIds,
        cost: serverPreviewForDisplay && Number.isFinite(serverMoveCost) ? serverMoveCost : 0,
        status: requestedPreviewSocketId === routeStartSocketId
          ? "idle"
          : serverPreviewForDisplay?.status ?? (routePreviewState === "error" ? "blocked" : "ready"),
        canMove: Boolean(serverPreviewForDisplay?.can_move),
        reason: serverPreviewForDisplay
          ? getLordHomeApiErrorMessage(serverPreviewForDisplay, serverPreviewForDisplay.reason || "Маршрут недоступен")
          : routePreviewState === "loading"
            ? "Проверяем маршрут."
            : ""
      };
  const previewTargetSocket = getMapSocket(displayRoutePreview.targetSocketId);
  const dispatchCost = serverPreviewForDisplay && Number.isFinite(serverMoveCost) ? serverMoveCost : displayRoutePreview.cost;
  const dispatchAvailableMp = Number(serverPreviewForDisplay?.mp_available ?? mapMovementPoints);
  const serverStopSocket =
    serverPreviewForDisplay?.to_node_id &&
    serverPreviewForDisplay.to_node_id !== displayRoutePreview.requestedSocketId &&
    hasMapSocket(serverPreviewForDisplay.to_node_id)
      ? getMapSocket(serverPreviewForDisplay.to_node_id)
      : null;
  const serverPreviewBlockReason = serverPreviewForDisplay
    ? getLordHomeApiErrorMessage(serverPreviewForDisplay, displayRoutePreview.reason)
    : displayRoutePreview.reason;
  const pendingStopSocket =
    backendPendingMove?.to_node_id && hasMapSocket(backendPendingMove.to_node_id)
      ? getMapSocket(backendPendingMove.to_node_id)
      : null;
  const routeStopSocketId = pendingStopSocket?.id ?? serverStopSocket?.id ?? displayRoutePreview.contactSocketId;
  const contactSocket = routeStopSocketId ? getMapSocket(routeStopSocketId) : null;
  const activeRoutePathIds = movementDraft?.pathIds ?? (pendingPathIds.length > 1 ? pendingPathIds : isMarchMode ? serverRouteIds : []);
  const displayPathIds = movementDraft?.pathIds ?? (isMarchMode ? displayRoutePreview.pathIds : []);
  const displayRouteSegments = getLordMapRouteSegments(displayPathIds, mapTravelEdges);
  const activeRouteSegments = getLordMapRouteSegments(activeRoutePathIds, mapTravelEdges);
  const hasSeparateActiveRoute =
    activeRoutePathIds.length > 1 &&
    displayPathIds.length > 1 &&
    activeRoutePathIds.join("|") !== displayPathIds.join("|");
  const routePlanSegments = hasSeparateActiveRoute ? displayRouteSegments : [];
  const routeCurrentSegments = activeRoutePathIds.length > 1 ? activeRouteSegments : displayRouteSegments;
  const displayRouteEdgeIds = new Set(
    displayPathIds.slice(1).map((socketId, index) => getLordMapTravelEdge(displayPathIds[index], socketId, mapTravelEdges)?.id).filter(Boolean)
  );
  const activeRouteEdgeIds = new Set(
    activeRoutePathIds.slice(1).map((socketId, index) => getLordMapTravelEdge(activeRoutePathIds[index], socketId, mapTravelEdges)?.id).filter(Boolean)
  );
  const displayPathLabel = displayPathIds.map((socketId) => getMapSocket(socketId).name).join(" - ");
  const displayPathCost = displayPathIds.length > 1 ? getLordMapPathCost(displayPathIds, mapTravelEdges) : displayRoutePreview.cost;
  const hasDisplayRoute = isMarchMode && displayPathIds.length > 1 && Number.isFinite(displayPathCost);
  const pendingMoveTiming = getLordMapMoveTiming(backendPendingMove, pendingRenderNowMs);
  const pendingTravelProgress = pendingMoveTiming.progress;
  const armyMarkerPoint = movementDraft
    ? getLordMapPointAlongPath(movementDraft.pathIds, armyTravelProgress, mapSockets, mapTravelEdges)
    : isBackendPendingMove && pendingPathIds.length > 1
      ? getLordMapPointAlongPath(pendingPathIds, pendingTravelProgress, mapSockets, mapTravelEdges)
    : { x: armySocket.x, y: armySocket.y };
  const movingTargetSocket = movementDraft
    ? getMapSocket(movementDraft.targetSocketId)
    : isBackendPendingMove
      ? getMapSocket(backendPendingMove?.to_node_id ?? backendPendingMove?.requested_to_node_id ?? armySocketId)
      : null;
  const armyMarkerTargetSocketId =
    movementDraft?.targetSocketId ?? backendPendingMove?.requested_to_node_id ?? backendPendingMove?.to_node_id ?? armySocketId;
  const isPlanningFromArmy = routeStartSocketId === armySocketId;
  const canDispatchRoute =
    isMarchMode &&
    !isMapReadOnly &&
    !isMoveSubmitting &&
    !isBackendPendingMove &&
    routePreviewState !== "loading" &&
    displayRoutePreview.status !== "idle" &&
    displayRoutePreview.status !== "blocked" &&
    isPlanningFromArmy &&
    (useDemoState
      ? displayRoutePreview.canMove
      : mapApiState === "online" && Boolean(serverPreviewForDisplay?.can_move) && serverRouteIds.length > 1);
  useEffect(() => {
    if (!useDemoState && serverPreviewForDisplay) {
      return undefined;
    }

    if (
      useDemoState ||
      !isMarchMode ||
      isMapReadOnly ||
      mapApiState !== "online" ||
      !isPlanningFromArmy ||
      movementDraft ||
      isBackendPendingMove ||
      displayRoutePreview.status === "idle" ||
      !hasMapSocket(requestedPreviewSocketId)
    ) {
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      return undefined;
    }

    const serial = routePreviewSerialRef.current + 1;
    routePreviewSerialRef.current = serial;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), lordRuntimeRequestTimeoutMs);
    setRoutePreviewState("loading");

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json"
    };
    if (backendRoleToken) {
      headers["X-Role-Token"] = backendRoleToken;
    }

    void fetch(`${apiBaseUrl}/api/lords/${backendLordId}/route-preview`, {
      method: "POST",
      headers,
      signal: controller.signal,
      body: JSON.stringify({
        to_node_id: requestedPreviewSocketId,
        source: "stage2b_map"
      })
    })
      .then(async (response) => {
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(getLordHomeApiErrorMessage(payload, "Маршрут недоступен"));
        }
        if (routePreviewSerialRef.current !== serial) {
          return;
        }
        const previewPayload = payload as LordMapBackendRoutePreview;
        const previewFromNodeId = typeof previewPayload.from_node_id === "string"
          ? previewPayload.from_node_id.trim()
          : "";
        if (previewFromNodeId && previewFromNodeId !== armySocketId) {
          const didSyncArmyNode = syncAuthoritativeArmyNode(previewFromNodeId, previewPayload.mp_available);
          if (didSyncArmyNode) {
            setServerRoutePreview(null);
            setRoutePreviewState("idle");
            void fetchLordMapState({ silent: true });
            return;
          }
        }
        setServerRoutePreview(previewPayload);
        setRoutePreviewState("ready");
      })
      .catch((error) => {
        if (controller.signal.aborted || routePreviewSerialRef.current !== serial) {
          return;
        }
        setServerRoutePreview({
          status: "blocked",
          can_move: false,
          requested_to_node_id: requestedPreviewSocketId,
          route: [],
          mp_cost: 0,
          mp_available: mapMovementPoints,
          reason: getLordHomeCaughtErrorMessage(error, "Маршрут недоступен")
        });
        setRoutePreviewState("error");
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
      });

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [
    apiBaseUrl,
    armySocketId,
    backendLordId,
    backendRoleToken,
    requestedPreviewSocketId,
    displayRoutePreview.status,
    hasMapSocket,
    isBackendPendingMove,
    isMapReadOnly,
    isPlanningFromArmy,
    isMarchMode,
    mapApiState,
    mapMovementPoints,
    movementDraft,
    serverPreviewForDisplay,
    syncAuthoritativeArmyNode,
    fetchLordMapState,
    useDemoState
  ]);

  const pendingArrivalLabel = formatLordMapArrivalTime(backendPendingMove?.arrival_at);
  const pendingTargetSocket = pendingStopSocket ?? movingTargetSocket;
  const pendingRequestedSocket =
    backendPendingMove?.requested_to_node_id && backendPendingMove.requested_to_node_id !== backendPendingMove.to_node_id
      ? getMapSocket(backendPendingMove.requested_to_node_id)
      : null;
  const pendingRemainingLabel = formatLordMapRemainingSeconds(pendingMoveTiming.remainingSeconds);
  const activeRouteLabel =
    activeRoutePathIds.length > 1
      ? activeRoutePathIds.map((socketId) => getMapSocket(socketId).name).join(" - ")
      : "";
  const displayRouteText = movementDraft
    ? `Армия идет к ${movingTargetSocket?.name ?? previewTargetSocket.name}.`
    : isBackendPendingMove
      ? `Армия идет к ${pendingTargetSocket?.name ?? previewTargetSocket.name}${pendingRequestedSocket ? `, плановая цель: ${pendingRequestedSocket.name}` : ""}. Осталось: ${pendingRemainingLabel}${pendingArrivalLabel ? `, прибытие ${pendingArrivalLabel}` : ""}.`
    : isMapReadOnly
      ? "Ожидает приказа"
    : displayRoutePreview.status === "idle"
    ? `Старт маршрута: ${routeStartSocket.name}. ${currentLord.armyName}: ${mapMovementPoints}/${mapMovementCap} MP.`
    : displayRoutePreview.status === "blocked"
      ? displayRoutePreview.reason
      : !isPlanningFromArmy
        ? `Расчет: ${displayRoutePreview.cost} MP от ${routeStartSocket.name} до ${previewTargetSocket.name}. Армия сейчас в ${armySocket.name}.`
        : routePreviewState === "loading"
          ? `Путь до ${previewTargetSocket.name}: ${displayRoutePreview.cost} MP. Проверяем первый рубеж.`
          : serverStopSocket
            ? `Путь до ${previewTargetSocket.name}: ${displayRoutePreview.cost} MP. Сейчас можно идти до ${serverStopSocket.name}: ${dispatchCost} MP.`
            : !(serverPreviewForDisplay ? serverPreviewForDisplay.can_move : displayRoutePreview.canMove)
              ? serverPreviewBlockReason
              : `Поход до ${previewTargetSocket.name}: ${displayRoutePreview.cost} MP. Останется ${Math.max(0, dispatchAvailableMp - dispatchCost)} MP.`;
  const selectionOwnerLabel = movementDraft || isBackendPendingMove
    ? "в пути"
    : displaySocket.id === armySocketId
      ? currentLord.armyName
      : displaySocket.id === routeStartSocketId
        ? "старт маршрута"
        : displaySocket.owner;
  const routeActionLabel = movementDraft || isBackendPendingMove
    ? "В пути"
    : isMapReadOnly
      ? "Ожидает приказа"
    : isMoveSubmitting
      ? "Приказ..."
    : !isPlanningFromArmy
      ? "Старт не у армии"
      : displayRoutePreview.status === "idle"
        ? "Армия здесь"
        : routePreviewState === "loading"
          ? "Проверяю путь"
          : serverPreviewForDisplay && !serverPreviewForDisplay.can_move
            ? "Недоступно"
          : serverStopSocket
            ? "Идти к рубежу"
        : "Отправить армию";
  const contactNoteText =
    contactSocket && contactSocket.id !== displayRoutePreview.requestedSocketId
      ? `Первый рубеж: ${contactSocket.name}`
      : null;
  const activeRouteNoteText =
    activeRouteLabel && (isBackendPendingMove || hasSeparateActiveRoute)
      ? `Текущий ход: ${activeRouteLabel}`
      : null;
  const activeBattle = lordUiState.activeBattle.active;
  const activeBattleId = lordUiState.activeBattle.battleId;
  const mapBattleClaim = useMemo(() => getLordMapPendingBattleClaim(backendState), [backendState]);
  const navigateToLordMapBattle = useCallback((battleId: string, territoryId = "") => {
    const territoryQuery = territoryId ? `&territory_id=${encodeURIComponent(territoryId)}` : "";
    window.location.assign(
      withLordRuntimeQuery(
        `/lords/battle?battle_id=${encodeURIComponent(battleId)}&return_to=map${territoryQuery}`,
        apiBaseUrl,
        { lordId: backendLordId }
      )
    );
  }, [apiBaseUrl, backendLordId]);
  const openLordMapBattle = useCallback(async (source = "stage2b_map_claim") => {
    if (activeBattleId) {
      navigateToLordMapBattle(activeBattleId, mapBattleClaim?.territoryId);
      return;
    }

    if (mapBattleClaim?.battleId) {
      navigateToLordMapBattle(mapBattleClaim.battleId, mapBattleClaim.territoryId);
      return;
    }

    const refreshedState = await fetchLordMapState({ silent: true });
    const refreshedBattleId = getLordMapActiveBattleId(refreshedState);
    const refreshedBattleClaim = getLordMapPendingBattleClaim(refreshedState);
    if (refreshedBattleId) {
      navigateToLordMapBattle(refreshedBattleId, refreshedBattleClaim?.territoryId);
      return;
    }

    const battleClaim = refreshedBattleClaim ?? mapBattleClaim;
    if (battleClaim?.battleId) {
      navigateToLordMapBattle(battleClaim.battleId, battleClaim.territoryId);
      return;
    }

    if (!battleClaim) {
      setMapActionStatus("Активного боя сейчас нет.");
      return;
    }

    if (battleClaimOpenRef.current === battleClaim.claimId) {
      setMapActionStatus("Бой уже открывается.");
      return;
    }

    battleClaimOpenRef.current = battleClaim.claimId;
    setMapActionStatus("Открываю бой за территорию.");
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), lordRuntimeRequestTimeoutMs);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "application/json"
      };
      if (backendRoleToken) {
        headers["X-Role-Token"] = backendRoleToken;
      }
      const response = await fetch(`${apiBaseUrl}/api/lord-battles`, {
        method: "POST",
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          claim_id: battleClaim.claimId,
          territory_id: battleClaim.territoryId,
          source
        })
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Бой не открыт"));
      }
      const battleId = typeof (payload as { battle_id?: unknown } | null)?.battle_id === "string"
        ? (payload as { battle_id: string }).battle_id
        : "";
      if (!battleId) {
        throw new Error("Бой создан без номера. Обновите карту или позовите мастера.");
      }
      navigateToLordMapBattle(battleId, battleClaim.territoryId);
    } catch (error) {
      setMapActionStatus(getLordHomeCaughtErrorMessage(error, "Бой не открыт. Позовите мастера."));
    } finally {
      window.clearTimeout(timeoutId);
      battleClaimOpenRef.current = null;
    }
  }, [
    activeBattleId,
    apiBaseUrl,
    backendLordId,
    backendRoleToken,
    fetchLordMapState,
    mapBattleClaim?.claimId,
    mapBattleClaim?.territoryId,
    mapBattleClaim?.battleId,
    navigateToLordMapBattle
  ]);

  useEffect(() => {
    if (!arrivalBattleOpenRequestId || !mapBattleClaim || isBackendPendingMove || movementDraft || isMoveSubmitting) {
      return;
    }

    setArrivalBattleOpenRequestId(null);
    void openLordMapBattle("stage2b_map_arrival");
  }, [
    arrivalBattleOpenRequestId,
    isBackendPendingMove,
    isMoveSubmitting,
    mapBattleClaim?.claimId,
    mapBattleClaim?.territoryId,
    movementDraft,
    openLordMapBattle
  ]);

  const mapClaimBannerText =
    mapBattleClaim && !isBackendPendingMove
      ? "Предбоевой рубеж: заявка на спорную территорию ожидает решения."
      : "";
  const mapTimerSummary = backendState?.timer_summary ?? null;
  const backendArmyCapacity = Number(backendState?.domain?.active_army_capacity);
  const mapArmyCapacity = Math.min(
    8,
    Math.max(
      1,
      Number.isFinite(backendArmyCapacity)
        ? backendArmyCapacity
        : lordHomeInitialDomainStats.activeArmyCapacity
    )
  );
  const backendActiveArmy = getLordHomeStacksFromBackend(backendState?.active_army ?? null);
  const mapActiveArmyStacks = mapApiState === "offline" && useDemoState ? lordHomeInitialArmy : backendActiveArmy;
  const mapArmySlots = Array.from({ length: mapArmyCapacity }, (_, index) => mapActiveArmyStacks[index] ?? null);
  const mapArmyUnitCount = mapActiveArmyStacks.reduce((total, stack) => total + stack.count, 0);
  const mapHudStatusText = movementDraft
    ? `Идет к ${movingTargetSocket?.name ?? previewTargetSocket.name}`
    : isBackendPendingMove
      ? `В пути к ${pendingTargetSocket?.name ?? previewTargetSocket.name}: ${pendingRemainingLabel}`
      : `Стоит в ${armySocket.name}`;
  const mapBattleSocket =
    hasMapModel &&
    (activeBattleId || mapBattleClaim) &&
    !movementDraft &&
    !isBackendPendingMove &&
    !isMoveSubmitting &&
    isLordMapRouteStopSocket(armySocket, currentLord)
      ? armySocket
      : null;
  const mapEnemyArmyIntel = (backendState?.lord_map_intel?.enemy_armies ?? []).filter((intel) =>
    hasMapSocket(intel.node_id)
  );
  const territoryInfoRows = getLordMapTerritoryInfoRows(displaySocket);

  const setLordMapMode = (mode: LordMapMode) => {
    setMapMode(mode);
    setHoveredSocketId(null);
    if (mode === "info") {
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
    }
  };

  const toggleMapLayer = (layerId: LordMapLayerId) => {
    setMapLayers((currentLayers) => ({
      ...currentLayers,
      [layerId]: !currentLayers[layerId]
    }));
  };

  const runLocalMovement = (pathIds: string[], targetSocketId: string, cost: number) => {
    setSelectedSocketId(targetSocketId);
    setHoveredSocketId(null);

    const durationMs = prefersReducedMotion ? 0 : Math.max(900, cost * 420);

    if (durationMs === 0) {
      setArmySocketId(targetSocketId);
      setRouteStartSocketId(targetSocketId);
      setArmyTravelProgress(0);
      return;
    }

    setArmyTravelProgress(0);
    setMovementDraft({
      pathIds,
      targetSocketId,
      startedAt: window.performance.now(),
      durationMs
    });
  };

  const sendArmyToPreviewTarget = async () => {
    if (!canDispatchRoute || movementDraft || isBackendPendingMove) {
      return;
    }

    if (mapApiState !== "online" || !serverPreviewForDisplay) {
      if (!useDemoState) {
        setMapActionStatus(lordUiState.readonlyReason || "Маршрут должен подтвердить сервер.");
        return;
      }
      runLocalMovement(displayRoutePreview.pathIds, displayRoutePreview.targetSocketId, displayRoutePreview.cost);
      return;
    }

    const routeIds = serverRouteIds.length > 1 ? serverRouteIds : displayRoutePreview.pathIds;
    const moveTargetId = serverPreviewForDisplay.to_node_id ?? routeIds[routeIds.length - 1] ?? displayRoutePreview.targetSocketId;
    const expectedCost = Number.isFinite(serverMoveCost) ? serverMoveCost : getLordMapPathCost(routeIds, mapTravelEdges);
    if (!useDemoState && (routeIds.length < 2 || !Number.isFinite(serverMoveCost))) {
      setMapActionStatus("Маршрут не подтвержден сервером.");
      return;
    }
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json"
    };
    if (backendRoleToken) {
      headers["X-Role-Token"] = backendRoleToken;
    }

    setIsMoveSubmitting(true);
    setMapActionStatus("Отправляю приказ.");
    setSelectedSocketId(displayRoutePreview.requestedSocketId);
    setHoveredSocketId(null);

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), lordRuntimeRequestTimeoutMs);
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${backendLordId}/move`, {
        method: "POST",
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          to_node_id: displayRoutePreview.requestedSocketId,
          route_node_ids: routeIds,
          expected_cost: expectedCost,
          source: "stage2b_map"
        })
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Поход не принят"));
      }

      const result = payload as LordMapBackendMoveResponse;
      const acceptedTargetId = result.to_node_id ?? moveTargetId;
      const requestedTargetId = result.requested_to_node_id ?? displayRoutePreview.requestedSocketId;
      const acceptedTargetSocket = getMapSocket(acceptedTargetId);
      const pendingMove = result.pending_move;
      if (!pendingMove || pendingMove.status !== "pending") {
        await fetchLordMapState({ silent: true });
        setMapActionStatus("Приказ отправлен, но сервер не вернул ожидающий поход. Обновите карту или позовите мастера.");
        return;
      }
      setMapActionStatus(
        acceptedTargetId !== requestedTargetId
          ? `Приказ принят: первый рубеж ${acceptedTargetSocket.name}.`
          : "Приказ принят."
      );
      setBackendState((currentState) => {
        const nextCurrentMp = result.current_mp ?? pendingMove.current_mp;

        if (!currentState) {
          return {
            pending_move: pendingMove,
            movement: {
              current_node_id: pendingMove.from_node_id ?? armySocketId,
              current_mp: nextCurrentMp
            }
          };
        }

        return {
          ...currentState,
          pending_move: pendingMove,
          movement: currentState.movement
            ? {
                ...currentState.movement,
                current_node_id: pendingMove.from_node_id ?? currentState.movement.current_node_id,
                current_mp: nextCurrentMp ?? currentState.movement.current_mp
              }
            : currentState.movement,
          domain: currentState.domain
            ? {
                ...currentState.domain,
                current_node_id: pendingMove.from_node_id ?? currentState.domain.current_node_id,
                current_mp: nextCurrentMp ?? currentState.domain.current_mp
              }
            : currentState.domain
        };
      });
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      setPendingRenderNowMs(Date.now());
      if (pendingMove.from_node_id && hasMapSocket(pendingMove.from_node_id)) {
        setArmySocketId(pendingMove.from_node_id);
        setRouteStartSocketId(pendingMove.from_node_id);
      }
      window.setTimeout(() => {
        void fetchLordMapState({ silent: true, summaryOnly: true });
      }, 280);
    } catch (error) {
      setMapActionStatus(getLordHomeCaughtErrorMessage(error, "Поход не принят"));
    } finally {
      window.clearTimeout(timeoutId);
      setIsMoveSubmitting(false);
    }
  };

  return (
    <main className="lord-map-game-screen" onContextMenu={(event) => event.preventDefault()}>
      <div className="lord-map-game-stage">
        <div className="lord-map-game-grade" />
        <header className="lord-map-top-strip">
          <LordHomeTimerChip timerSummary={mapTimerSummary} nowMs={mapTimerNowMs} />
        </header>
        <nav className="lord-map-left-dock lord-home-left-dock" aria-label="Основные действия лорда">
          {lordHomeActionDock.map((action) => (
            <button
              key={action.id}
              className={`lord-home-dock-button action-${action.id} ${action.tone}${action.id === "map" ? " is-selected" : ""}${"alert" in action && action.alert && (activeBattle || mapBattleClaim) ? " is-alert" : ""}`}
              type="button"
              aria-label={action.label}
              onClick={() => {
                if (action.id === "castle") {
                  window.location.assign(withLordRuntimeQuery(lordHomePath, apiBaseUrl));
                  return;
                }

                if (action.id === "map") {
                  return;
                }

                if (action.id === "buildings") {
                  window.location.assign(withLordRuntimeQuery(lordBuildingsPath, apiBaseUrl));
                  return;
                }

                if (action.id === "battle") {
                  void openLordMapBattle("stage2b_map_dock");
                  return;
                }

                window.location.assign(withLordRuntimeQuery(`/lords/home?panel=${action.id}`, apiBaseUrl));
              }}
            >
              <LordHomeActionIcon src={action.icon} />
              <span className="lord-home-dock-label">{action.label}</span>
            </button>
          ))}
        </nav>

        <section className="lord-map-board" aria-label="Карта земель">
          <motion.div
            className={`lord-map-artboard${mapLayers.territories ? " show-territories" : " hide-territories"}${mapLayers.roads ? " show-roads" : " hide-roads"}`}
            initial={prefersReducedMotion ? false : { opacity: 0.82, scale: 1.012 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, scale: 1 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.28, ease: "easeOut" }}
          >
            <img className="lord-map-playable-image is-base-map" src={mapBaseImage} alt="" draggable={false} />
            {mapRoadImage && (
              <img
                className={`lord-map-playable-image is-road-map${mapLayers.roads ? " is-visible" : ""}`}
                src={mapRoadImage}
                alt=""
                draggable={false}
              />
            )}
            {(routePlanSegments.length > 0 || routeCurrentSegments.length > 0) && (
              <svg
                className="lord-map-route-layer"
                viewBox={`0 0 ${mapRoadViewBox.width} ${mapRoadViewBox.height}`}
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                {routePlanSegments.map((segment) => (
                  <g key={`plan-${segment.id}`}>
                    <polyline className="lord-map-route-plan-shadow" points={formatLordMapSvgPoints(segment.points)} />
                    <polyline className="lord-map-route-plan" points={formatLordMapSvgPoints(segment.points)} />
                  </g>
                ))}
                {routeCurrentSegments.map((segment) => (
                  <g key={segment.id}>
                    <polyline className="lord-map-route-highlight-shadow" points={formatLordMapSvgPoints(segment.points)} />
                    <polyline className="lord-map-route-highlight" points={formatLordMapSvgPoints(segment.points)} />
                  </g>
                ))}
              </svg>
            )}
            <div className="lord-map-owner-layer">
              {mapSockets.map((socket) => {
                const directTravelCost = getLordMapDirectCost(routeStartSocketId, socket.id, mapTravelEdges);
                const isArmySocket = socket.id === armySocketId && !movementDraft && !isBackendPendingMove;
                const isRouteStart = socket.id === routeStartSocketId && !isArmySocket;
                const isRouteStep = displayPathIds.includes(socket.id) || activeRoutePathIds.includes(socket.id);
                const isRouteStop = routeStopSocketId === socket.id && hasDisplayRoute;
                const isPreviewTarget = isMarchMode && displaySocket.id === socket.id && !isArmySocket;
                const isRequestedTarget =
                  isMarchMode &&
                  displayRoutePreview.requestedSocketId === socket.id &&
                  routeStopSocketId !== null &&
                  routeStopSocketId !== socket.id;
                const isDirectRoute = isMarchMode && directTravelCost !== null && !isArmySocket && !isLordMapForeignResidence(socket, currentLord);
                const isBlockedTarget = isMarchMode && isPreviewTarget && displayRoutePreview.status === "blocked";
                const isOutOfRange =
                  isMarchMode &&
                  isPreviewTarget &&
                  displayRoutePreview.pathIds.length > 1 &&
                  Number.isFinite(displayRoutePreview.cost) &&
                  displayRoutePreview.cost > mapMovementPoints;

                return (
                  <button
                    key={socket.id}
                    className={`lord-map-owner-socket ${socket.tone}${selectedSocket.id === socket.id ? " is-selected" : ""}${isArmySocket ? " is-army-node" : ""}${isRouteStart ? " is-route-start" : ""}${isRouteStep ? " is-route-step" : ""}${isRouteStop ? " is-route-stop" : ""}${isDirectRoute ? " is-direct-route" : ""}${isPreviewTarget ? " is-preview-target" : ""}${isRequestedTarget ? " is-requested-target" : ""}${isBlockedTarget ? " is-blocked-target" : ""}${isOutOfRange ? " is-out-of-range" : ""}`}
                    type="button"
                    style={{ left: `${socket.x}%`, top: `${socket.y}%` }}
                    onClick={() => {
                      if (!isMarching) {
                        setSelectedSocketId(socket.id);
                      }
                    }}
                    onFocus={() => {
                      if (!isMarching && isMarchMode) {
                        setHoveredSocketId(socket.id);
                      }
                    }}
                    onBlur={() => setHoveredSocketId(null)}
                    onMouseEnter={() => {
                      if (!isMarching && isMarchMode) {
                        setHoveredSocketId(socket.id);
                      }
                    }}
                    onMouseLeave={() => setHoveredSocketId(null)}
                    aria-label={isArmySocket ? `${socket.name}, ${currentLord.armyName}` : socket.name}
                    disabled={isMarching}
                  />
                );
              })}
            </div>
            <div className="lord-map-cost-layer" aria-hidden="true">
              {mapLayers.costs && mapTravelEdges.map((travelEdge) => {
                const labelPoint = getLordMapPolylineMidpoint(travelEdge.points);
                const isRouteCost = displayRouteEdgeIds.has(travelEdge.id);
                const isActiveRouteCost = activeRouteEdgeIds.has(travelEdge.id);

                return (
                  <span
                    key={travelEdge.id}
                    className={`lord-map-travel-cost${isRouteCost ? " is-route-cost" : ""}${isActiveRouteCost ? " is-active-route-cost" : ""}${travelEdge.cost > mapMovementPoints ? " is-out-of-range" : ""}`}
                    style={getLordMapPointStyle(labelPoint, mapRoadViewBox)}
                  >
                    {travelEdge.cost} MP
                  </span>
                );
              })}
              {mapLayers.costs && hasDisplayRoute && (
                <span
                  className={`lord-map-travel-cost is-total-cost${displayRoutePreview.cost > mapMovementPoints ? " is-out-of-range" : ""}`}
                  style={{ left: `${previewTargetSocket.x}%`, top: `${previewTargetSocket.y}%` }}
                >
                  итого {displayRoutePreview.cost} MP
                </span>
              )}
            </div>
            {hasMapModel && (
              <button
              className={`lord-map-army-marker ${currentLord.tone}${movementDraft || isBackendPendingMove || isMoveSubmitting ? " is-moving" : ""}`}
              type="button"
              style={{ left: `${armyMarkerPoint.x}%`, top: `${armyMarkerPoint.y}%` }}
              onClick={() => setSelectedSocketId(armyMarkerTargetSocketId)}
              onFocus={() => {
                if (isMarchMode) {
                  setHoveredSocketId(armyMarkerTargetSocketId);
                }
              }}
              onBlur={() => setHoveredSocketId(null)}
              onMouseEnter={() => {
                if (isMarchMode) {
                  setHoveredSocketId(armyMarkerTargetSocketId);
                }
              }}
              onMouseLeave={() => setHoveredSocketId(null)}
              aria-label={`${currentLord.armyName}, ${(movingTargetSocket ?? armySocket).name}`}
            >
              <span className="lord-map-army-aura" />
              <span className="lord-map-army-standard">
                <span className="lord-map-army-flag" />
                <span className="lord-map-army-pole" />
              </span>
              <span className="lord-map-army-caption">{movementDraft || isBackendPendingMove || isMoveSubmitting ? "Идет" : "Армия"}</span>
              </button>
            )}
            {mapBattleSocket && (
              <button
                className="lord-map-battle-cta"
                type="button"
                style={{ left: `${mapBattleSocket.x}%`, top: `${mapBattleSocket.y}%` }}
                aria-label={`Начать бой: ${mapBattleSocket.name}`}
                onClick={() => {
                  void openLordMapBattle("stage2b_map_cta");
                }}
              >
                <Swords size={15} />
                Бой
              </button>
            )}
            {mapEnemyArmyIntel.map((intel) => {
              const intelSocket = getMapSocket(intel.node_id ?? "");
              const intelLabel = intel.owner_domain_name
                ? `Разведка: ${intel.owner_domain_name}`
                : "Разведка: чужой отряд";
              const strengthLabel = intel.rough_strength
                ? `, сила: ${intel.rough_strength}`
                : intel.detail_redacted
                  ? ", детали скрыты"
                  : "";

              return (
                <button
                  key={intel.target_id ?? `${intel.node_id}-enemy-army`}
                  className="lord-map-enemy-intel-marker"
                  type="button"
                  style={{ left: `${intelSocket.x}%`, top: `${intelSocket.y}%` }}
                  aria-label={`${intelLabel}${strengthLabel}`}
                  onClick={() => setSelectedSocketId(intelSocket.id)}
                >
                  <Swords size={13} />
                  <span>{intel.rough_strength ?? "?"}</span>
                </button>
              );
            })}
          </motion.div>
        </section>

        <button
          className={`lord-map-inspector-toggle${isMapInspectorCollapsed ? " is-collapsed" : ""}`}
          type="button"
          aria-label={isMapInspectorCollapsed ? "Развернуть панель карты" : "Свернуть панель карты"}
          aria-expanded={!isMapInspectorCollapsed}
          onClick={() => setIsMapInspectorCollapsed((current) => !current)}
        >
          {isMapInspectorCollapsed ? <Maximize2 size={17} /> : <Minimize2 size={17} />}
        </button>

        {!isMapInspectorCollapsed && (
          <aside className={`lord-map-selection ${displaySocket.tone}${movementDraft || isBackendPendingMove ? " is-moving" : ""}`} aria-live="polite">
            <span>{selectionOwnerLabel}</span>
            <h1>{displaySocket.name}</h1>
            <div className="lord-map-mode-toggle" role="tablist" aria-label="Режим карты">
              {lordMapModeButtons.map((modeButton) => {
                const ModeIcon = modeButton.icon;

                return (
                  <button
                    key={modeButton.id}
                    className={mapMode === modeButton.id ? "is-active" : ""}
                    type="button"
                    role="tab"
                    aria-selected={mapMode === modeButton.id}
                    onClick={() => setLordMapMode(modeButton.id)}
                  >
                    <ModeIcon size={14} />
                    {modeButton.label}
                  </button>
                );
              })}
            </div>
            {isMarchMode ? (
              <>
                <div className="lord-map-route-picker" aria-label="План похода">
                  <label>
                    <span>Старт</span>
                    <select
                      value={routeStartSocketId}
                      onChange={(event) => setRouteStartSocketId(event.target.value)}
                      disabled={isMarching}
                    >
                      {mapSockets.map((socket) => (
                        <option key={socket.id} value={socket.id}>
                          {socket.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="lord-map-route-reset"
                    type="button"
                    disabled={isMarching || routeStartSocketId === armySocketId}
                    onClick={() => setRouteStartSocketId(armySocketId)}
                  >
                    От армии
                  </button>
                  <label>
                    <span>Цель</span>
                    <select
                      value={displaySocket.id}
                      onChange={(event) => {
                        setSelectedSocketId(event.target.value);
                        setHoveredSocketId(null);
                      }}
                      disabled={isMarching}
                    >
                      {mapSockets.map((socket) => (
                        <option key={socket.id} value={socket.id}>
                          {socket.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <p>{displayRouteText}</p>
                {contactNoteText && (
                  <small className="lord-map-route-stop-note">{contactNoteText}</small>
                )}
                {activeRouteNoteText && (
                  <small className="lord-map-route-current-note">{activeRouteNoteText}</small>
                )}
                {mapClaimBannerText && (
                  <small className="lord-map-route-stop-note">{mapClaimBannerText}</small>
                )}
                {mapActionStatus && (
                  <small className="lord-map-route-stop-note">{mapActionStatus}</small>
                )}
                {displayPathIds.length > 1 && (
                  <small className="lord-map-route-chain">{displayPathLabel}</small>
                )}
                <button
                  className="lord-map-route-action"
                  type="button"
                  disabled={!canDispatchRoute || isMarching}
                  onClick={() => {
                    void sendArmyToPreviewTarget();
                  }}
                >
                  {routeActionLabel}
                </button>
              </>
            ) : (
              <div className="lord-map-info-details" aria-label="Сведения о территории">
                <dl className="lord-map-info-grid">
                  {territoryInfoRows.map((row) => (
                    <div key={row.label}>
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </aside>
        )}

        <section className="lord-map-army-hud" aria-label="Активная армия">
          <div className="lord-map-army-hud-main">
            <div className="lord-map-army-hud-title">
              <span>Активная армия</span>
              <b>{currentLord.armyName}</b>
              <small>{mapHudStatusText}</small>
            </div>
            <div className="lord-map-army-hud-row" aria-label={`${mapActiveArmyStacks.length} отрядов в активной армии`}>
              {mapArmySlots.map((stack, index) => {
                const unit = stack ? lordHomeUnitCatalog[stack.unitId] : null;

                return (
                  <div
                    key={stack?.stackId ?? `${stack?.unitId ?? "empty"}-${index}`}
                    className={`lord-map-army-hud-slot${stack && unit ? ` is-filled tone-${unit.tone}` : " is-empty"}`}
                    aria-label={stack && unit ? `${unit.name}: ${stack.count}` : "Пустой слот армии"}
                  >
                    {stack && unit ? (
                      <>
                        <img src={unit.icon} alt="" draggable={false} />
                        <b>{stack.count}</b>
                        <small>{unit.name}</small>
                      </>
                    ) : null}
                  </div>
                );
              })}
            </div>
            <div className="lord-map-army-hud-meta">
              <span><Users size={13} /> {mapArmyUnitCount}</span>
              <span>{mapActiveArmyStacks.length}/{mapArmyCapacity} слотов</span>
            </div>
          </div>
          <LordMpHud
            className="lord-map-mp-widget"
            currentMp={lordUiState.mp.isKnown || useDemoState ? mapMovementPoints : null}
            mpCap={lordUiState.mp.isKnown || useDemoState ? mapMovementCap : null}
          />
        </section>

        <aside className="lord-map-layer-panel" aria-label="Слои карты">
          <span><Layers size={14} /> Слои</span>
          <div className="lord-map-layer-toggles">
            {lordMapLayerButtons.map((layer) => {
              const LayerIcon = layer.icon;

              return (
                <button
                  key={layer.id}
                  className={`lord-map-layer-toggle${mapLayers[layer.id] ? " is-active" : ""}`}
                  type="button"
                  aria-pressed={mapLayers[layer.id]}
                  onClick={() => toggleMapLayer(layer.id)}
                >
                  <LayerIcon size={14} />
                  <b>{layer.label}</b>
                </button>
              );
            })}
          </div>
        </aside>
      </div>
    </main>
  );
}


export default LordMapScreen;
