import { useEffect, useRef, useState } from "react";
import type { FormEvent, MouseEvent } from "react";
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
import buildingBankIcon from "./assets/generated/lords-home/buildings/building-bank-v1.png";
import buildingMarketIcon from "./assets/generated/lords-home/buildings/building-market-v1.png";
import buildingStorehouseIcon from "./assets/generated/lords-home/buildings/building-storehouse-v1.png";
import buildingTaxOfficeIcon from "./assets/generated/lords-home/buildings/building-tax-office-v1.png";
import lordHomeActionBattleIcon from "./assets/generated/lords-home/actions/action-battle-v1.png";
import lordHomeActionBuildingsIcon from "./assets/generated/lords-home/actions/action-buildings-v1.png";
import lordHomeActionHelpIcon from "./assets/generated/lords-home/actions/action-help-v1.png";
import lordHomeActionLogoutIcon from "./assets/generated/lords-home/actions/action-logout-v1.png";
import lordHomeActionMapIcon from "./assets/generated/lords-home/actions/action-map-v1.png";
import lordHomeActionOrdersIcon from "./assets/generated/lords-home/actions/action-orders-v1.png";
import lordHomeActionRaidsIcon from "./assets/generated/lords-home/actions/action-raids-v1.png";
import lordHomeHudOverlay from "./assets/generated/lords-home/ui/lord-home-hud-overlay-v6.png";
import lordHomeMinimap from "./assets/generated/lords-home/minimap-v1.png";
import lordMapPlayableDisplay from "./assets/generated/lords-map/lord-map-playable-v1-display.webp";
import lordHomeMpFillField1 from "./assets/generated/lords-home/ui/mp-widget-fill-field-1-v5.png";
import lordHomeMpFillField2 from "./assets/generated/lords-home/ui/mp-widget-fill-field-2-v5.png";
import lordHomeMpFillField3 from "./assets/generated/lords-home/ui/mp-widget-fill-field-3-v5.png";
import lordHomeMpFillField4 from "./assets/generated/lords-home/ui/mp-widget-fill-field-4-v5.png";
import lordHomeMpFillField5 from "./assets/generated/lords-home/ui/mp-widget-fill-field-5-v5.png";
import lordHomeMpFillField6 from "./assets/generated/lords-home/ui/mp-widget-fill-field-6-v5.png";
import lordHomeMpFillField7 from "./assets/generated/lords-home/ui/mp-widget-fill-field-7-v5.png";
import lordHomeMpFillField8 from "./assets/generated/lords-home/ui/mp-widget-fill-field-8-v5.png";
import lordHomeMpWidgetFrame from "./assets/generated/lords-home/ui/mp-widget-frame-transparent-v5.png";
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
type LordHomeStack = { unitId: LordHomeUnitId; count: number };
type LordHomeDragPayload = { lane: "army" | "garrison"; index: number } | null;

const lordHomeUnitCatalog: Record<
  LordHomeUnitId,
  { name: string; role: string; icon: string; attack: number; defense: number; hp: number; cost: number; tone: Tone }
> = {
  infantry: { name: "Мечники", role: "пехота", icon: unitInfantryIcon, attack: 5, defense: 3, hp: 12, cost: 9, tone: "gold" },
  guard: { name: "Стража", role: "гарнизон", icon: unitGuardIcon, attack: 4, defense: 6, hp: 16, cost: 11, tone: "blue" },
  ranged: { name: "Лучники", role: "стрелки", icon: unitRangedIcon, attack: 6, defense: 2, hp: 8, cost: 10, tone: "green" },
  cavalry: { name: "Кавалерия", role: "конница", icon: unitCavalryIcon, attack: 8, defense: 4, hp: 14, cost: 18, tone: "red" },
  "heavy-siege": { name: "Осадники", role: "осада", icon: unitHeavySiegeIcon, attack: 10, defense: 5, hp: 20, cost: 24, tone: "gold" },
  specialist: { name: "Инженеры", role: "специалисты", icon: unitSpecialistIcon, attack: 3, defense: 3, hp: 9, cost: 14, tone: "violet" }
};

const lordHomeTerritories: Array<{
  id: LordHomeTerritoryId;
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
    name: "Туманное озеро",
    shortName: "Озеро",
    background: territoryMistLakeHome,
    income: 260,
    bonus: "Реагенты, разведка и скрытые тропы",
    heroHere: false,
    recruitIds: ["specialist", "ranged", "guard", null, null, null]
  }
];

