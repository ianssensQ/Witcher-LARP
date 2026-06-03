extends Control

const API_AUTH_PATH := "/api/auth/player-code"
const API_SNAPSHOT_PATH := "/api/content/snapshot"
const API_HEALTH_PATH := "/health"
const API_EVENTS_SYNC_PATH := "/api/events/sync"

var _http: HTTPRequest
var _pending_request := ""
var _pending_player_code := ""
var _status_label: Label
var _device_label: Label
var _snapshot_label: Label
var _character_label: Label
var _server_url_input: LineEdit
var _connection_text_input: LineEdit
var _player_code_input: LineEdit
var _unlock_code_input: LineEdit
var _qr_input: LineEdit
var _qr_result_label: Label
var _event_queue_label: Label
var _pending_sync_event_ids := []


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)
	_build_ui()
	_refresh_from_state()


func _build_ui() -> void:
	var background := ColorRect.new()
	background.color = Color("#101820")
	background.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 18)
	margin.add_theme_constant_override("margin_right", 18)
	margin.add_theme_constant_override("margin_top", 18)
	margin.add_theme_constant_override("margin_bottom", 18)
	add_child(margin)

	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	margin.add_child(scroll)

	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 14)
	scroll.add_child(content)

	content.add_child(_new_label("Witcher LARP", 28, Color("#f4f0df")))
	content.add_child(_new_label("Offline-first player shell", 16, Color("#d0b56f")))

	_status_label = _new_label("", 15, Color("#f4f0df"))
	content.add_child(_status_label)

	content.add_child(_section_title("Connection"))
	_server_url_input = _new_line_edit("http://192.168.1.9:8000")
	content.add_child(_server_url_input)

	var connection_buttons := HBoxContainer.new()
	connection_buttons.add_theme_constant_override("separation", 8)
	connection_buttons.add_child(_new_button("Save URL", _on_save_connection_pressed))
	connection_buttons.add_child(_new_button("Health", _on_health_pressed))
	content.add_child(connection_buttons)

	_connection_text_input = _new_line_edit("Connection URL or witcher-larp:// QR text")
	content.add_child(_connection_text_input)
	content.add_child(_new_button("Use Connection Text", _on_use_connection_text_pressed))

	_device_label = _new_label("", 13, Color("#aab4be"))
	content.add_child(_device_label)

	content.add_child(_section_title("Player Code"))
	_player_code_input = _new_line_edit("WC-WOLF-6GF4")
	_player_code_input.secret = false
	content.add_child(_player_code_input)

	var login_buttons := HBoxContainer.new()
	login_buttons.add_theme_constant_override("separation", 8)
	login_buttons.add_child(_new_button("Login + Snapshot", _on_login_pressed))
	login_buttons.add_child(_new_button("Bundled Snapshot", _on_bundled_snapshot_pressed))
	content.add_child(login_buttons)

	content.add_child(_section_title("Snapshot"))
	_snapshot_label = _new_label("", 15, Color("#d8dee4"))
	content.add_child(_snapshot_label)
	content.add_child(_new_button("Refresh Snapshot", _on_refresh_snapshot_pressed))

	content.add_child(_section_title("Character"))
	_character_label = _new_label("", 15, Color("#f4f0df"))
	content.add_child(_character_label)

	content.add_child(_section_title("Act Unlock"))
	_unlock_code_input = _new_line_edit("Act unlock code")
	content.add_child(_unlock_code_input)
	content.add_child(_new_button("Unlock Act Offline", _on_unlock_act_pressed))

	content.add_child(_section_title("QR / Manual ID"))
	_qr_input = _new_line_edit("QR-A1-K7Q2 or witcher-larp://qr?code=QR-A1-K7Q2")
	content.add_child(_qr_input)

	var qr_buttons := HBoxContainer.new()
	qr_buttons.add_theme_constant_override("separation", 8)
	qr_buttons.add_child(_new_button("QR Scan Text", _on_qr_scan_text_pressed))
	qr_buttons.add_child(_new_button("Manual ID", _on_manual_qr_pressed))
	content.add_child(qr_buttons)

	var qr_confirmation_buttons := HBoxContainer.new()
	qr_confirmation_buttons.add_theme_constant_override("separation", 8)
	qr_confirmation_buttons.add_child(_new_button("Confirm Physical Presence", _on_confirm_qr_presence_pressed))
	qr_confirmation_buttons.add_child(_new_button("Flag Review", _on_qr_honesty_review_pressed))
	content.add_child(qr_confirmation_buttons)

	_qr_result_label = _new_label("", 14, Color("#d8dee4"))
	content.add_child(_qr_result_label)

	content.add_child(_section_title("Event Queue"))
	var event_buttons := HBoxContainer.new()
	event_buttons.add_theme_constant_override("separation", 8)
	event_buttons.add_child(_new_button("Roll PvE d20", _on_pve_check_pressed))
	event_buttons.add_child(_new_button("PvE Timeout", _on_pve_timeout_pressed))
	content.add_child(event_buttons)
	content.add_child(_new_button("Sync Queue", _on_sync_queue_pressed))
	_event_queue_label = _new_label("", 14, Color("#d8dee4"))
	content.add_child(_event_queue_label)

	content.add_child(_new_button("Clear Login", _on_clear_login_pressed))


