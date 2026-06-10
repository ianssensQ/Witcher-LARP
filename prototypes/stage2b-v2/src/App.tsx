import { useCallback, useEffect, useRef, useState } from "react";
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
  FileWarning,
  Flame,
  FlaskConical,
  Gem,
  Gavel,
  Hammer,
  Hourglass,
  Layers,
  Map,
  Maximize2,
  Minimize2,
  Mountain,
  Package,
  Route,
  ScrollText,
  Shield,
  Skull,
  Sparkles,
  Swords,
  TreePine,
  Trophy,
  Users,
  Waves,
  Wifi,
  XCircle
} from "lucide-react";
import buildingTreeBg from "./assets/generated/building-tree-bg-v6-holes.png";
import castleCity from "./assets/generated/castle-city-v2.png";
import gwentTable from "./assets/generated/gwent-table-v2.png";
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
import arcaneCutout from "./assets/generated/map-cutouts/arcane.png";
import capitalCutout from "./assets/generated/map-cutouts/capital.png";
import emberFortCutout from "./assets/generated/map-cutouts/ember-fort.png";
import fieldsCutout from "./assets/generated/map-cutouts/fields.png";
import northFortCutout from "./assets/generated/map-cutouts/north-fort.png";
import riverGateCutout from "./assets/generated/map-cutouts/river-gate.png";
import ruinsCutout from "./assets/generated/map-cutouts/ruins.png";
import swampCutout from "./assets/generated/map-cutouts/swamp.png";
import witchwoodCutout from "./assets/generated/map-cutouts/witchwood.png";
import { LordMpHud, useLordMpRuntimeState } from "./LordMpHud";
import LordBattleScreen from "./LordBattleScreen";

type Tone = "gold" | "green" | "blue" | "red" | "violet" | "muted";

const territoryNodes = [
  { id: "north-fort", label: "Северный форт", x: 22, y: 28, tone: "blue", icon: Mountain, income: "+12 зол.", owner: "Север", status: "укреплен", cutoutWidth: 31.82 },
  { id: "witchwood", label: "Ведьмин лес", x: 34, y: 45, tone: "green", icon: TreePine, income: "+2 травы", owner: "ничья", status: "опасен", cutoutWidth: 31.82 },
  { id: "river-gate", label: "Речные ворота", x: 47, y: 38, tone: "blue", icon: Waves, income: "+1 путь", owner: "Север", status: "открыт", cutoutWidth: 35.64 },
  { id: "capital", label: "Белый Холм", x: 51, y: 55, tone: "gold", icon: Castle, income: "+25 зол.", owner: "Север", status: "спорный", cutoutWidth: 54.74 },
  { id: "fields", label: "Поля Сиверии", x: 67, y: 58, tone: "gold", icon: Coins, income: "+8 зерна", owner: "Север", status: "богатый", cutoutWidth: 35.64 },
  { id: "swamp", label: "Топь", x: 78, y: 72, tone: "green", icon: FlaskConical, income: "+1 реагент", owner: "ничья", status: "скрыта", cutoutWidth: 38.19 },
  { id: "ruins", label: "Черные руины", x: 17, y: 72, tone: "red", icon: Skull, income: "+1 улика", owner: "тьма", status: "прокляты", cutoutWidth: 38.19 },
  { id: "ember-fort", label: "Южный бастион", x: 56, y: 80, tone: "red", icon: Flame, income: "+10 зол.", owner: "Юг", status: "заперт", cutoutWidth: 31.82 },
  { id: "arcane", label: "Башня знаков", x: 73, y: 31, tone: "violet", icon: Sparkles, income: "+1 знак", owner: "чародеи", status: "тайная", cutoutWidth: 34.37 }
] as const;

const mapCutouts = {
  "north-fort": northFortCutout,
  witchwood: witchwoodCutout,
  "river-gate": riverGateCutout,
  capital: capitalCutout,
  fields: fieldsCutout,
  swamp: swampCutout,
  ruins: ruinsCutout,
  "ember-fort": emberFortCutout,
  arcane: arcaneCutout
} as const;

const toneColor: Record<Tone, string> = {
  gold: "#d9a64f",
  green: "#74c68a",
  blue: "#73c6d8",
  red: "#c86152",
  violet: "#a88be8",
  muted: "#b4aa9c"
};

const routeLines = [
  ["north-fort", "witchwood"],
  ["witchwood", "capital"],
  ["river-gate", "capital"],
  ["capital", "fields"],
  ["fields", "swamp"],
  ["capital", "ember-fort"],
  ["witchwood", "ruins"],
  ["river-gate", "arcane"]
] as const;

const buildingNodes = [
  { name: "Ратуша", state: "purchased", x: 48, y: 76, cost: "построено" },
  { name: "Казармы I", state: "purchased", x: 30, y: 55, cost: "построено" },
  { name: "Казармы II", state: "ready", x: 30, y: 37, cost: "80 зол. / 10 железа" },
  { name: "Арсенал", state: "locked", x: 30, y: 20, cost: "нужны Казармы II" },
  { name: "Рынок", state: "purchased", x: 48, y: 55, cost: "построено" },
  { name: "Гильдия", state: "ready", x: 48, y: 37, cost: "90 зол. / 2 влияния" },
  { name: "Башня мага", state: "locked", x: 48, y: 20, cost: "нужна Гильдия" },
  { name: "Конюшни", state: "ready", x: 66, y: 55, cost: "70 зол. / 8 зерна" },
  { name: "Ристалище", state: "locked", x: 66, y: 37, cost: "нужны Конюшни" }
] as const;

const army = [
  { name: "Стража", type: "гарнизон", hp: "16", atk: "4", tone: "blue" },
  { name: "Мечники", type: "пехота", hp: "12", atk: "5", tone: "gold" },
  { name: "Лучники", type: "стрелки", hp: "8", atk: "6", tone: "green" },
  { name: "Кавалерия", type: "конница", hp: "14", atk: "7", tone: "red" }
] as const;

const gwentCards = [
  { name: "Следопыт", power: 4, row: "ближний ряд", tone: "green" },
  { name: "Алхимик", power: 2, row: "особая карта", tone: "violet" },
  { name: "Арбалетчик", power: 5, row: "дальний ряд", tone: "blue" },
  { name: "Осадник", power: 7, row: "осадный ряд", tone: "gold" },
  { name: "Туман", power: 0, row: "погода", tone: "muted" }
] as const;

const reviewRows = [
  { id: "П0-14", title: "бумажный бой лорда спорит с текущей доской", tone: "red" },
  { id: "П1-08", title: "награда заблокирована до решения мастера", tone: "gold" },
  { id: "П2-22", title: "согласие фаворита ожидает чародейку 3", tone: "violet" },
  { id: "П3-11", title: "повторная сцена уже учтена и скрыта", tone: "blue" }
] as const;

const lordHomeStats = [
  { label: "Золото", value: "80", detail: "+25/час", icon: Coins, tone: "gold" },
  { label: "Влияние", value: "14", detail: "2-е место", icon: Gem, tone: "violet" },
  { label: "Акт", value: "II", detail: "42 мин.", icon: Hourglass, tone: "blue" }
] as const;

const lordHomeTimers = [
  { label: "Ходы армии", value: "4/6", detail: "пополнение через 12 мин.", icon: Route },
  { label: "Доход", value: "+25", detail: "следующий тик через 18 мин.", icon: Coins }
] as const;

