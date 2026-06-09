extends Control

signal navigate_requested(target: String)

const BASE_SIZE := Vector2(390, 844)

const PANELS := {
	"profile": {
		"eyebrow": "персонаж",
		"title": "Карточка ведьмака",
		"body": "Уровень, опыт, золото, репутация, травмы и известные сюжетные метки."
	},
	"orders": {
		"eyebrow": "заказы",
		"title": "Доска заказов",
		"body": "Активные контракты, условия сдачи, награды и решения мастера по спорным сценам."
	},
	"goals": {
		"eyebrow": "цели",
		"title": "Личные записи",
		"body": "Личные цели, найденные улики и заметки, которые не должны потеряться в общем потоке."
	},
	"qr": {
		"eyebrow": "оффлайн",
		"title": "QR / ручной ID",
		"body": "Переход к локальной PvE-сцене по QR или ручному коду без обязательной сети."
	},
	"bag": {
		"eyebrow": "сумка",
		"title": "Сумка",
		"body": "Предметы, зелья, артефакты, квестовые вещи и закрытые награды отдельно от оружия и защиты."
	},
	"gwent": {
		"eyebrow": "гвинт",
		"title": "Гвинт и вызовы",
		"body": "Колода, текущие вызовы, ожидание соперника и результат партии."
	},
	"trade": {
		"eyebrow": "обмен",
		"title": "Обмен",
		"body": "Предложение обмена: что отдаешь, что получаешь и кто подтверждает сделку."
	},
	"pvp": {
		"eyebrow": "дуэли",
		"title": "PVP",
		"body": "Вызовы другим игрокам, статус ожидания мастера и результат уже закрытых столкновений."
	},
	"sync": {
		"eyebrow": "связь",
		"title": "Оффлайн-снимок",
		"body": "Телефон хранит действия локально. Когда появится Wi-Fi игры, журнал отправит очередь на сервер."
	}
}

const BUTTON_PANELS := {
	"ActButton": "goals",
	"SyncButton": "sync",
	"CharacterButton": "profile",
	"OrderButton": "orders",
	"GoalButton": "goals",
	"QrActionButton": "qr",
	"OrdersActionButton": "orders",
	"TradeActionButton": "trade",
	"BagTabButton": "bag",
	"GwentTabButton": "gwent",
	"PvpTabButton": "pvp",
	"MoreTabButton": "sync"
}

const BUTTON_VISUALS := {
	"QrActionButton": ["QrActionTexture", "QrActionTitle"],
	"OrdersActionButton": ["OrdersActionTexture", "OrdersActionTitle"],
	"TradeActionButton": ["TradeActionTexture", "TradeActionTitle"],
	"BagTabButton": ["BagTabTexture", "BagTabLabel"],
	"GwentTabButton": ["GwentTabTexture", "GwentTabLabel"],
	"PvpTabButton": ["PvpTabTexture", "PvpTabLabel"],
	"MoreTabButton": ["MoreTabTexture", "MoreTabLabel"]
}

const ORDER_STATUS_PRIORITY := {
	"in_progress": 0,
	"accepted": 1,
	"claimed_at_prop": 2,
	"submitted_pending_sync": 3,
	"pending_master_approval": 4,
	"contested_review": 5,
	"failed_retryable": 6,
	"published": 7,
	"addressed_pending": 8,
	"completed": 9
}

const ORDER_STATUS_LABELS := {
	"published": "доступен",
	"addressed_pending": "адресован",
	"accepted": "принят",
	"in_progress": "в работе",
	"claimed_at_prop": "у цели",
	"submitted_pending_sync": "ждет связи",
	"pending_master_approval": "ждет мастера",
	"failed_retryable": "можно повторить",
	"contested_review": "спор",
	"completed": "закрыт"
}

const GOAL_STATE_LABELS := {
	"active": "активна",
	"completed": "выполнена",
	"failed": "провалена",
	"locked": "закрыта"
}

