import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Coins,
  Crosshair,
  Layers,
  Package,
  ScrollText,
  Swords,
  Trophy,
  Users,
  Wifi
} from "lucide-react";
import m1JournalActionButton from "../../assets/generated/mobile/m1-journal-v2/action-button-v1.png";
import m1JournalBg from "../../assets/generated/mobile/m1-journal-v2/journal-bg-v2.png";
import m1JournalMetalPlaque from "../../assets/generated/mobile/m1-journal-v2/metal-plaque-v1.png";
import m1JournalNavTab from "../../assets/generated/mobile/m1-journal-v2/nav-tab-v1.png";
import m1JournalParchmentCard from "../../assets/generated/mobile/m1-journal-v2/parchment-card-v1.png";
import m1JournalPortraitFrame from "../../assets/generated/mobile/m1-journal-v2/portrait-frame-cutout-v1.png";
import m1WitcherPortrait from "../../assets/generated/mobile/m1-journal-v2/witcher-portrait-v1.png";
import "./witcher-journal.css";

type WitcherJournalPanel = {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  body: string;
};

const witcherJournalPanels = {
  profile: {
    icon: Swords,
    eyebrow: "персонаж",
    title: "Карточка ведьмака",
    body: "Полный лист персонажа: уровень, опыт, репутация, травмы и известные сюжетные метки."
  },
  orders: {
    icon: ScrollText,
    eyebrow: "заказы",
    title: "Доска заказов",
    body: "Активные контракты, условия сдачи, награды и решения мастера по спорным сценам."
  },
  goals: {
    icon: BookOpen,
    eyebrow: "цели",
    title: "Личные записи",
    body: "Сюда уходят личные цели, найденные улики и заметки, которые не должны теряться в общем потоке."
  },
  qr: {
    icon: Crosshair,
    eyebrow: "оффлайн",
    title: "Сканирование QR",
    body: "Камера открывает PvE-сцену без сети. Итог сцены сохранится в журнале и синхронизируется позже."
  },
  reward: {
    icon: Coins,
    eyebrow: "награда",
    title: "Награда закрыта",
    body: "Монеты и предметы попадут в сумку после подтверждения мастером или успешной оффлайн-сцены."
  },
  trade: {
    icon: Users,
    eyebrow: "обмен",
    title: "Трейд",
    body: "Предложение обмена откроется отдельным листом: что отдаешь, что получаешь и кто подтверждает сделку."
  },
  bag: {
    icon: Package,
    eyebrow: "сумка",
    title: "Сумка",
    body: "Предметы, зелья, артефакты, квестовые вещи и закрытые награды лежат отдельно от оружия и защиты."
  },
  gwent: {
    icon: Trophy,
    eyebrow: "гвинт",
    title: "Гвинт и вызовы",
    body: "Колода, текущие вызовы, ожидание соперника и результат партии открываются из этой вкладки."
  },
  more: {
    icon: Layers,
    eyebrow: "еще",
    title: "Еще",
    body: "Инвентарь оружия и защиты, трейд, синхронизация, справка и выход из роли."
  },
  sync: {
    icon: Wifi,
    eyebrow: "связь",
    title: "Оффлайн-снимок",
    body: "Телефон хранит действия локально. Когда появится Wi-Fi игры, журнал отправит очередь на сервер."
  }
} satisfies Record<string, WitcherJournalPanel>;

type WitcherJournalPanelId = keyof typeof witcherJournalPanels;

type WitcherJournalQuickAction = {
  id: WitcherJournalPanelId;
  label: string;
  meta: string;
  icon: LucideIcon;
};

const witcherJournalNavItems = [
  { id: "journal", label: "Журнал", icon: BookOpen },
  { id: "orders", label: "Заказы", icon: ScrollText },
  { id: "bag", label: "Сумка", icon: Package },
  { id: "gwent", label: "Гвинт", icon: Trophy },
  { id: "more", label: "Еще", icon: Layers }
] as const;

