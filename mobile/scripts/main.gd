extends Control

const API_AUTH_PATH := "/api/auth/player-code"
const API_SNAPSHOT_PATH := "/api/content/snapshot"
const API_HEALTH_PATH := "/health"
const API_EVENTS_SYNC_PATH := "/api/events/sync"
const PLAYER_LOGIN_SCENE := preload("res://scenes/player_login.tscn")
const WITCHER_JOURNAL_SCENE := preload("res://scenes/witcher_journal.tscn")
const QR_PVE_SCENE := preload("res://scenes/qr_pve.tscn")

var _http: HTTPRequest
var _pending_request := ""
var _pending_player_code := ""
var _login_view: Control
var _journal_view: Control
var _qr_pve_view: Control
var _pending_sync_event_ids := []
var _status_message := ""
var _status_is_error := false
var _request_busy := false


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)
	_build_ui()
	_refresh_from_state()


func _build_ui() -> void:
	_login_view = PLAYER_LOGIN_SCENE.instantiate()
	_login_view.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_login_view)

	if _login_view.has_signal("login_requested"):
		_login_view.connect("login_requested", Callable(self, "_on_login_pressed"))
	if _login_view.has_signal("offline_login_requested"):
		_login_view.connect("offline_login_requested", Callable(self, "_on_bundled_snapshot_pressed"))
	if _login_view.has_signal("diagnostics_submitted"):
		_login_view.connect("diagnostics_submitted", Callable(self, "_on_diagnostics_submitted"))
	if _login_view.has_signal("health_requested"):
		_login_view.connect("health_requested", Callable(self, "_on_health_pressed"))
	if _login_view.has_signal("clear_login_requested"):
		_login_view.connect("clear_login_requested", Callable(self, "_on_clear_login_pressed"))


func _refresh_from_state() -> void:
	var player := AppState.current_player()
	if not player.is_empty() and not _current_role_is_mobile():
		AppState.clear_session()
		player = {}
		_set_status("Этот сохраненный вход не подходит для мобильного журнала.", true)

	if player.is_empty():
		_set_login_surface(true)
		_set_journal_surface(false)
		_set_qr_pve_surface(false)
		_refresh_login_view()
		return

	_set_login_surface(false)
	_set_qr_pve_surface(false)
	_set_journal_surface(true)
	_refresh_login_view()


func _set_status(message: String, is_error: bool = false) -> void:
	_status_message = message
	_status_is_error = is_error
	_refresh_login_view()


func _refresh_login_view() -> void:
	if _login_view and _login_view.has_method("refresh_from_state"):
		_login_view.call("refresh_from_state", _status_message, _status_is_error, _request_busy)


func _set_login_surface(should_show: bool) -> void:
	if _login_view:
		_login_view.visible = should_show
		if should_show:
			_login_view.move_to_front()
			_refresh_login_view()


func _set_journal_surface(should_show: bool) -> void:
	if should_show:
		if not _journal_view:
			_journal_view = WITCHER_JOURNAL_SCENE.instantiate()
			_journal_view.set_anchors_preset(Control.PRESET_FULL_RECT)
			add_child(_journal_view)
			if _journal_view.has_signal("navigate_requested"):
				_journal_view.connect("navigate_requested", Callable(self, "_on_journal_navigation_requested"))
		_journal_view.visible = true
		_journal_view.move_to_front()
		if _journal_view.has_method("refresh_from_state"):
			_journal_view.call("refresh_from_state")
	elif _journal_view:
		_journal_view.visible = false


func _set_qr_pve_surface(should_show: bool) -> void:
	if should_show:
		if not _qr_pve_view:
			_qr_pve_view = QR_PVE_SCENE.instantiate()
			_qr_pve_view.set_anchors_preset(Control.PRESET_FULL_RECT)
			add_child(_qr_pve_view)
			if _qr_pve_view.has_signal("back_requested"):
				_qr_pve_view.connect("back_requested", Callable(self, "_on_qr_back_requested"))
			if _qr_pve_view.has_signal("qr_code_detected"):
				_qr_pve_view.connect("qr_code_detected", Callable(self, "_on_qr_code_detected"))
			if _qr_pve_view.has_signal("start_requested"):
				_qr_pve_view.connect("start_requested", Callable(self, "_on_qr_start_requested"))
		_qr_pve_view.visible = true
		_qr_pve_view.move_to_front()
		if _qr_pve_view.has_method("refresh_from_state"):
			_qr_pve_view.call("refresh_from_state")
	elif _qr_pve_view:
		_qr_pve_view.visible = false


