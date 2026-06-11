import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, MouseEvent, PointerEvent as ReactPointerEvent } from "react";
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  Archive,
  BookOpen,
  Castle,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Coins,
  Crosshair,
  Crown,
  EyeOff,
  Flame,
  Gavel,
  Hammer,
  Hourglass,
  Layers,
  Map as MapIcon,
  Maximize2,
  Minimize2,
  Package,
  Route,
  ScrollText,
  Shield,
  Sparkles,
  Swords,
  Users,
  Wifi,
  XCircle
} from "lucide-react";
import buildingTreeBg from "./assets/generated/building-tree-bg-v6-holes.png";
import castleCity from "./assets/generated/castle-city-v2.png";
import buildingAlchemyLabIcon from "./assets/generated/lords-home/buildings/building-alchemy-lab-v1.png";
import buildingArcheryRangeIcon from "./assets/generated/lords-home/buildings/building-archery-range-v1.png";
import buildingBankIcon from "./assets/generated/lords-home/buildings/building-bank-v1.png";
import buildingBarracksIcon from "./assets/generated/lords-home/buildings/building-barracks-v1.png";
import buildingEnvoyHallIcon from "./assets/generated/lords-home/buildings/building-envoy-hall-v1.png";
import buildingMageStudyIcon from "./assets/generated/lords-home/buildings/building-mage-study-v1.png";
import buildingMapRoomIcon from "./assets/generated/lords-home/buildings/building-map-room-v1.png";
import buildingMarketIcon from "./assets/generated/lords-home/buildings/building-market-v1.png";
import buildingNoticeBoardIcon from "./assets/generated/lords-home/buildings/building-notice-board-v1.png";
import buildingRitualChamberIcon from "./assets/generated/lords-home/buildings/building-ritual-chamber-v1.png";
import buildingRaidOfficeIcon from "./assets/generated/lords-home/buildings/building-raid-office-v1.png";
import buildingScryingRoomIcon from "./assets/generated/lords-home/buildings/building-scrying-room-v1.png";
import buildingSiegeYardIcon from "./assets/generated/lords-home/buildings/building-siege-yard-v1.png";
import buildingStablesIcon from "./assets/generated/lords-home/buildings/building-stables-v1.png";
import buildingStorehouseIcon from "./assets/generated/lords-home/buildings/building-storehouse-v1.png";
import buildingTaxOfficeIcon from "./assets/generated/lords-home/buildings/building-tax-office-v1.png";
import buildingTrainingYardIcon from "./assets/generated/lords-home/buildings/building-training-yard-v1.png";
import buildingTreasuryHallIcon from "./assets/generated/lords-home/buildings/building-treasury-hall-v1.png";
import buildingWarAcademyIcon from "./assets/generated/lords-home/buildings/building-war-academy-v1.png";
import buildingWarCouncilIcon from "./assets/generated/lords-home/buildings/building-war-council-v1.png";
import buildingWardsIcon from "./assets/generated/lords-home/buildings/building-wards-v1.png";
import lordHomeActionBattleIcon from "./assets/generated/lords-home/actions/action-battle-v1.png";
import lordHomeActionBuildingsIcon from "./assets/generated/lords-home/actions/action-buildings-v1.png";
import lordHomeActionHelpIcon from "./assets/generated/lords-home/actions/action-help-v1.png";
import lordHomeActionLogoutIcon from "./assets/generated/lords-home/actions/action-logout-v1.png";
import lordHomeActionMapIcon from "./assets/generated/lords-home/actions/action-map-v1.png";
import lordHomeActionOrdersIcon from "./assets/generated/lords-home/actions/action-orders-v1.png";
import lordHomeActionRaidsIcon from "./assets/generated/lords-home/actions/action-raids-v1.png";
import lordHomeHudOverlay from "./assets/generated/lords-home/ui/lord-home-hud-overlay-v6.png";
import lordHomeMinimap from "./assets/generated/lords-home/minimap-v1.png";
import lordMapStrictV6BakedRoads from "./assets/generated/lords-map/lord-map-ai-strict-v6-baked-roads.webp";
import lordMapStrictV6RoadlessBase from "./assets/generated/lords-map/lord-map-ai-strict-v6-roadless-base.webp";
import lordHomeRecruitModalFrame from "./assets/generated/lords-home/ui/recruit-modal-frame-v2.png";
import territoryMistLakeHome from "./assets/generated/lords-home/territories/territory-home-mist-lake-v1.png";
import territoryNorthFortHome from "./assets/generated/lords-home/territories/territory-home-north-fort-v1.png";
import territoryRiverGateHome from "./assets/generated/lords-home/territories/territory-home-river-gate-v1.png";
import unitCavalryIcon from "./assets/generated/lords-home/units/unit-cavalry-v1.png";
import unitGuardIcon from "./assets/generated/lords-home/units/unit-guard-v1.png";
import unitHeavySiegeIcon from "./assets/generated/lords-home/units/unit-heavy-siege-v1.png";
import unitInfantryIcon from "./assets/generated/lords-home/units/unit-infantry-v1.png";
import unitRangedIcon from "./assets/generated/lords-home/units/unit-ranged-v1.png";
import unitSpecialistIcon from "./assets/generated/lords-home/units/unit-specialist-v1.png";
import lordLoginBackground from "./assets/generated/lords-login/login-background-warcraft.png";
import lordLoginLogo from "./assets/generated/lords-login/witcher-larp-logo.png";
import lordLoginMenuFrameLong from "./assets/generated/lords-login/menu-frame-warcraft-login.png";
import lordLoginMenuFrame from "./assets/generated/lords-login/menu-frame-warcraft.png";
import lordMap from "./assets/generated/lord-map-v2.png";
import { LordMpHud } from "./LordMpHud";
import LordBattleScreen from "./LordBattleScreen";
import {
  adaptLordState,
  createLordUiState,
  getLordApiErrorMessage,
  getLordClientErrorMessage,
  getLordRuntimeMode,
  markLordUiStateOffline
} from "./lordState";
import type { LordBackendStatePayload, LordUiState } from "./lordState";

type Tone = "gold" | "green" | "blue" | "red" | "violet" | "muted";