const lordHomeActions = [
  {
    id: "castle",
    label: "Замок",
    detail: "Резиденция, здания и доступные улучшения.",
    state: "1 доступно",
    icon: Castle,
    tone: "gold"
  },
  {
    id: "orders",
    label: "Заказы",
    detail: "Публичные и адресные поручения исполнителям.",
    state: "2/3",
    icon: ScrollText,
    tone: "violet"
  },
  {
    id: "raids",
    label: "Рейды",
    detail: "Жетоны, золото и временные эффекты.",
    state: "1 жетон",
    icon: Flame,
    tone: "red"
  },
  {
    id: "battle",
    label: "Бой",
    detail: "Отдельное поле 5x6, ход и таймер.",
    state: "нет боя",
    icon: Swords,
    tone: "red"
  }
] as const;

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
  node_id?: string;
  status?: string;
  income_per_hour?: number;
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
  incomePerHour: number;
  heroHere: boolean;
  isOwned: boolean;
  status: string;
  garrisonCapacity: number;
  garrisonSlotsUsed: number;
};
type LordHomeDomainStats = {
  incomePerHour: number;
  rawIncomePerHour: number;
  territoryIncomePerHour: number;
  currentMp: number;
  mpCap: number;
  activeArmyCapacity: number;
  activeArmySlotsUsed: number;
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

const lordHomeInitialRecruitStock: Record<LordHomeTerritoryId, Record<LordHomeUnitId, { rate: number; stock: number }>> = {
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

type LordHomeRecruitOffer = {
  offerId: string;
  cardId: string;
  status: string;
  cost: number;
  rate: number;
  stock: number;
};

type LordHomeBackendState = {
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
  };
  movement?: {
    current_node_id?: string;
    current_mp?: number;
    mp_cap?: number;
  };
  timer_summary?: LordHomeBackendTimerSummary;
  building_catalog?: Array<{ building_id?: string; status?: string }>;
  owned_buildings?: Array<{ building_id?: string; status?: string }>;
  territories?: LordHomeBackendTerritory[];
  neutral_territories?: LordHomeBackendTerritory[];
  other_territories?: LordHomeBackendTerritory[];
  active_army?: LordHomeBackendStack[];
  orders?: LordHomeOrder[];
  order_cap?: LordHomeOrderCap;
  escrow?: LordHomeOrderEscrow;
  order_conflicts?: unknown[];
  visible_targets?: LordHomeOrderTarget[];
  eligible_recipients?: LordHomeOrderRecipient[];
  order_reward_options?: LordHomeOrderRewardOption[];
  raid_tokens?: number;
  raid_rules?: LordHomeRaidRule[];
  raid_targets?: LordHomeRaidTarget[];
  active_raid_effects?: LordHomeRaidEffect[];
  raid_history?: LordHomeRaidEffect[];
  raid_effects?: LordHomeRaidEffect[];
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

type LordHomeBuildingPurchaseResponse = {
  status?: string;
  building_id?: string;
  gold_spent?: number;
};

type LordHomeRecruitActionResponse = {
  status?: string;
  territory_id?: string;
  count?: number;
  gold_spent?: number;
};

const lordHomeDefaultLordId = "p_lord_1";
const lordHomeDefaultRoleToken = "LORD-NORTH-R8K4";
const lordHomeClockTickMs = 1000;
const lordHomeStatePollMs = 15_000;

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

type LordMapBackendState = LordHomeBackendState & {
  lord?: { domain_id?: string };
  domain?: LordHomeBackendState["domain"] & LordMapBackendMovement;
  movement?: LordMapBackendMovement;
  pending_move?: LordMapBackendPendingMove | null;
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
type LordHomePanel = "map" | "orders" | "raids" | "battle" | "help";
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
};

type LordHomeOrderRecipient = {
  player_id: string;
  display_name?: string;
  role_label?: string;
};

type LordHomeOrderRewardOption = {
  reward_id: string;
  label?: string;
  gold?: number;
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
  loot_applied?: boolean;
  loot_gold?: number;
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
  token_cost: number;
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
  reward: { reward_id?: string };
  source: string;
};

type LordHomeRaidStartPayload = {
  target_territory_id: string;
  rule_id: string;
  expected_token_cost: number;
  expected_gold_cost: number;
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

const lordHomeRaidNodePositions: Record<string, Array<{ x: number; y: number }>> = {
  economy: [{ x: 21, y: 28 }],
  military: [{ x: 44, y: 25 }],
  recruit: [{ x: 29, y: 52 }],
  intrigue: [{ x: 57, y: 50 }],
  loot: [{ x: 43, y: 73 }],
  residence: [{ x: 73, y: 32 }]
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
    gold_cost: 15,
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
    gold_cost: 20,
    duration_minutes: 30,
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
    gold_cost: 25,
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
    gold_cost: 25,
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
    token_cost: 1,
    gold_cost: 30,
    duration_minutes: 10,
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
    gold_cost: 45,
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
    effect: "Открывает базовую пехоту и добавляет слот походной пачки."
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
    effect: "Открывает стражу для удержания линии и фортификаций."
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
    effect: "Дает стабильный источник стрелков и дальнюю защиту владения."
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
    effect: "Открывает кавалерию и ускоряет подготовку мобильных отрядов."
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
    raidUnlock: true,
    x: 50.2,
    y: 44.8,
    effect: "Открывает тяжелую осаду и усиливает давление в рейдах."
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
    effect: "Готовит специалистов, улучшает боевые решения и рейдовую координацию."
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
    effect: "Запускает торговый доход и базовый оборот ресурсов."
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
    effect: "Повышает регулярный доход владения и прозрачность казны."
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
    effect: "Дает запас вместимости и поддерживает дорогие ветки строительства."
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
    effect: "Укрепляет казну и снижает риск просадки экономики."
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
    effect: "Финальная экономическая опора дома, усиливает крупные покупки и удержание территорий."
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
    effect: "Открывает публичные поручения и связку лорда с наемниками."
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
    effect: "Усиливает адресные заказы, переговоры и влияние дома."
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
    effect: "Дает лучшие сведения о маршрутах и подготовке передвижений."
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
    effect: "Открывает планирование рейдов и временные эффекты давления."
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
    effect: "Связывает приказы, рейды и армию в одно стратегическое решение."
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
    effect: "Открывает магическую ветку, защиту и разведку владения."
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
    effect: "Укрепляет реагенты, защиту от истощения и подготовку оберегов."
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
    effect: "Дает разведку, предупреждения и осторожный взгляд за пределы владения."
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
    effect: "Снижает урон от рейдов и укрепляет магическую оборону дома."
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
    raidUnlock: true,
    x: 40.6,
    y: 13.2,
    effect: "Финальная магическая постройка: тайные решения, защита и редкие рейдовые эффекты."
  }
];

const lordBuildingKnownIds = new Set(lordBuildingTreeNodes.map((building) => building.id));

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
  insufficient_gold: "Недостаточно золота",
  missing_prerequisites: "Сначала нужны предыдущие постройки",
  invalid_count: "Количество должно быть больше нуля",
  missing_offer: "Предложение найма не выбрано",
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
  rule_locked: "Рейд закрыт постройками",
  invalid_target: "Цель не подходит для этого рейда",
  duplicate_active_effect: "Цель уже под таким эффектом",
  stale_expected_cost: "Стоимость изменилась, обновите экран",
  final_lock: "Финал закрыл новые рейды",
  raid_rule_not_found: "План рейда недоступен",
  territory_not_found: "Цель рейда недоступна"
};

const getLordHomeApiErrorMessage = (payload: unknown, fallback: string) => {
  if (!isLordHomeRecord(payload)) {
    return fallback;
  }

  const detail = payload.detail;
  if (typeof detail === "string") {
    return detail;
  }

  if (isLordHomeRecord(detail)) {
    if (typeof detail.code === "string" && lordHomeApiErrorLabelByCode[detail.code]) {
      return lordHomeApiErrorLabelByCode[detail.code];
    }
    if (typeof detail.message === "string") {
      return detail.message;
    }
    if (typeof detail.code === "string") {
      return detail.code;
    }
  }

  return fallback;
};

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

const getLordHomeRaidNodePosition = (rule: LordHomeRaidRule, index: number) => {
  const positions = lordHomeRaidNodePositions[rule.category] ?? lordHomeRaidNodePositions.economy;
  const base = positions[index % positions.length] ?? positions[0];
  const rowOffset = Math.floor(index / positions.length) * 7;
  return {
    x: rule.x ?? Math.min(84, base.x + rowOffset),
    y: rule.y ?? Math.min(82, base.y + rowOffset)
  };
};

const normalizeLordHomeRaidRule = (rule: LordHomeRaidRule, index: number): LordHomeRaidRule => {
  const fallback = lordHomeFallbackRaidRules[index % lordHomeFallbackRaidRules.length];
  const category = rule.category || fallback.category;
  return {
    ...fallback,
    ...rule,
    rule_id: rule.rule_id || fallback.rule_id,
    name: rule.name || fallback.name,
    tier: Number(rule.tier ?? fallback.tier) || fallback.tier,
    category,
    category_label: rule.category_label || getLordHomeRaidCategoryMeta(category).label,
    description: rule.description || fallback.description,
    token_cost: Number(rule.token_cost ?? fallback.token_cost) || 0,
    gold_cost: Number(rule.gold_cost ?? fallback.gold_cost) || 0,
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
  tier: Number(target.tier ?? 1) || 1,
  owner_label: target.owner_label || target.owner_domain_id || "ничья",
  bonus_label: target.bonus_label || target.bonus_type || "земля",
  active_effects: target.active_effects ?? [],
  can_target: target.can_target !== false
});

const isLordHomeRaidTargetCompatible = (rule: LordHomeRaidRule, target: LordHomeRaidTarget | null) => {
  if (!target) return false;
  const allowed = new Set(rule.allowed_target_types);
  if (target.is_residence) {
    return allowed.has("residence");
  }
  return allowed.has("territory") || allowed.has("contested") || allowed.has("b_raid_only");
};

const getLordHomeRaidBlockReason = ({
  rule,
  target,
  raidTokens,
  lordGold,
  activeEffects,
  isSubmitting
}: {
  rule: LordHomeRaidRule | null;
  target: LordHomeRaidTarget | null;
  raidTokens: number;
  lordGold: number;
  activeEffects: LordHomeRaidEffect[];
  isSubmitting: boolean;
}) => {
  if (isSubmitting) return "Печать уже ставится";
  if (!rule) return "План рейда не выбран";
  if (!target) return "Цель рейда не выбрана";
  if (rule.locked_reason) return rule.locked_reason;
  if (raidTokens < rule.token_cost) return "Нет рейдового жетона";
  if (lordGold < rule.gold_cost) return "Недостаточно золота";
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

const getLordHomeOrderWindowLabel = (order: LordHomeOrder) => {
  if (order.expires_at) {
    return order.expires_at;
  }
  const actMatch = String(order.target_act_id ?? "").match(/act_?(\d+)/i);
  return actMatch ? `Акт ${actMatch[1]}` : "Текущее окно";
};

const getLordHomeOrderRewardGold = (reward?: LordHomeOrderRewardOption | null) => {
  const gold = Number(reward?.gold ?? 0);
  return Number.isFinite(gold) ? Math.max(0, gold) : 0;
};

const getLordHomeOrderEscrowLabel = (order?: LordHomeOrder | null) => {
  const label = order?.escrow_label || "";
  if (/^в escrow$/i.test(label)) return "В залоге";
  if (/^нет escrow$/i.test(label)) return "нет";
  return label || "нет";
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

const lordBuildingRecruitLabels: Record<string, string> = {
  unit_infantry_t1: "мечники",
  unit_guard_t1: "стража",
  unit_ranged_t1: "лучники",
  unit_cavalry_t2: "кавалерия",
  unit_heavy_siege_t3: "осадники",
  unit_specialist_t3: "инженеры"
};

const lordBuildingBaseBenefitLabels: Record<string, string[]> = {
  b_market: ["Торговый доход"],
  b_tax_office: ["Рост дохода владения"],
  b_bank: ["Укрепление казны"],
  b_treasury_hall: ["Крупные покупки и удержание земель"],
  b_notice_board: ["Публичные поручения"],
  b_envoy_hall: ["Переговоры и адресные заказы"],
  b_map_room: ["Разведка маршрутов"],
  b_raid_office: ["Планирование рейдов"],
  b_alchemy_lab: ["Реагенты и защита"],
  b_scrying_room: ["Разведка"],
  b_wards: ["Защита от рейдов"],
  b_ritual_chamber: ["Редкие магические эффекты"]
};

const getLordBuildingState = (building: LordBuildingNode, builtBuildingIds: Set<string>): LordBuildingState => {
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
  activeArmySlotsUsed: lordHomeInitialArmy.length
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

const lordMapModeButtons = [
  { id: "march", label: "Поход", icon: Route },
  { id: "info", label: "Сведения", icon: ScrollText }
] as const satisfies ReadonlyArray<{ id: LordMapMode; label: string; icon: typeof Route }>;

const lordMapLayerButtons = [
  { id: "roads", label: "Дороги", icon: Route },
  { id: "territories", label: "Террит.", icon: Map },
  { id: "costs", label: "MP", icon: Layers }
] as const satisfies ReadonlyArray<{ id: LordMapLayerId; label: string; icon: typeof Route }>;

const lordMapSockets = [
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
] satisfies Array<{
  id: string;
  name: string;
  x: number;
  y: number;
  tone: LordMapSocketTone;
  owner: string;
  route: string;
}>;
type LordMapSocket = (typeof lordMapSockets)[number];
type LordMapRoadPoint = readonly [number, number];

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
    income: "+8 золота/час",
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
    income: "+8 золота/час",
    hire: "копейщики T1",
    defense: "+2 к обороне",
    garrison: "6 отрядов",
    neutralDefense: "острожная стража, остановка при входе"
  },
  node_fort_southwest: {
    tier: "T2",
    bonus: "южный рубеж, дорога к утесу",
    income: "+7 золота/час",
    hire: "ополчение T1",
    defense: "+2 к обороне",
    garrison: "6 отрядов",
    neutralDefense: "нейтральная крепь, остановка при входе"
  },
  node_spanish_magic: {
    tier: "T2",
    bonus: "магический спор",
    income: "+1 знак/час",
    magic: "ритуальный узел",
    orders: "заявка магам",
    neutralDefense: "нестабильная зона, остановка при входе"
  },
  node_science_barn: {
    tier: "T2",
    bonus: "мануфактура",
    income: "+10 золота/час",
    hire: "нет",
    orders: "ремесленный заказ"
  }
};

const getLordMapDefaultTerritoryProfile = (socket: LordMapSocket): LordMapTerritoryProfile => {
  if (isLordMapResidenceSocket(socket)) {
    return {
      tier: "T3",
      bonus: "резиденция дома",
      income: "+18 золота/час",
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
      income: "+6 золота/час",
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
      income: "+5 золота/час",
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
      income: "+4 золота/час",
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
      income: "+4 золота/час",
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
    income: "+5 золота/час",
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
] as const satisfies ReadonlyArray<{
  id: string;
  from: string;
  to: string;
  cost: number;
  points: readonly LordMapRoadPoint[];
}>;

const lordMapMovementPoints = 6;

const getLordMapSocketById = (socketId: string) =>
  lordMapSockets.find((socket) => socket.id === socketId) ?? lordMapSockets[0];

const getLordMapLordIdFromValue = (value: string | null | undefined): LordMapLordId | null => {
  if (value === "north" || value === "domain_north") return "north";
  if (value === "river" || value === "domain_river") return "river";
  if (value === "forest" || value === "domain_forest") return "forest";
  if (value === "hill" || value === "domain_hill") return "hill";
  return null;
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

const getLordMapKnownRouteIds = (routeIds: string[] | undefined) =>
  (Array.isArray(routeIds) ? routeIds : []).filter((socketId) =>
    lordMapSockets.some((socket) => socket.id === socketId)
  );

const getLordMapPendingRouteIds = (pendingMove: LordMapBackendPendingMove | null | undefined) =>
  getLordMapKnownRouteIds(pendingMove?.route_node_ids ?? pendingMove?.route);

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

const getLordMapDirectCost = (fromId: string, toId: string) => {
  const edge = lordMapTravelEdges.find(
    (travelEdge) =>
      (travelEdge.from === fromId && travelEdge.to === toId) ||
      (travelEdge.from === toId && travelEdge.to === fromId)
  );

  return edge?.cost ?? null;
};

const getLordMapTravelEdge = (fromId: string, toId: string) =>
  lordMapTravelEdges.find(
    (travelEdge) =>
      (travelEdge.from === fromId && travelEdge.to === toId) ||
      (travelEdge.from === toId && travelEdge.to === fromId)
  );

const getLordMapEdgePoints = (fromId: string, toId: string) => {
  const edge = getLordMapTravelEdge(fromId, toId);

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

const getLordMapPointStyle = (point: { x: number; y: number }) => ({
  left: `${(point.x / lordMapRoadViewBox.width) * 100}%`,
  top: `${(point.y / lordMapRoadViewBox.height) * 100}%`
});

const getLordMapRouteSegments = (pathIds: string[]) =>
  pathIds.slice(1).map((socketId, index) => {
    const fromId = pathIds[index];
    const points = getLordMapEdgePoints(fromId, socketId);
    return {
      id: `${fromId}-${socketId}`,
      points
    };
  }).filter((segment) => segment.points.length > 1);

const isLordMapResidenceSocket = (socket: LordMapSocket) => socket.id.startsWith("node_res_");

const isLordMapForeignResidence = (socket: LordMapSocket, currentLord: LordMapRouteLord) =>
  isLordMapResidenceSocket(socket) && socket.tone !== currentLord.tone;

const isLordMapRouteStopSocket = (socket: LordMapSocket, currentLord: LordMapRouteLord) =>
  socket.tone !== currentLord.tone;

type LordMapTravelNeighbor = { id: string; cost: number };

const getLordMapNeighbors = (socketId: string) => {
  const neighbors: LordMapTravelNeighbor[] = [];

  lordMapTravelEdges.forEach((travelEdge) => {
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

const getLordMapTravelState = (startSocketId: string, currentLord: LordMapRouteLord) => {
  const distances: Record<string, number> = {};
  const previous: Record<string, string | null> = {};
  const unsettled = lordMapSockets.map((socket) => socket.id);

  lordMapSockets.forEach((socket) => {
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

    getLordMapNeighbors(currentId).forEach((neighbor) => {
      const neighborSocket = getLordMapSocketById(neighbor.id);

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

const getLordMapPathCost = (pathIds: string[]) =>
  pathIds.slice(1).reduce((totalCost, socketId, index) => {
    const previousSocketId = pathIds[index];
    return totalCost + (getLordMapDirectCost(previousSocketId, socketId) ?? 0);
  }, 0);

const getLordMapFirstContactSocketId = (pathIds: string[], currentLord: LordMapRouteLord) =>
  pathIds.slice(1).find((socketId) => isLordMapRouteStopSocket(getLordMapSocketById(socketId), currentLord)) ?? null;

const getLordMapRoutePreview = (
  startSocketId: string,
  requestedSocketId: string,
  currentLord: LordMapRouteLord,
  movementPoints = lordMapMovementPoints
): LordMapRoutePreview => {
  const requestedSocket = getLordMapSocketById(requestedSocketId);

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

  const travelState = getLordMapTravelState(startSocketId, currentLord);
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
  const cost = getLordMapPathCost(fullPathIds);
  const contactSocketId = getLordMapFirstContactSocketId(fullPathIds, currentLord);
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

const getLordMapPointAlongPath = (pathIds: string[], progress: number) => {
  if (pathIds.length === 0) {
    return { x: 0, y: 0 };
  }

  if (pathIds.length === 1) {
    const socket = getLordMapSocketById(pathIds[0]);
    return { x: socket.x, y: socket.y };
  }

  const normalizedProgress = Math.min(Math.max(progress, 0), 1);
  const pathCost = getLordMapPathCost(pathIds);
  const totalCost = pathCost > 0 ? pathCost : pathIds.length - 1;
  let coveredCost = normalizedProgress * totalCost;

  for (let index = 0; index < pathIds.length - 1; index += 1) {
    const fromSocket = getLordMapSocketById(pathIds[index]);
    const toSocket = getLordMapSocketById(pathIds[index + 1]);
    const edgeCost = getLordMapDirectCost(fromSocket.id, toSocket.id) ?? 1;

    if (coveredCost <= edgeCost) {
      const localProgress = edgeCost > 0 ? coveredCost / edgeCost : 1;
      return {
        x: fromSocket.x + (toSocket.x - fromSocket.x) * localProgress,
        y: fromSocket.y + (toSocket.y - fromSocket.y) * localProgress
      };
    }

    coveredCost -= edgeCost;
  }

  const lastSocket = getLordMapSocketById(pathIds[pathIds.length - 1]);
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
    unlock: "+25 золота в час и удержание предложения найма.",
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

const lordEndpointLinks = [
  {
    path: "/login",
    title: "Legacy showcase login",
    detail: "Old Stage 2B showcase/fallback from the screenshot; not the active lord login.",
    state: "legacy",
    icon: Layers,
    tone: "red"
  },
  {
    path: "/lords/login",
    title: "Вход лорда",
    detail: "Игровой код роли, валидный вход в лордский контур.",
    state: "current",
    icon: Crown,
    tone: "blue"
  },
  {
    path: "/lords/castle",
    title: "Замок",
    detail: "Основная страница после входа: резиденция, ветки развития и здания.",
    state: "legacy",
    icon: Castle,
    tone: "muted"
  },
  {
    path: "/lords/home",
    title: "Карта владений",
    detail: "Крупная карта, мини-карта и переходы в замок, заказы и рейды.",
    state: "current",
    icon: Map,
    tone: "green"
  },
  {
    path: "/lords/dashboard",
    title: "Карта, алиас",
    detail: "Тот же экран карты для старых ссылок и тестов.",
    state: "legacy alias",
    icon: Route,
    tone: "muted"
  },
  {
    path: "/lords",
    title: "Основной вход",
    detail: "Алиас основной страницы лорда, сейчас ведет в замок.",
    state: "legacy alias",
    icon: Castle,
    tone: "muted"
  },
  {
    path: "/",
    title: "Stage 2B обзор",
    detail: "Общая витрина прототипов и старых экранов Stage 2B.",
    state: "legacy showcase",
    icon: Layers,
    tone: "muted"
  }
] as const;

const toneClass: Record<Tone, string> = {
  gold: "border-ember-300/70 bg-ember-300/20 text-ember-50",
  green: "border-emerald-300/55 bg-emerald-500/15 text-emerald-100",
  blue: "border-cyan-300/55 bg-cyan-500/15 text-cyan-100",
  red: "border-red-300/60 bg-red-500/15 text-red-100",
  violet: "border-arcane-300/60 bg-arcane-500/20 text-violet-100",
  muted: "border-stone-300/35 bg-stone-400/10 text-stone-200"
};

function App() {
  if (window.location.pathname === "/lords/login") {
    return <AnimatedLordLoginScreen />;
  }

  if (window.location.pathname === "/lords/battle") {
    return <LordBattleScreen />;
  }


  if (["/lords/endpoints", "/endpoints"].includes(window.location.pathname)) {
    return <LordEndpointIndexScreen />;
  }

  if (window.location.pathname === "/lords/map") {
    return <LordMapScreen />;
  }

  if (["/lords/home", "/lords/dashboard"].includes(window.location.pathname)) {
    return <LordHomeScreen />;
  }

  if (["/lords", "/lords/castle"].includes(window.location.pathname)) {
    return <LordCastleScreen />;
  }

  return (
    <main className="min-h-screen bg-night-950 text-ember-50">
      <LegacyPrototypeNotice />
      <HeroHeader />
      <section className="mx-auto flex w-full max-w-[1760px] flex-col gap-8 px-5 pb-16 md:px-8">
        <LordCommandTable />
        <GwentBoard />
        <MobileRoleScreens />
        <AdminOps />
        <AssetHandoff />
      </section>
    </main>
  );
}

function LegacyPrototypeNotice() {
  return (
    <div className="border-b border-red-300/30 bg-red-950/70 px-5 py-3 text-sm text-red-50 md:px-8">
      <div className="mx-auto flex w-full max-w-[1760px] flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <strong className="uppercase tracking-[.24em] text-red-200">Legacy / reference</strong>
        <span className="text-red-50/85">
          Current lord flow: <a className="underline decoration-red-200/60 underline-offset-4" href="/lords/login">/lords/login</a>{" -> "}
          <a className="underline decoration-red-200/60 underline-offset-4" href="/lords/home">/lords/home</a>{" -> "}
          <a className="underline decoration-red-200/60 underline-offset-4" href="/lords/home?panel=orders">/lords/home?panel=orders</a>
        </span>
      </div>
    </div>
  );
}

function LordMapScreen() {
  const mapRouteParams = new URLSearchParams(window.location.search);
  const apiBaseUrl = (mapRouteParams.get("api") || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const backendLordId =
    mapRouteParams.get("lord_id") ||
    mapRouteParams.get("lordId") ||
    localStorage.getItem("witcher_larp_lord_id") ||
    lordHomeDefaultLordId;
  const backendRoleToken =
    mapRouteParams.get("token") ||
    localStorage.getItem("witcher_larp_role_token") ||
    lordHomeDefaultRoleToken;
  const [currentLordId, setCurrentLordId] = useState<LordMapLordId>(() => getLordMapCurrentLordId());
  const currentLord = lordMapLordMeta[currentLordId];
  const initialSelectedSocketId = getLordMapInitialSelectedSocketId(currentLord.homeSocketId);
  const [armySocketId, setArmySocketId] = useState(currentLord.homeSocketId);
  const [routeStartSocketId, setRouteStartSocketId] = useState(currentLord.homeSocketId);
  const [selectedSocketId, setSelectedSocketId] = useState(initialSelectedSocketId);
  const [hoveredSocketId, setHoveredSocketId] = useState<string | null>(null);
  const [movementDraft, setMovementDraft] = useState<LordMapMovementDraft | null>(null);
  const [armyTravelProgress, setArmyTravelProgress] = useState(0);
  const [backendState, setBackendState] = useState<LordMapBackendState | null>(null);
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
  const routePreviewSerialRef = useRef(0);
  const lastPendingMoveRef = useRef<LordMapBackendPendingMove | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const backendPendingMove = backendState?.pending_move?.status === "pending" ? backendState.pending_move : null;
  const pendingPathIds = getLordMapPendingRouteIds(backendPendingMove);
  const isBackendPendingMove = Boolean(backendPendingMove);
  const isMarching = movementDraft !== null || isBackendPendingMove || isMoveSubmitting;
  const backendMovement = backendState?.movement ?? backendState?.domain ?? null;
  const backendCurrentMp = Number(backendMovement?.current_mp);
  const mapMovementPoints = Number.isFinite(backendCurrentMp) ? Math.max(0, backendCurrentMp) : lordMapMovementPoints;
  const backendMpCap = Number(backendMovement?.mp_cap);
  const mapMovementCap = Number.isFinite(backendMpCap) ? Math.max(mapMovementPoints, backendMpCap) : lordMapMovementPoints;
  const isMarchMode = mapMode === "march";

  const fetchLordMapState = useCallback(async (options?: { silent?: boolean }) => {
    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (backendRoleToken) {
        headers["X-Role-Token"] = backendRoleToken;
      }

      const response = await fetch(`${apiBaseUrl}/api/lords/${backendLordId}/state`, { headers });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Приказная не отвечает"));
      }

      const nextState = payload as LordMapBackendState;
      setBackendState(nextState);
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
      if (currentNodeId && lordMapSockets.some((socket) => socket.id === currentNodeId)) {
        setArmySocketId(currentNodeId);
        setRouteStartSocketId(currentNodeId);
      }

      const pendingMove = nextState.pending_move?.status === "pending" ? nextState.pending_move : null;
      const pendingTargetId = pendingMove?.requested_to_node_id ?? pendingMove?.to_node_id;
      if (pendingTargetId && lordMapSockets.some((socket) => socket.id === pendingTargetId)) {
        setSelectedSocketId(pendingTargetId);
      }
    } catch (error) {
      setBackendState(null);
      setMapApiState("offline");
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      if (!options?.silent) {
        setMapActionStatus(error instanceof Error ? error.message : "Приказная не отвечает");
      }
    }
  }, [apiBaseUrl, backendLordId, backendRoleToken]);

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
      void fetchLordMapState({ silent: true });
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
      void fetchLordMapState({ silent: true });
    }, 700);
    const timing = getLordMapMoveTiming(backendPendingMove, Date.now());
    const arrivalDelayMs = Math.max(160, timing.remainingSeconds * 1000 + 180);
    const arrivalTimeoutId = window.setTimeout(() => {
      void fetchLordMapState({ silent: true });
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
    if (arrivedSocketId && lordMapSockets.some((socket) => socket.id === arrivedSocketId)) {
      setMapActionStatus(`Армия прибыла: ${getLordMapSocketById(arrivedSocketId).name}.`);
    }
  }, [backendPendingMove, backendState]);

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

  const selectedSocket = getLordMapSocketById(selectedSocketId);
  const pendingDisplaySocketId = backendPendingMove?.requested_to_node_id ?? backendPendingMove?.to_node_id;
  const displaySocketId = movementDraft?.targetSocketId ?? pendingDisplaySocketId ?? (isMarchMode ? hoveredSocketId : null) ?? selectedSocketId;
  const displaySocket = getLordMapSocketById(displaySocketId);
  const armySocket = getLordMapSocketById(armySocketId);
  const routeStartSocket = getLordMapSocketById(routeStartSocketId);
  const displayRoutePreview = getLordMapRoutePreview(routeStartSocketId, displaySocket.id, currentLord, mapMovementPoints);
  const previewTargetSocket = getLordMapSocketById(displayRoutePreview.targetSocketId);
  const serverPreviewForDisplay =
    serverRoutePreview &&
    serverRoutePreview.requested_to_node_id === displayRoutePreview.requestedSocketId &&
    (!serverRoutePreview.from_node_id || serverRoutePreview.from_node_id === armySocketId)
      ? serverRoutePreview
      : null;
  const serverRouteIds = getLordMapKnownRouteIds(serverPreviewForDisplay?.route);
  const serverMoveCost = Number(serverPreviewForDisplay?.mp_cost);
  const dispatchCost = serverPreviewForDisplay && Number.isFinite(serverMoveCost) ? serverMoveCost : displayRoutePreview.cost;
  const dispatchAvailableMp = Number(serverPreviewForDisplay?.mp_available ?? mapMovementPoints);
  const serverStopSocket =
    serverPreviewForDisplay?.to_node_id &&
    serverPreviewForDisplay.to_node_id !== displayRoutePreview.requestedSocketId &&
    lordMapSockets.some((socket) => socket.id === serverPreviewForDisplay.to_node_id)
      ? getLordMapSocketById(serverPreviewForDisplay.to_node_id)
      : null;
  const pendingStopSocket =
    backendPendingMove?.to_node_id && lordMapSockets.some((socket) => socket.id === backendPendingMove.to_node_id)
      ? getLordMapSocketById(backendPendingMove.to_node_id)
      : null;
  const routeStopSocketId = pendingStopSocket?.id ?? serverStopSocket?.id ?? displayRoutePreview.contactSocketId;
  const contactSocket = routeStopSocketId ? getLordMapSocketById(routeStopSocketId) : null;
  const activeRoutePathIds = movementDraft?.pathIds ?? (pendingPathIds.length > 1 ? pendingPathIds : isMarchMode ? serverRouteIds : []);
  const displayPathIds = movementDraft?.pathIds ?? (isMarchMode ? displayRoutePreview.pathIds : []);
  const displayRouteSegments = getLordMapRouteSegments(displayPathIds);
  const activeRouteSegments = getLordMapRouteSegments(activeRoutePathIds);
  const hasSeparateActiveRoute =
    activeRoutePathIds.length > 1 &&
    displayPathIds.length > 1 &&
    activeRoutePathIds.join("|") !== displayPathIds.join("|");
  const routePlanSegments = hasSeparateActiveRoute ? displayRouteSegments : [];
  const routeCurrentSegments = activeRoutePathIds.length > 1 ? activeRouteSegments : displayRouteSegments;
  const displayRouteEdgeIds = new Set(
    displayPathIds.slice(1).map((socketId, index) => getLordMapTravelEdge(displayPathIds[index], socketId)?.id).filter(Boolean)
  );
  const activeRouteEdgeIds = new Set(
    activeRoutePathIds.slice(1).map((socketId, index) => getLordMapTravelEdge(activeRoutePathIds[index], socketId)?.id).filter(Boolean)
  );
  const displayPathLabel = displayPathIds.map((socketId) => getLordMapSocketById(socketId).name).join(" - ");
  const displayPathCost = displayPathIds.length > 1 ? getLordMapPathCost(displayPathIds) : displayRoutePreview.cost;
  const hasDisplayRoute = isMarchMode && displayPathIds.length > 1 && Number.isFinite(displayPathCost);
  const pendingMoveTiming = getLordMapMoveTiming(backendPendingMove, pendingRenderNowMs);
  const pendingTravelProgress = pendingMoveTiming.progress;
  const armyMarkerPoint = movementDraft
    ? getLordMapPointAlongPath(movementDraft.pathIds, armyTravelProgress)
    : isBackendPendingMove && pendingPathIds.length > 1
      ? getLordMapPointAlongPath(pendingPathIds, pendingTravelProgress)
    : { x: armySocket.x, y: armySocket.y };
  const movingTargetSocket = movementDraft
    ? getLordMapSocketById(movementDraft.targetSocketId)
    : isBackendPendingMove
      ? getLordMapSocketById(backendPendingMove?.to_node_id ?? backendPendingMove?.requested_to_node_id ?? armySocketId)
      : null;
  const armyMarkerTargetSocketId =
    movementDraft?.targetSocketId ?? backendPendingMove?.requested_to_node_id ?? backendPendingMove?.to_node_id ?? armySocketId;
  const isPlanningFromArmy = routeStartSocketId === armySocketId;
  const canDispatchRoute =
    isMarchMode &&
    !isMoveSubmitting &&
    !isBackendPendingMove &&
    routePreviewState !== "loading" &&
    displayRoutePreview.status !== "idle" &&
    displayRoutePreview.status !== "blocked" &&
    isPlanningFromArmy &&
    (serverPreviewForDisplay ? Boolean(serverPreviewForDisplay.can_move) : displayRoutePreview.canMove);
  const displayRouteKey = displayRoutePreview.pathIds.join("|");

  useEffect(() => {
    if (
      !isMarchMode ||
      mapApiState !== "online" ||
      !isPlanningFromArmy ||
      movementDraft ||
      isBackendPendingMove ||
      displayRoutePreview.status === "idle" ||
      displayRoutePreview.status === "blocked" ||
      displayRoutePreview.pathIds.length < 2
    ) {
      setServerRoutePreview(null);
      setRoutePreviewState("idle");
      return undefined;
    }

    const serial = routePreviewSerialRef.current + 1;
    routePreviewSerialRef.current = serial;
    const controller = new AbortController();
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
        to_node_id: displayRoutePreview.requestedSocketId,
        route_node_ids: displayRoutePreview.pathIds,
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
          requested_to_node_id: displayRoutePreview.requestedSocketId,
          route: [],
          mp_cost: 0,
          mp_available: mapMovementPoints,
          reason: error instanceof Error ? error.message : "Маршрут недоступен"
        });
        setRoutePreviewState("error");
      });

    return () => {
      controller.abort();
    };
  }, [
    apiBaseUrl,
    backendLordId,
    backendRoleToken,
    displayRouteKey,
    displayRoutePreview.requestedSocketId,
    displayRoutePreview.status,
    isBackendPendingMove,
    isPlanningFromArmy,
    isMarchMode,
    mapApiState,
    mapMovementPoints,
    movementDraft
  ]);

  const pendingArrivalLabel = formatLordMapArrivalTime(backendPendingMove?.arrival_at);
  const pendingTargetSocket = pendingStopSocket ?? movingTargetSocket;
  const pendingRequestedSocket =
    backendPendingMove?.requested_to_node_id && backendPendingMove.requested_to_node_id !== backendPendingMove.to_node_id
      ? getLordMapSocketById(backendPendingMove.requested_to_node_id)
      : null;
  const pendingRemainingLabel = formatLordMapRemainingSeconds(pendingMoveTiming.remainingSeconds);
  const activeRouteLabel =
    activeRoutePathIds.length > 1
      ? activeRoutePathIds.map((socketId) => getLordMapSocketById(socketId).name).join(" - ")
      : "";
  const displayRouteText = movementDraft
    ? `Армия идет к ${movingTargetSocket?.name ?? previewTargetSocket.name}.`
    : isBackendPendingMove
      ? `Армия идет к ${pendingTargetSocket?.name ?? previewTargetSocket.name}${pendingRequestedSocket ? `, плановая цель: ${pendingRequestedSocket.name}` : ""}. Осталось: ${pendingRemainingLabel}${pendingArrivalLabel ? `, прибытие ${pendingArrivalLabel}` : ""}.`
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
              ? serverPreviewForDisplay?.reason ?? displayRoutePreview.reason
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
  const activeBattle = true;
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
  const mapActiveArmyStacks = mapApiState === "online" ? backendActiveArmy : lordHomeInitialArmy;
  const mapArmySlots = Array.from({ length: mapArmyCapacity }, (_, index) => mapActiveArmyStacks[index] ?? null);
  const mapArmyUnitCount = mapActiveArmyStacks.reduce((total, stack) => total + stack.count, 0);
  const mapHudStatusText = movementDraft
    ? `Идет к ${movingTargetSocket?.name ?? previewTargetSocket.name}`
    : isBackendPendingMove
      ? `В пути к ${pendingTargetSocket?.name ?? previewTargetSocket.name}: ${pendingRemainingLabel}`
      : `Стоит в ${armySocket.name}`;
  const mapBattleSocket =
    !movementDraft &&
    !isBackendPendingMove &&
    !isMoveSubmitting &&
    isLordMapRouteStopSocket(armySocket, currentLord)
      ? armySocket
      : null;
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
  const territoryRoads = getLordMapNeighbors(displaySocket.id).map((neighbor) => {
    const neighborSocket = getLordMapSocketById(neighbor.id);
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
      runLocalMovement(displayRoutePreview.pathIds, displayRoutePreview.targetSocketId, displayRoutePreview.cost);
      return;
    }

    const routeIds = serverRouteIds.length > 1 ? serverRouteIds : displayRoutePreview.pathIds;
    const moveTargetId = serverPreviewForDisplay.to_node_id ?? routeIds[routeIds.length - 1] ?? displayRoutePreview.targetSocketId;
    const expectedCost = Number.isFinite(serverMoveCost) ? serverMoveCost : getLordMapPathCost(routeIds);
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

    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${backendLordId}/move`, {
        method: "POST",
        headers,
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
      const acceptedTargetSocket = getLordMapSocketById(acceptedTargetId);
      const pendingMove: LordMapBackendPendingMove = result.pending_move ?? {
        status: "pending",
        from_node_id: armySocketId,
        to_node_id: acceptedTargetId,
        requested_to_node_id: requestedTargetId,
        route: result.route ?? routeIds,
        mp_spent: result.mp_spent,
        current_mp: result.current_mp
      };
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
      if (pendingMove.from_node_id && lordMapSockets.some((socket) => socket.id === pendingMove.from_node_id)) {
        setArmySocketId(pendingMove.from_node_id);
        setRouteStartSocketId(pendingMove.from_node_id);
      }
      window.setTimeout(() => {
        void fetchLordMapState({ silent: true });
      }, 280);
    } catch (error) {
      setMapActionStatus(error instanceof Error ? error.message : "Поход не принят");
    } finally {
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
              className={`lord-home-dock-button action-${action.id} ${action.tone}${action.id === "map" ? " is-selected" : ""}${"alert" in action && action.alert && activeBattle ? " is-alert" : ""}`}
              type="button"
              aria-label={action.id === "map" ? "Вернуться на главный экран" : action.label}
              onClick={() => {
                if (action.id === "map") {
                  window.location.assign("/lords/home");
                  return;
                }

                if (action.id === "buildings") {
                  window.location.assign("/lords/home?view=buildings");
                  return;
                }

                if (action.id === "battle") {
                  window.location.assign("/lords/battle");
                  return;
                }

                window.location.assign(`/lords/home?panel=${action.id}`);
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
            <img className="lord-map-playable-image is-base-map" src={lordMapStrictV6RoadlessBase} alt="" draggable={false} />
            <img
              className={`lord-map-playable-image is-road-map${mapLayers.roads ? " is-visible" : ""}`}
              src={lordMapStrictV6BakedRoads}
              alt=""
              draggable={false}
            />
            {(routePlanSegments.length > 0 || routeCurrentSegments.length > 0) && (
              <svg
                className="lord-map-route-layer"
                viewBox={`0 0 ${lordMapRoadViewBox.width} ${lordMapRoadViewBox.height}`}
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
              {lordMapSockets.map((socket) => {
                const directTravelCost = getLordMapDirectCost(routeStartSocketId, socket.id);
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
              {mapLayers.costs && lordMapTravelEdges.map((travelEdge) => {
                const labelPoint = getLordMapPolylineMidpoint(travelEdge.points);
                const isRouteCost = displayRouteEdgeIds.has(travelEdge.id);
                const isActiveRouteCost = activeRouteEdgeIds.has(travelEdge.id);

                return (
                  <span
                    key={travelEdge.id}
                    className={`lord-map-travel-cost${isRouteCost ? " is-route-cost" : ""}${isActiveRouteCost ? " is-active-route-cost" : ""}${travelEdge.cost > mapMovementPoints ? " is-out-of-range" : ""}`}
                    style={getLordMapPointStyle(labelPoint)}
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
            {mapBattleSocket && (
              <button
                className="lord-map-battle-cta"
                type="button"
                style={{ left: `${mapBattleSocket.x}%`, top: `${mapBattleSocket.y}%` }}
                aria-label={`Начать бой: ${mapBattleSocket.name}`}
                onClick={() => {
                  window.location.assign(`/lords/battle?node=${mapBattleSocket.id}`);
                }}
              >
                <Swords size={15} />
                Бой
              </button>
            )}
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
                      {lordMapSockets.map((socket) => (
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
                      {lordMapSockets.map((socket) => (
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
          <LordMpHud className="lord-map-mp-widget" currentMp={mapMovementPoints} mpCap={mapMovementCap} />
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
    panelParam === "map" || panelParam === "battle" || panelParam === "help"
      ? panelParam
      : null;
  const apiBaseUrl = (homeRouteParams.get("api") || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const backendLordId = homeRouteParams.get("lord") || localStorage.getItem("witcher_larp_lord_id") || lordHomeDefaultLordId;
  const backendRoleToken = homeRouteParams.get("token") || localStorage.getItem("witcher_larp_role_token") || lordHomeDefaultRoleToken;
  const [selectedTerritoryId, setSelectedTerritoryId] = useState<LordHomeTerritoryId>("castle");
  const [army, setArmy] = useState<LordHomeStack[]>(lordHomeInitialArmy);
  const [garrisons, setGarrisons] = useState<Record<LordHomeTerritoryId, LordHomeStack[]>>(lordHomeInitialGarrisons);
  const [territoryRuntime, setTerritoryRuntime] = useState<Partial<Record<LordHomeTerritoryId, LordHomeTerritoryRuntime>>>({});
  const [domainStats, setDomainStats] = useState<LordHomeDomainStats>(lordHomeInitialDomainStats);
  const [timerSummary, setTimerSummary] = useState<LordHomeBackendTimerSummary | null>(null);
  const [timerNowMs, setTimerNowMs] = useState(() => Date.now());
  const [recruitStock, setRecruitStock] = useState(lordHomeInitialRecruitStock);
  const [recruitOffersByCard, setRecruitOffersByCard] = useState<Record<string, LordHomeRecruitOffer>>(lordHomeSeedRecruitOffers);
  const [recruitUnitId, setRecruitUnitId] = useState<LordHomeUnitId | null>(null);
  const [recruitQty, setRecruitQty] = useState(1);
  const [lordGold, setLordGold] = useState(18804);
  const [recruitStatus, setRecruitStatus] = useState("");
  const [isRecruitHiring, setIsRecruitHiring] = useState(false);
  const [isRecruitSliderDragging, setIsRecruitSliderDragging] = useState(false);
  const [dragPayload, setDragPayload] = useState<LordHomeDragPayload>(null);
  const dragPayloadRef = useRef<LordHomeDragPayload>(null);
  const suppressNextStackClickUntilRef = useRef(0);
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
  const [builtBuildingIds, setBuiltBuildingIds] = useState<Set<string>>(() => new Set(lordBuildingInitialBuiltIds));
  const [selectedBuildingId, setSelectedBuildingId] = useState(initialSelectedBuildingId);
  const [buildingStatus, setBuildingStatus] = useState("");
  const [buildingPurchaseId, setBuildingPurchaseId] = useState<string | null>(null);
  const [lordOrders, setLordOrders] = useState<LordHomeOrder[]>([]);
  const [lordOrderCap, setLordOrderCap] = useState<LordHomeOrderCap>({});
  const [lordOrderEscrow, setLordOrderEscrow] = useState<LordHomeOrderEscrow>({});
  const [lordOrderTargets, setLordOrderTargets] = useState<LordHomeOrderTarget[]>([]);
  const [lordOrderRecipients, setLordOrderRecipients] = useState<LordHomeOrderRecipient[]>([]);
  const [lordOrderRewards, setLordOrderRewards] = useState<LordHomeOrderRewardOption[]>([]);
  const [lordOrderFilter, setLordOrderFilter] = useState<LordHomeOrderFilterId>("open");
  const [selectedLordOrderId, setSelectedLordOrderId] = useState<string | null>(null);
  const [lordOrderStatus, setLordOrderStatus] = useState("");
  const [isLordOrderSubmitting, setIsLordOrderSubmitting] = useState(false);
  const [raidTokens, setRaidTokens] = useState(2);
  const [lordRaidRules, setLordRaidRules] = useState<LordHomeRaidRule[]>(lordHomeFallbackRaidRules);
  const [lordRaidTargets, setLordRaidTargets] = useState<LordHomeRaidTarget[]>(lordHomeFallbackRaidTargets);
  const [activeRaidEffects, setActiveRaidEffects] = useState<LordHomeRaidEffect[]>([]);
  const [lordRaidHistory, setLordRaidHistory] = useState<LordHomeRaidEffect[]>([]);
  const [selectedRaidRuleId, setSelectedRaidRuleId] = useState(lordHomeFallbackRaidRules[0].rule_id);
  const [selectedRaidTargetId, setSelectedRaidTargetId] = useState(lordHomeFallbackRaidTargets[0].target_territory_id);
  const [lordRaidStatus, setLordRaidStatus] = useState("");
  const [isLordRaidSubmitting, setIsLordRaidSubmitting] = useState(false);
  const [openPanel, setOpenPanel] = useState<LordHomePanel | null>(initialOpenPanel);
  const prefersReducedMotion = useReducedMotion();
  const selectedTerritory = lordHomeTerritories.find((territory) => territory.id === selectedTerritoryId) ?? lordHomeTerritories[0];
  const selectedTerritoryRuntime = territoryRuntime[selectedTerritory.id];
  const selectedHeroHere = selectedTerritoryRuntime?.heroHere ?? selectedTerritory.heroHere;
  const selectedGarrison = garrisons[selectedTerritory.id] ?? [];
  const selectedIncomePerHour = selectedTerritoryRuntime?.incomePerHour ?? selectedTerritory.income;
  const selectedGarrisonCapacity = selectedTerritoryRuntime?.garrisonCapacity ?? 8;
  const selectedGarrisonSlotsUsed = selectedTerritoryRuntime?.garrisonSlotsUsed ?? selectedGarrison.length;
  const selectedGarrisonSlotsFree = Math.max(0, selectedGarrisonCapacity - selectedGarrisonSlotsUsed);
  const displayedTerritoryBubbles = lordHomeTerritories
    .slice(1)
    .filter((territory) => territoryRuntime[territory.id]?.isOwned);
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
      !isTransferSubmitting
  );
  const recruitUnit = recruitUnitId ? lordHomeUnitCatalog[recruitUnitId] : null;
  const recruitStockInfo = recruitUnitId ? recruitStock[selectedTerritory.id][recruitUnitId] : null;
  const recruitOffer = recruitUnit ? recruitOffersByCard[recruitUnit.backendCardId] : null;
  const recruitStockAvailable = Math.max(0, recruitStockInfo?.stock ?? recruitOffer?.stock ?? 0);
  const recruitUnitCost = Math.max(0, recruitOffer?.cost ?? recruitUnit?.cost ?? 0);
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
    : Math.max(0, Math.min(recruitStockAvailable, recruitAffordableQty));
  const recruitSliderPercent = maxRecruitQty > 1
    ? ((recruitQty - 1) / (maxRecruitQty - 1)) * 100
    : maxRecruitQty > 0 ? 100 : 0;
  const recruitTotalCost = recruitQty * recruitUnitCost;
  const recruitCanSubmit = Boolean(
    recruitUnit &&
      recruitOffer &&
      ["available", "held"].includes(recruitOffer.status) &&
      recruitQty >= 1 &&
      recruitQty <= maxRecruitQty &&
      !recruitBlockedByGarrisonCap &&
      !isRecruitHiring
  );
  const activeBattle = true;
  const movementPointCap = Math.max(1, clampLordHomeMetric(domainStats.mpCap, lordHomeInitialDomainStats.mpCap));
  const currentMovementPoints = Math.min(
    movementPointCap,
    clampLordHomeMetric(domainStats.currentMp, lordHomeInitialDomainStats.currentMp)
  );
  const recruitUnitIds = lordHomeUnitOrder.filter((unitId) => {
    const offer = recruitOffersByCard[lordHomeUnitCatalog[unitId].backendCardId];
    return Boolean(offer && isLordHomeRecruitOfferUsable(offer.status));
  });
  const displayedRecruitUnitIds = Array.from({ length: 6 }, (_, index) => recruitUnitIds[index] ?? null);

  const applyBackendState = useCallback((state: LordHomeBackendState) => {
    const nextGold = Number(state.domain?.gold ?? state.domain?.starting_gold);
    if (Number.isFinite(nextGold)) {
      setLordGold(nextGold);
    }
    setTimerSummary(state.timer_summary ?? null);
    if (Array.isArray(state.orders)) {
      setLordOrders(state.orders);
    }
    setLordOrderCap(state.order_cap ?? {});
    setLordOrderEscrow(state.escrow ?? {});
    if (Array.isArray(state.visible_targets)) {
      setLordOrderTargets(state.visible_targets);
    }
    if (Array.isArray(state.eligible_recipients)) {
      setLordOrderRecipients(state.eligible_recipients);
    }
    if (Array.isArray(state.order_reward_options)) {
      setLordOrderRewards(state.order_reward_options);
    }
    const nextRaidTokens = Number(state.raid_tokens ?? state.domain?.raid_tokens);
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
      const nextIncome = Number(state.domain?.income_per_hour);
      const nextRawIncome = Number(state.domain?.raw_income_per_hour);
      const nextTerritoryIncome = Number(state.domain?.territory_income_per_hour);
      const nextCurrentMp = Number(state.movement?.current_mp ?? state.domain?.current_mp);
      const nextMpCap = Number(state.movement?.mp_cap ?? state.domain?.mp_cap);
      const nextArmyCapacity = Number(state.domain?.active_army_capacity);
      const nextArmySlotsUsed = Number(state.domain?.active_army_slots_used);

      return {
        incomePerHour: clampLordHomeMetric(nextIncome, current.incomePerHour),
        rawIncomePerHour: clampLordHomeMetric(nextRawIncome, current.rawIncomePerHour),
        territoryIncomePerHour: clampLordHomeMetric(nextTerritoryIncome, current.territoryIncomePerHour),
        currentMp: clampLordHomeMetric(nextCurrentMp, current.currentMp),
        mpCap: clampLordHomeMetric(nextMpCap, current.mpCap),
        activeArmyCapacity: clampLordHomeMetric(nextArmyCapacity, current.activeArmyCapacity),
        activeArmySlotsUsed: clampLordHomeMetric(nextArmySlotsUsed, current.activeArmySlotsUsed)
      };
    });

    const nextBuiltBuildingIds = getLordHomeBuiltBuildingIdsFromBackendState(state);
    if (nextBuiltBuildingIds) {
      setBuiltBuildingIds(nextBuiltBuildingIds);
    }

    if (Array.isArray(state.active_army)) {
      setArmy(getLordHomeStacksFromBackend(state.active_army));
    }

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
        const localTerritoryId = territory.territory_id
          ? lordHomeTerritoryIdByBackendId[territory.territory_id]
          : undefined;
        if (!localTerritoryId) {
          continue;
        }

        const localTerritory = lordHomeTerritories.find((item) => item.id === localTerritoryId);
        const stacks = getLordHomeStacksFromBackend(territory.garrisons);
        const incomePerHour = Number(territory.income_per_hour);
        const garrisonCapacity = Number(territory.fort?.garrison_capacity);
        const garrisonSlotsUsed = Number(territory.fort?.garrison_slots_used);
        const hasActiveNodeId = typeof activeNodeId === "string" && activeNodeId.length > 0;

        nextGarrisons[localTerritoryId] = stacks;
        nextTerritoryRuntime[localTerritoryId] = {
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

    if (Array.isArray(state.recruit_market)) {
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
  }, []);

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

  useEffect(() => {
    localStorage.setItem("witcher_larp_lord_id", backendLordId);
    localStorage.setItem("witcher_larp_role_token", backendRoleToken);
  }, [backendLordId, backendRoleToken]);

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

    const loadBackendState = async () => {
      try {
        await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/recruit`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Role-Token": backendRoleToken
          },
          body: JSON.stringify({ action: "refresh", source: "lord_home_recruit_modal" }),
          signal: controller.signal
        }).catch(() => undefined);

        const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
          headers: { "X-Role-Token": backendRoleToken },
          signal: controller.signal
        });
        const state = (await response.json().catch(() => ({}))) as LordHomeBackendState;
        if (!response.ok) {
          return;
        }

        applyBackendState(state);
      } catch {
        if (!controller.signal.aborted) {
          setRecruitStatus("Сервер найма недоступен");
        }
      }
    };

    loadBackendState();
    const intervalId = window.setInterval(loadBackendState, lordHomeStatePollMs);
    return () => {
      window.clearInterval(intervalId);
      controller.abort();
    };
  }, [apiBaseUrl, applyBackendState, backendLordId, backendRoleToken]);

  useEffect(() => {
    if (!recruitUnitId) return;
    setRecruitQty((current) => clampRecruitQty(current, maxRecruitQty));
  }, [maxRecruitQty, recruitUnitId]);

  useEffect(() => {
    if (!transferDraft) return;
    setTransferQty((current) => clampRecruitQty(current, maxTransferQty));
  }, [maxTransferQty, transferDraft]);

  const buildSelectedBuilding = async (buildingId: string) => {
    const building = lordBuildingTreeNodes.find((item) => item.id === buildingId);
    if (!building || buildingPurchaseId || getLordBuildingState(building, builtBuildingIds) !== "available") {
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
          source: "lord_home_building_tree"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Строительство не выполнено"));
      }

      const result = payload as LordHomeBuildingPurchaseResponse;
      const purchasedBuildingId =
        result.building_id && lordBuildingKnownIds.has(result.building_id)
          ? result.building_id
          : buildingId;
      setBuiltBuildingIds((current) => {
        const next = new Set(current);
        next.add(purchasedBuildingId);
        return next;
      });

      const goldSpent = Number(result.gold_spent ?? building.goldCost);
      if (Number.isFinite(goldSpent)) {
        setLordGold((current) => Math.max(0, current - goldSpent));
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
      const message =
        error instanceof Error && !["Failed to fetch", "NetworkError"].includes(error.message)
          ? error.message
          : "Сервер строительства недоступен";
      setBuildingStatus(message);
    } finally {
      setBuildingPurchaseId(null);
    }
  };

  const createLordHomeOrder = async (payload: LordHomeOrderCreatePayload) => {
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
      setLordOrderStatus(error instanceof Error ? error.message : "Заказ не опубликован");
    } finally {
      setIsLordOrderSubmitting(false);
    }
  };

  const cancelLordHomeOrder = async (order: LordHomeOrder) => {
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
          reason: "lord_cancelled_from_stage2b_orders",
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
      setLordOrderStatus(error instanceof Error ? error.message : "Заказ не отменен");
    } finally {
      setIsLordOrderSubmitting(false);
    }
  };

  const startLordHomeRaid = async (payload: LordHomeRaidStartPayload) => {
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
      setLordRaidStatus(error instanceof Error ? error.message : "Рейд не начат");
    } finally {
      setIsLordRaidSubmitting(false);
    }
  };

  const openStackTransfer = (lane: "army" | "garrison", index: number) => {
    const stack = lane === "army" ? army[index] : selectedGarrison[index];
    if (!stack) {
      return;
    }
    if (!selectedHeroHere) {
      setTransferStatus("Герой в другой локации");
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
    const stack = lane === "army" ? army[index] : selectedGarrison[index];
    if (!stack) {
      return;
    }
    if (lane === "army" && !selectedHeroHere) {
      setTransferStatus("Герой в другой локации");
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

  const mergeStackDropLocally = (
    from: Exclude<LordHomeDragPayload, null>,
    to: { lane: "army" | "garrison"; index: number },
    sourceStack: LordHomeStack
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
        const stacks = current[selectedTerritory.id] ?? [];
        const targetStack = stacks[to.index];
        if (!targetStack || targetStack.unitId !== sourceStack.unitId) {
          return current;
        }
        const next = stacks.map((stack) => ({ ...stack }));
        next[to.index] = {
          ...targetStack,
          count: targetStack.count + sourceStack.count
        };
        return { ...current, [selectedTerritory.id]: next };
      });
      return;
    }

    setGarrisons((current) => {
      const stacks = current[selectedTerritory.id] ?? [];
      const next = stacks.map((stack) => ({ ...stack }));
      next.splice(from.index, 1);
      return { ...current, [selectedTerritory.id]: next };
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
          territory_id: selectedTerritory.backendTerritoryId,
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

      const stateResponse = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
        headers: { "X-Role-Token": backendRoleToken }
      });
      const state = (await stateResponse.json().catch(() => ({}))) as LordHomeBackendState;
      if (!stateResponse.ok) {
        setTransferStatus(`${unit.name}: приказ принят, обновите экран`);
        return;
      }

      applyBackendState(state);
      setTransferStatus(`${unit.name}: пачки объединены`);
    } catch (error) {
      setTransferStatus(error instanceof Error ? error.message : "Объединение не выполнено");
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
    if (!transferDraft || !transferStack || !transferUnit || !transferCanSubmit) {
      return;
    }
    const targetTerritoryId = selectedTerritory.backendTerritoryId;
    const operation = transferDraft.mode === "split"
      ? transferDraft.lane === "army"
        ? "split_active"
        : "split_garrison"
      : transferDraft.lane === "army"
        ? "active_to_fort"
        : "fort_to_active";
    const count = clampRecruitQty(transferQty, transferStack.count);
    const clampedCount = transferDraft.mode === "split"
      ? clampRecruitQty(transferQty, Math.max(0, transferStack.count - 1))
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
          card_id: transferUnit.backendCardId,
          stack_id: transferStack.stackId,
          count: clampedCount,
          source: "lord_home_stack_transfer"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Перенос не выполнен"));
      }

      const stateResponse = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
        headers: { "X-Role-Token": backendRoleToken }
      });
      const state = (await stateResponse.json().catch(() => ({}))) as LordHomeBackendState;
      if (!stateResponse.ok) {
        setTransferStatus(`${transferUnit.name}: приказ принят, обновите экран`);
        return;
      }

      applyBackendState(state);
      setTransferStatus(transferDraft.mode === "split"
        ? `${transferUnit.name}: пачка разделена`
        : `${transferUnit.name}: перенесено ${clampedCount}`);
      setTransferDraft(null);
    } catch (error) {
      setTransferStatus(error instanceof Error ? error.message : "Перенос не выполнен");
    } finally {
      setIsTransferSubmitting(false);
    }
  };

  const hireRecruit = async () => {
    if (!recruitUnitId || !recruitUnit || !recruitOffer || !recruitCanSubmit) {
      return;
    }
    const targetTerritoryId = selectedTerritory.backendTerritoryId;
    if (!targetTerritoryId) {
      setRecruitStatus("Территория найма не выбрана");
      return;
    }

    setIsRecruitHiring(true);
    setRecruitStatus("Отправляю приказ найма");
    try {
      const response = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/recruit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Role-Token": backendRoleToken
        },
        body: JSON.stringify({
          action: "purchase",
          offer_id: recruitOffer.offerId,
          quantity: recruitQty,
          count: recruitQty,
          territory_id: targetTerritoryId,
          source: "lord_home_recruit_modal"
        })
      });
      const payload = (await response.json().catch(() => ({}))) as unknown;
      if (!response.ok) {
        throw new Error(getLordHomeApiErrorMessage(payload, "Найм не выполнен"));
      }

      const result = payload as LordHomeRecruitActionResponse;
      if (result.status !== "hired" || result.territory_id !== targetTerritoryId) {
        throw new Error("Сервер не подтвердил найм в гарнизон");
      }
      const hiredCount = Number(result.count ?? recruitQty);
      const acceptedText = `${recruitUnit.name}: нанято ${Number.isFinite(hiredCount) ? hiredCount : recruitQty}`;

      try {
        await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/recruit`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Role-Token": backendRoleToken
          },
          body: JSON.stringify({ action: "refresh", source: "lord_home_recruit_modal" })
        }).catch(() => undefined);

        const stateResponse = await fetch(`${apiBaseUrl}/api/lords/${encodeURIComponent(backendLordId)}/state`, {
          headers: { "X-Role-Token": backendRoleToken }
        });
        const state = (await stateResponse.json().catch(() => ({}))) as LordHomeBackendState;
        if (!stateResponse.ok) {
          setRecruitStatus(`${acceptedText}, обновите экран`);
          return;
        }

        applyBackendState(state);
      } catch {
        setRecruitStatus(`${acceptedText}, обновите экран`);
        return;
      }

      setRecruitStatus(acceptedText);
      setRecruitUnitId(null);
    } catch (error) {
      setRecruitStatus(error instanceof Error ? error.message : "Найм не выполнен");
    } finally {
      setIsRecruitHiring(false);
    }
  };

  const openRecruitModal = (unitId: LordHomeUnitId) => {
    setTransferDraft(null);
    setRecruitUnitId(unitId);
    const unit = lordHomeUnitCatalog[unitId];
    const offer = recruitOffersByCard[unit.backendCardId];
    const stock = recruitStock[selectedTerritory.id][unitId].stock || offer?.stock || 0;
    const unitCost = Math.max(0, offer?.cost ?? unit.cost);
    const affordable = unitCost > 0 ? Math.floor(lordGold / unitCost) : stock;
    setRecruitQty(clampRecruitQty(1, Math.min(stock, affordable)));
    setRecruitStatus("");
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
              builtBuildingIds={builtBuildingIds}
              selectedBuildingId={selectedBuildingId}
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
              builtBuildingIds={builtBuildingIds}
              selectedBuildingId={selectedBuildingId}
              buildingStatus={buildingStatus}
              buildingPurchaseId={buildingPurchaseId}
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
              style={{ backgroundImage: `url(${selectedTerritory.background})` }}
              key={selectedTerritory.id}
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.025 }}
              animate={prefersReducedMotion ? undefined : { opacity: 1, scale: [1.015, 1.035, 1.015] }}
              transition={prefersReducedMotion ? undefined : { opacity: { duration: 0.35 }, scale: { duration: 34, repeat: Infinity, ease: "easeInOut" } }}
            />
            <div className="lord-home-game-grade" />
          </>
        )}
        <img className="lord-home-hud-overlay" src={lordHomeHudOverlay} alt="" draggable={false} />

        {homeView === "orders" ? (
          <LordHomeOrdersBoard
            orders={lordOrders}
            orderCap={lordOrderCap}
            escrow={lordOrderEscrow}
            targets={lordOrderTargets}
            recipients={lordOrderRecipients}
            rewards={lordOrderRewards}
            filterId={lordOrderFilter}
            selectedOrderId={selectedLordOrderId}
            lordGold={lordGold}
            actionStatus={lordOrderStatus}
            isSubmitting={isLordOrderSubmitting}
            onFilterChange={setLordOrderFilter}
            onSelectOrder={setSelectedLordOrderId}
            onCreateOrder={(payload) => void createLordHomeOrder(payload)}
            onCancelOrder={(order) => void cancelLordHomeOrder(order)}
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
            lordGold={lordGold}
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
            <div className="lord-home-resource gold"><Coins size={14} /><b>{lordGold}</b><span>(+{domainStats.incomePerHour}/час)</span></div>
            <div className="lord-home-resource wood"><Archive size={14} /><b>17</b></div>
            <div className="lord-home-resource violet"><Gem size={14} /><b>63</b></div>
            <div className="lord-home-resource blue"><Sparkles size={14} /><b>42</b></div>
            <div className="lord-home-resource red"><Flame size={14} /><b>{raidTokens}</b><span>рейды</span></div>
            <div className="lord-home-resource iron"><Shield size={14} /><b>37</b></div>
            <div className="lord-home-resource green"><Users size={14} /><b>181</b></div>
          </div>
          <button className="lord-home-top-icon help" type="button" aria-label="Обучение" onClick={() => setOpenPanel("help")}>
            <LordHomeActionIcon src={lordHomeActionHelpIcon} />
          </button>
          <button className="lord-home-top-icon logout" type="button" aria-label="Выход" onClick={() => window.location.assign("/lords/login")}>
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
                  window.location.assign("/lords/map");
                  return;
                }

                if (action.id === "battle") {
                  window.location.assign("/lords/battle");
                  return;
                }
              }}
            >
              <LordHomeActionIcon src={action.icon} />
              <span className="lord-home-dock-label">{action.label}</span>
            </button>
          ))}
        </nav>

        <button className="lord-home-minimap-frame" type="button" aria-label="Открыть карту земель" onClick={() => window.location.assign("/lords/map")}>
          <img src={lordHomeMinimap} alt="" draggable={false} />
          <span />
        </button>

            {homeView !== "orders" ? (
            <section className="lord-home-bottom-panel" aria-label="Армия, гарнизон и найм">
              <div className="lord-home-location-title">{selectedTerritory.name}</div>
              <div className="lord-home-local-income">
                +{selectedIncomePerHour}/час · Г {selectedGarrisonSlotsUsed}/{selectedGarrisonCapacity} · А {domainStats.activeArmySlotsUsed}/{domainStats.activeArmyCapacity} · Рейды {raidTokens} · Эффекты {activeRaidEffects.filter((effect) => effect.status === "active").length} · {getLordHomeRaidExpiryLabel(activeRaidEffects)}
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

              {!selectedHeroHere ? <div className="lord-home-army-lock">Герой в другой локации</div> : null}

              <div className="lord-home-recruit-grid">
                {displayedRecruitUnitIds.map((unitId, index) => {
                  if (!unitId) {
                    return <div key={`empty-${index}`} className="lord-home-recruit-card is-empty" />;
                  }

                  const unit = lordHomeUnitCatalog[unitId];
                  const stockInfo = recruitStock[selectedTerritory.id][unitId];

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

        <LordMpHud className="lord-home-act-widget" currentMp={currentMovementPoints} mpCap={movementPointCap} />

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
                  <p>В гарнизон: {selectedTerritory.name}</p>
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
                  <small>Накоплено: {recruitStockAvailable}</small>
                  <small>Можно: {maxRecruitQty}</small>
                </div>
                <div className="lord-home-recruit-status">
                  {recruitStatus || (!recruitOffer ? "Предложение не открыто" : recruitBlockedByGarrisonCap ? "Нет свободного слота в гарнизоне" : recruitAffordableQty < 1 ? "Недостаточно золота" : "Гарнизон выбран")}
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
                  <p>{selectedTerritory.name}</p>
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
                  <small>{selectedTerritory.name}</small>
                </div>
                <div className="lord-home-recruit-status">
                  {transferStatus || (transferDraft.mode === "split" ? "Выберите размер новой пачки" : selectedHeroHere ? "Выберите часть пачки" : "Герой в другой локации")}
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
              selectedTerritory={selectedTerritory}
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
  builtBuildingIds,
  selectedBuildingId
}: {
  builtBuildingIds: Set<string>;
  selectedBuildingId: string;
}) {
  const activeBuildingId = selectedBuildingId;

  return (
    <div className="lord-building-icon-underlay-layer" aria-hidden="true">
      {lordBuildingTreeNodes.map((building) => {
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
  builtBuildingIds,
  selectedBuildingId,
  buildingStatus,
  buildingPurchaseId,
  onSelectBuilding,
  onBuild
}: {
  builtBuildingIds: Set<string>;
  selectedBuildingId: string;
  buildingStatus: string;
  buildingPurchaseId: string | null;
  onSelectBuilding: (buildingId: string) => void;
  onBuild: (buildingId: string) => void;
}) {
  const nodeById = new globalThis.Map(lordBuildingTreeNodes.map((building) => [building.id, building]));

  const buildingStateFor = (building: LordBuildingNode): LordBuildingState => getLordBuildingState(building, builtBuildingIds);

  const activeBuilding =
    lordBuildingTreeNodes.find((building) => building.id === selectedBuildingId) ??
    lordBuildingTreeNodes[0];
  const activeState = buildingStateFor(activeBuilding);
  const activeMeta = lordBuildingBranchMeta[activeBuilding.branch];
  const activeIconSrc = lordBuildingIconById[activeBuilding.id];
  const ActiveIcon = activeMeta.icon;
  const isBuildingPurchasePending = buildingPurchaseId === activeBuilding.id;
  const hasBuildingPurchasePending = buildingPurchaseId !== null;
  const missingPrerequisites = activeBuilding.prerequisiteIds
    .filter((id) => !builtBuildingIds.has(id))
    .map((id) => nodeById.get(id)?.name)
    .filter(Boolean);
  const recruitLabels = activeBuilding.recruitUnlockIds
    .map((id) => lordBuildingRecruitLabels[id] ?? id)
    .join(", ");
  const buildingBenefitBullets = [
    ...(lordBuildingBaseBenefitLabels[activeBuilding.id] ?? []),
    ...(activeBuilding.capacityDelta > 0 ? [`Слоты походных пачек +${activeBuilding.capacityDelta}`] : []),
    ...(recruitLabels ? [`Найм: ${recruitLabels}`] : []),
    ...(activeBuilding.raidUnlock ? ["Рейды: открыто"] : [])
  ];
  const buildButtonText =
    isBuildingPurchasePending
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
        {lordBuildingTreeNodes.flatMap((building) =>
          building.prerequisiteIds.map((prerequisiteId) => {
            const prerequisite = nodeById.get(prerequisiteId);

            if (!prerequisite) {
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
        {lordBuildingTreeNodes.map((building) => {
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
        {buildingStatus ? (
          <div className={`lord-building-api-status${isBuildingPurchasePending ? " is-pending" : ""}`}>
            {buildingStatus}
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
          disabled={activeState !== "available" || hasBuildingPurchasePending}
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
  targets,
  recipients,
  rewards,
  filterId,
  selectedOrderId,
  lordGold,
  actionStatus,
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
  targets: LordHomeOrderTarget[];
  recipients: LordHomeOrderRecipient[];
  rewards: LordHomeOrderRewardOption[];
  filterId: LordHomeOrderFilterId;
  selectedOrderId: string | null;
  lordGold: number;
  actionStatus: string;
  isSubmitting: boolean;
  onFilterChange: (filterId: LordHomeOrderFilterId) => void;
  onSelectOrder: (orderId: string | null) => void;
  onCreateOrder: (payload: LordHomeOrderCreatePayload) => void;
  onCancelOrder: (order: LordHomeOrder) => void;
  onStatus: (message: string) => void;
}) {
  const cap = getLordHomeOrderCap(orderCap);
  const filteredOrders = getLordHomeOrdersForFilter(orders, filterId);
  const selectedOrder = filteredOrders.find((order) => order.order_id === selectedOrderId) ?? filteredOrders[0] ?? null;
  const lockedAssets = Number(escrow.locked_asset_count ?? escrow.locked_assets?.length ?? 0);
  const lockedGold = Number(escrow.locked_gold ?? 0);
  const availableGold = getLordHomeOrderAvailableGold(escrow, lordGold);
  const conflictCount = orders.filter((order) => order.conflict_badge).length;
  const activeOrdersCount = cap.publicActive + cap.addressedActive;
  const activeOrdersLimit = cap.publicLimit + cap.addressedLimit;
  const defaultVisibility: LordHomeOrderVisibility =
    cap.publicActive < cap.publicLimit ? "public" : "addressed";
  const [composerOpen, setComposerOpen] = useState(false);
  const [visibility, setVisibility] = useState<LordHomeOrderVisibility>(defaultVisibility);
  const [targetId, setTargetId] = useState(targets[0]?.target_id ?? "");
  const [recipientId, setRecipientId] = useState("");
  const [rewardId, setRewardId] = useState(rewards[0]?.reward_id ?? "");
  const [visibleHook, setVisibleHook] = useState("");
  const selectedTarget = targets.find((target) => target.target_id === targetId) ?? null;
  const selectedRecipient = recipients.find((recipient) => recipient.player_id === recipientId) ?? null;
  const selectedReward = rewards.find((reward) => reward.reward_id === rewardId) ?? null;
  const prefersReducedMotion = useReducedMotion();
  const publicFull = cap.publicActive >= cap.publicLimit;
  const addressedFull = cap.addressedActive >= cap.addressedLimit;
  const selectedCapFull = visibility === "addressed" ? addressedFull : publicFull;
  const rewardGold = getLordHomeOrderRewardGold(selectedReward);
  const insufficientGold = rewardGold > availableGold;
  const needsRecipient = visibility === "addressed" && !recipientId;
  const createBlockReason =
    !targets.length
      ? "Нет доступных целей для заказа"
      : !rewards.length
        ? "В казне нет доступной награды"
        : publicFull && addressedFull
          ? `Лимит заказов занят: публичные ${cap.publicActive}/${cap.publicLimit}, адресный ${cap.addressedActive}/${cap.addressedLimit}`
          : "";
  const createHint =
    createBlockReason && publicFull && addressedFull
      ? "Лимит заказов занят"
      : createBlockReason || `${availableGold}g доступно для награды`;
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
            : insufficientGold
              ? "В казне не хватает награды"
              : !selectedTarget || !selectedReward
                ? "Заполните цель и награду"
                : "";
  const previewHook = visibleHook.trim() || `Найти и подтвердить: ${selectedTarget?.label ?? "цель"}`;
  const previewRecipient =
    visibility === "addressed"
      ? selectedRecipient
        ? `${selectedRecipient.display_name ?? "Исполнитель"}, ${selectedRecipient.role_label ?? ""}`.trim()
        : "адресат"
      : "любой исполнитель";
  const openComposer = (mode: "create" | "repeat" | "assign" = "create", order?: LordHomeOrder) => {
    setComposerOpen(true);
    const nextVisibility =
      mode === "assign"
        ? "addressed"
        : order?.visibility === "addressed"
          ? "addressed"
          : defaultVisibility;
    setVisibility(nextVisibility);
    setTargetId(order?.object_id || targets[0]?.target_id || "");
    setRecipientId(mode === "assign" ? order?.target_player_id || recipients[0]?.player_id || "" : order?.target_player_id || "");
    setRewardId(order?.escrow_reward_id || rewards[0]?.reward_id || "");
    setVisibleHook(order?.visible_hook || "");
    onStatus("");
  };

  useEffect(() => {
    if (!targetId && targets[0]?.target_id) {
      setTargetId(targets[0].target_id);
    }
  }, [targetId, targets]);

  useEffect(() => {
    if (!rewardId && rewards[0]?.reward_id) {
      setRewardId(rewards[0].reward_id);
    }
  }, [rewardId, rewards]);

  useEffect(() => {
    if (visibility === "addressed" && !recipientId && recipients[0]?.player_id) {
      setRecipientId(recipients[0].player_id);
    }
  }, [recipientId, recipients, visibility]);

  const submitOrder = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (publishBlockReason || !selectedTarget || !selectedReward) {
      onStatus(publishBlockReason || "Заполните заказ");
      return;
    }

    setComposerOpen(false);
    onCreateOrder({
      visibility,
      object_id: selectedTarget.target_id,
      target_player_id: visibility === "addressed" ? recipientId : undefined,
      visible_hook: visibleHook.trim() || previewHook,
      reward: { reward_id: selectedReward.reward_id },
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

      <aside className="lord-orders-filters" aria-label="Фильтры заказов">
        {lordHomeOrderFilters.map((filter) => (
          <button
            key={filter.id}
            type="button"
            aria-pressed={filter.id === filterId}
            onClick={() => {
              setComposerOpen(false);
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
              onSelectOrder(order.order_id);
            }}
          >
            <span className="lord-order-wax" aria-hidden="true" />
            <div className="lord-order-card-top">
              <span>{order.visibility_label || (order.visibility === "addressed" ? "Адресный" : "Публичный")}</span>
              <b>{order.status_label || order.status || "Открыт"}</b>
            </div>
            <h2>{getLordHomeOrderDisplayTitle(order)}</h2>
            <div className="lord-order-card-grid">
              <span><Crosshair size={13} /> {order.object_label || "объект"}</span>
              <span><Map size={13} /> {order.location_label || "по следу"}</span>
              <span className="is-wide"><Coins size={13} /> {order.reward_label || "награда"}</span>
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
        {composerOpen ? (
          <form className="lord-orders-composer" onSubmit={submitOrder}>
            <div className="lord-orders-detail-head">
              <span>Новая запись</span>
              <h2>Поручение исполнителю</h2>
            </div>
            <label>
              <span>Тип</span>
              <select value={visibility} onChange={(event) => setVisibility(event.target.value as LordHomeOrderVisibility)}>
                <option value="public">Публичный</option>
                <option value="addressed">Адресный</option>
              </select>
            </label>
            <label>
              <span>Цель</span>
              <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                {targets.map((target) => (
                  <option key={target.target_id} value={target.target_id}>
                    {target.target_type_label ? `${target.target_type_label}: ` : ""}{target.label}
                    {target.location_label && target.location_label !== target.label ? `, ${target.location_label}` : ""}
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
            <label>
              <span>Описание для исполнителя</span>
              <textarea
                value={visibleHook}
                onChange={(event) => setVisibleHook(event.target.value)}
                placeholder={`Найти и подтвердить: ${selectedTarget?.label ?? "цель"}`}
              />
            </label>
            <label>
              <span>Награда</span>
              <select value={rewardId} onChange={(event) => setRewardId(event.target.value)}>
                {rewards.map((reward) => (
                  <option key={reward.reward_id} value={reward.reward_id}>{reward.label}</option>
                ))}
              </select>
            </label>
            <div className="lord-orders-preview">
              <span>Как увидит исполнитель</span>
              <strong>{previewHook}</strong>
              <small>{previewRecipient} · {selectedTarget?.location_label || "локация по следу"}</small>
              <small>{selectedReward?.label || "награда"}; казна удержит {rewardGold}g из {availableGold}g</small>
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
              <h2>{selectedOrder.status_label || selectedOrder.status || "Статус заказа"}</h2>
            </div>
            <p className="lord-orders-detail-note">
              {selectedOrder.executor_label
                ? `Исполнитель: ${selectedOrder.executor_label}`
                : selectedOrder.target_player_label
                  ? `Адресат: ${selectedOrder.target_player_label}`
                  : "Исполнитель пока не назначен"}
            </p>
            <dl>
              <div><dt>Тип</dt><dd>{selectedOrder.visibility_label || (selectedOrder.visibility === "addressed" ? "Адресный" : "Публичный")}</dd></div>
              <div><dt>Залог</dt><dd>{getLordHomeOrderEscrowLabel(selectedOrder)}</dd></div>
              <div><dt>Срок</dt><dd>{getLordHomeOrderWindowLabel(selectedOrder)}</dd></div>
            </dl>
            {selectedOrder.conflict_badge ? (
              <p className="lord-orders-review-note">
                <AlertTriangle size={15} />
                {selectedOrder.conflict_badge.label}
              </p>
            ) : null}
            <div className="lord-orders-actions lord-orders-action-stack">
              <button type="button" disabled={!canCancelLordHomeOrder(selectedOrder) || isSubmitting} onClick={() => onCancelOrder(selectedOrder)}>
                <XCircle size={15} />
                Отменить
              </button>
              <button type="button" disabled={isSubmitting} onClick={() => openComposer("repeat", selectedOrder)}>
                <ScrollText size={15} />
                Повторить
              </button>
              <button
                type="button"
                disabled={!selectedOrder.conflict_badge}
                onClick={() => onStatus(selectedOrder.conflict_badge?.label || "По этому заказу нет открытого конфликта")}
              >
                <AlertTriangle size={15} />
                Посмотреть конфликт
              </button>
              <button type="button" disabled={isSubmitting || addressedFull} onClick={() => openComposer("assign", selectedOrder)}>
                <Users size={15} />
                Назначить исполнителя
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
  lordGold,
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
  lordGold: number;
  actionStatus: string;
  isSubmitting: boolean;
  selectedRuleId: string;
  selectedTargetId: string;
  onSelectRule: (ruleId: string) => void;
  onSelectTarget: (targetId: string) => void;
  onStart: (payload: LordHomeRaidStartPayload) => void;
}) {
  const prefersReducedMotion = useReducedMotion();
  const normalizedRules = rules.map(normalizeLordHomeRaidRule);
  const selectedRule = normalizedRules.find((rule) => rule.rule_id === selectedRuleId) ?? normalizedRules[0] ?? null;
  const normalizedTargets = targets.map(normalizeLordHomeRaidTarget);
  const selectedTarget =
    normalizedTargets.find((target) => target.target_territory_id === selectedTargetId) ??
    normalizedTargets.find((target) => target.can_target) ??
    normalizedTargets[0] ??
    null;
  const blockReason = getLordHomeRaidBlockReason({
    rule: selectedRule,
    target: selectedTarget,
    raidTokens,
    lordGold,
    activeEffects,
    isSubmitting
  });
  const activeCount = activeEffects.filter((effect) => effect.status === "active").length;
  const nearestExpiry = getLordHomeRaidExpiryLabel(activeEffects);
  const categoryEntries = Object.entries(lordHomeRaidCategoryMeta);
  const targetGroups = [
    {
      id: "foreign",
      label: "Чужие территории",
      items: normalizedTargets.filter((target) => target.can_target && !target.is_residence)
    },
    {
      id: "residence",
      label: "Резиденции raid-only",
      items: normalizedTargets.filter((target) => target.can_target && target.is_residence)
    },
    {
      id: "blocked",
      label: "Недоступны",
      items: normalizedTargets.filter((target) => !target.can_target)
    }
  ].filter((group) => group.items.length > 0);

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
        <div className="lord-raids-summary" aria-label="Сводка рейдов">
          <b><Flame size={14} /> Жетоны {raidTokens}</b>
          <span><Coins size={13} /> Казна {lordGold}</span>
          <span><Clock3 size={13} /> Эффекты {activeCount}</span>
          <span><Hourglass size={13} /> Истекает {nearestExpiry}</span>
        </div>
        <div className="lord-raids-seal">
          <span>Выбранный план</span>
          <b>{selectedRule?.name ?? "не выбран"}</b>
        </div>
      </header>

      <aside className="lord-raids-legend" aria-label="Типы рейдов">
        {categoryEntries.map(([category, meta]) => {
          const Icon = meta.icon;
          const count = normalizedRules.filter((rule) => rule.category === category).length;
          return (
            <button
              key={category}
              type="button"
              onClick={() => {
                const firstRule = normalizedRules.find((rule) => rule.category === category);
                if (firstRule) onSelectRule(firstRule.rule_id);
              }}
            >
              <Icon size={15} />
              <span>{meta.label}</span>
              <b>{count}</b>
            </button>
          );
        })}
        <div className="lord-raids-active-strip">
          <span>Активные метки</span>
          {activeEffects.slice(0, 3).map((effect) => (
            <b key={effect.raid_effect_id ?? `${effect.rule_id}-${effect.target_territory_id}`}>
              {effect.result_label || effect.rule_id || "эффект"} · {effect.expires_at ? getLordHomeRaidExpiryLabel([effect]) : "идет"}
            </b>
          ))}
          {activeEffects.length === 0 ? <b>Нет активных эффектов</b> : null}
        </div>
      </aside>

      <section className="lord-raids-plan" aria-label="Сетка доступных рейдов">
        <svg className="lord-raids-link-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path className="lord-raids-link" d="M 21 28 C 29 39 24 45 29 52" />
          <path className="lord-raids-link" d="M 44 25 C 50 35 52 42 57 50" />
          <path className="lord-raids-link" d="M 29 52 C 36 63 38 68 43 73" />
          <path className="lord-raids-link" d="M 57 50 C 66 45 70 39 73 32" />
        </svg>
        {normalizedRules.map((rule, index) => {
          const meta = getLordHomeRaidCategoryMeta(rule.category);
          const Icon = meta.icon;
          const position = getLordHomeRaidNodePosition(rule, index);
          const isActive = selectedRule?.rule_id === rule.rule_id;
          return (
            <button
              key={rule.rule_id}
              className={`lord-raid-node ${meta.tone}${isActive ? " is-active" : ""}${rule.locked_reason ? " is-locked" : ""}`}
              type="button"
              style={{ left: `${position.x}%`, top: `${position.y}%` }}
              aria-pressed={isActive}
              onClick={() => onSelectRule(rule.rule_id)}
            >
              <span className="lord-raid-node-icon"><Icon size={18} /></span>
              <span className="lord-raid-node-tier">T{rule.tier}</span>
              <b>{rule.name}</b>
              <small><Flame size={11} /> {rule.token_cost} · <Coins size={11} /> {rule.gold_cost} · {rule.duration_minutes}м</small>
              {rule.locked_reason ? <i>{rule.locked_reason}</i> : null}
            </button>
          );
        })}
      </section>

      <aside className="lord-raids-detail" aria-label="Детали выбранного рейда">
        {selectedRule ? (
          <motion.article
            key={selectedRule.rule_id}
            className={`lord-raid-detail-card ${getLordHomeRaidCategoryMeta(selectedRule.category).tone}`}
            initial={prefersReducedMotion ? false : { opacity: 0, x: 18 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, x: 0 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.18, ease: "easeOut" }}
          >
            <div className="lord-raids-detail-head">
              <span>{selectedRule.category_label}</span>
              <h2>{selectedRule.name}</h2>
            </div>
            <p>{selectedRule.description}</p>
            <dl>
              <div><dt>Цель</dt><dd>{selectedTarget?.name ?? "не выбрана"}</dd></div>
              <div><dt>Стоимость</dt><dd>{selectedRule.token_cost} жетон · {selectedRule.gold_cost} золота</dd></div>
              <div><dt>Эффект</dt><dd>{selectedRule.effect_type}</dd></div>
              <div><dt>Длительность</dt><dd>{selectedRule.duration_minutes} минут</dd></div>
              <div><dt>Видимость</dt><dd>{selectedRule.visibility}</dd></div>
              <div><dt>Защита</dt><dd>{selectedTarget?.raid_resistance_label || "детали скрыты"}</dd></div>
              <div><dt>Ответ</dt><dd>{selectedRule.counterplay}</dd></div>
            </dl>

            <div className="lord-raids-targets" aria-label="Цели рейда">
              {targetGroups.map((group) => (
                <section key={group.id}>
                  <span>{group.label}</span>
                  {group.items.map((target) => {
                    const isSelected = target.target_territory_id === selectedTarget?.target_territory_id;
                    const compatible = isLordHomeRaidTargetCompatible(selectedRule, target);
                    return (
                      <button
                        key={target.target_territory_id}
                        className={`${isSelected ? "is-selected" : ""}${compatible ? "" : " is-incompatible"}${target.active_effects?.length ? " has-effect" : ""}`}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => onSelectTarget(target.target_territory_id)}
                      >
                        <b>{target.name}</b>
                        <small>{target.owner_label} · T{target.tier} · {target.bonus_label}</small>
                        <em>{target.active_effects?.length ? `${target.active_effects.length} эффект` : target.visibility_level === "hidden_details" ? "детали скрыты" : target.disabled_reason || "цель открыта"}</em>
                      </button>
                    );
                  })}
                </section>
              ))}
            </div>

            <p className="lord-raids-status" role="status">
              {actionStatus || blockReason || "План готов к печати"}
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
                  expected_gold_cost: selectedRule.gold_cost,
                  source: "stage2b_lord_home_raids"
                });
              }}
            >
              <Flame size={15} />
              {isSubmitting ? "Начинаю" : "Начать рейд"}
            </button>
          </motion.article>
        ) : null}
        <div className="lord-raids-history">
          <span>Последние исходы</span>
          {raidHistory.slice(0, 3).map((effect) => (
            <b key={effect.raid_effect_id ?? `${effect.rule_id}-${effect.started_at}`}>
              {effect.result_label || effect.rule_id || "рейд"} · {effect.status || "записан"}
            </b>
          ))}
          {raidHistory.length === 0 ? <b>История пуста</b> : null}
        </div>
      </aside>
    </motion.section>
  );
}

function LordHomeActionOverlay({
  panel,
  selectedTerritory,
  onClose
}: {
  panel: "map" | "orders" | "raids" | "battle" | "help";
  selectedTerritory: (typeof lordHomeTerritories)[number];
  onClose: () => void;
}) {
  const panelCopy = {
    map: {
      title: "Карта земель",
      text: "Активная армия двигается по маршрутам и тратит очки передвижения.",
      icon: Map
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
    battle: {
      title: "На владение напали",
      text: "Открыть боевую доску 5x6 и выбрать защитный отряд.",
      icon: Swords
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
        <span>{selectedTerritory.name}</span>
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

function LordMapSurface({ isExpanded = false }: { isExpanded?: boolean }) {
  return (
    <>
      <span className={`lord-map-zoom${isExpanded ? " lord-map-zoom-expanded" : ""}`}>
        <img className="lord-command-map-image" src={lordMap} alt="" />
        <span className="lord-map-pin home" aria-hidden="true">
          <Castle size={18} />
        </span>
        <span className="lord-map-pin route" aria-hidden="true">
          <Route size={18} />
        </span>
        <span className="lord-map-pin dispute" aria-hidden="true">
          <Swords size={18} />
        </span>
        <span className="lord-map-pin income" aria-hidden="true">
          <Coins size={18} />
        </span>
      </span>
      <span className="lord-command-map-shadow" />
    </>
  );
}

function LordMiniMap({ isExpanded = false }: { isExpanded?: boolean }) {
  return (
    <div className={`lord-minimap${isExpanded ? " lord-minimap-expanded" : ""}`} aria-label="Мини-карта">
      <img src={lordMap} alt="" />
      <span className="lord-minimap-focus" />
    </div>
  );
}

function LordCastleScreen() {
  const [selectedBranch, setSelectedBranch] = useState<(typeof castleBranchTabs)[number]["id"]>("all");
  const [selectedBuildingId, setSelectedBuildingId] = useState<(typeof castleBuildings)[number]["id"]>("residence");
  const prefersReducedMotion = useReducedMotion();
  const castleMpState = useLordMpRuntimeState();
  const visibleBuildings =
    selectedBranch === "all"
      ? castleBuildings
      : castleBuildings.filter((building) => building.branch === selectedBranch || building.branch === "all");
  const selectedBuilding =
    castleBuildings.find((building) => building.id === selectedBuildingId) ?? castleBuildings[0];
  const SelectedIcon = selectedBuilding.icon;

  const selectBranch = (branchId: (typeof castleBranchTabs)[number]["id"]) => {
    setSelectedBranch(branchId);
    const nextBuilding = branchId === "all"
      ? castleBuildings[0]
      : castleBuildings.find((building) => building.branch === branchId) ?? castleBuildings[0];
    setSelectedBuildingId(nextBuilding.id);
  };

  return (
    <main className="lord-castle-screen">
      <motion.img
        className="lord-castle-bg"
        src={castleCity}
        alt=""
        animate={prefersReducedMotion ? undefined : { scale: [1.02, 1.035, 1.02] }}
        transition={{ duration: 34, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="lord-castle-cool-overlay" />
      <div className="lord-castle-vignette" />

      <header className="lord-castle-topbar">
        <button className="lord-castle-round-button" type="button" onClick={() => window.location.assign("/lords/home")} aria-label="Вернуться к карте">
          <Map size={26} />
        </button>
        <div className="lord-castle-title">
          <span>Дом Северного Дозора</span>
          <h1>Замок</h1>
        </div>
        <div className="lord-castle-resources">
          {lordHomeStats.map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className={`lord-castle-resource ${stat.tone}`}>
                <Icon size={17} />
                <span>{stat.label}</span>
                <b>{stat.value}</b>
              </div>
            );
          })}
        </div>
      </header>

      <nav className="lord-castle-branch-rail" aria-label="Ветки замка">
        {castleBranchTabs.map((branch) => {
          const Icon = branch.icon;
          return (
            <button
              key={branch.id}
              className={`lord-castle-branch ${branch.tone}${branch.id === selectedBranch ? " is-active" : ""}`}
              type="button"
              onClick={() => selectBranch(branch.id)}
            >
              <Icon size={26} />
              <span>{branch.label}</span>
            </button>
          );
        })}
      </nav>

      <section className="lord-castle-hotspots" aria-label="Здания замка">
        {visibleBuildings.map((building) => {
          const Icon = building.icon;
          return (
            <button
              key={building.id}
              className={`lord-castle-hotspot ${building.tone} ${building.state}${building.id === selectedBuilding.id ? " is-selected" : ""}`}
              style={{ left: `${building.x}%`, top: `${building.y}%` }}
              type="button"
              onClick={() => setSelectedBuildingId(building.id)}
            >
              <Icon size={22} />
              <span>{building.name}</span>
            </button>
          );
        })}
      </section>

      <section className={`lord-castle-building-panel ${selectedBuilding.tone}`}>
        <div className="lord-castle-portrait">
          <SelectedIcon size={40} />
        </div>
        <div className="lord-castle-building-main">
          <span>
            {selectedBuilding.state === "built"
              ? "построено"
              : selectedBuilding.state === "available"
                ? "доступно"
                : "закрыто"}
          </span>
          <h2>{selectedBuilding.name}</h2>
          <p>{selectedBuilding.detail}</p>
        </div>
        <div className="lord-castle-building-slots">
          <div>
            <span>Стоимость</span>
            <b>{selectedBuilding.cost}</b>
          </div>
          <div>
            <span>Открывает</span>
            <b>{selectedBuilding.unlock}</b>
          </div>
        </div>
        <button className="lord-castle-main-action" type="button" disabled={selectedBuilding.state === "locked"}>
          {selectedBuilding.action}
        </button>
      </section>
      <LordMpHud className="lord-castle-mp-widget" currentMp={castleMpState.currentMp} mpCap={castleMpState.mpCap} />
    </main>
  );
}

function LordEndpointIndexScreen() {
  return (
    <main className="lord-endpoints-screen">
      <img className="lord-endpoints-bg" src={lordLoginBackground} alt="" />
      <div className="lord-endpoints-vignette" />
      <section className="lord-endpoints-panel">
        <div className="lord-endpoints-head">
          <div className="lord-endpoints-crest">
            <Layers size={30} />
          </div>
          <div>
            <span>Лордский контур</span>
            <h1>Экраны в браузере</h1>
          </div>
        </div>

        <div className="lord-endpoints-grid">
          {lordEndpointLinks.map((endpoint) => {
            const Icon = endpoint.icon;
            return (
              <a key={endpoint.path} className={`lord-endpoint-card ${endpoint.tone}`} href={endpoint.path}>
                <Icon size={24} />
                <span>{endpoint.state}</span>
                <h2>{endpoint.title}</h2>
                <code>{endpoint.path}</code>
                <p>{endpoint.detail}</p>
              </a>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function LordLoginScreen() {
  const [mode, setMode] = useState<"menu" | "login" | "onboarding">("menu");
  const [code, setCode] = useState("");
  const previewHover = new URLSearchParams(window.location.search).get("hover");

  return (
    <main className="lord-login-screen" onContextMenu={preventLordLoginContextMenu}>
      <div className="lord-login-bg" aria-hidden="true" style={{ backgroundImage: `url(${lordLoginBackground})` }} />
      <div className="lord-login-mist" />
      <img className="lord-login-logo-image" src={lordLoginLogo} alt="Witcher LARP I" draggable={false} />

      <aside className="lord-menu-sign">
        <img className="lord-menu-art" src={lordLoginMenuFrame} alt="" draggable={false} />
        <div className="lord-menu-frame">
          {mode === "menu" ? (
            <div className="lord-menu-buttons">
              <button className={`lord-slot-button${previewHover === "enter" ? " is-hover" : ""}`} onClick={() => setMode("login")} aria-label={lordLoginCopy.enter}>
                <span data-label={"\u0412\u0445\u043e\u0434"}>{"\u0412\u0445\u043e\u0434"}</span>
              </button>
              <button className={`lord-slot-button${previewHover === "training" ? " is-hover" : ""}`} onClick={() => setMode("onboarding")} aria-label={lordLoginCopy.training}>
                <span data-label={"\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435"}>{"\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435"}</span>
              </button>
            </div>
          ) : null}

          {mode === "login" ? (
            <form
              className="lord-login-form"
              onSubmit={(event) => {
                event.preventDefault();
              }}
            >
              <label>
                <span>Код лорда</span>
                <input
                  autoFocus
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="Введите код"
                />
              </label>
              <button type="submit">Войти</button>
              <button type="button" onClick={() => setMode("menu")}>
                Назад
              </button>
            </form>
          ) : null}

          {mode === "onboarding" ? (
            <div className="lord-onboarding-panel">
              <h1>Перед игрой</h1>
              <p>Войдите по коду лорда на своем компьютере. После входа откроется владение, карта и армия.</p>
              <button type="button" onClick={() => setMode("menu")}>
                Назад
              </button>
            </div>
          ) : null}
        </div>
      </aside>
    </main>
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
  const apiBaseUrl = (queryParams.get("api") || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
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
      window.location.assign(nextPath);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : lordLoginCopy.invalidCode);
      window.setTimeout(focusCodeInput, 0);
    } finally {
      setIsSubmittingLogin(false);
    }
  };

  const openTrainingBuild = () => {
    window.location.assign("/lords/home?training=1");
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

function HeroHeader() {
  return (
    <header className="relative overflow-hidden border-b border-ember-300/20 bg-[radial-gradient(circle_at_20%_0%,rgba(201,161,90,.18),transparent_35%),linear-gradient(180deg,rgba(9,8,7,.92),rgba(9,8,7,.7))] px-5 py-8 md:px-8">
      <div className="mx-auto grid w-full max-w-[1760px] gap-6 lg:grid-cols-[1.1fr_.9fr] lg:items-end">
        <div>
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="gold" icon={<Castle size={14} />}>Направление этапа 2Б</Badge>
            <Badge tone="green" icon={<CheckCircle2 size={14} />}>оригинальные изображения</Badge>
            <Badge tone="red" icon={<EyeOff size={14} />}>без официального арта</Badge>
          </div>
          <h1 className="max-w-5xl font-display text-4xl font-bold leading-[1.02] text-ember-50 md:text-6xl">
            Ведьмачий ЛАРП: командный стол, Гвинт и мобильные досье
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-stone-300 md:text-lg">
            Первый прототип строит интерфейс поверх оригинальных живописных
            изображений: карта, замок, карточный стол и дерево зданий остаются иллюстрацией,
            а все состояния, маршруты, карты, слоты и решения мастера живут как
            редактируемый интерфейс.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <StatusCard label="Цель визуала" value="тактическая ролевая доска" detail="сначала карта, затем действия" />
          <StatusCard label="Главные маршруты" value="лорд и Гвинт" detail="первый проход для Фигмы" />
          <StatusCard label="Тон телефонов" value="журнал и досье" detail="состояния без сети" />
          <StatusCard label="Тон мастера" value="операторская консоль" detail="улики, спор, финал" />
        </div>
      </div>
    </header>
  );
}

function LordCommandTable() {
  const [activeTerritoryId, setActiveTerritoryId] = useState<(typeof territoryNodes)[number]["id"]>("capital");
  const activeTerritory = territoryNodes.find((node) => node.id === activeTerritoryId) ?? territoryNodes[3];

  return (
    <Section id="lords" label="01 Стол лорда" title="Карта, замок, армия и бой лорда">
      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.55fr)_520px]">
        <div className="panel overflow-hidden p-0">
          <LordTopBar />
          <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="relative min-h-[670px] overflow-hidden border-r border-ember-300/20 bg-black">
              <img className="absolute inset-0 h-full w-full object-cover" src={lordMap} alt="" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_55%,transparent_42%,rgba(0,0,0,.2)_70%),linear-gradient(180deg,rgba(0,0,0,.15),rgba(0,0,0,.45))]" />
              <RouteOverlay />
              <MapCutoutLayer activeId={activeTerritoryId} />
              {territoryNodes.map((node) => (
                <TerritoryMarker
                  key={node.id}
                  active={node.id === activeTerritoryId}
                  node={node}
                  onEnter={() => setActiveTerritoryId(node.id)}
                />
              ))}
              <div className="absolute left-4 top-4 flex max-w-[420px] flex-col gap-3">
                <GlassPanel>
                  <div className="flex items-center gap-3">
                    <Map className="text-ember-300" size={22} />
                    <div>
                      <p className="text-xs uppercase tracking-[.24em] text-ember-100/60">живая карта владений</p>
                      <h3 className="text-xl font-semibold">Северный театр войны</h3>
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <Metric label="ходы" value="4/6" />
                    <Metric label="заявки" value="2" />
                    <Metric label="споры" value="1" />
                  </div>
                </GlassPanel>
                <div className="flex gap-2">
                  <Badge tone="green" icon={<Route size={14} />}>путь доступен</Badge>
                  <Badge tone="red" icon={<AlertTriangle size={14} />}>есть спор</Badge>
                </div>
              </div>
              <div className="absolute bottom-4 left-4 right-4">
                <ArmyLane />
              </div>
            </div>
            <TerritoryInspector node={activeTerritory} />
          </div>
        </div>
        <div className="grid gap-5">
          <CastleTree />
          <LordBattleBoard />
        </div>
      </div>
    </Section>
  );
}

function LordTopBar() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-ember-300/20 bg-black/35 px-5 py-4">
      <div className="flex items-center gap-4">
        <div className="grid h-14 w-14 place-items-center rounded-md border border-ember-300/60 bg-[linear-gradient(135deg,#2f1b16,#0d0b09)] shadow-brass">
          <Crown className="text-ember-300" />
        </div>
        <div>
          <p className="text-xs uppercase tracking-[.24em] text-ember-100/60">панель лорда 1</p>
          <h3 className="font-display text-2xl font-bold">Дом Северного Дозора</h3>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Resource icon={<Coins size={15} />} label="золото" value="80" />
        <Resource icon={<Gem size={15} />} label="влияние" value="14" />
        <Resource icon={<Clock3 size={15} />} label="акт" value="02:18" />
        <Resource icon={<Wifi size={15} />} label="связь" value="живая" tone="green" />
      </div>
    </div>
  );
}

function RouteOverlay() {
  const points = Object.fromEntries(territoryNodes.map((node) => [node.id, node]));
  return (
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      {routeLines.map(([from, to]) => {
        const a = points[from];
        const b = points[to];
        return (
          <line
            key={`${from}-${to}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="rgba(231, 190, 106, .66)"
            strokeDasharray="1.5 1.8"
            strokeLinecap="round"
            strokeWidth=".42"
          />
        );
      })}
    </svg>
  );
}

