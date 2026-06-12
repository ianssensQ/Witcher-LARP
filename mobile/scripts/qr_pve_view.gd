extends Control

signal back_requested
signal qr_code_detected(code: String, source: String)
signal start_requested(context: Dictionary)

const BASE_SIZE := Vector2(390, 844)
const BG_TEXTURE := preload("res://assets/ui/witcher/m1_journal/journal-bg-v2.png")

var _stage: Control
var _camera_panel: Control
var _camera_texture: TextureRect
var _order_panel: Control
var _manual_input: LineEdit
var _status_label: Label
var _order_title_label: Label
var _order_memo_label: Label
var _start_button: Button
var _manual_timer: Timer
var _camera_feed = null
var _current_context := {}
var _last_submitted_code := ""
var _is_checking := false
var _native_scanner_started := false


func _ready() -> void:
	_build_ui()
	_connect_qr_scanner_bridge()
	_start_camera()
	refresh_from_state()
	_layout_stage()


func _exit_tree() -> void:
	_stop_camera()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and _stage:
		_layout_stage()


func refresh_from_state() -> void:
	if AppState.current_player().is_empty():
		_show_camera_state("Сначала войдите по коду игрока.", true)
	else:
		_show_camera_state("Камера готова.", false)


func receive_scanned_qr(qr_text: String) -> void:
	_submit_code(qr_text, "qr_scan")


func set_check_pending(code: String) -> void:
	_is_checking = true
	_status_label.text = "Проверяем заказ..."
	_status_label.add_theme_color_override("font_color", Color(0.82, 0.74, 0.62))
	_last_submitted_code = AppState.normalize_qr_code(code)


func apply_order_check_response(response_code: int, payload: Dictionary) -> void:
	_is_checking = false
	if response_code < 200 or response_code >= 300:
		_show_camera_state(_error_text_for_response(response_code), true)
		return

	var status := str(payload.get("status", ""))
	if status == "matched_order":
		_show_order_state(payload)
	elif status == "not_taken":
		_show_camera_state("Этот знак не относится к вашим взятым заказам.", true)
	elif status == "unknown_qr":
		_show_camera_state("Код не найден.", true)
	else:
		_show_camera_state(str(payload.get("message", "Заказ не подтвержден.")), true)


func apply_order_check_error(message: String = "") -> void:
	_is_checking = false
	var text := message.strip_edges()
	if text.is_empty():
		text = "Нет связи с сервером."
	_show_camera_state(text, true)


func show_start_placeholder() -> void:
	_status_label.text = "PvE-сцена откроется на следующем экране."
	_status_label.add_theme_color_override("font_color", Color(0.86, 0.76, 0.55))


func _build_ui() -> void:
	_stage = Control.new()
	_stage.name = "QrOrderStage"
	_stage.size = BASE_SIZE
	add_child(_stage)

	var bg := TextureRect.new()
	bg.texture = BG_TEXTURE
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_SCALE
	_place(bg, Rect2(0, 0, 390, 844))
	_stage.add_child(bg)

	_add_panel(Rect2(0, 0, 390, 844), Color(0.015, 0.012, 0.010, 0.36))
	_build_camera_panel()
	_build_order_panel()
	_build_header()
	_build_manual_area()

	_manual_timer = Timer.new()
	_manual_timer.one_shot = true
	_manual_timer.wait_time = 0.65
	_manual_timer.timeout.connect(_on_manual_timer_timeout)
	add_child(_manual_timer)


func _build_header() -> void:
	var shade := _add_panel(Rect2(0, 0, 390, 92), Color(0.02, 0.016, 0.014, 0.76))
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_make_label("Eyebrow", Rect2(28, 24, 160, 18), "QR-заказ", 11, Color(0.86, 0.65, 0.39))
	_make_label("Header", Rect2(28, 45, 220, 34), "Скан места", 28, Color(0.97, 0.90, 0.76))
	var back_button := _make_button("BackButton", Rect2(324, 32, 40, 40), "<")
	back_button.pressed.connect(_on_back_pressed)