func _on_journal_navigation_requested(target: String) -> void:
	if target == "qr_pve" or target == "qr":
		_set_journal_surface(false)
		_set_qr_pve_surface(true)
		_set_status("")
		return
	_set_status("Этот раздел пока остаётся в журнале.", true)


func _on_qr_back_requested() -> void:
	_set_qr_pve_surface(false)
	_set_journal_surface(true)
	_set_status("")


func _on_qr_sync_requested() -> void:
	if AppState.has_syncable_events():
		_on_sync_queue_pressed()
		return
	if str(AppState.session.get("player_id", "")).is_empty():
		_set_status("Сначала войдите по коду игрока.", true)
		return
	_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})


func _on_qr_code_detected(code: String, source: String) -> void:
	var payload := AppState.check_qr_order_gate(code, source)
	if _qr_pve_view and _qr_pve_view.has_method("apply_order_check_response"):
		_qr_pve_view.call("apply_order_check_response", 200, payload)


func _on_qr_start_requested(_context: Dictionary) -> void:
	if _qr_pve_view and _qr_pve_view.has_method("show_start_placeholder"):
		_qr_pve_view.call("show_start_placeholder")


func _on_save_connection_pressed() -> void:
	var server_url := str(AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL))
	if _login_view and _login_view.has_method("server_url"):
		server_url = str(_login_view.call("server_url"))
	AppState.set_server_url(server_url)
	_refresh_from_state()
	_set_status("Адрес сервера сохранен.")


func _on_use_connection_text_pressed() -> void:
	var connection_text := ""
	if _login_view and _login_view.has_method("connection_text"):
		connection_text = str(_login_view.call("connection_text"))
	var url := AppState.connection_text_to_server_url(connection_text)
	AppState.set_server_url(url)
	_refresh_from_state()
	_set_status("QR/строка подключения применена.")


func _on_diagnostics_submitted(server_url: String, connection_text: String) -> void:
	if connection_text.strip_edges().is_empty():
		AppState.set_server_url(server_url)
	else:
		AppState.set_server_url(AppState.connection_text_to_server_url(connection_text))
	_refresh_from_state()
	_set_status("Параметры связи сохранены.")


func _on_health_pressed() -> void:
	_start_request("health", API_HEALTH_PATH, HTTPClient.METHOD_GET, {})


func _on_login_pressed(requested_code: String = "") -> void:
	var player_code := requested_code.strip_edges()
	if player_code.is_empty() and _login_view and _login_view.has_method("player_code"):
		player_code = str(_login_view.call("player_code")).strip_edges()
	if player_code.is_empty():
		_set_status("Введите код игрока.", true)
		return

	var server_url := str(AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL))
	if _login_view and _login_view.has_method("server_url"):
		server_url = str(_login_view.call("server_url"))
	AppState.set_server_url(server_url)
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


func _on_bundled_snapshot_pressed(requested_code: String = "") -> void:
	var player_code := requested_code.strip_edges()
	if player_code.is_empty() and _login_view and _login_view.has_method("player_code"):
		player_code = str(_login_view.call("player_code")).strip_edges()
	if player_code.is_empty():
		_set_status("Введите код игрока для локального снимка.", true)
		return
	if AppState.bind_bundled_player_code(player_code):
		if not _current_role_is_mobile():
			AppState.clear_session()
			_refresh_from_state()
			_set_status("Этот код не для мобильного журнала ведьмака или чародейки.", true)
			return
		_refresh_from_state()
		_set_status("Локальный снимок загружен.")
	else:
		_refresh_from_state()
		_set_status(str(AppState.session.get("last_error", "Неизвестный код игрока.")), true)