@onready var _stage: Control = $JournalStage
@onready var _role_label: Label = $JournalStage/RoleLabel
@onready var _character_name_label: Label = $JournalStage/CharacterNameLabel
@onready var _character_meta_label: Label = $JournalStage/CharacterMetaLabel
@onready var _character_rep_label: Label = $JournalStage/CharacterRepLabel
@onready var _character_status_label: Label = $JournalStage/CharacterStatusLabel
@onready var _gold_label: Label = $JournalStage/GoldLabel
@onready var _xp_bar_track: ColorRect = $JournalStage/XpBarTrack
@onready var _xp_bar_fill: ColorRect = $JournalStage/XpBarFill
@onready var _xp_label: Label = $JournalStage/XpLabel
@onready var _sync_badge_label: Label = $JournalStage/SyncBadgeLabel
@onready var _act_label: Label = $JournalStage/ActLabel
@onready var _order_kicker_label: Label = $JournalStage/OrderKickerLabel
@onready var _order_title_label: Label = $JournalStage/OrderTitleLabel
@onready var _order_body_label: Label = $JournalStage/OrderBodyLabel
@onready var _order_footer_label: Label = $JournalStage/OrderFooterLabel
@onready var _goal_kicker_label: Label = $JournalStage/GoalKickerLabel
@onready var _goal_title_label: Label = $JournalStage/GoalTitleLabel
@onready var _goal_body_label: Label = $JournalStage/GoalBodyLabel
@onready var _sheet: Control = $JournalStage/JournalSheet
@onready var _sheet_eyebrow: Label = $JournalStage/JournalSheet/SheetEyebrow
@onready var _sheet_title: Label = $JournalStage/JournalSheet/SheetTitle
@onready var _sheet_body: Label = $JournalStage/JournalSheet/SheetBody


func _ready() -> void:
	_connect_buttons()
	_close_panel()
	refresh_from_state()
	_layout_stage()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and _stage:
		_layout_stage()


func refresh_from_state() -> void:
	var player := AppState.current_player()
	if player.is_empty():
		_show_missing_player_state()
		return

	var character_name := str(player.get("display_name", "Игрок"))
	var level := str(player.get("level", 1))
	var xp_current := _to_int_value(player.get("xp", 0))
	var xp_window := _xp_window_for_player(player, xp_current, 100)
	var xp_progress := _to_int_value(xp_window.get("progress", xp_current))
	var xp_required := _to_int_value(xp_window.get("required", 100))
	var gold := _to_int_value(player.get("gold", 0))
	var reputation := AppState.player_reputation_display(player)
	var status := _status_from_sync()

	_role_label.text = _role_label_for_player(player)
	_character_name_label.text = character_name
	_character_meta_label.text = "Ур. %s" % level
	_gold_label.text = "◉ %s зол." % gold
	_xp_label.text = "XP %s/%s" % [xp_progress, xp_required]
	_set_xp_bar(xp_progress, xp_required)
	_character_rep_label.text = "Репутация: %s" % reputation
	_character_status_label.text = status
	_sync_badge_label.text = _sync_label()
	_act_label.text = _act_label_text()
	_refresh_order_card(player)
	_refresh_goal_card(player)


func _show_missing_player_state() -> void:
	_role_label.text = "НЕТ ВХОДА"
	_character_name_label.text = "Нет игрока"
	_character_meta_label.text = "Вход"
	_gold_label.text = "◉ -- зол."
	_xp_label.text = "XP --/--"
	_xp_bar_fill.size.x = 0.0
	_character_rep_label.text = "Репутация: --"
	_character_status_label.text = "Нужен вход"
	_sync_badge_label.text = _sync_label()
	_act_label.text = _act_label_text()
	_order_kicker_label.text = "АКТИВНЫЙ ЗАКАЗ"
	_order_title_label.text = "Войдите по коду"
	_order_body_label.text = "После входа появятся заказы игрока."
	_order_footer_label.text = "Нет данных"
	_goal_kicker_label.text = "ЛИЧНАЯ ЦЕЛЬ"
	_goal_title_label.text = "Войдите по коду"
	_goal_body_label.text = "Личная цель появится после загрузки игрока."