func _build_camera_panel() -> void:
	_camera_panel = Control.new()
	_camera_panel.name = "CameraPanel"
	_place(_camera_panel, Rect2(0, 0, 390, 438))
	_stage.add_child(_camera_panel)

	var base := ColorRect.new()
	base.name = "CameraFallback"
	base.color = Color(0.025, 0.031, 0.030, 0.98)
	_place(base, Rect2(0, 0, 390, 438))
	_camera_panel.add_child(base)

	_camera_texture = TextureRect.new()
	_camera_texture.name = "CameraFeed"
	_camera_texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_camera_texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_place(_camera_texture, Rect2(0, 0, 390, 438))
	_camera_panel.add_child(_camera_texture)

	_add_panel_to(_camera_panel, Rect2(0, 0, 390, 438), Color(0.0, 0.0, 0.0, 0.20))
	_add_panel_to(_camera_panel, Rect2(18, 110, 354, 2), Color(0.90, 0.70, 0.42, 0.72))
	_add_panel_to(_camera_panel, Rect2(18, 378, 354, 2), Color(0.90, 0.70, 0.42, 0.64))
	_add_panel_to(_camera_panel, Rect2(18, 110, 2, 270), Color(0.90, 0.70, 0.42, 0.64))
	_add_panel_to(_camera_panel, Rect2(370, 110, 2, 270), Color(0.90, 0.70, 0.42, 0.64))
	_add_panel_to(_camera_panel, Rect2(70, 244, 250, 1), Color(0.94, 0.82, 0.58, 0.34))
	_add_panel_to(_camera_panel, Rect2(194, 146, 1, 196), Color(0.94, 0.82, 0.58, 0.24))
	_make_label_for(_camera_panel, "CameraBadge", Rect2(286, 398, 78, 22), "камера", 11, Color(0.78, 0.93, 0.83), HORIZONTAL_ALIGNMENT_CENTER)


func _build_order_panel() -> void:
	_order_panel = Control.new()
	_order_panel.name = "MatchedOrderPanel"
	_order_panel.visible = false
	_place(_order_panel, Rect2(0, 0, 390, 438))
	_stage.add_child(_order_panel)

	_add_panel_to(_order_panel, Rect2(0, 0, 390, 438), Color(0.035, 0.027, 0.021, 0.96))
	_add_panel_to(_order_panel, Rect2(24, 118, 342, 246), Color(0.73, 0.61, 0.42, 0.94))
	_add_panel_to(_order_panel, Rect2(32, 126, 326, 230), Color(0.92, 0.82, 0.60, 0.90))
	_make_label_for(_order_panel, "OrderKicker", Rect2(48, 148, 294, 20), "заказ подтвержден", 11, Color(0.36, 0.20, 0.08), HORIZONTAL_ALIGNMENT_CENTER)
	_order_title_label = _make_label_for(_order_panel, "OrderTitle", Rect2(50, 178, 290, 44), "", 24, Color(0.09, 0.055, 0.026), HORIZONTAL_ALIGNMENT_CENTER, true)
	_order_memo_label = _make_label_for(_order_panel, "OrderMemo", Rect2(54, 232, 282, 72), "", 13, Color(0.18, 0.10, 0.045), HORIZONTAL_ALIGNMENT_CENTER, true)
	_start_button = _make_button_for(_order_panel, "StartPveButton", Rect2(112, 316, 166, 40), "Начать")
	_start_button.pressed.connect(_on_start_pressed)


func _build_manual_area() -> void:
	_add_panel(Rect2(0, 438, 390, 406), Color(0.020, 0.016, 0.013, 0.78))
	_make_label("ManualLabel", Rect2(38, 478, 314, 18), "код знака", 11, Color(0.76, 0.58, 0.36), HORIZONTAL_ALIGNMENT_CENTER)
	_manual_input = LineEdit.new()
	_manual_input.name = "ManualCodeInput"
	_manual_input.placeholder_text = "QR-A1-X3L5"
	_manual_input.clear_button_enabled = true
	_manual_input.text_submitted.connect(_on_manual_submitted)
	_manual_input.text_changed.connect(_on_manual_text_changed)
	_manual_input.add_theme_font_size_override("font_size", 22)
	_manual_input.add_theme_color_override("font_color", Color(0.98, 0.91, 0.76))
	_manual_input.add_theme_color_override("font_placeholder_color", Color(0.56, 0.50, 0.42, 0.85))
	_manual_input.add_theme_color_override("caret_color", Color(0.94, 0.72, 0.42))
	_manual_input.add_theme_stylebox_override("normal", _line_edit_box(false))
	_manual_input.add_theme_stylebox_override("focus", _line_edit_box(true))
	_place(_manual_input, Rect2(32, 506, 326, 58))
	_stage.add_child(_manual_input)

	_status_label = _make_label("Status", Rect2(38, 578, 314, 46), "", 13, Color(0.75, 0.69, 0.60), HORIZONTAL_ALIGNMENT_CENTER, true)