type WitcherJournalStateId = "default" | "empty" | "reward" | "trade" | "online";

type WitcherJournalScenario = {
  act: string;
  syncLabel: string;
  syncMode: "offline" | "online";
  characterStatus: string;
  orderPanel: WitcherJournalPanelId;
  orderKicker: string;
  orderTitle: string;
  orderBody: string;
  orderFooter: string;
  goalKicker: string;
  goalTitle: string;
  goalBody: string;
  quickActions: WitcherJournalQuickAction[];
};

const witcherJournalStateScenarios = {
  default: {
    act: "Акт I",
    syncLabel: "оффлайн",
    syncMode: "offline",
    characterStatus: "Готов к заказу",
    orderPanel: "orders",
    orderKicker: "активный след",
    orderTitle: "Тварь у старой переправы",
    orderBody: "Собраны 2 улики · нужна проверка мастера",
    orderFooter: "Награда: 14 монет и редкий ингредиент",
    goalKicker: "личная цель",
    goalTitle: "Найти серебряную печать",
    goalBody: "След ведет к торгу и закрытой сумке",
    quickActions: [
      { id: "qr", label: "Скан QR", meta: "PvE оффлайн", icon: Crosshair },
      { id: "orders", label: "Активный заказ", meta: "след открыт", icon: ScrollText },
      { id: "trade", label: "Трейд", meta: "1 ответ", icon: Users }
    ]
  },
  empty: {
    act: "Акт I",
    syncLabel: "оффлайн",
    syncMode: "offline",
    characterStatus: "Свободен",
    orderPanel: "orders",
    orderKicker: "доска свободна",
    orderTitle: "Нет активного заказа",
    orderBody: "Можно взять контракт у мастера или просканировать QR на локации",
    orderFooter: "Новые следы появятся после синхронизации",
    goalKicker: "личная цель",
    goalTitle: "Найти серебряную печать",
    goalBody: "След ведет к торгу и закрытой сумке",
    quickActions: [
      { id: "qr", label: "Скан QR", meta: "найти сцену", icon: Crosshair },
      { id: "orders", label: "Доска", meta: "пусто", icon: ScrollText },
      { id: "bag", label: "Сумка", meta: "проверить", icon: Package }
    ]
  },
  reward: {
    act: "Акт I",
    syncLabel: "оффлайн",
    syncMode: "offline",
    characterStatus: "Ждет награду",
    orderPanel: "reward",
    orderKicker: "награда",
    orderTitle: "Награда ждет мастера",
    orderBody: "Заказ сдан, но монеты и предмет закрыты до подтверждения",
    orderFooter: "После проверки все попадет в сумку",
    goalKicker: "личная цель",
    goalTitle: "Найти серебряную печать",
    goalBody: "След ведет к торгу и закрытой сумке",
    quickActions: [
      { id: "reward", label: "Награда", meta: "ожидает", icon: Coins },
      { id: "bag", label: "Сумка", meta: "закрыто", icon: Package },
      { id: "qr", label: "Скан QR", meta: "доступно", icon: Crosshair }
    ]
  },
  trade: {
    act: "Акт I",
    syncLabel: "оффлайн",
    syncMode: "offline",
    characterStatus: "Есть обмен",
    orderPanel: "trade",
    orderKicker: "входящий трейд",
    orderTitle: "Мирон предлагает обмен",
    orderBody: "Отдать: коготь утопца · получить: масло против тварей",
    orderFooter: "Нужно подтвердить до конца акта",
    goalKicker: "личная цель",
    goalTitle: "Найти серебряную печать",
    goalBody: "След ведет к торгу и закрытой сумке",
    quickActions: [
      { id: "trade", label: "Трейд", meta: "принять", icon: Users },
      { id: "bag", label: "Сумка", meta: "предметы", icon: Package },
      { id: "orders", label: "Заказы", meta: "1 активен", icon: ScrollText }
    ]
  },
  online: {
    act: "Акт I",
    syncLabel: "онлайн",
    syncMode: "online",
    characterStatus: "Синхронизирован",
    orderPanel: "orders",
    orderKicker: "активный след",
    orderTitle: "Тварь у старой переправы",
    orderBody: "Очередь отправлена · мастер видит результат",
    orderFooter: "Синхронизировано 2 минуты назад",
    goalKicker: "личная цель",
    goalTitle: "Найти серебряную печать",
    goalBody: "След ведет к торгу и закрытой сумке",
    quickActions: [
      { id: "qr", label: "Скан QR", meta: "доступно", icon: Crosshair },
      { id: "orders", label: "Заказ", meta: "обновлен", icon: ScrollText },
      { id: "gwent", label: "Гвинт", meta: "вызов", icon: Trophy }
    ]
  }
} satisfies Record<WitcherJournalStateId, WitcherJournalScenario>;

