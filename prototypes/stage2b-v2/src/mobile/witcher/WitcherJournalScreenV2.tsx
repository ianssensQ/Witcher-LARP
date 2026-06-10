import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Clock3,
  Coins,
  Crosshair,
  FileWarning,
  Layers,
  LockKeyhole,
  MapPin,
  Package,
  ScrollText,
  Send,
  Shield,
  Swords,
  Trophy,
  Users,
  Wifi,
  XCircle
} from "lucide-react";
import w1ActionSlot from "../../assets/generated/mobile/m1-journal-v2/w1_action_slot_v2.png";
import w1BottomNav from "../../assets/generated/mobile/m1-journal-v2/w1_bottom_nav_v2.png";
import w1GoalPlaque from "../../assets/generated/mobile/m1-journal-v2/w1_goal_plaque_v2.png";
import w1HeaderPlate from "../../assets/generated/mobile/m1-journal-v2/w1_header_plate_v2.png";
import w1JournalBg from "../../assets/generated/mobile/m1-journal-v2/w1_journal_background_v2.png";
import w1PortraitFrame from "../../assets/generated/mobile/m1-journal-v2/w1_portrait_frame_v2.png";
import w1SyncBadgeSet from "../../assets/generated/mobile/m1-journal-v2/w1_sync_badge_set_v2.png";
import w1WitcherPortrait from "../../assets/generated/mobile/m1-journal-v2/w1_witcher_portrait_v2.png";
import w7AddressedRibbon from "../../assets/generated/mobile/w7-orders-v1/w7_addressed_ribbon_v1.png";
import w7ConflictOverlay from "../../assets/generated/mobile/w7-orders-v1/w7_conflict_overlay_v1.png";
import w7ContractSlip from "../../assets/generated/mobile/w7-orders-v1/w7_contract_slip_v1.png";
import w7DetailSheet from "../../assets/generated/mobile/w7-orders-v1/w7_detail_sheet_v1.png";
import w7LockedBadge from "../../assets/generated/mobile/w7-orders-v1/w7_locked_badge_v1.png";
import w7LordSealForest from "../../assets/generated/mobile/w7-orders-v1/w7_lord_seal_forest_v1.png";
import w7LordSealHill from "../../assets/generated/mobile/w7-orders-v1/w7_lord_seal_hill_v1.png";
import w7LordSealNorth from "../../assets/generated/mobile/w7-orders-v1/w7_lord_seal_north_v1.png";
import w7LordSealRiver from "../../assets/generated/mobile/w7-orders-v1/w7_lord_seal_river_v1.png";
import w7OrdersBoardBg from "../../assets/generated/mobile/w7-orders-v1/w7_orders_board_bg_v1.png";
import w7RewardChip from "../../assets/generated/mobile/w7-orders-v1/w7_reward_chip_v1.png";
import "./witcher-journal-v2.css";

const PLAYER_STATE_ENDPOINT_BLOCKER =
  "UI-BLOCKER-045-01: GET /api/players/{id}/state is still absent; W1 visual scenarios below are mock PlayerState fixtures only.";
const PLAYER_ORDER_BOARD_ENDPOINT_BLOCKER =
  "UI-BLOCKER-045-02: GET /api/players/{player_id}/orders is still absent; W7 uses a mock player-visible OrderBoard read model with redacted object ids.";

type WitcherJournalStateId = "normal" | "offline" | "pending";
type WitcherMobileScreenId = "journal" | "orders";
type WitcherRoleType = "witcher" | "sorceress" | "lord" | "npc_master";
type WitcherSyncStatus = "synced" | "offline_snapshot" | "pending_review";
type GoalTrackState = "active" | "completed" | "locked";
type WitcherJournalPanelId = "profile" | "goals" | "qr" | "inventory" | "bag" | "orders" | "trade" | "gwent" | "sync";
type WitcherJournalQuickActionId = Exclude<WitcherJournalPanelId, "profile" | "goals" | "sync">;
type WitcherOrdersStateId = "normal" | "addressed" | "accepted" | "conflict" | "review" | "offline";
type WitcherOrderTabId = "available" | "mine" | "addressed" | "history";
type WitcherLordSealAsset = "north" | "river" | "forest" | "hill";
type WitcherOrderVisibility = "public" | "addressed";
type WitcherOrderStatus =
  | "available"
  | "addressed"
  | "accepted"
  | "submitted_pending_sync"
  | "pending_master_approval"
  | "contested_review"
  | "object_conflict"
  | "completed";
type WitcherEscrowStatus = "none" | "held" | "locked" | "pending";
type WitcherConflictState = "none" | "object_conflict" | "contested_review" | "pending_master_approval";

type WitcherPlayerState = {
  player_id: string;
  display_name: string;
  role_type: WitcherRoleType;
  portrait_asset: string;
  level: number;
  xp: number;
  xp_next: number;
  gold: number;
  current_act: string;
  reputation_descriptor: string;
  sync_status: WitcherSyncStatus;
  pending_events_count: number;
  review_count: number;
  locked_rewards_count: number;
  personal_goals: Array<{
    goal_id: string;
    title: string;
    progress_hint: string;
  }>;
  goal_tracks: Array<{
    goal_id: string;
    current_value: number;
    target_value: number;
    state: GoalTrackState;
  }>;
  revealed_final_hooks: string[];
  locks: Partial<Record<WitcherJournalQuickActionId, string>>;
};

type WitcherJournalGoalRow = {
  id: string;
  title: string;
  progress: string;
  chip: string;
  isLocked: boolean;
};

type WitcherJournalView = {
  player: WitcherPlayerState;
  roleLabel: string;
  syncBadges: string[];
  statusLine: string;
  goals: WitcherJournalGoalRow[];
};

type WitcherJournalPanel = {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  body: string;
};

type WitcherJournalQuickAction = {
  id: WitcherJournalQuickActionId;
  label: string;
  meta: string;
  icon: LucideIcon;
};

type WitcherOrderReadModel = {
  order_id: string;
  lord_id: string;
  lord_name: string;
  lord_seal_asset: WitcherLordSealAsset;
  visibility: WitcherOrderVisibility;
  addressed_to_player_id: string | null;
  status: WitcherOrderStatus;
  title: string;
  hook: string;
  location_hint: string;
  target_label: string;
  object_id_redacted: true;
  reward_label: string;
  escrow_status: WitcherEscrowStatus;
  act: string;
  tier: string;
  competition_count: number;
  accepted_by_me: boolean;
  result_event_id: string | null;
  conflict_state: WitcherConflictState;
  expires_at: string;
  updated_at: string;
};