func _start_camera() -> void:
	if Engine.is_editor_hint():
		return
	if _start_native_qr_scanner():
		return
	if not Engine.has_singleton("CameraServer"):
		return
	CameraServer.set_monitoring_feeds(true)
	var feeds = CameraServer.feeds()
	if feeds.is_empty():
		return
	_camera_feed = feeds[0]
	if _camera_feed == null:
		return
	_camera_feed.set_active(true)
	var texture := CameraTexture.new()
	texture.camera_feed_id = _camera_feed.get_id()
	texture.camera_is_active = true
	_camera_texture.texture = texture


func _stop_camera() -> void:
	if _native_scanner_started:
		QrScannerBridge.stop_scan()
		_native_scanner_started = false
	if _camera_feed != null:
		_camera_feed.set_active(false)
	_camera_feed = null


func _show_camera_state(message: String, is_error: bool) -> void:
	_current_context = {}
	_order_panel.visible = false
	_camera_panel.visible = true
	_start_camera()
	_status_label.text = message
	_status_label.add_theme_color_override("font_color", Color(0.90, 0.53, 0.44) if is_error else Color(0.75, 0.69, 0.60))


func _show_order_state(payload: Dictionary) -> void:
	_current_context = payload.duplicate(true)
	_stop_camera()
	_camera_panel.visible = false
	_order_panel.visible = true
	var order = payload.get("order", {})
	var quest = payload.get("quest", {})
	var title := "Заказ"
	if typeof(order) == TYPE_DICTIONARY:
		title = str(order.get("title", order.get("object_label", order.get("order_id", "Заказ"))))
	_order_title_label.text = title
	_order_memo_label.text = _quest_memo_text(quest)
	_status_label.text = "Можно начинать PvE."
	_status_label.add_theme_color_override("font_color", Color(0.78, 0.93, 0.83))


func _connect_qr_scanner_bridge() -> void:
	var scanned_callback := Callable(self, "_on_native_qr_scanned")
	if not QrScannerBridge.qr_scanned.is_connected(scanned_callback):
		QrScannerBridge.qr_scanned.connect(scanned_callback)
	var error_callback := Callable(self, "_on_native_scanner_error")
	if not QrScannerBridge.scanner_error.is_connected(error_callback):
		QrScannerBridge.scanner_error.connect(error_callback)


func _start_native_qr_scanner() -> bool:
	if not QrScannerBridge.is_native_scanner_available():
		return false
	var scan_rect := _native_scan_rect_normalized()
	if not QrScannerBridge.start_scan_normalized(scan_rect):
		return false
	_native_scanner_started = true
	_camera_feed = null
	_camera_texture.texture = null
	return true


func _native_scan_rect_normalized() -> Rect2:
	var rect := Rect2(0, 92, 390, 346)
	return Rect2(
		Vector2(rect.position.x / BASE_SIZE.x, rect.position.y / BASE_SIZE.y),
		Vector2(rect.size.x / BASE_SIZE.x, rect.size.y / BASE_SIZE.y)
	)


func _on_native_qr_scanned(qr_text: String) -> void:
	receive_scanned_qr(qr_text)


func _on_native_scanner_error(_message: String) -> void:
	if _current_context.is_empty():
		_show_camera_state("Камера не готова; введите код ниже.", true)


func _quest_memo_text(quest: Variant) -> String:
	if typeof(quest) != TYPE_DICTIONARY:
		return "Проверьте знак на месте и переходите к сцене."
	var primary_stat := str(quest.get("primary_stat", "")).strip_edges()
	var dc := str(quest.get("dc", "")).strip_edges()
	var success_text := str(quest.get("success_text", "")).strip_edges()
	var parts := []
	if not primary_stat.is_empty() and not dc.is_empty():
		parts.append("%s против %s" % [primary_stat, dc])
	if not success_text.is_empty():
		parts.append(success_text)
	if parts.is_empty():
		return "Проверьте знак на месте и переходите к сцене."
	return " · ".join(parts)


func _on_manual_text_changed(value: String) -> void:
	_manual_timer.stop()
	var normalized := AppState.normalize_qr_code(value)
	if normalized.length() >= 8 and normalized != _last_submitted_code and not _is_checking:
		_manual_timer.start()


func _on_manual_timer_timeout() -> void:
	_submit_code(_manual_input.text, "manual_id")


func _on_manual_submitted(value: String) -> void:
	_submit_code(value, "manual_id")


