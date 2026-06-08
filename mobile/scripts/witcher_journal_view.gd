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
		"title": "QR / Manual ID",
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
		"title": "Трейд",
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

@onready var _stage: Control = $JournalStage
@onready var _character_name_label: Label = $JournalStage/CharacterNameLabel
@onready var _character_meta_label: Label = $JournalStage/CharacterMetaLabel
@onready var _character_rep_label: Label = $JournalStage/CharacterRepLabel
@onready var _character_status_label: Label = $JournalStage/CharacterStatusLabel
@onready var _sync_badge_label: Label = $JournalStage/SyncBadgeLabel
@onready var _act_label: Label = $JournalStage/ActLabel
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
	var character_name := "Эйрик"
	var level := "3"
	var xp := "18"
	var gold := "20"
	var reputation := "нейтральная"
	var status := "Готов к заказу"

	if not player.is_empty():
		character_name = str(player.get("display_name", character_name))
		level = str(player.get("level", level))
		xp = str(player.get("xp", xp))
		gold = str(player.get("gold", gold))
		reputation = AppState.player_reputation_display(player)
		status = _status_from_sync()

	_character_name_label.text = character_name
	_character_meta_label.text = "Ур. %s · %s опыта · %s зол." % [level, xp, gold]
	_character_rep_label.text = "Репутация: %s" % reputation
	_character_status_label.text = status
	_sync_badge_label.text = _sync_label()
	_act_label.text = _act_label_text()


func _connect_buttons() -> void:
	for node_name in BUTTON_PANELS.keys():
		var button := _stage.get_node_or_null(node_name) as Button
		if button:
			button.pressed.connect(_open_panel.bind(str(BUTTON_PANELS[node_name])))

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