func _new_label(text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _section_title(text: String) -> Label:
	return _new_label(text, 20, Color("#d0b56f"))


func _new_line_edit(placeholder: String) -> LineEdit:
	var input := LineEdit.new()
	input.placeholder_text = placeholder
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return input


func _new_button(text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.pressed.connect(callback)
	return button


func _refresh_from_state() -> void:
	_server_url_input.text = str(AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL))
	_device_label.text = "Device: %s" % str(AppState.settings.get("device_id", ""))

	var snapshot_version := str(AppState.snapshot.get("snapshot_version", "none"))
	var source := AppState.snapshot_source
	var generated := str(AppState.snapshot.get("generated_at", "unknown"))
	_snapshot_label.text = "Version: %s\nSource: %s\nGenerated: %s" % [snapshot_version, source, generated]

	var player := AppState.current_player()
	if player.is_empty():
		_character_label.text = "No character loaded. Enter a player_code or load bundled snapshot."
		_qr_result_label.text = AppState.qr_context_summary()
		_event_queue_label.text = AppState.event_queue_summary()
		return

	var stats := player.get("stats", {})
	var reputation := int(player.get("reputation", 0))
	_character_label.text = "%s\nRole: %s\nLevel %s, XP %s, Gold %s\nReputation: %d (%s)\nStats: %s\nLogin: %s" % [
		str(player.get("display_name", "Unknown")),
		str(player.get("role_type", "unknown")),
		str(player.get("level", 1)),
		str(player.get("xp", 0)),
		str(player.get("gold", 0)),
		reputation,
		AppState.reputation_label(reputation),
		JSON.stringify(stats),
		str(AppState.session.get("login_status", "signed_out"))
	]
	_qr_result_label.text = AppState.qr_context_summary()
	_event_queue_label.text = AppState.event_queue_summary()


func _set_status(message: String, is_error: bool = false) -> void:
	_status_label.text = message
	_status_label.add_theme_color_override("font_color", Color("#ffb3a7") if is_error else Color("#f4f0df"))


func _on_save_connection_pressed() -> void:
	AppState.set_server_url(_server_url_input.text)
	_refresh_from_state()
	_set_status("Server URL saved.")


func _on_use_connection_text_pressed() -> void:
	var url := AppState.connection_text_to_server_url(_connection_text_input.text)
	AppState.set_server_url(url)
	_refresh_from_state()
	_set_status("Connection text applied.")


func _on_health_pressed() -> void:
	_start_request("health", API_HEALTH_PATH, HTTPClient.METHOD_GET, {})


func _on_login_pressed() -> void:
	var player_code := _player_code_input.text.strip_edges()
	if player_code.is_empty():
		_set_status("Enter a player_code.", true)
		return

	AppState.set_server_url(_server_url_input.text)
	_pending_player_code = player_code.to_upper()
	_start_request(
		"auth",
		API_AUTH_PATH,
		HTTPClient.METHOD_POST,
		{
			"player_code": _pending_player_code,
			"device_id": AppState.settings.get("device_id", "")
		}
	)


func _on_bundled_snapshot_pressed() -> void:
	var player_code := _player_code_input.text.strip_edges()
	if player_code.is_empty():
		_set_status("Enter a bundled seed player_code first.", true)
		return
	if AppState.bind_bundled_player_code(player_code):
		_refresh_from_state()
		_set_status("Bundled snapshot loaded and persisted.")
	else:
		_refresh_from_state()
		_set_status(str(AppState.session.get("last_error", "Unknown player code.")), true)


func _on_refresh_snapshot_pressed() -> void:
	if str(AppState.session.get("player_id", "")).is_empty():
		_set_status("Login with a player_code before refreshing snapshot.", true)
		return
	_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})