type WitcherOrderBoard = {
  state_id: WitcherOrdersStateId;
  player_id: string;
  sync_label: string;
  sync_tone: "online" | "offline" | "review";
  my_count: number;
  new_count: number;
  default_tab: WitcherOrderTabId;
  selected_order_id: string | null;
  offline: boolean;
  orders: WitcherOrderReadModel[];
};

const witcherJournalPanels: Record<WitcherJournalPanelId, WitcherJournalPanel> = {
  profile: {
    icon: Swords,
    eyebrow: "персонаж",
    title: "Лист ведьмака",
    body: "Имя, роль, уровень, опыт, золото и репутация из последнего снимка игрока."
  },
  goals: {
    icon: BookOpen,
    eyebrow: "личные цели",
    title: "Запись в журнале",
    body: "Плашка раскрывается как страница: видны только открытые цели и их прогресс."
  },
  qr: {
    icon: Crosshair,
    eyebrow: "сцена",
    title: "QR",
    body: "Открывает сцену на месте и сохраняет результат в очередь телефона."
  },
  inventory: {
    icon: Swords,
    eyebrow: "снаряжение",
    title: "Инвентарь",
    body: "Оружие, броня и активные боевые предметы персонажа."
  },
  bag: {
    icon: Package,
    eyebrow: "сумка",
    title: "Сумка",
    body: "Предметы, зелья, трофеи и награды, которые уже можно использовать."
  },
  orders: {
    icon: ScrollText,
    eyebrow: "контракты",
    title: "Заказы",
    body: "Активные договоры, следы, сдача результата и короткий статус мастера."
  },
  trade: {
    icon: Users,
    eyebrow: "обмен",
    title: "Обмен",
    body: "Предложения между игроками с подтверждением сторон."
  },
  gwent: {
    icon: Trophy,
    eyebrow: "гвинт",
    title: "Гвинт",
    body: "Колода, вызовы и партии, доступные в текущем акте."
  },
  sync: {
    icon: Wifi,
    eyebrow: "связь",
    title: "Состояние журнала",
    body: "Журнал показывает снимок, очередь телефона и события, которые должен подтвердить мастер."
  }
};

const witcherJournalQuickActions: ReadonlyArray<WitcherJournalQuickAction> = [
  { id: "qr", label: "QR", meta: "сцена", icon: Crosshair },
  { id: "inventory", label: "Инвентарь", meta: "оружие", icon: Swords },
  { id: "bag", label: "Сумка", meta: "предметы", icon: Package },
  { id: "orders", label: "Заказы", meta: "следы", icon: ScrollText },
  { id: "trade", label: "Обмен", meta: "игроки", icon: Users },
  { id: "gwent", label: "Гвинт", meta: "колода", icon: Trophy }
];

const witcherJournalNavItems: ReadonlyArray<{
  id: WitcherJournalPanelId | "journal";
  label: string;
  icon: LucideIcon;
}> = [
  { id: "journal", label: "Журнал", icon: BookOpen },
  { id: "qr", label: "QR", icon: Crosshair },
  { id: "inventory", label: "Инв.", icon: Swords },
  { id: "bag", label: "Сумка", icon: Package },
  { id: "orders", label: "Заказы", icon: ScrollText },
  { id: "gwent", label: "Гвинт", icon: Trophy }
];

const w7OrderTabs: ReadonlyArray<{ id: WitcherOrderTabId; label: string; shortLabel: string }> = [
  { id: "available", label: "Доступные", shortLabel: "Доступ" },
  { id: "mine", label: "Мои", shortLabel: "Мои" },
  { id: "addressed", label: "Адресные", shortLabel: "Личные" },
  { id: "history", label: "Архив", shortLabel: "Архив" }
];

const w7LordSealAssets: Record<WitcherLordSealAsset, string> = {
  north: w7LordSealNorth,
  river: w7LordSealRiver,
  forest: w7LordSealForest,
  hill: w7LordSealHill
};

const w7OrderNavItems: ReadonlyArray<{
  id: WitcherJournalPanelId | "journal";
  label: string;
  icon: LucideIcon;
}> = [
  { id: "journal", label: "Журнал", icon: BookOpen },
  { id: "qr", label: "QR", icon: Crosshair },
  { id: "inventory", label: "Инв.", icon: Swords },
  { id: "bag", label: "Сумка", icon: Package },
  { id: "orders", label: "Заказы", icon: ScrollText },
  { id: "gwent", label: "Гвинт", icon: Trophy }
];

const w7BasePublicOrders: WitcherOrderReadModel[] = [
  {
    order_id: "ord_cursed_contract_trace",
    lord_id: "p_lord_1",
    lord_name: "Северная стража",
    lord_seal_asset: "north",
    visibility: "public",
    addressed_to_player_id: null,
    status: "available",
    title: "След проклятого договора",
    hook: "Улика у старой мельницы. Нужен ведьмак, который не боится печати.",
    location_hint: "Старая мельница у северной тропы",
    target_label: "проклятая печать",
    object_id_redacted: true,
    reward_label: "35g",
    escrow_status: "held",
    act: "Акт II",
    tier: "T3",
    competition_count: 2,
    accepted_by_me: false,
    result_event_id: null,
    conflict_state: "none",
    expires_at: "18:30",
    updated_at: "17:42"
  },
  {
    order_id: "ord_river_brooch",
    lord_id: "p_lord_2",
    lord_name: "Речные ворота",
    lord_seal_asset: "river",
    visibility: "public",
    addressed_to_player_id: null,
    status: "available",
    title: "Брошь под водой",
    hook: "Проверьте настил у реки и отметьте, кто трогал сундук.",
    location_hint: "Нижний мост у синего фонаря",
    target_label: "речная брошь",
    object_id_redacted: true,
    reward_label: "Карта",
    escrow_status: "held",
    act: "Акт II",
    tier: "T2",
    competition_count: 0,
    accepted_by_me: false,
    result_event_id: null,
    conflict_state: "none",
    expires_at: "19:00",
    updated_at: "17:35"
  },
  {
    order_id: "ord_blackwood_nest",
    lord_id: "p_lord_3",
    lord_name: "Лесная марка",
    lord_seal_asset: "forest",
    visibility: "public",
    addressed_to_player_id: null,
    status: "available",
    title: "Гнездо в чернолесье",
    hook: "Сначала найдите метку на коре. Награда держится в escrow.",
    location_hint: "Чернолесье за старым колодцем",
    target_label: "гнездо твари",
    object_id_redacted: true,
    reward_label: "Артефакт",
    escrow_status: "locked",
    act: "Акт II",
    tier: "T3",
    competition_count: 1,
    accepted_by_me: false,
    result_event_id: null,
    conflict_state: "none",
    expires_at: "18:10",
    updated_at: "17:21"
  },
  {
    order_id: "ord_ferry_ghost",
    lord_id: "p_lord_4",
    lord_name: "Каменная корона",
    lord_seal_asset: "hill",
    visibility: "public",
    addressed_to_player_id: null,
    status: "available",
    title: "Призрак у переправы",
    hook: "Спросите сторожа и проверьте знак на цепи.",
    location_hint: "Старая переправа у склона",
    target_label: "след призрака",
    object_id_redacted: true,
    reward_label: "25g",
    escrow_status: "none",
    act: "Акт II",
    tier: "T2",
    competition_count: 0,
    accepted_by_me: false,
    result_event_id: null,
    conflict_state: "none",
    expires_at: "20:00",
    updated_at: "17:08"
  }
];

