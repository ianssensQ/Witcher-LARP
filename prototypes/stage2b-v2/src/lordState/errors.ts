const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

export const lordReasonCodeMessages: Record<string, string> = {
  active_stack_not_found: "Пачка армии не найдена",
  ai_not_available: "Нейтральный ход сейчас недоступен",
  already_at_target: "Армия уже здесь",
  army_capacity_exceeded: "В армии не хватает места",
  army_not_at_territory: "Армия героя в другой локации",
  battle_finished: "Бой уже завершен",
  battle_not_found: "Бой сейчас недоступен",
  battle_not_visible: "Этот бой недоступен вашему дому",
  building_already_owned: "Постройка уже возведена",
  building_not_found: "Постройка недоступна",
  deployment_card_not_in_hand: "Этой карты нет в руке выставления",
  duplicate_active_effect: "Цель уже под таким эффектом",
  friendly_fire: "Нельзя атаковать свой отряд",
  final_lock: "Финал закрыл новые действия",
  final_lock_orders_closed: "Финал закрыл новые заказы",
  forbidden_residence_target: "В чужую резиденцию ход закрыт",
  fort_capacity_exceeded: "В гарнизоне не хватает места",
  garrison_capacity_full: "В гарнизоне нет свободного слота",
  garrison_stack_not_found: "Пачка гарнизона не найдена",
  insufficient_escrow_gold: "В казне не хватает награды",
  insufficient_garrison: "В гарнизоне нет такой пачки",
  insufficient_gold: "Недостаточно золота",
  insufficient_mp: "Недостаточно MP",
  insufficient_raid_tokens: "Нет рейдового жетона",
  insufficient_stock: "Нет накопленного найма для этого отряда",
  invalid_addressed_target: "Адресат недоступен для заказа",
  invalid_count: "Количество должно быть больше нуля",
  invalid_route: "Маршрут недоступен",
  invalid_side: "Сторона боя недоступна",
  invalid_target: "Цель не подходит для этого действия",
  illegal_attack: "Цель вне дальности или без линии удара",
  illegal_hero_attack: "Ставка героя вне дальности или без линии удара",
  map_node_not_found: "Цель пути сейчас недоступна",
  master_required: "Для этой стороны нужен мастер",
  missing_actor_token: "Нужно заново войти как лорд",
  missing_active_army: "Нужна армия героя на этой территории",
  missing_attacker_army: "Для боя нужна активная армия",
  missing_card_id: "Карта не выбрана",
  missing_defender_army: "У цели нет доступной защиты для боя",
  missing_offer: "Предложение найма не выбрано",
  missing_route: "Цель похода не выбрана",
  missing_stack_id: "Пачка не выбрана",
  missing_target: "Цель удара не выбрана",
  missing_territory_id: "Территория найма не выбрана",
  move_off_board: "Клетка вне поля боя",
  move_out_of_range: "Цель вне дальности хода",
  move_to_hero_cell: "Отряд не может встать в клетку героя",
  move_to_occupied_cell: "Клетка уже занята",
  no_active_battle: "Активного боя сейчас нет",
  no_active_stack: "В бою нет активного отряда",
  no_route: "Нет открытой дороги",
  not_active_side: "Сейчас ходит другая сторона",
  not_active_stack: "Сейчас ходит другой отряд",
  not_ai_turn: "Сейчас не ход нейтральной стороны",
  offer_held: "Предложение удерживает другой дом",
  offer_not_available: "Предложение найма уже недоступно",
  offer_not_found: "Предложение найма не найдено",
  order_already_in_progress: "Заказ уже в работе или закрыт",
  order_cap_exceeded: "Лимит активных заказов занят",
  order_object_conflict: "За этот объект уже идет поручение",
  pending_move_active: "Армия в пути",
  recruit_blocked_by_raid: "Найм в эту территорию заблокирован рейдом",
  reward_asset_locked: "Эта награда уже под замком",
  route_cost_mismatch: "Стоимость пути изменилась",
  route_stopped_at_front: "Поход остановится на первом рубеже",
  rule_locked: "Рейд закрыт постройками",
  same_domain: "Нужны разные стороны боя",
  stale_expected_cost: "Стоимость изменилась, обновите экран",
  stack_cannot_split: "Эту пачку нельзя разделить",
  stack_not_found: "Отряд боя не найден",
  target_destroyed: "Цель уже разбита",
  takeover_not_available: "Мастерский перехват здесь недоступен",
  territory_contested: "Спорная территория не принимает новобранцев",
  territory_node_not_found: "У этой земли нет точки на карте",
  territory_not_found: "Цель сейчас недоступна",
  territory_not_owned: "Эта территория не под контролем дома",
  unknown_action: "Такой боевой приказ недоступен",
  unknown_order_object: "Цель заказа сейчас недоступна",
  unsupported_unit_class: "Тип отряда не поддерживается",
  wrong_actor_domain: "Этот приказ не принадлежит вашему дому",
  wrong_stack_side: "Этот отряд принадлежит другой стороне"
};

const getStringField = (value: unknown, key: string) =>
  isRecord(value) && typeof value[key] === "string" ? String(value[key]) : "";

export const getLordApiReasonCode = (payload: unknown): string => {
  if (!isRecord(payload)) {
    return "";
  }

  const detail = payload.detail;
  const directCode =
    getStringField(payload, "reason_code") ||
    getStringField(payload, "code") ||
    getStringField(payload, "reason");

  if (directCode) {
    return directCode;
  }

  return (
    getStringField(detail, "reason_code") ||
    getStringField(detail, "code") ||
    getStringField(detail, "reason")
  );
};

export const getLordApiErrorMessage = (
  payload: unknown,
  fallback = "Действие не принято. Обновите экран или позовите мастера."
) => {
  const reasonCode = getLordApiReasonCode(payload);
  if (reasonCode && lordReasonCodeMessages[reasonCode]) {
    return lordReasonCodeMessages[reasonCode];
  }

  return fallback;
};

export const getLordClientErrorMessage = (
  error: unknown,
  fallback = "Связь с сервером потеряна. Экран открыт только для чтения."
) => {
  const message = error instanceof Error ? error.message.trim() : "";
  if (
    !message ||
    message.includes("Failed to fetch") ||
    message.includes("NetworkError") ||
    !/[^\x00-\x7F]/.test(message)
  ) {
    return fallback;
  }

  return message;
};
