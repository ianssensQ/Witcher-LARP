extends Control

signal login_requested(player_code: String)
signal offline_login_requested(player_code: String)
signal diagnostics_submitted(server_url: String, connection_text: String)
signal health_requested
signal clear_login_requested

const BASE_SIZE := Vector2(390, 844)

var _is_busy := false

@onready var _stage: Control = $LoginStage
@onready var _connection_badge_label: Label = $LoginStage/ConnectionBadge/ConnectionBadgeLabel
@onready var _snapshot_badge_label: Label = $LoginStage/SnapshotBadge/SnapshotBadgeLabel
@onready var _player_code_input: LineEdit = $LoginStage/LoginPanel/PlayerCodeInput
@onready var _login_button: Button = $LoginStage/LoginPanel/LoginButton
@onready var _offline_button: Button = $LoginStage/LoginPanel/OfflineButton
@onready var _status_label: Label = $LoginStage/LoginPanel/StatusLabel
@onready var _diagnostics_toggle: Button = $LoginStage/LoginPanel/DiagnosticsToggleButton
@onready var _diagnostics_panel: Panel = $LoginStage/DiagnosticsPanel
@onready var _server_url_input: LineEdit = $LoginStage/DiagnosticsPanel/ServerUrlInput
@onready var _connection_text_input: LineEdit = $LoginStage/DiagnosticsPanel/ConnectionTextInput
@onready var _save_connection_button: Button = $LoginStage/DiagnosticsPanel/SaveConnectionButton
@onready var _health_button: Button = $LoginStage/DiagnosticsPanel/HealthButton
@onready var _clear_button: Button = $LoginStage/DiagnosticsPanel/ClearButton
@onready var _device_label: Label = $LoginStage/DiagnosticsPanel/DeviceLabel


func _ready() -> void:
	_login_button.pressed.connect(_submit_login)
	_offline_button.pressed.connect(_submit_offline_login)
	_player_code_input.text_submitted.connect(_on_code_submitted)
	_diagnostics_toggle.pressed.connect(_toggle_diagnostics)
	_save_connection_button.pressed.connect(_submit_diagnostics)
	_health_button.pressed.connect(_request_health)
	_clear_button.pressed.connect(_request_clear_login)
	_diagnostics_panel.visible = false
	_layout_stage()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and _stage:
		_layout_stage()


func refresh_from_state(status_text: String = "", is_error: bool = false, is_busy: bool = false) -> void:
	_is_busy = is_busy
	_login_button.disabled = is_busy
	var has_bundled_codes := _has_bundled_player_codes()
	_offline_button.visible = has_bundled_codes
	_offline_button.disabled = is_busy
	_layout_secondary_buttons(has_bundled_codes)
	_save_connection_button.disabled = is_busy
	_health_button.disabled = is_busy
	_login_button.text = "Проверяем..." if is_busy else "Войти"

	var saved_code := str(AppState.session.get("player_code", "")).strip_edges()
	if _player_code_input.text.strip_edges().is_empty() and not saved_code.is_empty():
		_player_code_input.text = saved_code

	_server_url_input.text = str(AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL))
	_device_label.text = "Устройство: %s" % str(AppState.settings.get("device_id", ""))
	_connection_badge_label.text = _connection_badge_text()
	_snapshot_badge_label.text = _snapshot_badge_text()
	set_status(status_text, is_error)


func set_status(message: String, is_error: bool = false) -> void:
	if message.strip_edges().is_empty():
		message = _default_status_text()
		is_error = false
	_status_label.text = message
	_status_label.add_theme_color_override(
		"font_color",
		Color("#ffb3a7") if is_error else Color("#f3e6c5")
	)


func player_code() -> String:
	return _player_code_input.text.strip_edges().to_upper()


func server_url() -> String:
	return _server_url_input.text.strip_edges()


func connection_text() -> String:
	return _connection_text_input.text.strip_edges()


func _submit_login() -> void:
	if _is_busy:
		return
	login_requested.emit(player_code())


func _submit_offline_login() -> void:
	if _is_busy:
		return
	offline_login_requested.emit(player_code())


func _on_code_submitted(_text: String) -> void:
	_submit_login()


func _toggle_diagnostics() -> void:
	_diagnostics_panel.visible = not _diagnostics_panel.visible
	if _diagnostics_panel.visible:
		_diagnostics_panel.move_to_front()


func _submit_diagnostics() -> void:
	diagnostics_submitted.emit(server_url(), connection_text())


func _request_health() -> void:
	health_requested.emit()


func _request_clear_login() -> void:
	clear_login_requested.emit()


func _connection_badge_text() -> String:
	var sync_status := str(AppState.sync_status.get("status", "offline"))
	if sync_status == "synced":
		return "online"
	if int(AppState.sync_status.get("queued_count", 0)) > 0 or int(AppState.sync_status.get("pending_count", 0)) > 0:
		return "queue"
	return "offline"


func _snapshot_badge_text() -> String:
	if AppState.snapshot.is_empty():
		return "нет снимка"
	if AppState.current_player().is_empty():
		return "нужен код"
	return "снимок есть"


func _default_status_text() -> String:
	if not AppState.current_player().is_empty():
		return "Игрок загружен."
	if not AppState.snapshot.is_empty():
		return "Введите код игрока, чтобы открыть свой журнал."
	return "Введите код игрока. После загрузки журнал продолжит работать офлайн."


func _has_bundled_player_codes() -> bool:
	return AppState.load_bundled_snapshot().has("player_codes")


func _layout_secondary_buttons(has_bundled_codes: bool) -> void:
	if has_bundled_codes:
		_offline_button.offset_left = 24.0
		_offline_button.offset_right = 206.0
		_diagnostics_toggle.offset_left = 218.0
		_diagnostics_toggle.offset_right = 318.0
	else:
		_diagnostics_toggle.offset_left = 24.0
		_diagnostics_toggle.offset_right = 318.0


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