const lordHomeInitialRecruitStock: Record<LordHomeTerritoryId, Record<LordHomeUnitId, { rate: number; stock: number }>> = {
  castle: {
    infantry: { rate: 35, stock: 0 },
    guard: { rate: 21, stock: 0 },
    ranged: { rate: 13, stock: 0 },
    cavalry: { rate: 6, stock: 0 },
    "heavy-siege": { rate: 3, stock: 0 },
    specialist: { rate: 2, stock: 0 }
  },
  "north-fort": {
    infantry: { rate: 18, stock: 8 },
    guard: { rate: 24, stock: 12 },
    ranged: { rate: 10, stock: 4 },
    cavalry: { rate: 0, stock: 0 },
    "heavy-siege": { rate: 4, stock: 1 },
    specialist: { rate: 0, stock: 0 }
  },
  "river-gate": {
    infantry: { rate: 20, stock: 5 },
    guard: { rate: 0, stock: 0 },
    ranged: { rate: 12, stock: 6 },
    cavalry: { rate: 8, stock: 2 },
    "heavy-siege": { rate: 0, stock: 0 },
    specialist: { rate: 5, stock: 1 }
  },
  "mist-lake": {
    infantry: { rate: 0, stock: 0 },
    guard: { rate: 7, stock: 3 },
    ranged: { rate: 9, stock: 4 },
    cavalry: { rate: 0, stock: 0 },
    "heavy-siege": { rate: 0, stock: 0 },
    specialist: { rate: 8, stock: 2 }
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

const lordHomeMaxMovementPoints = 8;
const lordHomeMovementFillFields = [
  lordHomeMpFillField1,
  lordHomeMpFillField2,
  lordHomeMpFillField3,
  lordHomeMpFillField4,
  lordHomeMpFillField5,
  lordHomeMpFillField6,
  lordHomeMpFillField7,
  lordHomeMpFillField8
];

const lordHomeActionDock = [
  { id: "buildings", label: "Здания", icon: lordHomeActionBuildingsIcon, tone: "gold" },
  { id: "map", label: "Карта", icon: lordHomeActionMapIcon, tone: "blue" },
  { id: "orders", label: "Заказы", icon: lordHomeActionOrdersIcon, tone: "green" },
  { id: "raids", label: "Рейды", icon: lordHomeActionRaidsIcon, tone: "red" },
  { id: "battle", label: "Бой", icon: lordHomeActionBattleIcon, tone: "red", alert: true }
] as const;

type LordHomeView = "territory" | "buildings";
type LordHomePanel = "map" | "orders" | "raids" | "battle" | "help";
type LordBuildingBranch = "military" | "economy" | "order" | "magic";
type LordBuildingState = "built" | "available" | "locked";

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

const lordBuildingIconById: Partial<Record<string, string>> = {
  b_market: buildingMarketIcon,
  b_tax_office: buildingTaxOfficeIcon,
  b_storehouse: buildingStorehouseIcon,
  b_bank: buildingBankIcon
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
    name: "Тренировочный двор",
    tier: 1,
    goldCost: 40,
    prerequisiteIds: [],
    recruitUnlockIds: ["unit_infantry_t1", "unit_guard_t1"],
    capacityDelta: 2,
    raidUnlock: false,
    x: 53.0,
    y: 67.4,
    effect: "Открывает базовую пехоту и стражу, увеличивает вместимость гарнизона."
  },
  {
    id: "b_barracks",
    branch: "military",
    name: "Казармы",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_training_yard"],
    recruitUnlockIds: ["unit_ranged_t1"],
    capacityDelta: 3,
    raidUnlock: false,
    x: 56.0,
    y: 56.4,
    effect: "Усиливает набор строевых отрядов и расширяет казарменные слоты."
  },
  {
    id: "b_archery_range",
    branch: "military",
    name: "Стрельбище",
    tier: 2,
    goldCost: 75,
    prerequisiteIds: ["b_training_yard"],
    recruitUnlockIds: ["unit_ranged_t1"],
    capacityDelta: 1,
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
    goldCost: 75,
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
    capacityDelta: 1,
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
    capacityDelta: 2,
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
    recruitUnlockIds: ["unit_infantry_t1"],
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
    capacityDelta: 4,
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
    recruitUnlockIds: ["unit_infantry_t1"],
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
    recruitUnlockIds: ["unit_specialist_t3"],
    capacityDelta: 0,
    raidUnlock: false,
    x: 40.6,
    y: 67.4,
    effect: "Открывает магическую ветку и редких специалистов поддержки."
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

const lordMapSockets = [
  { id: "node_fort_east", name: "Северная застава", x: 47.92, y: 21.33, tone: "neutral", owner: "нейтрально", route: "2 MP до центра" },
  { id: "node_res_north", name: "Северная резиденция", x: 44.55, y: 41.1, tone: "domain-north", owner: "Север", route: "резиденция, рейды" },
  { id: "node_res_river", name: "Речная резиденция", x: 51.15, y: 39.15, tone: "domain-river", owner: "Река", route: "резиденция, рейды" },
  { id: "node_res_forest", name: "Лесная резиденция", x: 44.85, y: 48.15, tone: "domain-forest", owner: "Лес", route: "резиденция, рейды" },
  { id: "node_res_hill", name: "Холмовая резиденция", x: 56, y: 48.85, tone: "domain-hill", owner: "Холм", route: "резиденция, рейды" },
  { id: "node_field_oats", name: "Северные овсы", x: 30.06, y: 27.23, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_mountain_north_alpine", name: "Северный кряж", x: 61.79, y: 22.18, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_well_city", name: "Колодезный торг", x: 70.95, y: 28.34, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_field_west_large", name: "Левобережные пашни", x: 11.75, y: 23.65, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_village_east_shed", name: "Восточная слобода", x: 74.61, y: 45.36, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_lake_mist", name: "Зеркальный пруд", x: 80.99, y: 40.29, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_fort_west", name: "Западный острог", x: 20.82, y: 43.6, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_mountain_gray", name: "Серый дозор", x: 62, y: 55.78, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_field_east_large", name: "Правые пашни", x: 73.33, y: 60.33, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_fort_southwest", name: "Южная крепь", x: 37.03, y: 62.69, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_village_barn", name: "Сенной посад", x: 51.69, y: 65.34, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_swamp_black", name: "Черная топь", x: 16.95, y: 70.18, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_forest_dark", name: "Травничья роща", x: 13.86, y: 83.2, tone: "neutral", owner: "нейтрально", route: "1 MP" },
  { id: "node_spanish_magic", name: "Чародейский угол", x: 51.44, y: 94.47, tone: "neutral", owner: "нейтрально", route: "спор, 2 MP" },
  { id: "node_mountain_west_alpine", name: "Волчий утес", x: 44.5, y: 85.53, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_science_barn", name: "Двухъярусная мануфактура", x: 60.84, y: 86.21, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_forest_south_garden", name: "Нижний сад", x: 93.87, y: 84.93, tone: "neutral", owner: "нейтрально", route: "2 MP" },
  { id: "node_lake_south_pond", name: "Лунная заводь", x: 87.07, y: 94.61, tone: "neutral", owner: "нейтрально", route: "1 MP" }
] satisfies Array<{
  id: string;
  name: string;
  x: number;
  y: number;
  tone: LordMapSocketTone;
  owner: string;
  route: string;
}>;

const lordMapLordMeta: Record<LordMapLordId, { name: string; armyName: string; homeSocketId: string; tone: LordMapSocketTone }> = {
  north: { name: "Север", armyName: "Северное войско", homeSocketId: "node_res_north", tone: "domain-north" },
  river: { name: "Река", armyName: "Речное войско", homeSocketId: "node_res_river", tone: "domain-river" },
  forest: { name: "Лес", armyName: "Лесное войско", homeSocketId: "node_res_forest", tone: "domain-forest" },
  hill: { name: "Холм", armyName: "Холмовое войско", homeSocketId: "node_res_hill", tone: "domain-hill" }
};

const lordMapTravelEdges = [
  { from: "node_res_north", to: "node_field_oats", cost: 1 },
  { from: "node_res_north", to: "node_fort_east", cost: 2 },
  { from: "node_fort_east", to: "node_mountain_north_alpine", cost: 2 },
  { from: "node_fort_west", to: "node_field_oats", cost: 1 },
  { from: "node_fort_west", to: "node_field_west_large", cost: 1 },
  { from: "node_fort_west", to: "node_fort_east", cost: 2 },
  { from: "node_field_west_large", to: "node_forest_dark", cost: 2 },
  { from: "node_swamp_black", to: "node_forest_dark", cost: 2 },
  { from: "node_swamp_black", to: "node_fort_southwest", cost: 2 },
  { from: "node_res_forest", to: "node_fort_southwest", cost: 1 },
  { from: "node_fort_southwest", to: "node_mountain_west_alpine", cost: 2 },
  { from: "node_res_forest", to: "node_village_barn", cost: 1 },
  { from: "node_village_barn", to: "node_spanish_magic", cost: 2 },
  { from: "node_village_barn", to: "node_mountain_gray", cost: 2 },
  { from: "node_spanish_magic", to: "node_science_barn", cost: 2 },
  { from: "node_science_barn", to: "node_forest_south_garden", cost: 2 },
  { from: "node_forest_south_garden", to: "node_lake_south_pond", cost: 1 },
  { from: "node_field_east_large", to: "node_science_barn", cost: 2 },
  { from: "node_res_hill", to: "node_field_east_large", cost: 1 },
  { from: "node_res_hill", to: "node_mountain_gray", cost: 2 },
  { from: "node_village_east_shed", to: "node_well_city", cost: 1 },
  { from: "node_village_east_shed", to: "node_lake_mist", cost: 1 },
  { from: "node_lake_mist", to: "node_field_east_large", cost: 1 },
  { from: "node_res_river", to: "node_well_city", cost: 1 },
  { from: "node_res_river", to: "node_village_east_shed", cost: 1 },
  { from: "node_fort_east", to: "node_well_city", cost: 2 },
] as const;

const lordMapMovementPoints = 6;

const getLordMapSocketById = (socketId: string) =>
  lordMapSockets.find((socket) => socket.id === socketId) ?? lordMapSockets[0];

const getLordMapCurrentLordId = (): LordMapLordId => {
  const lordParam = new URLSearchParams(window.location.search).get("lord");

  if (lordParam === "north" || lordParam === "river" || lordParam === "forest" || lordParam === "hill") {
    return lordParam;
  }

  return "forest";
};

const getLordMapDirectCost = (fromId: string, toId: string) => {
  const edge = lordMapTravelEdges.find(
    (travelEdge) =>
      (travelEdge.from === fromId && travelEdge.to === toId) ||
      (travelEdge.from === toId && travelEdge.to === fromId)
  );

  return edge?.cost ?? null;
};

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

const getLordMapTravelState = (startSocketId: string) => {
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
    path: "/lords/login",
    title: "Вход лорда",
    detail: "Игровой код роли, валидный вход в лордский контур.",
    state: "готово",
    icon: Crown,
    tone: "blue"
  },
  {
    path: "/lords/castle",
    title: "Замок",
    detail: "Основная страница после входа: резиденция, ветки развития и здания.",
    state: "основная",
    icon: Castle,
    tone: "gold"
  },
  {
    path: "/lords/home",
    title: "Карта владений",
    detail: "Крупная карта, мини-карта и переходы в замок, заказы и рейды.",
    state: "готово",
    icon: Map,
    tone: "green"
  },
  {
    path: "/lords/dashboard",
    title: "Карта, алиас",
    detail: "Тот же экран карты для старых ссылок и тестов.",
    state: "алиас",
    icon: Route,
    tone: "muted"
  },
  {
    path: "/lords",
    title: "Основной вход",
    detail: "Алиас основной страницы лорда, сейчас ведет в замок.",
    state: "алиас",
    icon: Castle,
    tone: "muted"
  },
  {
    path: "/",
    title: "Stage 2B обзор",
    detail: "Общая витрина прототипов и старых экранов Stage 2B.",
    state: "служебно",
    icon: Layers,
    tone: "violet"
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

function LordMapScreen() {
  const currentLordId = getLordMapCurrentLordId();
  const currentLord = lordMapLordMeta[currentLordId];
  const armySocketId = currentLord.homeSocketId;
  const [selectedSocketId, setSelectedSocketId] = useState(armySocketId);
  const [hoveredSocketId, setHoveredSocketId] = useState<string | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const selectedSocket = getLordMapSocketById(selectedSocketId);
  const displaySocket = getLordMapSocketById(hoveredSocketId ?? selectedSocketId);
  const armySocket = getLordMapSocketById(armySocketId);
  const travelState = getLordMapTravelState(armySocketId);
  const displayTravelCost = travelState.distances[displaySocket.id];
  const displayPathIds = getLordMapTravelPath(armySocketId, displaySocket.id, travelState.previous);
  const displayPathLabel = displayPathIds.map((socketId) => getLordMapSocketById(socketId).name).join(" - ");
  const hasDisplayRoute = Number.isFinite(displayTravelCost);
  const displayRouteText = displaySocket.id === armySocketId
    ? `${currentLord.armyName}: ${lordMapMovementPoints} MP.`
    : hasDisplayRoute && displayTravelCost <= lordMapMovementPoints
      ? `Поход: ${displayTravelCost} MP. Останется ${lordMapMovementPoints - displayTravelCost} MP.`
      : hasDisplayRoute
        ? `Дальний поход: ${displayTravelCost} MP. Сейчас ${lordMapMovementPoints} MP.`
        : "Нет открытой дороги.";
  const activeBattle = true;

  return (
    <main className="lord-map-game-screen" onContextMenu={(event) => event.preventDefault()}>
      <div className="lord-map-game-stage">
        <div className="lord-map-game-grade" />
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
            className="lord-map-artboard"
            initial={prefersReducedMotion ? false : { opacity: 0.82, scale: 1.012 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, scale: 1 }}
            transition={prefersReducedMotion ? undefined : { duration: 0.28, ease: "easeOut" }}
          >
            <img className="lord-map-playable-image" src={lordMapPlayableDisplay} alt="" draggable={false} />
            <div className="lord-map-owner-layer">
              {lordMapSockets.map((socket) => {
                const directTravelCost = getLordMapDirectCost(armySocketId, socket.id);
                const travelCost = travelState.distances[socket.id];
                const isArmySocket = socket.id === armySocketId;
                const isRouteStep = displayPathIds.includes(socket.id);
                const isPreviewTarget = displaySocket.id === socket.id && !isArmySocket;
                const isDirectRoute = directTravelCost !== null && !isArmySocket;
                const isOutOfRange = isPreviewTarget && Number.isFinite(travelCost) && travelCost > lordMapMovementPoints;

                return (
                  <button
                    key={socket.id}
                    className={`lord-map-owner-socket ${socket.tone}${selectedSocket.id === socket.id ? " is-selected" : ""}${isArmySocket ? " is-army-node" : ""}${isRouteStep ? " is-route-step" : ""}${isDirectRoute ? " is-direct-route" : ""}${isPreviewTarget ? " is-preview-target" : ""}${isOutOfRange ? " is-out-of-range" : ""}`}
                    type="button"
                    style={{ left: `${socket.x}%`, top: `${socket.y}%` }}
                    onClick={() => setSelectedSocketId(socket.id)}
                    onFocus={() => setHoveredSocketId(socket.id)}
                    onBlur={() => setHoveredSocketId(null)}
                    onMouseEnter={() => setHoveredSocketId(socket.id)}
                    onMouseLeave={() => setHoveredSocketId(null)}
                    aria-label={isArmySocket ? `${socket.name}, ${currentLord.armyName}` : socket.name}
                  />
                );
              })}
            </div>
            <div className="lord-map-cost-layer" aria-hidden="true">
              {lordMapSockets.map((socket) => {
                const directTravelCost = getLordMapDirectCost(armySocketId, socket.id);
                const travelCost = travelState.distances[socket.id];
                const isArmySocket = socket.id === armySocketId;
                const isPreviewTarget = displaySocket.id === socket.id && !isArmySocket;
                const visibleCost = directTravelCost ?? (isPreviewTarget && Number.isFinite(travelCost) ? travelCost : null);

                if (isArmySocket || visibleCost === null) {
                  return null;
                }

                return (
                  <span
                    key={socket.id}
                    className={`lord-map-travel-cost${directTravelCost === null ? " is-total-cost" : ""}${visibleCost > lordMapMovementPoints ? " is-out-of-range" : ""}`}
                    style={{ left: `${socket.x}%`, top: `${socket.y}%` }}
                  >
                    {visibleCost} MP
                  </span>
                );
              })}
            </div>
            <button
              className={`lord-map-army-marker ${currentLord.tone}`}
              type="button"
              style={{ left: `${armySocket.x}%`, top: `${armySocket.y}%` }}
              onClick={() => setSelectedSocketId(armySocketId)}
              onFocus={() => setHoveredSocketId(armySocketId)}
              onBlur={() => setHoveredSocketId(null)}
              onMouseEnter={() => setHoveredSocketId(armySocketId)}
              onMouseLeave={() => setHoveredSocketId(null)}
              aria-label={`${currentLord.armyName}, ${armySocket.name}`}
            >
              <span className="lord-map-army-aura" />
              <span className="lord-map-army-standard">
                <span className="lord-map-army-flag" />
                <span className="lord-map-army-pole" />
              </span>
              <span className="lord-map-army-caption">Армия</span>
            </button>
          </motion.div>
        </section>

        <aside className={`lord-map-selection ${displaySocket.tone}`} aria-live="polite">
          <span>{displaySocket.id === armySocketId ? currentLord.armyName : displaySocket.owner}</span>
          <h1>{displaySocket.name}</h1>
          <p>{displayRouteText}</p>
          {displayPathIds.length > 1 && (
            <small className="lord-map-route-chain">{displayPathLabel}</small>
          )}
        </aside>
      </div>
    </main>
  );
}

function LordHomeScreen() {
  const homeRouteParams = new URLSearchParams(window.location.search);
  const initialHomeView: LordHomeView = homeRouteParams.get("view") === "buildings" ? "buildings" : "territory";
  const buildingParam = homeRouteParams.get("building");
  const initialSelectedBuildingId =
    buildingParam && lordBuildingTreeNodes.some((building) => building.id === buildingParam)
      ? buildingParam
      : "b_barracks";
  const panelParam = homeRouteParams.get("panel");
  const initialOpenPanel: LordHomePanel | null =
    panelParam === "map" || panelParam === "orders" || panelParam === "raids" || panelParam === "battle" || panelParam === "help"
      ? panelParam
      : null;
  const [selectedTerritoryId, setSelectedTerritoryId] = useState<LordHomeTerritoryId>("castle");
  const [army, setArmy] = useState<LordHomeStack[]>(lordHomeInitialArmy);
  const [garrisons, setGarrisons] = useState<Record<LordHomeTerritoryId, LordHomeStack[]>>(lordHomeInitialGarrisons);
  const [recruitStock, setRecruitStock] = useState(lordHomeInitialRecruitStock);
  const [recruitUnitId, setRecruitUnitId] = useState<LordHomeUnitId | null>(null);
  const [recruitQty, setRecruitQty] = useState(1);
  const [dragPayload, setDragPayload] = useState<LordHomeDragPayload>(null);
  const [homeView, setHomeView] = useState<LordHomeView>(initialHomeView);
  const [builtBuildingIds, setBuiltBuildingIds] = useState<Set<string>>(() => new Set(lordBuildingInitialBuiltIds));
  const [selectedBuildingId, setSelectedBuildingId] = useState(initialSelectedBuildingId);
  const [openPanel, setOpenPanel] = useState<LordHomePanel | null>(initialOpenPanel);
  const prefersReducedMotion = useReducedMotion();
  const selectedTerritory = lordHomeTerritories.find((territory) => territory.id === selectedTerritoryId) ?? lordHomeTerritories[0];
  const selectedGarrison = garrisons[selectedTerritory.id] ?? [];
  const recruitUnit = recruitUnitId ? lordHomeUnitCatalog[recruitUnitId] : null;
  const recruitStockInfo = recruitUnitId ? recruitStock[selectedTerritory.id][recruitUnitId] : null;
  const maxRecruitQty = Math.max(0, recruitStockInfo?.stock ?? 0);
  const recruitSliderPercent = maxRecruitQty > 1
    ? ((recruitQty - 1) / (maxRecruitQty - 1)) * 100
    : maxRecruitQty > 0 ? 100 : 0;
  const activeBattle = true;
  const currentMovementPoints = 6;

  const buildSelectedBuilding = (buildingId: string) => {
    const building = lordBuildingTreeNodes.find((item) => item.id === buildingId);
    if (!building || getLordBuildingState(building, builtBuildingIds) !== "available") {
      return;
    }

    setBuiltBuildingIds((current) => {
      const next = new Set(current);
      next.add(buildingId);
      return next;
    });
  };

  const mergeStack = (target: LordHomeStack[], stack: LordHomeStack, maxSlots: number) => {
    const existingIndex = target.findIndex((item) => item.unitId === stack.unitId);

    if (existingIndex >= 0) {
      return target.map((item, index) => index === existingIndex ? { ...item, count: item.count + stack.count } : item);
    }

    if (target.length >= maxSlots) {
      return target;
    }

    return [...target, stack];
  };

  const moveStack = (fromLane: "army" | "garrison", index: number, toLane: "army" | "garrison") => {
    if (!selectedTerritory.heroHere || fromLane === toLane) {
      return;
    }

    if (fromLane === "army") {
      const stack = army[index];
      if (!stack) {
        return;
      }

      setArmy((current) => current.filter((_, itemIndex) => itemIndex !== index));
      setGarrisons((current) => ({
        ...current,
        [selectedTerritory.id]: mergeStack(current[selectedTerritory.id] ?? [], stack, 8)
      }));
      return;
    }

    const stack = selectedGarrison[index];
    if (!stack) {
      return;
    }

    setGarrisons((current) => ({
      ...current,
      [selectedTerritory.id]: current[selectedTerritory.id].filter((_, itemIndex) => itemIndex !== index)
    }));
    setArmy((current) => mergeStack(current, stack, 8));
  };

  const hireRecruit = () => {
    if (!recruitUnitId || recruitQty < 1 || recruitQty > maxRecruitQty) {
      return;
    }

    const hiredStack: LordHomeStack = { unitId: recruitUnitId, count: recruitQty };

    setRecruitStock((current) => ({
      ...current,
      [selectedTerritory.id]: {
        ...current[selectedTerritory.id],
        [recruitUnitId]: {
          ...current[selectedTerritory.id][recruitUnitId],
          stock: current[selectedTerritory.id][recruitUnitId].stock - recruitQty
        }
      }
    }));
    setGarrisons((current) => ({
      ...current,
      [selectedTerritory.id]: mergeStack(current[selectedTerritory.id] ?? [], hiredStack, 8)
    }));
    setRecruitUnitId(null);
  };

  const openRecruitModal = (unitId: LordHomeUnitId) => {
    setRecruitUnitId(unitId);
    setRecruitQty(recruitStock[selectedTerritory.id][unitId].stock > 0 ? 1 : 0);
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
              onSelectBuilding={setSelectedBuildingId}
              onBuild={buildSelectedBuilding}
            />
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

        <header className="lord-home-top-strip">
          <div className="lord-home-resource-row">
            <div className="lord-home-resource gold"><Coins size={14} /><b>18804</b><span>(+3040/час)</span></div>
            <div className="lord-home-resource wood"><Archive size={14} /><b>17</b></div>
            <div className="lord-home-resource violet"><Gem size={14} /><b>63</b></div>
            <div className="lord-home-resource blue"><Sparkles size={14} /><b>42</b></div>
            <div className="lord-home-resource red"><Flame size={14} /><b>41</b></div>
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
              className={`lord-home-dock-button action-${action.id} ${action.tone}${"alert" in action && action.alert && activeBattle ? " is-alert" : ""}${action.id === "buildings" && homeView === "buildings" ? " is-selected" : ""}`}
              type="button"
              aria-label={action.label}
              onClick={() => {
                if (action.id === "buildings") {
                  setHomeView((current) => current === "buildings" ? "territory" : "buildings");
                  setOpenPanel(null);
                  return;
                }

                if (action.id === "map") {
                  window.location.assign("/lords/map");
                  return;
                }

                setOpenPanel(action.id);
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

            <section className="lord-home-bottom-panel" aria-label="Армия, гарнизон и найм">
              <div className="lord-home-location-title">{selectedTerritory.name}</div>
              <div className="lord-home-local-income">Доход территории: +{selectedTerritory.income}/час</div>

              <LordHomeLane
                lane="army"
                label="Армия"
                stacks={selectedTerritory.heroHere ? army : []}
                locked={!selectedTerritory.heroHere}
                onStackClick={(index) => moveStack("army", index, "garrison")}
                onDragStart={(payload) => setDragPayload(payload)}
                onDrop={() => {
                  if (dragPayload) {
                    moveStack(dragPayload.lane, dragPayload.index, "army");
                  }
                  setDragPayload(null);
                }}
              />
              <LordHomeLane
                lane="garrison"
                label="Гарнизон"
                stacks={selectedGarrison}
                locked={false}
                onStackClick={(index) => moveStack("garrison", index, "army")}
                onDragStart={(payload) => setDragPayload(payload)}
                onDrop={() => {
                  if (dragPayload) {
                    moveStack(dragPayload.lane, dragPayload.index, "garrison");
                  }
                  setDragPayload(null);
                }}
              />

              {!selectedTerritory.heroHere ? <div className="lord-home-army-lock">Герой в другой локации</div> : null}

              <div className="lord-home-recruit-grid">
                {selectedTerritory.recruitIds.map((unitId, index) => {
                  if (!unitId) {
                    return <div key={`empty-${index}`} className="lord-home-recruit-card is-empty" />;
                  }

                  const unit = lordHomeUnitCatalog[unitId];
                  const stockInfo = recruitStock[selectedTerritory.id][unitId];

                  return (
                    <button key={unitId} className="lord-home-recruit-card" type="button" onClick={() => openRecruitModal(unitId)}>
                      <img src={unit.icon} alt="" draggable={false} />
                      <span className="lord-home-recruit-count">+{stockInfo.rate} ({stockInfo.stock})</span>
                    </button>
                  );
                })}
              </div>
            </section>

        {homeView === "territory" ? (
            <aside className="lord-home-territory-bubbles" aria-label="Захваченные территории">
              {lordHomeTerritories.slice(1).map((territory) => (
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

        <section
          className="lord-home-act-widget"
          aria-label={`Акт II, 42 минуты до следующего акта, передвижений ${currentMovementPoints} из ${lordHomeMaxMovementPoints}`}
        >
          <div className="lord-home-mp-rect-layer" aria-hidden="true">
            {lordHomeMovementFillFields.map((src, index) =>
              index < currentMovementPoints ? (
                <img key={src} className="lord-home-mp-fill-field" src={src} alt="" draggable={false} />
              ) : null
            )}
          </div>
          <img className="lord-home-mp-widget-frame" src={lordHomeMpWidgetFrame} alt="" draggable={false} />
          <div className="lord-home-act-caption">
            <b>Акт II</b>
            <span>42 мин.</span>
          </div>
        </section>

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
                    <b>АТК {recruitUnit.attack}</b>
                    <b>ЗЩТ {recruitUnit.defense}</b>
                    <b>HP {recruitUnit.hp}</b>
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
                      onClick={() => setRecruitQty((current) => Math.max(1, current - 1))}
                    >
                      -
                    </button>
                    <button
                      className="lord-home-recruit-track"
                      type="button"
                      aria-label="Выбрать количество"
                      disabled={maxRecruitQty < 1}
                      onClick={(event) => setRecruitQtyFromTrack(event.clientX, event.currentTarget)}
                    >
                      <span className="lord-home-recruit-track-fill" style={{ width: `${recruitSliderPercent}%` }} />
                      <i className="lord-home-recruit-track-thumb" style={{ left: `${recruitSliderPercent}%` }} />
                    </button>
                    <button
                      className="lord-home-recruit-step"
                      type="button"
                      aria-label="Увеличить количество"
                      disabled={maxRecruitQty < 1 || recruitQty >= maxRecruitQty}
                      onClick={() => setRecruitQty((current) => Math.min(maxRecruitQty, current + 1))}
                    >
                      +
                    </button>
                  </div>
                </div>
                <div className="lord-home-recruit-cost">
                  <span>Стоимость</span>
                  <b>{recruitQty * recruitUnit.cost} золота</b>
                  <small>В наличии: {maxRecruitQty}</small>
                </div>
                <button className="lord-home-hire-button" type="button" onClick={hireRecruit} disabled={maxRecruitQty < 1}>
                  Нанять
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
  onSelectBuilding,
  onBuild
}: {
  builtBuildingIds: Set<string>;
  selectedBuildingId: string;
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
  const missingPrerequisites = activeBuilding.prerequisiteIds
    .filter((id) => !builtBuildingIds.has(id))
    .map((id) => nodeById.get(id)?.name)
    .filter(Boolean);
  const recruitLabels = activeBuilding.recruitUnlockIds
    .map((id) => lordBuildingRecruitLabels[id] ?? id)
    .join(", ");
  const buildingBenefitBullets = [
    ...(lordBuildingBaseBenefitLabels[activeBuilding.id] ?? []),
    ...(activeBuilding.capacityDelta > 0 ? [`Гарнизон +${activeBuilding.capacityDelta}`] : []),
    ...(recruitLabels ? [`Найм: ${recruitLabels}`] : []),
    ...(activeBuilding.raidUnlock ? ["Рейды: открыто"] : [])
  ];
  const buildButtonText =
    activeState === "built" ? "Построено" : activeState === "available" ? "Построить" : "Недоступно";

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
            {activeState === "built" ? "Построено" : activeState === "available" ? "Можно построить" : "Требуются постройки"}
          </span>
          <h2>{activeBuilding.name}</h2>
          <p>{activeBuilding.effect}</p>
        </div>
        <div className="lord-building-cost-row">
          <b><Coins size={13} /> {activeBuilding.goldCost}</b>
          <b><Crown size={13} /> Уровень {activeBuilding.tier}</b>
        </div>
        {activeState !== "built" && missingPrerequisites.length ? (
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
          disabled={activeState !== "available"}
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
  onDragStart,
  onDrop
}: {
  lane: "army" | "garrison";
  label: string;
  stacks: LordHomeStack[];
  locked: boolean;
  onStackClick: (index: number) => void;
  onDragStart: (payload: LordHomeDragPayload) => void;
  onDrop: () => void;
}) {
  return (
    <div
      className={`lord-home-lane ${lane}${locked ? " is-locked" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={onDrop}
    >
      <span className="lord-home-lane-label">{label}</span>
      {Array.from({ length: 8 }).map((_, index) => {
        const stack = stacks[index];

        return (
          <button
            key={`${lane}-${index}`}
            className={`lord-home-unit-slot${stack ? " is-filled" : ""}`}
            type="button"
            disabled={!stack || locked}
            draggable={Boolean(stack && !locked)}
            onDragStart={() => onDragStart({ lane, index })}
            onDragEnd={() => onDragStart(null)}
            onClick={() => stack && onStackClick(index)}
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

const validLordAccessCodes = new Set(["1234", "LORD", "LORD-1", "\u0421\u0415\u0412\u0415\u0420"]);

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
  const initialMode: AnimatedLordLoginMode =
    requestedView === "login" || requestedView === "onboarding" ? requestedView : "menu";
  const [mode, setMode] = useState<AnimatedLordLoginMode>(initialMode);
  const [code, setCode] = useState("");
  const [loginError, setLoginError] = useState(queryParams.get("error") === "login" ? lordLoginCopy.invalidCode : "");
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

  const handleLoginSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedCode = normalizeLordAccessCode(code);

    if (!normalizedCode) {
      setLoginError(lordLoginCopy.emptyCode);
      window.setTimeout(focusCodeInput, 0);
      return;
    }

    if (validLordAccessCodes.has(normalizedCode)) {
      setLoginError("");
      window.location.assign("/lords/home");
      return;
    }

    setLoginError(lordLoginCopy.invalidCode);
    window.setTimeout(focusCodeInput, 0);
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
                  <button className="lord-panel-action-button lord-submit-button" type="submit" disabled={isTransitioning}>
                    {lordLoginCopy.submit}
                  </button>
                  <button className="lord-panel-action-button lord-back-button" type="button" onClick={() => void movePanelTo("menu")} disabled={isTransitioning}>
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
