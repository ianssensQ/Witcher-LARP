import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Crosshair,
  Crown,
  Flame,
  Gavel,
  Hourglass,
  Shield,
  Skull,
  Sparkles,
  Swords,
  Trophy,
  Users,
  Waves,
  XCircle
} from "lucide-react";
import lordBattleBoardCloseup from "./assets/generated/lords-battle/lord-battle-board-closeup-v1.png";
import lordBattleWarTable from "./assets/generated/lords-battle/lord-battle-war-table-v1.png";
import unitCavalryIcon from "./assets/generated/lords-home/units/unit-cavalry-v1.png";
import unitGuardIcon from "./assets/generated/lords-home/units/unit-guard-v1.png";
import unitHeavySiegeIcon from "./assets/generated/lords-home/units/unit-heavy-siege-v1.png";
import unitInfantryIcon from "./assets/generated/lords-home/units/unit-infantry-v1.png";
import unitRangedIcon from "./assets/generated/lords-home/units/unit-ranged-v1.png";
import unitSpecialistIcon from "./assets/generated/lords-home/units/unit-specialist-v1.png";
import { LordMpHud, useLordMpRuntimeState } from "./LordMpHud";
import {
  adaptLordState,
  createLordUiState,
  getLordApiErrorMessage,
  getLordClientErrorMessage,
  getLordRuntimeMode,
  markLordUiStateOffline
} from "./lordState";
import type { LordBackendStatePayload, LordUiState } from "./lordState";
import {
  clearLordRuntimeSession,
  getLordRuntimeApiBaseUrl,
  getLordRuntimeCurrentPathWithoutSensitiveParams,
  getLordRuntimeLoginPath,
  isLordRuntimeAuthResponse,
  isLordRuntimeProductionOrigin,
  readLordRuntimeSession,
  stripLordRuntimeSensitiveQueryParams,
  withLordRuntimeQuery
} from "./lordRuntime";

type BattlePhase = "deployment" | "turn" | "timeout" | "result" | "garrison";
type BattleSideId = "north" | "river";
type BattleUnitClass = "infantry" | "guard" | "ranged" | "cavalry" | "heavy_siege" | "specialist";
type BattleActionMode = "move" | "attack" | "defend" | "ability";
type BattleCell = { row: number; col: number };

type BattleSide = {
  id: BattleSideId;
  name: string;
  domain: string;
  hp: number;
  maxHp: number;
  accent: "blue" | "red";
};

type BattleUnit = {
  id: string;
  side: BattleSideId;
  name: string;
  classId: BattleUnitClass;
  title: string;
  countAlive: number;
  countStart: number;
  attack: number;
  defense: number;
  hp: number;
  initiative: number;
  moveRange: number;
  attackRange: number;
  position: BattleCell | null;
  woundsOnFrontUnit: number;
  status?: "defending" | "destroyed" | "wounded";
  ability?: string;
  sourceId?: string;
  cardId?: string;
};

type BattleHeroTarget = {
  side: BattleSideId;
  serverSide: LordBattleServerSide;
  cell: BattleCell;
  name: string;
  hp: number;
  maxHp: number;
};

type BattleEffect =
  | { type: "move"; from: BattleCell; to: BattleCell }
  | { type: "ranged"; from: BattleCell; to: BattleCell }
  | { type: "melee"; from: BattleCell; to: BattleCell }
  | null;

type LordBattleServerSide = "attacker" | "defender";

type LordBattleStackPayload = Record<string, unknown> & {
  stack_id?: unknown;
  side?: unknown;
  domain_id?: unknown;
  source_type?: unknown;
  source_id?: unknown;
  card_id?: unknown;
  unit_class?: unknown;
  attack?: unknown;
  defense?: unknown;
  hp?: unknown;
  initiative?: unknown;
  move_range?: unknown;
  attack_range?: unknown;
  initial_count?: unknown;
  count_alive?: unknown;
  wounds_on_front_unit?: unknown;
  x?: unknown;
  y?: unknown;
  defended?: unknown;
};

type LordBattleLogEntryPayload = Record<string, unknown> & {
  round_number?: unknown;
  actor_side?: unknown;
  entry_type?: unknown;
  payload?: unknown;
};

type LordBattlePayload = Record<string, unknown> & {
  battle_id?: unknown;
  battle_type?: unknown;
  territory_id?: unknown;
  territory?: unknown;
  claim?: unknown;
  attacker_domain_id?: unknown;
  defender_domain_id?: unknown;
  defender_control?: unknown;
  status?: unknown;
  round_number?: unknown;
  active_side?: unknown;
  active_stack_id?: unknown;
  timeout_at?: unknown;
  timeout_counts?: unknown;
  board?: unknown;
  hero_hp?: unknown;
  initiative_order?: unknown;
  battle_log?: unknown;
  result?: unknown;
  deployment?: unknown;
  auto_resolve?: unknown;
  visibility?: unknown;
};

const boardRows = 6;
const boardCols = 5;
const isRecordValue = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toSafeString = (value: unknown) => (typeof value === "string" ? value.trim() : "");

const toSafeNumber = (value: unknown, fallback = 0) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : fallback;
};

const withLordBattleRuntimeQuery = (path: string) => {
  const routeParams = new URLSearchParams(window.location.search);
  const apiBaseUrl = getLordRuntimeApiBaseUrl(routeParams);
  const session = readLordRuntimeSession(routeParams);
  return withLordRuntimeQuery(path, apiBaseUrl, { lordId: session?.lordId });
};

const getLordBattleReturnPath = (routeParams: URLSearchParams) => {
  const returnTo = toSafeString(routeParams.get("return_to") || routeParams.get("return"));
  if (returnTo === "map" || returnTo.startsWith("/lords/map")) {
    return "/lords/map";
  }
  if (returnTo === "home" || returnTo.startsWith("/lords/home")) {
    return "/lords/home";
  }
  return "/lords/home";
};

const getLordBattleRuntimeConnection = () => {
  const routeParams = new URLSearchParams(window.location.search);
  const session = readLordRuntimeSession(routeParams);
  return {
    routeParams,
    mode: getLordRuntimeMode(routeParams),
    apiBaseUrl: getLordRuntimeApiBaseUrl(routeParams),
    lordId: session?.lordId ?? "",
    roleToken: session?.roleToken ?? ""
  };
};

const deploymentRows: Record<BattleSideId, number[]> = {
  river: [0, 1],
  north: [4, 5]
};

const battleCells = Array.from({ length: boardRows * boardCols }, (_, index) => ({
  row: Math.floor(index / boardCols),
  col: index % boardCols
}));

const cellKey = (cell: BattleCell) => `${cell.row}:${cell.col}`;
const isSameCell = (a: BattleCell | null, b: BattleCell | null) =>
  Boolean(a && b && a.row === b.row && a.col === b.col);
const getCellDistance = (a: BattleCell, b: BattleCell) => Math.abs(a.row - b.row) + Math.abs(a.col - b.col);

const battleSides: Record<BattleSideId, BattleSide> = {
  north: {
    id: "north",
    name: "Владыка Севера",
    domain: "Северный дом",
    hp: 52,
    maxHp: 64,
    accent: "blue"
  },
  river: {
    id: "river",
    name: "Леди Переправ",
    domain: "Речной дом",
    hp: 41,
    maxHp: 58,
    accent: "red"
  }
};

const unitClassLabel: Record<BattleUnitClass, string> = {
  infantry: "пехота",
  guard: "стража",
  ranged: "стрелки",
  cavalry: "конница",
  heavy_siege: "осада",
  specialist: "специалисты"
};

const unitClassIcon: Record<BattleUnitClass, string> = {
  infantry: unitInfantryIcon,
  guard: unitGuardIcon,
  ranged: unitRangedIcon,
  cavalry: unitCavalryIcon,
  heavy_siege: unitHeavySiegeIcon,
  specialist: unitSpecialistIcon
};

const serverSideToUiSide: Record<LordBattleServerSide, BattleSideId> = {
  attacker: "north",
  defender: "river"
};

const uiSideToServerSide: Record<BattleSideId, LordBattleServerSide> = {
  north: "attacker",
  river: "defender"
};

const domainNameById: Record<string, string> = {
  domain_north: "Северный дом",
  domain_river: "Речной дом",
  domain_forest: "Лесной дом",
  domain_hill: "Горный дом"
};

const battleSourceTypeLabel: Record<string, string> = {
  active_army: "полевая армия",
  garrison: "гарнизон",
  neutral_profile: "нейтральная охрана"
};

const serverBattleFinalStatuses = new Set(["finished", "needs_master_review", "cancelled", "closed", "resolved"]);

const normalizeServerSide = (value: unknown): LordBattleServerSide | null => {
  const side = toSafeString(value);
  return side === "attacker" || side === "defender" ? side : null;
};

const normalizeUnitClass = (value: unknown): BattleUnitClass => {
  const unitClass = toSafeString(value);
  if (
    unitClass === "infantry" ||
    unitClass === "guard" ||
    unitClass === "ranged" ||
    unitClass === "cavalry" ||
    unitClass === "heavy_siege" ||
    unitClass === "specialist"
  ) {
    return unitClass;
  }
  return "infantry";
};

const getDomainName = (domainId: unknown, fallback: string) => {
  const normalized = toSafeString(domainId);
  return domainNameById[normalized] ?? (normalized || fallback);
};

const getHeroHpForSide = (payload: LordBattlePayload, side: LordBattleServerSide) => {
  const heroHp = isRecordValue(payload.hero_hp) ? payload.hero_hp : {};
  const sideHp = isRecordValue(heroHp[side]) ? heroHp[side] : {};
  const maxHp = Math.max(1, Math.floor(toSafeNumber(sideHp.max, 1)));
  const currentHp = Math.max(0, Math.min(maxHp, Math.floor(toSafeNumber(sideHp.current, maxHp))));
  return { currentHp, maxHp };
};

const getBattleSidesFromPayload = (payload: LordBattlePayload): Record<BattleSideId, BattleSide> => {
  const attackerHp = getHeroHpForSide(payload, "attacker");
  const defenderHp = getHeroHpForSide(payload, "defender");
  const defenderDomainId = toSafeString(payload.defender_domain_id);

  return {
    north: {
      ...battleSides.north,
      name: getDomainName(payload.attacker_domain_id, "Атакующий дом"),
      domain: "Атакующий",
      hp: attackerHp.currentHp,
      maxHp: attackerHp.maxHp
    },
    river: {
      ...battleSides.river,
      name: defenderDomainId ? getDomainName(defenderDomainId, "Защитник") : "Нейтральная стража",
      domain: defenderDomainId ? "Защитник" : "Нейтральная территория",
      hp: defenderHp.currentHp,
      maxHp: defenderHp.maxHp
    }
  };
};

