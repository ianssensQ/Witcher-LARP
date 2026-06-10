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
import lordSealNorth from "./assets/generated/mobile/w7-orders-v1/w7_lord_seal_north_v1.png";
import lordSealRiver from "./assets/generated/mobile/w7-orders-v1/w7_lord_seal_river_v1.png";
import unitCavalryIcon from "./assets/generated/lords-home/units/unit-cavalry-v1.png";
import unitGuardIcon from "./assets/generated/lords-home/units/unit-guard-v1.png";
import unitHeavySiegeIcon from "./assets/generated/lords-home/units/unit-heavy-siege-v1.png";
import unitInfantryIcon from "./assets/generated/lords-home/units/unit-infantry-v1.png";
import unitRangedIcon from "./assets/generated/lords-home/units/unit-ranged-v1.png";
import unitSpecialistIcon from "./assets/generated/lords-home/units/unit-specialist-v1.png";
import { LordMpHud, useLordMpRuntimeState } from "./LordMpHud";

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
  seal: string;
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
};

type BattleEffect =
  | { type: "move"; from: BattleCell; to: BattleCell }
  | { type: "ranged"; from: BattleCell; to: BattleCell }
  | { type: "melee"; from: BattleCell; to: BattleCell }
  | null;

const boardRows = 6;
const boardCols = 5;
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
    accent: "blue",
    seal: lordSealNorth
  },
  river: {
    id: "river",
    name: "Леди Переправ",
    domain: "Речной дом",
    hp: 41,
    maxHp: 58,
    accent: "red",
    seal: lordSealRiver
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

const formatTimer = (seconds: number) => `00:${Math.max(0, seconds).toString().padStart(2, "0")}`;

function LordBattleScreen() {
  const prefersReducedMotion = useReducedMotion();
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

  const selectedUnit = units.find((unit) => unit.id === selectedUnitId);
  const selectedReserve = units.find((unit) => unit.id === selectedReserveId);
  const initiativeQueue = useMemo(
    () =>
      [...units]
        .filter((unit) => unit.status !== "destroyed" && unit.position)
        .sort((left, right) => right.initiative - left.initiative || right.attack - left.attack),
    [units]
  );
  const reserveUnits = units.filter((unit) => unit.side === "north" && !unit.position && unit.status !== "destroyed");
  const legalMoveKeys = useMemo(() => getLegalMoves(selectedUnit, units), [selectedUnit, units]);
  const legalAttackKeys = useMemo(() => getLegalAttacks(selectedUnit, units), [selectedUnit, units]);
  const lineOfSightTarget = useMemo(() => getLineOfSightTarget(selectedUnit, units), [selectedUnit, units]);
  const livingNorthUnits = units.filter((unit) => unit.side === "north" && unit.status !== "destroyed" && unit.countAlive > 0);
  const canFinishGarrison = selectedGarrisonIds.length > 0 && selectedGarrisonIds.length <= 3;

  const addLog = (message: string) => {
    setBattleLog((current) => [message, ...current].slice(0, 8));
  };

  useEffect(() => {
    const focusTimer = window.setTimeout(() => {
      setIsBoardFocused(true);
    }, prefersReducedMotion ? 120 : 950);

    return () => window.clearTimeout(focusTimer);
  }, [prefersReducedMotion]);

  useEffect(() => {
    if (phase !== "turn" && phase !== "timeout") {
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
    if (phase === "turn" && timerSeconds === 0) {
      triggerTimeout();
    }
  }, [phase, timerSeconds]);

  const startTurnPhase = () => {
    setPhase("turn");
    setTimerSeconds(42);
    setSelectedUnitId("north-rangers");
    setSelectedReserveId("");
    setActionMode("attack");
    addLog("Север завершил выставление. Очередь инициативы поднята на стол.");
  };

  const triggerTimeout = () => {
    setPhase("timeout");
    setTimeoutCount((current) => Math.max(1, current + 1));
    setTimerSeconds(9);
    addLog("Таймер сорвался. Активный отряд получит автозащиту, если ход не будет решен.");
  };

  const moveUnit = (targetCell: BattleCell) => {
    if (!selectedUnit?.position) {
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

  const defendSelectedUnit = () => {
    if (!selectedUnit) {
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

    setUnits((current) => current.map((unit) => (unit.id === selectedReserve.id ? { ...unit, position: { ...cell } } : unit)));
    setSelectedUnitId(selectedReserve.id);
    setSelectedReserveId("");
    addLog(`${selectedReserve.name} выставлены на стартовую линию Севера.`);
  };

  const handleCellClick = (cell: BattleCell) => {
    const occupant = getUnitAtCell(units, cell);

    if (phase === "deployment") {
      if (occupant) {
        setSelectedUnitId(occupant.id);
        return;
      }

      if (selectedReserve && deploymentRows.north.includes(cell.row)) {
        deployReserve(cell);
      }

      return;
    }

    if (phase !== "turn") {
      return;
    }

    if (occupant) {
      if (occupant.side === "north") {
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

  return (
    <main className="lord-battle-screen" onContextMenu={(event) => event.preventDefault()}>
      <motion.div
        className="lord-battle-table-glow"
        aria-hidden="true"
        animate={prefersReducedMotion ? undefined : { opacity: [0.58, 0.86, 0.62] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />

      <header className="lord-battle-hud" aria-label="Сводка боя">
        <button className="lord-battle-back" type="button" onClick={() => window.location.assign("/lords/home")}>
          <ArrowLeft size={16} />
          Замок
        </button>
        <BattleLordPlate side={battleSides.north} align="left" />
        <div className={`lord-battle-timer${timerSeconds <= 10 && phase !== "result" ? " is-warning" : ""}`}>
          <span>Раунд {round}</span>
          <b>{formatTimer(timerSeconds)}</b>
          <small>{phaseLabel[phase]}</small>
        </div>
        <BattleLordPlate side={battleSides.river} align="right" />
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
                Выберите карту и поставьте ее на две нижние стартовые линии.
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
            <CommanderSeal side={battleSides.north} />
            <CommanderSeal side={battleSides.river} />
            <div className="lord-battle-grid-layer" aria-label="Тактическое поле 5 на 6">
              {lineOfSightTarget?.position && selectedUnit?.position ? (
                <LineOfSight from={selectedUnit.position} to={lineOfSightTarget.position} />
              ) : null}
              {battleEffect ? <BattleEffectLayer effect={battleEffect} /> : null}
              {battleCells.map((cell) => {
                const occupant = getUnitAtCell(units, cell);
                const key = cellKey(cell);
                const isDeployCell = phase === "deployment" && deploymentRows.north.includes(cell.row) && !occupant;
                const isLegalMove = phase === "turn" && legalMoveKeys.has(key);
                const isLegalAttack = phase === "turn" && legalAttackKeys.has(key);
                return (
                  <button
                    key={key}
                    className={`lord-battle-hit-cell${isDeployCell ? " is-deploy" : ""}${isLegalMove ? " is-move" : ""}${isLegalAttack ? " is-attack" : ""}${occupant ? " has-unit" : ""}`}
                    type="button"
                    aria-label={occupant ? occupant.name : `Клетка ${cell.row + 1}-${cell.col + 1}`}
                    onClick={() => handleCellClick(cell)}
                  >
                    {occupant ? (
                      <BattleUnitToken
                        unit={occupant}
                        isActive={occupant.id === selectedUnitId}
                        isCurrent={occupant.id === "north-rangers" && phase === "turn"}
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
            {phase === "result" || phase === "garrison" ? (
              <motion.div
                className="lord-battle-victory-seal"
                initial={prefersReducedMotion ? false : { opacity: 0, scale: 1.35, rotate: -8 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                transition={{ type: "spring", stiffness: 120, damping: 13 }}
              >
                <Trophy size={28} />
                <b>Победа Севера</b>
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
            {initiativeQueue.slice(0, 6).map((unit) => (
              <button
                key={unit.id}
                type="button"
                className={`lord-battle-queue-row ${unit.side}${unit.id === selectedUnitId ? " is-selected" : ""}`}
                onClick={() => setSelectedUnitId(unit.id)}
              >
                <img src={unitClassIcon[unit.classId]} alt="" draggable={false} />
                <span>{unit.name}</span>
                <b>{unit.initiative}</b>
              </button>
            ))}
          </div>
          <div className="lord-battle-modifiers">
            <BattleStateChip icon={<Shield size={14} />} text="щитовая стена: +2 защита" tone="blue" />
            <BattleStateChip icon={<Waves size={14} />} text="мостовой туман: дальность видна" tone="steel" />
            <BattleStateChip icon={<AlertIcon />} text={timeoutCount > 1 ? "перехват мастера готов" : "повторный таймаут опасен"} tone="red" />
          </div>
          <div className="lord-battle-log" aria-live="polite">
            {battleLog.map((entry) => (
              <p key={entry}>{entry}</p>
            ))}
          </div>
          <div className="lord-battle-panel-actions">
            <button type="button" onClick={defendSelectedUnit} disabled={!selectedUnit || phase !== "turn"}>
              <Shield size={15} />
              Защита
            </button>
            <button type="button" onClick={showResult} disabled={phase === "deployment"}>
              <Gavel size={15} />
              Авторасчет
            </button>
            <button type="button" onClick={showResult} disabled={phase === "result" || phase === "garrison"}>
              <XCircle size={15} />
              Сдаться
            </button>
          </div>
        </aside>
      </section>

      <footer className="lord-battle-command-bar">
        <div>
          <span>Команда</span>
          <b>{selectedUnit?.name ?? selectedReserve?.name ?? "выберите отряд"}</b>
          <small>{lastLosses}</small>
        </div>
        <div className="lord-battle-command-actions">
          <CommandActionButton active={actionMode === "move"} disabled={phase !== "turn"} onClick={() => setActionMode("move")} icon={<Sparkles size={15} />} label="Переместить" />
          <CommandActionButton active={actionMode === "attack"} disabled={phase !== "turn"} onClick={() => setActionMode("attack")} icon={<Crosshair size={15} />} label="Атаковать" />
          <CommandActionButton active={actionMode === "defend"} disabled={phase !== "turn"} onClick={defendSelectedUnit} icon={<Shield size={15} />} label="Защищаться" />
          {selectedUnit?.ability ? (
            <CommandActionButton active={actionMode === "ability"} disabled={phase !== "turn"} onClick={() => setActionMode("ability")} icon={<Flame size={15} />} label="Способность" />
          ) : null}
          <CommandActionButton active={false} disabled={phase === "deployment"} onClick={() => setSelectedUnitId("north-rangers")} icon={<XCircle size={15} />} label="Отмена" />
        </div>
        <div className="lord-battle-flow-actions">
          {phase === "deployment" ? (
            <button type="button" onClick={startTurnPhase}>
              <CheckCircle2 size={15} />
              Готов
            </button>
          ) : null}
          {phase === "turn" ? (
            <button type="button" onClick={triggerTimeout}>
              <Clock3 size={15} />
              Истечь таймер
            </button>
          ) : null}
          {phase === "timeout" ? (
            <>
              <button type="button" onClick={applyAutoDefend}>
                <Shield size={15} />
                Автозащита
              </button>
              <button type="button" onClick={applyMasterTakeover}>
                <Hourglass size={15} />
                Повторный таймаут
              </button>
              <button type="button" onClick={showResult}>
                <Gavel size={15} />
                Авторасчет
              </button>
            </>
          ) : null}
          {phase === "result" ? (
            <button type="button" onClick={() => setPhase("garrison")}>
              <Shield size={15} />
              Оставить гарнизон
            </button>
          ) : null}
          {phase === "garrison" ? (
            <button type="button" onClick={resetBattle}>
              <Swords size={15} />
              Новый прогон
            </button>
          ) : null}
        </div>
        <LordMpHud className="lord-battle-mp-widget" currentMp={battleMpState.currentMp} mpCap={battleMpState.mpCap} />
      </footer>

      <AnimatePresence>
        {phase === "garrison" ? (
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
      <img src={side.seal} alt="" draggable={false} />
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
      <img src={side.seal} alt="" draggable={false} />
      <Crown size={18} />
    </div>
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

function BattleUnitToken({ unit, isActive, isCurrent }: { unit: BattleUnit; isActive: boolean; isCurrent: boolean }) {
  return (
    <motion.div
      layout
      className={`lord-battle-unit-token ${unit.side} ${unit.classId}${isActive ? " is-selected" : ""}${isCurrent ? " is-current" : ""}${unit.status === "destroyed" ? " is-destroyed" : ""}${unit.status === "defending" ? " is-defending" : ""}`}
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