const w7AddressedOrder: WitcherOrderReadModel = {
  order_id: "ord_personal_sealed_letter",
  lord_id: "p_lord_2",
  lord_name: "Речные ворота",
  lord_seal_asset: "river",
  visibility: "addressed",
  addressed_to_player_id: "p_witcher_1",
  status: "addressed",
  title: "Письмо без подписи",
  hook: "Лорд просит прийти одному. В записке только место и печать.",
  location_hint: "Тихий причал за нижним мостом",
  target_label: "запечатанное письмо",
  object_id_redacted: true,
  reward_label: "Легенд.",
  escrow_status: "locked",
  act: "Акт II",
  tier: "T3",
  competition_count: 0,
  accepted_by_me: false,
  result_event_id: null,
  conflict_state: "none",
  expires_at: "18:45",
  updated_at: "17:50"
};

const w7AcceptedOrder: WitcherOrderReadModel = {
  order_id: "ord_my_mill_contract",
  lord_id: "p_lord_1",
  lord_name: "Северная стража",
  lord_seal_asset: "north",
  visibility: "public",
  addressed_to_player_id: null,
  status: "accepted",
  title: "След у старой мельницы",
  hook: "QR найден. Можно сдать результат после sync события.",
  location_hint: "Старая мельница у северной тропы",
  target_label: "проклятая печать",
  object_id_redacted: true,
  reward_label: "35g",
  escrow_status: "held",
  act: "Акт II",
  tier: "T3",
  competition_count: 1,
  accepted_by_me: true,
  result_event_id: "evt_local_mill_success",
  conflict_state: "none",
  expires_at: "18:30",
  updated_at: "17:54"
};

const w7QrNeededOrder: WitcherOrderReadModel = {
  ...w7BasePublicOrders[1],
  order_id: "ord_my_river_qr_needed",
  status: "accepted",
  accepted_by_me: true,
  result_event_id: null,
  competition_count: 0,
  hook: "Сначала дойдите до объекта и запустите QR или ручной код на месте."
};

const w7PendingSyncOrder: WitcherOrderReadModel = {
  ...w7AcceptedOrder,
  order_id: "ord_pending_sync_reward",
  status: "submitted_pending_sync",
  title: "Сдать печать мельницы",
  hook: "Локальный результат есть, сервер еще не применил событие.",
  reward_label: "35g",
  updated_at: "17:57"
};

const w7ConflictOrder: WitcherOrderReadModel = {
  ...w7BasePublicOrders[0],
  order_id: "ord_object_conflict_mill",
  status: "object_conflict",
  title: "След проклятого договора",
  hook: "У тебя уже есть контракт на этот объект. Нужен выбор или мастер.",
  competition_count: 2,
  conflict_state: "object_conflict",
  updated_at: "17:58"
};

const w7ReviewOrder: WitcherOrderReadModel = {
  ...w7AcceptedOrder,
  order_id: "ord_master_review_lock",
  status: "pending_master_approval",
  title: "Знак в запертой сумке",
  hook: "Награда и объект закрыты до решения мастера.",
  reward_label: "Легенд.",
  escrow_status: "locked",
  conflict_state: "pending_master_approval",
  updated_at: "17:59"
};

const w7ContestedOrder: WitcherOrderReadModel = {
  ...w7BasePublicOrders[2],
  order_id: "ord_contested_review",
  status: "contested_review",
  title: "Спор за чернолесье",
  hook: "Два следа сошлись на одном объекте. Решит мастер.",
  reward_label: "Артефакт",
  escrow_status: "locked",
  conflict_state: "contested_review",
  competition_count: 2,
  updated_at: "18:01"
};

const w7CompletedOrder: WitcherOrderReadModel = {
  ...w7BasePublicOrders[3],
  order_id: "ord_completed_ferry",
  status: "completed",
  title: "Переправа закрыта",
  hook: "Результат принят. Запись оставлена для истории.",
  reward_label: "25g",
  accepted_by_me: true,
  result_event_id: "evt_ferry_done",
  updated_at: "16:42"
};

const w7OrderBoards: Record<WitcherOrdersStateId, WitcherOrderBoard> = {
  normal: {
    state_id: "normal",
    player_id: "p_witcher_1",
    sync_label: "сеть",
    sync_tone: "online",
    my_count: 2,
    new_count: 4,
    default_tab: "available",
    selected_order_id: "ord_cursed_contract_trace",
    offline: false,
    orders: [...w7BasePublicOrders, w7AcceptedOrder, w7AddressedOrder, w7CompletedOrder]
  },
  addressed: {
    state_id: "addressed",
    player_id: "p_witcher_1",
    sync_label: "сеть",
    sync_tone: "online",
    my_count: 1,
    new_count: 3,
    default_tab: "addressed",
    selected_order_id: "ord_personal_sealed_letter",
    offline: false,
    orders: [w7AddressedOrder, ...w7BasePublicOrders.slice(1), w7AcceptedOrder]
  },
  accepted: {
    state_id: "accepted",
    player_id: "p_witcher_1",
    sync_label: "сеть",
    sync_tone: "online",
    my_count: 2,
    new_count: 3,
    default_tab: "mine",
    selected_order_id: "ord_my_mill_contract",
    offline: false,
    orders: [w7AcceptedOrder, w7QrNeededOrder, ...w7BasePublicOrders.slice(2), w7CompletedOrder]
  },
  conflict: {
    state_id: "conflict",
    player_id: "p_witcher_1",
    sync_label: "спор",
    sync_tone: "review",
    my_count: 2,
    new_count: 3,
    default_tab: "available",
    selected_order_id: "ord_object_conflict_mill",
    offline: false,
    orders: [w7ConflictOrder, w7AcceptedOrder, ...w7BasePublicOrders.slice(1), w7ContestedOrder]
  },
  review: {
    state_id: "review",
    player_id: "p_witcher_1",
    sync_label: "спор",
    sync_tone: "review",
    my_count: 3,
    new_count: 2,
    default_tab: "mine",
    selected_order_id: "ord_master_review_lock",
    offline: false,
    orders: [w7ReviewOrder, w7PendingSyncOrder, w7ContestedOrder, ...w7BasePublicOrders.slice(1, 3)]
  },
  offline: {
    state_id: "offline",
    player_id: "p_witcher_1",
    sync_label: "нет",
    sync_tone: "offline",
    my_count: 2,
    new_count: 4,
    default_tab: "available",
    selected_order_id: "ord_cursed_contract_trace",
    offline: true,
    orders: [w7AcceptedOrder, ...w7BasePublicOrders, w7AddressedOrder, w7PendingSyncOrder]
  }
};