const getBattleStacks = (payload: LordBattlePayload): LordBattleStackPayload[] => {
  const board = isRecordValue(payload.board) ? payload.board : {};
  const stacks = board.stacks;
  return Array.isArray(stacks) ? stacks.filter(isRecordValue) : [];
};

const getBattleInitiativeOrder = (payload: LordBattlePayload) =>
  Array.isArray(payload.initiative_order) ? payload.initiative_order.map(toSafeString).filter(Boolean) : [];

const getBattleDeployment = (payload: LordBattlePayload | null) =>
  isRecordValue(payload?.deployment) ? payload?.deployment : {};

const getDeploymentHandForSide = (payload: LordBattlePayload, side: LordBattleServerSide) => {
  const deployment = getBattleDeployment(payload);
  const hand = isRecordValue(deployment.hand) ? deployment.hand : {};
  const sideHand = hand[side];
  return Array.isArray(sideHand) ? sideHand.filter(isRecordValue) : [];
};

const getDeploymentDeployedSourceIds = (payload: LordBattlePayload, side: LordBattleServerSide) => {
  const deployment = getBattleDeployment(payload);
  const deployed = isRecordValue(deployment.deployed) ? deployment.deployed : {};
  const sideDeployed = deployed[side];
  const entries = Array.isArray(sideDeployed) ? sideDeployed.filter(isRecordValue) : [];
  return new Set(entries.map((entry) => toSafeString(entry.source_id)).filter(Boolean));
};

const unitClassDisplayName: Record<BattleUnitClass, string> = {
  infantry: "Пехота",
  guard: "Стража",
  ranged: "Стрелки",
  cavalry: "Конница",
  heavy_siege: "Осадный расчет",
  specialist: "Специалисты"
};

const stackToBattleUnit = (stack: LordBattleStackPayload): BattleUnit | null => {
  const serverSide = normalizeServerSide(stack.side);
  const stackId = toSafeString(stack.stack_id);
  if (!serverSide || !stackId) {
    return null;
  }

  const classId = normalizeUnitClass(stack.unit_class);
  const countAlive = Math.max(0, Math.floor(toSafeNumber(stack.count_alive)));
  const countStart = Math.max(countAlive, Math.floor(toSafeNumber(stack.initial_count, countAlive)));
  const x = Math.floor(toSafeNumber(stack.x));
  const y = Math.floor(toSafeNumber(stack.y));
  const sourceType = toSafeString(stack.source_type);
  const cardId = toSafeString(stack.card_id);
  const sourceLabel = battleSourceTypeLabel[sourceType] ?? "боевой источник";

  return {
    id: stackId,
    side: serverSideToUiSide[serverSide],
    name: unitClassDisplayName[classId],
    classId,
    title: sourceLabel,
    countAlive,
    countStart,
    attack: Math.floor(toSafeNumber(stack.attack)),
    defense: Math.floor(toSafeNumber(stack.defense)),
    hp: Math.max(1, Math.floor(toSafeNumber(stack.hp, 1))),
    initiative: Math.floor(toSafeNumber(stack.initiative)),
    moveRange: Math.max(0, Math.floor(toSafeNumber(stack.move_range))),
    attackRange: Math.max(1, Math.floor(toSafeNumber(stack.attack_range, 1))),
    position: { row: y, col: x },
    woundsOnFrontUnit: Math.max(0, Math.floor(toSafeNumber(stack.wounds_on_front_unit))),
    status: countAlive <= 0 ? "destroyed" : stack.defended ? "defending" : toSafeNumber(stack.wounds_on_front_unit) > 0 ? "wounded" : undefined,
    sourceId: toSafeString(stack.source_id),
    cardId
  };
};

const deploymentItemToBattleUnit = (
  item: Record<string, unknown>,
  side: LordBattleServerSide
): BattleUnit | null => {
  const sourceId = toSafeString(item.source_id);
  const cardId = toSafeString(item.card_id);
  if (!sourceId && !cardId) {
    return null;
  }
  const classId = normalizeUnitClass(item.unit_class);
  const countAlive = Math.max(1, Math.floor(toSafeNumber(item.count, 1)));
  return {
    id: `reserve:${sourceId || cardId}`,
    side: serverSideToUiSide[side],
    name: unitClassDisplayName[classId],
    classId,
    title: "резерв для расстановки",
    countAlive,
    countStart: countAlive,
    attack: Math.floor(toSafeNumber(item.attack)),
    defense: Math.floor(toSafeNumber(item.defense)),
    hp: Math.max(1, Math.floor(toSafeNumber(item.hp, 1))),
    initiative: Math.floor(toSafeNumber(item.initiative)),
    moveRange: Math.max(0, Math.floor(toSafeNumber(item.move_range))),
    attackRange: Math.max(1, Math.floor(toSafeNumber(item.attack_range, 1))),
    position: null,
    woundsOnFrontUnit: 0,
    sourceId,
    cardId
  };
};

const adaptBattleUnitsFromPayload = (payload: LordBattlePayload, playerSide: LordBattleServerSide | null) => {
  const stackUnits = getBattleStacks(payload).map(stackToBattleUnit).filter((unit): unit is BattleUnit => Boolean(unit));
  if (getBattleStatus(payload) !== "deployment" || !playerSide) {
    return stackUnits;
  }
  const deployedSourceIds = getDeploymentDeployedSourceIds(payload, playerSide);
  const reserveUnits = getDeploymentHandForSide(payload, playerSide)
    .filter((item) => !deployedSourceIds.has(toSafeString(item.source_id)))
    .map((item) => deploymentItemToBattleUnit(item, playerSide))
    .filter((unit): unit is BattleUnit => Boolean(unit));
  return [...stackUnits, ...reserveUnits];
};

const getPlayerDomainIdFromStatePayload = (payload: LordBackendStatePayload | null | undefined) => {
  const domain = isRecordValue(payload?.domain) ? payload?.domain : {};
  const lord = isRecordValue(payload?.lord) ? payload?.lord : {};
  const movement = isRecordValue(payload?.movement) ? payload?.movement : {};
  return (
    toSafeString(domain.domain_id) ||
    toSafeString(lord.domain_id) ||
    toSafeString(movement.domain_id) ||
    toSafeString(localStorage.getItem("witcher_larp_domain_id"))
  );
};

const getPlayerSideForBattle = (payload: LordBattlePayload | null, playerDomainId: string): LordBattleServerSide | null => {
  if (!payload || !playerDomainId) {
    return null;
  }
  if (playerDomainId === toSafeString(payload.attacker_domain_id)) {
    return "attacker";
  }
  if (playerDomainId === toSafeString(payload.defender_domain_id)) {
    return "defender";
  }
  return null;
};

const getBattleStatus = (payload: LordBattlePayload | null) => toSafeString(payload?.status);

const getBattleTimerSeconds = (payload: LordBattlePayload | null) => {
  const timeoutAt = toSafeString(payload?.timeout_at);
  if (!timeoutAt || serverBattleFinalStatuses.has(getBattleStatus(payload))) {
    return 0;
  }
  const timestamp = Date.parse(timeoutAt);
  if (!Number.isFinite(timestamp)) {
    return 0;
  }
  return Math.max(0, Math.ceil((timestamp - Date.now()) / 1000));
};

const getBattleTimeoutCount = (payload: LordBattlePayload | null) => {
  const activeSide = normalizeServerSide(payload?.active_side);
  const timeoutCounts = isRecordValue(payload?.timeout_counts) ? payload?.timeout_counts : {};
  if (!activeSide) {
    return 0;
  }
  return Math.max(0, Math.floor(toSafeNumber(timeoutCounts[activeSide])));
};

const getDeploymentRowsForServerSide = (payload: LordBattlePayload | null, side: LordBattleServerSide | null) => {
  if (!payload || !side || getBattleStatus(payload) !== "deployment") {
    return new Set<number>();
  }
  const board = isRecordValue(payload.board) ? payload.board : {};
  const startLines = isRecordValue(board.start_lines) ? board.start_lines : {};
  const height = Math.max(1, Math.floor(toSafeNumber(board.height, boardRows)));
  const startLine = Math.floor(toSafeNumber(startLines[side], side === "attacker" ? 0 : height - 1));
  return side === "attacker"
    ? new Set([startLine, Math.min(height - 1, startLine + 1)])
    : new Set([startLine, Math.max(0, startLine - 1)]);
};

const getBattleLogLines = (payload: LordBattlePayload) => {
  const entries = Array.isArray(payload.battle_log) ? payload.battle_log.filter(isRecordValue) : [];
  return entries
    .slice(-8)
    .reverse()
    .map((entry) => formatBattleLogEntry(entry as LordBattleLogEntryPayload));
};

const formatBattleLogEntry = (entry: LordBattleLogEntryPayload) => {
  const type = toSafeString(entry.entry_type);
  const side = normalizeServerSide(entry.actor_side);
  const sideLabel = side === "attacker" ? "Атакующий" : side === "defender" ? "Защитник" : "Система";
  const payload = isRecordValue(entry.payload) ? entry.payload : {};
  const stackId = toSafeString(payload.stack_id);
  const targetStackId = toSafeString(payload.target_stack_id);
  const casualties = isRecordValue(payload.casualties) ? Math.floor(toSafeNumber(payload.casualties.killed)) : 0;

  if (type === "lord_battle_started") return "Бой открыт сервером.";
  if (type === "deployment_recorded") return "Боевые пачки выставлены на поле.";
  if (type === "unit_moved") return `${sideLabel}: ${stackId || "отряд"} сменил позицию.`;
  if (type === "unit_attacked" || type === "ai_attack") {
    return `${sideLabel}: ${stackId || "отряд"} атаковал ${targetStackId || "цель"}${casualties ? `, потери ${casualties}` : ""}.`;
  }
  if (type === "hero_attacked") return `${sideLabel}: удар по ставке героя.`;
  if (type === "unit_defended" || type === "unit_auto_defended") return `${sideLabel}: ${stackId || "отряд"} занял защиту.`;
  if (type === "lord_battle_turn_timeout") return `${sideLabel}: ход истек по таймеру.`;
  if (type === "master_takeover") return "Мастер забрал ход нейтральной стороны.";
  if (type === "lord_battle_finished") return "Бой завершен, результат записан сервером.";
  return `${sideLabel}: ${type || "обновление боя"}.`;
};