type LordHomeUnitId = "infantry" | "guard" | "ranged" | "cavalry" | "heavy-siege" | "specialist";
type LordHomeTerritoryId = "castle" | "north-fort" | "river-gate" | "mist-lake";
type LordHomeStack = { stackId?: string; unitId: LordHomeUnitId; count: number };
type LordHomeDragPayload = { lane: "army" | "garrison"; index: number } | null;
type LordHomeTransferDraft = { lane: "army" | "garrison"; index: number; mode: "transfer" | "split" } | null;
type LordHomeBackendStack = {
  army_id?: string;
  garrison_id?: string;
  card_id?: string;
  count?: number;
  status?: string;
  hidden?: boolean;
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
  fort?: {
    garrison_capacity?: number;
    garrison_slots_used?: number;
    garrison_slots_free?: number;
  } | null;
  garrisons?: LordHomeBackendStack[] | "" | null;
};
type LordHomeBackendLockReason = {
  code?: string;
  reason_code?: string;
  message?: string;
  surfaces?: string[];
};
type LordHomeRecruitPurchasePayload = {
  action?: string;
  territory_id?: string;
  card_id?: string;
  offer_id?: string;
  quantity?: number;
  source?: string;
};
type LordHomeBackendRecruitStock = {
  offer_id?: string;
  card_id?: string;
  status?: string;
  cost?: number;
  cost_per_unit?: number;
  rate_per_hour?: number;
  current_stock?: number;
  stock?: number;
  max_purchasable?: number;
  gold_cost?: number;
  garrison_capacity?: number;
  garrison_slots_used?: number;
  garrison_slots_free?: number;
  can_recruit?: boolean;
  lock_reason?: string;
  lock_reasons?: LordHomeBackendLockReason[];
  purchase_payload?: LordHomeRecruitPurchasePayload;
  unit?: {
    attack?: number;
    defense?: number;
    hp?: number;
    initiative?: number;
    move_range?: number;
    attack_range?: number;
    cost?: number;
  } | null;
};
type LordHomeBackendBuilding = {
  building_id?: string;
  branch?: string;
  name?: string;
  tier?: number | string;
  gold_cost?: number | string;
  prerequisite_ids?: string[] | string;
  missing_prerequisite_ids?: string[] | string;
  recruit_unlock_ids?: string[] | string;
  capacity_delta?: number | string;
  raid_unlock?: boolean | string;
  raid_token_delta?: number | string;
  status?: string;
  can_build?: boolean;
  effect_labels?: string[];
  effects?: {
    properties?: string[];
    unlocks?: Array<{ building_id?: string; name?: string }>;
    recruit_unlocks?: Array<{ card_id?: string; label?: string }>;
    capacity_delta?: number | string;
    raid_unlock?: boolean | string;
    raid_token_delta?: number | string;
  };
  purchase_payload?: {
    building_id?: string;
    territory_id?: string;
  };
};
type LordHomeBackendTerritoryView = LordHomeBackendTerritory & {
  short_name?: string;
  is_owned?: boolean;
  is_selectable?: boolean;
  is_residence?: boolean;
  hero_here?: boolean;
  active_army_present?: boolean;
  active_army_lock_reason?: string;
  lock_reason?: string;
  lock_reasons?: LordHomeBackendLockReason[];
  recruit_stock?: LordHomeBackendRecruitStock[];
  recruit_lock_reason?: string;
  building_tree?: {
    scope?: string;
    status?: string;
    node_ids?: string[];
    nodes?: LordHomeBackendBuilding[];
    lock_reason?: string;
  };
  building_tree_status?: string;
  building_tree_lock_reason?: string;
  background_asset_id?: string;
  card_asset_id?: string;
};
type LordHomeBackendTimerSummary = {
  server_time?: string;
  status?: string;
  current_act_id?: string | null;
  active_started_at?: string | null;
  applied_tick_count?: number;
  last_tick?: {
    timer_id?: string;
    act_id?: string;
    effect_type?: string;
    due_at?: string;
    applied_at?: string;
  } | null;
  next_tick?: {
    timer_id?: string;
    act_id?: string;
    effect_type?: string;
    due_at?: string;
    seconds_until?: number;
    minutes_until?: number;
  } | null;
};
type LordHomeTerritoryRuntime = {
  backendTerritoryId: string;
  name?: string;
  shortName?: string;
  background?: string;
  incomePerHour: number;
  heroHere: boolean;
  isOwned: boolean;
  isSelectable?: boolean;
  status: string;
  garrisonCapacity: number;
  garrisonSlotsUsed: number;
  activeArmyLockReason?: string;
  recruitLockReason?: string;
  buildingTreeLockReason?: string;
  buildingNodeIds?: string[];
  buildingNodes?: LordHomeBackendBuilding[];
  lockReasons?: LordHomeBackendLockReason[];
};
type LordHomeRecruitStockInfo = {
  rate: number;
  stock: number;
  status?: string;
  cost?: number;
  maxPurchasable?: number;
  canRecruit?: boolean;
  lockReason?: string;
  purchasePayload?: LordHomeRecruitPurchasePayload;
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

const lordHomeTerritories: Array<{
  id: LordHomeTerritoryId;
  backendTerritoryId: string;
  name: string;
  shortName: string;
  background: string;
  income: number;
  bonus: string;
  heroHere: boolean;
  recruitIds: Array<LordHomeUnitId | null>;
}> = [
  {
    id: "castle",
    backendTerritoryId: "territory_res_north",
    name: "Главный замок",
    shortName: "Замок",
    background: castleCity,
    income: 2000,
    bonus: "Резиденция, казна и основной гарнизон",
    heroHere: true,
    recruitIds: ["infantry", "guard", "ranged", "cavalry", "heavy-siege", "specialist"]
  },
  {
    id: "north-fort",
    backendTerritoryId: "territory_fort_east",
    name: "Северный форт",
    shortName: "Форт",
    background: territoryNorthFortHome,
    income: 420,
    bonus: "Оборона, стража и осадные мастерские",
    heroHere: false,
    recruitIds: ["guard", "infantry", "ranged", "heavy-siege", null, null]
  },
  {
    id: "river-gate",
    backendTerritoryId: "territory_field_oats",
    name: "Речные ворота",
    shortName: "Река",
    background: territoryRiverGateHome,
    income: 360,
    bonus: "Торговля, дороги и быстрые отряды",
    heroHere: false,
    recruitIds: ["infantry", "ranged", "cavalry", "specialist", null, null]
  },
  {
    id: "mist-lake",
    backendTerritoryId: "territory_lake_mist",
    name: "Туманное озеро",
    shortName: "Озеро",
    background: territoryMistLakeHome,
    income: 260,
    bonus: "Реагенты, разведка и скрытые тропы",
    heroHere: false,
    recruitIds: ["specialist", "ranged", "guard", null, null, null]
  }
];

const lordHomeTerritoryIdByBackendId = Object.fromEntries(
  lordHomeTerritories.map((territory) => [territory.backendTerritoryId, territory.id])
) as Partial<Record<string, LordHomeTerritoryId>>;

const isLordHomeBackendResidenceTerritory = (territory: LordHomeBackendTerritory) => {
  const territoryId = territory.territory_id ?? "";
  return (
    territory.bonus_type === "residence" ||
    territory.node_type === "residence" ||
    territoryId.startsWith("territory_res_")
  );
};

const getLordHomeLocalTerritoryId = (
  territory: LordHomeBackendTerritory,
  isOwned: boolean
): LordHomeTerritoryId | undefined => {
  const directId = territory.territory_id
    ? lordHomeTerritoryIdByBackendId[territory.territory_id]
    : undefined;
  if (directId === "castle") {
    return isOwned ? "castle" : undefined;
  }
  if (directId) {
    return directId;
  }
  if (isOwned && isLordHomeBackendResidenceTerritory(territory)) {
    return "castle";
  }
  return undefined;
};

const lordHomeTerritoryBackgroundByBackendId: Partial<Record<string, string>> = {
  territory_res_north: castleCity,
  territory_fort_east: territoryNorthFortHome,
  territory_field_oats: territoryRiverGateHome,
  territory_lake_mist: territoryMistLakeHome
};

const getLordHomeTerritoryBackground = (territory: LordHomeBackendTerritoryView, fallback: string) => {
  const territoryId = territory.territory_id ?? "";
  const directBackground = lordHomeTerritoryBackgroundByBackendId[territoryId];
  if (directBackground) return directBackground;
  if (isLordHomeBackendResidenceTerritory(territory)) return castleCity;

  const bonusType = territory.bonus_type ?? "";
  if (bonusType === "defense") return territoryNorthFortHome;
  if (bonusType === "gold_income" || bonusType === "resource" || bonusType === "order") return territoryRiverGateHome;
  if (bonusType === "magic" || bonusType === "artifact" || bonusType === "research") return territoryMistLakeHome;
  return fallback;
};

const getLordHomeLockReasonMessage = (
  reasons: LordHomeBackendLockReason[] | undefined,
  surfaces: string[],
  fallback = ""
) => {
  const surfaceSet = new Set(surfaces);
  const reason = reasons?.find((item) =>
    (item.surfaces ?? []).some((surface) => surfaceSet.has(surface))
  );
  return reason ? getLordApiErrorMessage(reason, fallback) : fallback;
};

const lordHomeInitialRecruitStock: Record<LordHomeTerritoryId, Record<LordHomeUnitId, LordHomeRecruitStockInfo>> = {
  castle: {
    infantry: { rate: 24, stock: 0 },
    guard: { rate: 12, stock: 0 },
    ranged: { rate: 12, stock: 0 },
    cavalry: { rate: 4, stock: 0 },
    "heavy-siege": { rate: 2, stock: 0 },
    specialist: { rate: 3, stock: 0 }
  },
  "north-fort": {
    infantry: { rate: 24, stock: 8 },
    guard: { rate: 12, stock: 12 },
    ranged: { rate: 12, stock: 4 },
    cavalry: { rate: 0, stock: 0 },
    "heavy-siege": { rate: 2, stock: 1 },
    specialist: { rate: 0, stock: 0 }
  },
  "river-gate": {
    infantry: { rate: 24, stock: 5 },
    guard: { rate: 0, stock: 0 },
    ranged: { rate: 12, stock: 6 },
    cavalry: { rate: 4, stock: 2 },
    "heavy-siege": { rate: 0, stock: 0 },
    specialist: { rate: 3, stock: 1 }
  },
  "mist-lake": {
    infantry: { rate: 0, stock: 0 },
    guard: { rate: 12, stock: 3 },
    ranged: { rate: 12, stock: 4 },
    cavalry: { rate: 0, stock: 0 },
    "heavy-siege": { rate: 0, stock: 0 },
    specialist: { rate: 3, stock: 2 }
  }
};

const createEmptyLordHomeRecruitStock = () =>
  Object.fromEntries(
    lordHomeTerritories.map((territory) => [
      territory.id,
      Object.fromEntries(lordHomeUnitOrder.map((unitId) => [unitId, { rate: 0, stock: 0 }]))
    ])
  ) as Record<LordHomeTerritoryId, Record<LordHomeUnitId, LordHomeRecruitStockInfo>>;

const lordHomeInitialGarrisons: Record<LordHomeTerritoryId, LordHomeStack[]> = {
  castle: [
    { unitId: "guard", count: 1 },
    { unitId: "infantry", count: 1 }
  ],
  "north-fort": [
    { unitId: "guard", count: 2 },
    { unitId: "ranged", count: 1 }
  ],
  "river-gate": [
    { unitId: "infantry", count: 2 },
    { unitId: "specialist", count: 1 }
  ],
  "mist-lake": [
    { unitId: "specialist", count: 1 },
    { unitId: "guard", count: 1 }
  ]
};

const lordHomeInitialArmy: LordHomeStack[] = [
  { unitId: "infantry", count: 1 },
  { unitId: "ranged", count: 1 }
];

const lordHomeEmptyArmy: LordHomeStack[] = [];

const createEmptyLordHomeGarrisons = () =>
  lordHomeTerritories.reduce(
    (accumulator, territory) => ({ ...accumulator, [territory.id]: [] }),
    {} as Record<LordHomeTerritoryId, LordHomeStack[]>
  );

type LordHomeRecruitOffer = {
  offerId: string;
  cardId: string;
  status: string;
  cost: number;
  rate: number;
  stock: number;
};

type LordHomeBackendState = LordBackendStatePayload & {
  domain?: {
    domain_id?: string;
    gold?: number;
    starting_gold?: number;
    base_income?: number;
    income_per_hour?: number;
    raw_income_per_hour?: number;
    territory_income_per_hour?: number;
    current_mp?: number;
    mp_cap?: number;
    current_node_id?: string;
    active_army_capacity?: number;
    active_army_slots_used?: number;
    active_army_slots_free?: number;
    raid_tokens?: number;
    raid_token_cap?: number;
  };
  resources?: {
    gold?: number;
    income_per_hour?: number;
    raw_income_per_hour?: number;
    territory_income_per_hour?: number;
    current_mp?: number;
    mp_cap?: number;
    raid_tokens?: number;
    raid_token_cap?: number;
  };
  movement?: {
    current_node_id?: string;
    current_mp?: number;
    mp_cap?: number;
  };
  timer_summary?: LordHomeBackendTimerSummary;
  building_catalog?: LordHomeBackendBuilding[];
  owned_buildings?: Array<{ building_id?: string; territory_id?: string; status?: string }>;
  territories?: LordHomeBackendTerritory[];
  neutral_territories?: LordHomeBackendTerritory[];
  other_territories?: LordHomeBackendTerritory[];
  territory_views?: LordHomeBackendTerritoryView[];
  active_army_location?: {
    node_id?: string;
    node_name?: string;
    territory_id?: string;
    pending_move_active?: boolean;
  };
  active_army?: LordHomeBackendStack[];
  orders?: LordHomeOrder[];
  order_cap?: LordHomeOrderCap;
  escrow?: LordHomeOrderEscrow;
  order_conflicts?: LordHomeOrderConflict[];
  visible_targets?: LordHomeOrderTarget[];
  eligible_recipients?: LordHomeOrderRecipient[];
  raid_tokens?: number;
  raid_rules?: LordHomeRaidRule[];
  raid_targets?: LordHomeRaidTarget[];
  active_raid_effects?: LordHomeRaidEffect[];
  raid_history?: LordHomeRaidEffect[];
  raid_effects?: LordHomeRaidEffect[];
  battles?: Array<Record<string, unknown> & { battle_id?: string; status?: string }>;
  active_battles?: Array<Record<string, unknown> & { battle_id?: string; status?: string }>;
  claims?: LordMapClaimPayload[];
  battle_alerts?: LordMapBattleAlertPayload[];
  recruit_market?: Array<{
    offer_id: string;
    card_id: string;
    status?: string;
    cost?: number;
    rate_per_hour?: number;
    current_stock?: number;
    stock?: number;
    unit?: {
      attack?: number;
      defense?: number;
      hp?: number;
      initiative?: number;
      move_range?: number;
      attack_range?: number;
      cost?: number;
    } | null;
  }>;
  army_reserve?: Array<{ card_id: string; count: number; status?: string }>;
};

type LordHomeRecruitActionResponse = {
  status?: string;
  territory_id?: string;
  card_id?: string;
  count?: number;
  gold_spent?: number;
  garrison?: LordHomeBackendStack;
};

type LordHomeTransferActionResponse = {
  status?: string;
  territory_id?: string;
  operation?: string;
  card_id?: string;
  count?: number;
  source_remaining?: number;
  source_stack_id?: string;
  target_stack_id?: string;
  target_stack?: LordHomeBackendStack;
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

const lordHomeDefaultLordId = "p_lord_1";
const lordHomeDefaultRoleToken = "LORD-NORTH-R8K4";
const lordHomeClockTickMs = 1000;
const lordHomeStatePollMs = 10_000;
const lordRuntimeApiStorageKey = "witcher_larp_api_base_url";
const lordRuntimeStateCachePrefix = "witcher_larp_lord_state_cache_v1";
const lordRuntimeStateCacheTtlMs = 12 * 60 * 60 * 1000;
const lordRuntimeProductionPort = "8002";
const lordRuntimeRequestTimeoutMs = 6_000;

const normalizeLordRuntimeApiBaseUrl = (value: string | null | undefined) => (value || "").trim().replace(/\/$/, "");

const isLordRuntimeProductionOrigin = () => window.location.protocol.startsWith("http") && window.location.port === lordRuntimeProductionPort;

const getLordRuntimeApiBaseUrl = (routeParams: URLSearchParams) => {
  if (isLordRuntimeProductionOrigin()) {
    localStorage.removeItem(lordRuntimeApiStorageKey);
    return "";
  }

  const queryApiBaseUrl = normalizeLordRuntimeApiBaseUrl(routeParams.get("api"));
  if (queryApiBaseUrl) {
    localStorage.setItem(lordRuntimeApiStorageKey, queryApiBaseUrl);
    return queryApiBaseUrl;
  }

  return normalizeLordRuntimeApiBaseUrl(
    localStorage.getItem(lordRuntimeApiStorageKey) || import.meta.env.VITE_API_BASE_URL
  );
};

const withLordRuntimeQuery = (
  path: string,
  apiBaseUrl: string,
  auth?: { lordId?: string; roleToken?: string }
) => {
  const normalizedApiBaseUrl = isLordRuntimeProductionOrigin() ? "" : normalizeLordRuntimeApiBaseUrl(apiBaseUrl);
  const url = new URL(path, window.location.origin);
  if (normalizedApiBaseUrl) {
    url.searchParams.set("api", normalizedApiBaseUrl);
  }
  if (auth?.lordId) {
    url.searchParams.set("lord", auth.lordId);
  }
  if (auth?.roleToken) {
    url.searchParams.set("token", auth.roleToken);
  }
  return `${url.pathname}${url.search}${url.hash}`;
};

const getLordRuntimeStateCacheKey = (apiBaseUrl: string, lordId: string) =>
  `${lordRuntimeStateCachePrefix}:${normalizeLordRuntimeApiBaseUrl(apiBaseUrl) || "same-origin"}:${lordId}`;

function readLordRuntimeCachedState<T>(apiBaseUrl: string, lordId: string): T | null {
  try {
    const raw = localStorage.getItem(getLordRuntimeStateCacheKey(apiBaseUrl, lordId));
    if (!raw) return null;

    const parsed = JSON.parse(raw) as { cachedAt?: unknown; state?: unknown };
    const cachedAt = Number(parsed.cachedAt);
    if (!Number.isFinite(cachedAt) || Date.now() - cachedAt > lordRuntimeStateCacheTtlMs) {
      return null;
    }
    if (!parsed.state || typeof parsed.state !== "object") {
      return null;
    }

    return parsed.state as T;
  } catch {
    return null;
  }
}

const writeLordRuntimeCachedState = (apiBaseUrl: string, lordId: string, state: unknown) => {
  try {
    localStorage.setItem(
      getLordRuntimeStateCacheKey(apiBaseUrl, lordId),
      JSON.stringify({ cachedAt: Date.now(), state })
    );
  } catch {
    // Cache writes are best-effort; the server remains authoritative.
  }
};

const mergeLordRuntimeSummaryState = <T extends LordHomeBackendState>(
  current: T | null,
  summary: LordHomeBackendState
): T => ({
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

const lordHomeSeedRecruitOffers: Record<string, LordHomeRecruitOffer> = {
  unit_infantry_t1: {
    offerId: "offer_north_infantry",
    cardId: "unit_infantry_t1",
    status: "available",
    cost: 1,
    rate: 24,
    stock: 0
  }
};

const lordHomeRuntimeRecruitOffers: Record<string, LordHomeRecruitOffer> = {};

const clampRecruitQty = (value: number, max: number) => {
  if (max < 1) return 0;
  return Math.max(1, Math.min(max, Math.round(value)));
};

const mergeLordHomeStackList = (stacks: LordHomeStack[], sourceIndex: number, targetIndex: number) => {
  const sourceStack = stacks[sourceIndex];
  const targetStack = stacks[targetIndex];
  if (!sourceStack || !targetStack || sourceIndex === targetIndex || sourceStack.unitId !== targetStack.unitId) {
    return stacks;
  }

  const nextStacks = stacks.map((stack) => ({ ...stack }));
  nextStacks[targetIndex] = {
    ...targetStack,
    count: targetStack.count + sourceStack.count
  };
  nextStacks.splice(sourceIndex, 1);
  return nextStacks;
};

const lordHomeRecruitStatusRank = (status: string) => {
  if (status === "held") return 3;
  if (status === "available") return 2;
  return 1;
};

const isLordHomeRecruitOfferUsable = (status: string) => status === "available" || status === "held";

const lordHomeActionDock = [
  { id: "buildings", label: "Здания", icon: lordHomeActionBuildingsIcon, tone: "gold" },
  { id: "map", label: "Карта", icon: lordHomeActionMapIcon, tone: "blue" },
  { id: "orders", label: "Заказы", icon: lordHomeActionOrdersIcon, tone: "green" },
  { id: "raids", label: "Рейды", icon: lordHomeActionRaidsIcon, tone: "red" },
  { id: "battle", label: "Бой", icon: lordHomeActionBattleIcon, tone: "red", alert: true }
] as const;

type LordHomeView = "territory" | "buildings" | "orders" | "raids";
type LordHomePanel = "map" | "orders" | "raids" | "help";
type LordBuildingBranch = "military" | "economy" | "order" | "magic";
type LordBuildingState = "built" | "available" | "locked";

type LordHomeOrderStatus =
  | "draft"
  | "published"
  | "addressed_pending"
  | "accepted"
  | "in_progress"
  | "claimed_at_prop"
  | "submitted_pending_sync"
  | "pending_master_approval"
  | "completed"
  | "failed_retryable"
  | "failed_closed"
  | "cancelled_by_lord"
  | "expired"
  | "contested_review";

type LordHomeOrderVisibility = "public" | "addressed";

type LordHomeOrder = {
  order_id: string;
  visibility?: LordHomeOrderVisibility | string;
  visibility_label?: string;
  status?: LordHomeOrderStatus | string;
  status_label?: string;
  visible_hook?: string;
  object_id?: string | null;
  object_label?: string;
  location_id?: string | null;
  location_label?: string;
  target_player_id?: string | null;
  target_player_label?: string;
  executor_label?: string;
  reward_label?: string;
  reward_gold?: number;
  escrow_label?: string;
  escrow_reward_id?: string | null;
  target_act_id?: string | null;
  expires_at?: string | null;
  conflict_badge?: { label?: string; tone?: string } | null;
};

type LordHomeOrderCap = {
  public_active?: number;
  public_limit?: number;
  addressed_active?: number;
  addressed_limit?: number;
};

type LordHomeOrderEscrow = {
  locked_gold?: number;
  locked_assets?: unknown[];
  locked_asset_count?: number;
  available_gold?: number;
};

type LordHomeOrderTarget = {
  target_id: string;
  target_type?: string;
  target_type_label?: string;
  label?: string;
  location_id?: string | null;
  location_label?: string;
  suggested_payment_gold?: number;
  source?: string;
};

type LordHomeOrderRecipient = {
  player_id: string;
  display_name?: string;
  role_label?: string;
};

type LordHomeOrderConflict = {
  conflict_id?: string;
  object_id?: string;
  object_label?: string;
  status?: string;
  badge_label?: string;
  own_order_ids?: string[];
  competing_order_count?: number;
  competing_lord_count?: number;
};

type LordHomeRaidEffect = {
  raid_effect_id?: string;
  rule_id?: string;
  source_domain_id?: string;
  target_domain_id?: string;
  target_territory_id?: string;
  status?: string;
  effect_type?: string;
  started_at?: string;
  expires_at?: string;
  expired_at?: string;
  resisted?: boolean;
  blocked?: boolean;
  loot_applied?: boolean;
  loot_gold?: number;
  target_raid_tokens_lost?: number;
  resistance_outcome?: string;
  effect_multiplier?: number;
  visibility?: string;
  counterplay?: string;
  result_label?: string;
};

type LordHomeRaidRule = {
  rule_id: string;
  name: string;
  tier: number;
  category: string;
  category_label?: string;
  description: string;
  base_token_cost?: number;
  token_cost: number;
  token_surcharge?: number;
  gold_cost: number;
  duration_minutes: number;
  effect_type: string;
  allowed_target_types: string[];
  required_building_ids: string[];
  required_building_labels?: string[];
  visibility: string;
  counterplay: string;
  locked_reason?: string | null;
  x?: number;
  y?: number;
};

type LordHomeRaidTarget = {
  target_territory_id: string;
  name: string;
  owner_domain_id?: string | null;
  owner_label?: string;
  tier?: number;
  bonus_type?: string;
  bonus_label?: string;
  is_residence?: boolean;
  is_raid_only?: boolean;
  active_effects?: LordHomeRaidEffect[];
  raid_resistance_label?: string;
  visibility_level?: string;
  raid_defense_score?: number | null;
  garrison_power?: number | null;
  risk_label?: string;
  has_wards?: boolean | null;
  active_army_present?: boolean | null;
  can_target?: boolean;
  disabled_reason?: string;
};

type LordHomeRaidResponse = {
  status?: string;
  started?: boolean;
  resisted?: boolean;
  loot_applied?: boolean;
  validation_error?: string | null;
  needs_master_review?: boolean;
  raid_tokens?: number;
  gold?: number;
  active_raid_effects?: LordHomeRaidEffect[];
  audit_event_id?: number;
  token_spent?: number;
  gold_spent?: number;
};

type LordHomeOrderCreatePayload = {
  visibility: LordHomeOrderVisibility;
  target_player_id?: string;
  object_id?: string;
  visible_hook?: string;
  reward: { reward_id?: string; gold?: number };
  source: string;
};

type LordHomeRaidStartPayload = {
  target_territory_id: string;
  rule_id: string;
  expected_token_cost: number;
  expected_gold_cost?: number;
  source: string;
};

type LordBuildingNode = {
  id: string;
  branch: LordBuildingBranch;
  name: string;
  tier: number;
  goldCost: number;
  prerequisiteIds: string[];
  recruitUnlockIds: string[];
  capacityDelta: number;
  raidUnlock: boolean;
  x: number;
  y: number;
  effect: string;
  effectLabels?: string[];
  serverState?: LordBuildingState;
  missingPrerequisiteIds?: string[];
};

const lordBuildingBranchMeta = {
  military: { label: "Военная ветка", tone: "red", icon: Shield },
  economy: { label: "Экономика", tone: "gold", icon: Coins },
  order: { label: "Приказы", tone: "green", icon: ScrollText },
  magic: { label: "Магия", tone: "violet", icon: Sparkles }
} as const;

const lordHomeRaidCategoryMeta = {
  economy: { label: "Экономика", tone: "gold", icon: Coins },
  military: { label: "Военная диверсия", tone: "red", icon: Shield },
  recruit: { label: "Саботаж найма", tone: "green", icon: Users },
  intrigue: { label: "Интрига", tone: "violet", icon: EyeOff },
  loot: { label: "Налет за добычей", tone: "blue", icon: Package },
  residence: { label: "Рейд резиденции", tone: "red", icon: Castle }
} as const;

const lordHomeRaidEffectLabels: Record<string, string> = {
  income_down: "снижает доход цели",
  defense_down: "ослабляет оборону и дозор",
  recruit_block: "останавливает накопление найма",
  order_visibility_disrupt: "путает заказы и скрывает следы",
  loot_once: "разовая добыча: золото, карта или влияние",
  residence_pressure: "давление на резиденцию без захвата"
};

const lordHomeRaidVisibilityLabels: Record<string, string> = {
  source_target_and_masters: "видят вы, цель и мастера",
  visible_to_target: "цель видит помеху",
  source_and_masters: "видят вы и мастера"
};

const lordHomeRaidCounterplayLabels: Record<string, string> = {
  garrison_or_ward_reduces_effect: "гарнизон или оберег снижает эффект",
  owner_can_clear_with_order_or_ward: "владелец может снять заказом или оберегом",
  scrying_or_master_review_reveals: "Комната видений или мастерский разбор раскрывает след",
  loot_requires_master_audit_if_rare: "редкая добыча уходит в мастерский аудит",
  wards_or_ritual_chamber_can_block: "Обереги или ритуальная палата могут заблокировать"
};

const lordHomeRaidTargetNameLabels: Record<string, string> = {
  "River Residence": "Речная резиденция",
  "Forest Residence": "Лесная резиденция",
  "Hill Residence": "Холмовая резиденция",
  "North Residence": "Северная резиденция",
  "East Fort": "Северная застава",
  "West Fort": "Западный острог",
  "Oat Fields": "Северные овсы",
  "Barn Village": "Сенной посад",
  "Well City": "Колодезный торг",
  "Magic Corner": "Чародейский угол",
  "Science Barn": "Двухъярусная мануфактура",
  "Dark Forest": "Травничья роща",
  "Mist Lake": "Зеркальный пруд",
  "Black Swamp": "Черная топь",
  "Gray Mountain": "Серый дозор"
};

const lordHomeRaidOwnerLabels: Record<string, string> = {
  "River Gate": "Речные ворота",
  "Forest March": "Лесная марка",
  "Hill Crown": "Холмовая корона",
  "North Watch": "Северный дозор"
};

const lordHomeRaidBonusLabels: Record<string, string> = {
  home: "резиденция",
  orders: "заказы",
  defense: "оборона",
  gold: "доход",
  recruit: "найм",
  resource: "ресурсы",
  magic: "магия",
  research: "исследование",
  monster: "монстры",
  alchemy: "алхимия",
  "rare metal": "редкий металл"
};

const lordHomeFallbackRaidRules: LordHomeRaidRule[] = [
  {
    rule_id: "raid_income_sabotage",
    name: "Сжечь книги податей",
    tier: 1,
    category: "economy",
    category_label: "Экономика",
    description: "Тихая вылазка по складам и книгам сборщиков снижает доход цели.",
    token_cost: 1,
    gold_cost: 0,
    duration_minutes: 30,
    effect_type: "income_down",
    allowed_target_types: ["territory"],
    required_building_ids: ["b_raid_office"],
    required_building_labels: ["Рейдовая ставка"],
    visibility: "Цель видит следы после применения",
    counterplay: "Гарнизон или обереги снижают эффект",
    locked_reason: null
  },
  {
    rule_id: "raid_garrison_diversion",
    name: "Ночная диверсия",
    tier: 1,
    category: "military",
    category_label: "Военная диверсия",
    description: "Отряд режет сигнальные веревки и ослабляет дозор.",
    token_cost: 1,
    gold_cost: 0,
    duration_minutes: 60,
    effect_type: "defense_down",
    allowed_target_types: ["territory"],
    required_building_ids: ["b_raid_office"],
    required_building_labels: ["Рейдовая ставка"],
    visibility: "Источник и цель видят итог",
    counterplay: "Сильный гарнизон может погасить удар",
    locked_reason: null
  },
  {
    rule_id: "raid_recruit_sabotage",
    name: "Сорвать вербовку",
    tier: 2,
    category: "recruit",
    category_label: "Саботаж найма",
    description: "Ложные приказы на время останавливают приток рекрутов.",
    token_cost: 1,
    gold_cost: 0,
    duration_minutes: 45,
    effect_type: "recruit_block",
    allowed_target_types: ["territory"],
    required_building_ids: ["b_raid_office"],
    required_building_labels: ["Рейдовая ставка"],
    visibility: "Цель видит блокировку найма",
    counterplay: "Заказ или оберег может снять помеху",
    locked_reason: null
  },
  {
    rule_id: "raid_order_intrigue",
    name: "Черная печать",
    tier: 2,
    category: "intrigue",
    category_label: "Интрига",
    description: "Фальшивая печать путает доску объявлений и видимость следов.",
    token_cost: 1,
    gold_cost: 0,
    duration_minutes: 45,
    effect_type: "order_visibility_disrupt",
    allowed_target_types: ["territory"],
    required_building_ids: ["b_war_council"],
    required_building_labels: ["Военный совет"],
    visibility: "Часть деталей скрыта без разведки",
    counterplay: "Комната видений или мастерский разбор раскрывает след",
    locked_reason: "Нужно построить: Военный совет"
  },
  {
    rule_id: "raid_loot_run",
    name: "Налет за добычей",
    tier: 2,
    category: "loot",
    category_label: "Налет за добычей",
    description: "Быстрый налет не удерживает землю но может принести добычу.",
    token_cost: 2,
    gold_cost: 0,
    duration_minutes: 0,
    effect_type: "loot_once",
    allowed_target_types: ["territory"],
    required_building_ids: ["b_raid_office"],
    required_building_labels: ["Рейдовая ставка"],
    visibility: "Добычу видят источник и мастера",
    counterplay: "Редкая добыча уходит в мастерский аудит",
    locked_reason: null
  },
  {
    rule_id: "raid_residence_mark",
    name: "Метка на воротах",
    tier: 3,
    category: "residence",
    category_label: "Рейд резиденции",
    description: "Поздний знак на воротах приносит добычу или дебафф без захвата.",
    token_cost: 2,
    gold_cost: 0,
    duration_minutes: 60,
    effect_type: "residence_pressure",
    allowed_target_types: ["residence"],
    required_building_ids: ["b_war_council", "b_scrying_room"],
    required_building_labels: ["Военный совет", "Комната видений"],
    visibility: "Источник и цель видят итог",
    counterplay: "Обереги или ритуальная палата могут заблокировать",
    locked_reason: "Нужно построить: Военный совет, Комната видений"
  }
];

const lordHomeFallbackRaidTargets: LordHomeRaidTarget[] = [
  {
    target_territory_id: "territory_fort_east",
    name: "Северная застава",
    owner_domain_id: "domain_river",
    owner_label: "Речные ворота",
    tier: 2,
    bonus_type: "defense",
    bonus_label: "оборона",
    is_residence: false,
    is_raid_only: false,
    active_effects: [],
    raid_resistance_label: "детали скрыты",
    visibility_level: "hidden_details",
    can_target: true
  },
  {
    target_territory_id: "territory_field_east_large",
    name: "Правые пашни",
    owner_domain_id: "domain_forest",
    owner_label: "Лесная марка",
    tier: 1,
    bonus_type: "recruit",
    bonus_label: "найм",
    is_residence: false,
    is_raid_only: false,
    active_effects: [{ rule_id: "raid_income_sabotage", status: "active", result_label: "Доход уже горит", expires_at: "через 18 мин." }],
    raid_resistance_label: "детали скрыты",
    visibility_level: "hidden_details",
    can_target: true
  },
  {
    target_territory_id: "territory_res_river",
    name: "Речная резиденция",
    owner_domain_id: "domain_river",
    owner_label: "Речные ворота",
    tier: 1,
    bonus_type: "residence",
    bonus_label: "резиденция",
    is_residence: true,
    is_raid_only: true,
    active_effects: [],
    raid_resistance_label: "обереги не раскрыты",
    visibility_level: "hidden_details",
    can_target: true
  },
  {
    target_territory_id: "territory_res_north",
    name: "Северная резиденция",
    owner_domain_id: "domain_north",
    owner_label: "Северный дозор",
    tier: 1,
    bonus_type: "residence",
    bonus_label: "резиденция",
    is_residence: true,
    is_raid_only: true,
    active_effects: [],
    raid_resistance_label: "свои укрепления",
    visibility_level: "owner_full",
    can_target: false,
    disabled_reason: "Своя резиденция не цель рейда"
  }
];


const lordBuildingIconById: Partial<Record<string, string>> = {
  b_training_yard: buildingTrainingYardIcon,
  b_barracks: buildingBarracksIcon,
  b_archery_range: buildingArcheryRangeIcon,
  b_stables: buildingStablesIcon,
  b_siege_yard: buildingSiegeYardIcon,
  b_war_academy: buildingWarAcademyIcon,
  b_market: buildingMarketIcon,
  b_tax_office: buildingTaxOfficeIcon,
  b_storehouse: buildingStorehouseIcon,
  b_bank: buildingBankIcon,
  b_treasury_hall: buildingTreasuryHallIcon,
  b_notice_board: buildingNoticeBoardIcon,
  b_envoy_hall: buildingEnvoyHallIcon,
  b_map_room: buildingMapRoomIcon,
  b_raid_office: buildingRaidOfficeIcon,
  b_war_council: buildingWarCouncilIcon,
  b_mage_study: buildingMageStudyIcon,
  b_alchemy_lab: buildingAlchemyLabIcon,
  b_scrying_room: buildingScryingRoomIcon,
  b_wards: buildingWardsIcon,
  b_ritual_chamber: buildingRitualChamberIcon
};

const lordBuildingInitialBuiltIds = [
  "b_training_yard",
  "b_market",
  "b_notice_board",
  "b_mage_study",
  "b_barracks",
  "b_tax_office",
  "b_envoy_hall"
] as const;

const lordBuildingRuntimeInitialBuiltIds: readonly string[] = [];

const lordBuildingTreeNodes: LordBuildingNode[] = [
  {
    id: "b_training_yard",
    branch: "military",
    name: "Учебный двор",
    tier: 1,
    goldCost: 40,
    prerequisiteIds: [],
    recruitUnlockIds: ["unit_infantry_t1"],
    capacityDelta: 1,
    raidUnlock: false,
    x: 53.0,
    y: 67.4,
    effect: "Открывает найм мечников и повышает максимум активной армии на 1."
  },
  {
    id: "b_barracks",
    branch: "military",
    name: "Казармы",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_training_yard"],
    recruitUnlockIds: ["unit_guard_t1"],
    capacityDelta: 0,
    raidUnlock: false,
    x: 56.0,
    y: 56.4,
    effect: "Открывает найм стражи."
  },
  {
    id: "b_archery_range",
    branch: "military",
    name: "Стрельбище",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_training_yard"],
    recruitUnlockIds: ["unit_ranged_t1"],
    capacityDelta: 0,
    raidUnlock: false,
    x: 50.2,
    y: 56.4,
    effect: "Открывает найм лучников."
  },
  {
    id: "b_stables",
    branch: "military",
    name: "Конюшни",
    tier: 3,
    goldCost: 120,
    prerequisiteIds: ["b_barracks"],
    recruitUnlockIds: ["unit_cavalry_t2"],
    capacityDelta: 1,
    raidUnlock: false,
    x: 56.0,
    y: 44.8,
    effect: "Открывает найм кавалерии и повышает максимум активной армии на 1."
  },
  {
    id: "b_siege_yard",
    branch: "military",
    name: "Осадный двор",
    tier: 3,
    goldCost: 120,
    prerequisiteIds: ["b_archery_range"],
    recruitUnlockIds: ["unit_heavy_siege_t3"],
    capacityDelta: 0,
    raidUnlock: false,
    x: 50.2,
    y: 44.8,
    effect: "Открывает найм осадников."
  },
  {
    id: "b_war_academy",
    branch: "military",
    name: "Военная академия",
    tier: 4,
    goldCost: 180,
    prerequisiteIds: ["b_siege_yard", "b_war_council"],
    recruitUnlockIds: ["unit_specialist_t3"],
    capacityDelta: 1,
    raidUnlock: true,
    x: 50.2,
    y: 13.2,
    effect: "Открывает найм инженеров, повышает максимум активной армии на 1 и кап рейдовых жетонов на 2."
  },
  {
    id: "b_market",
    branch: "economy",
    name: "Рынок",
    tier: 1,
    goldCost: 40,
    prerequisiteIds: [],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 28.6,
    y: 67.4,
    effect: "Добавляет +5 золота к каждому доходному тику."
  },
  {
    id: "b_tax_office",
    branch: "economy",
    name: "Налоговая палата",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_market"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 25.4,
    y: 56.4,
    effect: "Повышает доход с контролируемых территорий на 25%."
  },
  {
    id: "b_storehouse",
    branch: "economy",
    name: "Склад",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_market"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 32.0,
    y: 56.4,
    effect: "Увеличивает лимит накопления всех уже открытых войск на 25%."
  },
  {
    id: "b_bank",
    branch: "economy",
    name: "Банк",
    tier: 3,
    goldCost: 120,
    prerequisiteIds: ["b_tax_office", "b_storehouse"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 32.0,
    y: 44.8,
    effect: "Добавляет +10 золота к доходному тику и снижает кражу золота рейдом Налет за добычей на 50%."
  },
  {
    id: "b_treasury_hall",
    branch: "economy",
    name: "Казначейский зал",
    tier: 4,
    goldCost: 180,
    prerequisiteIds: ["b_bank"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 32.0,
    y: 30.0,
    effect: "Добавляет +20 золота к доходному тику и не дает итоговому доходу упасть ниже 50% от дохода до штрафов."
  },
  {
    id: "b_notice_board",
    branch: "order",
    name: "Доска объявлений",
    tier: 1,
    goldCost: 40,
    prerequisiteIds: [],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 66.4,
    y: 67.4,
    effect: "Открывает публичные заказы и лимит 2 активных публичных заказов."
  },
  {
    id: "b_envoy_hall",
    branch: "order",
    name: "Посольский зал",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_notice_board"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 69.5,
    y: 56.4,
    effect: "Открывает адресные заказы и лимит 1 активного адресного заказа."
  },
  {
    id: "b_map_room",
    branch: "order",
    name: "Картографическая",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_notice_board"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 63.8,
    y: 56.4,
    effect: "Открывает список целей рейда и показывает общий риск защиты цели."
  },
  {
    id: "b_raid_office",
    branch: "order",
    name: "Рейдовая ставка",
    tier: 3,
    goldCost: 120,
    prerequisiteIds: ["b_map_room", "b_stables"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: true,
    x: 63.8,
    y: 44.8,
    effect: "Повышает кап рейдовых жетонов на 2 и открывает территориальные рейды."
  },
  {
    id: "b_war_council",
    branch: "order",
    name: "Военный совет",
    tier: 4,
    goldCost: 180,
    prerequisiteIds: ["b_raid_office", "b_envoy_hall"],
    recruitUnlockIds: [],
    capacityDelta: 1,
    raidUnlock: true,
    x: 63.8,
    y: 30.0,
    effect: "Повышает максимум активной армии на 1, кап рейдовых жетонов на 1 и открывает Черную печать."
  },
  {
    id: "b_mage_study",
    branch: "magic",
    name: "Кабинет мага",
    tier: 1,
    goldCost: 40,
    prerequisiteIds: [],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 40.6,
    y: 67.4,
    effect: "Добавляет +1 к защите резиденции от рейдов."
  },
  {
    id: "b_alchemy_lab",
    branch: "magic",
    name: "Алхимическая лаборатория",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_mage_study"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 37.5,
    y: 56.4,
    effect: "Сокращает длительность входящих активных рейд-эффектов на 15 минут, но не сокращает мгновенный лут."
  },
  {
    id: "b_scrying_room",
    branch: "magic",
    name: "Комната видений",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_mage_study"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 43.8,
    y: 56.4,
    effect: "Показывает точную защиту цели, силу гарнизона, обереги и активную армию."
  },
  {
    id: "b_wards",
    branch: "magic",
    name: "Обереги",
    tier: 3,
    goldCost: 120,
    prerequisiteIds: ["b_scrying_room", "b_alchemy_lab"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 43.8,
    y: 44.8,
    effect: "Добавляет +1 к защите обычных территорий и +2 к защите резиденции от рейдов."
  },
  {
    id: "b_ritual_chamber",
    branch: "magic",
    name: "Ритуальная палата",
    tier: 4,
    goldCost: 180,
    prerequisiteIds: ["b_wards", "b_treasury_hall"],
    recruitUnlockIds: [],
    capacityDelta: 0,
    raidUnlock: false,
    x: 40.6,
    y: 13.2,
    effect: "Раз в доходный тик дает 1 заряд очищения, который снимает активный рейд-эффект с владений дома."
  }
];

const lordBuildingKnownIds = new Set(lordBuildingTreeNodes.map((building) => building.id));

const getLordHomeIdList = (value: unknown): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  return String(value)
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const getLordHomeNumber = (value: unknown, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const getLordHomeBoolean = (value: unknown, fallback: boolean) => {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes", "y"].includes(normalized)) return true;
    if (["false", "0", "no", "n", ""].includes(normalized)) return false;
  }
  return fallback;
};

const normalizeLordBuildingState = (status: string | undefined): LordBuildingState | undefined => {
  if (["built", "owned", "purchased"].includes(status ?? "")) return "built";
  if (status === "available") return "available";
  if (status?.startsWith("locked") || status === "blocked") return "locked";
  return undefined;
};

const mergeLordBuildingNode = (
  layoutNode: LordBuildingNode,
  backendNode: LordHomeBackendBuilding | undefined
): LordBuildingNode => {
  if (!backendNode) return layoutNode;
  const effectLabels = Array.isArray(backendNode.effect_labels)
    ? backendNode.effect_labels.map((label) => String(label).trim()).filter(Boolean)
    : [];
  return {
    ...layoutNode,
    branch: (backendNode.branch && backendNode.branch in lordBuildingBranchMeta
      ? backendNode.branch
      : layoutNode.branch) as LordBuildingBranch,
    name: backendNode.name || layoutNode.name,
    tier: getLordHomeNumber(backendNode.tier, layoutNode.tier),
    goldCost: getLordHomeNumber(backendNode.gold_cost, layoutNode.goldCost),
    prerequisiteIds: getLordHomeIdList(backendNode.prerequisite_ids).length
      ? getLordHomeIdList(backendNode.prerequisite_ids)
      : layoutNode.prerequisiteIds,
    recruitUnlockIds: getLordHomeIdList(backendNode.recruit_unlock_ids).length
      ? getLordHomeIdList(backendNode.recruit_unlock_ids)
      : layoutNode.recruitUnlockIds,
    capacityDelta: getLordHomeNumber(backendNode.capacity_delta, layoutNode.capacityDelta),
    raidUnlock: getLordHomeBoolean(backendNode.raid_unlock, layoutNode.raidUnlock),
    effect: effectLabels.length ? effectLabels.join(". ") : layoutNode.effect,
    effectLabels,
    serverState: normalizeLordBuildingState(backendNode.status),
    missingPrerequisiteIds: getLordHomeIdList(backendNode.missing_prerequisite_ids)
  };
};

const getLordBuildingNodesFromBackend = (
  backendNodes: LordHomeBackendBuilding[] | undefined,
  visibleBuildingIds?: Set<string> | null
) => {
  const backendById = new globalThis.Map(
    (backendNodes ?? [])
      .filter((building) => building.building_id && lordBuildingKnownIds.has(building.building_id))
      .map((building) => [building.building_id as string, building])
  );
  const visibleIds =
    backendById.size > 0
      ? new Set(backendById.keys())
      : visibleBuildingIds;
  return lordBuildingTreeNodes
    .filter((building) => !visibleIds || visibleIds.has(building.id))
    .map((building) => mergeLordBuildingNode(building, backendById.get(building.id)));
};

const getLordBuiltBuildingIdsFromNodes = (nodes: LordBuildingNode[]) =>
  new Set(
    nodes
      .filter((building) => getLordBuildingState(building, new Set()) === "built")
      .map((building) => building.id)
  );

const getLordHomeBuiltBuildingIdsFromBackendState = (state: LordHomeBackendState): Set<string> | null => {
  const hasAuthoritativeBuildings = Array.isArray(state.building_catalog) || Array.isArray(state.owned_buildings);
  if (!hasAuthoritativeBuildings) {
    return null;
  }

  const nextBuiltIds = new Set<string>();
  for (const building of state.owned_buildings ?? []) {
    const buildingId = building.building_id;
    if (buildingId && lordBuildingKnownIds.has(buildingId)) {
      nextBuiltIds.add(buildingId);
    }
  }

  for (const building of state.building_catalog ?? []) {
    const buildingId = building.building_id;
    if (
      buildingId &&
      lordBuildingKnownIds.has(buildingId) &&
      ["owned", "built", "purchased"].includes(building.status ?? "")
    ) {
      nextBuiltIds.add(buildingId);
    }
  }

  return nextBuiltIds;
};

const isLordHomeRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const lordHomeApiErrorLabelByCode: Record<string, string> = {
  building_already_owned: "Постройка уже возведена",
  building_not_found: "Постройка недоступна",
  building_not_in_territory_tree: "Постройка недоступна в выбранной территории",
  missing_building_territory: "Не выбрано владение для строительства",
  insufficient_gold: "Недостаточно золота",
  missing_prerequisites: "Сначала нужны предыдущие постройки",
  invalid_count: "Количество должно быть больше нуля",
  insufficient_stock: "Нет накопленного найма для этого отряда",
  garrison_capacity_full: "В гарнизоне нет свободного слота",
  missing_offer: "Предложение найма не выбрано",
  missing_territory_id: "Территория найма не выбрана",
  offer_not_available: "Предложение найма уже недоступно",
  offer_held: "Предложение удерживает другой дом",
  offer_not_found: "Предложение найма не найдено",
  territory_not_owned: "Эта территория не под контролем дома",
  territory_contested: "Спорная территория не принимает новобранцев",
  fort_capacity_exceeded: "В гарнизоне не хватает места",
  army_capacity_exceeded: "В армии не хватает места",
  insufficient_garrison: "В гарнизоне нет такой пачки",
  stack_cannot_split: "Эту пачку нельзя разделить",
  invalid_split_count: "Нужно оставить бойцов в обеих пачках",
  merge_same_stack: "Выберите другую пачку",
  merge_unit_mismatch: "Складывать можно только одинаковые пачки",
  missing_stack_id: "Пачка не выбрана",
  active_stack_not_found: "Пачка армии не найдена",
  garrison_stack_not_found: "Пачка гарнизона не найдена",
  missing_active_army: "Нужна армия героя на этой территории",
  army_not_at_territory: "Армия героя в другой локации",
  pending_move_active: "Армия в пути",
  already_at_target: "Армия уже здесь",
  forbidden_residence_target: "В чужую резиденцию ход закрыт",
  insufficient_mp: "Недостаточно MP",
  invalid_route: "Маршрут недоступен",
  map_node_not_found: "Цель пути сейчас недоступна",
  missing_route: "Цель похода не выбрана",
  no_route: "Нет открытой дороги",
  route_cost_mismatch: "Стоимость пути изменилась",
  route_stopped_at_front: "Поход остановится на первом рубеже",
  territory_node_not_found: "У этой земли нет точки на карте",
  order_cap_exceeded: "Лимит активных заказов занят",
  insufficient_escrow_gold: "В казне не хватает награды",
  reward_asset_locked: "Эта награда уже под замком",
  order_object_conflict: "За этот объект уже идет поручение",
  final_lock_orders_closed: "Финал закрыл новые заказы",
  invalid_addressed_target: "Адресат недоступен для заказа",
  order_already_in_progress: "Заказ уже в работе или закрыт",
  unknown_order_object: "Цель заказа сейчас недоступна",
  insufficient_raid_tokens: "Нет рейдового жетона",
  recruit_blocked_by_raid: "Найм в эту территорию заблокирован рейдом",
  rule_locked: "Рейд закрыт постройками",
  invalid_target: "Цель не подходит для этого рейда",
  duplicate_active_effect: "Цель уже под таким эффектом",
  stale_expected_cost: "Стоимость изменилась, обновите экран",
  final_lock: "Финал закрыл новые рейды",
  raid_rule_not_found: "План рейда недоступен",
  territory_not_found: "Цель рейда недоступна"
};

const getLordHomeApiErrorMessage = (payload: unknown, fallback: string) =>
  getLordApiErrorMessage(payload, fallback);

const getLordHomeCaughtErrorMessage = (error: unknown, fallback: string) =>
  getLordClientErrorMessage(error, fallback);

const normalizeStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return value.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
};

const getLordHomeRaidCategoryMeta = (category: string) =>
  lordHomeRaidCategoryMeta[category as keyof typeof lordHomeRaidCategoryMeta] ??
  lordHomeRaidCategoryMeta.economy;

const getLordHomeRaidTechnicalLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();

const getLordHomeRaidReadableValue = (value: string | undefined, labels: Record<string, string>) => {
  const normalized = String(value ?? "").trim();
  if (!normalized) return "";
  return labels[normalized] ?? getLordHomeRaidTechnicalLabel(normalized);
};

const getLordHomeRaidEffectLabel = (effectType: string | undefined) =>
  getLordHomeRaidReadableValue(effectType, lordHomeRaidEffectLabels) || "временный эффект";

const formatLordHomeRaidDuration = (minutes: number) =>
  minutes > 0 ? `${minutes} минут` : "сразу";

const getLordHomeRaidVisibilityLabel = (visibility: string | undefined) =>
  getLordHomeRaidReadableValue(visibility, lordHomeRaidVisibilityLabels) || "по правилам видимости";

const getLordHomeRaidCounterplayLabel = (counterplay: string | undefined) =>
  getLordHomeRaidReadableValue(counterplay, lordHomeRaidCounterplayLabels) || "защита цели проверяется сервером";

const isLordHomeRaidTechnicalName = (name: string | undefined) => {
  const normalized = String(name ?? "").trim().toLowerCase();
  return !normalized || normalized === "raid default" || normalized === "raid_default" || normalized === "default";
};

const getLordHomeRaidFallbackRule = (rule: LordHomeRaidRule, index: number) =>
  lordHomeFallbackRaidRules.find((fallback) => fallback.rule_id === rule.rule_id) ??
  lordHomeFallbackRaidRules.find((fallback) => fallback.effect_type === rule.effect_type) ??
  lordHomeFallbackRaidRules.find((fallback) => fallback.category === rule.category) ??
  lordHomeFallbackRaidRules[index % lordHomeFallbackRaidRules.length];

const normalizeLordHomeRaidRule = (rule: LordHomeRaidRule, index: number): LordHomeRaidRule => {
  const fallback = getLordHomeRaidFallbackRule(rule, index);
  const category = rule.category || fallback.category;
  const name = isLordHomeRaidTechnicalName(rule.name) ? fallback.name : rule.name;
  return {
    ...fallback,
    ...rule,
    rule_id: rule.rule_id || fallback.rule_id,
    name: name || fallback.name,
    tier: Number(rule.tier ?? fallback.tier) || fallback.tier,
    category,
    category_label: rule.category_label || getLordHomeRaidCategoryMeta(category).label,
    description: rule.description || fallback.description,
    base_token_cost: Number(rule.base_token_cost ?? fallback.base_token_cost ?? rule.token_cost ?? fallback.token_cost) || 0,
    token_cost: Number(rule.token_cost ?? fallback.token_cost) || 0,
    token_surcharge: Number(rule.token_surcharge ?? fallback.token_surcharge ?? 0) || 0,
    gold_cost: 0,
    duration_minutes: Number(rule.duration_minutes ?? fallback.duration_minutes) || 0,
    effect_type: rule.effect_type || fallback.effect_type,
    allowed_target_types: normalizeStringArray(rule.allowed_target_types).length
      ? normalizeStringArray(rule.allowed_target_types)
      : fallback.allowed_target_types,
    required_building_ids: normalizeStringArray(rule.required_building_ids),
    required_building_labels: normalizeStringArray(rule.required_building_labels),
    visibility: rule.visibility || fallback.visibility,
    counterplay: rule.counterplay || fallback.counterplay,
    locked_reason: rule.locked_reason ?? null
  };
};

const normalizeLordHomeRaidTarget = (target: LordHomeRaidTarget): LordHomeRaidTarget => ({
  ...target,
  name: lordHomeRaidTargetNameLabels[target.name] ?? target.name,
  tier: Number(target.tier ?? 1) || 1,
  owner_label: lordHomeRaidOwnerLabels[target.owner_label ?? ""] ?? target.owner_label ?? target.owner_domain_id ?? "ничья",
  bonus_label: lordHomeRaidBonusLabels[target.bonus_label ?? ""] ?? lordHomeRaidBonusLabels[target.bonus_type ?? ""] ?? target.bonus_label ?? target.bonus_type ?? "земля",
  active_effects: target.active_effects ?? [],
  can_target: target.can_target !== false
});

const isLordHomeRaidTargetCompatible = (rule: LordHomeRaidRule, target: LordHomeRaidTarget | null) => {
  if (!target) return false;
  const allowed = new Set(rule.allowed_target_types);
  if (target.is_residence) {
    return allowed.has("residence") || (Boolean(target.is_raid_only) && allowed.has("b_raid_only"));
  }
  return allowed.has("territory") || allowed.has("contested") || (Boolean(target.is_raid_only) && allowed.has("b_raid_only"));
};

const getLordHomeRaidBlockReason = ({
  rule,
  target,
  raidTokens,
  activeEffects,
  isSubmitting
}: {
  rule: LordHomeRaidRule | null;
  target: LordHomeRaidTarget | null;
  raidTokens: number;
  activeEffects: LordHomeRaidEffect[];
  isSubmitting: boolean;
}) => {
  if (isSubmitting) return "Печать уже ставится";
  if (!rule) return "План рейда не выбран";
  if (!target) return "Цель рейда не выбрана";
  if (rule.locked_reason) return rule.locked_reason;
  if (raidTokens < rule.token_cost) return "Нет рейдового жетона";
  if (target.can_target === false) return target.disabled_reason || "Цель недоступна";
  if (!isLordHomeRaidTargetCompatible(rule, target)) return "Цель не подходит для этого плана";
  const duplicateTargetEffects = [
    ...(target.active_effects ?? []),
    ...activeEffects.filter((effect) => effect.target_territory_id === target.target_territory_id)
  ];
  if (duplicateTargetEffects.some((effect) => effect.rule_id === rule.rule_id || effect.effect_type === rule.effect_type)) {
    return "Цель уже под таким эффектом";
  }
  if (target.disabled_reason) return target.disabled_reason;
  return "";
};

const getLordHomeRaidExpiryLabel = (effects: LordHomeRaidEffect[]) => {
  const dated = effects
    .filter((effect) => effect.status === "active" && effect.expires_at)
    .map((effect) => ({ effect, time: Date.parse(String(effect.expires_at)) }))
    .filter((item) => Number.isFinite(item.time))
    .sort((a, b) => a.time - b.time);
  if (!dated.length) {
    const textual = effects.find((effect) => effect.status === "active" && effect.expires_at)?.expires_at;
    return textual ? String(textual) : "нет";
  }
  const deltaMs = dated[0].time - Date.now();
  if (deltaMs <= 0) return "истекает";
  return formatLordHomeTimerCountdown(deltaMs / 1000);
};

const getLordHomeActiveRaidSummary = (effects: LordHomeRaidEffect[]) => {
  const activeCount = effects.filter((effect) => effect.status === "active").length;
  if (!activeCount) return "";
  const expiryLabel = getLordHomeRaidExpiryLabel(effects);
  return expiryLabel === "нет" ? `${activeCount} активно` : `${activeCount} активно · ${expiryLabel}`;
};

const getLordHomeRaidResultText = (result: LordHomeRaidResponse) => {
  if (result.needs_master_review) return "Результат ушел мастеру";
  if (result.resisted) return "Цель выдержала удар";
  if (result.loot_applied) return "Добыча внесена в казну";
  if (result.started) return "Рейд начат";
  return result.status || "Приказ принят";
};

const lordHomeOrderFilters = [
  { id: "drafts", label: "Черновики", statuses: ["draft"] },
  { id: "open", label: "Открытые", statuses: ["published", "addressed_pending"] },
  { id: "taken", label: "Взяты", statuses: ["accepted", "in_progress", "claimed_at_prop", "submitted_pending_sync"] },
  { id: "review", label: "Ждут мастера", statuses: ["pending_master_approval", "contested_review", "failed_retryable"] },
  { id: "archive", label: "Архив", statuses: ["completed", "failed_closed", "cancelled_by_lord", "expired"] }
] as const;

type LordHomeOrderFilterId = (typeof lordHomeOrderFilters)[number]["id"];

const lordHomeCancellableOrderStatuses = new Set(["draft", "published", "addressed_pending", "accepted", "failed_retryable"]);

const getLordHomeOrderCap = (cap?: LordHomeOrderCap) => ({
  publicActive: Number(cap?.public_active ?? 0),
  publicLimit: Number(cap?.public_limit ?? 2),
  addressedActive: Number(cap?.addressed_active ?? 0),
  addressedLimit: Number(cap?.addressed_limit ?? 1)
});

const getLordHomeOrdersForFilter = (orders: LordHomeOrder[], filterId: LordHomeOrderFilterId) => {
  const filter = lordHomeOrderFilters.find((item) => item.id === filterId) ?? lordHomeOrderFilters[1];
  const statuses = new Set<string>(filter.statuses);
  return orders.filter((order) => statuses.has(String(order.status ?? "")));
};

const getLordHomeOrderDisplayTitle = (order: LordHomeOrder) => {
  const label = (order.visible_hook || order.object_label || "Заказ").trim();
  return label.replace(/^(Публичный|Адресный)\s+заказ:\s*/i, "").trim() || label;
};

const lordHomeOrderInterestTargetTypes = new Set(["artifact", "card", "treasure"]);

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const cleanLordHomeOrderInterestLabel = (label?: string | null, location?: string | null) => {
  const rawLabel = String(label ?? "").trim();
  const rawLocation = String(location ?? "").trim();
  if (!rawLabel) return "Объект интереса";

  let cleaned = rawLabel
    .replace(/^(Публичный|Адресный|Спорный)\s+заказ:\s*/i, "")
    .replace(/^(QR-сцена|Территория|Заказной объект):\s*/i, "")
    .trim();

  if (rawLocation && cleaned !== rawLocation) {
    cleaned = cleaned.replace(new RegExp(`\\s*\\(${escapeRegExp(rawLocation)}\\)\\s*$`, "i"), "").trim();
  }

  return cleaned || rawLabel;
};

const getLordHomeOrderInterestTargets = (targets: LordHomeOrderTarget[]) =>
  targets.filter((target) => lordHomeOrderInterestTargetTypes.has(String(target.target_type ?? "")));

const getLordHomeOrderInterestLabel = (order: LordHomeOrder) =>
  cleanLordHomeOrderInterestLabel(order.object_label || order.visible_hook, order.location_label);

const getLordHomeOrderTargetInterestLabel = (target?: LordHomeOrderTarget | null) =>
  cleanLordHomeOrderInterestLabel(target?.label, target?.location_label);

const getLordHomeOrderTargetOptionLabel = (target: LordHomeOrderTarget) => {
  const interestLabel = getLordHomeOrderTargetInterestLabel(target);
  const locationLabel = String(target.location_label ?? "").trim();
  const typeLabel = target.target_type === "card"
    ? "Карта"
    : target.target_type === "artifact"
      ? "Артефакт"
      : target.target_type === "treasure"
        ? "Сокровище"
        : "";
  const typedLabel = typeLabel && !interestLabel.toLowerCase().startsWith(typeLabel.toLowerCase())
    ? `${typeLabel}: ${interestLabel}`
    : interestLabel;

  if (!locationLabel || locationLabel === interestLabel || locationLabel === "предмет" || locationLabel === "артефакт") {
    return typedLabel;
  }

  return `${typedLabel} · ${locationLabel}`;
};

const getLordHomeOrderGeneratedHook = (target: LordHomeOrderTarget) =>
  `Вернуть лорду объект интереса: ${getLordHomeOrderTargetInterestLabel(target)}`;

const getLordHomeOrderWindowLabel = (order: LordHomeOrder) => {
  if (order.expires_at) {
    return order.expires_at;
  }
  const actMatch = String(order.target_act_id ?? "").match(/act_?(\d+)/i);
  return actMatch ? `Акт ${actMatch[1]}` : "Текущее окно";
};

const getLordHomeOrderGoldFromLabel = (label?: string | null) => {
  const match = String(label ?? "").match(/(\d+)\s*(?:g|золот)/i);
  return match ? Number(match[1]) : 0;
};

const parseLordHomeOrderGoldInput = (value: string) => {
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.floor(parsed));
};

const getLordHomeOrderDefaultPaymentGold = (availableGold: number, target?: LordHomeOrderTarget | null) => {
  if (availableGold <= 0) return "";
  const suggestedGold = Number(target?.suggested_payment_gold ?? 0);
  const defaultGold = suggestedGold > 0 ? suggestedGold : 15;
  return String(Math.min(defaultGold, Math.max(1, Math.floor(availableGold))));
};

const getLordHomeOrderGoldLabel = (gold: number) => (
  gold > 0 ? `${gold} золота` : "оплата не указана"
);

const getLordHomeOrderPaymentLabel = (order: LordHomeOrder) => {
  const gold = Number(order.reward_gold ?? 0) || getLordHomeOrderGoldFromLabel(order.reward_label);
  return getLordHomeOrderGoldLabel(gold);
};

const getLordHomeOrderEscrowLabel = (order?: LordHomeOrder | null) => {
  const label = order?.escrow_label || "";
  if (/^в escrow$/i.test(label)) return "В залоге";
  if (/^нет escrow$/i.test(label)) return "нет";
  return label || "нет";
};

const getLordHomeOrderConflict = (
  order: LordHomeOrder | null,
  conflicts: LordHomeOrderConflict[]
) => {
  if (!order) return null;
  return conflicts.find((conflict) => {
    const ownOrderIds = Array.isArray(conflict.own_order_ids) ? conflict.own_order_ids : [];
    return ownOrderIds.includes(order.order_id) || (
      Boolean(order.object_id) &&
      Boolean(conflict.object_id) &&
      String(conflict.object_id) === String(order.object_id)
    );
  }) ?? null;
};

const getLordHomeOrderAvailableGold = (escrow?: LordHomeOrderEscrow, lordGold = 0) => {
  const availableGold = Number(escrow?.available_gold);
  if (Number.isFinite(availableGold)) {
    return Math.max(0, availableGold);
  }
  return Math.max(0, lordGold - Number(escrow?.locked_gold ?? 0));
};

const canCancelLordHomeOrder = (order?: LordHomeOrder | null) =>
  Boolean(order?.order_id && lordHomeCancellableOrderStatuses.has(String(order.status ?? "")));

const getLordHomeOrderTone = (order?: LordHomeOrder | null) => {
  const status = String(order?.status ?? "");
  if (status === "contested_review" || order?.conflict_badge) return "review";
  if (status === "completed") return "done";
  if (["cancelled_by_lord", "expired", "failed_closed"].includes(status)) return "muted";
  if (["accepted", "in_progress", "claimed_at_prop", "submitted_pending_sync", "pending_master_approval"].includes(status)) return "taken";
  return "open";
};

const getLordHomeStacksFromBackend = (rows: LordHomeBackendStack[] | "" | null | undefined): LordHomeStack[] => {
  return (Array.isArray(rows) ? rows : []).flatMap((row) => {
    if (row.hidden || (row.status && row.status !== "active")) {
      return [];
    }

    const unitId = row.card_id ? lordHomeUnitIdByBackendCardId[row.card_id] : undefined;
    const count = Number(row.count ?? 0);
    if (!unitId || !Number.isFinite(count) || count <= 0) {
      return [];
    }

    return [{
      stackId: row.army_id ?? row.garrison_id,
      unitId,
      count
    }];
  });
};

const lordBuildingBaseBenefitLabels: Record<string, string[]> = {
  b_training_yard: ["Максимум активной армии +1", "Открывает найм мечников"],
  b_barracks: ["Открывает найм стражи"],
  b_archery_range: ["Открывает найм лучников"],
  b_stables: ["Максимум активной армии +1", "Открывает найм кавалерии"],
  b_siege_yard: ["Открывает найм осадников"],
  b_war_academy: ["Максимум активной армии +1", "Открывает найм инженеров", "Кап рейдовых жетонов +2"],
  b_market: ["Доход за тик +5 золота"],
  b_tax_office: ["Доход с контролируемых территорий +25%"],
  b_storehouse: ["Лимит накопления открытых войск +25%"],
  b_bank: ["Доход за тик +10 золота", "Налет за добычей крадет на 50% меньше золота"],
  b_treasury_hall: ["Доход за тик +20 золота", "Итоговый доход не падает ниже 50% от дохода до штрафов"],
  b_notice_board: ["Открывает публичные заказы", "Лимит публичных заказов: 2 активных"],
  b_envoy_hall: ["Открывает адресные заказы", "Лимит адресных заказов: 1 активный"],
  b_map_room: ["Открывает список целей рейда", "Показывает общий риск защиты цели"],
  b_raid_office: ["Кап рейдовых жетонов +2", "Открывает территориальные рейды"],
  b_war_council: [
    "Максимум активной армии +1",
    "Кап рейдовых жетонов +1",
    "Открывает рейд Черная печать",
    "С Комнатой видений открывает рейд по резиденции"
  ],
  b_mage_study: ["Защита резиденции от рейдов +1"],
  b_alchemy_lab: ["Длительность входящих рейд-эффектов -15 минут", "Мгновенный лут-рейд не сокращается"],
  b_scrying_room: ["Показывает точную защиту цели", "Показывает силу гарнизона цели", "Показывает обереги и активную армию цели"],
  b_wards: ["Обычные территории: защита от рейдов +1", "Резиденция: защита от рейдов +2"],
  b_ritual_chamber: ["Раз в доходный тик дает 1 заряд очищения", "Заряд снимает один активный рейд-эффект с владений дома"]
};

const getLordBuildingState = (building: LordBuildingNode, builtBuildingIds: Set<string>): LordBuildingState => {
  if (building.serverState) {
    return building.serverState;
  }
  if (builtBuildingIds.has(building.id)) {
    return "built";
  }

  return building.prerequisiteIds.every((id) => builtBuildingIds.has(id)) ? "available" : "locked";
};

const lordHomeInitialDomainStats: LordHomeDomainStats = {
  incomePerHour: 25,
  rawIncomePerHour: 25,
  territoryIncomePerHour: 0,
  currentMp: 6,
  mpCap: 6,
  activeArmyCapacity: 5,
  activeArmySlotsUsed: lordHomeInitialArmy.length,
  raidTokenCap: 1
};

const lordHomeRuntimeInitialDomainStats: LordHomeDomainStats = {
  incomePerHour: 0,
  rawIncomePerHour: 0,
  territoryIncomePerHour: 0,
  currentMp: 0,
  mpCap: 1,
  activeArmyCapacity: 5,
  activeArmySlotsUsed: 0,
  raidTokenCap: 0
};

const lordHomeActLabelById: Record<string, string> = {
  act1: "Акт I",
  act2: "Акт II",
  act3: "Акт III",
  final_act: "Финал",
  final_lock: "Финал"
};

const lordHomeTickEffectLabelById: Record<string, string> = {
  lord_income_and_mana: "тик дохода",
  income: "тик дохода",
  mana: "тик маны",
  movement: "тик MP",
  movement_points: "тик MP",
  final_lock: "финальный тик"
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

  if (hours > 0) {
    return `${hours}ч ${String(minutes).padStart(2, "0")}м`;
  }

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
};

const getLordHomeTimerRemainingSeconds = (
  timerSummary: LordHomeBackendTimerSummary | null,
  nowMs: number
) => {
  const nextTick = timerSummary?.next_tick;
  if (!nextTick) {
    return null;
  }

  const dueAtMs = nextTick.due_at ? Date.parse(nextTick.due_at) : Number.NaN;
  if (Number.isFinite(dueAtMs)) {
    return Math.max(0, Math.ceil((dueAtMs - nowMs) / 1000));
  }

  const secondsUntil = Number(nextTick.seconds_until ?? 0);
  return Number.isFinite(secondsUntil) ? Math.max(0, Math.ceil(secondsUntil)) : null;
};

const getLordHomeTimerShortLabel = (
  timerSummary: LordHomeBackendTimerSummary | null,
  nowMs = Date.now()
) => {
  const nextTick = timerSummary?.next_tick;
  if (!nextTick) {
    return timerSummary?.status === "active" ? "тики завершены" : "нет акта";
  }

  const secondsUntil = getLordHomeTimerRemainingSeconds(timerSummary, nowMs);
  return secondsUntil === null ? "нет времени" : formatLordHomeTimerCountdown(secondsUntil);
};

const getLordHomeTickLabel = (timerSummary: LordHomeBackendTimerSummary | null) => {
  const effectType = timerSummary?.next_tick?.effect_type ?? "";
  return lordHomeTickEffectLabelById[effectType] ?? (effectType ? "следующий тик" : "");
};

function LordHomeTimerChip({
  timerSummary,
  nowMs
}: {
  timerSummary: LordHomeBackendTimerSummary | null;
  nowMs: number;
}) {
  const actLabel = getLordHomeActLabel(timerSummary);
  const timerLabel = getLordHomeTimerShortLabel(timerSummary, nowMs);
  const tickLabel = getLordHomeTickLabel(timerSummary);
  const isActive = timerSummary?.status === "active";
  const ariaLabel = [actLabel, tickLabel, timerLabel].filter(Boolean).join(": ");

  return (
    <div className={`lord-home-timer-chip${isActive ? " is-active" : ""}`} aria-label={ariaLabel}>
      <Clock3 size={14} aria-hidden="true" />
      <b>{actLabel}</b>
      <span>{timerLabel}</span>
      {tickLabel ? <small>{tickLabel}</small> : null}
    </div>
  );
}

const clampLordHomeMetric = (value: number, fallback: number) =>
  Number.isFinite(value) ? Math.max(0, Math.round(value)) : fallback;

const lordBuildingLinkSlot = {
  halfX: 2.8,
  halfY: 3.05
} as const;

const formatLordBuildingPathValue = (value: number) => Number(value.toFixed(2));

const getLordBuildingLinkPath = (from: LordBuildingNode, to: LordBuildingNode) => {
  if (from.id === "b_stables" && to.id === "b_raid_office") {
    const startX = from.x + lordBuildingLinkSlot.halfX;
    const endX = to.x - lordBuildingLinkSlot.halfX;

    return `M ${formatLordBuildingPathValue(startX)} ${formatLordBuildingPathValue(from.y)} H ${formatLordBuildingPathValue(endX)}`;
  }

  if (from.id === "b_envoy_hall" && to.id === "b_war_council") {
    const startX = from.x;
    const startY = from.y - lordBuildingLinkSlot.halfY;
    const endX = to.x + lordBuildingLinkSlot.halfX;
    const endY = to.y;

    return `M ${formatLordBuildingPathValue(startX)} ${formatLordBuildingPathValue(startY)} V ${formatLordBuildingPathValue(endY)} H ${formatLordBuildingPathValue(endX)}`;
  }

  const sameRow = Math.abs(from.y - to.y) < lordBuildingLinkSlot.halfY * 1.45;

  if (sameRow) {
    const direction = to.x >= from.x ? 1 : -1;
    const startX = from.x + direction * lordBuildingLinkSlot.halfX;
    const startY = from.y - 0.45;
    const endX = to.x - direction * lordBuildingLinkSlot.halfX;
    const endY = to.y - 0.45;
    const routeY = Math.min(startY, endY) - 4.75;

    return `M ${formatLordBuildingPathValue(startX)} ${formatLordBuildingPathValue(startY)} V ${formatLordBuildingPathValue(routeY)} H ${formatLordBuildingPathValue(endX)} V ${formatLordBuildingPathValue(endY)}`;
  }

  const startX = from.x;
  const startY = from.y - lordBuildingLinkSlot.halfY;
  const endX = to.x;
  const endY = to.y + lordBuildingLinkSlot.halfY;
  const midY = (startY + endY) / 2;

  return `M ${formatLordBuildingPathValue(startX)} ${formatLordBuildingPathValue(startY)} V ${formatLordBuildingPathValue(midY)} H ${formatLordBuildingPathValue(endX)} V ${formatLordBuildingPathValue(endY)}`;
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

type LordMapTerritoryProfile = {
  tier: string;
  bonus: string;
  income: string;
  hire: string;
  magic: string;
  orders: string;
  defense: string;
  garrison: string;
  neutralDefense: string;
  raidEffects: string;
};

const lordMapTerritoryProfileOverrides: Record<string, Partial<LordMapTerritoryProfile>> = {
  node_fort_east: {
    tier: "T2",
    bonus: "северный рубеж, оборона дорог",
    income: "+8 золота/тик",
    hire: "стража T1",
    magic: "нет",
    orders: "перехват на северной дороге",
    defense: "+2 к обороне",
    garrison: "6 отрядов",
    neutralDefense: "стража заставы, остановка при входе"
  },
  node_fort_west: {
    tier: "T2",
    bonus: "западный рубеж, контроль пашен",
    income: "+8 золота/тик",
    hire: "копейщики T1",
    defense: "+2 к обороне",
    garrison: "6 отрядов",
    neutralDefense: "острожная стража, остановка при входе"
  },
  node_fort_southwest: {
    tier: "T2",
    bonus: "южный рубеж, дорога к утесу",
    income: "+7 золота/тик",
    hire: "ополчение T1",
    defense: "+2 к обороне",
    garrison: "6 отрядов",
    neutralDefense: "нейтральная крепь, остановка при входе"
  },
  node_spanish_magic: {
    tier: "T2",
    bonus: "магический спор",
    income: "+1 знак/тик",
    magic: "ритуальный узел",
    orders: "заявка магам",
    neutralDefense: "нестабильная зона, остановка при входе"
  },
  node_science_barn: {
    tier: "T2",
    bonus: "мануфактура",
    income: "+10 золота/тик",
    hire: "нет",
    orders: "ремесленный заказ"
  }
};

const getLordMapDefaultTerritoryProfile = (socket: LordMapSocket): LordMapTerritoryProfile => {
  if (isLordMapResidenceSocket(socket)) {
    return {
      tier: "T3",
      bonus: "резиденция дома",
      income: "+18 золота/тик",
      hire: "основной набор",
      magic: "придворная поддержка",
      orders: "приказы дома",
      defense: "+3 к обороне",
      garrison: "8 отрядов",
      neutralDefense: "нет",
      raidEffects: "нет видимых эффектов"
    };
  }

  if (socket.id.includes("field") || socket.id.includes("oats")) {
    return {
      tier: "T1",
      bonus: "зерно и доход",
      income: "+6 золота/тик",
      hire: "ополчение T1",
      magic: "нет",
      orders: "снабжение",
      defense: "+0 к обороне",
      garrison: "4 отряда",
      neutralDefense: "местная стража, остановка при входе",
      raidEffects: "нет видимых эффектов"
    };
  }

  if (socket.id.includes("village") || socket.id.includes("barn") || socket.id.includes("well")) {
    return {
      tier: "T1",
      bonus: "люди и торговля",
      income: "+5 золота/тик",
      hire: "ополчение T1",
      magic: "нет",
      orders: "посыльные",
      defense: "+1 к обороне",
      garrison: "4 отряда",
      neutralDefense: "деревенская стража, остановка при входе",
      raidEffects: "нет видимых эффектов"
    };
  }

  if (socket.id.includes("mountain")) {
    return {
      tier: "T2",
      bonus: "трудный перевал",
      income: "+4 золота/тик",
      hire: "егеря T1",
      magic: "нет",
      orders: "дозор",
      defense: "+2 к обороне",
      garrison: "5 отрядов",
      neutralDefense: "горный дозор, остановка при входе",
      raidEffects: "нет видимых эффектов"
    };
  }

  if (socket.id.includes("lake") || socket.id.includes("swamp") || socket.id.includes("forest")) {
    return {
      tier: "T1",
      bonus: "укрытия и разведка",
      income: "+4 золота/тик",
      hire: "следопыты T1",
      magic: socket.id.includes("swamp") ? "слабый знак" : "нет",
      orders: "засада",
      defense: "+1 к обороне",
      garrison: "4 отряда",
      neutralDefense: "местные дозоры, остановка при входе",
      raidEffects: "нет видимых эффектов"
    };
  }

  return {
    tier: "T1",
    bonus: "локальный доход",
    income: "+5 золота/тик",
    hire: "ополчение T1",
    magic: "нет",
    orders: "снабжение",
    defense: "+1 к обороне",
    garrison: "4 отряда",
    neutralDefense: "нейтральная стража, остановка при входе",
    raidEffects: "нет видимых эффектов"
  };
};

const getLordMapTerritoryProfile = (socket: LordMapSocket): LordMapTerritoryProfile => ({
  ...getLordMapDefaultTerritoryProfile(socket),
  ...(lordMapTerritoryProfileOverrides[socket.id] ?? {})
});

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
  return lordId ? lordMapLordMeta[lordId].name : domainId || "РЅРµР№С‚СЂР°Р»СЊРЅРѕ";
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
};

const lordMapBattleClaimStatuses = new Set(["in_battle", "contested", "contested_pending_tick"]);

const getLordMapPendingBattleClaim = (state: LordMapBackendState | null): LordMapPendingBattleClaim | null => {
  if (!state) return null;
  const domainId = state.domain?.domain_id ?? state.lord?.domain_id ?? "";
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
    const status = item.status ?? "";
    return (
      Boolean(claimId) &&
      Boolean(territoryId) &&
      (item.battle_required || lordMapBattleClaimStatuses.has(status)) &&
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

function App() {
  const path = window.location.pathname;

  if (path === "/lords/login") {
    return <AnimatedLordLoginScreen />;
  }

  if (path === "/lords/battle") {
    return <LordBattleScreen />;
  }

  if (path === "/lords/map") {
    return <LordMapScreen />;
  }

  if (path === "/lords/home") {
    return <LordHomeScreen />;
  }

  if (path === "/lords" || path === "/lords/castle" || path === "/lords/dashboard") {
    return <RedirectTo path="/lords/home" />;
  }

  return <RedirectTo path="/lords/login" />;
}

function RedirectTo({ path }: { path: string }) {
  useEffect(() => {
    window.location.replace(path);
  }, [path]);

  return null;
}

function LordMapScreen() {
  const mapRouteParams = new URLSearchParams(window.location.search);
  const lordRuntimeMode = getLordRuntimeMode(mapRouteParams);
  const useDemoState = lordRuntimeMode !== "production";
  const apiBaseUrl = getLordRuntimeApiBaseUrl(mapRouteParams);
  const backendLordId =
    mapRouteParams.get("lord") ||
    mapRouteParams.get("lord_id") ||
    mapRouteParams.get("lordId") ||
    localStorage.getItem("witcher_larp_lord_id") ||
    lordHomeDefaultLordId;
  const backendRoleToken =
    mapRouteParams.get("token") ||
    localStorage.getItem("witcher_larp_role_token") ||
    lordHomeDefaultRoleToken;
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

  const fetchLordMapState = useCallback(async (options?: { silent?: boolean; summaryOnly?: boolean }) => {
    if (stateFetchInFlightRef.current) {
      return;
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
    } catch (error) {
      setBackendState((currentState) => currentState);
      setLordUiState((current) => markLordUiStateOffline(current));
      setMapApiState("offline");
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      if (!options?.silent) {
        setMapActionStatus(getLordHomeCaughtErrorMessage(error, "Приказная не отвечает"));
      }
    } finally {
      window.clearTimeout(timeoutId);
      stateFetchInFlightRef.current = false;
    }
  }, [apiBaseUrl, backendLordId, backendRoleToken, lordRuntimeMode]);

  useEffect(() => {
    localStorage.setItem("witcher_larp_lord_id", backendLordId);
    localStorage.setItem("witcher_larp_role_token", backendRoleToken);
  }, [backendLordId, backendRoleToken]);

  useEffect(() => {
    void fetchLordMapState({ silent: true });
  }, [fetchLordMapState]);

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
    const arrivedSocketId = backendState.movement?.current_node_id ?? backendState.domain?.current_node_id ?? arrivedMove.to_node_id;
    if (arrivedSocketId && hasMapSocket(arrivedSocketId)) {
      setMapActionStatus(`Армия прибыла: ${getMapSocket(arrivedSocketId).name}.`);
    }
  }, [backendPendingMove, backendState, getMapSocket, hasMapSocket]);

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
          ? getLordHomeApiErrorMessage(serverPreviewForDisplay, serverPreviewForDisplay.reason || "РњР°СЂС€СЂСѓС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ")
          : routePreviewState === "loading"
            ? "РџСЂРѕРІРµСЂСЏРµРј РјР°СЂС€СЂСѓС‚."
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
        setServerRoutePreview(payload as LordMapBackendRoutePreview);
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
      ? lordUiState.readonlyReason
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
      ? "Только чтение"
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
  const openLordMapBattle = useCallback(async (source = "stage2b_map_claim") => {
    const battleRuntimeAuth = { lordId: backendLordId, roleToken: backendRoleToken };
    if (activeBattleId) {
      window.location.assign(
        withLordRuntimeQuery(`/lords/battle?battle_id=${encodeURIComponent(activeBattleId)}&return_to=map`, apiBaseUrl, battleRuntimeAuth)
      );
      return;
    }

    if (!mapBattleClaim) {
      setMapActionStatus("Активного боя сейчас нет.");
      return;
    }

    if (battleClaimOpenRef.current === mapBattleClaim.claimId) {
      return;
    }

    battleClaimOpenRef.current = mapBattleClaim.claimId;
    setMapActionStatus("Открываю бой за территорию.");
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
        body: JSON.stringify({
          claim_id: mapBattleClaim.claimId,
          territory_id: mapBattleClaim.territoryId,
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
      window.location.assign(
        withLordRuntimeQuery(`/lords/battle?battle_id=${encodeURIComponent(battleId)}&return_to=map`, apiBaseUrl, battleRuntimeAuth)
      );
    } catch (error) {
      battleClaimOpenRef.current = null;
      setMapActionStatus(getLordHomeCaughtErrorMessage(error, "Бой не открыт. Позовите мастера."));
    }
  }, [
    activeBattleId,
    apiBaseUrl,
    backendLordId,
    backendRoleToken,
    mapBattleClaim?.claimId,
    mapBattleClaim?.territoryId
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
  const territoryProfile = getLordMapTerritoryProfile(displaySocket);
  const territoryInfoRows = [
    { label: "Tier", value: territoryProfile.tier },
    { label: "Бонус", value: territoryProfile.bonus },
    { label: "Доход", value: territoryProfile.income },
    { label: "Найм", value: territoryProfile.hire },
    { label: "Магия", value: territoryProfile.magic },
    { label: "Заказы", value: territoryProfile.orders },
    { label: "Оборона", value: territoryProfile.defense },
    { label: "Гарнизон", value: territoryProfile.garrison },
    { label: "Нейтральная стража", value: territoryProfile.neutralDefense },
    { label: "Набеги", value: territoryProfile.raidEffects }
  ];
  const territoryRoads = getLordMapNeighbors(displaySocket.id, mapTravelEdges).map((neighbor) => {
    const neighborSocket = getMapSocket(neighbor.id);
    return `${neighborSocket.name}: ${neighbor.cost} MP`;
  });

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
              aria-label={action.id === "map" ? "Вернуться на главный экран" : action.label}
              onClick={() => {
                if (action.id === "map") {
                  window.location.assign(withLordRuntimeQuery(lordHomePath, apiBaseUrl));
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
                <div className="lord-map-info-roads">
                  <b>Дороги</b>
                  <p>{territoryRoads.length > 0 ? territoryRoads.join("; ") : "нет открытых дорог"}</p>
                </div>
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

function LordHomeScreen() {
  const homeRouteParams = new URLSearchParams(window.location.search);
  const lordRuntimeMode = getLordRuntimeMode(homeRouteParams);
  const useDemoState = lordRuntimeMode !== "production";
  const viewParam = homeRouteParams.get("view");
  const panelParam = homeRouteParams.get("panel");
  const initialHomeView: LordHomeView =
    viewParam === "buildings"
      ? "buildings"
      : viewParam === "raids" || panelParam === "raids"
        ? "raids"
      : viewParam === "orders" || panelParam === "orders"
        ? "orders"
        : "territory";
  const buildingParam = homeRouteParams.get("building");
  const initialSelectedBuildingId =
    buildingParam && lordBuildingTreeNodes.some((building) => building.id === buildingParam)
      ? buildingParam
      : "b_barracks";
  const initialOpenPanel: LordHomePanel | null =
    panelParam === "map" || panelParam === "help"
      ? panelParam
      : null;
  const apiBaseUrl = getLordRuntimeApiBaseUrl(homeRouteParams);
  const backendLordId = homeRouteParams.get("lord") || localStorage.getItem("witcher_larp_lord_id") || lordHomeDefaultLordId;
  const backendRoleToken = homeRouteParams.get("token") || localStorage.getItem("witcher_larp_role_token") || lordHomeDefaultRoleToken;
  const initialHomeBackendStateRef = useRef<LordHomeBackendState | null>(
    useDemoState ? null : readLordRuntimeCachedState<LordHomeBackendState>(apiBaseUrl, backendLordId)
  );
  const [lordUiState, setLordUiState] = useState<LordUiState>(() =>
    initialHomeBackendStateRef.current
      ? markLordUiStateOffline(adaptLordState(initialHomeBackendStateRef.current, { mode: lordRuntimeMode }))
      : createLordUiState(useDemoState ? "demo" : "loading", { mode: lordRuntimeMode })
  );
  const [selectedTerritoryId, setSelectedTerritoryId] = useState<LordHomeTerritoryId>("castle");
  const [army, setArmy] = useState<LordHomeStack[]>(() => useDemoState ? lordHomeInitialArmy : lordHomeEmptyArmy);
  const [garrisons, setGarrisons] = useState<Record<LordHomeTerritoryId, LordHomeStack[]>>(() =>
    useDemoState ? lordHomeInitialGarrisons : createEmptyLordHomeGarrisons()
  );
  const [territoryRuntime, setTerritoryRuntime] = useState<Partial<Record<LordHomeTerritoryId, LordHomeTerritoryRuntime>>>({});
  const [domainStats, setDomainStats] = useState<LordHomeDomainStats>(() =>
    useDemoState ? lordHomeInitialDomainStats : lordHomeRuntimeInitialDomainStats
  );
  const [timerSummary, setTimerSummary] = useState<LordHomeBackendTimerSummary | null>(null);
  const [timerNowMs, setTimerNowMs] = useState(() => Date.now());
  const [recruitStock, setRecruitStock] = useState(() =>
    useDemoState ? lordHomeInitialRecruitStock : createEmptyLordHomeRecruitStock()
  );
  const [recruitOffersByCard, setRecruitOffersByCard] = useState<Record<string, LordHomeRecruitOffer>>(() =>
    useDemoState ? lordHomeSeedRecruitOffers : lordHomeRuntimeRecruitOffers
  );
  const [recruitUnitId, setRecruitUnitId] = useState<LordHomeUnitId | null>(null);
  const [recruitQty, setRecruitQty] = useState(1);
  const [lordGold, setLordGold] = useState(() => useDemoState ? 18804 : 0);
  const [recruitStatus, setRecruitStatus] = useState("");
  const [isRecruitHiring, setIsRecruitHiring] = useState(false);
  const [isRecruitSliderDragging, setIsRecruitSliderDragging] = useState(false);
  const [dragPayload, setDragPayload] = useState<LordHomeDragPayload>(null);
  const dragPayloadRef = useRef<LordHomeDragPayload>(null);
  const suppressNextStackClickUntilRef = useRef(0);
  const stateFetchInFlightRef = useRef(false);
  const cachedHomeStateAppliedRef = useRef(false);
  const backgroundStateRefreshInFlightRef = useRef(false);
  const backgroundStateRefreshQueuedRef = useRef<{ source: string; refreshRecruit: boolean } | null>(null);
  const pointerDragRef = useRef<{
    payload: Exclude<LordHomeDragPayload, null>;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const [transferDraft, setTransferDraft] = useState<LordHomeTransferDraft>(null);
  const [transferQty, setTransferQty] = useState(1);
  const [transferStatus, setTransferStatus] = useState("");
  const [isTransferSubmitting, setIsTransferSubmitting] = useState(false);
  const [homeView, setHomeView] = useState<LordHomeView>(initialHomeView);
  const [builtBuildingIds, setBuiltBuildingIds] = useState<Set<string>>(() =>
    new Set(useDemoState ? lordBuildingInitialBuiltIds : lordBuildingRuntimeInitialBuiltIds)
  );
  const [backendBuildingCatalog, setBackendBuildingCatalog] = useState<LordHomeBackendBuilding[]>([]);
  const [selectedBuildingId, setSelectedBuildingId] = useState(initialSelectedBuildingId);
  const [buildingStatus, setBuildingStatus] = useState("");
  const [buildingPurchaseId, setBuildingPurchaseId] = useState<string | null>(null);
  const [lordOrders, setLordOrders] = useState<LordHomeOrder[]>([]);
  const [lordOrderCap, setLordOrderCap] = useState<LordHomeOrderCap>({});
  const [lordOrderEscrow, setLordOrderEscrow] = useState<LordHomeOrderEscrow>({});
  const [lordOrderConflicts, setLordOrderConflicts] = useState<LordHomeOrderConflict[]>([]);
  const [lordOrderTargets, setLordOrderTargets] = useState<LordHomeOrderTarget[]>([]);
  const [lordOrderRecipients, setLordOrderRecipients] = useState<LordHomeOrderRecipient[]>([]);
  const [lordOrderFilter, setLordOrderFilter] = useState<LordHomeOrderFilterId>("open");
  const [selectedLordOrderId, setSelectedLordOrderId] = useState<string | null>(null);
  const [lordOrderStatus, setLordOrderStatus] = useState("");
  const [lordOrderReadOnlyReason, setLordOrderReadOnlyReason] = useState("");
  const [isLordOrderSubmitting, setIsLordOrderSubmitting] = useState(false);
  const [raidTokens, setRaidTokens] = useState(() => useDemoState ? 2 : 0);
  const [lordRaidRules, setLordRaidRules] = useState<LordHomeRaidRule[]>(() =>
    useDemoState ? lordHomeFallbackRaidRules : []
  );
  const [lordRaidTargets, setLordRaidTargets] = useState<LordHomeRaidTarget[]>(() =>
    useDemoState ? lordHomeFallbackRaidTargets : []
  );
  const [activeRaidEffects, setActiveRaidEffects] = useState<LordHomeRaidEffect[]>([]);
  const [lordRaidHistory, setLordRaidHistory] = useState<LordHomeRaidEffect[]>([]);
  const [selectedRaidRuleId, setSelectedRaidRuleId] = useState(() =>
    useDemoState ? lordHomeFallbackRaidRules[0].rule_id : ""
  );
  const [selectedRaidTargetId, setSelectedRaidTargetId] = useState(() =>
    useDemoState ? lordHomeFallbackRaidTargets[0].target_territory_id : ""
  );
  const [lordRaidStatus, setLordRaidStatus] = useState("");
  const [isLordRaidSubmitting, setIsLordRaidSubmitting] = useState(false);
  const [openPanel, setOpenPanel] = useState<LordHomePanel | null>(initialOpenPanel);
  const prefersReducedMotion = useReducedMotion();
  const selectedTerritory = lordHomeTerritories.find((territory) => territory.id === selectedTerritoryId) ?? lordHomeTerritories[0];
  const selectedTerritoryRuntime = territoryRuntime[selectedTerritory.id];
  const selectedTerritoryBackendId = selectedTerritoryRuntime?.backendTerritoryId || selectedTerritory.backendTerritoryId;
  const selectedTerritoryName = selectedTerritoryRuntime?.name || selectedTerritory.name;
  const selectedTerritoryBackground = selectedTerritoryRuntime?.background || selectedTerritory.background;
  const selectedHeroHere = selectedTerritoryRuntime?.heroHere ?? (useDemoState ? selectedTerritory.heroHere : false);
  const selectedGarrison = garrisons[selectedTerritory.id] ?? [];
  const selectedIncomePerHour = selectedTerritoryRuntime?.incomePerHour ?? (useDemoState ? selectedTerritory.income : 0);
  const selectedGarrisonCapacity = selectedTerritoryRuntime?.garrisonCapacity ?? 8;
  const selectedGarrisonSlotsUsed = selectedTerritoryRuntime?.garrisonSlotsUsed ?? selectedGarrison.length;
  const selectedGarrisonSlotsFree = Math.max(0, selectedGarrisonCapacity - selectedGarrisonSlotsUsed);
  const selectedActiveArmyLockReason = selectedTerritoryRuntime?.activeArmyLockReason || (!selectedHeroHere ? "Герой в другой локации" : "");
  const selectedRecruitLockReason = selectedTerritoryRuntime?.recruitLockReason || "";
  const selectedBuildingTreeLockReason = selectedTerritoryRuntime?.buildingTreeLockReason || "";
  const selectedBuildingNodeIds = selectedTerritoryRuntime?.buildingNodeIds;
  const selectedBuildingNodeIdSet = useMemo(
    () => selectedBuildingNodeIds?.length ? new Set(selectedBuildingNodeIds) : null,
    [selectedBuildingNodeIds]
  );
  const selectedBuildingTreeNodes = useMemo(
    () => {
      const backendNodes = selectedTerritoryRuntime?.buildingNodes;
      const sourceNodes = selectedBuildingTreeLockReason
        ? (backendNodes ?? [])
        : backendNodes?.length
          ? backendNodes
          : backendBuildingCatalog;
      return getLordBuildingNodesFromBackend(sourceNodes, selectedBuildingNodeIdSet);
    },
    [
      backendBuildingCatalog,
      selectedBuildingNodeIdSet,
      selectedBuildingTreeLockReason,
      selectedTerritoryRuntime?.buildingNodes
    ]
  );
  const selectedBuiltBuildingIds = useMemo(
    () => selectedBuildingTreeNodes.some((building) => building.serverState)
      ? getLordBuiltBuildingIdsFromNodes(selectedBuildingTreeNodes)
      : builtBuildingIds,
    [builtBuildingIds, selectedBuildingTreeNodes]
  );
  const isHomeReadOnly = lordUiState.mode === "production" && lordUiState.isReadOnly;
  const homeReadOnlyReason = isHomeReadOnly ? lordUiState.readonlyReason : "";
  const displayedTerritoryBubbles = lordHomeTerritories
    .filter((territory) => territory.id !== "castle" && territoryRuntime[territory.id]?.isOwned)
    .map((territory) => {
      const runtime = territoryRuntime[territory.id];
      return {
        ...territory,
        name: runtime?.name || territory.name,
        shortName: runtime?.shortName || territory.shortName,
        background: runtime?.background || territory.background
      };
    });
  const transferStack = transferDraft
    ? transferDraft.lane === "army"
      ? army[transferDraft.index]
      : selectedGarrison[transferDraft.index]
    : null;
  const transferUnit = transferStack ? lordHomeUnitCatalog[transferStack.unitId] : null;
  const isSplitDraft = transferDraft?.mode === "split";
  const maxTransferQty = transferStack
    ? isSplitDraft
      ? Math.max(0, transferStack.count - 1)
      : transferStack.count
    : 0;
  const transferSliderPercent = maxTransferQty > 1
    ? ((transferQty - 1) / (maxTransferQty - 1)) * 100
    : maxTransferQty > 0 ? 100 : 0;
  const transferCanSubmit = Boolean(
    transferDraft &&
      transferStack &&
      transferUnit &&
      (isSplitDraft || selectedHeroHere) &&
      transferQty >= 1 &&
      transferQty <= maxTransferQty &&
      !isHomeReadOnly &&
      !isTransferSubmitting
  );
  const recruitUnit = recruitUnitId ? lordHomeUnitCatalog[recruitUnitId] : null;
  const recruitStockInfo = recruitUnitId ? recruitStock[selectedTerritory.id]?.[recruitUnitId] : null;
  const recruitOffer = recruitUnit ? recruitOffersByCard[recruitUnit.backendCardId] : null;
  const recruitHasOffer = Boolean(recruitStockInfo || recruitOffer);
  const recruitOfferStatus = recruitStockInfo?.status ?? recruitOffer?.status ?? "available";
  const recruitStockLockReason = recruitStockInfo?.lockReason ?? "";
  const effectiveRecruitLockReason = selectedRecruitLockReason || recruitStockLockReason;
  const recruitCanRecruitByStock = recruitStockInfo?.canRecruit ?? true;
  const recruitStockAvailable = Math.max(0, recruitStockInfo?.stock ?? recruitOffer?.stock ?? 0);
  const recruitUnitCost = Math.max(0, recruitStockInfo?.cost ?? recruitOffer?.cost ?? recruitUnit?.cost ?? 0);
  const recruitWouldUseNewGarrisonSlot = Boolean(
    recruitUnitId && !selectedGarrison.some((stack) => stack.unitId === recruitUnitId)
  );
  const recruitBlockedByGarrisonCap = recruitWouldUseNewGarrisonSlot && selectedGarrisonSlotsFree < 1;
  const recruitAffordableQty = recruitUnit
    ? recruitUnitCost > 0
      ? Math.floor(lordGold / recruitUnitCost)
      : recruitStockAvailable
    : 0;
  const maxRecruitQty = recruitBlockedByGarrisonCap
    ? 0
    : Math.max(0, Math.min(recruitStockAvailable, recruitAffordableQty, recruitStockInfo?.maxPurchasable ?? Number.POSITIVE_INFINITY));
  const recruitSliderPercent = maxRecruitQty > 1
    ? ((recruitQty - 1) / (maxRecruitQty - 1)) * 100
    : maxRecruitQty > 0 ? 100 : 0;
  const recruitTotalCost = recruitQty * recruitUnitCost;
  const recruitNoStockReason = "Нет накопленного найма: дождитесь следующего тика";
  const recruitIdleStatus = !recruitHasOffer
    ? "Предложение не открыто"
    : effectiveRecruitLockReason
    ? effectiveRecruitLockReason
    : recruitStockAvailable < 1
    ? recruitNoStockReason
    : recruitBlockedByGarrisonCap
    ? "Нет свободного слота в гарнизоне"
    : recruitAffordableQty < 1
    ? "Недостаточно золота"
    : "";
  const recruitCanSubmit = Boolean(
    recruitUnit &&
      recruitHasOffer &&
      isLordHomeRecruitOfferUsable(recruitOfferStatus) &&
      recruitCanRecruitByStock &&
      recruitQty >= 1 &&
      recruitQty <= maxRecruitQty &&
      !recruitBlockedByGarrisonCap &&
      !effectiveRecruitLockReason &&
      !isHomeReadOnly &&
      !isRecruitHiring
  );
  const activeBattle = lordUiState.activeBattle.active;
  const activeBattleId = lordUiState.activeBattle.battleId;
  const canShowRuntimeResources = lordUiState.hasAuthoritativeState || useDemoState;
  const goldResourceLabel = canShowRuntimeResources ? String(lordGold) : "--";
  const incomeResourceLabel = canShowRuntimeResources ? `+${domainStats.incomePerHour}/тик` : "--";
  const territoryIncomeResourceLabel = canShowRuntimeResources ? `+${domainStats.territoryIncomePerHour}/тик` : "--";
  const raidResourceLabel = canShowRuntimeResources ? `${raidTokens}/${domainStats.raidTokenCap}` : "--/--";
  const armyResourceLabel = canShowRuntimeResources ? `${domainStats.activeArmySlotsUsed}/${domainStats.activeArmyCapacity}` : "--/--";
  const garrisonResourceLabel = canShowRuntimeResources ? `${selectedGarrisonSlotsUsed}/${selectedGarrisonCapacity}` : "--/--";
  const movementFallbackStats = useDemoState ? lordHomeInitialDomainStats : lordHomeRuntimeInitialDomainStats;
  const movementPointCap = lordUiState.mp.isKnown && lordUiState.mp.mpCap !== null
    ? lordUiState.mp.mpCap
    : Math.max(1, clampLordHomeMetric(domainStats.mpCap, movementFallbackStats.mpCap));
  const currentMovementPoints = lordUiState.mp.isKnown && lordUiState.mp.currentMp !== null
    ? lordUiState.mp.currentMp
    : Math.min(
        movementPointCap,
        clampLordHomeMetric(domainStats.currentMp, movementFallbackStats.currentMp)
      );
  const recruitUnitIds = lordHomeUnitOrder.filter((unitId) => {
    const stockInfo = recruitStock[selectedTerritory.id]?.[unitId];
    const offer = recruitOffersByCard[lordHomeUnitCatalog[unitId].backendCardId];
    const status = stockInfo?.status ?? offer?.status ?? "available";
    return Boolean(
      (stockInfo || offer) &&
      isLordHomeRecruitOfferUsable(status) &&
      ((stockInfo?.rate ?? offer?.rate ?? 0) > 0 || (stockInfo?.stock ?? offer?.stock ?? 0) > 0)
    );
  });
  const displayedRecruitUnitIds = Array.from({ length: 6 }, (_, index) => recruitUnitIds[index] ?? null);
  const lordMapPath = useDemoState ? "/lords/map?demo=1" : "/lords/map";

  const applyBackendState = useCallback((
    state: LordHomeBackendState,
    options?: { cache?: boolean; stale?: boolean }
  ) => {
    const nextLordUiState = adaptLordState(state, { mode: lordRuntimeMode });
    setLordUiState(options?.stale ? markLordUiStateOffline(nextLordUiState) : nextLordUiState);
    if (options?.cache !== false) {
      writeLordRuntimeCachedState(apiBaseUrl, backendLordId, state);
    }
    if (Array.isArray(state.building_catalog)) {
      setBackendBuildingCatalog(state.building_catalog);
    }
    const nextGold = Number(state.resources?.gold ?? state.domain?.gold ?? state.domain?.starting_gold);
    if (Number.isFinite(nextGold)) {
      setLordGold(nextGold);
    }
    setTimerSummary(state.timer_summary ?? null);
    if (Array.isArray(state.orders)) {
      setLordOrders(state.orders);
    }
    setLordOrderCap(state.order_cap ?? {});
    setLordOrderEscrow(state.escrow ?? {});
    setLordOrderConflicts(Array.isArray(state.order_conflicts) ? state.order_conflicts : []);
    setLordOrderReadOnlyReason("");
    if (Array.isArray(state.visible_targets)) {
      setLordOrderTargets(state.visible_targets);
    }
    if (Array.isArray(state.eligible_recipients)) {
      setLordOrderRecipients(state.eligible_recipients);
    }
    const nextRaidTokens = Number(state.resources?.raid_tokens ?? state.raid_tokens ?? state.domain?.raid_tokens);
    if (Number.isFinite(nextRaidTokens)) {
      setRaidTokens(nextRaidTokens);
    }
    if (Array.isArray(state.raid_rules) && state.raid_rules.length > 0) {
      const normalizedRules = state.raid_rules.map(normalizeLordHomeRaidRule);
      setLordRaidRules(normalizedRules);
      setSelectedRaidRuleId((current) =>
        normalizedRules.some((rule) => rule.rule_id === current)
          ? current
          : normalizedRules[0]?.rule_id ?? current
      );
    }
    if (Array.isArray(state.raid_targets) && state.raid_targets.length > 0) {
      const normalizedTargets = state.raid_targets.map(normalizeLordHomeRaidTarget);
      setLordRaidTargets(normalizedTargets);
      setSelectedRaidTargetId((current) =>
        normalizedTargets.some((target) => target.target_territory_id === current)
          ? current
          : normalizedTargets.find((target) => target.can_target)?.target_territory_id ??
            normalizedTargets[0]?.target_territory_id ??
            current
      );
    }
    if (Array.isArray(state.active_raid_effects)) {
      setActiveRaidEffects(state.active_raid_effects);
    } else if (Array.isArray(state.raid_effects)) {
      setActiveRaidEffects(state.raid_effects.filter((effect) => effect.status === "active"));
    }
    if (Array.isArray(state.raid_history)) {
      setLordRaidHistory(state.raid_history);
    } else if (Array.isArray(state.raid_effects)) {
      setLordRaidHistory(state.raid_effects);
    }
    setDomainStats((current) => {
      const nextIncome = Number(state.resources?.income_per_hour ?? state.domain?.income_per_hour);
      const nextRawIncome = Number(state.resources?.raw_income_per_hour ?? state.domain?.raw_income_per_hour);
      const nextTerritoryIncome = Number(state.resources?.territory_income_per_hour ?? state.domain?.territory_income_per_hour);
      const nextCurrentMp = Number(state.resources?.current_mp ?? state.movement?.current_mp ?? state.domain?.current_mp);
      const nextMpCap = Number(state.resources?.mp_cap ?? state.movement?.mp_cap ?? state.domain?.mp_cap);
      const nextArmyCapacity = Number(state.domain?.active_army_capacity);
      const nextArmySlotsUsed = Number(state.domain?.active_army_slots_used);
      const nextRaidTokenCap = Number(state.resources?.raid_token_cap ?? state.domain?.raid_token_cap);

      return {
        incomePerHour: clampLordHomeMetric(nextIncome, current.incomePerHour),
        rawIncomePerHour: clampLordHomeMetric(nextRawIncome, current.rawIncomePerHour),
        territoryIncomePerHour: clampLordHomeMetric(nextTerritoryIncome, current.territoryIncomePerHour),
        currentMp: clampLordHomeMetric(nextCurrentMp, current.currentMp),
        mpCap: clampLordHomeMetric(nextMpCap, current.mpCap),
        activeArmyCapacity: clampLordHomeMetric(nextArmyCapacity, current.activeArmyCapacity),
        activeArmySlotsUsed: clampLordHomeMetric(nextArmySlotsUsed, current.activeArmySlotsUsed),
        raidTokenCap: clampLordHomeMetric(nextRaidTokenCap, current.raidTokenCap)
      };
    });

    const nextBuiltBuildingIds = getLordHomeBuiltBuildingIdsFromBackendState(state);
    if (nextBuiltBuildingIds) {
      setBuiltBuildingIds(nextBuiltBuildingIds);
    }

    if (Array.isArray(state.active_army)) {
      setArmy(getLordHomeStacksFromBackend(state.active_army));
    }

    const backendTerritoryViews = Array.isArray(state.territory_views) ? state.territory_views : [];
    if (backendTerritoryViews.length > 0) {
      const nextGarrisons = createEmptyLordHomeGarrisons();
      const nextTerritoryRuntime: Partial<Record<LordHomeTerritoryId, LordHomeTerritoryRuntime>> = {};
      const nextRecruitStock = createEmptyLordHomeRecruitStock();

      for (const territory of backendTerritoryViews) {
        const isOwned = territory.is_owned === true;
        const localTerritoryId = getLordHomeLocalTerritoryId(territory, isOwned);
        if (!localTerritoryId) {
          continue;
        }

        const localTerritory = lordHomeTerritories.find((item) => item.id === localTerritoryId);
        const backendTerritoryId = territory.territory_id ?? localTerritory?.backendTerritoryId ?? "";
        const stacks = getLordHomeStacksFromBackend(territory.garrisons);
        const incomePerHour = Number(territory.income_per_hour);
        const garrisonCapacity = Number(territory.fort?.garrison_capacity);
        const garrisonSlotsUsed = Number(territory.fort?.garrison_slots_used);
        const buildingNodeIds = territory.building_tree?.node_ids?.filter((buildingId) =>
          lordBuildingKnownIds.has(buildingId)
        ) ?? territory.building_tree?.nodes
          ?.map((building) => building.building_id ?? "")
          .filter((buildingId) => lordBuildingKnownIds.has(buildingId));
        const buildingNodes = (territory.building_tree?.nodes ?? []).filter(
          (building) => building.building_id && lordBuildingKnownIds.has(building.building_id)
        );
        const activeArmyLockReason =
          territory.active_army_lock_reason ||
          getLordHomeLockReasonMessage(territory.lock_reasons, ["active_army", "transfer"]);
        const recruitLockReason =
          territory.recruit_lock_reason ||
          getLordHomeLockReasonMessage(territory.lock_reasons, ["recruit"]);
        const buildingTreeLockReason =
          territory.building_tree_lock_reason ||
          territory.building_tree?.lock_reason ||
          getLordHomeLockReasonMessage(territory.lock_reasons, ["building_tree", "building"]);

        nextGarrisons[localTerritoryId] = stacks;
        nextTerritoryRuntime[localTerritoryId] = {
          backendTerritoryId,
          name: territory.name || territory.node_name || localTerritory?.name,
          shortName: territory.short_name || localTerritory?.shortName,
          background: getLordHomeTerritoryBackground(territory, localTerritory?.background ?? castleCity),
          incomePerHour: clampLordHomeMetric(incomePerHour, localTerritory?.income ?? 0),
          heroHere: Boolean(territory.active_army_present ?? territory.hero_here),
          isOwned,
          isSelectable: territory.is_selectable !== false,
          status: territory.status ?? "controlled",
          garrisonCapacity: clampLordHomeMetric(garrisonCapacity, Math.max(8, stacks.length)),
          garrisonSlotsUsed: clampLordHomeMetric(garrisonSlotsUsed, stacks.length),
          activeArmyLockReason,
          recruitLockReason,
          buildingTreeLockReason,
          buildingNodeIds: buildingNodeIds ?? [],
          buildingNodes,
          lockReasons: territory.lock_reasons
        };

        for (const offer of territory.recruit_stock ?? []) {
          const cardId = offer.card_id ?? "";
          const unitId = lordHomeUnitIdByBackendCardId[cardId];
          if (!unitId) {
            continue;
          }
          const stock = Number(offer.current_stock ?? offer.stock ?? 0);
          const rate = Number(offer.rate_per_hour ?? 0);
          const cost = Number(offer.cost_per_unit ?? offer.cost ?? offer.unit?.cost ?? 0);
          const maxPurchasable = Number(offer.max_purchasable);
          const lockReason = offer.lock_reason || getLordHomeLockReasonMessage(offer.lock_reasons, ["recruit"], "");
          nextRecruitStock[localTerritoryId][unitId] = {
            rate: Number.isFinite(rate) ? rate : 0,
            stock: Number.isFinite(stock) && isLordHomeRecruitOfferUsable(offer.status ?? "available") ? stock : 0,
            status: offer.status ?? "available",
            cost: Number.isFinite(cost) ? cost : undefined,
            maxPurchasable: Number.isFinite(maxPurchasable) ? maxPurchasable : undefined,
            canRecruit: typeof offer.can_recruit === "boolean" ? offer.can_recruit : undefined,
            lockReason,
            purchasePayload: offer.purchase_payload
          };
        }
      }

      setGarrisons(nextGarrisons);
      setTerritoryRuntime(nextTerritoryRuntime);
      setRecruitStock(nextRecruitStock);
    } else {
      const backendTerritories = [
        ...(state.territories ?? []).map((territory) => ({ territory, isOwned: true })),
        ...(state.neutral_territories ?? []).map((territory) => ({ territory, isOwned: false })),
        ...(state.other_territories ?? []).map((territory) => ({ territory, isOwned: false }))
      ];
      if (backendTerritories.length > 0) {
      const activeNodeId = state.movement?.current_node_id ?? state.domain?.current_node_id;
      const nextGarrisons = lordHomeTerritories.reduce(
        (accumulator, territory) => ({ ...accumulator, [territory.id]: [] }),
        {} as Record<LordHomeTerritoryId, LordHomeStack[]>
      );
      const nextTerritoryRuntime: Partial<Record<LordHomeTerritoryId, LordHomeTerritoryRuntime>> = {};

      for (const { territory, isOwned } of backendTerritories) {
        const localTerritoryId = getLordHomeLocalTerritoryId(territory, isOwned);
        if (!localTerritoryId) {
          continue;
        }

        const localTerritory = lordHomeTerritories.find((item) => item.id === localTerritoryId);
        const backendTerritoryId = territory.territory_id ?? localTerritory?.backendTerritoryId ?? "";
        const stacks = getLordHomeStacksFromBackend(territory.garrisons);
        const incomePerHour = Number(territory.income_per_hour);
        const garrisonCapacity = Number(territory.fort?.garrison_capacity);
        const garrisonSlotsUsed = Number(territory.fort?.garrison_slots_used);
        const hasActiveNodeId = typeof activeNodeId === "string" && activeNodeId.length > 0;

        nextGarrisons[localTerritoryId] = stacks;
        nextTerritoryRuntime[localTerritoryId] = {
          backendTerritoryId,
          name: territory.name || territory.node_name || localTerritory?.name,
          incomePerHour: clampLordHomeMetric(incomePerHour, localTerritory?.income ?? 0),
          heroHere: hasActiveNodeId ? activeNodeId === territory.node_id : Boolean(localTerritory?.heroHere),
          isOwned,
          status: territory.status ?? "controlled",
          garrisonCapacity: clampLordHomeMetric(garrisonCapacity, Math.max(8, stacks.length)),
          garrisonSlotsUsed: clampLordHomeMetric(garrisonSlotsUsed, stacks.length)
        };
      }

      setGarrisons(nextGarrisons);
      setTerritoryRuntime(nextTerritoryRuntime);
      }
    }

    const nextOffers: Record<string, LordHomeRecruitOffer> = {};
    const recruitStockByUnitId: Partial<Record<LordHomeUnitId, number>> = {};
    const recruitRateByUnitId: Partial<Record<LordHomeUnitId, number>> = {};
    const reserveStockByUnitId: Partial<Record<LordHomeUnitId, number>> = {};
    for (const reserve of state.army_reserve ?? []) {
      if (reserve.status && reserve.status !== "available") {
        continue;
      }

      const unitId = lordHomeUnitIdByBackendCardId[reserve.card_id];
      const count = Number(reserve.count ?? 0);
      if (!unitId || !Number.isFinite(count) || count <= 0) {
        continue;
      }

      reserveStockByUnitId[unitId] = (reserveStockByUnitId[unitId] ?? 0) + count;
    }

    for (const offer of state.recruit_market ?? []) {
      const unit = offer.unit;
      const cost = Number(offer.cost ?? unit?.cost ?? 0);
      const unitId = lordHomeUnitIdByBackendCardId[offer.card_id];
      const explicitStock = Number(offer.current_stock ?? offer.stock);
      const rate = Number(offer.rate_per_hour ?? 0);
      const status = offer.status ?? "available";
      const stock = isLordHomeRecruitOfferUsable(status)
        ? Number.isFinite(explicitStock)
          ? explicitStock
          : unitId ? reserveStockByUnitId[unitId] ?? 0 : 0
        : 0;
      if (!isLordHomeRecruitOfferUsable(status)) {
        continue;
      }

      const previous = nextOffers[offer.card_id];
      if (previous && lordHomeRecruitStatusRank(previous.status) > lordHomeRecruitStatusRank(status)) {
        continue;
      }
      nextOffers[offer.card_id] = {
        offerId: offer.offer_id,
        cardId: offer.card_id,
        status,
        cost: Number.isFinite(cost) ? cost : 0,
        rate: Number.isFinite(rate) ? rate : 0,
        stock: Number.isFinite(stock) ? stock : 0
      };

      if (unitId) {
        recruitStockByUnitId[unitId] = Math.max(recruitStockByUnitId[unitId] ?? 0, Number.isFinite(stock) ? stock : 0);
        recruitRateByUnitId[unitId] = Math.max(recruitRateByUnitId[unitId] ?? 0, Number.isFinite(rate) ? rate : 0);
      }
    }
    if (Array.isArray(state.recruit_market)) {
      setRecruitOffersByCard(nextOffers);
    }

    if (Array.isArray(state.recruit_market) && backendTerritoryViews.length === 0) {
      setRecruitStock((current) => Object.fromEntries(
        Object.entries(current).map(([territoryId, units]) => [
          territoryId,
          Object.fromEntries(
            Object.entries(units).map(([unitId, value]) => [
              unitId,
              {
                ...value,
                rate: recruitRateByUnitId[unitId as LordHomeUnitId] ?? value.rate,
                stock: recruitStockByUnitId[unitId as LordHomeUnitId] ?? 0
              }
            ])
          )
        ])
      ) as Record<LordHomeTerritoryId, Record<LordHomeUnitId, { rate: number; stock: number }>>);
    }
  }, [apiBaseUrl, backendLordId, lordRuntimeMode]);

  const applyBackendSummary = useCallback((state: LordHomeBackendState) => {
    setLordUiState(adaptLordState(state, { mode: lordRuntimeMode }));
    setLordOrderReadOnlyReason("");

    const nextGold = Number(state.resources?.gold ?? state.domain?.gold);
    if (Number.isFinite(nextGold)) {
      setLordGold(nextGold);
    }

    const nextRaidTokens = Number(state.resources?.raid_tokens ?? state.raid_tokens ?? state.domain?.raid_tokens);
    if (Number.isFinite(nextRaidTokens)) {
      setRaidTokens(nextRaidTokens);
    }

    setDomainStats((current) => {
      const nextCurrentMp = Number(state.resources?.current_mp ?? state.movement?.current_mp ?? state.domain?.current_mp);
      const nextMpCap = Number(state.resources?.mp_cap ?? state.movement?.mp_cap ?? state.domain?.mp_cap);
      const nextRaidTokenCap = Number(state.resources?.raid_token_cap ?? state.domain?.raid_token_cap);

      return {
        ...current,
        currentMp: clampLordHomeMetric(nextCurrentMp, current.currentMp),
        mpCap: clampLordHomeMetric(nextMpCap, current.mpCap),
        raidTokenCap: clampLordHomeMetric(nextRaidTokenCap, current.raidTokenCap)
      };
    });
  }, [lordRuntimeMode]);

  const reloadLordHomeState = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
      headers: { "X-Role-Token": backendRoleToken },
      signal
    });
    const state = (await response.json().catch(() => ({}))) as LordHomeBackendState;
    if (!response.ok) {
      throw new Error(getLordHomeApiErrorMessage(state, "Канцелярия не отвечает"));
    }
    applyBackendState(state);
    return state;
  }, [apiBaseUrl, applyBackendState, backendLordId, backendRoleToken]);

  const refreshLordHomeStateInBackground = useCallback((
    source: string,
    options?: { refreshRecruit?: boolean }
  ) => {
    const request = { source, refreshRecruit: Boolean(options?.refreshRecruit) };
    if (backgroundStateRefreshInFlightRef.current) {
      backgroundStateRefreshQueuedRef.current = {
        source,
        refreshRecruit: Boolean(backgroundStateRefreshQueuedRef.current?.refreshRecruit || request.refreshRecruit)
      };
      return;
    }

    backgroundStateRefreshInFlightRef.current = true;
    void (async () => {
      try {
        if (request.refreshRecruit) {
          await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/recruit`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Role-Token": backendRoleToken
            },
            body: JSON.stringify({ action: "refresh", source: request.source })
          }).catch(() => undefined);
        }
        await reloadLordHomeState();
      } catch {
        // The accepted action stays visible locally; the regular poll will retry sync.
      } finally {
        backgroundStateRefreshInFlightRef.current = false;
        const queuedRequest = backgroundStateRefreshQueuedRef.current;
        backgroundStateRefreshQueuedRef.current = null;
        if (queuedRequest) {
          refreshLordHomeStateInBackground(queuedRequest.source, { refreshRecruit: queuedRequest.refreshRecruit });
        }
      }
    })();
  }, [apiBaseUrl, backendLordId, backendRoleToken, reloadLordHomeState]);

  useEffect(() => {
    if (cachedHomeStateAppliedRef.current || !initialHomeBackendStateRef.current) {
      return;
    }

    cachedHomeStateAppliedRef.current = true;
    applyBackendState(initialHomeBackendStateRef.current, { cache: false, stale: true });
  }, [applyBackendState]);

  useEffect(() => {
    localStorage.setItem("witcher_larp_lord_id", backendLordId);
    localStorage.setItem("witcher_larp_role_token", backendRoleToken);
  }, [backendLordId, backendRoleToken]);

  useEffect(() => {
    if (homeReadOnlyReason) {
      setLordOrderReadOnlyReason(homeReadOnlyReason);
      setLordRaidStatus(homeReadOnlyReason);
      setRecruitStatus(homeReadOnlyReason);
      setTransferStatus(homeReadOnlyReason);
    }
  }, [homeReadOnlyReason]);

  useEffect(() => {
    const filteredOrders = getLordHomeOrdersForFilter(lordOrders, lordOrderFilter);
    if (filteredOrders.length === 0) {
      setSelectedLordOrderId(null);
      return;
    }
    if (!filteredOrders.some((order) => order.order_id === selectedLordOrderId)) {
      setSelectedLordOrderId(filteredOrders[0].order_id);
    }
  }, [lordOrderFilter, lordOrders, selectedLordOrderId]);

  useEffect(() => {
    if (!lordRaidRules.some((rule) => rule.rule_id === selectedRaidRuleId)) {
      setSelectedRaidRuleId(lordRaidRules[0]?.rule_id ?? "");
    }
  }, [lordRaidRules, selectedRaidRuleId]);

  useEffect(() => {
    if (!lordRaidTargets.some((target) => target.target_territory_id === selectedRaidTargetId)) {
      setSelectedRaidTargetId(
        lordRaidTargets.find((target) => target.can_target)?.target_territory_id ??
        lordRaidTargets[0]?.target_territory_id ??
        ""
      );
    }
  }, [lordRaidTargets, selectedRaidTargetId]);

  useEffect(() => {
    if (selectedTerritory.id !== "castle" && selectedTerritoryRuntime && !selectedTerritoryRuntime.isOwned) {
      setSelectedTerritoryId("castle");
    }
  }, [selectedTerritory.id, selectedTerritoryRuntime]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setTimerNowMs(Date.now());
    }, lordHomeClockTickMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const loadBackendState = async (summaryOnly = false) => {
      if (stateFetchInFlightRef.current) {
        return;
      }

      stateFetchInFlightRef.current = true;
      try {
        const endpoint = summaryOnly ? "summary" : "state";
        const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/${endpoint}`, {
          headers: { "X-Role-Token": backendRoleToken },
          signal: controller.signal
        });
        const state = (await response.json().catch(() => ({}))) as LordHomeBackendState;
        if (!response.ok) {
          setLordUiState((current) => markLordUiStateOffline(current));
          setLordOrderReadOnlyReason(getLordHomeApiErrorMessage(state, "Канцелярия не отвечает. Действия временно закрыты."));
          return;
        }

        if (summaryOnly) {
          applyBackendSummary(state);
        } else {
          applyBackendState(state);
        }
      } catch {
        if (!controller.signal.aborted) {
          setLordUiState((current) => markLordUiStateOffline(current));
          setRecruitStatus("Сервер найма недоступен");
          setLordOrderReadOnlyReason("Связь с канцелярией потеряна. Видимые заказы сохранены, действия временно закрыты.");
        }
      } finally {
        stateFetchInFlightRef.current = false;
      }
    };

    loadBackendState();
    const intervalId = window.setInterval(() => loadBackendState(true), lordHomeStatePollMs);
    return () => {
      window.clearInterval(intervalId);
      controller.abort();
    };
  }, [apiBaseUrl, applyBackendState, applyBackendSummary, backendLordId, backendRoleToken]);

  useEffect(() => {
    if (!recruitUnitId) return;
    setRecruitQty((current) => clampRecruitQty(current, maxRecruitQty));
  }, [maxRecruitQty, recruitUnitId]);

  useEffect(() => {
    if (!transferDraft) return;
    setTransferQty((current) => clampRecruitQty(current, maxTransferQty));
  }, [maxTransferQty, transferDraft]);

  useEffect(() => {
    if (!selectedBuildingNodeIdSet || selectedBuildingNodeIdSet.has(selectedBuildingId)) {
      return;
    }
    const nextBuilding = selectedBuildingTreeNodes.find((building) => selectedBuildingNodeIdSet.has(building.id));
    if (nextBuilding) {
      setSelectedBuildingId(nextBuilding.id);
      setBuildingStatus("");
    }
  }, [selectedBuildingId, selectedBuildingNodeIdSet, selectedBuildingTreeNodes]);

  const buildSelectedBuilding = async (buildingId: string) => {
    if (isHomeReadOnly) {
      setBuildingStatus(homeReadOnlyReason);
      return;
    }
    if (selectedBuildingTreeLockReason) {
      setBuildingStatus(selectedBuildingTreeLockReason);
      return;
    }
    if (selectedBuildingNodeIdSet && !selectedBuildingNodeIdSet.has(buildingId)) {
      setBuildingStatus("Постройка недоступна в выбранной территории");
      return;
    }
    const building = selectedBuildingTreeNodes.find((item) => item.id === buildingId);
    if (!building || buildingPurchaseId || getLordBuildingState(building, selectedBuiltBuildingIds) !== "available") {
      return;
    }

    setBuildingPurchaseId(buildingId);
    setBuildingStatus("Отправляю приказ строительства");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/buildings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          building_id: buildingId,
          territory_id: selectedTerritoryBackendId,
          source: "lord_home_building_tree"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Строительство не выполнено"));
      }

      setBuildingStatus(`${building.name}: построено`);

      const stateResponse = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
        headers: { "X-Role-Token": backendRoleToken }
      });
      const state = (await stateResponse.json().catch(() => ({}))) as LordHomeBackendState;
      if (stateResponse.ok) {
        applyBackendState(state);
      }
    } catch (error) {
      const message = getLordHomeCaughtErrorMessage(error, "Сервер строительства недоступен");
      setBuildingStatus(message);
    } finally {
      setBuildingPurchaseId(null);
    }
  };

  const createLordHomeOrder = async (payload: LordHomeOrderCreatePayload) => {
    if (isHomeReadOnly) {
      setLordOrderReadOnlyReason(homeReadOnlyReason);
      setLordOrderStatus(homeReadOnlyReason);
      return;
    }
    if (isLordOrderSubmitting) {
      return;
    }

    setIsLordOrderSubmitting(true);
    setLordOrderStatus("Ставлю печать и удерживаю награду");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          action: "create",
          ...payload
        })
      });
      const result = (await response.json().catch(() => ({}))) as { order?: LordHomeOrder };
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(result, "Заказ не опубликован"));
      }

      if (result.order?.order_id) {
        setSelectedLordOrderId(result.order.order_id);
      }
      setLordOrderFilter("open");
      setLordOrderStatus("Заказ опубликован, награда под замком");
      await reloadLordHomeState();
    } catch (error) {
      const message = getLordHomeCaughtErrorMessage(error, "Заказ не опубликован");
      const isOfflineError = error instanceof Error && (
        error.message.includes("Failed to fetch") || error.message.includes("NetworkError")
      );
      if (isOfflineError) {
        setLordUiState((current) => markLordUiStateOffline(current));
        setLordOrderReadOnlyReason("Связь с канцелярией потеряна. Видимые заказы сохранены, действия временно закрыты.");
      }
      setLordOrderStatus(isOfflineError ? "Связь потеряна, заказ не опубликован" : message);
    } finally {
      setIsLordOrderSubmitting(false);
    }
  };

  const cancelLordHomeOrder = async (order: LordHomeOrder, reason: string) => {
    if (isHomeReadOnly) {
      setLordOrderReadOnlyReason(homeReadOnlyReason);
      setLordOrderStatus(homeReadOnlyReason);
      return;
    }
    if (isLordOrderSubmitting || !canCancelLordHomeOrder(order)) {
      return;
    }

    setIsLordOrderSubmitting(true);
    setLordOrderStatus("Отзываю заказ и возвращаю награду");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          action: "cancel",
          order_id: order.order_id,
          reason: reason.trim() || "Отозвано лордом",
          source: "stage2b_lord_home_orders"
        })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(result, "Заказ не отменен"));
      }

      setLordOrderStatus("Заказ отменен, награда возвращена");
      await reloadLordHomeState();
    } catch (error) {
      const message = getLordHomeCaughtErrorMessage(error, "Заказ не отменен");
      const isOfflineError = error instanceof Error && (
        error.message.includes("Failed to fetch") || error.message.includes("NetworkError")
      );
      if (isOfflineError) {
        setLordUiState((current) => markLordUiStateOffline(current));
        setLordOrderReadOnlyReason("Связь с канцелярией потеряна. Видимые заказы сохранены, действия временно закрыты.");
      }
      setLordOrderStatus(isOfflineError ? "Связь потеряна, заказ не отменен" : message);
    } finally {
      setIsLordOrderSubmitting(false);
    }
  };

  const startLordHomeRaid = async (payload: LordHomeRaidStartPayload) => {
    if (isHomeReadOnly) {
      setLordRaidStatus(homeReadOnlyReason);
      return;
    }
    if (isLordRaidSubmitting) {
      return;
    }

    setIsLordRaidSubmitting(true);
    setLordRaidStatus("Ставлю печать на план рейда");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/raids`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify(payload)
      });
      const result = (await response.json().catch(() => ({}))) as LordHomeRaidResponse;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(result, "Рейд не начат"));
      }

      if (typeof result.raid_tokens === "number") {
        setRaidTokens(result.raid_tokens);
      }
      if (typeof result.gold === "number") {
        setLordGold(result.gold);
      }
      if (Array.isArray(result.active_raid_effects) && result.active_raid_effects.length > 0) {
        setActiveRaidEffects((current) => [...result.active_raid_effects!, ...current]);
        setLordRaidHistory((current) => [...result.active_raid_effects!, ...current].slice(0, 8));
      }
      setLordRaidStatus(getLordHomeRaidResultText(result));
      await reloadLordHomeState();
    } catch (error) {
      setLordRaidStatus(getLordHomeCaughtErrorMessage(error, "Рейд не начат"));
    } finally {
      setIsLordRaidSubmitting(false);
    }
  };

  const openStackTransfer = (lane: "army" | "garrison", index: number) => {
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      return;
    }
    const stack = lane === "army" ? army[index] : selectedGarrison[index];
    if (!stack) {
      return;
    }
    if (!selectedHeroHere) {
      setTransferStatus(selectedActiveArmyLockReason);
      return;
    }

    setRecruitUnitId(null);
    setTransferDraft({ lane, index, mode: "transfer" });
    setTransferQty(clampRecruitQty(1, stack.count));
    setTransferStatus("");
  };

  const setCurrentDragPayload = (payload: LordHomeDragPayload) => {
    dragPayloadRef.current = payload;
    setDragPayload(payload);
  };

  const startPointerStackDrag = (
    payload: Exclude<LordHomeDragPayload, null>,
    point: { x: number; y: number }
  ) => {
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      return;
    }
    pointerDragRef.current = {
      payload,
      startX: point.x,
      startY: point.y,
      moved: false
    };
    setCurrentDragPayload(payload);
  };

  const updatePointerStackDrag = (point: { x: number; y: number }) => {
    const pointerDrag = pointerDragRef.current;
    if (!pointerDrag || pointerDrag.moved) {
      return;
    }

    pointerDrag.moved = Math.hypot(point.x - pointerDrag.startX, point.y - pointerDrag.startY) > 10;
  };

  const getPointerStackDropTarget = (
    point: { x: number; y: number }
  ): { lane: "army" | "garrison"; index?: number } | null => {
    const pointElement = document.elementFromPoint(point.x, point.y);
    const laneElement = pointElement?.closest<HTMLElement>(".lord-home-lane");
    const toLane = laneElement?.dataset.lane === "army" || laneElement?.dataset.lane === "garrison"
      ? laneElement.dataset.lane
      : undefined;
    if (!laneElement || !toLane || (toLane === "army" && !selectedHeroHere)) {
      return null;
    }

    const directSlot = pointElement?.closest<HTMLButtonElement>(".lord-home-unit-slot");
    if (
      directSlot &&
      laneElement.contains(directSlot) &&
      directSlot.classList.contains("is-filled") &&
      !directSlot.disabled
    ) {
      const index = Number(directSlot.dataset.slotIndex);
      return Number.isFinite(index) ? { lane: toLane, index } : { lane: toLane };
    }

    const filledSlots = Array.from(
      laneElement.querySelectorAll<HTMLButtonElement>(".lord-home-unit-slot.is-filled:not(:disabled)")
    );
    let bestTarget: { index: number; distance: number } | null = null;
    for (const slot of filledSlots) {
      const rect = slot.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const deltaX = Math.abs(point.x - centerX);
      const deltaY = Math.abs(point.y - centerY);
      const horizontalRadius = Math.max(36, rect.width * 0.8);
      const verticalRadius = Math.max(34, rect.height * 0.7);
      if (deltaX > horizontalRadius || deltaY > verticalRadius) {
        continue;
      }

      const index = Number(slot.dataset.slotIndex);
      if (!Number.isFinite(index)) {
        continue;
      }

      const distance = Math.hypot(deltaX, deltaY);
      if (!bestTarget || distance < bestTarget.distance) {
        bestTarget = { index, distance };
      }
    }

    return typeof bestTarget?.index === "number"
      ? { lane: toLane, index: bestTarget.index }
      : { lane: toLane };
  };

  const finishPointerStackDrop = (
    point: { x: number; y: number }
  ) => {
    const pointerDrag = pointerDragRef.current;
    if (!pointerDrag) {
      return false;
    }

    updatePointerStackDrag(point);
    pointerDragRef.current = null;
    if (!pointerDrag.moved) {
      setCurrentDragPayload(null);
      return false;
    }
    suppressNextStackClickUntilRef.current = Date.now() + 350;

    const target = getPointerStackDropTarget(point);
    if (!target) {
      setCurrentDragPayload(null);
      return true;
    }

    const isSameSlot = pointerDrag.payload.lane === target.lane && pointerDrag.payload.index === target.index;
    if (isSameSlot) {
      setCurrentDragPayload(null);
      return true;
    }

    handleStackDrop(target.lane, target.index);
    return true;
  };

  const openStackSplit = (lane: "army" | "garrison", index: number) => {
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      return;
    }
    const stack = lane === "army" ? army[index] : selectedGarrison[index];
    if (!stack) {
      return;
    }
    if (lane === "army" && !selectedHeroHere) {
      setTransferStatus(selectedActiveArmyLockReason);
      return;
    }

    setRecruitUnitId(null);
    setTransferDraft({ lane, index, mode: "split" });
    setTransferQty(clampRecruitQty(1, Math.max(0, stack.count - 1)));
    setTransferStatus(stack.count <= 1 ? "Эту пачку нельзя разделить" : "");
  };

  const mergeStacksLocally = (lane: "army" | "garrison", sourceIndex: number, targetIndex: number) => {
    if (lane === "army") {
      setArmy((current) => mergeLordHomeStackList(current, sourceIndex, targetIndex));
      return;
    }

    setGarrisons((current) => ({
      ...current,
      [selectedTerritory.id]: mergeLordHomeStackList(current[selectedTerritory.id] ?? [], sourceIndex, targetIndex)
    }));
  };

  const updateStackLaneLocally = (
    lane: "army" | "garrison",
    territoryId: LordHomeTerritoryId,
    updater: (stacks: LordHomeStack[]) => LordHomeStack[]
  ) => {
    if (lane === "army") {
      setArmy((current) => updater(current));
      return;
    }

    setGarrisons((current) => ({
      ...current,
      [territoryId]: updater(current[territoryId] ?? [])
    }));
  };

  const getBackendTargetStack = (
    payload: LordHomeTransferActionResponse,
    unitId: LordHomeUnitId,
    fallbackCount: number
  ): LordHomeStack => {
    const backendStack = getLordHomeStacksFromBackend(payload.target_stack ? [payload.target_stack] : [])[0];
    return backendStack ?? {
      unitId,
      count: fallbackCount
    };
  };

  const splitStackLocally = (
    lane: "army" | "garrison",
    territoryId: LordHomeTerritoryId,
    sourceIndex: number,
    unitId: LordHomeUnitId,
    splitCount: number,
    payload: LordHomeTransferActionResponse
  ) => {
    const targetStack = getBackendTargetStack(payload, unitId, splitCount);
    const payloadSourceRemaining = Number(payload.source_remaining);
    updateStackLaneLocally(lane, territoryId, (stacks) => {
      const sourceStack = stacks[sourceIndex];
      if (!sourceStack) {
        return stacks;
      }

      const next = stacks.map((stack) => ({ ...stack }));
      const sourceRemaining = Number.isFinite(payloadSourceRemaining)
        ? Math.max(0, payloadSourceRemaining)
        : Math.max(0, sourceStack.count - splitCount);
      if (sourceRemaining > 0) {
        next[sourceIndex] = { ...sourceStack, count: sourceRemaining };
      } else {
        next.splice(sourceIndex, 1);
      }
      next.splice(Math.min(sourceIndex + 1, next.length), 0, targetStack);
      return next;
    });
  };

  const moveStackLocally = (
    fromLane: "army" | "garrison",
    territoryId: LordHomeTerritoryId,
    sourceIndex: number,
    unitId: LordHomeUnitId,
    movedCount: number,
    payload: LordHomeTransferActionResponse
  ) => {
    const toLane = fromLane === "army" ? "garrison" : "army";
    const targetStack = getBackendTargetStack(payload, unitId, movedCount);
    updateStackLaneLocally(fromLane, territoryId, (stacks) => {
      const sourceStack = stacks[sourceIndex];
      if (!sourceStack) {
        return stacks;
      }

      const next = stacks.map((stack) => ({ ...stack }));
      const sourceRemaining = Math.max(0, sourceStack.count - movedCount);
      if (sourceRemaining > 0) {
        next[sourceIndex] = { ...sourceStack, count: sourceRemaining };
      } else {
        next.splice(sourceIndex, 1);
      }
      return next;
    });
    updateStackLaneLocally(toLane, territoryId, (stacks) => {
      const next = stacks.map((stack) => ({ ...stack }));
      if (targetStack.stackId) {
        const existingIndex = next.findIndex((stack) => stack.stackId === targetStack.stackId);
        if (existingIndex >= 0) {
          next[existingIndex] = targetStack;
          return next;
        }
      }
      next.push(targetStack);
      return next;
    });
  };

  const addRecruitToGarrisonLocally = (
    territoryId: LordHomeTerritoryId,
    unitId: LordHomeUnitId,
    backendCardId: string,
    count: number,
    goldSpent: number
  ) => {
    setLordGold((current) => Math.max(0, current - goldSpent));
    setRecruitStock((current) => {
      const territoryStock = current[territoryId];
      const unitStock = territoryStock?.[unitId];
      if (!territoryStock || !unitStock) {
        return current;
      }

      const nextMaxPurchasable = Number.isFinite(unitStock.maxPurchasable)
        ? Math.max(0, Number(unitStock.maxPurchasable) - count)
        : unitStock.maxPurchasable;
      return {
        ...current,
        [territoryId]: {
          ...territoryStock,
          [unitId]: {
            ...unitStock,
            stock: Math.max(0, unitStock.stock - count),
            maxPurchasable: nextMaxPurchasable
          }
        }
      };
    });
    setRecruitOffersByCard((current) => {
      const offer = current[backendCardId];
      if (!offer) {
        return current;
      }
      return {
        ...current,
        [backendCardId]: {
          ...offer,
          stock: Math.max(0, offer.stock - count)
        }
      };
    });
    setGarrisons((current) => {
      const stacks = current[territoryId] ?? [];
      const existingIndex = stacks.findIndex((stack) => stack.unitId === unitId);
      const next = stacks.map((stack) => ({ ...stack }));
      if (existingIndex >= 0) {
        next[existingIndex] = {
          ...next[existingIndex],
          count: next[existingIndex].count + count
        };
      } else {
        next.push({ unitId, count });
      }
      return { ...current, [territoryId]: next };
    });
  };

  const mergeStackDropLocally = (
    from: Exclude<LordHomeDragPayload, null>,
    to: { lane: "army" | "garrison"; index: number },
    sourceStack: LordHomeStack,
    territoryId: LordHomeTerritoryId = selectedTerritory.id
  ) => {
    if (from.lane === to.lane) {
      mergeStacksLocally(from.lane, from.index, to.index);
      return;
    }

    if (from.lane === "army") {
      setArmy((current) => {
        const next = current.map((stack) => ({ ...stack }));
        next.splice(from.index, 1);
        return next;
      });
      setGarrisons((current) => {
        const stacks = current[territoryId] ?? [];
        const targetStack = stacks[to.index];
        if (!targetStack || targetStack.unitId !== sourceStack.unitId) {
          return current;
        }
        const next = stacks.map((stack) => ({ ...stack }));
        next[to.index] = {
          ...targetStack,
          count: targetStack.count + sourceStack.count
        };
        return { ...current, [territoryId]: next };
      });
      return;
    }

    setGarrisons((current) => {
      const stacks = current[territoryId] ?? [];
      const next = stacks.map((stack) => ({ ...stack }));
      next.splice(from.index, 1);
      return { ...current, [territoryId]: next };
    });
    setArmy((current) => {
      const targetStack = current[to.index];
      if (!targetStack || targetStack.unitId !== sourceStack.unitId) {
        return current;
      }
      const next = current.map((stack) => ({ ...stack }));
      next[to.index] = {
        ...targetStack,
        count: targetStack.count + sourceStack.count
      };
      return next;
    });
  };

  const submitStackMerge = async (
    from: Exclude<LordHomeDragPayload, null>,
    to: { lane: "army" | "garrison"; index: number }
  ) => {
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      setCurrentDragPayload(null);
      return;
    }
    const sourceStack = from.lane === "army" ? army[from.index] : selectedGarrison[from.index];
    const targetStack = to.lane === "army" ? army[to.index] : selectedGarrison[to.index];
    if (!sourceStack || !targetStack || isTransferSubmitting) {
      return;
    }
    const isSameLane = from.lane === to.lane;
    if (isSameLane && from.index === to.index) {
      setCurrentDragPayload(null);
      return;
    }
    if (sourceStack.unitId !== targetStack.unitId) {
      setTransferStatus("Складывать можно только одинаковые пачки");
      setCurrentDragPayload(null);
      return;
    }

    const unit = lordHomeUnitCatalog[sourceStack.unitId];
    const frontendTerritoryId = selectedTerritory.id;
    setRecruitUnitId(null);
    setTransferDraft(null);

    if (!sourceStack.stackId || !targetStack.stackId) {
      mergeStackDropLocally(from, to, sourceStack);
      setTransferStatus(`${unit.name}: пачки объединены`);
      setCurrentDragPayload(null);
      return;
    }

    setIsTransferSubmitting(true);
    setTransferStatus("Отправляю приказ");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/garrisons/transfer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          operation: isSameLane
            ? from.lane === "army"
              ? "merge_active"
              : "merge_garrison"
            : from.lane === "army"
              ? "active_to_fort"
              : "fort_to_active",
          territory_id: selectedTerritoryBackendId,
          card_id: unit.backendCardId,
          stack_id: sourceStack.stackId,
          target_stack_id: targetStack.stackId,
          count: isSameLane ? 1 : sourceStack.count,
          source: "lord_home_stack_merge"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Объединение не выполнено"));
      }

      mergeStackDropLocally(from, to, sourceStack, frontendTerritoryId);
      setTransferStatus(`${unit.name}: пачки объединены`);
      refreshLordHomeStateInBackground("lord_home_stack_merge");
    } catch (error) {
      setTransferStatus(getLordHomeCaughtErrorMessage(error, "Объединение не выполнено"));
    } finally {
      setIsTransferSubmitting(false);
      setCurrentDragPayload(null);
    }
  };

  const handleStackDrop = (toLane: "army" | "garrison", targetIndex?: number) => {
    pointerDragRef.current = null;
    const droppedPayload = dragPayloadRef.current ?? dragPayload;
    if (!droppedPayload) {
      return;
    }
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      setCurrentDragPayload(null);
      return;
    }

    if (typeof targetIndex === "number") {
      void submitStackMerge(droppedPayload, { lane: toLane, index: targetIndex });
      return;
    }

    if (droppedPayload.lane !== toLane) {
      openStackTransfer(droppedPayload.lane, droppedPayload.index);
    }
    setCurrentDragPayload(null);
  };

  const submitStackTransfer = async () => {
    if (isHomeReadOnly) {
      setTransferStatus(homeReadOnlyReason);
      return;
    }
    if (!transferDraft || !transferStack || !transferUnit || !transferCanSubmit) {
      return;
    }
    const currentTransferDraft = transferDraft;
    const currentTransferStack = transferStack;
    const currentTransferUnit = transferUnit;
    const frontendTerritoryId = selectedTerritory.id;
    const targetTerritoryId = selectedTerritoryBackendId;
    const operation = currentTransferDraft.mode === "split"
      ? currentTransferDraft.lane === "army"
        ? "split_active"
        : "split_garrison"
      : currentTransferDraft.lane === "army"
        ? "active_to_fort"
        : "fort_to_active";
    const count = clampRecruitQty(transferQty, currentTransferStack.count);
    const clampedCount = currentTransferDraft.mode === "split"
      ? clampRecruitQty(transferQty, Math.max(0, currentTransferStack.count - 1))
      : count;

    setIsTransferSubmitting(true);
    setTransferStatus("Отправляю приказ");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/garrisons/transfer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          operation,
          territory_id: targetTerritoryId,
          card_id: currentTransferUnit.backendCardId,
          stack_id: currentTransferStack.stackId,
          count: clampedCount,
          source: "lord_home_stack_transfer"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Перенос не выполнен"));
      }

      const result = payload as LordHomeTransferActionResponse;
      if (currentTransferDraft.mode === "split") {
        splitStackLocally(
          currentTransferDraft.lane,
          frontendTerritoryId,
          currentTransferDraft.index,
          currentTransferStack.unitId,
          clampedCount,
          result
        );
      } else {
        moveStackLocally(
          currentTransferDraft.lane,
          frontendTerritoryId,
          currentTransferDraft.index,
          currentTransferStack.unitId,
          clampedCount,
          result
        );
      }
      setTransferStatus(currentTransferDraft.mode === "split"
        ? `${currentTransferUnit.name}: пачка разделена`
        : `${currentTransferUnit.name}: перенесено ${clampedCount}`);
      setTransferDraft(null);
      refreshLordHomeStateInBackground("lord_home_stack_transfer");
    } catch (error) {
      setTransferStatus(getLordHomeCaughtErrorMessage(error, "Перенос не выполнен"));
    } finally {
      setIsTransferSubmitting(false);
    }
  };

  const hireRecruit = async () => {
    if (isHomeReadOnly) {
      setRecruitStatus(homeReadOnlyReason);
      return;
    }
    if (effectiveRecruitLockReason) {
      setRecruitStatus(effectiveRecruitLockReason);
      return;
    }
    if (recruitStockAvailable < 1) {
      setRecruitStatus(recruitNoStockReason);
      return;
    }
    if (recruitBlockedByGarrisonCap) {
      setRecruitStatus("Нет свободного слота в гарнизоне");
      return;
    }
    if (recruitAffordableQty < 1) {
      setRecruitStatus("Недостаточно золота");
      return;
    }
    if (!recruitUnitId || !recruitUnit || !recruitHasOffer || !recruitCanSubmit) {
      return;
    }
    const currentRecruitUnitId = recruitUnitId;
    const currentRecruitUnit = recruitUnit;
    const requestedRecruitQty = recruitQty;
    const requestedRecruitCost = recruitTotalCost;
    const frontendTerritoryId = selectedTerritory.id;
    const targetTerritoryId = selectedTerritoryBackendId;
    if (!targetTerritoryId) {
      setRecruitStatus("Территория найма не выбрана");
      return;
    }

    setIsRecruitHiring(true);
    setRecruitStatus("Отправляю приказ найма");
    try {
      const recruitPurchasePayload = recruitStockInfo?.purchasePayload;
      const recruitRequestBody = {
        ...(recruitPurchasePayload ?? {
          action: "purchase_stock",
          card_id: currentRecruitUnit.backendCardId
        }),
        action: recruitPurchasePayload?.action ?? "purchase_stock",
        card_id: recruitPurchasePayload?.card_id ?? currentRecruitUnit.backendCardId,
        quantity: requestedRecruitQty,
        territory_id: recruitPurchasePayload?.territory_id ?? targetTerritoryId,
        source: "lord_home_recruit_modal"
      };
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/recruit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify(recruitRequestBody)
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Найм не выполнен"));
      }

      const result = payload as LordHomeRecruitActionResponse;
      if (result.status !== "hired" || result.territory_id !== targetTerritoryId) {
        throw new Error("Сервер не подтвердил найм в гарнизон");
      }
      const hiredCount = Number(result.count ?? requestedRecruitQty);
      const safeHiredCount = Math.max(0, Number.isFinite(hiredCount) ? hiredCount : requestedRecruitQty);
      const goldSpent = Number(result.gold_spent ?? requestedRecruitCost);
      const safeGoldSpent = Math.max(0, Number.isFinite(goldSpent) ? goldSpent : requestedRecruitCost);
      const acceptedText = `${currentRecruitUnit.name}: нанято ${safeHiredCount}`;

      addRecruitToGarrisonLocally(
        frontendTerritoryId,
        currentRecruitUnitId,
        currentRecruitUnit.backendCardId,
        safeHiredCount,
        safeGoldSpent
      );
      setRecruitStatus(acceptedText);
      setRecruitUnitId(null);
      refreshLordHomeStateInBackground("lord_home_recruit_modal", { refreshRecruit: true });
    } catch (error) {
      setRecruitStatus(getLordHomeCaughtErrorMessage(error, "Найм не выполнен"));
    } finally {
      setIsRecruitHiring(false);
    }
  };

  const openRecruitModal = (unitId: LordHomeUnitId) => {
    setTransferDraft(null);
    setRecruitUnitId(unitId);
    const unit = lordHomeUnitCatalog[unitId];
    const stockInfo = recruitStock[selectedTerritory.id]?.[unitId];
    const offer = recruitOffersByCard[unit.backendCardId];
    const stock = stockInfo?.stock ?? offer?.stock ?? 0;
    const unitCost = Math.max(0, stockInfo?.cost ?? offer?.cost ?? unit.cost);
    const affordable = unitCost > 0 ? Math.floor(lordGold / unitCost) : stock;
    const maxPurchasable = stockInfo?.maxPurchasable ?? Number.POSITIVE_INFINITY;
    setRecruitQty(clampRecruitQty(1, Math.min(stock, affordable, maxPurchasable)));
    setRecruitStatus(selectedRecruitLockReason || stockInfo?.lockReason || "");
  };

  const setRecruitQtyFromTrack = (clientX: number, track: HTMLElement) => {
    if (maxRecruitQty < 1) {
      return;
    }

    const rect = track.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const nextQty = maxRecruitQty > 1 ? Math.round(1 + ratio * (maxRecruitQty - 1)) : 1;
    setRecruitQty(Math.max(1, Math.min(maxRecruitQty, nextQty)));
  };

  return (
    <main className="lord-home-game-screen" onContextMenu={(event) => event.preventDefault()}>
      <div className="lord-home-game-stage">
        {homeView === "buildings" ? (
          <>
            <LordHomeBuildingIconLayer
              buildingNodes={selectedBuildingTreeNodes}
              builtBuildingIds={selectedBuiltBuildingIds}
              selectedBuildingId={selectedBuildingId}
              visibleBuildingIds={selectedBuildingNodeIdSet}
            />
            <motion.img
              className="lord-home-building-bg"
              src={buildingTreeBg}
              alt=""
              draggable={false}
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.01 }}
              animate={prefersReducedMotion ? undefined : { opacity: 1, scale: [1, 1.012, 1] }}
              transition={prefersReducedMotion ? undefined : { opacity: { duration: 0.22 }, scale: { duration: 32, repeat: Infinity, ease: "easeInOut" } }}
            />
            <LordHomeBuildingTree
              buildingNodes={selectedBuildingTreeNodes}
              builtBuildingIds={selectedBuiltBuildingIds}
              selectedBuildingId={selectedBuildingId}
              buildingStatus={buildingStatus}
              buildingPurchaseId={buildingPurchaseId}
              visibleBuildingIds={selectedBuildingNodeIdSet}
              scopedLockReason={selectedBuildingTreeLockReason}
              onSelectBuilding={(buildingId) => {
                setSelectedBuildingId(buildingId);
                if (!buildingPurchaseId) {
                  setBuildingStatus("");
                }
              }}
              onBuild={buildSelectedBuilding}
            />
          </>
        ) : homeView === "raids" ? (
          <>
            <motion.img
              className="lord-home-building-bg lord-raid-war-table-bg"
              src={buildingTreeBg}
              alt=""
              draggable={false}
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.01 }}
              animate={prefersReducedMotion ? undefined : { opacity: 1, scale: [1, 1.008, 1] }}
              transition={prefersReducedMotion ? undefined : { opacity: { duration: 0.22 }, scale: { duration: 36, repeat: Infinity, ease: "easeInOut" } }}
            />
            <div className="lord-raid-table-grade" />
          </>
        ) : (
          <>
            <motion.div
              className="lord-home-game-bg"
              style={{ backgroundImage: `url(${selectedTerritoryBackground})` }}
              key={`${selectedTerritory.id}-${selectedTerritoryBackendId}`}
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.025 }}
              animate={prefersReducedMotion ? undefined : { opacity: 1, scale: [1.015, 1.035, 1.015] }}
              transition={prefersReducedMotion ? undefined : { opacity: { duration: 0.35 }, scale: { duration: 34, repeat: Infinity, ease: "easeInOut" } }}
            />
            <div className="lord-home-game-grade" />
          </>
        )}
        <img className="lord-home-hud-overlay" src={lordHomeHudOverlay} alt="" draggable={false} />

        {homeReadOnlyReason ? (
          <div className="lord-home-readonly-banner" role="status">
            <Wifi size={14} />
            <span>{homeReadOnlyReason}</span>
          </div>
        ) : null}

        {homeView === "orders" ? (
          <LordHomeOrdersBoard
            orders={lordOrders}
            orderCap={lordOrderCap}
            escrow={lordOrderEscrow}
            orderConflicts={lordOrderConflicts}
            targets={lordOrderTargets}
            recipients={lordOrderRecipients}
            filterId={lordOrderFilter}
            selectedOrderId={selectedLordOrderId}
            lordGold={lordGold}
            actionStatus={lordOrderStatus}
            readOnlyReason={lordOrderReadOnlyReason}
            isSubmitting={isLordOrderSubmitting}
            onFilterChange={setLordOrderFilter}
            onSelectOrder={setSelectedLordOrderId}
            onCreateOrder={(payload) => void createLordHomeOrder(payload)}
            onCancelOrder={(order, reason) => void cancelLordHomeOrder(order, reason)}
            onStatus={setLordOrderStatus}
          />
        ) : null}

        {homeView === "raids" ? (
          <LordHomeRaidsBoard
            rules={lordRaidRules}
            targets={lordRaidTargets}
            activeEffects={activeRaidEffects}
            raidHistory={lordRaidHistory}
            raidTokens={raidTokens}
            actionStatus={lordRaidStatus}
            isSubmitting={isLordRaidSubmitting}
            selectedRuleId={selectedRaidRuleId}
            selectedTargetId={selectedRaidTargetId}
            onSelectRule={setSelectedRaidRuleId}
            onSelectTarget={setSelectedRaidTargetId}
            onStart={(payload) => void startLordHomeRaid(payload)}
          />
        ) : null}

        <header className="lord-home-top-strip">
          <LordHomeTimerChip timerSummary={timerSummary} nowMs={timerNowMs} />
          <div className="lord-home-resource-row">
            <div className="lord-home-resource gold"><Coins size={14} /><b>{goldResourceLabel}</b><span>({incomeResourceLabel})</span></div>
            <div className="lord-home-resource wood"><Archive size={14} /><b>{territoryIncomeResourceLabel}</b><span>земли</span></div>
            <div className="lord-home-resource violet"><Route size={14} /><b>{currentMovementPoints}/{movementPointCap}</b><span>MP</span></div>
            <div className="lord-home-resource blue"><Swords size={14} /><b>{armyResourceLabel}</b><span>армия</span></div>
            <div className="lord-home-resource red"><Flame size={14} /><b>{raidResourceLabel}</b><span>рейды</span></div>
            <div className="lord-home-resource iron"><Shield size={14} /><b>{garrisonResourceLabel}</b><span>гарнизон</span></div>
            <div className="lord-home-resource green"><Users size={14} /><b>{displayedTerritoryBubbles.length + 1}</b><span>владения</span></div>
          </div>
          <button className="lord-home-top-icon help" type="button" aria-label="Обучение" onClick={() => setOpenPanel("help")}>
            <LordHomeActionIcon src={lordHomeActionHelpIcon} />
          </button>
          <button className="lord-home-top-icon logout" type="button" aria-label="Выход" onClick={() => window.location.assign(withLordRuntimeQuery("/lords/login", apiBaseUrl))}>
            <LordHomeActionIcon src={lordHomeActionLogoutIcon} />
          </button>
        </header>

        <nav className="lord-home-left-dock" aria-label="Основные действия лорда">
          {lordHomeActionDock.map((action) => (
            <button
              key={action.id}
              className={`lord-home-dock-button action-${action.id} ${action.tone}${"alert" in action && action.alert && activeBattle ? " is-alert" : ""}${action.id === homeView ? " is-selected" : ""}`}
              type="button"
              aria-label={action.label}
              onClick={() => {
                if (action.id === "buildings") {
                  setHomeView((current) => current === "buildings" ? "territory" : "buildings");
                  setOpenPanel(null);
                  return;
                }

                if (action.id === "orders") {
                  setHomeView((current) => current === "orders" ? "territory" : "orders");
                  setOpenPanel(null);
                  return;
                }

                if (action.id === "raids") {
                  setHomeView((current) => current === "raids" ? "territory" : "raids");
                  setOpenPanel(null);
                  return;
                }

                if (action.id === "map") {
                  window.location.assign(useDemoState
                    ? withLordRuntimeQuery(lordMapPath, apiBaseUrl)
                    : withLordRuntimeQuery("/lords/map", apiBaseUrl));
                  return;
                }

                if (action.id === "battle") {
                  if (!activeBattleId) {
                    setOpenPanel(null);
                    return;
                  }
                  window.location.assign(withLordRuntimeQuery(
                    `/lords/battle?battle_id=${activeBattleId}&return_to=home`,
                    apiBaseUrl,
                    { lordId: backendLordId, roleToken: backendRoleToken }
                  ));
                  return;
                }
              }}
            >
              <LordHomeActionIcon src={action.icon} />
              <span className="lord-home-dock-label">{action.label}</span>
            </button>
          ))}
        </nav>

        <button className="lord-home-minimap-frame" type="button" aria-label="Открыть карту земель" onClick={() => window.location.assign(withLordRuntimeQuery(lordMapPath, apiBaseUrl))}>
          <img src={lordHomeMinimap} alt="" draggable={false} />
          <span />
        </button>

            {homeView !== "orders" ? (
            <section className="lord-home-bottom-panel" aria-label="Армия, гарнизон и найм">
              <div className="lord-home-location-title">{selectedTerritoryName}</div>
              <div className="lord-home-local-income">
                +{selectedIncomePerHour}/тик · Г {selectedGarrisonSlotsUsed}/{selectedGarrisonCapacity} · А {domainStats.activeArmySlotsUsed}/{domainStats.activeArmyCapacity}
              </div>

              <LordHomeLane
                lane="army"
                label="Армия"
                stacks={selectedHeroHere ? army : []}
                locked={!selectedHeroHere}
                onStackClick={(index) => openStackSplit("army", index)}
                activeDragPayload={dragPayload}
                onDrop={() => handleStackDrop("army")}
                onPointerStart={(payload, point) => startPointerStackDrag(payload, point)}
                onPointerMove={(point) => updatePointerStackDrag(point)}
                onPointerDrop={(point) => finishPointerStackDrop(point)}
                onSuppressStackClick={() => {
                  if (Date.now() > suppressNextStackClickUntilRef.current) {
                    suppressNextStackClickUntilRef.current = 0;
                    return false;
                  }
                  suppressNextStackClickUntilRef.current = 0;
                  return true;
                }}
              />
              <LordHomeLane
                lane="garrison"
                label="Гарнизон"
                stacks={selectedGarrison}
                locked={false}
                onStackClick={(index) => openStackSplit("garrison", index)}
                activeDragPayload={dragPayload}
                onDrop={() => handleStackDrop("garrison")}
                onPointerStart={(payload, point) => startPointerStackDrag(payload, point)}
                onPointerMove={(point) => updatePointerStackDrag(point)}
                onPointerDrop={(point) => finishPointerStackDrop(point)}
                onSuppressStackClick={() => {
                  if (Date.now() > suppressNextStackClickUntilRef.current) {
                    suppressNextStackClickUntilRef.current = 0;
                    return false;
                  }
                  suppressNextStackClickUntilRef.current = 0;
                  return true;
                }}
              />

              {selectedActiveArmyLockReason ? <div className="lord-home-army-lock">{selectedActiveArmyLockReason}</div> : null}
              {selectedRecruitLockReason ? <div className="lord-home-army-lock">{selectedRecruitLockReason}</div> : null}

              <div className="lord-home-recruit-grid">
                {displayedRecruitUnitIds.map((unitId, index) => {
                  if (!unitId) {
                    return <div key={`empty-${index}`} className="lord-home-recruit-card is-empty" />;
                  }

                  const unit = lordHomeUnitCatalog[unitId];
                  const stockInfo = recruitStock[selectedTerritory.id]?.[unitId] ?? { rate: 0, stock: 0 };

                  return (
                    <button
                      key={unitId}
                      className={`lord-home-recruit-card${stockInfo.stock < 1 ? " is-depleted" : ""}`}
                      type="button"
                      onClick={() => openRecruitModal(unitId)}
                    >
                      <img src={unit.icon} alt="" draggable={false} />
                      <span className="lord-home-recruit-count">+{stockInfo.rate} ({stockInfo.stock})</span>
                    </button>
                  );
                })}
              </div>
            </section>
            ) : null}

        {homeView === "territory" ? (
            <aside className="lord-home-territory-bubbles" aria-label="Захваченные территории">
              {displayedTerritoryBubbles.map((territory) => (
                <button
                  key={territory.id}
                  className={`lord-home-territory-bubble${territory.id === selectedTerritory.id ? " is-selected" : ""}`}
                  type="button"
                  onClick={() => {
                    setHomeView("territory");
                    setSelectedTerritoryId(territory.id);
                  }}
                  aria-label={territory.name}
                >
                  <img src={territory.background} alt="" draggable={false} />
                  <span>{territory.shortName}</span>
                </button>
              ))}
            </aside>
        ) : null}

        <LordMpHud
          className="lord-home-act-widget"
          currentMp={lordUiState.mp.isKnown || useDemoState ? currentMovementPoints : null}
          mpCap={lordUiState.mp.isKnown || useDemoState ? movementPointCap : null}
        />

        <AnimatePresence>
          {recruitUnit && recruitUnitId ? (
            <motion.div className="lord-home-modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <motion.section
                className="lord-home-recruit-modal"
                initial={prefersReducedMotion ? false : { y: 24, scale: 0.96 }}
                animate={prefersReducedMotion ? undefined : { y: 0, scale: 1 }}
                exit={prefersReducedMotion ? undefined : { y: 18, scale: 0.97 }}
              >
                <img className="lord-home-recruit-modal-frame" src={lordHomeRecruitModalFrame} alt="" draggable={false} />
                <button className="lord-home-modal-close" type="button" onClick={() => setRecruitUnitId(null)} aria-label="Закрыть">
                  ×
                </button>
                <div className="lord-home-recruit-portrait">
                  <img src={recruitUnit.icon} alt="" draggable={false} />
                </div>
                <div className="lord-home-recruit-info">
                  <span>{recruitUnit.role}</span>
                  <h2>{recruitUnit.name}</h2>
                  <div className="lord-home-unit-stats">
                    <b><span>АТК</span>{recruitUnit.attack}</b>
                    <b><span>ЗЩТ</span>{recruitUnit.defense}</b>
                    <b><span>HP</span>{recruitUnit.hp}</b>
                    <b><span>ДАЛЬ</span>{recruitUnit.attackRange}</b>
                    <b><span>ИНИЦ</span>{recruitUnit.initiative}</b>
                    <b><span>ХОД</span>{recruitUnit.moveRange}</b>
                  </div>
                  <p>В гарнизон: {selectedTerritoryName}</p>
                </div>
                <div className="lord-home-recruit-slider">
                  <span>Количество: {recruitQty}</span>
                  <div className="lord-home-recruit-slider-row">
                    <button
                      className="lord-home-recruit-step"
                      type="button"
                      aria-label="Уменьшить количество"
                      disabled={maxRecruitQty < 1 || recruitQty <= 1}
                      onClick={() => setRecruitQty((current) => clampRecruitQty(current - 1, maxRecruitQty))}
                    >
                      -
                    </button>
                    <div
                      className={`lord-home-recruit-track${maxRecruitQty < 1 ? " is-disabled" : ""}`}
                      onPointerDown={(event) => {
                        if (maxRecruitQty < 1) return;
                        event.currentTarget.setPointerCapture(event.pointerId);
                        setIsRecruitSliderDragging(true);
                        setRecruitQtyFromTrack(event.clientX, event.currentTarget);
                      }}
                      onPointerMove={(event) => {
                        if (!isRecruitSliderDragging || maxRecruitQty < 1) return;
                        setRecruitQtyFromTrack(event.clientX, event.currentTarget);
                      }}
                      onPointerUp={(event) => {
                        setIsRecruitSliderDragging(false);
                        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                          event.currentTarget.releasePointerCapture(event.pointerId);
                        }
                      }}
                      onPointerCancel={(event) => {
                        setIsRecruitSliderDragging(false);
                        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                          event.currentTarget.releasePointerCapture(event.pointerId);
                        }
                      }}
                    >
                      <span className="lord-home-recruit-track-fill" style={{ width: `${recruitSliderPercent}%` }} />
                      <i className="lord-home-recruit-track-thumb" style={{ left: `${recruitSliderPercent}%` }} />
                      <input
                        type="range"
                        min={maxRecruitQty > 0 ? 1 : 0}
                        max={Math.max(1, maxRecruitQty)}
                        step={1}
                        value={recruitQty}
                      aria-label="Выбрать количество"
                        disabled={maxRecruitQty < 1}
                        onChange={(event) => setRecruitQty(clampRecruitQty(Number(event.currentTarget.value), maxRecruitQty))}
                      />
                    </div>
                    <button
                      className="lord-home-recruit-step"
                      type="button"
                      aria-label="Увеличить количество"
                      disabled={maxRecruitQty < 1 || recruitQty >= maxRecruitQty}
                      onClick={() => setRecruitQty((current) => clampRecruitQty(current + 1, maxRecruitQty))}
                    >
                      +
                    </button>
                  </div>
                </div>
                <div className="lord-home-recruit-cost">
                  <span>Стоимость</span>
                  <b>{recruitTotalCost} золота</b>
                </div>
                <div className="lord-home-recruit-status">
                  {recruitStatus || recruitIdleStatus}
                </div>
                <button className="lord-home-hire-button" type="button" onClick={hireRecruit} disabled={!recruitCanSubmit}>
                  {isRecruitHiring ? "Нанимаю" : "Нанять"}
                </button>
              </motion.section>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <AnimatePresence>
          {transferDraft && transferStack && transferUnit ? (
            <motion.div className="lord-home-modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <motion.section
                className="lord-home-recruit-modal lord-home-transfer-modal"
                initial={prefersReducedMotion ? false : { y: 24, scale: 0.96 }}
                animate={prefersReducedMotion ? undefined : { y: 0, scale: 1 }}
                exit={prefersReducedMotion ? undefined : { y: 18, scale: 0.97 }}
              >
                <img className="lord-home-recruit-modal-frame" src={lordHomeRecruitModalFrame} alt="" draggable={false} />
                <button className="lord-home-modal-close" type="button" onClick={() => setTransferDraft(null)} aria-label="Закрыть">
                  ×
                </button>
                <div className="lord-home-recruit-portrait">
                  <img src={transferUnit.icon} alt="" draggable={false} />
                </div>
                <div className="lord-home-recruit-info">
                  <span>{transferDraft.mode === "split" ? "Разделить пачку" : transferDraft.lane === "army" ? "В гарнизон" : "В армию"}</span>
                  <h2>{transferUnit.name}</h2>
                  <div className="lord-home-unit-stats">
                    <b><span>АТК</span>{transferUnit.attack}</b>
                    <b><span>ЗЩТ</span>{transferUnit.defense}</b>
                    <b><span>HP</span>{transferUnit.hp}</b>
                    <b><span>ДАЛЬ</span>{transferUnit.attackRange}</b>
                    <b><span>ИНИЦ</span>{transferUnit.initiative}</b>
                    <b><span>ХОД</span>{transferUnit.moveRange}</b>
                  </div>
                  <p>{selectedTerritoryName}</p>
                </div>
                <div className="lord-home-recruit-slider">
                  <span>Количество: {transferQty} из {transferStack.count}</span>
                  <div className="lord-home-recruit-slider-row">
                    <button
                      className="lord-home-recruit-step"
                      type="button"
                      aria-label="Уменьшить количество"
                      disabled={maxTransferQty < 1 || transferQty <= 1}
                      onClick={() => setTransferQty((current) => clampRecruitQty(current - 1, maxTransferQty))}
                    >
                      -
                    </button>
                    <div className={`lord-home-recruit-track${maxTransferQty < 1 ? " is-disabled" : ""}`}>
                      <span className="lord-home-recruit-track-fill" style={{ width: `${transferSliderPercent}%` }} />
                      <i className="lord-home-recruit-track-thumb" style={{ left: `${transferSliderPercent}%` }} />
                      <input
                        type="range"
                        min={maxTransferQty > 0 ? 1 : 0}
                        max={Math.max(1, maxTransferQty)}
                        step={1}
                        value={transferQty}
                        aria-label="Выбрать количество"
                        disabled={maxTransferQty < 1}
                        onChange={(event) => setTransferQty(clampRecruitQty(Number(event.currentTarget.value), maxTransferQty))}
                      />
                    </div>
                    <button
                      className="lord-home-recruit-step"
                      type="button"
                      aria-label="Увеличить количество"
                      disabled={maxTransferQty < 1 || transferQty >= maxTransferQty}
                      onClick={() => setTransferQty((current) => clampRecruitQty(current + 1, maxTransferQty))}
                    >
                      +
                    </button>
                  </div>
                </div>
                <div className="lord-home-recruit-cost">
                  <span>{transferDraft.mode === "split" ? "Новая пачка" : "Направление"}</span>
                  <b>{transferDraft.mode === "split" ? "В той же линии" : transferDraft.lane === "army" ? "В гарнизон" : "В армию"}</b>
                  <small>В пачке: {transferStack.count}</small>
                  <small>{selectedTerritoryName}</small>
                </div>
                <div className="lord-home-recruit-status">
                  {transferStatus || (transferDraft.mode === "split" ? "Выберите размер новой пачки" : selectedHeroHere ? "Выберите часть пачки" : selectedActiveArmyLockReason)}
                </div>
                <button className="lord-home-hire-button" type="button" onClick={submitStackTransfer} disabled={!transferCanSubmit}>
                  {isTransferSubmitting ? "Отправляю" : transferDraft.mode === "split" ? "Разделить" : "Перенести"}
                </button>
              </motion.section>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <AnimatePresence>
          {openPanel ? (
            <LordHomeActionOverlay
              panel={openPanel}
              onClose={() => setOpenPanel(null)}
              selectedTerritoryName={selectedTerritoryName}
            />
          ) : null}
        </AnimatePresence>
      </div>
    </main>
  );
}

function LordHomeActionIcon({ src }: { src: string }) {
  return (
    <span className="lord-home-action-medallion" aria-hidden="true">
      <img className="lord-home-action-icon" src={src} alt="" draggable={false} />
    </span>
  );
}

function LordHomeBuildingIconLayer({
  buildingNodes,
  builtBuildingIds,
  selectedBuildingId,
  visibleBuildingIds
}: {
  buildingNodes?: LordBuildingNode[];
  builtBuildingIds: Set<string>;
  selectedBuildingId: string;
  visibleBuildingIds?: Set<string> | null;
}) {
  const activeBuildingId = selectedBuildingId;
  const sourceNodes = buildingNodes !== undefined ? buildingNodes : lordBuildingTreeNodes;
  const visibleBuildings = visibleBuildingIds
    ? sourceNodes.filter((building) => visibleBuildingIds.has(building.id))
    : sourceNodes;

  return (
    <div className="lord-building-icon-underlay-layer" aria-hidden="true">
      {visibleBuildings.map((building) => {
        const state = getLordBuildingState(building, builtBuildingIds);
        const meta = lordBuildingBranchMeta[building.branch];
        const iconSrc = lordBuildingIconById[building.id];
        const Icon = meta.icon;

        return (
          <span
            key={building.id}
            className={`lord-building-icon-underlay ${meta.tone} is-${state}${building.id === activeBuildingId ? " is-active" : ""}`}
            style={{ left: `${building.x}%`, top: `${building.y}%` }}
          >
            {iconSrc ? <img src={iconSrc} alt="" draggable={false} /> : <Icon size={44} />}
            <i />
          </span>
        );
      })}
    </div>
  );
}

function LordHomeBuildingTree({
  buildingNodes,
  builtBuildingIds,
  selectedBuildingId,
  buildingStatus,
  buildingPurchaseId,
  visibleBuildingIds,
  scopedLockReason,
  onSelectBuilding,
  onBuild
}: {
  buildingNodes?: LordBuildingNode[];
  builtBuildingIds: Set<string>;
  selectedBuildingId: string;
  buildingStatus: string;
  buildingPurchaseId: string | null;
  visibleBuildingIds?: Set<string> | null;
  scopedLockReason?: string;
  onSelectBuilding: (buildingId: string) => void;
  onBuild: (buildingId: string) => void;
}) {
  const sourceNodes = buildingNodes !== undefined ? buildingNodes : lordBuildingTreeNodes;
  const nodeById = new globalThis.Map(sourceNodes.map((building) => [building.id, building]));
  const visibleBuildings = visibleBuildingIds
    ? sourceNodes.filter((building) => visibleBuildingIds.has(building.id))
    : sourceNodes;

  if (visibleBuildings.length === 0) {
    return (
      <section className="lord-building-tree-screen" aria-label="Дерево зданий главного замка">
        <div className="lord-building-branch-ribbon" aria-hidden="true">
          {Object.entries(lordBuildingBranchMeta).map(([branch, meta]) => (
            <span key={branch} className={`lord-building-branch-label ${meta.tone}`}>
              {meta.label}
            </span>
          ))}
        </div>
        <aside className="lord-building-hover-panel economy is-locked" aria-live="polite">
          <div className="lord-building-portrait">
            <Castle size={58} />
            <span />
          </div>
          <div className="lord-building-panel-copy">
            <span className="lord-building-state">Недоступно</span>
            <h2>Главный замок</h2>
            <p>{scopedLockReason || "Здания строятся в главном замке"}</p>
          </div>
          <div className="lord-building-effects">
            <span>Дает</span>
            <ul>
              <li>Выберите резиденцию дома, чтобы строить здания</li>
            </ul>
          </div>
          <button className="lord-building-build-button" type="button" disabled>
            Недоступно
          </button>
        </aside>
      </section>
    );
  }

  const buildingStateFor = (building: LordBuildingNode): LordBuildingState => getLordBuildingState(building, builtBuildingIds);

  const activeBuilding =
    visibleBuildings.find((building) => building.id === selectedBuildingId) ??
    visibleBuildings[0] ??
    sourceNodes[0];
  const activeState = buildingStateFor(activeBuilding);
  const activeMeta = lordBuildingBranchMeta[activeBuilding.branch];
  const activeIconSrc = lordBuildingIconById[activeBuilding.id];
  const ActiveIcon = activeMeta.icon;
  const isBuildingPurchasePending = buildingPurchaseId === activeBuilding.id;
  const hasBuildingPurchasePending = buildingPurchaseId !== null;
  const missingPrerequisiteIds = activeBuilding.missingPrerequisiteIds?.length
    ? activeBuilding.missingPrerequisiteIds
    : activeBuilding.prerequisiteIds.filter((id) => !builtBuildingIds.has(id));
  const missingPrerequisites = missingPrerequisiteIds
    .map((id) => nodeById.get(id)?.name)
    .filter(Boolean);
  const fallbackBenefitBullets = Array.from(new Set([
    ...(lordBuildingBaseBenefitLabels[activeBuilding.id] ?? [])
  ]));
  const buildingBenefitBulletsBase = activeBuilding.effectLabels?.length
    ? activeBuilding.effectLabels
    : fallbackBenefitBullets;
  const buildingBenefitBullets = buildingBenefitBulletsBase.length
    ? buildingBenefitBulletsBase
    : [activeBuilding.effect];
  const buildButtonText =
    scopedLockReason
      ? "Недоступно"
      : isBuildingPurchasePending
        ? "Строю"
        : activeState === "built" ? "Построено" : activeState === "available" ? "Построить" : "Недоступно";

  return (
    <section className="lord-building-tree-screen" aria-label="Дерево зданий главного замка">
      <div className="lord-building-branch-ribbon" aria-hidden="true">
        {Object.entries(lordBuildingBranchMeta).map(([branch, meta]) => (
          <span key={branch} className={`lord-building-branch-label ${meta.tone}`}>
            {meta.label}
          </span>
        ))}
      </div>

      <svg className="lord-building-link-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {visibleBuildings.flatMap((building) =>
          building.prerequisiteIds.map((prerequisiteId) => {
            const prerequisite = nodeById.get(prerequisiteId);

            if (!prerequisite || (visibleBuildingIds && !visibleBuildingIds.has(prerequisiteId))) {
              return null;
            }

            const meta = lordBuildingBranchMeta[building.branch];
            const linkState = builtBuildingIds.has(building.id)
              ? "complete"
              : builtBuildingIds.has(prerequisiteId)
                ? "open"
                : "locked";
            const path = getLordBuildingLinkPath(prerequisite, building);

            return (
              <g
                key={`${prerequisiteId}-${building.id}`}
                data-link-id={`${prerequisiteId}-${building.id}`}
                className={`lord-building-link-route ${meta.tone} is-${linkState}`}
              >
                <path className="lord-building-link-halo" d={path} />
                <path className="lord-building-link" d={path} />
              </g>
            );
          })
        )}
      </svg>

      <div className="lord-building-node-layer">
        {visibleBuildings.map((building) => {
          const state = buildingStateFor(building);
          const meta = lordBuildingBranchMeta[building.branch];
          const isActive = building.id === activeBuilding.id;

          return (
            <button
              key={building.id}
              data-building-id={building.id}
              className={`lord-building-node ${meta.tone} is-${state}${isActive ? " is-active" : ""}`}
              style={{ left: `${building.x}%`, top: `${building.y}%` }}
              type="button"
              onClick={() => onSelectBuilding(building.id)}
              aria-label={`${building.name}: ${state === "built" ? "построено" : state === "available" ? "можно построить" : "закрыто"}`}
            >
              <span className="lord-building-state-mark" aria-hidden="true" />
              <span className="lord-building-node-title">{building.name}</span>
            </button>
          );
        })}
      </div>

      <aside className={`lord-building-hover-panel ${activeMeta.tone} is-${activeState}`} aria-live="polite">
        <div className="lord-building-portrait">
          {activeIconSrc ? <img src={activeIconSrc} alt="" draggable={false} /> : <ActiveIcon size={58} />}
          <span />
        </div>
        <div className="lord-building-panel-copy">
          <span className="lord-building-state">
            {isBuildingPurchasePending
              ? "Строительство"
              : activeState === "built" ? "Построено" : activeState === "available" ? "Можно построить" : "Требуются постройки"}
          </span>
          <h2>{activeBuilding.name}</h2>
          <p>{activeBuilding.effect}</p>
        </div>
        <div className="lord-building-cost-row">
          <b><Coins size={13} /> {activeBuilding.goldCost}</b>
          <b><Crown size={13} /> Уровень {activeBuilding.tier}</b>
        </div>
        {buildingStatus || scopedLockReason ? (
          <div className={`lord-building-api-status${isBuildingPurchasePending ? " is-pending" : ""}`}>
            {buildingStatus || scopedLockReason}
          </div>
        ) : activeState !== "built" && missingPrerequisites.length ? (
          <div className="lord-building-requirements">
            <span>Необходимо построить</span>
            <b>{missingPrerequisites.join(", ")}</b>
          </div>
        ) : null}
        <div className="lord-building-effects">
          <span>Дает</span>
          <ul>
            {buildingBenefitBullets.map((benefit) => (
              <li key={benefit}>{benefit}</li>
            ))}
          </ul>
        </div>
        <button
          className="lord-building-build-button"
          type="button"
          disabled={Boolean(scopedLockReason) || activeState !== "available" || hasBuildingPurchasePending}
          onClick={() => onBuild(activeBuilding.id)}
        >
          {buildButtonText}
        </button>
      </aside>
    </section>
  );
}

function LordHomeLane({
  lane,
  label,
  stacks,
  locked,
  onStackClick,
  activeDragPayload,
  onDrop,
  onPointerStart,
  onPointerMove,
  onPointerDrop,
  onSuppressStackClick
}: {
  lane: "army" | "garrison";
  label: string;
  stacks: LordHomeStack[];
  locked: boolean;
  onStackClick: (index: number) => void;
  activeDragPayload: LordHomeDragPayload;
  onDrop: (targetIndex?: number) => void;
  onPointerStart: (payload: Exclude<LordHomeDragPayload, null>, point: { x: number; y: number }) => void;
  onPointerMove: (point: { x: number; y: number }) => void;
  onPointerDrop: (point: { x: number; y: number }) => boolean;
  onSuppressStackClick: () => boolean;
}) {
  return (
    <div
      data-lane={lane}
      className={`lord-home-lane ${lane}${locked ? " is-locked" : ""}`}
      onPointerUp={(event) => {
        const handled = onPointerDrop({ x: event.clientX, y: event.clientY });
        if (handled) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }

        onDrop();
      }}
    >
      <span className="lord-home-lane-label">{label}</span>
      {Array.from({ length: 8 }).map((_, index) => {
        const stack = stacks[index];
        const isDragSource = activeDragPayload?.lane === lane && activeDragPayload.index === index;

        return (
          <button
            key={`${lane}-${index}`}
            className={`lord-home-unit-slot${stack ? " is-filled" : ""}${isDragSource ? " is-drag-source" : ""}`}
            type="button"
            data-slot-index={index}
            disabled={!stack || locked}
            draggable={false}
            onPointerDown={(event) => {
              if (!stack || locked || event.button !== 0) {
                return;
              }

              event.currentTarget.setPointerCapture(event.pointerId);
              onPointerStart({ lane, index }, { x: event.clientX, y: event.clientY });
            }}
            onPointerMove={(event) => {
              if (!stack || locked) {
                return;
              }

              onPointerMove({ x: event.clientX, y: event.clientY });
            }}
            onPointerUp={(event) => {
              if (!stack || locked) {
                return;
              }

              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                event.currentTarget.releasePointerCapture(event.pointerId);
              }

              const handled = onPointerDrop({ x: event.clientX, y: event.clientY });
              if (handled) {
                event.preventDefault();
                event.stopPropagation();
              }
            }}
            onPointerCancel={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                event.currentTarget.releasePointerCapture(event.pointerId);
              }
              onPointerDrop({ x: event.clientX, y: event.clientY });
            }}
            onClick={(event) => {
              if (onSuppressStackClick()) {
                event.preventDefault();
                event.stopPropagation();
                return;
              }
              if (stack) {
                onStackClick(index);
              }
            }}
            aria-label={stack ? `${lordHomeUnitCatalog[stack.unitId].name}: ${stack.count}` : "Пустой слот"}
          >
            {stack ? (
              <>
                <img src={lordHomeUnitCatalog[stack.unitId].icon} alt="" draggable={false} />
                <b>{stack.count}</b>
              </>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function LordHomeOrdersBoard({
  orders,
  orderCap,
  escrow,
  orderConflicts,
  targets,
  recipients,
  filterId,
  selectedOrderId,
  lordGold,
  actionStatus,
  readOnlyReason,
  isSubmitting,
  onFilterChange,
  onSelectOrder,
  onCreateOrder,
  onCancelOrder,
  onStatus
}: {
  orders: LordHomeOrder[];
  orderCap: LordHomeOrderCap;
  escrow: LordHomeOrderEscrow;
  orderConflicts: LordHomeOrderConflict[];
  targets: LordHomeOrderTarget[];
  recipients: LordHomeOrderRecipient[];
  filterId: LordHomeOrderFilterId;
  selectedOrderId: string | null;
  lordGold: number;
  actionStatus: string;
  readOnlyReason: string;
  isSubmitting: boolean;
  onFilterChange: (filterId: LordHomeOrderFilterId) => void;
  onSelectOrder: (orderId: string | null) => void;
  onCreateOrder: (payload: LordHomeOrderCreatePayload) => void;
  onCancelOrder: (order: LordHomeOrder, reason: string) => void;
  onStatus: (message: string) => void;
}) {
  const cap = getLordHomeOrderCap(orderCap);
  const filteredOrders = getLordHomeOrdersForFilter(orders, filterId);
  const selectedOrder = filteredOrders.find((order) => order.order_id === selectedOrderId) ?? filteredOrders[0] ?? null;
  const lockedAssets = Number(escrow.locked_asset_count ?? escrow.locked_assets?.length ?? 0);
  const lockedGold = Number(escrow.locked_gold ?? 0);
  const availableGold = getLordHomeOrderAvailableGold(escrow, lordGold);
  const conflictCount = orderConflicts.length || orders.filter((order) => order.conflict_badge).length;
  const activeOrdersCount = cap.publicActive + cap.addressedActive;
  const activeOrdersLimit = cap.publicLimit + cap.addressedLimit;
  const defaultVisibility: LordHomeOrderVisibility =
    cap.publicActive < cap.publicLimit ? "public" : "addressed";
  const interestTargets = useMemo(() => getLordHomeOrderInterestTargets(targets), [targets]);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerMode, setComposerMode] = useState<"create" | "repeat" | "addressed">("create");
  const [cancelDraft, setCancelDraft] = useState<LordHomeOrder | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [conflictOpen, setConflictOpen] = useState(false);
  const [visibility, setVisibility] = useState<LordHomeOrderVisibility>(defaultVisibility);
  const [targetId, setTargetId] = useState(interestTargets[0]?.target_id ?? "");
  const [recipientId, setRecipientId] = useState("");
  const [paymentGoldInput, setPaymentGoldInput] = useState(getLordHomeOrderDefaultPaymentGold(availableGold, interestTargets[0]));
  const selectedConflict = getLordHomeOrderConflict(selectedOrder, orderConflicts);
  const selectedTarget = interestTargets.find((target) => target.target_id === targetId) ?? null;
  const prefersReducedMotion = useReducedMotion();
  const readOnlyBlockReason = readOnlyReason.trim();
  const publicFull = cap.publicActive >= cap.publicLimit;
  const addressedFull = cap.addressedActive >= cap.addressedLimit;
  const selectedCapFull = visibility === "addressed" ? addressedFull : publicFull;
  const paymentGold = parseLordHomeOrderGoldInput(paymentGoldInput);
  const invalidPaymentGold = paymentGold <= 0;
  const insufficientGold = paymentGold > availableGold;
  const needsRecipient = visibility === "addressed" && !recipientId;
  const createBlockReason =
    readOnlyBlockReason
      ? readOnlyBlockReason
      : !interestTargets.length
      ? "Нет доступных объектов интереса"
      : availableGold <= 0
        ? "В казне нет золота для оплаты"
        : publicFull && addressedFull
          ? `Лимит заказов занят: публичные ${cap.publicActive}/${cap.publicLimit}, адресный ${cap.addressedActive}/${cap.addressedLimit}`
          : "";
  const createHint =
    readOnlyBlockReason
      ? "Только просмотр"
      : createBlockReason && publicFull && addressedFull
      ? "Лимит заказов занят"
      : createBlockReason || `${availableGold}g доступно для оплаты`;
  const publishBlockReason =
    isSubmitting
      ? "Канцелярия уже ставит печать"
      : createBlockReason
        ? createBlockReason
        : selectedCapFull
          ? visibility === "addressed"
            ? `Адресный лимит занят ${cap.addressedActive}/${cap.addressedLimit}`
            : `Публичные заказы заняты ${cap.publicActive}/${cap.publicLimit}`
          : needsRecipient
            ? "Выберите адресата"
            : invalidPaymentGold
              ? "Укажите оплату золотом"
              : insufficientGold
                ? "В казне не хватает золота"
                : !selectedTarget
                  ? "Выберите объект интереса"
                  : "";
  const openComposer = (mode: "create" | "repeat" | "addressed" = "create", order?: LordHomeOrder) => {
    if (readOnlyBlockReason) {
      onStatus(readOnlyBlockReason);
      return;
    }
    setComposerOpen(true);
    setCancelDraft(null);
    setConflictOpen(false);
    setComposerMode(mode);
    const nextVisibility =
      mode === "addressed"
        ? "addressed"
          : order?.visibility === "addressed"
          ? "addressed"
          : defaultVisibility;
    const repeatedTarget = interestTargets.find((target) => target.target_id === order?.object_id);
    const nextTarget = repeatedTarget || interestTargets[0] || null;
    setVisibility(nextVisibility);
    setTargetId(nextTarget?.target_id || "");
    setRecipientId(mode === "addressed" ? order?.target_player_id || recipients[0]?.player_id || "" : order?.target_player_id || "");
    const repeatedGold = order ? Number(order.reward_gold ?? 0) || getLordHomeOrderGoldFromLabel(order.reward_label) : 0;
    setPaymentGoldInput(repeatedGold > 0 ? String(repeatedGold) : getLordHomeOrderDefaultPaymentGold(availableGold, nextTarget));
    onStatus("");
  };

  useEffect(() => {
    if (!interestTargets.length) {
      if (targetId) {
        setTargetId("");
      }
      return;
    }
    if (!targetId || !interestTargets.some((target) => target.target_id === targetId)) {
      setTargetId(interestTargets[0].target_id);
    }
  }, [interestTargets, targetId]);

  useEffect(() => {
    if (visibility === "addressed" && !recipientId && recipients[0]?.player_id) {
      setRecipientId(recipients[0].player_id);
    }
  }, [recipientId, recipients, visibility]);

  useEffect(() => {
    setCancelDraft(null);
    setCancelReason("");
    setConflictOpen(false);
  }, [filterId, selectedOrder?.order_id]);

  const submitOrder = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (publishBlockReason || !selectedTarget) {
      onStatus(publishBlockReason || "Заполните заказ");
      return;
    }

    setComposerOpen(false);
    onCreateOrder({
      visibility,
      object_id: selectedTarget.target_id,
      target_player_id: visibility === "addressed" ? recipientId : undefined,
      visible_hook: getLordHomeOrderGeneratedHook(selectedTarget),
      reward: { gold: paymentGold },
      source: "stage2b_lord_home_orders"
    });
  };

  return (
    <motion.section
      className="lord-orders-board"
      aria-label="Канцелярия заказов"
      initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
      animate={prefersReducedMotion ? undefined : { opacity: 1, y: 0 }}
      transition={prefersReducedMotion ? undefined : { duration: 0.22, ease: "easeOut" }}
    >
      <header className="lord-orders-header">
        <div className="lord-orders-title">
          <span>Доска объявлений владения</span>
          <h1>Канцелярия заказов</h1>
        </div>
        <div className="lord-orders-summary" aria-label="Состояние заказов">
          <b><ScrollText size={14} /> Активно {activeOrdersCount}/{activeOrdersLimit}</b>
          <span>Публичные {cap.publicActive}/{cap.publicLimit}</span>
          <span>Адресный {cap.addressedActive}/{cap.addressedLimit}</span>
          <span><Archive size={13} /> Залог {lockedGold}g</span>
          {lockedAssets ? <span><Package size={13} /> Вещи {lockedAssets}</span> : null}
          <span className={conflictCount ? "is-alert" : undefined}>
            <AlertTriangle size={13} /> Конфликты {conflictCount}
          </span>
        </div>
        <div className="lord-orders-create-shell">
          <button
            className="lord-orders-create"
            type="button"
            disabled={Boolean(createBlockReason)}
            title={createBlockReason || "Создать заказ"}
            onClick={() => openComposer("create")}
          >
            <ScrollText size={15} />
            Создать
          </button>
          <small>{createHint}</small>
        </div>
      </header>

      {readOnlyBlockReason ? (
        <p className="lord-orders-notice is-readonly" role="status">
          <Wifi size={14} />
          {readOnlyBlockReason}
        </p>
      ) : actionStatus ? (
        <p className="lord-orders-notice" role="status">
          <CheckCircle2 size={14} />
          {actionStatus}
        </p>
      ) : null}

      <aside className="lord-orders-filters" aria-label="Фильтры заказов">
        {lordHomeOrderFilters.map((filter) => (
          <button
            key={filter.id}
            type="button"
            aria-pressed={filter.id === filterId}
            onClick={() => {
              setComposerOpen(false);
              setCancelDraft(null);
              setConflictOpen(false);
              onFilterChange(filter.id);
            }}
          >
            <span>{filter.label}</span>
            <b>{getLordHomeOrdersForFilter(orders, filter.id).length}</b>
          </button>
        ))}
      </aside>

      <section className="lord-orders-list" aria-label="Пергаменты заказов">
        {filteredOrders.length ? filteredOrders.map((order) => (
          <button
            key={order.order_id}
            className={`lord-order-parchment ${getLordHomeOrderTone(order)}`}
            type="button"
            aria-pressed={selectedOrder?.order_id === order.order_id}
            onClick={() => {
              setComposerOpen(false);
              setCancelDraft(null);
              setConflictOpen(false);
              onSelectOrder(order.order_id);
            }}
          >
            <span className="lord-order-wax" aria-hidden="true" />
            <div className="lord-order-card-top">
              <span>{order.visibility_label || (order.visibility === "addressed" ? "Адресный" : "Публичный")}</span>
              <b>{order.status_label || order.status || "Открыт"}</b>
            </div>
            <h2>{getLordHomeOrderInterestLabel(order)}</h2>
            <div className="lord-order-card-grid">
              <span><MapIcon size={13} /> Где: {order.location_label || "по следу"}</span>
              <span><Coins size={13} /> Оплата: {getLordHomeOrderPaymentLabel(order)}</span>
            </div>
            <div className="lord-order-card-foot">
              <span><Archive size={13} /> {getLordHomeOrderEscrowLabel(order)}</span>
              <span><Clock3 size={13} /> {getLordHomeOrderWindowLabel(order)}</span>
              {order.executor_label ? <span><Users size={13} /> {order.executor_label}</span> : null}
              {order.conflict_badge ? <mark>{order.conflict_badge.label}</mark> : null}
            </div>
          </button>
        )) : (
          <div className="lord-orders-empty">
            <ScrollText size={22} />
            <b>{lordHomeOrderFilters.find((filter) => filter.id === filterId)?.label}</b>
            <span>В этом разделе пока тихо.</span>
            <button type="button" disabled={Boolean(createBlockReason)} onClick={() => openComposer("create")}>
              Создать
            </button>
          </div>
        )}
      </section>

      <aside className="lord-orders-detail" aria-label="Детали заказа">
        {cancelDraft ? (
          <article className={`lord-orders-selected lord-orders-cancel ${getLordHomeOrderTone(cancelDraft)}`}>
            <div className="lord-orders-detail-head">
              <span>Отзыв заказа</span>
              <h2>{getLordHomeOrderInterestLabel(cancelDraft)}</h2>
            </div>
            <p className="lord-orders-detail-note">
              Заказ будет закрыт для исполнителей. Если награда уже в залоге, канцелярия вернет ее в казну после подтверждения.
            </p>
            <label>
              <span>Причина для журнала мастера</span>
              <textarea
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
                placeholder="Например: цель потеряла значение или договоренность сорвалась"
              />
            </label>
            <div className="lord-orders-actions">
              <button
                type="button"
                onClick={() => {
                  setCancelDraft(null);
                  setCancelReason("");
                }}
              >
                Назад
              </button>
              <button
                className="is-danger"
                type="button"
                disabled={Boolean(readOnlyBlockReason) || isSubmitting}
                onClick={() => {
                  onCancelOrder(cancelDraft, cancelReason);
                  setCancelDraft(null);
                  setCancelReason("");
                }}
              >
                <XCircle size={15} />
                Отозвать
              </button>
            </div>
            <p className="lord-orders-status" role="status">{readOnlyBlockReason || actionStatus}</p>
          </article>
        ) : conflictOpen && selectedOrder ? (
          <article className={`lord-orders-selected lord-orders-conflict ${getLordHomeOrderTone(selectedOrder)}`}>
            <div className="lord-orders-detail-head">
              <span>{selectedConflict?.badge_label || selectedOrder.conflict_badge?.label || "Конфликт"}</span>
              <h2>{cleanLordHomeOrderInterestLabel(selectedConflict?.object_label || selectedOrder.object_label, selectedOrder.location_label)}</h2>
            </div>
            <p className="lord-orders-review-note">
              <AlertTriangle size={15} />
              {selectedConflict?.status === "contested_review"
                ? "На решении мастера"
                : selectedOrder.conflict_badge?.label || "Есть пересечение по объекту"}
            </p>
            <dl>
              <div><dt>Ваши заказы</dt><dd>{selectedConflict?.own_order_ids?.length ?? 1}</dd></div>
              <div><dt>Чужие заявки</dt><dd>{selectedConflict?.competing_order_count ?? 0}</dd></div>
              <div><dt>Лорды</dt><dd>{selectedConflict?.competing_lord_count ?? 0}</dd></div>
            </dl>
            <p className="lord-orders-detail-note">
              Приватные причины и чужие адресные детали скрыты. Полный разбор видит мастер; лорд видит только факт спора и состояние решения.
            </p>
            <div className="lord-orders-actions">
              <button type="button" onClick={() => setConflictOpen(false)}>Назад</button>
              <button type="button" disabled>
                <Gavel size={15} />
                Ждем мастера
              </button>
            </div>
          </article>
        ) : composerOpen ? (
          <form className="lord-orders-composer" onSubmit={submitOrder}>
            <div className="lord-orders-detail-head">
              <span>Новая запись</span>
              <h2>
                {composerMode === "repeat"
                  ? "Повторить как новый"
                  : composerMode === "addressed"
                    ? "Адресный заказ"
                    : "Поручение исполнителю"}
              </h2>
            </div>
            {composerMode === "repeat" ? (
              <p className="lord-orders-detail-note">Это создаст новый заказ и заново удержит оплату в залоге.</p>
            ) : composerMode === "addressed" ? (
              <p className="lord-orders-detail-note">Это новый адресный заказ по выбранному объекту, а не изменение уже взятого поручения.</p>
            ) : null}
            <div className="lord-orders-composer-section">
              <h3>1. Заказ</h3>
              <label>
                <span>Тип</span>
                <select value={visibility} onChange={(event) => setVisibility(event.target.value as LordHomeOrderVisibility)}>
                  <option value="public">Публичный</option>
                  <option value="addressed">Адресный</option>
                </select>
              </label>
              <label>
                <span>Объект интереса</span>
                <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                  {interestTargets.map((target) => (
                    <option key={target.target_id} value={target.target_id}>
                      {getLordHomeOrderTargetOptionLabel(target)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Адресат</span>
                <select
                  value={recipientId}
                  disabled={visibility !== "addressed"}
                  onChange={(event) => setRecipientId(event.target.value)}
                >
                  <option value="">Любой исполнитель</option>
                  {recipients.map((recipient) => (
                    <option key={recipient.player_id} value={recipient.player_id}>
                      {recipient.display_name}{recipient.role_label ? `, ${recipient.role_label}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="lord-orders-composer-section">
              <h3>2. Оплата</h3>
              <label>
                <span>Оплата золотом</span>
                <div className="lord-orders-gold-input">
                  <Coins size={14} />
                  <input
                    type="number"
                    min="1"
                    max={Math.max(1, Math.floor(availableGold))}
                    step="1"
                    inputMode="numeric"
                    value={paymentGoldInput}
                    onChange={(event) => setPaymentGoldInput(event.target.value)}
                    aria-label="Сумма оплаты золотом"
                  />
                  <small>из {availableGold}g</small>
                </div>
              </label>
            </div>
            <p className="lord-orders-status" role="status">{publishBlockReason || actionStatus}</p>
            <div className="lord-orders-actions">
              <button type="button" onClick={() => setComposerOpen(false)}>Отмена</button>
              <button type="submit" disabled={Boolean(publishBlockReason)}>
                <Gavel size={15} />
                Опубликовать
              </button>
            </div>
          </form>
        ) : selectedOrder ? (
          <article className={`lord-orders-selected ${getLordHomeOrderTone(selectedOrder)}`}>
            <span className="lord-order-wax detail" aria-hidden="true" />
            <div className="lord-orders-detail-head">
              <span>{selectedOrder.visibility_label || selectedOrder.visibility || "Публичный"}</span>
              <h2>{getLordHomeOrderInterestLabel(selectedOrder)}</h2>
            </div>
            <p className="lord-orders-detail-note">
              {selectedOrder.executor_label
                ? `Исполнитель: ${selectedOrder.executor_label}`
                : selectedOrder.target_player_label
                  ? `Адресат: ${selectedOrder.target_player_label}`
                  : "Исполнитель пока не назначен"}
            </p>
            <dl>
              <div><dt>Статус</dt><dd>{selectedOrder.status_label || selectedOrder.status || "Открыт"}</dd></div>
              <div><dt>Где</dt><dd>{selectedOrder.location_label || "по следу"}</dd></div>
              <div><dt>Оплата</dt><dd>{getLordHomeOrderPaymentLabel(selectedOrder)}</dd></div>
              <div><dt>Залог</dt><dd>{getLordHomeOrderEscrowLabel(selectedOrder)}</dd></div>
              <div><dt>Срок</dt><dd>{getLordHomeOrderWindowLabel(selectedOrder)}</dd></div>
            </dl>
            {selectedOrder.conflict_badge || selectedConflict ? (
              <p className="lord-orders-review-note">
                <AlertTriangle size={15} />
                {selectedOrder.conflict_badge?.label || selectedConflict?.badge_label}
              </p>
            ) : null}
            <div className="lord-orders-actions lord-orders-action-stack">
              <button
                type="button"
                disabled={!canCancelLordHomeOrder(selectedOrder) || Boolean(readOnlyBlockReason) || isSubmitting}
                onClick={() => {
                  setCancelDraft(selectedOrder);
                  setCancelReason("");
                }}
              >
                <XCircle size={15} />
                Отменить
              </button>
              <button type="button" disabled={Boolean(readOnlyBlockReason) || isSubmitting} onClick={() => openComposer("repeat", selectedOrder)}>
                <ScrollText size={15} />
                Повторить как новый
              </button>
              <button
                type="button"
                disabled={!selectedOrder.conflict_badge && !selectedConflict}
                onClick={() => setConflictOpen(true)}
              >
                <AlertTriangle size={15} />
                Посмотреть конфликт
              </button>
              <button type="button" disabled={Boolean(readOnlyBlockReason) || isSubmitting || addressedFull} onClick={() => openComposer("addressed", selectedOrder)}>
                <Users size={15} />
                Создать адресный
              </button>
            </div>
            <p className="lord-orders-status" role="status">{actionStatus}</p>
          </article>
        ) : (
          <div className="lord-orders-empty is-detail">
            <ClipboardCheck size={24} />
            <b>Заказ не выбран</b>
            <span>Выберите пергамент или создайте новое поручение.</span>
            <button type="button" disabled={Boolean(createBlockReason)} onClick={() => openComposer("create")}>Создать</button>
          </div>
        )}
      </aside>
    </motion.section>
  );
}