func _on_clear_login_pressed() -> void:
	AppState.clear_session()
	_refresh_from_state()
	_set_status("Login cleared. Snapshot remains on device for offline review.")


func _on_unlock_act_pressed() -> void:
	var event := AppState.offline_unlock_act(_unlock_code_input.text)
	_refresh_from_state()
	if event.is_empty():
		_set_status(str(AppState.session.get("last_error", "Act unlock failed.")), true)
		return
	_set_status("Act unlocked locally; sync queue will verify the master reveal.")


func _on_qr_scan_text_pressed() -> void:
	_prepare_qr("qr_scan")


func _on_manual_qr_pressed() -> void:
	_prepare_qr("manual_id")


func _on_confirm_qr_presence_pressed() -> void:
	var context := AppState.confirm_qr_physical_presence()
	_refresh_from_state()
	if context.is_empty():
		_set_status(str(AppState.session.get("last_error", "No QR attempt is ready.")), true)
		return
	if str(context.get("event_type", "")) == "qr_scene_started":
		_set_status("QR scene ready. Offline result will carry qr_mode and physical-presence confirmation.")
	else:
		_set_status("QR attempt is not ready to start; review the status below.", true)


func _on_qr_honesty_review_pressed() -> void:
	var context := AppState.flag_qr_honesty_violation()
	_refresh_from_state()
	if context.is_empty():
		_set_status(str(AppState.session.get("last_error", "No QR attempt is ready.")), true)
	else:
		_set_status("QR attempt marked needs_master_review for honesty_violation_suspected.", true)


func _on_pve_check_pressed() -> void:
	_record_pve_check()


func _on_pve_timeout_pressed() -> void:
	_record_pve_result("timeout")


func _on_sync_queue_pressed() -> void:
	if _http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_set_status("Request already in progress.", true)
		return
	if not AppState.has_syncable_events():
		_refresh_from_state()
		_set_status("No offline or retryable events to sync.")
		return

	AppState.set_server_url(_server_url_input.text)
	var prepared := AppState.prepare_sync_request()
	_pending_sync_event_ids = prepared.get("event_ids", [])
	var request_body = prepared.get("request", {})
	if typeof(request_body) != TYPE_DICTIONARY or request_body.is_empty():
		_refresh_from_state()
		_set_status(str(AppState.sync_status.get("last_error", "No events ready for sync.")), true)
		return

	_refresh_from_state()
	_start_request("event_sync", API_EVENTS_SYNC_PATH, HTTPClient.METHOD_POST, request_body)