const getBattleVictoryLabel = (payload: LordBattlePayload | null, sides: Record<BattleSideId, BattleSide>) => {
  const result = isRecordValue(payload?.result) ? payload?.result : {};
  const winnerSide = normalizeServerSide(result.winner_side);
  if (!winnerSide) {
    return "Бой завершен";
  }
  return `Победа ${sides[serverSideToUiSide[winnerSide]].name}`;
};

const getServerBattlePhaseLabel = (payload: LordBattlePayload | null, sides: Record<BattleSideId, BattleSide>) => {
  if (!payload) {
    return "загрузка";
  }
  if (serverBattleFinalStatuses.has(getBattleStatus(payload))) {
    return "завершен";
  }
  const activeSide = normalizeServerSide(payload.active_side);
  if (!activeSide) {
    return "ожидает хода";
  }
  const activeUiSide = serverSideToUiSide[activeSide];
  return `ходит ${sides[activeUiSide].name}`;
};

const getBattleActionSummary = (actionType: string, result: unknown) => {
  const payload = isRecordValue(result) ? result : {};
  if (actionType === "move") return "Отряд перемещен. Ход записан сервером.";
  if (actionType === "defend" || actionType === "skip") return "Отряд занял защиту. Ход записан сервером.";
  if (actionType === "timeout") return "Таймаут записан сервером.";
  if (actionType === "auto_resolve") return "Авторасчет записан сервером.";
  if (actionType === "surrender") return "Сдача боя записана сервером.";
  if (actionType === "attack") {
    const casualties = isRecordValue(payload.casualties) ? Math.floor(toSafeNumber(payload.casualties.killed)) : 0;
    return casualties > 0 ? `Удар записан сервером. Потери цели: ${casualties}.` : "Удар записан сервером.";
  }
  return "Ход записан сервером.";
};

const getAutoResolveLabel = (payload: LordBattlePayload | null) => {
  const autoResolve = isRecordValue(payload?.auto_resolve) ? payload?.auto_resolve : {};
  return toSafeString(autoResolve.label) || "Авторасчет";
};

const getBattleResultRecord = (payload: LordBattlePayload | null) =>
  isRecordValue(payload?.result) ? payload?.result : {};

const getBattleResultTitle = (
  payload: LordBattlePayload | null,
  sides: Record<BattleSideId, BattleSide>,
  playerSide: LordBattleServerSide | null
) => {
  const result = getBattleResultRecord(payload);
  const winnerSide = normalizeServerSide(result.winner_side);
  if (!winnerSide) {
    return "Бой завершен";
  }
  const winnerLabel = sides[serverSideToUiSide[winnerSide]].name;
  if (playerSide && winnerSide === playerSide) {
    return `Победа: ${winnerLabel}`;
  }
  if (playerSide) {
    return `Поражение: победил ${winnerLabel}`;
  }
  return `Победил ${winnerLabel}`;
};

const getBattleResultOutcomeLabel = (
  payload: LordBattlePayload | null,
  playerSide: LordBattleServerSide | null
) => {
  const result = getBattleResultRecord(payload);
  const winnerSide = normalizeServerSide(result.winner_side);
  if (!winnerSide) {
    return "Бой завершен";
  }
  if (playerSide && winnerSide !== playerSide) {
    return "Поражение";
  }
  return "Победа";
};

const getBattleResultDetail = (payload: LordBattlePayload | null) => {
  const result = getBattleResultRecord(payload);
  const outcome = toSafeString(result.outcome);
  const reason = toSafeString(result.reason);
  if (outcome === "auto_resolve") {
    return reason === "manual_auto_resolve_confirmed"
      ? "Авторасчет подтвержден обеими сторонами."
      : "Авторасчет завершил бой.";
  }
  if (outcome === "hero_hp") return "Ставка лорда потеряла все HP.";
  if (outcome === "unit_wipe") return "У одной стороны не осталось боевых отрядов.";
  if (outcome === "surrender") return "Одна сторона сдалась.";
  if (outcome === "deployment_no_units") return "После расстановки у стороны не осталось выставленных отрядов.";
  return "Итог записан сервером.";
};

const getBattleCaptureText = (payload: LordBattlePayload | null) => {
  const result = getBattleResultRecord(payload);
  const capture = isRecordValue(result.capture) ? result.capture : {};
  const status = toSafeString(capture.status);
  if (status === "capture_pending_garrison") {
    return "Территория требует гарнизон: вернитесь на карту или в дом лорда и оставьте отряд.";
  }
  if (status === "captured") return "Территория захвачена.";
  if (status === "defended") return "Территория удержана защитником.";
  if (status) return `Статус территории: ${status}.`;
  return "Территориальный результат не требуется.";
};

const getTerritoryIdFromRecord = (value: unknown) =>
  isRecordValue(value) ? toSafeString(value.territory_id) || toSafeString(value.target_territory_id) : "";

const getBattleTerritoryId = (payload: LordBattlePayload | null, routeParams?: URLSearchParams) => {
  const result = getBattleResultRecord(payload);
  const capture = isRecordValue(result.capture) ? result.capture : {};
  return (
    toSafeString(payload?.territory_id) ||
    getTerritoryIdFromRecord(payload?.territory) ||
    getTerritoryIdFromRecord(payload?.claim) ||
    getTerritoryIdFromRecord(capture) ||
    getTerritoryIdFromRecord(result.territory) ||
    getTerritoryIdFromRecord(result.claim) ||
    toSafeString(routeParams?.get("territory_id")) ||
    toSafeString(routeParams?.get("target_territory_id"))
  );
};

const getBattleTerritoryHomePath = (payload: LordBattlePayload | null, routeParams?: URLSearchParams) => {
  const territoryId = getBattleTerritoryId(payload, routeParams);
  return territoryId ? `/lords/home?territory_id=${encodeURIComponent(territoryId)}` : "/lords/home";
};

const initialUnits: BattleUnit[] = [
  {
    id: "north-rangers",
    side: "north",
    name: "Лучники Серого кряжа",
    classId: "ranged",
    title: "раненый стек, линия огня",
    countAlive: 68,
    countStart: 80,
    attack: 6,
    defense: 2,
    hp: 4,
    initiative: 7,
    moveRange: 1,
    attackRange: 4,
    position: { row: 4, col: 2 },
    woundsOnFrontUnit: 2,
    status: "wounded"
  },
  {
    id: "north-cavalry",
    side: "north",
    name: "Рысья конница",
    classId: "cavalry",
    title: "быстрый фланг",
    countAlive: 24,
    countStart: 24,
    attack: 8,
    defense: 3,
    hp: 6,
    initiative: 9,
    moveRange: 3,
    attackRange: 1,
    position: { row: 5, col: 0 },
    woundsOnFrontUnit: 0
  },
  {
    id: "north-guard",
    side: "north",
    name: "Щитовая стража",
    classId: "guard",
    title: "высокая защита",
    countAlive: 42,
    countStart: 42,
    attack: 4,
    defense: 7,
    hp: 7,
    initiative: 3,
    moveRange: 1,
    attackRange: 1,
    position: { row: 4, col: 4 },
    woundsOnFrontUnit: 0,
    status: "defending"
  },
  {
    id: "north-siege",
    side: "north",
    name: "Тяжелая баллиста",
    classId: "heavy_siege",
    title: "медленная осада",
    countAlive: 6,
    countStart: 6,
    attack: 12,
    defense: 3,
    hp: 10,
    initiative: 1,
    moveRange: 1,
    attackRange: 5,
    position: { row: 5, col: 4 },
    woundsOnFrontUnit: 0
  },
  {
    id: "north-infantry",
    side: "north",
    name: "Мечники заставы",
    classId: "infantry",
    title: "линейная пехота",
    countAlive: 70,
    countStart: 70,
    attack: 5,
    defense: 4,
    hp: 5,
    initiative: 5,
    moveRange: 2,
    attackRange: 1,
    position: { row: 5, col: 2 },
    woundsOnFrontUnit: 0
  },
  {
    id: "north-sappers",
    side: "north",
    name: "Саперы у ворот",
    classId: "specialist",
    title: "резерв для выставления",
    countAlive: 18,
    countStart: 18,
    attack: 5,
    defense: 4,
    hp: 5,
    initiative: 6,
    moveRange: 2,
    attackRange: 2,
    position: null,
    woundsOnFrontUnit: 0,
    ability: "Разметить проход"
  },
  {
    id: "river-guard",
    side: "river",
    name: "Стража переправы",
    classId: "guard",
    title: "щитовой центр",
    countAlive: 55,
    countStart: 55,
    attack: 4,
    defense: 8,
    hp: 7,
    initiative: 4,
    moveRange: 1,
    attackRange: 1,
    position: { row: 1, col: 2 },
    woundsOnFrontUnit: 0
  },
  {
    id: "river-rangers",
    side: "river",
    name: "Арбалеты моста",
    classId: "ranged",
    title: "дальняя угроза",
    countAlive: 44,
    countStart: 44,
    attack: 7,
    defense: 2,
    hp: 4,
    initiative: 6,
    moveRange: 1,
    attackRange: 4,
    position: { row: 1, col: 4 },
    woundsOnFrontUnit: 1
  },
  {
    id: "river-cavalry",
    side: "river",
    name: "Багряные всадники",
    classId: "cavalry",
    title: "контратака",
    countAlive: 18,
    countStart: 18,
    attack: 8,
    defense: 3,
    hp: 6,
    initiative: 8,
    moveRange: 3,
    attackRange: 1,
    position: { row: 0, col: 0 },
    woundsOnFrontUnit: 0
  },
  {
    id: "river-siege",
    side: "river",
    name: "Камнеметная команда",
    classId: "heavy_siege",
    title: "осадный медляк",
    countAlive: 5,
    countStart: 5,
    attack: 11,
    defense: 3,
    hp: 10,
    initiative: 1,
    moveRange: 1,
    attackRange: 5,
    position: { row: 0, col: 3 },
    woundsOnFrontUnit: 0
  },
  {
    id: "river-infantry",
    side: "river",
    name: "Копейщики пристани",
    classId: "infantry",
    title: "линейная пехота",
    countAlive: 62,
    countStart: 62,
    attack: 5,
    defense: 4,
    hp: 5,
    initiative: 5,
    moveRange: 2,
    attackRange: 1,
    position: { row: 1, col: 0 },
    woundsOnFrontUnit: 0
  },
  {
    id: "river-banner",
    side: "river",
    name: "Знаменосцы речников",
    classId: "specialist",
    title: "модификатор защиты",
    countAlive: 12,
    countStart: 12,
    attack: 3,
    defense: 5,
    hp: 5,
    initiative: 7,
    moveRange: 2,
    attackRange: 2,
    position: { row: 0, col: 2 },
    woundsOnFrontUnit: 0,
    ability: "Держать строй"
  }
];