func _submit_code(raw_code: String, source: String) -> void:
	var normalized := AppState.normalize_qr_code(raw_code)
	if normalized.is_empty():
		_show_camera_state("Введите код знака.", true)
		return
	if _is_checking or normalized == _last_submitted_code:
		return
	_last_submitted_code = normalized
	set_check_pending(normalized)
	qr_code_detected.emit(normalized, source)


func _on_start_pressed() -> void:
	if _current_context.is_empty():
		return
	start_requested.emit(_current_context.duplicate(true))


func _on_back_pressed() -> void:
	back_requested.emit()


func _error_text_for_response(response_code: int) -> String:
	if response_code == 401:
		return "Сначала войдите по коду игрока."
	if response_code == 403:
		return "Этот знак не доступен вашему персонажу."
	if response_code == 404:
		return "QR-контент не загружен на сервере."
	return "Сервер не подтвердил заказ."


func _make_button(node_name: String, rect: Rect2, text: String) -> Button:
	return _make_button_for(_stage, node_name, rect, text)


func _make_button_for(parent: Node, node_name: String, rect: Rect2, text: String) -> Button:
	var button := Button.new()
	button.name = node_name
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 15)
	button.add_theme_color_override("font_color", Color(0.98, 0.91, 0.76))
	button.add_theme_stylebox_override("normal", _button_box(Color(0.18, 0.13, 0.09, 0.96), Color(0.76, 0.58, 0.36, 0.85)))
	button.add_theme_stylebox_override("hover", _button_box(Color(0.27, 0.19, 0.12, 0.98), Color(0.90, 0.70, 0.42, 0.95)))
	button.add_theme_stylebox_override("pressed", _button_box(Color(0.10, 0.075, 0.052, 0.98), Color(0.90, 0.70, 0.42, 0.95)))
	_place(button, rect)
	parent.add_child(button)
	return button


func _button_box(bg: Color, border: Color) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = bg
	box.border_color = border
	box.border_width_left = 1
	box.border_width_top = 1
	box.border_width_right = 1
	box.border_width_bottom = 1
	box.corner_radius_top_left = 7
	box.corner_radius_top_right = 7
	box.corner_radius_bottom_left = 7
	box.corner_radius_bottom_right = 7
	box.content_margin_left = 8
	box.content_margin_right = 8
	return box


func _line_edit_box(focused: bool) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.035, 0.027, 0.022, 0.96)
	box.border_color = Color(0.95, 0.76, 0.45, 0.94) if focused else Color(0.62, 0.50, 0.35, 0.76)
	box.border_width_left = 1
	box.border_width_top = 1
	box.border_width_right = 1
	box.border_width_bottom = 1
	box.corner_radius_top_left = 8
	box.corner_radius_top_right = 8
	box.corner_radius_bottom_left = 8
	box.corner_radius_bottom_right = 8
	box.content_margin_left = 18
	box.content_margin_right = 18
	return box


func _make_label(
	node_name: String,
	rect: Rect2,
	text: String,
	font_size: int,
	color: Color,
	alignment: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT,
	autowrap: bool = false
) -> Label:
	return _make_label_for(_stage, node_name, rect, text, font_size, color, alignment, autowrap)


func _make_label_for(
	parent: Node,
	node_name: String,
	rect: Rect2,
	text: String,
	font_size: int,
	color: Color,
	alignment: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT,
	autowrap: bool = false
) -> Label:
	var label := Label.new()
	label.name = node_name
	label.text = text
	label.horizontal_alignment = alignment
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART if autowrap else TextServer.AUTOWRAP_OFF
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color(0.02, 0.015, 0.01, 0.70))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	_place(label, rect)
	parent.add_child(label)
	return label


func _add_panel(rect: Rect2, color: Color) -> ColorRect:
	return _add_panel_to(_stage, rect, color)


func _add_panel_to(parent: Node, rect: Rect2, color: Color) -> ColorRect:
	var panel := ColorRect.new()
	panel.color = color
	_place(panel, rect)
	parent.add_child(panel)
	return panel


func _place(node: Control, rect: Rect2) -> void:
	node.position = rect.position
	node.size = rect.size


func _layout_stage() -> void:
	var available := size
	if available.x <= 0.0 or available.y <= 0.0:
		available = BASE_SIZE
	var scale_value: float = min(available.x / BASE_SIZE.x, available.y / BASE_SIZE.y)
	_stage.scale = Vector2(scale_value, scale_value)
	_stage.position = (available - BASE_SIZE * scale_value) * 0.5
	_stage.size = BASE_SIZE