function LordHomeRaidsBoard({
  rules,
  targets,
  activeEffects,
  raidHistory,
  raidTokens,
  actionStatus,
  isSubmitting,
  selectedRuleId,
  selectedTargetId,
  onSelectRule,
  onSelectTarget,
  onStart
}: {
  rules: LordHomeRaidRule[];
  targets: LordHomeRaidTarget[];
  activeEffects: LordHomeRaidEffect[];
  raidHistory: LordHomeRaidEffect[];
  raidTokens: number;
  actionStatus: string;
  isSubmitting: boolean;
  selectedRuleId: string;
  selectedTargetId: string;
  onSelectRule: (ruleId: string) => void;
  onSelectTarget: (targetId: string) => void;
  onStart: (payload: LordHomeRaidStartPayload) => void;
}) {
  const prefersReducedMotion = useReducedMotion();
  const [journalOpen, setJournalOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const normalizedRules = rules.map(normalizeLordHomeRaidRule);
  const normalizedTargets = targets.map(normalizeLordHomeRaidTarget);
  const availableTargets = normalizedTargets.filter((target) => target.can_target !== false);
  const explicitTarget = availableTargets.find((target) => target.target_territory_id === selectedTargetId) ?? null;
  const selectedTarget =
    explicitTarget ??
    availableTargets[0] ??
    null;
  const compatibleRules = selectedTarget
    ? normalizedRules.filter((rule) => isLordHomeRaidTargetCompatible(rule, selectedTarget))
    : normalizedRules;
  const selectedRule =
    compatibleRules.find((rule) => rule.rule_id === selectedRuleId) ??
    compatibleRules.find((rule) => !rule.locked_reason) ??
    compatibleRules[0] ??
    null;
  const blockReason = getLordHomeRaidBlockReason({
    rule: selectedRule,
    target: selectedTarget,
    raidTokens,
    activeEffects,
    isSubmitting
  });
  const activeCount = activeEffects.filter((effect) => effect.status === "active").length;
  const journalCount = activeCount + raidHistory.length;

  return (
    <motion.section
      className="lord-raids-board"
      aria-label="Рейдовые операции владения"
      initial={prefersReducedMotion ? false : { opacity: 0, y: 10 }}
      animate={prefersReducedMotion ? undefined : { opacity: 1, y: 0 }}
      transition={prefersReducedMotion ? undefined : { duration: 0.22, ease: "easeOut" }}
    >
      <header className="lord-raids-header">
        <div className="lord-raids-title">
          <span>Военный стол</span>
          <h1>Рейдовые операции</h1>
        </div>
        <div className="lord-raids-tools">
          <button
            className="lord-raids-journal-button"
            type="button"
            aria-expanded={guideOpen}
            onClick={() => setGuideOpen((current) => !current)}
          >
            <BookOpen size={14} />
            Справка
          </button>
          <button
            className="lord-raids-journal-button"
            type="button"
            aria-expanded={journalOpen}
            onClick={() => setJournalOpen((current) => !current)}
          >
            <Archive size={14} />
            Журнал
            {journalCount ? <b>{journalCount}</b> : null}
          </button>
        </div>
      </header>

      <aside className="lord-raids-target-column" aria-label="Цели рейда">
        <div className="lord-raids-column-head">
          <span>1. Территория</span>
          <b>{availableTargets.length}</b>
        </div>
        <div className="lord-raids-target-list">
          {availableTargets.map((target) => {
            const isSelected = target.target_territory_id === selectedTarget?.target_territory_id;
            return (
              <button
                key={target.target_territory_id}
                className={`lord-raids-target-button${isSelected ? " is-selected" : ""}${target.active_effects?.length ? " has-effect" : ""}`}
                type="button"
                aria-pressed={isSelected}
                onClick={() => onSelectTarget(target.target_territory_id)}
              >
                <b>{target.name}</b>
                <small>{target.owner_label} · {target.raid_resistance_label ?? target.risk_label ?? "риск неизвестен"}</small>
                <em>{target.bonus_label}</em>
              </button>
            );
          })}
          {availableTargets.length === 0 ? (
            <div className="lord-raids-empty-note">
              <b>Нет целей</b>
              <span>Доступные территории появятся здесь.</span>
            </div>
          ) : null}
        </div>
      </aside>

      <section className="lord-raids-plan" aria-label="Операции рейда">
        <div className="lord-raids-column-head">
          <span>2. Операция</span>
          <b>{compatibleRules.filter((rule) => !rule.locked_reason).length}/{compatibleRules.length}</b>
        </div>
        <div className="lord-raid-operation-list">
        {compatibleRules.map((rule) => {
          const meta = getLordHomeRaidCategoryMeta(rule.category);
          const Icon = meta.icon;
          const isActive = selectedRule?.rule_id === rule.rule_id;
          return (
            <button
              key={rule.rule_id}
              className={`lord-raid-operation ${meta.tone}${isActive ? " is-active" : ""}${rule.locked_reason ? " is-locked" : ""}`}
              type="button"
              aria-pressed={isActive}
              onClick={() => onSelectRule(rule.rule_id)}
            >
              <span className="lord-raid-operation-icon"><Icon size={18} /></span>
              <b>{rule.name}</b>
              <small>{getLordHomeRaidEffectLabel(rule.effect_type)}</small>
              <span className="lord-raid-cost-row">
                <Flame size={11} /> {rule.token_cost}
                <Hourglass size={11} /> {formatLordHomeRaidDuration(rule.duration_minutes)}
              </span>
              {rule.locked_reason ? <i>{rule.locked_reason}</i> : null}
            </button>
          );
        })}
        {compatibleRules.length === 0 ? (
          <div className="lord-raids-empty-note">
            <b>Нет операций</b>
            <span>Для выбранной территории нет доступного типа рейда.</span>
          </div>
        ) : null}
        </div>
      </section>

      <aside className="lord-raids-detail" aria-label="Итог выбранного рейда">
        {selectedRule ? (
          <motion.article
            key={selectedRule.rule_id}
            className={`lord-raid-detail-card ${getLordHomeRaidCategoryMeta(selectedRule.category).tone}`}
            initial={prefersReducedMotion ? false : { opacity: 0, x: 18 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, x: 0 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.18, ease: "easeOut" }}
          >
            <div className="lord-raids-detail-head">
              <span>3. Итог</span>
              <h2>{selectedRule.name}</h2>
            </div>
            <dl>
              <div><dt>Территория</dt><dd>{selectedTarget?.name ?? "не выбрана"}</dd></div>
              <div><dt>Цена</dt><dd>{selectedRule.token_cost} жетон</dd></div>
              <div><dt>Длительность</dt><dd>{formatLordHomeRaidDuration(selectedRule.duration_minutes)}</dd></div>
              <div><dt>Эффект</dt><dd>{getLordHomeRaidEffectLabel(selectedRule.effect_type)}</dd></div>
              <div><dt>Риск</dt><dd>{selectedTarget?.raid_resistance_label ?? "неизвестен"}</dd></div>
            </dl>

            <p className="lord-raids-status" role="status">
              {actionStatus || blockReason || "Готово"}
            </p>
            <button
              className="lord-raids-start"
              type="button"
              disabled={Boolean(blockReason)}
              onClick={() => {
                if (!selectedTarget || blockReason) return;
                onStart({
                  target_territory_id: selectedTarget.target_territory_id,
                  rule_id: selectedRule.rule_id,
                  expected_token_cost: selectedRule.token_cost,
                  expected_gold_cost: 0,
                  source: "stage2b_lord_home_raids"
                });
              }}
            >
              <Flame size={15} />
              {isSubmitting ? "Запускаю" : "Начать рейд"}
            </button>
          </motion.article>
        ) : (
          <div className="lord-raids-empty-note is-detail">
            <b>Рейд не выбран</b>
            <span>Выберите территорию и операцию.</span>
          </div>
        )}
      </aside>

      <AnimatePresence>
        {guideOpen ? (
          <motion.aside
            className="lord-raids-guide-panel"
            aria-label="Справка рейдов"
            initial={prefersReducedMotion ? false : { opacity: 0, x: 18 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, x: 0 }}
            exit={prefersReducedMotion ? undefined : { opacity: 0, x: 18 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.16, ease: "easeOut" }}
          >
            <div className="lord-raids-journal-head">
              <span>Справка</span>
              <button type="button" onClick={() => setGuideOpen(false)} aria-label="Закрыть справку">
                <XCircle size={17} />
              </button>
            </div>
            <div className="lord-raids-guide-list">
              {normalizedRules.map((rule) => (
                <article key={rule.rule_id} className="lord-raids-guide-item">
                  <b>{rule.name}</b>
                  <span>{rule.description}</span>
                  <small>
                    {rule.token_cost} жетон · {formatLordHomeRaidDuration(rule.duration_minutes)} · {rule.required_building_labels?.join(", ") || "без здания"}
                  </small>
                </article>
              ))}
            </div>
          </motion.aside>
        ) : null}
        {journalOpen ? (
          <motion.aside
            className="lord-raids-journal-panel"
            aria-label="Журнал рейдов"
            initial={prefersReducedMotion ? false : { opacity: 0, x: 18 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, x: 0 }}
            exit={prefersReducedMotion ? undefined : { opacity: 0, x: 18 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.16, ease: "easeOut" }}
          >
            <div className="lord-raids-journal-head">
              <span>Журнал</span>
              <button type="button" onClick={() => setJournalOpen(false)} aria-label="Закрыть журнал">
                <XCircle size={17} />
              </button>
            </div>
            <section>
              <span>Активные</span>
              {activeEffects.slice(0, 6).map((effect) => (
                <b key={effect.raid_effect_id ?? `${effect.rule_id}-${effect.target_territory_id}`}>
                  {effect.result_label || getLordHomeRaidEffectLabel(effect.effect_type)} · {effect.expires_at ? getLordHomeRaidExpiryLabel([effect]) : "активен"}
                </b>
              ))}
              {activeEffects.length === 0 ? <b>Нет активных рейдов</b> : null}
            </section>
            <section>
              <span>История</span>
              {raidHistory.slice(0, 8).map((effect) => (
                <b key={effect.raid_effect_id ?? `${effect.rule_id}-${effect.started_at}`}>
                  {effect.result_label || effect.rule_id || "рейд"} · {effect.status || "записан"}
                </b>
              ))}
              {raidHistory.length === 0 ? <b>История пуста</b> : null}
            </section>
          </motion.aside>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}

function LordHomeActionOverlay({
  panel,
  selectedTerritoryName,
  onClose
}: {
  panel: "map" | "orders" | "raids" | "help";
  selectedTerritoryName: string;
  onClose: () => void;
}) {
  const panelCopy = {
    map: {
      title: "Карта земель",
      text: "Активная армия двигается по маршрутам и тратит очки передвижения.",
      icon: MapIcon
    },
    orders: {
      title: "Доска объявлений",
      text: "Публичные и адресные заказы удерживают награду в казне до результата.",
      icon: ScrollText
    },
    raids: {
      title: "Рейды",
      text: "Рейд тратит жетон и золото, а результат действует на территорию ограниченное время.",
      icon: Flame
    },
    help: {
      title: "Обучение",
      text: "Повторить обход основных экранов под учебным лордом.",
      icon: BookOpen
    }
  }[panel];
  const Icon = panelCopy.icon;

  return (
    <motion.div className="lord-home-action-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.section
        className={`lord-home-action-panel ${panel}`}
        initial={{ y: -12, scale: 0.98 }}
        animate={{ y: 0, scale: 1 }}
        exit={{ y: -10, scale: 0.98 }}
      >
        <button className="lord-home-modal-close" type="button" onClick={onClose} aria-label="Закрыть">×</button>
        <Icon size={32} />
        <span>{selectedTerritoryName}</span>
        <h2>{panelCopy.title}</h2>
        <p>{panelCopy.text}</p>
        {panel === "map" ? <img className="lord-home-action-map" src={lordMap} alt="" draggable={false} /> : null}
        {panel === "orders" ? (
          <div className="lord-home-paper-list">
            <b>Охота за реликтом</b>
            <b>Сопроводить обоз</b>
            <b>Разведать переправу</b>
          </div>
        ) : null}
        {panel === "raids" ? (
          <div className="lord-home-paper-list">
            <b>Поджечь склады</b>
            <b>Сорвать найм</b>
            <b>Ослабить дозор</b>
          </div>
        ) : null}
      </motion.section>
    </motion.div>
  );
}

type AnimatedLordLoginMode = "menu" | "login" | "onboarding";
type AnimatedLordMenuTarget = "enter" | "training";

type LordRoleTokenAuth = {
  role_type?: string;
  owner_id?: string;
  lord_id?: string | null;
  domain_id?: string | null;
  display_name?: string;
};

const lordLoginCopy = {
  enter: "\u0412\u0445\u043e\u0434",
  training: "\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
  lordCode: "\u041a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  codePlaceholder: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434",
  submit: "\u0412\u043e\u0439\u0442\u0438",
  back: "\u041d\u0430\u0437\u0430\u0434",
  emptyCode: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  invalidCode: "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u043a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  beforeGame: "\u041f\u0435\u0440\u0435\u0434 \u0438\u0433\u0440\u043e\u0439",
  onboarding:
    "\u0412\u043e\u0439\u0434\u0438\u0442\u0435 \u043f\u043e \u043a\u043e\u0434\u0443 \u043b\u043e\u0440\u0434\u0430 \u043d\u0430 \u0441\u0432\u043e\u0435\u043c \u043a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440\u0435. \u041f\u043e\u0441\u043b\u0435 \u0432\u0445\u043e\u0434\u0430 \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432\u043b\u0430\u0434\u0435\u043d\u0438\u0435, \u043a\u0430\u0440\u0442\u0430 \u0438 \u0430\u0440\u043c\u0438\u044f."
} as const;

const normalizeLordAccessCode = (value: string) => value.trim().replace(/\s+/g, "").toLocaleUpperCase("ru-RU");

const preventLordLoginContextMenu = (event: MouseEvent<HTMLElement>) => {
  const target = event.target;

  if (target instanceof HTMLElement && target.closest("input, textarea")) {
    return;
  }

  event.preventDefault();
};

function AnimatedLordLoginScreen() {
  const queryParams = new URLSearchParams(window.location.search);
  const requestedView = queryParams.get("view");
  const apiBaseUrl = getLordRuntimeApiBaseUrl(queryParams);
  const requestedNext = queryParams.get("next");
  const nextPath = requestedNext?.startsWith("/lords/") ? requestedNext : "/lords/home";
  const initialMode: AnimatedLordLoginMode =
    requestedView === "login" || requestedView === "onboarding" ? requestedView : "menu";
  const [mode, setMode] = useState<AnimatedLordLoginMode>(initialMode);
  const [code, setCode] = useState("");
  const [loginError, setLoginError] = useState(queryParams.get("error") === "login" ? lordLoginCopy.invalidCode : "");
  const [isSubmittingLogin, setIsSubmittingLogin] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [pressedTarget, setPressedTarget] = useState<AnimatedLordMenuTarget | null>(null);
  const codeInputRef = useRef<HTMLInputElement>(null);
  const panelControls = useAnimationControls();
  const prefersReducedMotion = useReducedMotion();
  const previewHover = queryParams.get("hover");
  const motionScale = queryParams.get("motion") === "slow" ? 1.75 : 1;

  const movePanelTo = async (nextMode: AnimatedLordLoginMode, target: AnimatedLordMenuTarget | null = null) => {
    if (isTransitioning || nextMode === mode) {
      return;
    }

    setIsTransitioning(true);
    setPressedTarget(target);

    if (!prefersReducedMotion) {
      await panelControls.start({
        y: 12,
        rotate: -0.45,
        transition: { duration: 0.12 * motionScale, ease: "easeOut" }
      });
      await panelControls.start({
        y: "-118vh",
        rotate: 2.2,
        transition: { duration: 0.54 * motionScale, ease: [0.74, 0, 0.28, 1] }
      });
    }

    setMode(nextMode);
    setPressedTarget(null);

    if (!prefersReducedMotion) {
      panelControls.set({ y: "-118vh", rotate: -1.6 });
      await panelControls.start({
        y: 20,
        rotate: 0.7,
        transition: { duration: 0.62 * motionScale, ease: [0.12, 0.82, 0.22, 1] }
      });
      await panelControls.start({
        y: 0,
        rotate: 0,
        transition: { type: "spring", stiffness: 160 / motionScale, damping: 10, mass: 1.1 }
      });
    }

    setIsTransitioning(false);
  };

  const focusCodeInput = () => {
    codeInputRef.current?.focus({ preventScroll: true });
  };

  const handleCodeChange = (value: string) => {
    setCode(value);

    if (loginError) {
      setLoginError("");
    }
  };

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedCode = normalizeLordAccessCode(code);

    if (!normalizedCode) {
      setLoginError(lordLoginCopy.emptyCode);
      window.setTimeout(focusCodeInput, 0);
      return;
    }

    setIsSubmittingLogin(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/role-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ token: normalizedCode })
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(lordLoginCopy.invalidCode);
      }

      const auth = payload as LordRoleTokenAuth;
      const lordId = auth.lord_id || auth.owner_id;
      if (auth.role_type !== "lord" || !lordId) {
        throw new Error(lordLoginCopy.invalidCode);
      }

      localStorage.setItem("witcher_larp_role_token", normalizedCode);
      localStorage.setItem("witcher_larp_lord_id", lordId);
      if (auth.domain_id) {
        localStorage.setItem("witcher_larp_domain_id", auth.domain_id);
      }
      setLoginError("");
      window.location.assign(withLordRuntimeQuery(nextPath, apiBaseUrl));
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : lordLoginCopy.invalidCode);
      window.setTimeout(focusCodeInput, 0);
    } finally {
      setIsSubmittingLogin(false);
    }
  };

  const openTrainingBuild = () => {
    window.location.assign(withLordRuntimeQuery("/lords/home?training=1", apiBaseUrl));
  };

  useEffect(() => {
    if (queryParams.get("auto") !== "login" || mode !== "menu") {
      return;
    }

    const timer = window.setTimeout(() => {
      void movePanelTo("login", "enter");
    }, 240);

    return () => window.clearTimeout(timer);
  }, []);

  return (
    <main className="lord-login-screen" onContextMenu={preventLordLoginContextMenu}>
      <motion.div
        className="lord-login-bg"
        aria-hidden="true"
        style={{ backgroundImage: `url(${lordLoginBackground})` }}
        animate={prefersReducedMotion ? undefined : { scale: [1.02, 1.045, 1.02] }}
        transition={{ duration: 28, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="lord-login-mist"
        animate={prefersReducedMotion ? undefined : { opacity: [0.82, 1, 0.86] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.img
        className="lord-login-logo-image"
        src={lordLoginLogo}
        alt="Witcher LARP I"
        draggable={false}
        animate={
          prefersReducedMotion
            ? undefined
            : {
                filter: [
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 16px rgba(128, 202, 255, .16))",
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 30px rgba(128, 202, 255, .34))",
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 16px rgba(128, 202, 255, .16))"
                ]
              }
        }
        transition={{ duration: 5.8, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.aside
        className={`lord-menu-sign${mode === "login" ? " is-login-panel" : ""}`}
        animate={panelControls}
        initial={{ y: 0, rotate: 0 }}
        style={{ transformOrigin: "50% 5%" }}
        aria-busy={isTransitioning}
      >
        <span className="lord-rise-chain lord-rise-chain-left" aria-hidden="true" />
        <span className="lord-rise-chain lord-rise-chain-right" aria-hidden="true" />
        <img className="lord-menu-art" src={mode === "login" ? lordLoginMenuFrameLong : lordLoginMenuFrame} alt="" draggable={false} />
        <div className="lord-menu-frame">
          <AnimatePresence mode="wait">
            {mode === "menu" ? (
              <motion.div
                key="menu"
                className="lord-menu-buttons lord-panel-content"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.24 * motionScale }}
              >
                <button
                  className={`lord-slot-button${previewHover === "enter" ? " is-hover" : ""}${pressedTarget === "enter" ? " is-pressed" : ""}`}
                  onClick={() => void movePanelTo("login", "enter")}
                  disabled={isTransitioning}
                  aria-label={lordLoginCopy.enter}
                >
                  <span data-label={lordLoginCopy.enter}>{lordLoginCopy.enter}</span>
                </button>
                <button
                  className={`lord-slot-button${previewHover === "training" ? " is-hover" : ""}${pressedTarget === "training" ? " is-pressed" : ""}`}
                  onClick={openTrainingBuild}
                  disabled={isTransitioning}
                  aria-label={lordLoginCopy.training}
                >
                  <span data-label={lordLoginCopy.training}>{lordLoginCopy.training}</span>
                </button>
              </motion.div>
            ) : null}

            {mode === "login" ? (
              <motion.form
                key="login"
                className="lord-login-form lord-panel-content"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 * motionScale }}
                onSubmit={handleLoginSubmit}
              >
                <label
                  className="lord-code-slot"
                  onClick={focusCodeInput}
                  onPointerDown={(event) => {
                    if (event.target !== codeInputRef.current) {
                      event.preventDefault();
                    }
                    focusCodeInput();
                  }}
                >
                  <input
                    autoFocus
                    ref={codeInputRef}
                    aria-label={lordLoginCopy.lordCode}
                    aria-invalid={Boolean(loginError)}
                    aria-describedby={loginError ? "lord-login-error" : undefined}
                    value={code}
                    onChange={(event) => handleCodeChange(event.target.value)}
                    placeholder={lordLoginCopy.codePlaceholder}
                  />
                </label>
                <div className="lord-form-actions">
                  <button className="lord-panel-action-button lord-submit-button" type="submit" disabled={isTransitioning || isSubmittingLogin}>
                    {lordLoginCopy.submit}
                  </button>
                  <button className="lord-panel-action-button lord-back-button" type="button" onClick={() => void movePanelTo("menu")} disabled={isTransitioning || isSubmittingLogin}>
                    {lordLoginCopy.back}
                  </button>
                </div>
                <AnimatePresence>
                  {loginError ? (
                    <motion.p
                      key="lord-login-error"
                      id="lord-login-error"
                      className="lord-login-error"
                      role="alert"
                      initial={{ opacity: 0, y: -6, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4, scale: 0.97 }}
                      transition={{ duration: 0.18 * motionScale }}
                    >
                      {loginError}
                    </motion.p>
                  ) : null}
                </AnimatePresence>
              </motion.form>
            ) : null}

            {mode === "onboarding" ? (
              <motion.div
                key="onboarding"
                className="lord-onboarding-panel lord-panel-content"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 * motionScale }}
              >
                <h1>{lordLoginCopy.beforeGame}</h1>
                <p>{lordLoginCopy.onboarding}</p>
                <button className="lord-panel-action-button" type="button" onClick={() => void movePanelTo("menu")} disabled={isTransitioning}>
                  {lordLoginCopy.back}
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </motion.aside>
    </main>
  );
}

export default App;