func _on_refresh_snapshot_pressed() -> void:
	if str(AppState.session.get("player_id", "")).is_empty():
		_set_status("Сначала войдите по коду игрока.", true)
		return
	_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})


func _on_clear_login_pressed() -> void:
	AppState.clear_session()
	_refresh_from_state()
	_set_status("Вход сброшен. Локальный снимок остался на устройстве.")


func _on_unlock_act_pressed() -> void:
	var unlock_code := ""
	var event := AppState.offline_unlock_act(unlock_code)
	_refresh_from_state()
	if event.is_empty():
		_set_status(str(AppState.session.get("last_error", "Act unlock failed.")), true)
		return
	_set_status("Act unlocked locally; sync queue will verify the master reveal.")


func _on_qr_scan_text_pressed(qr_text: String = "") -> void:
	_prepare_qr("qr_scan", qr_text)


func _on_manual_qr_pressed(qr_text: String = "") -> void:
	_prepare_qr("manual_id", qr_text)


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

	var server_url := str(AppState.settings.get("server_url", AppState.DEFAULT_SERVER_URL))
	if _login_view and _login_view.has_method("server_url"):
		server_url = str(_login_view.call("server_url"))
	AppState.set_server_url(server_url)
	var prepared := AppState.prepare_sync_request()
	_pending_sync_event_ids = prepared.get("event_ids", [])
	var request_body = prepared.get("request", {})
	if typeof(request_body) != TYPE_DICTIONARY or request_body.is_empty():
		_refresh_from_state()
		_set_status(str(AppState.sync_status.get("last_error", "No events ready for sync.")), true)
		return

	_refresh_from_state()
	_start_request("event_sync", API_EVENTS_SYNC_PATH, HTTPClient.METHOD_POST, request_body)


func _prepare_qr(source: String, qr_text: String = "") -> void:
	var context := AppState.prepare_qr_attempt(qr_text, source)
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
		_set_status("Запрос уже выполняется.", true)
		return

	_pending_request = label
	_request_busy = true
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
		_set_status(_request_status_text(label))


func _handle_request_start_error(label: String) -> void:
	_request_busy = false
	if label == "auth":
		_try_bundled_login("Сеть недоступна.")
	elif label == "event_sync":
		AppState.mark_sync_batch_error(_pending_sync_event_ids, "Network request could not start.")
		_refresh_from_state()
		_set_status("Синхронизация не началась. Очередь сохранена для повтора.", true)
	else:
		_set_status("Сеть недоступна. Локальное состояние сохранено.", true)
	_pending_request = ""


func _request_status_text(label: String) -> String:
	if label == "auth":
		return "Проверяем код игрока..."
	if label == "snapshot":
		return "Загружаем журнал..."
	if label == "health":
		return "Проверяем связь..."
	if label == "event_sync":
		return "Отправляем офлайн-очередь..."
	return "Выполняется запрос..."


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var label := _pending_request
	_pending_request = ""
	_request_busy = false
	_refresh_login_view()

	if label == "health":
		if result == OK and response_code >= 200 and response_code < 300:
			_set_status("Сервер игры доступен.")
		else:
			_set_status("Сервер недоступен. Офлайн-состояние можно использовать.", true)
		return

	if label == "auth":
		_handle_auth_response(result, response_code, body)
		return

	if label == "snapshot":
		_handle_snapshot_response(result, response_code, body)
		return

	if label == "event_sync":
		_handle_event_sync_response(result, response_code, body)
		return

func _handle_auth_response(result: int, response_code: int, body: PackedByteArray) -> void:
	if result != OK or response_code == 0 or response_code == 404:
		_try_bundled_login("Auth API unavailable; bundled artifact is non-playable.")
		return

	var payload := _parse_json_body(body)
	if response_code >= 200 and response_code < 300 and not payload.is_empty():
		var player_id := _player_id_from_auth_payload(payload)
		if player_id.is_empty():
			_try_bundled_login("Ответ входа не содержит игрока.")
			return
		if not _auth_payload_is_mobile_role(payload):
			_refresh_from_state()
			_set_status("Этот код не для мобильного журнала ведьмака или чародейки.", true)
			return
		AppState.bind_player(_pending_player_code, player_id, "online")
		_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})
		return

	_set_status("Неверный код игрока или устройство отклонено.", true)