function MapCutoutLayer({ activeId }: { activeId: (typeof territoryNodes)[number]["id"] }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10">
      {territoryNodes.map((node) => (
        <img
          key={node.id}
          className={`map-cutout ${node.id === activeId ? "map-cutout-active" : ""}`}
          src={mapCutouts[node.id]}
          alt=""
          style={{
            left: `${node.x}%`,
            top: `${node.y}%`,
            width: `${node.cutoutWidth}%`,
            "--map-tone": toneColor[node.tone]
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

function TerritoryMarker({
  node,
  active,
  onEnter
}: {
  node: (typeof territoryNodes)[number];
  active: boolean;
  onEnter: () => void;
}) {
  const Icon = node.icon;
  return (
    <button
      className={`map-hotspot ${active ? "map-hotspot-active" : ""}`}
      style={{
        left: `${node.x}%`,
        top: `${node.y}%`,
        "--map-tone": toneColor[node.tone]
      } as React.CSSProperties}
      aria-label={node.label}
      onClick={onEnter}
      onFocus={onEnter}
      onMouseEnter={onEnter}
    >
      <Icon size={18} />
      <span className="map-hotspot-label">
        {node.label}
      </span>
    </button>
  );
}

function TerritoryInspector({ node }: { node: (typeof territoryNodes)[number] }) {
  return (
    <aside className="flex min-h-[670px] flex-col gap-4 bg-[linear-gradient(180deg,rgba(39,27,20,.94),rgba(16,13,11,.96))] p-4">
      <div className="overflow-hidden rounded-md border border-ember-300/35 bg-black/35">
        <img className="h-36 w-full object-cover" src={castleCity} alt="" />
        <div className="p-4">
          <p className="text-xs uppercase tracking-[.22em] text-ember-100/60">выбранная локация</p>
          <h3 className="mt-1 font-display text-2xl font-bold">{node.label}</h3>
          <p className="mt-2 text-sm leading-5 text-stone-300">
            Отдельная вырезка этой области лежит поверх карты. При наведении
            увеличивается именно фрагмент изображения, а не служебная кнопка.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Metric label="владелец" value={node.owner} />
        <Metric label="доход" value={node.income} />
        <Metric label="цена пути" value="2 хода" />
        <Metric label="статус" value={node.status} tone={node.tone === "red" ? "red" : "gold"} />
      </div>
      <GlassPanel>
        <div className="mb-3 flex items-center justify-between">
          <h4 className="font-semibold">Гарнизон и разведка</h4>
          <Badge tone="muted" icon={<EyeOff size={13} />}>враг скрыт</Badge>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {["Стража", "Стрелки", "Осада"].map((slot, index) => (
            <div key={slot} className="slot">
              <Shield size={16} />
              <span>{slot}</span>
              <b>{index === 2 ? "?" : index + 1}</b>
            </div>
          ))}
        </div>
      </GlassPanel>
      <div className="grid gap-2">
        <CommandButton icon={<Route size={16} />} label="Проложить маршрут" />
        <CommandButton icon={<Swords size={16} />} label="Начать захват" tone="red" />
        <CommandButton icon={<Archive size={16} />} label="Перебросить в форт" tone="muted" />
      </div>
      <StateStack />
    </aside>
  );
}

function ArmyLane() {
  return (
    <div className="rounded-lg border border-ember-300/30 bg-black/60 p-3 shadow-brass backdrop-blur-md">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Layers size={16} className="text-ember-300" /> Армия, резерв и гарнизон
        </div>
        <span className="text-xs text-stone-300">слоты для перетаскивания</span>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {army.map((unit) => (
          <UnitCard key={unit.name} unit={unit} />
        ))}
      </div>
    </div>
  );
}

function CastleTree() {
  return (
    <div className="panel relative min-h-[430px] overflow-hidden p-0">
      <img className="absolute inset-0 h-full w-full object-cover" src={buildingTreeBg} alt="" />
      <div className="absolute inset-0 bg-black/10" />
      <div className="relative flex h-full min-h-[430px] flex-col p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[.22em] text-cyan-100/60">дерево замка 6</p>
            <h3 className="font-display text-2xl font-bold">Развитие резиденции</h3>
          </div>
          <Badge tone="blue" icon={<Hammer size={14} />}>логика построек</Badge>
        </div>
        <div className="relative flex-1 rounded-md border border-cyan-200/20 bg-black/20">
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path d="M48 76 L30 55 L30 37 L30 20" stroke="rgba(133,211,255,.55)" strokeWidth=".45" fill="none" />
            <path d="M48 76 L48 55 L48 37 L48 20" stroke="rgba(133,211,255,.55)" strokeWidth=".45" fill="none" />
            <path d="M48 76 L66 55 L66 37" stroke="rgba(133,211,255,.55)" strokeWidth=".45" fill="none" />
          </svg>
          {buildingNodes.map((node) => (
            <BuildingNode key={node.name} node={node} />
          ))}
        </div>
      </div>
    </div>
  );
}

function BuildingNode({ node }: { node: (typeof buildingNodes)[number] }) {
  const stateTone = node.state === "purchased" ? "green" : node.state === "ready" ? "gold" : "muted";
  return (
    <button
      className={`absolute min-w-[98px] -translate-x-1/2 -translate-y-1/2 rounded-md border px-3 py-2 text-left shadow-brass backdrop-blur-sm ${toneClass[stateTone]}`}
      style={{ left: `${node.x}%`, top: `${node.y}%` }}
    >
      <span className="block text-[11px] font-bold leading-4">{node.name}</span>
      <span className="block text-[10px] text-current/70">{node.cost}</span>
    </button>
  );
}

function LordBattleBoard() {
  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[.22em] text-ember-100/60">боевой стол 10</p>
          <h3 className="font-display text-2xl font-bold">Бой 5x6</h3>
        </div>
        <Badge tone="red" icon={<Hourglass size={14} />}>ход 00:42</Badge>
      </div>
      <div className="grid grid-cols-6 gap-1 rounded-md border border-ember-300/25 bg-[linear-gradient(135deg,rgba(64,42,25,.8),rgba(15,12,9,.95))] p-2">
        {Array.from({ length: 30 }).map((_, index) => {
          const hasUnit = [2, 8, 13, 18, 23, 27].includes(index);
          return (
            <div key={index} className={`battle-cell ${hasUnit ? "battle-cell-active" : ""}`}>
              {hasUnit ? <Swords size={16} /> : null}
            </div>
          );
        })}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <Metric label="здоровье" value="18/24" tone="red" />
        <Metric label="инициатива" value="стража" tone="blue" />
        <Metric label="автоход" value="2 таймера" tone="gold" />
      </div>
    </div>
  );
}

function GwentBoard() {
  return (
    <Section id="gwent" label="02 Личный Гвинт" title="Личный карточный стол">
      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_430px]">
        <div className="panel relative min-h-[790px] overflow-hidden p-0">
          <img className="absolute inset-0 h-full w-full object-cover" src={gwentTable} alt="" />
          <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(0,0,0,.25),transparent_20%,transparent_78%,rgba(0,0,0,.32))]" />
          <div className="relative grid min-h-[790px] grid-cols-[230px_minmax(0,1fr)_190px] gap-4 p-5">
            <GwentSidebar side="соперник" score="63" name="Ильнгард" tone="red" />
            <div className="flex flex-col justify-between py-5">
              <GwentRows owner="opponent" />
              <div className="mx-auto flex w-full max-w-[760px] items-center justify-between rounded-md border border-ember-300/25 bg-black/50 p-3">
                <Badge tone="blue" icon={<Waves size={14} />}>погода: туман</Badge>
                <Badge tone="gold" icon={<Trophy size={14} />}>раунд 2 / ставка закрыта</Badge>
                <Badge tone="green" icon={<CheckCircle2 size={14} />}>ваш ход</Badge>
              </div>
              <GwentRows owner="player" />
              <div className="grid grid-cols-5 gap-2">
                {gwentCards.map((card) => (
                  <GwentCard key={card.name} card={card} />
                ))}
              </div>
            </div>
            <GwentDecks />
          </div>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[.22em] text-ember-100/60">экран телефона</p>
          <h3 className="mt-1 font-display text-2xl font-bold">Состояния Гвинта</h3>
          <div className="mt-4 grid gap-3">
            <StateItem icon={<Users size={16} />} title="ожидание вызова" text="Игрок ждет стол, жетон удержан." tone="blue" />
            <StateItem icon={<Package size={16} />} title="колода и сброс" text="Колода и кладбище отдельными стопками." tone="gold" />
            <StateItem icon={<XCircle size={16} />} title="проверка отказа" text="Отказ или таймаут уходит мастеру." tone="red" />
          </div>
          <div className="mt-4 rounded-lg border border-ember-300/25 bg-black/45 p-3">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Действие руки</span>
              <Badge tone="red">ставка закрыта</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <CommandButton icon={<Swords size={16} />} label="Сыграть" />
              <CommandButton icon={<Skull size={16} />} label="Спасовать" tone="muted" />
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
}

function GwentRows({ owner }: { owner: "opponent" | "player" }) {
  const rows = owner === "opponent" ? ["мечники", "лучники", "осада"] : ["мечники", "лучники", "осада"];
  return (
    <div className="grid gap-2">
      {rows.map((row, index) => (
        <div key={`${owner}-${row}`} className="gwent-row">
          <div className="score-chip">{owner === "opponent" ? [30, 7, 26][index] : [87, 24, 6][index]}</div>
          <span className="row-label">{row}</span>
          <div className="flex flex-1 gap-2">
            {Array.from({ length: index + (owner === "player" ? 2 : 1) }).map((_, cardIndex) => (
              <div key={cardIndex} className="mini-card">
                <span>{cardIndex + 2 + index}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function GwentSidebar({ side, score, name, tone }: { side: string; score: string; name: string; tone: Tone }) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-ember-300/25 bg-black/60 p-4 shadow-insetDeep">
      <div>
        <div className={`mb-3 grid h-24 place-items-center rounded border ${toneClass[tone]}`}>
          <Crown size={32} />
        </div>
        <p className="text-xs uppercase tracking-[.22em] text-stone-400">{side}</p>
        <h4 className="font-display text-xl font-bold">{name}</h4>
        <div className="mt-3 flex items-end gap-3">
          <span className="font-display text-5xl font-black text-ember-50">{score}</span>
          <span className="pb-2 text-xs text-stone-300">очков</span>
        </div>
      </div>
      <div className="grid gap-2">
        <Badge tone={tone} icon={<Shield size={14} />}>умение лидера готово</Badge>
        <Badge tone="muted" icon={<Skull size={14} />}>сброс виден</Badge>
      </div>
    </div>
  );
}

function GwentDecks() {
  return (
    <div className="flex flex-col justify-between gap-4 py-5">
      <div className="deck-stack blue">
        <Package size={26} />
        <span>10</span>
      </div>
      <div className="deck-stack grave">
        <Skull size={24} />
        <span>3</span>
      </div>
      <div className="deck-stack grave">
        <Skull size={24} />
        <span>1</span>
      </div>
      <div className="deck-stack red">
        <Package size={26} />
        <span>19</span>
      </div>
    </div>
  );
}

function GwentCard({ card }: { card: (typeof gwentCards)[number] }) {
  return (
    <button className={`gwent-card-piece ${card.tone}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-black/60 font-display text-lg font-black">
          {card.power}
        </span>
        <Sparkles size={16} />
      </div>
      <div className="mt-8">
        <b className="block text-sm">{card.name}</b>
        <span className="text-xs opacity-70">{card.row}</span>
      </div>
    </button>
  );
}

function MobileRoleScreens() {
  return (
    <Section id="mobile" label="03-04 Роли в телефоне" title="Телефоны: журнал ведьмака и досье чародейки">
      <div className="grid gap-5 xl:grid-cols-2">
        <MobileShell variant="witcher" />
        <MobileShell variant="sorceress" />
      </div>
    </Section>
  );
}

function MobileShell({ variant }: { variant: "witcher" | "sorceress" }) {
  const isWitcher = variant === "witcher";
  return (
    <div className="panel grid min-w-0 gap-5 p-4 2xl:grid-cols-[430px_minmax(0,1fr)]">
      <div className="phone-frame">
        <div className={`phone-screen ${isWitcher ? "witcher-phone" : "sorceress-phone"}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-stone-300">9:41</span>
            <Badge tone={isWitcher ? "blue" : "violet"} icon={<Wifi size={12} />}>без сети</Badge>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <div className={`grid h-20 w-20 place-items-center rounded-lg border ${isWitcher ? toneClass.blue : toneClass.violet}`}>
              {isWitcher ? <Swords size={34} /> : <Sparkles size={34} />}
            </div>
            <div>
              <p className="text-xs uppercase tracking-[.2em] text-stone-400">{isWitcher ? "журнал ведьмака 1" : "досье чародейки 1"}</p>
              <h3 className="font-display text-2xl font-bold">{isWitcher ? "Лютобор" : "Элиана из Марибора"}</h3>
              <p className="text-sm text-stone-300">{isWitcher ? "Школа Волка / Нейтральный" : "Мана 7/12 / Серебряный круг"}</p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label={isWitcher ? "жизни" : "мана"} value={isWitcher ? "18" : "7"} />
            <Metric label="акт" value="II" />
            <Metric label="очередь" value="3" tone="gold" />
          </div>
          <div className="mt-4 rounded-lg border border-ember-300/20 bg-black/40 p-3">
            <div className="mb-2 flex items-center justify-between">
              <b>{isWitcher ? "Код сцены" : "Цель заклинания"}</b>
              <Badge tone={isWitcher ? "red" : "violet"}>{isWitcher ? "пауза" : "проверка"}</Badge>
            </div>
            <p className="text-sm leading-5 text-stone-300">
              {isWitcher
                ? "Один бросок уже зафиксирован приложением. Награда ждет мастера."
                : "Заклинание влияет на видимость территории, причина видна только мастеру."}
            </p>
          </div>
          <div className="mt-4 grid gap-2">
            {(isWitcher
              ? ["Сканировать код", "Инвентарь", "Контракты", "Гвинт"]
              : ["Каталог чар", "Зелья", "Фавориты", "Финальная воля"]
            ).map((item, index) => (
              <button key={item} className="mobile-action">
                <span>{item}</span>
                <span>{index === 0 ? "активно" : "открыть"}</span>
              </button>
            ))}
          </div>
          <div className="mt-auto grid grid-cols-4 gap-2 pt-4">
            {[BookOpen, Crosshair, Package, Trophy].map((Icon, index) => (
              <button key={index} className="mobile-tab">
                <Icon size={18} />
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="grid min-w-0 content-start gap-3">
        <StateItem icon={<Wifi size={16} />} title="снимок без сети" text="Последний снимок явно маркирован и не скрывает очередь." tone="blue" />
        <StateItem icon={<AlertTriangle size={16} />} title={isWitcher ? "награда закрыта" : "цель неверна"} text={isWitcher ? "Нельзя тратить или ставить до решения мастера." : "Цель и мана проверяются сервером."} tone={isWitcher ? "gold" : "red"} />
        <StateItem icon={<ClipboardCheck size={16} />} title="нужна проверка мастера" text="Игрок видит краткое состояние, мастер видит причину." tone="violet" />
      </div>
    </div>
  );
}

function AdminOps() {
  return (
    <Section id="admin" label="05 Мастерская" title="Мастерская доска: проверка, бумага, финальные улики">
      <div className="panel grid gap-0 overflow-hidden p-0 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
        <aside className="border-r border-ember-300/20 bg-black/35 p-4">
          <div className="mb-5 flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-md border border-ember-300/45 bg-ember-300/10">
              <Gavel />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[.22em] text-stone-400">обзор 1</p>
              <h3 className="font-display text-xl font-bold">Пульт мастера</h3>
            </div>
          </div>
          <div className="grid gap-2">
            {["Проверка", "Награды", "Бумажный ввод", "Лорды", "Дуэли", "Инструменты НИП", "Финал"].map((item, index) => (
              <button key={item} className={`nav-row ${index === 2 ? "nav-row-active" : ""}`}>
                <span>{item}</span>
                <b>{index + 1}</b>
              </button>
            ))}
          </div>
        </aside>
        <div className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[.22em] text-ember-100/60">события и сверка 3</p>
              <h3 className="font-display text-3xl font-bold">Очередь улик</h3>
            </div>
            <Badge tone="red" icon={<FileWarning size={14} />}>срочные открыты</Badge>
          </div>
          <div className="grid gap-3">
            {reviewRows.map((row) => (
              <div key={row.id} className="review-row">
                <Badge tone={row.tone as Tone}>{row.id}</Badge>
                <span>{row.title}</span>
                <button>смотреть</button>
              </div>
            ))}
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <GlassPanel>
              <p className="text-xs uppercase tracking-[.2em] text-stone-400">бумажное восстановление 5</p>
              <h4 className="mt-1 text-xl font-semibold">действие лорда с бумаги</h4>
              <div className="mt-3 grid gap-2">
                <div className="input">лист: ЛРД-042</div>
                <div className="input">оператор: мастер-НИП / причина обязательна</div>
                <div className="input danger">конфликт: армия уже двигалась в приложении</div>
              </div>
            </GlassPanel>
            <GlassPanel>
              <p className="text-xs uppercase tracking-[.2em] text-stone-400">финальные улики 11</p>
              <h4 className="mt-1 text-xl font-semibold">Нерешенные блокировки</h4>
              <div className="mt-3 grid gap-2">
                <StateItem icon={<Sparkles size={15} />} title="магический замысел" text="2 приняты, 1 на проверке" tone="violet" compact />
                <StateItem icon={<Coins size={15} />} title="цены НИП" text="скрыто от игроков" tone="gold" compact />
              </div>
            </GlassPanel>
          </div>
        </div>
        <aside className="border-l border-ember-300/20 bg-black/30 p-4">
          <p className="text-xs uppercase tracking-[.22em] text-stone-400">панель решения</p>
          <h3 className="mt-1 font-display text-2xl font-bold">Разбор события</h3>
          <div className="mt-4 grid gap-2">
            <CommandButton icon={<CheckCircle2 size={16} />} label="Одобрить" />
            <CommandButton icon={<XCircle size={16} />} label="Отклонить с причиной" tone="red" />
            <CommandButton icon={<ClipboardCheck size={16} />} label="Исправить данные" tone="gold" />
          </div>
          <div className="mt-4 rounded-md border border-red-300/35 bg-red-500/10 p-3 text-sm text-red-100">
            Без причины отправка заблокирована. Тихая перезапись запрещена.
          </div>
        </aside>
      </div>
    </Section>
  );
}

function AssetHandoff() {
  return (
    <Section id="assets" label="06 Передача слоев" title="Слои, которые пойдут в Фигму">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AssetCard title="карта владений" src={lordMap} note="арт-слой, вырезки локаций и маршруты" />
        <AssetCard title="город-замок" src={castleCity} note="настроение и детализация замка" />
        <AssetCard title="карточный стол" src={gwentTable} note="доска, живые карты и стопки" />
        <AssetCard title="дерево зданий" src={buildingTreeBg} note="фон, поверх него живые узлы" />
      </div>
    </Section>
  );
}

function AssetCard({ title, src, note }: { title: string; src: string; note: string }) {
  return (
    <div className="panel overflow-hidden p-0">
      <img className="h-44 w-full object-cover" src={src} alt="" />
      <div className="p-4">
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-stone-300">{note}</p>
        <Badge tone="green" icon={<CheckCircle2 size={13} />}>сгенерировано отдельно</Badge>
      </div>
    </div>
  );
}

function Section({ id, label, title, children }: { id: string; label: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6 pt-8">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[.24em] text-ember-300/70">{label}</p>
          <h2 className="mt-1 font-display text-3xl font-bold md:text-4xl">{title}</h2>
        </div>
        <div className="flex gap-2">
          <Badge tone="gold">редактируемый интерфейс</Badge>
          <Badge tone="muted">готово для Фигмы</Badge>
        </div>
      </div>
      {children}
    </section>
  );
}

function Badge({ tone = "muted", icon, children }: { tone?: Tone; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className={`inline-flex min-h-7 items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-bold ${toneClass[tone]}`}>
      {icon}
      {children}
    </span>
  );
}

function StatusCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-ember-300/25 bg-black/40 p-4 shadow-brass backdrop-blur">
      <p className="text-xs uppercase tracking-[.22em] text-stone-400">{label}</p>
      <b className="mt-1 block text-lg text-ember-50">{value}</b>
      <span className="text-sm text-stone-300">{detail}</span>
    </div>
  );
}

function GlassPanel({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-ember-300/25 bg-black/50 p-4 shadow-insetDeep backdrop-blur-md">{children}</div>;
}

function Metric({ label, value, tone = "muted" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className={`rounded-md border px-3 py-2 ${toneClass[tone]}`}>
      <span className="block text-[10px] uppercase tracking-[.18em] opacity-70">{label}</span>
      <b className="text-sm">{value}</b>
    </div>
  );
}

function Resource({ icon, label, value, tone = "gold" }: { icon: React.ReactNode; label: string; value: string; tone?: Tone }) {
  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 ${toneClass[tone]}`}>
      {icon}
      <span className="text-xs uppercase text-current/60">{label}</span>
      <b>{value}</b>
    </div>
  );
}

function UnitCard({ unit }: { unit: (typeof army)[number] }) {
  return (
    <div className={`rounded-md border p-3 ${toneClass[unit.tone as Tone]}`}>
      <div className="mb-3 flex items-start justify-between">
        <Shield size={18} />
        <span className="text-[10px] uppercase opacity-70">{unit.type}</span>
      </div>
      <b className="block">{unit.name}</b>
      <div className="mt-2 flex gap-2 text-xs">
        <span>атака {unit.atk}</span>
        <span>жизни {unit.hp}</span>
      </div>
    </div>
  );
}

function CommandButton({ icon, label, tone = "gold" }: { icon: React.ReactNode; label: string; tone?: Tone }) {
  return (
    <button className={`flex min-h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-bold transition hover:brightness-125 ${toneClass[tone]}`}>
      {icon}
      {label}
    </button>
  );
}

function StateStack() {
  return (
    <div className="grid gap-2">
      <StateItem icon={<AlertTriangle size={15} />} title="нет ходов" text="Маршрут подсвечен, действие заблокировано." tone="red" compact />
      <StateItem icon={<EyeOff size={15} />} title="данные скрыты" text="Чужой гарнизон скрыт." tone="muted" compact />
      <StateItem icon={<FileWarning size={15} />} title="бумажный режим" text="Только как восстановление." tone="gold" compact />
    </div>
  );
}

function StateItem({
  icon,
  title,
  text,
  tone,
  compact
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  tone: Tone;
  compact?: boolean;
}) {
  return (
    <div className={`flex gap-3 rounded-md border ${toneClass[tone]} ${compact ? "p-2" : "p-3"}`}>
      <div className="mt-0.5">{icon}</div>
      <div>
        <b className="block text-sm">{title}</b>
        <span className="text-xs leading-5 opacity-75">{text}</span>
      </div>
    </div>
  );
}

export default App;