func _role_label_for_player(player: Dictionary) -> String:
	var role_type := _string_value(player.get("role_type", "")).strip_edges().to_lower()
	if role_type == "sorceress":
		return "ЧАРОДЕЙКА"
	if role_type == "witcher":
		return "ВЕДЬМАК"
	return "ИГРОК"


func _refresh_order_card(player: Dictionary) -> void:
	_order_kicker_label.text = "АКТИВНЫЙ ЗАКАЗ"
	var order := _active_order_for_player(_string_value(player.get("player_id", "")))
	if order.is_empty():
		_order_title_label.text = "Нет активного заказа"
		_order_body_label.text = "Проверь доску заказов или дождись лорда."
		_order_footer_label.text = "Награда появится позже"
		return

	_order_title_label.text = _order_title(order)
	_order_body_label.text = "Статус: %s" % _order_status_text(order)
	_order_footer_label.text = _order_reward_text(order)


func _refresh_goal_card(player: Dictionary) -> void:
	_goal_kicker_label.text = "ЛИЧНАЯ ЦЕЛЬ"
	var goal := _primary_goal_for_player(_string_value(player.get("player_id", "")))
	if goal.is_empty():
		_goal_title_label.text = "Цель не назначена"
		_goal_body_label.text = "Появится после входа по коду игрока."
		return

	_goal_title_label.text = _string_value(goal.get("public_text", "Личная цель"))
	_goal_body_label.text = _goal_progress_text(goal)


func _active_order_for_player(player_id: String) -> Dictionary:
	var orders: Variant = AppState.snapshot.get("orders", [])
	if typeof(orders) != TYPE_ARRAY:
		return {}

	var best_order := {}
	var best_priority := 1000
	for raw_order in orders:
		if typeof(raw_order) != TYPE_DICTIONARY:
			continue
		var order: Dictionary = raw_order
		if not _order_matches_player(order, player_id):
			continue
		var status := _string_value(order.get("status", "")).strip_edges().to_lower()
		var priority := int(ORDER_STATUS_PRIORITY.get(status, 100))
		if best_order.is_empty() or priority < best_priority:
			best_order = order
			best_priority = priority
	return best_order


func _order_matches_player(order: Dictionary, player_id: String) -> bool:
	if player_id.is_empty():
		return true
	var target_player_id := _string_value(order.get("target_player_id", ""))
	var accepted_by_player_id := _string_value(order.get("accepted_by_player_id", ""))
	var submitted_by_player_id := _string_value(order.get("submitted_by_player_id", ""))
	if player_id == target_player_id or player_id == accepted_by_player_id or player_id == submitted_by_player_id:
		return true
	return target_player_id.is_empty() and _string_value(order.get("visibility", "")).to_lower() == "public"


func _order_title(order: Dictionary) -> String:
	for key in ["object_label", "title", "object_id", "order_id"]:
		var value := _string_value(order.get(key, ""))
		if not value.is_empty():
			return value
	return "Заказ"


func _order_status_text(order: Dictionary) -> String:
	var status := _string_value(order.get("status", "")).strip_edges().to_lower()
	if status.is_empty():
		return "неизвестно"
	return _string_value(ORDER_STATUS_LABELS.get(status, status))


func _order_reward_text(order: Dictionary) -> String:
	var reward := _reward_for_order(order)
	if reward.is_empty():
		return "Награда уточняется"

	var parts := []
	var gold := _to_int_value(reward.get("gold", 0))
	var xp := _to_int_value(reward.get("xp", 0))
	if gold > 0:
		parts.append("%s зол." % gold)
	if xp > 0:
		parts.append("%s XP" % xp)
	if parts.is_empty():
		return "Награда уточняется"
	return "Награда: %s" % _join_parts(parts)