func _prepare_qr(source: String) -> void:
	var context := AppState.prepare_qr_attempt(_qr_input.text, source)
	_refresh_from_state()
	var status := str(context.get("local_status", ""))
	if status == "awaiting_physical_presence":
		_set_status("Confirm physical presence at the prop/location before starting this QR scene.")
	elif status == "needs_master_review":
		_set_status("QR attempt needs master review: %s." % str(context.get("review_reason", "")), true)
	elif status == "blocked_future_act":
		_set_status("Future-act QR is locked until sync or master unlock code.", true)
	elif status == "cooldown_active":
		_set_status("This QR is on a personal 30-minute failure cooldown.", true)
	elif status == "unknown_qr" or status == "input_error":
		_set_status(str(context.get("review_reason", "Unknown QR/manual ID.")), true)
	else:
		_set_status("QR attempt recorded.")


func _start_request(label: String, path: String, method: int, body: Dictionary) -> void:
	if _http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_set_status("Request already in progress.", true)
		return

	_pending_request = label
	var url := "%s%s" % [AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL), path]
	var headers := ["Accept: application/json", "Content-Type: application/json"]
	if label == "event_sync":
		var player_code := str(AppState.session.get("player_code", "")).strip_edges()
		if not player_code.is_empty():
			headers.append("X-Player-Code: %s" % player_code)
	var request_body := "" if method == HTTPClient.METHOD_GET else JSON.stringify(body)
	var err := _http.request(url, headers, method, request_body)
	if err != OK:
		_handle_request_start_error(label)
	else:
		_set_status("Requesting %s..." % label)


func _handle_request_start_error(label: String) -> void:
	if label == "auth":
		_try_bundled_login("Network request could not start.")
	elif label == "event_sync":
		AppState.mark_sync_batch_error(_pending_sync_event_ids, "Network request could not start.")
		_refresh_from_state()
		_set_status("Event sync could not start. Queue was kept for retry.", true)
	else:
		_set_status("Network request could not start. Existing offline state was kept.", true)
	_pending_request = ""


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var label := _pending_request
	_pending_request = ""

	if label == "health":
		if result == OK and response_code >= 200 and response_code < 300:
			_set_status("Server health OK.")
		else:
			_set_status("Server health unavailable. Offline state is still usable.", true)
		return

	if label == "auth":
		_handle_auth_response(result, response_code, body)
		return

	if label == "snapshot":
		_handle_snapshot_response(result, response_code, body)
		return

	if label == "event_sync":
		_handle_event_sync_response(result, response_code, body)


func _handle_auth_response(result: int, response_code: int, body: PackedByteArray) -> void:
	if result != OK or response_code == 0 or response_code == 404:
		_try_bundled_login("Auth API unavailable; bundled artifact is non-playable.")
		return

	var payload := _parse_json_body(body)
	if response_code >= 200 and response_code < 300 and not payload.is_empty():
		var player_id := _player_id_from_auth_payload(payload)
		if player_id.is_empty():
			_try_bundled_login("Auth response did not include player_id; bundled artifact is non-playable.")
			return
		AppState.bind_player(_pending_player_code, player_id, "online")
		_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})
		return

	_set_status("Invalid player_code or rejected device. Existing data was kept.", true)


func _handle_snapshot_response(result: int, response_code: int, body: PackedByteArray) -> void:
	var payload := _parse_json_body(body)
	if result == OK and response_code >= 200 and response_code < 300 and not payload.is_empty():
		AppState.set_snapshot(payload, "server")
		_refresh_from_state()
		_set_status("Snapshot downloaded and saved to user://.")
		return

	if AppState.snapshot.is_empty():
		_try_bundled_login("Snapshot API unavailable; bundled artifact is non-playable.")
	else:
		_refresh_from_state()
		_set_status("Snapshot API unavailable. Last local snapshot was kept.", true)