const initialLog = [
  "Север открыл бой за Речные ворота.",
  "Стража переправы держит центральную линию.",
  "Лучники Серого кряжа ранены, но сохраняют прямую линию огня.",
  "Мастер отмечает: повторный таймаут переведет бой в авторасчет."
];

const createInitialUnits = () =>
  initialUnits.map((unit) => ({
    ...unit,
    position: unit.position ? { ...unit.position } : null
  }));

const phaseLabel: Record<BattlePhase, string> = {
  deployment: "выставление",
  turn: "ходит Север",
  timeout: "таймаут",
  result: "победа Севера",
  garrison: "оставить гарнизон"
};

const getUnitAtCell = (units: BattleUnit[], cell: BattleCell) =>
  units.find((unit) => unit.position && unit.status !== "destroyed" && isSameCell(unit.position, cell));

const hasStraightLineOfSight = (units: BattleUnit[], from: BattleCell, to: BattleCell, attackerId: string) => {
  if (from.row !== to.row && from.col !== to.col) {
    return false;
  }

  const rowStep = Math.sign(to.row - from.row);
  const colStep = Math.sign(to.col - from.col);
  let row = from.row + rowStep;
  let col = from.col + colStep;

  while (row !== to.row || col !== to.col) {
    const blocker = units.find(
      (unit) => unit.id !== attackerId && unit.position && unit.status !== "destroyed" && unit.position.row === row && unit.position.col === col
    );

    if (blocker) {
      return false;
    }

    row += rowStep;
    col += colStep;
  }

  return true;
};

const getLegalMoves = (unit: BattleUnit | undefined, units: BattleUnit[]) => {
  if (!unit?.position || unit.status === "destroyed") {
    return new Set<string>();
  }

  return new Set(
    battleCells
      .filter((cell) => {
        const distance = getCellDistance(unit.position as BattleCell, cell);
        return distance > 0 && distance <= unit.moveRange && !getUnitAtCell(units, cell);
      })
      .map(cellKey)
  );
};

const getLegalAttacks = (unit: BattleUnit | undefined, units: BattleUnit[]) => {
  if (!unit?.position || unit.status === "destroyed") {
    return new Set<string>();
  }

  return new Set(
    units
      .filter((target) => {
        if (target.side === unit.side || target.status === "destroyed" || !target.position || !unit.position) {
          return false;
        }

        const distance = getCellDistance(unit.position, target.position);
        if (unit.attackRange <= 1) {
          return distance === 1;
        }

        return distance <= unit.attackRange && hasStraightLineOfSight(units, unit.position, target.position, unit.id);
      })
      .map((target) => cellKey(target.position as BattleCell))
  );
};

const getHeroTargetsFromPayload = (
  payload: LordBattlePayload | null,
  sides: Record<BattleSideId, BattleSide>
): BattleHeroTarget[] => {
  const board = isRecordValue(payload?.board) ? payload?.board : {};
  const heroCells = isRecordValue(board.hero_cells) ? board.hero_cells : {};
  return (["attacker", "defender"] as LordBattleServerSide[])
    .map((serverSide) => {
      const rawCell = isRecordValue(heroCells[serverSide]) ? heroCells[serverSide] : null;
      if (!rawCell) {
        return null;
      }
      const side = serverSideToUiSide[serverSide];
      return {
        side,
        serverSide,
        cell: {
          row: Math.floor(toSafeNumber(rawCell.y)),
          col: Math.floor(toSafeNumber(rawCell.x))
        },
        name: sides[side].name,
        hp: sides[side].hp,
        maxHp: sides[side].maxHp
      };
    })
    .filter((target): target is BattleHeroTarget => Boolean(target));
};

const getLegalHeroAttacks = (
  unit: BattleUnit | undefined,
  units: BattleUnit[],
  heroTargets: BattleHeroTarget[]
) => {
  if (!unit?.position || unit.status === "destroyed") {
    return new Set<string>();
  }
  return new Set(
    heroTargets
      .filter((target) => {
        if (target.side === unit.side || !unit.position) {
          return false;
        }
        const distance = getCellDistance(unit.position, target.cell);
        return distance <= unit.attackRange && hasStraightLineOfSight(units, unit.position, target.cell, unit.id);
      })
      .map((target) => cellKey(target.cell))
  );
};

const getLineOfSightTarget = (unit: BattleUnit | undefined, units: BattleUnit[]) => {
  if (!unit?.position || unit.attackRange <= 1) {
    return null;
  }

  return (
    units.find(
      (target) =>
        target.side !== unit.side &&
        target.status !== "destroyed" &&
        target.position &&
        unit.position &&
        getCellDistance(unit.position, target.position) <= unit.attackRange &&
        hasStraightLineOfSight(units, unit.position, target.position, unit.id)
    ) ?? null
  );
};