func _reward_for_order(order: Dictionary) -> Dictionary:
	var reward_id := _string_value(order.get("escrow_reward_id", ""))
	return _find_snapshot_row(AppState.snapshot.get("rewards", []), "reward_id", reward_id)


func _primary_goal_for_player(player_id: String) -> Dictionary:
	var goals: Variant = AppState.snapshot.get("goals", {})
	if typeof(goals) != TYPE_DICTIONARY:
		return {}
	var personal_goals: Variant = goals.get("personal_goals", [])
	if typeof(personal_goals) != TYPE_ARRAY:
		return {}
	for raw_goal in personal_goals:
		if typeof(raw_goal) != TYPE_DICTIONARY:
			continue
		var goal: Dictionary = raw_goal
		if player_id.is_empty() or _string_value(goal.get("player_id", "")) == player_id:
			return goal
	return {}


func _goal_progress_text(goal: Dictionary) -> String:
	var goal_id := _string_value(goal.get("goal_id", ""))
	var track := _goal_track(goal_id)
	if track.is_empty():
		return "Прогресс появится после события."

	var current_value := _to_int_value(track.get("current_value", 0))
	var target_value: int = int(max(_to_int_value(track.get("target_value", 1)), 1))
	var state := _string_value(track.get("state", "")).strip_edges().to_lower()
	var state_text := _string_value(GOAL_STATE_LABELS.get(state, state))
	if state_text.is_empty():
		state_text = "активна"
	return "Прогресс: %s/%s · %s" % [current_value, target_value, state_text]


func _goal_track(goal_id: String) -> Dictionary:
	var goals: Variant = AppState.snapshot.get("goals", {})
	if typeof(goals) != TYPE_DICTIONARY:
		return {}
	return _find_snapshot_row(goals.get("goal_tracks", []), "goal_id", goal_id)


func _find_snapshot_row(rows: Variant, key: String, value: String) -> Dictionary:
	if value.is_empty() or typeof(rows) != TYPE_ARRAY:
		return {}
	for raw_row in rows:
		if typeof(raw_row) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = raw_row
		if _string_value(row.get(key, "")) == value:
			return row
	return {}


func _join_parts(parts: Array) -> String:
	var text := ""
	for index in range(parts.size()):
		if index > 0:
			text += " · "
		text += _string_value(parts[index])
	return text


func _connect_buttons() -> void:
	for node_name in BUTTON_PANELS.keys():
		var button := _stage.get_node_or_null(node_name) as Button
		if button:
			button.pressed.connect(_open_panel.bind(str(BUTTON_PANELS[node_name])))
			if BUTTON_VISUALS.has(node_name):
				button.button_down.connect(_set_button_visual_pressed.bind(str(node_name), true))
				button.button_up.connect(_set_button_visual_pressed.bind(str(node_name), false))
				button.mouse_exited.connect(_set_button_visual_pressed.bind(str(node_name), false))

	var close_button := _sheet.get_node_or_null("SheetCloseButton") as Button
	if close_button:
		close_button.pressed.connect(_close_panel)


func _open_panel(panel_id: String) -> void:
	if not PANELS.has(panel_id):
		navigate_requested.emit(panel_id)
		return

	var panel: Dictionary = PANELS[panel_id]
	_sheet_eyebrow.text = str(panel.get("eyebrow", ""))
	_sheet_title.text = str(panel.get("title", ""))
	_sheet_body.text = str(panel.get("body", ""))
	_sheet.visible = true
	_sheet.move_to_front()


func _close_panel() -> void:
	_sheet.visible = false


func _set_xp_bar(xp_current: int, xp_target: int) -> void:
	var target: int = int(max(xp_target, 1))
	var ratio: float = clamp(float(xp_current) / float(target), 0.0, 1.0)
	var fill_width := 0.0
	if xp_current > 0:
		fill_width = max(4.0, (_xp_bar_track.size.x - 4.0) * ratio)
	_xp_bar_fill.size.x = fill_width