const witcherJournalMockPlayerStates: Record<WitcherJournalStateId, WitcherPlayerState> = {
  normal: {
    player_id: "p_witcher_1",
    display_name: "Эскель из Каэр Морхена",
    role_type: "witcher",
    portrait_asset: "w1_witcher_portrait_v2",
    level: 4,
    xp: 135,
    xp_next: 175,
    gold: 999,
    current_act: "Акт II",
    reputation_descriptor: "опасная слава",
    sync_status: "synced",
    pending_events_count: 0,
    review_count: 0,
    locked_rewards_count: 0,
    personal_goals: [
      {
        goal_id: "goal_cursed_contract",
        title: "Найти след проклятого договора",
        progress_hint: "Проверить знак у старой переправы"
      },
      {
        goal_id: "goal_silver_witness",
        title: "Расспросить серебряного свидетеля",
        progress_hint: "Осталась одна улика"
      }
    ],
    goal_tracks: [
      { goal_id: "goal_cursed_contract", current_value: 1, target_value: 3, state: "active" },
      { goal_id: "goal_silver_witness", current_value: 2, target_value: 4, state: "active" }
    ],
    revealed_final_hooks: [],
    locks: {}
  },
  offline: {
    player_id: "p_witcher_1",
    display_name: "Эскель из Каэр Морхена",
    role_type: "witcher",
    portrait_asset: "w1_witcher_portrait_v2",
    level: 4,
    xp: 135,
    xp_next: 175,
    gold: 999,
    current_act: "Акт II",
    reputation_descriptor: "опасная слава",
    sync_status: "offline_snapshot",
    pending_events_count: 0,
    review_count: 0,
    locked_rewards_count: 0,
    personal_goals: [
      {
        goal_id: "goal_cursed_contract",
        title: "Найти след проклятого договора",
        progress_hint: "Доступно из снимка"
      }
    ],
    goal_tracks: [{ goal_id: "goal_cursed_contract", current_value: 1, target_value: 3, state: "active" }],
    revealed_final_hooks: [],
    locks: {
      orders: "Wi-Fi",
      trade: "Wi-Fi",
      gwent: "Wi-Fi"
    }
  },
  pending: {
    player_id: "p_witcher_1",
    display_name: "Эскель из Каэр Морхена",
    role_type: "witcher",
    portrait_asset: "w1_witcher_portrait_v2",
    level: 4,
    xp: 135,
    xp_next: 175,
    gold: 999,
    current_act: "Акт II",
    reputation_descriptor: "опасная слава",
    sync_status: "pending_review",
    pending_events_count: 2,
    review_count: 1,
    locked_rewards_count: 1,
    personal_goals: [
      {
        goal_id: "goal_cursed_contract",
        title: "Найти след проклятого договора",
        progress_hint: "Ждет решения мастера"
      },
      {
        goal_id: "goal_locked_reward",
        title: "Забрать награду у переправы",
        progress_hint: "Награда закрыта"
      }
    ],
    goal_tracks: [
      { goal_id: "goal_cursed_contract", current_value: 2, target_value: 3, state: "active" },
      { goal_id: "goal_locked_reward", current_value: 1, target_value: 1, state: "locked" }
    ],
    revealed_final_hooks: [],
    locks: {
      bag: "Награда закрыта",
      orders: "Нужен мастер",
      trade: "Нужен мастер"
    }
  }
};

void PLAYER_STATE_ENDPOINT_BLOCKER;
void PLAYER_ORDER_BOARD_ENDPOINT_BLOCKER;

function getInitialWitcherJournalState(): WitcherJournalStateId {
  const state = new URLSearchParams(window.location.search).get("state") ?? "";
  const aliases: Record<string, WitcherJournalStateId> = {
    default: "normal",
    empty: "normal",
    online: "normal",
    reward: "pending",
    trade: "pending"
  };

  if (state in witcherJournalMockPlayerStates) {
    return state as WitcherJournalStateId;
  }

  return aliases[state] ?? "normal";
}

function getInitialWitcherMobileScreen(): WitcherMobileScreenId {
  const params = new URLSearchParams(window.location.search);
  const screen = params.get("screen") ?? "";
  if (screen === "orders" || window.location.pathname.endsWith("/orders")) {
    return "orders";
  }

  return "journal";
}

function getInitialWitcherJournalPanel(): WitcherJournalPanelId | null {
  const panel = new URLSearchParams(window.location.search).get("panel");
  return panel && panel in witcherJournalPanels ? (panel as WitcherJournalPanelId) : null;
}

function getInitialWitcherOrdersState(): WitcherOrdersStateId {
  const params = new URLSearchParams(window.location.search);
  const state = params.get("ordersState") ?? params.get("orderState") ?? params.get("state") ?? "";
  const aliases: Record<string, WitcherOrdersStateId> = {
    default: "normal",
    online: "normal",
    pending: "review",
    reward: "review",
    master: "review",
    contested: "conflict"
  };

  if (state in w7OrderBoards) {
    return state as WitcherOrdersStateId;
  }

  return aliases[state] ?? "normal";
}

function getInitialWitcherOrderTab(defaultTab: WitcherOrderTabId): WitcherOrderTabId {
  const tab = new URLSearchParams(window.location.search).get("tab") ?? "";
  return w7OrderTabs.some((candidate) => candidate.id === tab) ? (tab as WitcherOrderTabId) : defaultTab;
}