func _handle_event_sync_response(result: int, response_code: int, body: PackedByteArray) -> void:
	if result != OK or response_code == 0:
		AppState.mark_sync_batch_error(_pending_sync_event_ids, "Event sync network error.", response_code)
		_refresh_from_state()
		_set_status("Event sync failed. Queue is visible and retryable.", true)
		_pending_sync_event_ids = []
		return

	var payload := _parse_json_body(body)
	AppState.apply_sync_response(_pending_sync_event_ids, response_code, payload)
	_refresh_from_state()
	if str(AppState.sync_status.get("status", "")) == "sync_error":
		_set_status("Event sync returned an error. Retry when the server is reachable.", true)
	elif str(AppState.sync_status.get("status", "")) == "needs_master_review":
		_set_status("Event synced; at least one result needs master review.", true)
	else:
		_set_status("Event queue synced.")
	_pending_sync_event_ids = []


func _try_bundled_login(prefix: String) -> void:
	if AppState.bind_bundled_player_code(_pending_player_code):
		_refresh_from_state()
		_set_status("%s Bundled snapshot loaded." % prefix)
	else:
		_refresh_from_state()
		_set_status("%s Existing local data was kept; reconnect for playable login." % prefix, true)


func _parse_json_body(body: PackedByteArray) -> Dictionary:
	var text := body.get_string_from_utf8()
	var parsed = JSON.parse_string(text)
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


func _player_id_from_auth_payload(payload: Dictionary) -> String:
	if payload.has("player_id"):
		return str(payload["player_id"])
	if payload.has("player") and typeof(payload["player"]) == TYPE_DICTIONARY:
		return str(payload["player"].get("player_id", ""))
	return ""


func _snapshot_request_path() -> String:
	var player_code := str(AppState.session.get("player_code", "")).strip_edges()
	if player_code.is_empty():
		return API_SNAPSHOT_PATH
	return "%s?player_code=%s" % [API_SNAPSHOT_PATH, player_code.uri_encode()]


func _record_pve_check() -> void:
	var event := AppState.enqueue_pve_result("check")
	_refresh_from_state()
	if event.is_empty():
		_set_status(str(AppState.session.get("last_error", "PvE result was not queued.")), true)
		return
	_set_status(_pve_event_status_message("PvE check", event))


func _record_pve_result(result: String) -> void:
	var event := AppState.enqueue_pve_result(result)
	_refresh_from_state()
	if event.is_empty():
		_set_status(str(AppState.session.get("last_error", "PvE result was not queued.")), true)
		return
	_set_status(_pve_event_status_message("PvE %s" % result, event))


func _pve_event_status_message(label: String, event: Dictionary) -> String:
	var payload = event.get("payload", {})
	if typeof(payload) != TYPE_DICTIONARY:
		return "%s queued as client event #%s." % [label, str(event.get("client_sequence", ""))]
	var roll_log = payload.get("roll_log", [])
	var roll_entry := {}
	if typeof(roll_log) == TYPE_ARRAY and not roll_log.is_empty() and typeof(roll_log[0]) == TYPE_DICTIONARY:
		roll_entry = roll_log[0]
	var modifiers = payload.get("modifiers", roll_entry.get("modifiers", []))
	var modifier_total := 0
	if typeof(modifiers) == TYPE_ARRAY:
		for modifier in modifiers:
			if typeof(modifier) == TYPE_DICTIONARY:
				modifier_total += int(modifier.get("value", 0))
	return "%s queued as client event #%s: d20 %s + %s %s + modifiers %d = %s (%s)." % [
		label,
		str(event.get("client_sequence", "")),
		str(payload.get("roll", roll_entry.get("roll", ""))),
		str(payload.get("stat", roll_entry.get("stat", "stat"))),
		str(payload.get("stat_value", roll_entry.get("stat_value", ""))),
		modifier_total,
		str(payload.get("total", roll_entry.get("total", ""))),
		str(payload.get("outcome", payload.get("result", "")))
	]