func _set_button_visual_pressed(node_name: String, is_pressed: bool) -> void:
	if not BUTTON_VISUALS.has(node_name):
		return

	var tint := Color(0.94, 0.82, 0.58, 1.0) if is_pressed else Color.WHITE
	for visual_name in BUTTON_VISUALS[node_name]:
		var visual := _stage.get_node_or_null(str(visual_name)) as CanvasItem
		if visual:
			visual.modulate = tint


func _layout_stage() -> void:
	if not _stage:
		return

	var available := size
	if available.x <= 0.0 or available.y <= 0.0:
		available = BASE_SIZE

	var scale_value: float = min(available.x / BASE_SIZE.x, available.y / BASE_SIZE.y)
	_stage.scale = Vector2(scale_value, scale_value)
	_stage.position = (available - BASE_SIZE * scale_value) * 0.5
	_stage.size = BASE_SIZE


func _sync_label() -> String:
	var sync := AppState.sync_status
	var status := str(sync.get("status", "offline"))
	if status == "synced":
		return "online"
	if int(sync.get("pending_count", 0)) > 0 or int(sync.get("queued_count", 0)) > 0:
		return "queue"
	return "offline"


func _status_from_sync() -> String:
	var sync := AppState.sync_status
	if int(sync.get("review_count", 0)) > 0:
		return "Ждет мастера"
	if int(sync.get("pending_count", 0)) > 0 or int(sync.get("queued_count", 0)) > 0:
		return "Есть очередь"
	return "Готов к заказу"


func _act_label_text() -> String:
	var acts = AppState.session.get("unlocked_acts", ["act1"])
	if typeof(acts) == TYPE_ARRAY and acts.has("act3"):
		return "Акт III"
	if typeof(acts) == TYPE_ARRAY and acts.has("act2"):
		return "Акт II"
	return "Акт I"


func _xp_window_for_player(player: Dictionary, xp_current: int, fallback: int) -> Dictionary:
	var level := _to_int_value(player.get("level", 1))
	var next_level_cost := _xp_required_for_next_level(level, 0)
	if next_level_cost > 0:
		return {
			"progress": int(max(0, xp_current)),
			"required": next_level_cost
		}

	for key in ["xp_next", "xp_to_next_level", "next_level_xp", "xp_target"]:
		if player.has(key):
			var value := _to_int_value(player.get(key, fallback))
			if value > xp_current:
				return {
					"progress": xp_current,
					"required": int(max(1, value))
				}
	return {
		"progress": xp_current,
		"required": int(max(max(fallback, xp_current), 1))
	}


func _xp_required_for_next_level(level: int, fallback: int) -> int:
	var costs := _xp_costs_from_rules()
	var index := level - 1
	if not costs.is_empty() and _to_int_value(costs[0]) == 0:
		index = level
	if index < 0 or index >= costs.size():
		return fallback
	return _to_int_value(costs[index])


func _xp_costs_from_rules() -> Array:
	var checks: Variant = AppState.snapshot.get("checks", {})
	if typeof(checks) != TYPE_DICTIONARY:
		return []
	var rules: Variant = checks.get("xp_rules", [])
	if typeof(rules) != TYPE_ARRAY or rules.is_empty() or typeof(rules[0]) != TYPE_DICTIONARY:
		return []

	var costs := []
	var raw_thresholds := _string_value(rules[0].get("level_thresholds", ""))
	for part in raw_thresholds.split(";"):
		var trimmed := part.strip_edges()
		if trimmed.is_empty():
			continue
		costs.append(_to_int_value(trimmed))
	return costs


func _to_int_value(value: Variant) -> int:
	if value == null or str(value).is_empty():
		return 0
	return int(value)


func _string_value(value: Variant) -> String:
	if value == null:
		return ""
	return str(value)