function mapPlayerStateToJournalView(player: WitcherPlayerState): WitcherJournalView {
  return {
    player,
    roleLabel: player.role_type === "witcher" ? "ведьмак" : "игрок",
    statusLine: statusLineForPlayerState(player),
    syncBadges: syncBadgesForPlayerState(player),
    goals: player.personal_goals.slice(0, 2).map((goal) => {
      const track = player.goal_tracks.find((candidate) => candidate.goal_id === goal.goal_id);
      const currentValue = track?.current_value ?? 0;
      const targetValue = Math.max(track?.target_value ?? 1, 1);
      return {
        id: goal.goal_id,
        title: goal.title,
        progress: goal.progress_hint,
        chip: track?.state === "locked" ? "Закрыто" : `${currentValue}/${targetValue}`,
        isLocked: track?.state === "locked"
      };
    })
  };
}

function syncBadgesForPlayerState(player: WitcherPlayerState): string[] {
  if (player.sync_status === "synced") {
    return ["Синхронизировано", "Очередь пуста"];
  }

  if (player.sync_status === "offline_snapshot") {
    return ["Офлайн-снимок", "Wi-Fi нужен"];
  }

  return [
    `${player.pending_events_count} события ждут`,
    player.review_count > 0 ? "Нужен мастер" : "Очередь",
    player.locked_rewards_count > 0 ? "Награда закрыта" : "Без наград"
  ];
}

function statusLineForPlayerState(player: WitcherPlayerState): string {
  if (player.review_count > 0) {
    return "Нужен мастер";
  }

  if (player.pending_events_count > 0) {
    return `${player.pending_events_count} события ждут`;
  }

  if (player.sync_status === "offline_snapshot") {
    return "Офлайн-снимок";
  }

  return "Готов к заказу";
}

function panelForState(panelId: WitcherJournalPanelId, view: WitcherJournalView): WitcherJournalPanel {
  const panel = witcherJournalPanels[panelId];
  if (panelId === "sync") {
    return {
      ...panel,
      body: view.syncBadges.join(" · ")
    };
  }

  const lockHint = view.player.locks[panelId as WitcherJournalQuickActionId];
  if (lockHint) {
    return {
      ...panel,
      body: `${panel.body} Сейчас: ${lockHint}.`
    };
  }

  return panel;
}

function isOrderInTab(order: WitcherOrderReadModel, tab: WitcherOrderTabId): boolean {
  if (tab === "available") {
    return order.visibility === "public" && !order.accepted_by_me && order.status !== "completed";
  }

  if (tab === "mine") {
    return order.accepted_by_me || order.status === "submitted_pending_sync" || order.status === "pending_master_approval";
  }

  if (tab === "addressed") {
    return order.visibility === "addressed";
  }

  return order.status === "completed" || order.status === "submitted_pending_sync";
}

function statusLabelForOrder(order: WitcherOrderReadModel, board: WitcherOrderBoard): string {
  if (board.offline) {
    return "Офлайн-снимок";
  }

  const labels: Record<WitcherOrderStatus, string> = {
    available: "Свободен",
    addressed: "Личный",
    accepted: "Взят",
    submitted_pending_sync: "Ждет sync",
    pending_master_approval: "Ждет мастера",
    contested_review: "Спор",
    object_conflict: "Спор",
    completed: "Сдан"
  };
  return labels[order.status];
}

function toneForOrder(order: WitcherOrderReadModel, board: WitcherOrderBoard): string {
  if (board.offline) {
    return "offline";
  }

  if (order.status === "pending_master_approval" || order.status === "submitted_pending_sync") {
    return "pending";
  }

  if (order.status === "contested_review" || order.status === "object_conflict") {
    return "conflict";
  }

  if (order.status === "accepted" || order.status === "completed") {
    return "accepted";
  }

  if (order.visibility === "addressed") {
    return "addressed";
  }

  return "available";
}

function primaryActionForOrder(order: WitcherOrderReadModel | null, board: WitcherOrderBoard) {
  if (!order) {
    return { label: "Выберите контракт", hint: "", disabled: true, icon: ScrollText };
  }

  if (board.offline) {
    return { label: "Подробнее", hint: "Офлайн-снимок: действия недоступны", disabled: true, icon: LockKeyhole };
  }

  if (order.status === "available") {
    return { label: "Взять", hint: "Контракт свободен", disabled: false, icon: CheckCircle2 };
  }

  if (order.status === "addressed") {
    return { label: "Принять", hint: "Личный заказ", disabled: false, icon: CheckCircle2 };
  }

  if (order.status === "accepted") {
    return {
      label: order.result_event_id ? "Сдать" : "К QR",
      hint: order.result_event_id ? "Результат готов" : "Нужен объект",
      disabled: false,
      icon: order.result_event_id ? Send : Crosshair
    };
  }

  return { label: "Подробнее", hint: statusLabelForOrder(order, board), disabled: false, icon: FileWarning };
}

function orderReviewText(order: WitcherOrderReadModel, board: WitcherOrderBoard): string {
  if (board.offline) {
    return "Доска доступна из последнего снимка. Взять или сдать можно после связи.";
  }

  if (order.conflict_state === "object_conflict") {
    return "У тебя уже есть контракт на этот объект";
  }

  if (order.conflict_state === "contested_review") {
    return "Решит мастер";
  }

  if (order.conflict_state === "pending_master_approval") {
    return "Награда и объект закрыты до решения мастера";
  }

  if (order.status === "submitted_pending_sync") {
    return "Локальный результат ждет sync";
  }

  return order.escrow_status === "locked" ? "Эскроу закрыт до подтверждения" : "";
}

function useCountUp(value: number, reducedMotion: boolean | null) {
  const [displayValue, setDisplayValue] = useState(() => (reducedMotion ? value : 0));

  useEffect(() => {
    if (reducedMotion) {
      setDisplayValue(value);
      return;
    }

    let frame = 0;
    let stopped = false;
    const duration = 650;
    const startedAt = performance.now();
    setDisplayValue(0);

    const tick = (time: number) => {
      if (stopped) {
        return;
      }

      const ratio = Math.min((time - startedAt) / duration, 1);
      const eased = 1 - Math.pow(1 - ratio, 3);
      setDisplayValue(Math.round(value * eased));

      if (ratio < 1) {
        frame = requestAnimationFrame(tick);
      }
    };

    frame = requestAnimationFrame(tick);
    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
    };
  }, [reducedMotion, value]);

  return displayValue;
}