const formatTimer = (seconds: number) => {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`;
};

function LordBattleScreen() {
  stripLordRuntimeSensitiveQueryParams();
  const prefersReducedMotion = useReducedMotion();
  const battleConnection = getLordBattleRuntimeConnection();
  const useDemoState = battleConnection.mode !== "production";
  const returnPath = getLordBattleReturnPath(battleConnection.routeParams);
  const loginRedirectPath = getLordRuntimeLoginPath(
    battleConnection.apiBaseUrl,
    getLordRuntimeCurrentPathWithoutSensitiveParams()
  );
  const requestedBattleId = battleConnection.routeParams.get("battle_id") || battleConnection.routeParams.get("battle") || "";
  const [lordUiState, setLordUiState] = useState<LordUiState>(() =>
    createLordUiState(useDemoState ? "demo" : "loading", { mode: battleConnection.mode })
  );
  const [battleGateStatus, setBattleGateStatus] = useState("");
  const [serverBattle, setServerBattle] = useState<LordBattlePayload | null>(null);
  const [isBattleLoading, setIsBattleLoading] = useState(!useDemoState);
  const [playerDomainId, setPlayerDomainId] = useState(() => toSafeString(localStorage.getItem("witcher_larp_domain_id")));
  const [battleSideViews, setBattleSideViews] = useState<Record<BattleSideId, BattleSide>>(battleSides);
  const [activeStackId, setActiveStackId] = useState("");
  const [initiativeOrder, setInitiativeOrder] = useState<string[]>([]);
  const [isBattleActionPending, setIsBattleActionPending] = useState(false);
  const battleMpState = useLordMpRuntimeState();
  const [isBoardFocused, setIsBoardFocused] = useState(false);
  const isDebugGrid =
    typeof window !== "undefined" && new URLSearchParams(window.location.search).get("debugGrid") === "1";
  const [phase, setPhase] = useState<BattlePhase>("deployment");
  const [timerSeconds, setTimerSeconds] = useState(60);
  const [round, setRound] = useState(2);
  const [units, setUnits] = useState(createInitialUnits);
  const [selectedUnitId, setSelectedUnitId] = useState("north-rangers");
  const [selectedReserveId, setSelectedReserveId] = useState("north-sappers");
  const [actionMode, setActionMode] = useState<BattleActionMode>("attack");
  const [battleLog, setBattleLog] = useState(initialLog);
  const [timeoutCount, setTimeoutCount] = useState(0);
  const [lastLosses, setLastLosses] = useState("потерь после последнего удара нет");
  const [battleEffect, setBattleEffect] = useState<BattleEffect>(null);
  const [damageMarker, setDamageMarker] = useState<{ cell: BattleCell; label: string } | null>(null);
  const [selectedGarrisonIds, setSelectedGarrisonIds] = useState<string[]>(["north-guard"]);

  const isProductionBattle = !useDemoState && Boolean(serverBattle);
  const currentBattleId = toSafeString(serverBattle?.battle_id) || lordUiState.activeBattle.battleId || requestedBattleId;
  const playerServerSide = getPlayerSideForBattle(serverBattle, playerDomainId);
  const playerUiSide = playerServerSide ? serverSideToUiSide[playerServerSide] : "north";
  const activeServerSide = normalizeServerSide(serverBattle?.active_side);
  const selectedUnit = units.find((unit) => unit.id === selectedUnitId);
  const selectedServerSide = selectedUnit ? uiSideToServerSide[selectedUnit.side] : null;
  const selectedReserve = units.find((unit) => unit.id === selectedReserveId);
  const initiativeQueue = useMemo(
    () => {
      const aliveUnits = units.filter((unit) => unit.status !== "destroyed" && unit.position);
      if (initiativeOrder.length > 0) {
        const orderIndex = new Map(initiativeOrder.map((id, index) => [id, index]));
        return aliveUnits.sort(
          (left, right) =>
            (orderIndex.get(left.id) ?? Number.MAX_SAFE_INTEGER) -
              (orderIndex.get(right.id) ?? Number.MAX_SAFE_INTEGER) ||
            right.initiative - left.initiative ||
            right.attack - left.attack
        );
      }
      return aliveUnits.sort((left, right) => right.initiative - left.initiative || right.attack - left.attack);
    },
    [initiativeOrder, units]
  );
  const reserveUnits = units.filter((unit) => unit.side === playerUiSide && !unit.position && unit.status !== "destroyed");
  const deploymentRowSet = useMemo(
    () => getDeploymentRowsForServerSide(serverBattle, playerServerSide),
    [playerServerSide, serverBattle]
  );
  const serverHeroCellKeys = useMemo(() => {
    const board = isRecordValue(serverBattle?.board) ? serverBattle?.board : {};
    const heroCells = isRecordValue(board.hero_cells) ? Object.values(board.hero_cells).filter(isRecordValue) : [];
    return new Set(heroCells.map((cell) => cellKey({ row: Math.floor(toSafeNumber(cell.y)), col: Math.floor(toSafeNumber(cell.x)) })));
  }, [serverBattle]);
  const legalMoveKeys = useMemo(() => {
    const keys = getLegalMoves(selectedUnit, units);
    if (isProductionBattle) {
      serverHeroCellKeys.forEach((key) => keys.delete(key));
    }
    return keys;
  }, [isProductionBattle, selectedUnit, serverHeroCellKeys, units]);
  const heroTargets = useMemo(
    () => getHeroTargetsFromPayload(serverBattle, battleSideViews),
    [battleSideViews, serverBattle]
  );
  const heroTargetByCellKey = useMemo(
    () => new Map(heroTargets.map((target) => [cellKey(target.cell), target])),
    [heroTargets]
  );
  const legalHeroAttackKeys = useMemo(
    () => getLegalHeroAttacks(selectedUnit, units, heroTargets),
    [heroTargets, selectedUnit, units]
  );
  const legalAttackKeys = useMemo(() => {
    const keys = getLegalAttacks(selectedUnit, units);
    legalHeroAttackKeys.forEach((key) => keys.add(key));
    return keys;
  }, [legalHeroAttackKeys, selectedUnit, units]);
  const lineOfSightTarget = useMemo(() => getLineOfSightTarget(selectedUnit, units), [selectedUnit, units]);
  const livingNorthUnits = units.filter((unit) => unit.side === "north" && unit.status !== "destroyed" && unit.countAlive > 0);
  const canFinishGarrison = selectedGarrisonIds.length > 0 && selectedGarrisonIds.length <= 3;
  const canActWithSelectedUnit =
    useDemoState ||
    (Boolean(serverBattle) &&
      getBattleStatus(serverBattle) === "active" &&
      Boolean(playerServerSide) &&
      playerServerSide === activeServerSide &&
      selectedServerSide === activeServerSide &&
      selectedUnit?.id === activeStackId &&
      !isBattleActionPending);
  const battleVictoryLabel = useDemoState ? "Победа Севера" : getBattleVictoryLabel(serverBattle, battleSideViews);
  const autoResolveLabel = getAutoResolveLabel(serverBattle);
  const battleResultOutcomeLabel = useDemoState ? "Победа" : getBattleResultOutcomeLabel(serverBattle, playerServerSide);
  const battleTerritoryHomePath = useDemoState
    ? "/lords/home?demo=1&territory=river-gate"
    : getBattleTerritoryHomePath(serverBattle, battleConnection.routeParams);

  const addLog = (message: string) => {
    setBattleLog((current) => [message, ...current].slice(0, 8));
  };

  const applyServerBattlePayload = (payload: LordBattlePayload, effectivePlayerDomainId = playerDomainId) => {
    const nextSides = getBattleSidesFromPayload(payload);
    const nextInitiativeOrder = getBattleInitiativeOrder(payload);
    const nextActiveStackId = toSafeString(payload.active_stack_id);
    const isFinal = serverBattleFinalStatuses.has(getBattleStatus(payload));
    const isDeployment = getBattleStatus(payload) === "deployment";
    const nextPlayerSide = getPlayerSideForBattle(payload, effectivePlayerDomainId);
    const nextUnits = adaptBattleUnitsFromPayload(payload, nextPlayerSide);
    const nextSelectedUnitId =
      nextActiveStackId ||
      nextUnits.find((unit) => nextPlayerSide && unit.side === serverSideToUiSide[nextPlayerSide] && unit.status !== "destroyed")?.id ||
      nextUnits.find((unit) => unit.status !== "destroyed")?.id ||
      "";
    const nextSelectedReserveId =
      isDeployment
        ? nextUnits.find((unit) => nextPlayerSide && unit.side === serverSideToUiSide[nextPlayerSide] && !unit.position)?.id || ""
        : "";

    setServerBattle(payload);
    setBattleSideViews(nextSides);
    setUnits(nextUnits);
    setInitiativeOrder(nextInitiativeOrder);
    setActiveStackId(nextActiveStackId);
    setSelectedUnitId((current) =>
      current && nextUnits.some((unit) => unit.id === current && unit.status !== "destroyed")
        ? nextActiveStackId || current
        : nextSelectedUnitId
    );
    setSelectedReserveId(nextSelectedReserveId);
    setPhase(isFinal ? "result" : isDeployment ? "deployment" : "turn");
    setRound(Math.max(1, Math.floor(toSafeNumber(payload.round_number, 1))));
    setTimerSeconds(getBattleTimerSeconds(payload));
    setTimeoutCount(getBattleTimeoutCount(payload));
    setBattleLog(getBattleLogLines(payload));
    setLastLosses(
      isFinal
        ? getBattleVictoryLabel(payload, nextSides)
        : isDeployment
          ? "Расставьте отряды и подтвердите готовность."
          : nextActiveStackId
            ? "Выберите действие для активного отряда."
            : "Сервер ожидает следующий ход."
    );
    setBattleGateStatus("");
    setIsBattleLoading(false);
  };

  const submitServerBattleAction = async (
    actionType: string,
    payload: Record<string, unknown> = {},
    actorSide: LordBattleServerSide | null = selectedServerSide ?? activeServerSide
  ) => {
    if (!serverBattle || !currentBattleId || !battleConnection.roleToken || !actorSide) {
      const message = "Боевой приказ сейчас недоступен. Обновите экран или позовите мастера.";
      setLastLosses(message);
      addLog(message);
      return;
    }

    setIsBattleActionPending(true);
    try {
      const headers: Record<string, string> = {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role-Token": battleConnection.roleToken
      };
      const response = await fetch(
        `${battleConnection.apiBaseUrl}/api/lord-battles/${encodeURIComponent(currentBattleId)}/actions`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            action_id: `lord-ui-${currentBattleId}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            action_type: actionType,
            actor_side: actorSide,
            payload,
            source: "lord_battle_ui"
          })
        }
      );
      const actionPayload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(getLordApiErrorMessage(actionPayload, "Боевой приказ не принят сервером."));
      }

      const nextBattle = isRecordValue(actionPayload) && isRecordValue(actionPayload.battle) ? actionPayload.battle : null;
      if (nextBattle) {
        applyServerBattlePayload(nextBattle as LordBattlePayload);
      } else {
        const refreshResponse = await fetch(
          `${battleConnection.apiBaseUrl}/api/lord-battles/${encodeURIComponent(currentBattleId)}`,
          { headers }
        );
        const refreshPayload: unknown = await refreshResponse.json().catch(() => null);
        if (!refreshResponse.ok) {
          throw new Error(getLordApiErrorMessage(refreshPayload, "Боевой стол не обновился."));
        }
        applyServerBattlePayload(refreshPayload as LordBattlePayload);
      }
      const summary = getBattleActionSummary(actionType, actionPayload);
      setLastLosses(summary);
      addLog(summary);
    } catch (error) {
      const message = getLordClientErrorMessage(error, "Боевой приказ не принят сервером.");
      setLastLosses(message);
      addLog(message);
    } finally {
      setIsBattleActionPending(false);
    }
  };

  useEffect(() => {
    const focusTimer = window.setTimeout(() => {
      setIsBoardFocused(true);
    }, prefersReducedMotion ? 120 : 950);

    return () => window.clearTimeout(focusTimer);
  }, [prefersReducedMotion]);

  useEffect(() => {
    if (phase !== "deployment" && phase !== "turn" && phase !== "timeout") {
      return;
    }

    const tick = window.setInterval(() => {
      setTimerSeconds((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(tick);
  }, [phase]);

  useEffect(() => {
    if (phase === "timeout") {
      setTimerSeconds(9);
    }
  }, [phase]);

  useEffect(() => {
    if (useDemoState && phase === "turn" && timerSeconds === 0) {
      triggerTimeout();
    }
  }, [phase, timerSeconds, useDemoState]);

  useEffect(() => {
    if (
      useDemoState ||
      phase !== "deployment" ||
      timerSeconds > 0 ||
      !playerServerSide ||
      isBattleActionPending
    ) {
      return;
    }
    void submitServerBattleAction("ready", {}, playerServerSide);
  }, [isBattleActionPending, phase, playerServerSide, timerSeconds, useDemoState]);

  useEffect(() => {
    if (useDemoState) {
      setServerBattle(null);
      setBattleSideViews(battleSides);
      setIsBattleLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const loadProductionBattle = async () => {
      setIsBattleLoading(true);
      if (!battleConnection.lordId || !battleConnection.roleToken) {
        clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
        window.location.replace(loginRedirectPath);
        setLordUiState(createLordUiState("offline", { mode: "production" }));
        setBattleGateStatus("Боевой экран открыт только для чтения: нет подтвержденного входа лорда.");
        setServerBattle(null);
        setIsBattleLoading(false);
        return;
      }

      try {
        const headers: Record<string, string> = {
          Accept: "application/json",
          "X-Role-Token": battleConnection.roleToken
        };
        const response = await fetch(
          `${battleConnection.apiBaseUrl}/api/lords/${encodeURIComponent(battleConnection.lordId)}/summary`,
          { headers, signal: controller.signal }
        );
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          if (isLordRuntimeAuthResponse(response)) {
            clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
            window.location.replace(loginRedirectPath);
            return;
          }
          throw new Error(getLordApiErrorMessage(payload, "Боевой экран не получил состояние лорда."));
        }

        const statePayload = payload as LordBackendStatePayload;
        const adaptedState = adaptLordState(statePayload, { mode: "production" });
        const nextPlayerDomainId = getPlayerDomainIdFromStatePayload(statePayload);
        if (nextPlayerDomainId) {
          localStorage.setItem("witcher_larp_domain_id", nextPlayerDomainId);
          setPlayerDomainId(nextPlayerDomainId);
        }
        setLordUiState(adaptedState);
        const battleId = requestedBattleId || adaptedState.activeBattle.battleId;
        if (!battleId) {
          setServerBattle(null);
          setBattleGateStatus("Активного боя сейчас нет.");
          setIsBattleLoading(false);
          return;
        }

        const battleResponse = await fetch(
          `${battleConnection.apiBaseUrl}/api/lord-battles/${encodeURIComponent(battleId)}`,
          { headers, signal: controller.signal }
        );
        const battlePayload: unknown = await battleResponse.json().catch(() => null);
        if (!battleResponse.ok) {
          if (isLordRuntimeAuthResponse(battleResponse)) {
            clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
            window.location.replace(loginRedirectPath);
            return;
          }
          throw new Error(getLordApiErrorMessage(battlePayload, "Боевой стол сейчас недоступен."));
        }

        applyServerBattlePayload(battlePayload as LordBattlePayload, nextPlayerDomainId || playerDomainId);
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setLordUiState((current) => markLordUiStateOffline(current));
        setServerBattle(null);
        setIsBattleLoading(false);
        setBattleGateStatus(getLordClientErrorMessage(error, "Связь с боевой канцелярией потеряна."));
      }
    };

    void loadProductionBattle();
    return () => controller.abort();
  }, [
    battleConnection.apiBaseUrl,
    battleConnection.lordId,
    battleConnection.mode,
    battleConnection.roleToken,
    loginRedirectPath,
    playerDomainId,
    requestedBattleId,
    useDemoState
  ]);

  useEffect(() => {
    if (useDemoState || !currentBattleId || !battleConnection.roleToken) {
      return undefined;
    }
    const intervalId = window.setInterval(async () => {
      if (isBattleActionPending) {
        return;
      }
      try {
        const response = await fetch(
          `${battleConnection.apiBaseUrl}/api/lord-battles/${encodeURIComponent(currentBattleId)}`,
          {
            headers: {
              Accept: "application/json",
              "X-Role-Token": battleConnection.roleToken
            }
          }
        );
        const payload: unknown = await response.json().catch(() => null);
        if (response.ok) {
          applyServerBattlePayload(payload as LordBattlePayload);
        } else if (isLordRuntimeAuthResponse(response)) {
          clearLordRuntimeSession({ clearApiBaseUrl: isLordRuntimeProductionOrigin() });
          window.location.replace(loginRedirectPath);
        }
      } catch {
        // Keep the last rendered battle state if the local server is briefly unreachable.
      }
    }, 3_000);
    return () => window.clearInterval(intervalId);
  }, [
    battleConnection.apiBaseUrl,
    battleConnection.roleToken,
    currentBattleId,
    isBattleActionPending,
    loginRedirectPath,
    useDemoState
  ]);

  const startTurnPhase = () => {
    if (isProductionBattle) {
      return;
    }
    setPhase("turn");
    setTimerSeconds(42);
    setSelectedUnitId("north-rangers");
    setSelectedReserveId("");
    setActionMode("attack");
    addLog("Север завершил выставление. Очередь инициативы поднята на стол.");
  };

  const confirmDeploymentReady = () => {
    if (isProductionBattle) {
      if (playerServerSide && !isBattleActionPending) {
        void submitServerBattleAction("ready", {}, playerServerSide);
      }
      return;
    }
    startTurnPhase();
  };

  const triggerTimeout = () => {
    if (isProductionBattle) {
      if (activeServerSide && playerServerSide === activeServerSide) {
        void submitServerBattleAction("timeout", {}, activeServerSide);
        return;
      }
      const message = "Таймаут может записать только активная сторона боя.";
      setLastLosses(message);
      addLog(message);
      return;
    }

    setPhase("timeout");
    setTimeoutCount((current) => Math.max(1, current + 1));
    setTimerSeconds(9);
    addLog("Таймер сорвался. Активный отряд получит автозащиту, если ход не будет решен.");
  };

  const moveUnit = (targetCell: BattleCell) => {
    if (!selectedUnit?.position) {
      return;
    }

    if (isProductionBattle) {
      if (!canActWithSelectedUnit || !selectedServerSide) {
        const message = "Сейчас ходит другая сторона или выбран не активный отряд.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      setBattleEffect({ type: "move", from: selectedUnit.position, to: targetCell });
      window.setTimeout(() => setBattleEffect(null), prefersReducedMotion ? 0 : 520);
      void submitServerBattleAction(
        "move",
        { stack_id: selectedUnit.id, to: { x: targetCell.col, y: targetCell.row } },
        selectedServerSide
      );
      return;
    }

    const from = selectedUnit.position;
    setBattleEffect({ type: "move", from, to: targetCell });
    setUnits((current) =>
      current.map((unit) => (unit.id === selectedUnit.id ? { ...unit, position: { ...targetCell }, status: undefined } : unit))
    );
    setLastLosses("перемещение без потерь");
    addLog(`${selectedUnit.name} смещаются на отмеченную клетку и открывают линию.`);
    window.setTimeout(() => setBattleEffect(null), prefersReducedMotion ? 0 : 520);
  };

  const attackUnit = (target: BattleUnit) => {
    if (!selectedUnit?.position || !target.position) {
      return;
    }

    if (isProductionBattle) {
      if (!canActWithSelectedUnit || !selectedServerSide) {
        const message = "Сейчас ходит другая сторона или выбран не активный отряд.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      const effectType = selectedUnit.attackRange > 1 ? "ranged" : "melee";
      setBattleEffect({ type: effectType, from: selectedUnit.position, to: target.position });
      window.setTimeout(() => setBattleEffect(null), prefersReducedMotion ? 0 : 720);
      void submitServerBattleAction(
        "attack",
        { stack_id: selectedUnit.id, target_stack_id: target.id },
        selectedServerSide
      );
      return;
    }

    const isRanged = selectedUnit.attackRange > 1;
    const rawDamage = selectedUnit.countAlive * Math.max(1, selectedUnit.attack - target.defense + 1);
    const battleDamage = Math.max(9, Math.floor(rawDamage / 12));
    const totalWounds = target.woundsOnFrontUnit + battleDamage;
    const killed = Math.min(target.countAlive, Math.max(1, Math.floor(totalWounds / target.hp)));
    const nextCount = Math.max(0, target.countAlive - killed);
    const nextWounds = nextCount === 0 ? 0 : totalWounds % target.hp;
    const effectType = isRanged ? "ranged" : "melee";

    setBattleEffect({ type: effectType, from: selectedUnit.position, to: target.position });
    setDamageMarker({ cell: target.position, label: `-${killed}` });
    setUnits((current) =>
      current.map((unit) =>
        unit.id === target.id
          ? {
              ...unit,
              countAlive: nextCount,
              woundsOnFrontUnit: nextWounds,
              status: nextCount === 0 ? "destroyed" : "wounded"
            }
          : unit
      )
    );
    setLastLosses(`${target.name}: -${killed}, ранение ${nextWounds}`);
    addLog(`${selectedUnit.name} наносят удар по цели: ${target.name}. Потери ${killed}, ранение ${nextWounds}.`);
    window.setTimeout(() => {
      setBattleEffect(null);
      setDamageMarker(null);
    }, prefersReducedMotion ? 0 : 720);
  };

  const attackHero = (target: BattleHeroTarget) => {
    if (!selectedUnit?.position) {
      return;
    }

    if (isProductionBattle) {
      if (!canActWithSelectedUnit || !selectedServerSide) {
        const message = "Сейчас ходит другая сторона или выбран не активный отряд.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      const effectType = selectedUnit.attackRange > 1 ? "ranged" : "melee";
      setBattleEffect({ type: effectType, from: selectedUnit.position, to: target.cell });
      window.setTimeout(() => setBattleEffect(null), prefersReducedMotion ? 0 : 720);
      void submitServerBattleAction(
        "attack",
        { stack_id: selectedUnit.id, target_type: "hero", target_side: target.serverSide },
        selectedServerSide
      );
    }
  };

  const defendSelectedUnit = () => {
    if (!selectedUnit) {
      return;
    }

    if (isProductionBattle) {
      if (!canActWithSelectedUnit || !selectedServerSide) {
        const message = "Защиту может поставить только активный отряд вашей стороны.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      void submitServerBattleAction("defend", { stack_id: selectedUnit.id }, selectedServerSide);
      return;
    }

    setActionMode("defend");
    setUnits((current) => current.map((unit) => (unit.id === selectedUnit.id ? { ...unit, status: "defending" } : unit)));
    setLastLosses("отряд укрепил защиту, потерь нет");
    addLog(`${selectedUnit.name} закрываются щитами и получают защитную метку.`);
  };

  const deployReserve = (cell: BattleCell) => {
    if (!selectedReserve) {
      return;
    }

    if (isProductionBattle) {
      if (!playerServerSide || getBattleStatus(serverBattle) !== "deployment" || isBattleActionPending) {
        return;
      }
      void submitServerBattleAction(
        "deploy",
        {
          source_id: selectedReserve.sourceId,
          card_id: selectedReserve.cardId,
          to: { x: cell.col, y: cell.row }
        },
        playerServerSide
      );
      return;
    }

    setUnits((current) => current.map((unit) => (unit.id === selectedReserve.id ? { ...unit, position: { ...cell } } : unit)));
    setSelectedUnitId(selectedReserve.id);
    setSelectedReserveId("");
    addLog(`${selectedReserve.name} выставлены на стартовую линию Севера.`);
  };

  const handleCellClick = (cell: BattleCell) => {
    const occupant = getUnitAtCell(units, cell);
    const isHeroCell = heroTargetByCellKey.has(cellKey(cell));

    if (phase === "deployment") {
      if (occupant) {
        setSelectedUnitId(occupant.id);
        return;
      }

      if (selectedReserve && !isHeroCell && (useDemoState ? deploymentRows.north.includes(cell.row) : deploymentRowSet.has(cell.row))) {
        deployReserve(cell);
      }

      return;
    }

    if (phase !== "turn") {
      return;
    }

    const heroTarget = heroTargetByCellKey.get(cellKey(cell));
    if (heroTarget && legalHeroAttackKeys.has(cellKey(cell))) {
      attackHero(heroTarget);
      return;
    }

    if (occupant) {
      if (occupant.side === playerUiSide) {
        setSelectedUnitId(occupant.id);
        setActionMode(occupant.attackRange > 1 ? "attack" : "move");
        return;
      }

      if (legalAttackKeys.has(cellKey(cell))) {
        attackUnit(occupant);
      }

      return;
    }

    if (legalMoveKeys.has(cellKey(cell))) {
      moveUnit(cell);
    }
  };

  const applyAutoDefend = () => {
    defendSelectedUnit();
    setTimerSeconds(60);
    setPhase("turn");
    setTimeoutCount(1);
    addLog("Автозащита применена. Следующий повторный таймаут отдаст бой мастеру.");
  };

  const applyMasterTakeover = () => {
    setTimeoutCount(2);
    setPhase("timeout");
    addLog("Повторный таймаут. Мастер может забрать ход или запустить авторасчет.");
  };

  const showResult = () => {
    if (isProductionBattle) {
      if (!playerServerSide) {
        const message = "Авторасчет доступен только участнику боя или мастеру.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      void submitServerBattleAction("auto_resolve", {}, playerServerSide);
      return;
    }

    setPhase("result");
    setTimerSeconds(0);
    setRound(3);
    setUnits((current) =>
      current.map((unit) =>
        unit.id === "river-guard" || unit.id === "river-siege"
          ? { ...unit, countAlive: 0, woundsOnFrontUnit: 0, status: "destroyed" }
          : unit.id === "north-rangers"
            ? { ...unit, countAlive: 53, woundsOnFrontUnit: 1, status: "wounded" }
            : unit
      )
    );
    setLastLosses("Стража переправы и камнеметная команда сгорели после боя");
    addLog("Север удержал поле. Речные ворота переходят победителю после выбора гарнизона.");
  };

  const surrenderBattle = () => {
    if (isProductionBattle) {
      if (!activeServerSide || playerServerSide !== activeServerSide) {
        const message = "Сдаться может только сторона, чей ход сейчас активен.";
        setLastLosses(message);
        addLog(message);
        return;
      }
      void submitServerBattleAction("surrender", {}, activeServerSide);
      return;
    }

    showResult();
  };

  const toggleGarrison = (unitId: string) => {
    setSelectedGarrisonIds((current) => {
      if (current.includes(unitId)) {
        return current.filter((id) => id !== unitId);
      }

      if (current.length >= 3) {
        return current;
      }

      return [...current, unitId];
    });
  };

  const resetBattle = () => {
    if (isProductionBattle) {
      return;
    }
    setPhase("deployment");
    setTimerSeconds(60);
    setRound(2);
    setUnits(createInitialUnits());
    setSelectedUnitId("north-rangers");
    setSelectedReserveId("north-sappers");
    setActionMode("attack");
    setBattleLog(initialLog);
    setTimeoutCount(0);
    setLastLosses("потерь после последнего удара нет");
    setBattleEffect(null);
    setDamageMarker(null);
    setSelectedGarrisonIds(["north-guard"]);
  };

  if (!useDemoState && !serverBattle && isBattleLoading) {
    return <LordBattleOpeningScreen />;
  }

  if (!useDemoState && !serverBattle) {
    return (
      <LordBattleReadOnlyScreen
        battleId={currentBattleId || null}
        message={battleGateStatus || lordUiState.readonlyReason}
        mpState={battleMpState}
      />
    );
  }

  return (
    <main className="lord-battle-screen" onContextMenu={(event) => event.preventDefault()}>
      <motion.div
        className="lord-battle-table-glow"
        aria-hidden="true"
        animate={prefersReducedMotion ? undefined : { opacity: [0.58, 0.86, 0.62] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />

      <header className="lord-battle-hud" aria-label="Сводка боя">
        <button className="lord-battle-back" type="button" onClick={() => window.location.assign(withLordBattleRuntimeQuery(returnPath))}>
          <ArrowLeft size={16} />
          Назад
        </button>
        <BattleLordPlate side={battleSideViews.north} align="left" />
        <div className={`lord-battle-timer${timerSeconds <= 10 && phase !== "result" ? " is-warning" : ""}`}>
          <span>Раунд {round}</span>
          <b>{formatTimer(timerSeconds)}</b>
        </div>
        <BattleLordPlate side={battleSideViews.river} align="right" />
      </header>

      <section className="lord-battle-shell" aria-label="Бой лордов">
        <aside className="lord-battle-side-panel left">
          <div className="lord-battle-panel-title">
            <span>{phase === "deployment" ? "Резерв Севера" : "Выбранный отряд"}</span>
            <b>{phase === "deployment" ? "выставление" : selectedUnit?.name ?? "нет выбора"}</b>
          </div>
          {phase === "deployment" ? (
            <div className="lord-battle-reserve-list">
              {reserveUnits.map((unit) => (
                <button
                  key={unit.id}
                  className={`lord-battle-reserve-card ${unit.side}${selectedReserveId === unit.id ? " is-selected" : ""}`}
                  type="button"
                  onClick={() => setSelectedReserveId(unit.id)}
                >
                  <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
                  <span>{unitClassLabel[unit.classId]}</span>
                  <b>{unit.name}</b>
                  <small>отряд {unit.countAlive} · А{unit.attack} З{unit.defense} HP{unit.hp}</small>
                </button>
              ))}
              <div className="lord-battle-deploy-note">
                <CheckCircle2 size={15} />
                Выберите карту и поставьте ее на две стартовые линии у ставки.
              </div>
            </div>
          ) : (
            <SelectedUnitPanel unit={selectedUnit} />
          )}
        </aside>

        <motion.div
          className={`lord-battle-board-wrap${isBoardFocused ? " is-focused" : ""}${isDebugGrid ? " is-debug-grid" : ""}`}
          initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.96, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 0.75, 0.2, 1] }}
        >
          <motion.div
            className={`lord-battle-board-stage${isBoardFocused ? " is-focused" : ""}`}
            animate={{ scale: isBoardFocused ? 1 : 0.985 }}
            transition={prefersReducedMotion ? { duration: 0 } : { duration: 1.35, ease: [0.18, 0.72, 0.18, 1] }}
            style={{ transformOrigin: "50% 50%" }}
          >
            <img className="lord-battle-table-art is-overview" src={lordBattleWarTable} alt="" draggable={false} />
            <img className="lord-battle-table-art is-closeup" src={lordBattleBoardCloseup} alt="" draggable={false} />
            <div className="lord-battle-board-fog" aria-hidden="true" />
            <CommanderSeal side={battleSideViews.north} />
            <CommanderSeal side={battleSideViews.river} />
            <div className="lord-battle-grid-layer" aria-label="Тактическое поле 5 на 6">
              {lineOfSightTarget?.position && selectedUnit?.position ? (
                <LineOfSight from={selectedUnit.position} to={lineOfSightTarget.position} />
              ) : null}
              {battleEffect ? <BattleEffectLayer effect={battleEffect} /> : null}
              {battleCells.map((cell) => {
                const occupant = getUnitAtCell(units, cell);
                const key = cellKey(cell);
                const heroTarget = heroTargetByCellKey.get(key);
                const isDeployCell =
                  phase === "deployment" &&
                  (useDemoState ? deploymentRows.north.includes(cell.row) : deploymentRowSet.has(cell.row)) &&
                  !occupant &&
                  !heroTarget;
                const isLegalMove = phase === "turn" && canActWithSelectedUnit && legalMoveKeys.has(key);
                const isLegalAttack = phase === "turn" && canActWithSelectedUnit && legalAttackKeys.has(key);
                return (
                  <button
                    key={key}
                    className={`lord-battle-hit-cell${isDeployCell ? " is-deploy" : ""}${isLegalMove ? " is-move" : ""}${isLegalAttack ? " is-attack" : ""}${occupant ? " has-unit" : ""}`}
                    type="button"
                    aria-label={occupant ? occupant.name : `Клетка ${cell.row + 1}-${cell.col + 1}`}
                    onClick={() => handleCellClick(cell)}
                  >
                    {heroTarget ? (
                      <BattleHeroCell
                        target={heroTarget}
                        isAttackable={isLegalAttack}
                      />
                    ) : null}
                    {occupant ? (
                      <BattleUnitToken
                        unit={occupant}
                        isActive={occupant.id === selectedUnitId}
                        currentTone={occupant.id === activeStackId && phase === "turn" ? (occupant.side === playerUiSide ? "own" : "enemy") : null}
                      />
                    ) : null}
                    {damageMarker && isSameCell(damageMarker.cell, cell) ? (
                      <motion.span
                        className="lord-battle-damage-mark"
                        initial={prefersReducedMotion ? false : { opacity: 0, y: 10, scale: 0.8 }}
                        animate={{ opacity: 1, y: -10, scale: 1 }}
                        exit={{ opacity: 0 }}
                      >
                        {damageMarker.label}
                      </motion.span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            {useDemoState && (phase === "result" || phase === "garrison") ? (
              <motion.div
                className="lord-battle-victory-seal"
                initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.35, rotate: -8 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                transition={{ type: "spring", stiffness: 120, damping: 13 }}
              >
                <Trophy size={28} />
                <b>{battleVictoryLabel}</b>
              </motion.div>
            ) : null}
          </motion.div>
          <button className="lord-battle-camera-toggle" type="button" onClick={() => setIsBoardFocused((current) => !current)}>
            {isBoardFocused ? "Весь стол" : "Клетки"}
          </button>
        </motion.div>

        <aside className="lord-battle-side-panel right">
          <div className="lord-battle-panel-title">
            <span>Очередь инициативы</span>
            <b>{initiativeQueue[0]?.name ?? "нет отрядов"}</b>
          </div>
          <div className="lord-battle-initiative">
            {initiativeQueue.slice(0, 6).map((unit) => {
              const currentTone = unit.id === activeStackId ? (unit.side === playerUiSide ? "own" : "enemy") : null;
              return (
                <button
                  key={unit.id}
                  type="button"
                  className={`lord-battle-queue-row ${unit.side}${unit.id === selectedUnitId ? " is-selected" : ""}${currentTone ? ` is-current is-current-${currentTone}` : ""}`}
                  onClick={() => setSelectedUnitId(unit.id)}
                >
                  <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
                  <span>{unit.name}</span>
                  <b>{unit.initiative}</b>
                </button>
              );
            })}
          </div>
        </aside>
      </section>

      {phase === "result" ? (
        <motion.section
          className="lord-battle-result-panel"
          aria-label="Итог боя"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 180, damping: 22 }}
        >
          <div>
            <h2>{battleResultOutcomeLabel}</h2>
          </div>
          <div className="lord-battle-result-actions">
            <button type="button" onClick={() => window.location.assign(withLordBattleRuntimeQuery(battleTerritoryHomePath))}>
              <Trophy size={15} />
              Перейти в территорию
            </button>
          </div>
        </motion.section>
      ) : null}

      {phase !== "result" ? (
        <footer className="lord-battle-command-bar">
          <div>
            <span>Команда</span>
            <b>{selectedUnit?.name ?? selectedReserve?.name ?? "выберите отряд"}</b>
          </div>
          <div className="lord-battle-command-actions">
            <CommandActionButton active={actionMode === "move"} disabled={phase !== "turn" || !canActWithSelectedUnit} onClick={() => setActionMode("move")} icon={<Sparkles size={15} />} label="Переместить" />
            <CommandActionButton active={actionMode === "attack"} disabled={phase !== "turn" || !canActWithSelectedUnit} onClick={() => setActionMode("attack")} icon={<Crosshair size={15} />} label="Атаковать" />
            <CommandActionButton active={actionMode === "defend"} disabled={phase !== "turn" || !canActWithSelectedUnit} onClick={defendSelectedUnit} icon={<Shield size={15} />} label="Защищаться" />
            <CommandActionButton active={false} disabled={phase !== "turn"} onClick={() => setActionMode("attack")} icon={<XCircle size={15} />} label="Отмена" />
          </div>
          <div className="lord-battle-flow-actions">
            {phase === "deployment" ? (
              <button type="button" onClick={confirmDeploymentReady} disabled={isProductionBattle && (!playerServerSide || isBattleActionPending)}>
                <CheckCircle2 size={15} />
                Готов
              </button>
            ) : null}
            {useDemoState && phase === "turn" ? (
              <button type="button" onClick={triggerTimeout} disabled={isProductionBattle && (!activeServerSide || playerServerSide !== activeServerSide || isBattleActionPending)}>
                <Clock3 size={15} />
                Истечь таймер
              </button>
            ) : null}
            {useDemoState && phase === "timeout" ? (
              <>
                <button type="button" onClick={applyAutoDefend}>
                  <Shield size={15} />
                  Автозащита
                </button>
                <button type="button" onClick={showResult}>
                  <Gavel size={15} />
                  Авторасчет
                </button>
              </>
            ) : null}
            {useDemoState && phase === "garrison" ? (
              <button type="button" onClick={resetBattle}>
                <Swords size={15} />
                Новый прогон
              </button>
            ) : null}
            {phase !== "deployment" && phase !== "garrison" ? (
              <>
                <button type="button" onClick={showResult} disabled={isProductionBattle && (!playerServerSide || isBattleActionPending)}>
                  <Gavel size={15} />
                  {autoResolveLabel}
                </button>
                <button type="button" onClick={surrenderBattle} disabled={isProductionBattle && (!activeServerSide || playerServerSide !== activeServerSide || isBattleActionPending)}>
                  <XCircle size={15} />
                  Сдаться
                </button>
              </>
            ) : null}
          </div>
          <LordMpHud className="lord-battle-mp-widget" currentMp={battleMpState.currentMp} mpCap={battleMpState.mpCap} />
        </footer>
      ) : null}

      <AnimatePresence>
        {useDemoState && phase === "garrison" ? (
          <motion.div className="lord-battle-modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.section
              className="lord-battle-garrison-modal"
              initial={prefersReducedMotion ? false : { opacity: 0, y: 18, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
            >
              <div className="lord-battle-panel-title">
                <span>Захват Речных ворот</span>
                <b>выберите гарнизон</b>
              </div>
              <p>Нужно оставить минимум одну выжившую пачку. Вместимость форпоста: 3 отряда.</p>
              <div className="lord-battle-garrison-list">
                {livingNorthUnits.map((unit) => (
                  <button
                    key={unit.id}
                    className={`lord-battle-garrison-row${selectedGarrisonIds.includes(unit.id) ? " is-selected" : ""}`}
                    type="button"
                    onClick={() => toggleGarrison(unit.id)}
                  >
                    <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
                    <span>{unit.name}</span>
                    <b>{unit.countAlive}</b>
                  </button>
                ))}
              </div>
              <div className="lord-battle-garrison-footer">
                <small>{selectedGarrisonIds.length}/3 выбрано</small>
                <button type="button" disabled={!canFinishGarrison} onClick={resetBattle}>
                  Закрепить захват
                </button>
              </div>
              {!canFinishGarrison ? <strong>Нельзя завершить захват без гарнизона.</strong> : null}
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </main>
  );
}

function AlertIcon() {
  return <Skull size={14} />;
}

function BattleLordPlate({ side, align }: { side: BattleSide; align: "left" | "right" }) {
  const hpPercent = Math.max(0, Math.min(100, (side.hp / side.maxHp) * 100));

  return (
    <article className={`lord-battle-lord-plate ${side.accent} ${align}`}>
      <span className="lord-battle-side-seal" aria-hidden="true">
        <Crown size={26} strokeWidth={1.7} />
      </span>
      <div>
        <span>{side.domain}</span>
        <b>{side.name}</b>
        <small>HP {side.hp}/{side.maxHp}</small>
      </div>
      <div className="lord-battle-hp-track" aria-hidden="true">
        <i style={{ width: `${hpPercent}%` }} />
      </div>
    </article>
  );
}

function CommanderSeal({ side }: { side: BattleSide }) {
  return (
    <div className={`lord-battle-commander commander-${side.id}`} aria-hidden="true">
      <div className="lord-battle-commander-seal">
        <Crown size={24} />
      </div>
    </div>
  );
}

function BattleHeroCell({ target, isAttackable }: { target: BattleHeroTarget; isAttackable: boolean }) {
  const hpPercent = Math.max(0, Math.min(100, (target.hp / target.maxHp) * 100));
  return (
    <span className={`lord-battle-hero-cell ${target.side}${isAttackable ? " is-attackable" : ""}`}>
      <Crown size={16} />
      <b>Ставка</b>
      <small>{target.hp}/{target.maxHp}</small>
      <i style={{ width: `${hpPercent}%` }} />
    </span>
  );
}

function SelectedUnitPanel({ unit }: { unit: BattleUnit | undefined }) {
  if (!unit) {
    return (
      <div className="lord-battle-empty-detail">
        <Users size={24} />
        <b>Отряд не выбран</b>
        <span>Нажмите на карту на поле или в очереди инициативы.</span>
      </div>
    );
  }

  return (
    <article className={`lord-battle-unit-detail ${unit.side}`}>
      <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
      <span>{unitClassLabel[unit.classId]}</span>
      <h2>{unit.name}</h2>
      <p>{unit.title}</p>
      <div className="lord-battle-stat-grid">
        <Metric label="число" value={`${unit.countAlive}/${unit.countStart}`} />
        <Metric label="атака" value={unit.attack} />
        <Metric label="защита" value={unit.defense} />
        <Metric label="hp" value={unit.hp} />
        <Metric label="иниц." value={unit.initiative} />
        <Metric label="дальн." value={unit.attackRange} />
      </div>
      {unit.woundsOnFrontUnit > 0 ? <strong>Ранение передней единицы: {unit.woundsOnFrontUnit}</strong> : null}
      {unit.ability ? <em>{unit.ability}</em> : null}
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function BattleUnitToken({
  unit,
  isActive,
  currentTone
}: {
  unit: BattleUnit;
  isActive: boolean;
  currentTone: "own" | "enemy" | null;
}) {
  return (
    <motion.div
      layout
      className={`lord-battle-unit-token ${unit.side} ${unit.classId}${isActive ? " is-selected" : ""}${currentTone ? ` is-current is-current-${currentTone}` : ""}${unit.status === "destroyed" ? " is-destroyed" : ""}${unit.status === "defending" ? " is-defending" : ""}`}
      initial={{ opacity: 0, y: 16, rotate: unit.side === "north" ? -1.5 : 1.5 }}
      animate={{ opacity: 1, y: isActive ? -8 : 0, rotate: 0 }}
      transition={{ type: "spring", stiffness: 240, damping: 22 }}
    >
      <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
      <span>{unitClassLabel[unit.classId]}</span>
      <b>{unit.name}</b>
      <small>{unit.countAlive}</small>
    </motion.div>
  );
}

function BattleEffectLayer({ effect }: { effect: Exclude<BattleEffect, null> }) {
  const from = getCellCenter(effect.from);
  const to = getCellCenter(effect.to);

  return (
    <motion.svg className={`lord-battle-effect-svg ${effect.type}`} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <motion.line
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        vectorEffect="non-scaling-stroke"
        initial={{ opacity: 0, pathLength: 0 }}
        animate={{ opacity: 1, pathLength: 1 }}
        exit={{ opacity: 0 }}
      />
    </motion.svg>
  );
}

function LineOfSight({ from, to }: { from: BattleCell; to: BattleCell }) {
  const start = getCellCenter(from);
  const end = getCellCenter(to);

  return (
    <svg className="lord-battle-los-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <line x1={start.x} y1={start.y} x2={end.x} y2={end.y} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function getCellCenter(cell: BattleCell) {
  return {
    x: ((cell.col + 0.5) / boardCols) * 100,
    y: ((cell.row + 0.5) / boardRows) * 100
  };
}

function LordBattleOpeningScreen() {
  return (
    <main className="lord-battle-screen is-opening" role="status" onContextMenu={(event) => event.preventDefault()}>
      <h1 className="lord-battle-opening-text">Открываем бой</h1>
    </main>
  );
}

function LordBattleReadOnlyScreen({
  battleId,
  message,
  mpState
}: {
  battleId: string | null;
  message: string;
  mpState: { currentMp: number | null; mpCap: number | null };
}) {
  return (
    <main className="lord-battle-screen is-readonly" onContextMenu={(event) => event.preventDefault()}>
      <div className="lord-battle-table-glow" />
      <header className="lord-battle-hud" aria-label="Сводка боя">
        <button className="lord-battle-back" type="button" onClick={() => window.location.assign(withLordBattleRuntimeQuery(getLordBattleReturnPath(new URLSearchParams(window.location.search))))}>
          <ArrowLeft size={16} />
          Назад
        </button>
        <div className="lord-battle-timer">
          <span>Боевой стол</span>
          <b>--:--</b>
          <small>только чтение</small>
        </div>
        <LordMpHud className="lord-battle-mp-widget" currentMp={mpState.currentMp} mpCap={mpState.mpCap} />
      </header>
      <section className="lord-battle-readonly-panel" role="status">
        <Swords size={38} />
        <span>{battleId ? `Бой ${battleId}` : "Активного боя нет"}</span>
        <h1>Боевой экран закрыт</h1>
        <p>{message || "Связь с боевой канцелярией потеряна. Экран открыт только для чтения."}</p>
      </section>
    </main>
  );
}

function BattleStateChip({ icon, text, tone }: { icon: ReactNode; text: string; tone: "blue" | "steel" | "red" }) {
  return (
    <span className={`lord-battle-state-chip ${tone}`}>
      {icon}
      {text}
    </span>
  );
}

function CommandActionButton({
  active,
  disabled,
  onClick,
  icon,
  label
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button className={active ? "is-active" : ""} type="button" disabled={disabled} onClick={onClick}>
      {icon}
      {label}
    </button>
  );
}

export default LordBattleScreen;