func _handle_snapshot_response(result: int, response_code: int, body: PackedByteArray) -> void:
	var payload := _parse_json_body(body)
	if result == OK and response_code >= 200 and response_code < 300 and not payload.is_empty():
		AppState.set_snapshot(payload, "server")
		if not _current_role_is_mobile():
			AppState.clear_session()
			_refresh_from_state()
			_set_status("Загруженный игрок не является ведьмаком или чародейкой.", true)
			return
		_refresh_from_state()
		_set_status("Журнал загружен и сохранен.")
		return

	if AppState.snapshot.is_empty():
		_try_bundled_login("Снимок недоступен.")
	else:
		_refresh_from_state()
		_set_status("Снимок недоступен. Последний локальный снимок сохранен.", true)


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
		_pending_sync_event_ids = []
	elif str(AppState.sync_status.get("status", "")) == "needs_master_review":
		_pending_sync_event_ids = []
		_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})
	else:
		_pending_sync_event_ids = []
		_start_request("snapshot", _snapshot_request_path(), HTTPClient.METHOD_GET, {})


func _try_bundled_login(prefix: String) -> void:
	if AppState.bind_bundled_player_code(_pending_player_code):
		if not _current_role_is_mobile():
			AppState.clear_session()
			_refresh_from_state()
			_set_status("%s Этот код не для мобильного журнала ведьмака или чародейки." % prefix, true)
			return
		_refresh_from_state()
		_set_status("%s Локальный снимок загружен." % prefix)
	else:
		_refresh_from_state()
		_set_status("%s Локальные данные сохранены; подключитесь к серверу для входа." % prefix, true)


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


func _auth_payload_is_mobile_role(payload: Dictionary) -> bool:
	var role_type := str(payload.get("role_type", "")).strip_edges().to_lower()
	if role_type.is_empty() and payload.has("player") and typeof(payload["player"]) == TYPE_DICTIONARY:
		role_type = str(payload["player"].get("role_type", "")).strip_edges().to_lower()
	return _is_mobile_role(role_type)


func _current_role_is_mobile() -> bool:
	var player := AppState.current_player()
	if player.is_empty():
		return false
	return _is_mobile_role(str(player.get("role_type", "")).strip_edges().to_lower())


func _is_mobile_role(role_type: String) -> bool:
	return role_type == "witcher" or role_type == "sorceress"


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
	var reward_note := ""
	var local_reward = event.get("local_reward_update", {})
	if typeof(local_reward) == TYPE_DICTIONARY and not local_reward.is_empty():
		reward_note = " Reward applied offline: +%s XP, +%s gold; sync pending." % [
			str(local_reward.get("xp_gain", 0)),
			str(local_reward.get("gold_gain", 0))
		]
	var leave_in_place_note := _ordinary_qr_leave_in_place_note(payload)
	return "%s queued as client event #%s: d20 %s + %s %s + modifiers %d = %s (%s).%s" % [
		label,
		str(event.get("client_sequence", "")),
		str(payload.get("roll", roll_entry.get("roll", ""))),
		str(payload.get("stat", roll_entry.get("stat", "stat"))),
		str(payload.get("stat_value", roll_entry.get("stat_value", ""))),
		modifier_total,
		str(payload.get("total", roll_entry.get("total", ""))),
		str(payload.get("outcome", payload.get("result", ""))),
		reward_note + leave_in_place_note
	]


func _ordinary_qr_leave_in_place_note(payload: Dictionary) -> String:
	var qr_mode := str(payload.get("qr_mode", ""))
	if qr_mode == "repeatable_scene" or qr_mode == "always_available_scene":
		return " После награды не забирайте этот QR-знак или лист: оставьте его на месте для других игроков."
	return ""