export function WitcherJournalScreenV2() {
  const prefersReducedMotion = useReducedMotion();
  const journalStateId = getInitialWitcherJournalState();
  const playerState = witcherJournalMockPlayerStates[journalStateId];
  const view = mapPlayerStateToJournalView(playerState);
  const animatedXp = useCountUp(view.player.xp, prefersReducedMotion);
  const animatedGold = useCountUp(view.player.gold, prefersReducedMotion);
  const [activePanel, setActivePanel] = useState<WitcherJournalPanelId | null>(() => getInitialWitcherJournalPanel());
  const [mobileScreen, setMobileScreen] = useState<WitcherMobileScreenId>(() => getInitialWitcherMobileScreen());
  const activeTarget = activePanel ? panelForState(activePanel, view) : null;
  const ActiveIcon = activeTarget?.icon;

  const setPanelRoute = (panel: WitcherJournalPanelId | null) => {
    const versionSuffix = "version=v2";
    const stateSuffix = journalStateId === "normal" ? "" : `state=${journalStateId}`;
    const params = [versionSuffix, stateSuffix, panel ? `panel=${panel}` : ""].filter(Boolean).join("&");
    const nextUrl = params ? `/mobile/witcher/journal?${params}` : "/mobile/witcher/journal";
    window.history.replaceState(null, "", nextUrl);
  };

  const openOrdersScreen = () => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    const params = new URLSearchParams();
    params.set("version", "v2");
    if (journalStateId !== "normal") {
      params.set("state", journalStateId);
    }
    setActivePanel(null);
    setMobileScreen("orders");
    window.history.replaceState(null, "", `/mobile/witcher/orders?${params.toString()}`);
  };

  const openPanel = (panel: WitcherJournalPanelId) => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    setMobileScreen("journal");
    setActivePanel(panel);
    setPanelRoute(panel);
  };

  const closePanel = () => {
    setMobileScreen("journal");
    setActivePanel(null);
    setPanelRoute(null);
  };

  if (mobileScreen === "orders") {
    return (
      <W7OrdersScreen
        player={view.player}
        journalStateId={journalStateId}
        prefersReducedMotion={prefersReducedMotion}
        onBackToJournal={closePanel}
        onOpenJournalPanel={openPanel}
      />
    );
  }

  return (
    <main className="witcher-journal-page">
      <motion.div
        className="witcher-journal-screen"
        initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 18 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: prefersReducedMotion ? 0.01 : 0.42, ease: "easeOut" }}
      >
        <div className="witcher-journal-stage" aria-label="Журнал ведьмака">
          <img className="w1-bg-layer" src={w1JournalBg} alt="" draggable={false} />

          <section className="w1-character-zone" aria-label="Персонаж">
            <button className="w1-portrait-button" type="button" onClick={() => openPanel("profile")} aria-label="Открыть лист персонажа">
              <img className="w1-portrait-image" src={w1WitcherPortrait} alt="" draggable={false} />
              <img className="w1-portrait-frame" src={w1PortraitFrame} alt="" draggable={false} />
            </button>
            <button className="w1-header-plate" type="button" onClick={() => openPanel("profile")}>
              <img src={w1HeaderPlate} alt="" draggable={false} />
              <span className="w1-role">{view.roleLabel}</span>
              <strong className="w1-name">{view.player.display_name}</strong>
              <span className="w1-header-grid">
                <span>Ур. {view.player.level}</span>
                <span>{animatedXp} / {view.player.xp_next} XP</span>
                <span><Coins size={12} />{animatedGold}g</span>
                <span>{view.player.current_act}</span>
              </span>
            </button>
          </section>

          <button className={`w1-sync-zone is-${view.player.sync_status}`} type="button" onClick={() => openPanel("sync")}>
            <img src={w1SyncBadgeSet} alt="" draggable={false} />
            <span className="w1-reputation">
              <Shield size={13} />
              <span>{view.player.reputation_descriptor}</span>
            </span>
            <span className="w1-sync-badges">
              {view.syncBadges.map((badge) => (
                <em key={badge}>{badge}</em>
              ))}
            </span>
          </button>

          <motion.button
            className="w1-goals-zone"
            type="button"
            onClick={() => openPanel("goals")}
            whileTap={prefersReducedMotion ? undefined : { rotateX: 2, y: 2, scale: 0.992 }}
            aria-label="Открыть личные цели"
          >
            <img className="w1-goal-plaque" src={w1GoalPlaque} alt="" draggable={false} />
            <span className="w1-section-title">Личные цели</span>
            <span className="w1-goal-list">
              {view.goals.map((goal) => (
                <span key={goal.id} className={`w1-goal-row${goal.isLocked ? " is-locked" : ""}`}>
                  <span className="w1-goal-copy">
                    <strong>{goal.title}</strong>
                    <small>{goal.progress}</small>
                  </span>
                  <em>{goal.chip}</em>
                </span>
              ))}
            </span>
          </motion.button>

          <section className="w1-actions-zone" aria-label="Быстрые действия">
            {witcherJournalQuickActions.map((action) => {
              const Icon = action.icon;
              const lockHint = view.player.locks[action.id];
              return (
                <motion.button
                  key={action.id}
                  className={`w1-action-slot${lockHint ? " is-locked" : ""}`}
                  type="button"
                  onClick={() => {
                    if (action.id === "orders") {
                      openOrdersScreen();
                      return;
                    }
                    openPanel(action.id);
                  }}
                  whileTap={prefersReducedMotion ? undefined : { y: 3, scale: 0.965 }}
                  aria-label={lockHint ? `${action.label}: ${lockHint}` : action.label}
                >
                  <img src={w1ActionSlot} alt="" draggable={false} />
                  <Icon size={21} />
                  <span>{action.label}</span>
                  <small>{lockHint ?? action.meta}</small>
                  {lockHint ? (
                    <em className="w1-lock-mark" aria-hidden="true">
                      <AlertTriangle size={10} />
                    </em>
                  ) : null}
                </motion.button>
              );
            })}
          </section>

          <nav className="w1-bottom-nav" aria-label="Основная навигация">
            {witcherJournalNavItems.map((item) => {
              const Icon = item.icon;
              const isCurrent = item.id === "journal";
              return (
                <button
                  key={item.id}
                  className={`w1-nav-tab${isCurrent ? " is-current" : ""}`}
                  type="button"
                  onClick={() => {
                    if (item.id === "journal") {
                      closePanel();
                      return;
                    }
                    if (item.id === "orders") {
                      openOrdersScreen();
                      return;
                    }
                    openPanel(item.id);
                  }}
                  aria-current={isCurrent ? "page" : undefined}
                >
                  <img src={w1BottomNav} alt="" draggable={false} />
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <AnimatePresence>
            {activeTarget ? (
              <motion.aside
                className="w1-journal-sheet"
                initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, rotateY: -9, x: -18 }}
                animate={{ opacity: 1, rotateY: 0, x: 0 }}
                exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, rotateY: -7, x: -12 }}
                transition={{ type: "spring", stiffness: 260, damping: 30 }}
                aria-label={activeTarget.title}
              >
                <img className="w1-sheet-art" src={w1GoalPlaque} alt="" draggable={false} />
                <button className="w1-sheet-close" type="button" onClick={closePanel} aria-label="Закрыть">
                  ×
                </button>
                <span className="w1-sheet-icon">{ActiveIcon ? <ActiveIcon size={22} /> : null}</span>
                <span className="w1-sheet-eyebrow">{activeTarget.eyebrow}</span>
                <strong>{activeTarget.title}</strong>
                <p>{activeTarget.body}</p>
                <span className="w1-sheet-status">
                  {view.statusLine}
                  {view.player.locked_rewards_count > 0 ? " · награда закрыта" : ""}
                </span>
                <button className="w1-sheet-action" type="button" onClick={closePanel}>
                  Вернуться
                </button>
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </div>
      </motion.div>
    </main>
  );
}