function getInitialWitcherJournalPanel(): WitcherJournalPanelId | null {
  const panel = new URLSearchParams(window.location.search).get("panel");
  return panel && panel in witcherJournalPanels ? (panel as WitcherJournalPanelId) : null;
}

function getInitialWitcherJournalState(): WitcherJournalStateId {
  const state = new URLSearchParams(window.location.search).get("state");
  return state && state in witcherJournalStateScenarios ? (state as WitcherJournalStateId) : "default";
}

export function WitcherJournalScreenV1() {
  const prefersReducedMotion = useReducedMotion();
  const journalStateId = getInitialWitcherJournalState();
  const journalState = witcherJournalStateScenarios[journalStateId];
  const [activePanel, setActivePanel] = useState<WitcherJournalPanelId | null>(() => getInitialWitcherJournalPanel());
  const activeTarget = activePanel ? witcherJournalPanels[activePanel] : null;
  const ActiveIcon = activeTarget?.icon;

  const setPanelRoute = (panel: WitcherJournalPanelId | null) => {
    const stateSuffix = journalStateId === "default" ? "" : `state=${journalStateId}`;
    const params = [stateSuffix, panel ? `panel=${panel}` : ""].filter(Boolean).join("&");
    const nextUrl = params ? `/mobile/witcher/journal?${params}` : "/mobile/witcher/journal";
    window.history.replaceState(null, "", nextUrl);
  };

  const openPanel = (panel: WitcherJournalPanelId) => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    setActivePanel(panel);
    setPanelRoute(panel);
  };

  const closePanel = () => {
    setActivePanel(null);
    setPanelRoute(null);
  };

  return (
    <main className="witcher-journal-page">
      <div className="witcher-journal-screen">
        <div className="witcher-journal-stage" aria-label="Журнал ведьмака">
          <img className="m1-bg-layer" src={m1JournalBg} alt="" draggable={false} />

          <header className="m1-topbar" aria-label="Состояние журнала">
            <button className="m1-act-chip" type="button" onClick={() => openPanel("goals")}>
              <span>{journalState.act}</span>
            </button>
            <div className="m1-title-plaque" aria-current="page">
              <img src={m1JournalMetalPlaque} alt="" draggable={false} />
              <span>Журнал</span>
            </div>
            <button className={`m1-sync-chip is-${journalState.syncMode}`} type="button" onClick={() => openPanel("sync")} aria-label="Открыть состояние связи">
              <Wifi size={15} />
              <span>{journalState.syncLabel}</span>
            </button>
          </header>

          <motion.button
            className="m1-panel m1-character-card"
            type="button"
            onClick={() => openPanel("profile")}
            whileTap={prefersReducedMotion ? undefined : { y: 2, scale: 0.99 }}
            aria-label="Открыть карточку персонажа"
          >
            <img className="m1-panel-art" src={m1JournalParchmentCard} alt="" draggable={false} />
            <span className="m1-portrait-slot" aria-hidden="true">
              <span className="m1-portrait-glow" />
              <img className="m1-portrait-image" src={m1WitcherPortrait} alt="" draggable={false} />
              <span className="m1-portrait-mark"><Swords size={17} /></span>
              <img className="m1-portrait-frame" src={m1JournalPortraitFrame} alt="" draggable={false} />
            </span>
            <span className="m1-character-copy">
              <span className="m1-eyebrow">ведьмак</span>
              <strong>Эйрик</strong>
              <span>Уровень 3 · 18 опыта</span>
              <span>Репутация: нейтральная</span>
              <em>{journalState.characterStatus}</em>
            </span>
          </motion.button>

          <motion.button
            className="m1-panel m1-order-card"
            type="button"
            onClick={() => openPanel(journalState.orderPanel)}
            whileTap={prefersReducedMotion ? undefined : { y: 2, scale: 0.99 }}
            aria-label="Открыть активный заказ"
          >
            <img className="m1-panel-art" src={m1JournalParchmentCard} alt="" draggable={false} />
            <span className="m1-card-kicker">{journalState.orderKicker}</span>
            <strong>{journalState.orderTitle}</strong>
            <span>{journalState.orderBody}</span>
            <em>{journalState.orderFooter}</em>
          </motion.button>

          <motion.button
            className="m1-panel m1-goal-card"
            type="button"
            onClick={() => openPanel("goals")}
            whileTap={prefersReducedMotion ? undefined : { y: 2, scale: 0.99 }}
            aria-label="Открыть личные записи"
          >
            <img className="m1-panel-art" src={m1JournalParchmentCard} alt="" draggable={false} />
            <span className="m1-card-kicker">{journalState.goalKicker}</span>
            <strong>{journalState.goalTitle}</strong>
            <span>{journalState.goalBody}</span>
          </motion.button>

          <div className="m1-quick-actions" aria-label="Быстрые действия">
            {journalState.quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <motion.button
                  key={action.id}
                  className="m1-action-button"
                  type="button"
                  onClick={() => openPanel(action.id)}
                  whileTap={prefersReducedMotion ? undefined : { y: 3, scale: 0.96 }}
                >
                  <img src={m1JournalActionButton} alt="" draggable={false} />
                  <Icon size={21} />
                  <span>{action.label}</span>
                  <small>{action.meta}</small>
                </motion.button>
              );
            })}
          </div>

          <nav className="m1-bottom-nav" aria-label="Основная навигация">
            {witcherJournalNavItems.map((item) => {
              const Icon = item.icon;
              const isCurrent = item.id === "journal";
              return (
                <button
                  key={item.id}
                  className={`m1-nav-tab${isCurrent ? " is-current" : ""}`}
                  type="button"
                  onClick={() => {
                    if (isCurrent) {
                      closePanel();
                      return;
                    }
                    openPanel(item.id);
                  }}
                  aria-current={isCurrent ? "page" : undefined}
                >
                  <img src={m1JournalNavTab} alt="" draggable={false} />
                  <Icon size={17} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <AnimatePresence>
            {activeTarget ? (
              <motion.aside
                className="m1-destination-sheet"
                initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 28, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 24, scale: 0.98 }}
                transition={{ type: "spring", stiffness: 260, damping: 28 }}
                aria-label={activeTarget.title}
              >
                <img className="m1-sheet-art" src={m1JournalParchmentCard} alt="" draggable={false} />
                <button className="m1-sheet-close" type="button" onClick={closePanel} aria-label="Закрыть">
                  ×
                </button>
                <span className="m1-sheet-icon">{ActiveIcon ? <ActiveIcon size={22} /> : null}</span>
                <span className="m1-eyebrow">{activeTarget.eyebrow}</span>
                <strong>{activeTarget.title}</strong>
                <p>{activeTarget.body}</p>
                <button className="m1-sheet-action" type="button" onClick={closePanel}>
                  Вернуться
                </button>
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