type W7OrdersScreenProps = {
  player: WitcherPlayerState;
  journalStateId: WitcherJournalStateId;
  prefersReducedMotion: boolean | null;
  onBackToJournal: () => void;
  onOpenJournalPanel: (panel: WitcherJournalPanelId) => void;
};

function W7OrdersScreen({
  player,
  journalStateId,
  prefersReducedMotion,
  onBackToJournal,
  onOpenJournalPanel
}: W7OrdersScreenProps) {
  const [ordersStateId] = useState<WitcherOrdersStateId>(() => getInitialWitcherOrdersState());
  const board = w7OrderBoards[ordersStateId];
  const [activeTab, setActiveTab] = useState<WitcherOrderTabId>(() => getInitialWitcherOrderTab(board.default_tab));
  const initialOrderFromQuery = new URLSearchParams(window.location.search).get("order");
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(() => {
    if (initialOrderFromQuery && board.orders.some((order) => order.order_id === initialOrderFromQuery)) {
      return initialOrderFromQuery;
    }
    return board.selected_order_id;
  });
  const [isDetailOpen, setIsDetailOpen] = useState(() => new URLSearchParams(window.location.search).get("detail") === "1");

  const visibleOrders = useMemo(
    () => board.orders.filter((order) => isOrderInTab(order, activeTab)).slice(0, 4),
    [activeTab, board]
  );

  useEffect(() => {
    if (visibleOrders.length === 0) {
      setSelectedOrderId(null);
      return;
    }

    if (!selectedOrderId || !visibleOrders.some((order) => order.order_id === selectedOrderId)) {
      setSelectedOrderId(visibleOrders[0].order_id);
    }
  }, [selectedOrderId, visibleOrders]);

  const selectedOrder =
    board.orders.find((order) => order.order_id === selectedOrderId) ?? visibleOrders[0] ?? null;
  const primaryAction = primaryActionForOrder(selectedOrder, board);
  const PrimaryActionIcon = primaryAction.icon;
  const reviewText = selectedOrder ? orderReviewText(selectedOrder, board) : "";

  const updateOrdersRoute = (tab: WitcherOrderTabId, orderId: string | null = selectedOrderId) => {
    const params = new URLSearchParams();
    params.set("version", "v2");
    params.set("ordersState", ordersStateId);
    params.set("tab", tab);
    if (journalStateId !== "normal") {
      params.set("state", journalStateId);
    }
    if (orderId) {
      params.set("order", orderId);
    }
    window.history.replaceState(null, "", `/mobile/witcher/orders?${params.toString()}`);
  };

  const selectTab = (tab: WitcherOrderTabId) => {
    setActiveTab(tab);
    const nextOrder = board.orders.find((order) => isOrderInTab(order, tab))?.order_id ?? null;
    setSelectedOrderId(nextOrder);
    setIsDetailOpen(false);
    updateOrdersRoute(tab, nextOrder);
  };

  const selectOrder = (order: WitcherOrderReadModel) => {
    setSelectedOrderId(order.order_id);
    setIsDetailOpen(true);
    updateOrdersRoute(activeTab, order.order_id);
  };

  return (
    <main className="witcher-journal-page">
      <motion.div
        className="witcher-journal-screen"
        initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 18 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: prefersReducedMotion ? 0.01 : 0.42, ease: "easeOut" }}
      >
        <div className="witcher-journal-stage w7-orders-stage" aria-label="Заказы ведьмака">
          <img className="w7-bg-layer" src={w7OrdersBoardBg} alt="" draggable={false} />

          <header className="w7-topbar" aria-label="Панель заказов">
            <button className="w7-back-button" type="button" onClick={onBackToJournal} aria-label="Вернуться в журнал">
              <ArrowLeft size={14} />
              <span>Журнал</span>
            </button>
            <strong className="w7-title">Заказы</strong>
            <button className={`w7-sync-badge is-${board.sync_tone}`} type="button" onClick={() => onOpenJournalPanel("sync")}>
              <Wifi size={11} />
              <span>{board.sync_label}</span>
            </button>
            <div className="w7-counters" aria-label="Счетчики заказов">
              <span>Мои: {board.my_count}</span>
              <span>Новые: {board.new_count}</span>
            </div>
          </header>

          <nav className="w7-segment-tabs" aria-label="Разделы заказов">
            {w7OrderTabs.map((tab) => (
              <button
                key={tab.id}
                className={`w7-segment-tab${activeTab === tab.id ? " is-current" : ""}`}
                type="button"
                onClick={() => selectTab(tab.id)}
                aria-pressed={activeTab === tab.id}
              >
                <span className="w7-tab-full">{tab.label}</span>
                <span className="w7-tab-short">{tab.shortLabel}</span>
              </button>
            ))}
          </nav>

          <section className="w7-orders-list" aria-label="Список контрактов">
            {visibleOrders.map((order, index) => {
              const SealIcon = w7LordSealAssets[order.lord_seal_asset];
              const orderTone = toneForOrder(order, board);
              const isSelected = order.order_id === selectedOrder?.order_id;
              const hasConflictOverlay = order.conflict_state === "object_conflict" || order.conflict_state === "contested_review";
              const hasLockedOverlay =
                board.offline || order.status === "pending_master_approval" || order.status === "submitted_pending_sync";
              return (
                <motion.button
                  key={order.order_id}
                  className={`w7-order-slip is-${orderTone}${isSelected ? " is-selected" : ""}`}
                  type="button"
                  onClick={() => selectOrder(order)}
                  initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 18, rotate: index % 2 === 0 ? -1.5 : 1.2 }}
                  animate={{ opacity: 1, y: 0, rotate: 0 }}
                  transition={{ delay: prefersReducedMotion ? 0 : 0.04 * index, type: "spring", stiffness: 280, damping: 28 }}
                  whileTap={prefersReducedMotion ? undefined : { y: 3, scale: 0.99 }}
                  aria-pressed={isSelected}
                  aria-label={`${order.title}, ${statusLabelForOrder(order, board)}`}
                >
                  <img className="w7-slip-art" src={w7ContractSlip} alt="" draggable={false} />
                  {order.visibility === "addressed" ? (
                    <span className="w7-addressed-ribbon" aria-label="Личный заказ">
                      <img src={w7AddressedRibbon} alt="" draggable={false} />
                      <span>Личный</span>
                    </span>
                  ) : null}
                  {hasConflictOverlay ? <img className="w7-slip-overlay is-conflict" src={w7ConflictOverlay} alt="" draggable={false} /> : null}
                  {hasLockedOverlay ? <img className="w7-slip-overlay is-locked" src={w7LockedBadge} alt="" draggable={false} /> : null}
                  <span className="w7-slip-content">
                    <span className="w7-order-seal">
                      <img src={SealIcon} alt="" draggable={false} />
                    </span>
                    <span className="w7-order-main">
                      <span className="w7-order-topline">
                        <strong>{order.title}</strong>
                        <em>{order.act}</em>
                      </span>
                      <span className="w7-order-lord">{order.lord_name}</span>
                      <span className="w7-order-hook">{order.hook} {order.location_hint}</span>
                      <span className="w7-order-bottomline">
                        <span className="w7-chip w7-reward-chip">
                          <img src={w7RewardChip} alt="" draggable={false} />
                          <span>{order.reward_label}</span>
                        </span>
                        <span className={`w7-chip w7-status-chip is-${orderTone}`}>{statusLabelForOrder(order, board)}</span>
                        <span className="w7-chip w7-tier-chip">{order.tier}</span>
                        <span className="w7-competition">
                          <Layers size={11} />
                          <span>{order.competition_count > 0 ? `еще ${order.competition_count}` : "один"}</span>
                        </span>
                      </span>
                    </span>
                  </span>
                </motion.button>
              );
            })}

            {visibleOrders.length === 0 ? (
              <div className="w7-order-empty">
                <ScrollText size={18} />
                <span>Нет контрактов</span>
              </div>
            ) : null}
          </section>

          <section className="w7-primary-zone" aria-label="Действие выбранного заказа">
            {selectedOrder ? (
              <>
                <span className="w7-selected-summary">
                  <strong>{selectedOrder.title}</strong>
                  <small>{primaryAction.hint || statusLabelForOrder(selectedOrder, board)}</small>
                </span>
                <button className="w7-primary-action" type="button" disabled={primaryAction.disabled} onClick={() => setIsDetailOpen(true)}>
                  <PrimaryActionIcon size={17} />
                  <span>{primaryAction.label}</span>
                </button>
              </>
            ) : (
              <span className="w7-no-selection">Выберите контракт</span>
            )}
          </section>

          <nav className="w1-bottom-nav w7-bottom-nav" aria-label="Основная навигация">
            {w7OrderNavItems.map((item) => {
              const Icon = item.icon;
              const isCurrent = item.id === "orders";
              return (
                <button
                  key={item.id}
                  className={`w1-nav-tab w7-nav-tab${isCurrent ? " is-current" : ""}`}
                  type="button"
                  onClick={() => {
                    if (item.id === "orders") {
                      setIsDetailOpen(false);
                      return;
                    }
                    if (item.id === "journal") {
                      onBackToJournal();
                      return;
                    }
                    onOpenJournalPanel(item.id);
                  }}
                  aria-current={isCurrent ? "page" : undefined}
                >
                  <img src={w1BottomNav} alt="" draggable={false} />
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <AnimatePresence>
            {isDetailOpen && selectedOrder ? (
              <motion.aside
                className={`w7-detail-sheet is-${toneForOrder(selectedOrder, board)}`}
                initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 170 }}
                animate={{ opacity: 1, y: 0 }}
                exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 150 }}
                transition={{ type: "spring", stiffness: 260, damping: 28 }}
                aria-label={`Подробности заказа ${selectedOrder.title}`}
              >
                <img className="w7-detail-art" src={w7DetailSheet} alt="" draggable={false} />
                <button className="w7-detail-close" type="button" onClick={() => setIsDetailOpen(false)} aria-label="Закрыть">
                  ×
                </button>
                <div className="w7-detail-content">
                  <span className="w7-detail-header">
                    <img src={w7LordSealAssets[selectedOrder.lord_seal_asset]} alt="" draggable={false} />
                    <span>
                      <small>{selectedOrder.lord_name}</small>
                      <strong>{selectedOrder.title}</strong>
                    </span>
                  </span>
                  <dl className="w7-detail-grid">
                    <div>
                      <dt>Заказчик</dt>
                      <dd>{selectedOrder.lord_name}</dd>
                    </div>
                    <div>
                      <dt>Крючок</dt>
                      <dd>{selectedOrder.hook}</dd>
                    </div>
                    <div>
                      <dt>Локация</dt>
                      <dd><MapPin size={12} /> {selectedOrder.location_hint}</dd>
                    </div>
                    <div>
                      <dt>Объект</dt>
                      <dd>{selectedOrder.target_label}</dd>
                    </div>
                    <div>
                      <dt>Награда</dt>
                      <dd>{selectedOrder.reward_label} · {selectedOrder.escrow_status === "none" ? "без эскроу" : "эскроу"}</dd>
                    </div>
                    <div>
                      <dt>Ограничения</dt>
                      <dd>{selectedOrder.act} · {selectedOrder.tier} · до {selectedOrder.expires_at}</dd>
                    </div>
                  </dl>
                  {reviewText ? (
                    <p className="w7-review-note">
                      <AlertTriangle size={13} />
                      <span>{reviewText}</span>
                    </p>
                  ) : null}
                  <p className="w7-detail-copy">
                    Длинное описание живет только здесь: проверьте место, подтвердите результат через QR или событие и не передавайте скрытые причины другим игрокам.
                  </p>
                  <div className="w7-detail-actions">
                    <button className="w7-detail-primary" type="button" disabled={primaryAction.disabled}>
                      <PrimaryActionIcon size={15} />
                      <span>{primaryAction.label}</span>
                    </button>
                    {selectedOrder.status === "addressed" ? (
                      <button className="w7-detail-secondary" type="button">
                        <XCircle size={14} />
                        <span>Отклонить</span>
                      </button>
                    ) : null}
                    {selectedOrder.status === "accepted" ? (
                      <button className="w7-detail-secondary" type="button">
                        <Clock3 size={14} />
                        <span>Отказаться</span>
                      </button>
                    ) : null}
                  </div>
                </div>
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </div>
      </motion.div>
    </main>
  );
}
