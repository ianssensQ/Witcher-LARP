extends Node

const SETTINGS_PATH := "user://settings.json"
const SESSION_PATH := "user://session.json"
const SNAPSHOT_PATH := "user://snapshot.json"
const QR_ATTEMPTS_PATH := "user://qr_attempts.json"
const QR_EVENT_CONTEXT_PATH := "user://qr_event_context.json"
const PVE_COOLDOWNS_PATH := "user://pve_cooldowns.json"
const EVENT_QUEUE_PATH := "user://event_queue.json"
const SYNC_STATUS_PATH := "user://sync_status.json"
const DEFAULT_SERVER_URL := "http://127.0.0.1:8000"
const BUNDLED_SNAPSHOT_PATH := "res://assets/bundled_snapshot.json"
const QR_MANUAL_LIMIT := 5
const QR_RATE_WINDOW_SECONDS := 60
const PVE_FAILURE_COOLDOWN_SECONDS := 30 * 60
const EVENT_HISTORY_LIMIT := 200
const SYNC_RETRY_STATUSES := ["offline", "pending", "sync_error"]

var settings := {
	"server_url": DEFAULT_SERVER_URL,
	"device_id": "",
	"last_client_sequence": 0
}

var session := {
	"player_id": "",
	"player_code": "",
	"login_status": "signed_out",
	"last_error": "",
	"unlocked_acts": ["act1"]
}

var snapshot := {}
var snapshot_source := "none"
var qr_attempts := []
var last_qr_event_context := {}
var pve_cooldowns := {}
var event_queue := []
var sync_status := {
	"status": "offline",
	"queued_count": 0,
	"pending_count": 0,
	"synced_count": 0,
	"sync_error_count": 0,
	"review_count": 0,
	"last_error": "",
	"last_sync_at": "",
	"last_response_code": 0
}


func _ready() -> void:
	load_all()


func load_all() -> void:
	settings = _load_json(SETTINGS_PATH, settings)
	if str(settings.get("device_id", "")).is_empty():
		settings["device_id"] = _new_device_id()
		save_settings()

	session = _load_json(SESSION_PATH, session)
	snapshot = _load_json(SNAPSHOT_PATH, {})
	snapshot_source = "user" if not snapshot.is_empty() else "none"
	_merge_unlocked_acts_from_snapshot()
	qr_attempts = _load_json(QR_ATTEMPTS_PATH, [])
	last_qr_event_context = _load_json(QR_EVENT_CONTEXT_PATH, {})
	pve_cooldowns = _load_json(PVE_COOLDOWNS_PATH, {})
	if typeof(pve_cooldowns) != TYPE_DICTIONARY:
		pve_cooldowns = {}
	event_queue = _load_json(EVENT_QUEUE_PATH, [])
	if typeof(event_queue) != TYPE_ARRAY:
		event_queue = []
	sync_status = _load_json(SYNC_STATUS_PATH, sync_status)
	if typeof(sync_status) != TYPE_DICTIONARY:
		sync_status = {}
	_refresh_sequence_from_queue()
	_cleanup_pve_cooldowns()
	_update_sync_status_counts(false)


func save_settings() -> void:
	_save_json(SETTINGS_PATH, settings)


func save_session() -> void:
	_save_json(SESSION_PATH, session)


func save_snapshot() -> void:
	_save_json(SNAPSHOT_PATH, snapshot)


func save_qr_attempts() -> void:
	_save_json(QR_ATTEMPTS_PATH, qr_attempts)


func save_qr_event_context() -> void:
	_save_json(QR_EVENT_CONTEXT_PATH, last_qr_event_context)


func save_pve_cooldowns() -> void:
	_save_json(PVE_COOLDOWNS_PATH, pve_cooldowns)


func save_event_queue() -> void:
	_save_json(EVENT_QUEUE_PATH, event_queue)


func save_sync_status() -> void:
	_save_json(SYNC_STATUS_PATH, sync_status)


func set_server_url(value: String) -> void:
	settings["server_url"] = normalize_server_url(value)
	save_settings()


func normalize_server_url(value: String) -> String:
	var trimmed := value.strip_edges()
	while trimmed.ends_with("/"):
		trimmed = trimmed.substr(0, trimmed.length() - 1)
	if trimmed.is_empty():
		return DEFAULT_SERVER_URL
	if not trimmed.begins_with("http://") and not trimmed.begins_with("https://"):
		trimmed = "http://" + trimmed
	return trimmed


func connection_text_to_server_url(value: String) -> String:
	var text := value.strip_edges()
	var marker := "witcher-larp://connect?server="
	if text.begins_with(marker):
		return normalize_server_url(text.substr(marker.length()).uri_decode())
	return normalize_server_url(text)


func load_bundled_snapshot() -> Dictionary:
	var loaded = _load_json(BUNDLED_SNAPSHOT_PATH, {})
	return loaded if typeof(loaded) == TYPE_DICTIONARY else {}


func bind_player(player_code: String, player_id: String, status: String) -> void:
	session["player_code"] = player_code.strip_edges().to_upper()
	session["player_id"] = player_id
	session["login_status"] = status
	session["last_error"] = ""
	save_session()


func bind_bundled_player_code(player_code: String) -> bool:
	var code_row := lookup_bundled_player_code(player_code)
	if code_row.is_empty():
		session["last_error"] = "Bundled snapshot does not contain player codes; connect to the local server to log in."
		save_session()
		return false

	snapshot = load_bundled_snapshot()
	snapshot_source = "bundled"
	save_snapshot()
	bind_player(player_code, str(code_row.get("player_id", "")), "offline_bundled")
	return true


func lookup_bundled_player_code(player_code: String) -> Dictionary:
	var code := player_code.strip_edges().to_upper()
	if code.is_empty():
		return {}

	var bundled := load_bundled_snapshot()
	if not bundled.has("player_codes"):
		return {}
	for row in bundled.get("player_codes", []):
		if str(row.get("code", "")).to_upper() == code and bool(row.get("enabled", true)):
			return row
	return {}


func set_snapshot(new_snapshot: Dictionary, source: String) -> void:
	snapshot = new_snapshot
	snapshot_source = source
	_merge_unlocked_acts_from_snapshot()
	save_snapshot()


func current_player() -> Dictionary:
	if snapshot.is_empty():
		return {}

	var player_id := str(session.get("player_id", ""))
	if player_id.is_empty():
		return {}

	for player in snapshot.get("players", []):
		if str(player.get("player_id", "")) == player_id:
			return player
	return {}


func normalize_qr_code(value: String) -> String:
	var text := value.strip_edges()
	for marker in [
		"witcher-larp://qr?id=",
		"witcher-larp://qr?code=",
		"witcher-larp://scene?qr="
	]:
		if text.to_lower().begins_with(marker):
			text = text.substr(marker.length())
			break
	return text.strip_edges().to_upper()


func lookup_qr_code(value: String) -> Dictionary:
	var normalized := normalize_qr_code(value)
	if normalized.is_empty():
		return {"status": "empty", "message": "Enter a QR/manual ID."}

	var qr := _find_qr(normalized)
	if qr.is_empty():
		return {
			"status": "unknown_qr",
			"normalized_code": normalized,
			"message": "Unknown QR/manual ID."
		}

	var scenario := _find_by_id(snapshot.get("pve_scenarios", []), "scenario_id", str(qr.get("scenario_id", "")))
	var act := _find_by_id(snapshot.get("acts", []), "act_id", str(qr.get("act_id", "")))
	return {
		"status": "found",
		"normalized_code": normalized,
		"qr": qr,
		"scenario": scenario,
		"act": act,
		"requires_act_unlock": _requires_act_unlock(qr, act),
		"offline_instruction": _offline_instruction(qr)
	}


func offline_unlock_act(code: String) -> Dictionary:
	var normalized := code.strip_edges().to_upper()
	if normalized.is_empty():
		session["last_error"] = "Enter an act unlock code."
		save_session()
		return {}

	var unlock := _find_revealed_act_unlock(normalized)
	if unlock.is_empty():
		session["last_error"] = "Unknown or unrevealed act unlock code."
		save_session()
		return {}

	var act_id := str(unlock.get("act_id", ""))
	if act_id.is_empty():
		session["last_error"] = "Act unlock code has no act_id."
		save_session()
		return {}

	_remember_unlocked_act(act_id)
	var unlocked_at := Time.get_datetime_string_from_system(true)
	return enqueue_event(
		"act_unlocked_offline",
		{
			"act_id": act_id,
			"unlock_id": str(unlock.get("unlock_id", "")),
			"code": normalized,
			"code_sha256": normalized.sha256_text(),
			"verifier_sha256": str(unlock.get("code_sha256", "")),
			"unlock_source": "master_unlock_code",
			"unlocked_at": unlocked_at,
			"snapshot_version": str(snapshot.get("snapshot_version", "")),
			"revealed_at": str(unlock.get("unlock_revealed_at", ""))
		}
	)


func prepare_qr_attempt(value: String, source: String) -> Dictionary:
	var lookup := lookup_qr_code(value)
	var source_type := "qr_scan" if source == "qr_scan" else "manual_id"
	var status := "awaiting_physical_presence"
	var event_type := "qr_attempt"
	var reason := ""

	if lookup.get("status", "") == "empty":
		status = "input_error"
		reason = "empty_qr"
	elif source_type == "manual_id" and _bad_manual_attempt_count() >= QR_MANUAL_LIMIT:
		status = "needs_master_review"
		reason = "manual_rate_limit"
	elif lookup.get("status", "") == "unknown_qr":
		if source_type == "manual_id" and _bad_manual_attempt_count() + 1 >= QR_MANUAL_LIMIT:
			status = "needs_master_review"
			reason = "manual_rate_limit"
		else:
			status = "unknown_qr"
			reason = "unknown_qr"
	elif bool(lookup.get("requires_act_unlock", false)):
		status = "blocked_future_act"
		reason = "future_act_requires_sync_or_unlock"
	else:
		var qr = lookup.get("qr", {})
		var cooldown := active_pve_cooldown(str(qr.get("qr_id", "")) if typeof(qr) == TYPE_DICTIONARY else "")
		if not cooldown.is_empty():
			status = "cooldown_active"
			reason = "pve_failure_cooldown"

	var context := _build_qr_event_context(
		lookup,
		source_type,
		status,
		event_type,
		reason,
		false
	)
	_store_qr_context(context)
	if _should_queue_qr_context(context):
		_queue_qr_context_for_sync(context)
	return last_qr_event_context


func confirm_qr_physical_presence() -> Dictionary:
	if last_qr_event_context.is_empty():
		session["last_error"] = "No QR attempt is ready for confirmation."
		save_session()
		return {}

	var context: Dictionary = last_qr_event_context.duplicate(true)
	if str(context.get("qr_id", "")).is_empty():
		context["local_status"] = "unknown_qr"
		context["review_reason"] = "unknown_qr"
	elif str(context.get("local_status", "")) == "blocked_future_act":
		context["review_reason"] = "future_act_requires_sync_or_unlock"
	elif str(context.get("local_status", "")) == "cooldown_active":
		context["review_reason"] = "pve_failure_cooldown"
	else:
		context["event_type"] = "qr_scene_started"
		context["local_status"] = "ready"
		context["review_reason"] = ""
		context["physical_presence_confirmed"] = true
		context["confirmed_at"] = Time.get_datetime_string_from_system(true)

	_store_qr_context(context)
	if _should_queue_qr_context(context):
		_queue_qr_context_for_sync(context)
	return last_qr_event_context


func flag_qr_honesty_violation(reason: String = "honesty_violation_suspected") -> Dictionary:
	if last_qr_event_context.is_empty():
		session["last_error"] = "No QR attempt is ready for master review."
		save_session()
		return {}

	var context: Dictionary = last_qr_event_context.duplicate(true)
	context["event_type"] = "qr_attempt"
	context["local_status"] = "needs_master_review"
	context["review_reason"] = reason
	context["physical_presence_confirmed"] = false
	_store_qr_context(context)
	_queue_qr_context_for_sync(context)
	return last_qr_event_context


func enqueue_pve_result(result: String) -> Dictionary:
	if last_qr_event_context.is_empty():
		session["last_error"] = "No QR scene context is ready for an offline result."
		save_session()
		return {}

	var context: Dictionary = last_qr_event_context.duplicate(true)
	if str(context.get("event_type", "")) != "qr_scene_started":
		session["last_error"] = "Confirm physical presence before recording a PvE result."
		save_session()
		return {}
	if context.has("pve_result_event_id") and not str(context.get("pve_result_event_id", "")).is_empty():
		session["last_error"] = "This PvE check already has a queued d20 result; sync it or ask a master for recovery."
		save_session()
		return {}

	var normalized_result := result.strip_edges().to_lower()
	if not ["check", "timeout"].has(normalized_result):
		session["last_error"] = "Unsupported PvE result."
		save_session()
		return {}

	var roll_log := _ensure_app_generated_pve_roll(context)
	if roll_log.is_empty():
		session["last_error"] = "PvE roll generation failed; ask a master for recovery."
		save_session()
		return {}

	var payload := _build_pve_result_payload(context, normalized_result, roll_log)
	var event := enqueue_event("pve_completed", payload)
	if not event.is_empty():
		var local_reward := _apply_local_pve_reward(payload, str(event.get("event_id", "")))
		if not local_reward.is_empty():
			event["local_reward_update"] = local_reward
			event["payload"]["local_reward_applied"] = true
			event["payload"]["local_reward_status"] = "pending_sync"
			event["payload"]["local_reward_update"] = local_reward
			_replace_event(event)
		context["pve_result_event_id"] = str(event.get("event_id", ""))
		context["pve_result_queued_at"] = str(event.get("created_at", ""))
		_save_qr_runtime_context(context)
	return event


func enqueue_event(event_type: String, payload: Dictionary, local_status: String = "offline") -> Dictionary:
	var now := Time.get_datetime_string_from_system(true)
	var sequence := _next_client_sequence()
	var record := {
		"event_id": _new_event_id("evt"),
		"device_id": str(settings.get("device_id", "")),
		"player_id": str(session.get("player_id", "")),
		"actor_type": "player",
		"client_sequence": sequence,
		"created_at": now,
		"event_type": event_type,
		"payload": payload.duplicate(true),
		"local_status": local_status,
		"server_status": "",
		"server_event_id": null,
		"sync_attempts": 0,
		"last_error": "",
		"last_sync_started_at": "",
		"last_sync_finished_at": ""
	}
	event_queue.append(record)
	_compact_event_queue()
	save_event_queue()
	_update_sync_status_counts(true)
	return record


func _queue_qr_context_for_sync(context: Dictionary) -> Dictionary:
	if not _should_queue_qr_context(context):
		return {}

	var queued_event_ids = context.get("queued_event_ids", {})
	if typeof(queued_event_ids) != TYPE_DICTIONARY:
		queued_event_ids = {}

	var queue_key := _qr_context_queue_key(context)
	var existing_event_id := str(queued_event_ids.get(queue_key, ""))
	if not existing_event_id.is_empty():
		var existing_event := _event_by_id(existing_event_id)
		if not existing_event.is_empty():
			last_qr_event_context = context
			save_qr_event_context()
			return existing_event

	var event_type := str(context.get("event_type", "qr_attempt"))
	var event := enqueue_event(event_type, _qr_sync_payload(context))
	if event.is_empty():
		return {}

	queued_event_ids[queue_key] = str(event.get("event_id", ""))
	context["queued_event_ids"] = queued_event_ids
	context["last_queued_event_id"] = str(event.get("event_id", ""))
	context["last_queued_event_type"] = event_type
	context["last_queued_at"] = str(event.get("created_at", ""))
	last_qr_event_context = context
	save_qr_event_context()
	return event


func _should_queue_qr_context(context: Dictionary) -> bool:
	var event_type := str(context.get("event_type", ""))
	var local_status := str(context.get("local_status", ""))
	var review_reason := str(context.get("review_reason", ""))
	if event_type == "qr_scene_started":
		return bool(context.get("physical_presence_confirmed", false))
	if event_type != "qr_attempt":
		return false
	return local_status == "needs_master_review" or ["honesty_violation_suspected", "manual_rate_limit"].has(review_reason)


func _qr_context_queue_key(context: Dictionary) -> String:
	return "%s::%s::%s::%s::%s" % [
		str(context.get("event_type", "")),
		str(context.get("local_status", "")),
		str(context.get("review_reason", "")),
		str(context.get("qr_id", "")),
		str(context.get("normalized_code", ""))
	]


func _qr_sync_payload(context: Dictionary) -> Dictionary:
	var payload: Dictionary = context.duplicate(true)
	payload["qr_context_id"] = str(context.get("event_id", ""))
	payload["snapshot_version"] = str(snapshot.get("snapshot_version", ""))
	payload["client_recorded_at"] = Time.get_datetime_string_from_system(true)
	payload.erase("queued_event_ids")
	payload.erase("last_queued_event_id")
	payload.erase("last_queued_event_type")
	payload.erase("last_queued_at")
	if str(payload.get("local_status", "")) == "needs_master_review" or not str(payload.get("review_reason", "")).is_empty():
		payload["requires_master_review"] = true
	return payload


func has_syncable_events() -> bool:
	for event in event_queue:
		if typeof(event) == TYPE_DICTIONARY and SYNC_RETRY_STATUSES.has(str(event.get("local_status", ""))):
			return true
	return false


func prepare_sync_request(max_events: int = 20) -> Dictionary:
	var player_id := str(session.get("player_id", ""))
	if player_id.is_empty():
		sync_status["status"] = "sync_error"
		sync_status["last_error"] = "Login with a player_code before syncing events."
		save_sync_status()
		return {"request": {}, "event_ids": []}

	var request_events := []
	var event_ids := []
	var now := Time.get_datetime_string_from_system(true)
	for index in range(event_queue.size()):
		if request_events.size() >= max_events:
			break
		var event = event_queue[index]
		if typeof(event) != TYPE_DICTIONARY:
			continue
		if not SYNC_RETRY_STATUSES.has(str(event.get("local_status", ""))):
			continue
		if not _event_belongs_to_current_player(event, player_id):
			event["local_status"] = "needs_master_review"
			event["server_status"] = "wrong_actor_queue"
			event["last_error"] = "Queued event belongs to another player/session; ask a master for paper recovery."
			event["last_sync_finished_at"] = now
			event_queue[index] = event
			continue

		event["local_status"] = "pending"
		event["sync_attempts"] = int(event.get("sync_attempts", 0)) + 1
		event["last_sync_started_at"] = now
		event["last_error"] = ""
		event_queue[index] = event
		event_ids.append(str(event.get("event_id", "")))
		request_events.append({
			"event_id": str(event.get("event_id", "")),
			"client_sequence": int(event.get("client_sequence", 0)),
			"created_at": event.get("created_at", now),
			"event_type": str(event.get("event_type", "")),
			"payload": event.get("payload", {})
		})

	save_event_queue()
	_update_sync_status_counts(true)
	if request_events.is_empty():
		return {"request": {}, "event_ids": []}

	return {
		"request": {
			"device_id": str(settings.get("device_id", "")),
			"actor_id": player_id,
			"actor_type": "player",
			"events": request_events
		},
		"event_ids": event_ids
	}


func _event_belongs_to_current_player(event: Dictionary, player_id: String) -> bool:
	var event_player_id := str(event.get("player_id", ""))
	if event_player_id.is_empty():
		return true
	return event_player_id == player_id


func mark_sync_batch_error(event_ids: Array, message: String, response_code: int = 0) -> void:
	var now := Time.get_datetime_string_from_system(true)
	for event_id in event_ids:
		var index := _find_event_index(str(event_id))
		if index < 0:
			continue
		var event = event_queue[index]
		event["local_status"] = "sync_error"
		event["last_error"] = message
		event["last_sync_finished_at"] = now
		event_queue[index] = event
	sync_status["status"] = "sync_error"
	sync_status["last_error"] = message
	sync_status["last_sync_at"] = now
	sync_status["last_response_code"] = response_code
	save_event_queue()
	_update_sync_status_counts(true)


func apply_sync_response(event_ids: Array, response_code: int, response: Dictionary) -> void:
	var now := Time.get_datetime_string_from_system(true)
	if response_code < 200 or response_code >= 300 or response.is_empty():
		mark_sync_batch_error(event_ids, "Event sync failed with HTTP %d." % response_code, response_code)
		return

	var results_by_id := {}
	for result in response.get("results", []):
		if typeof(result) == TYPE_DICTIONARY:
			results_by_id[str(result.get("event_id", ""))] = result

	for event_id in event_ids:
		var index := _find_event_index(str(event_id))
		if index < 0:
			continue
		var event = event_queue[index]
		var result = results_by_id.get(str(event_id), {})
		if typeof(result) != TYPE_DICTIONARY or result.is_empty():
			event["local_status"] = "sync_error"
			event["last_error"] = "Server response omitted event_id."
		else:
			var server_status := str(result.get("status", ""))
			event["server_status"] = server_status
			event["server_event_id"] = result.get("server_event_id", null)
			event["last_error"] = str(result.get("reason", ""))
			if server_status == "accepted" or server_status == "duplicate":
				event["local_status"] = "synced"
			elif server_status == "needs_master_review" or server_status == "pending_master_approval" or server_status == "rejected":
				event["local_status"] = "needs_master_review"
			else:
				event["local_status"] = "sync_error"
				event["last_error"] = "Unsupported server status: %s" % server_status
		event["last_sync_finished_at"] = now
		event_queue[index] = event

	sync_status["last_sync_at"] = now
	sync_status["last_response_code"] = response_code
	sync_status["last_error"] = ""
	_compact_event_queue()
	save_event_queue()
	_update_sync_status_counts(true)


func event_queue_summary() -> String:
	_update_sync_status_counts(false)
	var latest := _latest_event()
	var latest_line := "Latest: none"
	if not latest.is_empty():
		latest_line = "Latest: #%s %s %s (%s)" % [
			str(latest.get("client_sequence", "")),
			str(latest.get("event_type", "")),
			str(latest.get("local_status", "")),
			str(latest.get("last_error", ""))
		]
	return "Sync: %s\nQueued: %d, Pending: %d, Synced: %d, Errors: %d, Review: %d\nLast sync: %s\n%s" % [
		str(sync_status.get("status", "offline")),
		int(sync_status.get("queued_count", 0)),
		int(sync_status.get("pending_count", 0)),
		int(sync_status.get("synced_count", 0)),
		int(sync_status.get("sync_error_count", 0)),
		int(sync_status.get("review_count", 0)),
		str(sync_status.get("last_sync_at", "never")),
		latest_line
	]


func qr_context_summary() -> String:
	if last_qr_event_context.is_empty():
		return "No QR/manual ID prepared."

	var context := last_qr_event_context
	return "Status: %s\nEvent: %s\nQR: %s / %s\nMode: %s\nAct: %s\nScenario: %s\nPresence confirmed: %s\nInstruction: %s\nReview: %s" % [
		str(context.get("local_status", "")),
		str(context.get("event_type", "")),
		str(context.get("qr_id", "")),
		str(context.get("manual_code", "")),
		str(context.get("qr_mode", "")),
		str(context.get("act_id", "")),
		str(context.get("scenario_id", "")),
		str(context.get("physical_presence_confirmed", false)),
		str(context.get("offline_instruction", "")),
		str(context.get("review_reason", ""))
	]


func is_act_unlocked(act_id: String) -> bool:
	if act_id == "act1":
		return true
	var unlocked = session.get("unlocked_acts", ["act1"])
	if typeof(unlocked) != TYPE_ARRAY:
		return false
	return unlocked.has(act_id)


func _merge_unlocked_acts_from_snapshot() -> void:
	if snapshot.is_empty():
		return
	var state = snapshot.get("act_unlock_state", {})
	if typeof(state) != TYPE_DICTIONARY:
		return
	var changed := false
	for act_id in state.get("unlocked_act_ids", []):
		changed = _remember_unlocked_act(str(act_id), false) or changed
	if changed:
		save_session()


func _remember_unlocked_act(act_id: String, should_save: bool = true) -> bool:
	if act_id.is_empty():
		return false
	var unlocked = session.get("unlocked_acts", ["act1"])
	if typeof(unlocked) != TYPE_ARRAY:
		unlocked = ["act1"]
	if unlocked.has(act_id):
		return false
	unlocked.append(act_id)
	session["unlocked_acts"] = unlocked
	if should_save:
		save_session()
	return true


func _find_revealed_act_unlock(normalized_code: String) -> Dictionary:
	for row in snapshot.get("act_unlock_codes", []):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		if not _truthy(row.get("revealed", false)):
			continue
		var raw_code := str(row.get("code", "")).strip_edges().to_upper()
		if not raw_code.is_empty() and raw_code == normalized_code:
			return row
		var code_hash := str(row.get("code_sha256", ""))
		if not code_hash.is_empty() and normalized_code.sha256_text() == code_hash:
			return row
	return {}


func active_pve_cooldown(qr_id: String) -> Dictionary:
	_cleanup_pve_cooldowns()
	var key := _pve_cooldown_key(str(session.get("player_id", "")), qr_id)
	var cooldown = pve_cooldowns.get(key, {})
	return cooldown if typeof(cooldown) == TYPE_DICTIONARY else {}


func player_reputation_display(player: Dictionary) -> String:
	var state = player.get("reputation_state", {})
	if typeof(state) != TYPE_DICTIONARY:
		return "Hidden"

	var label := str(state.get("state_label", state.get("canonical_label", ""))).strip_edges()
	var descriptor := str(state.get("player_descriptor", "")).strip_edges()
	if not label.is_empty() and not descriptor.is_empty():
		return "%s (%s)" % [label, descriptor]
	if not label.is_empty():
		return label
	if not descriptor.is_empty():
		return descriptor
	return "Hidden"


func clear_session() -> void:
	session = {
		"player_id": "",
		"player_code": "",
		"login_status": "signed_out",
		"last_error": "",
		"unlocked_acts": ["act1"]
	}
	save_session()


func _find_qr(normalized_code: String) -> Dictionary:
	for row in snapshot.get("qr_objects", []):
		if typeof(row) == TYPE_DICTIONARY:
			var manual_code := str(row.get("manual_code", "")).to_upper()
			if manual_code == normalized_code:
				return row
	return {}


func _find_by_id(rows: Variant, id_key: String, row_id: String) -> Dictionary:
	if typeof(rows) != TYPE_ARRAY:
		return {}
	for row in rows:
		if typeof(row) == TYPE_DICTIONARY and str(row.get(id_key, "")) == row_id:
			return row
	return {}


func _requires_act_unlock(qr: Dictionary, act: Dictionary) -> bool:
	var act_id := str(qr.get("act_id", ""))
	if is_act_unlocked(act_id):
		return false
	if not act.is_empty():
		return _truthy(act.get("unlock_required", false))
	return act_id != "act1" and not act_id.is_empty()


func _offline_instruction(qr: Dictionary) -> String:
	if str(qr.get("qr_mode", "")) == "unique_object" or str(qr.get("consumption_rule", "")) == "consume_once":
		return "success_take_physical_qr_failure_leave_it"
	return "repeatable_scene_no_physical_qr_consumption"


func _build_qr_event_context(
	lookup: Dictionary,
	source_type: String,
	status: String,
	event_type: String,
	reason: String,
	physical_presence_confirmed: bool
) -> Dictionary:
	var qr: Dictionary = lookup.get("qr", {})
	var scenario: Dictionary = lookup.get("scenario", {})
	var now := Time.get_datetime_string_from_system(true)
	return {
		"event_id": _new_event_id("qr"),
		"event_type": event_type,
		"local_status": status,
		"review_reason": reason,
		"source": source_type,
		"player_id": str(session.get("player_id", "")),
		"device_id": str(settings.get("device_id", "")),
		"normalized_code": str(lookup.get("normalized_code", "")),
		"qr_id": str(qr.get("qr_id", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"manual_code": str(qr.get("manual_code", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"qr_mode": str(qr.get("qr_mode", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"consumption_rule": str(qr.get("consumption_rule", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"act_id": str(qr.get("act_id", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"scenario_id": str(qr.get("scenario_id", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"scene_type": str(scenario.get("scene_type", "")) if typeof(scenario) == TYPE_DICTIONARY else "",
		"location_node_id": str(qr.get("location_node_id", "")) if typeof(qr) == TYPE_DICTIONARY else "",
		"physical_presence_required": _truthy(qr.get("physical_presence_required", true)) if typeof(qr) == TYPE_DICTIONARY else true,
		"physical_presence_confirmed": physical_presence_confirmed,
		"honesty_notice": "physical_presence_only",
		"offline_instruction": str(lookup.get("offline_instruction", "")),
		"created_at": now,
		"created_at_unix": Time.get_unix_time_from_system()
	}


func _store_qr_context(context: Dictionary) -> void:
	last_qr_event_context = context
	save_qr_event_context()
	_record_qr_attempt(context)


func _save_qr_runtime_context(context: Dictionary) -> void:
	last_qr_event_context = context
	save_qr_event_context()


func _ensure_app_generated_pve_roll(context: Dictionary) -> Array:
	var existing: Variant = context.get("pve_roll_log", [])
	if typeof(existing) == TYPE_ARRAY and not existing.is_empty() and typeof(existing[0]) == TYPE_DICTIONARY:
		var existing_rolls: Array = existing
		return existing_rolls.duplicate(true)

	var scenario := _find_by_id(snapshot.get("pve_scenarios", []), "scenario_id", str(context.get("scenario_id", "")))
	if scenario.is_empty():
		return []
	var stat_name := str(scenario.get("primary_stat", "Сила"))
	var stat_value := _player_stat_value(stat_name)
	var dc := _to_int(scenario.get("dc", 10))
	var created_at := Time.get_datetime_string_from_system(true)
	var check_id := str(context.get("event_id", ""))
	if check_id.is_empty():
		check_id = _new_event_id("check")
		context["event_id"] = check_id
	var roll_value := _generate_d20_roll()
	var roll_entry := {
		"roll_id": _new_event_id("roll"),
		"check_id": check_id,
		"source": "app_generated",
		"created_at": created_at,
		"rolled_at": created_at,
		"player_id": str(session.get("player_id", "")),
		"qr_id": str(context.get("qr_id", "")),
		"scenario_id": str(context.get("scenario_id", "")),
		"die": "d20",
		"roll": roll_value,
		"roll_value": roll_value,
		"stat": stat_name,
		"stat_value": stat_value,
		"dc": dc,
		"modifiers": []
	}
	context["pve_roll_log"] = [roll_entry]
	context["pve_roll_created_at"] = created_at
	_save_qr_runtime_context(context)
	return [roll_entry]


func _generate_d20_roll() -> int:
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	return rng.randi_range(1, 20)


func _record_qr_attempt(context: Dictionary) -> void:
	qr_attempts.append(context.duplicate(true))
	if qr_attempts.size() > 100:
		qr_attempts = qr_attempts.slice(qr_attempts.size() - 100, qr_attempts.size())
	save_qr_attempts()


func _bad_manual_attempt_count() -> int:
	var cutoff := Time.get_unix_time_from_system() - QR_RATE_WINDOW_SECONDS
	var count := 0
	for attempt in qr_attempts:
		if typeof(attempt) != TYPE_DICTIONARY:
			continue
		if str(attempt.get("source", "")) != "manual_id":
			continue
		if int(attempt.get("created_at_unix", 0)) < cutoff:
			continue
		var status := str(attempt.get("local_status", ""))
		var reason := str(attempt.get("review_reason", ""))
		if status == "unknown_qr" or reason == "manual_rate_limit":
			count += 1
	return count


func _build_pve_result_payload(context: Dictionary, result: String, roll_log: Array) -> Dictionary:
	var completed_at := Time.get_datetime_string_from_system(true)
	var scenario := _find_by_id(snapshot.get("pve_scenarios", []), "scenario_id", str(context.get("scenario_id", "")))
	var mob := _find_by_id(snapshot.get("mobs", []), "mob_id", str(scenario.get("combat_profile_id", "")))
	var reward := _find_by_id(snapshot.get("rewards", []), "reward_id", str(scenario.get("reward_id", "")))
	var combat_rule := _first_combat_rule()
	var stat_name := str(scenario.get("primary_stat", "Сила"))
	var stat_value := _player_stat_value(stat_name)
	var dc := _to_int(scenario.get("dc", 10))
	var roll_entry := _coerce_roll_entry(roll_log, stat_name, stat_value, dc)
	var roll := _to_int(roll_entry.get("roll", 1))
	var modifiers := _normalize_modifiers(roll_entry.get("modifiers", []))
	var modifier_total := 0
	for modifier in modifiers:
		modifier_total += _to_int(modifier.get("value", 0))
	var total := roll + stat_value + modifier_total
	var calculated_outcome := _calculate_pve_outcome(total, dc)
	if result == "check":
		result = calculated_outcome
	var tier := _to_int(scenario.get("tier", 1))
	var scene_hp := _to_int(mob.get("scene_hp", 0))
	if scene_hp <= 0:
		scene_hp = _default_scene_hp(tier)
	var base_damage: int = int(max(1, _to_int(combat_rule.get("base_damage", 1))))
	var margin: int = int(max(0, total - dc))
	var damage: int = scene_hp if result == "success" else base_damage + int(floor(float(margin) / 5.0))
	var scene_hp_remaining: int = 0 if result == "success" else int(max(0, scene_hp - damage))
	var player_scene_hp: int = int(max(7, 6 + _to_int(current_player().get("level", 1))))
	var scene_damage: int = _to_int(mob.get("scene_damage", 0))
	var player_scene_hp_remaining: int = int(max(0, player_scene_hp - scene_damage)) if ["failure", "timeout"].has(result) else player_scene_hp
	var cooldown_until := ""
	if ["failure", "timeout"].has(result):
		cooldown_until = _cooldown_until_string(PVE_FAILURE_COOLDOWN_SECONDS)
		_store_pve_cooldown(str(context.get("qr_id", "")), cooldown_until)
	var reward_id := str(scenario.get("reward_id", ""))
	var reward_approval_policy := str(reward.get("approval_policy", "auto"))
	var reward_status := "none"
	if result == "success" and not reward_id.is_empty():
		reward_status = "auto"
	var replay_roll := {
		"roll_id": str(roll_entry.get("roll_id", "")),
		"check_id": str(roll_entry.get("check_id", context.get("event_id", ""))),
		"source": str(roll_entry.get("source", "app_generated")),
		"created_at": str(roll_entry.get("created_at", roll_entry.get("rolled_at", completed_at))),
		"player_id": str(roll_entry.get("player_id", session.get("player_id", ""))),
		"qr_id": str(roll_entry.get("qr_id", context.get("qr_id", ""))),
		"scenario_id": str(roll_entry.get("scenario_id", context.get("scenario_id", ""))),
		"die": "d20",
		"roll": roll,
		"roll_value": roll,
		"stat": stat_name,
		"stat_value": stat_value,
		"modifiers": modifiers,
		"total": total,
		"dc": dc,
		"outcome": calculated_outcome,
		"rolled_at": str(roll_entry.get("rolled_at", completed_at))
	}
	var payload := {
		"qr_id": str(context.get("qr_id", "")),
		"scenario_id": str(context.get("scenario_id", "")),
		"check_id": str(replay_roll.get("check_id", "")),
		"roll_source": str(replay_roll.get("source", "app_generated")),
		"result": result,
		"outcome": calculated_outcome,
		"roll": roll,
		"stat": stat_name,
		"stat_value": stat_value,
		"modifiers": modifiers,
		"total": total,
		"dc": dc,
		"check_policy": "single_d20",
		"combat_dc": _to_int(mob.get("combat_dc", dc)),
		"rounds": [
			{
				"round": 1,
				"action": "attack/check",
				"roll": replay_roll,
				"damage": damage,
				"scene_hp_remaining": scene_hp_remaining,
				"player_scene_hp_remaining": player_scene_hp_remaining
			}
		],
		"roll_log": [replay_roll],
		"scene_hp": scene_hp,
		"scene_hp_remaining": scene_hp_remaining,
		"player_scene_hp": player_scene_hp,
		"player_scene_hp_remaining": player_scene_hp_remaining,
		"reward_id": reward_id,
		"reward_approval_policy": reward_approval_policy,
		"reward_status": reward_status,
		"cooldown_until": cooldown_until,
		"qr_mode": str(context.get("qr_mode", "")),
		"consumption_rule": str(context.get("consumption_rule", "")),
		"act_id": str(context.get("act_id", "")),
		"unlock_source": "act1_default" if str(context.get("act_id", "")) == "act1" else "server_sync",
		"source": str(context.get("source", "")),
		"physical_presence_confirmed": bool(context.get("physical_presence_confirmed", false)),
		"scene_started_at": str(context.get("confirmed_at", context.get("created_at", ""))),
		"completed_at": completed_at,
		"client_recorded_at": completed_at,
		"role_load_profile": "5_witchers_4_field_sorceresses",
		"timeout_outcome": str(scenario.get("timeout_outcome", "fail_and_cooldown")),
		"player_scene_hp_reset_after_scene": true
	}
	if typeof(scenario) == TYPE_DICTIONARY and not scenario.is_empty():
		payload["scene_type"] = str(scenario.get("scene_type", ""))
		payload["primary_stat"] = stat_name
	return payload


func _coerce_roll_entry(roll_log: Array, stat_name: String, stat_value: int, dc: int) -> Dictionary:
	var completed_at := Time.get_datetime_string_from_system(true)
	if not roll_log.is_empty() and typeof(roll_log[0]) == TYPE_DICTIONARY:
		var source_entry: Dictionary = roll_log[0]
		var entry: Dictionary = source_entry.duplicate(true)
		if not entry.has("roll"):
			entry["roll"] = entry.get("roll_value", entry.get("value", 1))
		if not entry.has("roll_value"):
			entry["roll_value"] = entry.get("roll", 1)
		entry["source"] = str(entry.get("source", "app_generated"))
		entry["die"] = "d20"
		entry["stat"] = str(entry.get("stat", stat_name))
		entry["stat_value"] = _to_int(entry.get("stat_value", stat_value))
		entry["dc"] = _to_int(entry.get("dc", dc))
		entry["modifiers"] = _normalize_modifiers(entry.get("modifiers", []))
		entry["rolled_at"] = str(entry.get("rolled_at", completed_at))
		entry["created_at"] = str(entry.get("created_at", entry.get("rolled_at", completed_at)))
		return entry
	var fallback_roll := _generate_d20_roll()
	return {
		"roll_id": _new_event_id("roll"),
		"check_id": _new_event_id("check"),
		"source": "app_generated",
		"created_at": completed_at,
		"die": "d20",
		"roll": fallback_roll,
		"roll_value": fallback_roll,
		"stat": stat_name,
		"stat_value": stat_value,
		"dc": dc,
		"modifiers": [],
		"rolled_at": completed_at
	}


func _apply_local_pve_reward(payload: Dictionary, event_id: String) -> Dictionary:
	var result := str(payload.get("result", payload.get("outcome", "")))
	if result != "success":
		return {}
	var reward_id := str(payload.get("reward_id", ""))
	if reward_id.is_empty():
		return {}
	var reward := _find_by_id(snapshot.get("rewards", []), "reward_id", reward_id)
	if reward.is_empty():
		return {}
	var player_id := str(session.get("player_id", ""))
	if player_id.is_empty():
		return {}
	var player_index := _find_snapshot_player_index(player_id)
	if player_index < 0:
		return {}

	var applied_event_ids: Variant = snapshot.get("local_reward_event_ids", [])
	if typeof(applied_event_ids) != TYPE_ARRAY:
		applied_event_ids = []
	if applied_event_ids.has(event_id):
		return {}

	var players: Array = snapshot.get("players", [])
	var player: Dictionary = players[player_index].duplicate(true)
	var xp_before := _to_int(player.get("xp", 0))
	var gold_before := _to_int(player.get("gold", 0))
	var level_before := _to_int(player.get("level", 1))
	var xp_gain := _to_int(reward.get("xp", 0))
	var gold_gain := _to_int(reward.get("gold", 0))
	var level_result := _spend_xp_for_levels(level_before, xp_before + xp_gain)
	var xp_after := _to_int(level_result.get("xp", xp_before + xp_gain))
	var gold_after := gold_before + gold_gain
	var level_after := _to_int(level_result.get("level", level_before))
	var stats := _player_stats(player).duplicate(true)
	var stat_gains := _apply_local_level_stat_gains(
		stats,
		max(0, level_after - level_before),
		str(payload.get("stat", ""))
	)

	player["xp"] = xp_after
	player["gold"] = gold_after
	player["level"] = level_after
	if not stats.is_empty():
		player["stats"] = stats
		player["stats_json"] = JSON.stringify(stats)
	player["local_reward_status"] = "pending_sync"
	player["local_reward_event_id"] = event_id
	player["local_reward_id"] = reward_id
	player["local_reward_applied_at"] = Time.get_datetime_string_from_system(true)

	players[player_index] = player
	snapshot["players"] = players
	var current_player_payload = snapshot.get("player", {})
	if typeof(current_player_payload) == TYPE_DICTIONARY and str(current_player_payload.get("player_id", "")) == player_id:
		snapshot["player"] = player.duplicate(true)
	applied_event_ids.append(event_id)
	snapshot["local_reward_event_ids"] = applied_event_ids
	save_snapshot()

	return {
		"status": "applied_locally",
		"sync_status": "pending_sync",
		"reward_id": reward_id,
		"event_id": event_id,
		"xp_gain": xp_gain,
		"gold_gain": gold_gain,
		"xp_before": xp_before,
		"xp_after": xp_after,
		"gold_before": gold_before,
		"gold_after": gold_after,
		"level_before": level_before,
		"level_after": level_after,
		"stat_gains": stat_gains
	}


func _find_snapshot_player_index(player_id: String) -> int:
	var players: Variant = snapshot.get("players", [])
	if typeof(players) != TYPE_ARRAY:
		return -1
	for index in range(players.size()):
		var player = players[index]
		if typeof(player) == TYPE_DICTIONARY and str(player.get("player_id", "")) == player_id:
			return index
	return -1


func _spend_xp_for_levels(level_before: int, xp_available: int) -> Dictionary:
	var costs := _level_costs_from_rules()
	var level: int = int(max(level_before, 1))
	var remaining_xp: int = int(max(xp_available, 0))
	while true:
		var next_cost := _next_level_cost(costs, level)
		if next_cost <= 0 or remaining_xp < next_cost:
			break
		remaining_xp -= next_cost
		level += 1
	return {
		"xp": remaining_xp,
		"level": level
	}


func _level_costs_from_rules() -> Array:
	var costs := [0, 10, 25, 45, 70, 100, 135, 175, 220, 270]
	var rules = snapshot.get("checks", {}).get("xp_rules", []) if typeof(snapshot.get("checks", {})) == TYPE_DICTIONARY else []
	if typeof(rules) == TYPE_ARRAY and not rules.is_empty() and typeof(rules[0]) == TYPE_DICTIONARY:
		var raw_thresholds := str(rules[0].get("level_thresholds", ""))
		var parsed_costs := []
		for part in raw_thresholds.split(";"):
			var trimmed := part.strip_edges()
			if not trimmed.is_empty():
				parsed_costs.append(_to_int(trimmed))
		if not parsed_costs.is_empty():
			costs = parsed_costs
	return costs


func _next_level_cost(costs: Array, current_level: int) -> int:
	var index := current_level - 1
	if not costs.is_empty() and _to_int(costs[0]) == 0:
		index = current_level
	if index < 0 or index >= costs.size():
		return 0
	return _to_int(costs[index])


func _apply_local_level_stat_gains(stats: Dictionary, level_count: int, preferred_stat: String) -> Array:
	var gains := []
	var max_stat := _max_local_stat()
	for _index in range(level_count):
		var stat_name := _stat_to_raise(stats, preferred_stat)
		if stat_name.is_empty():
			break
		var before := _to_int(stats.get(stat_name, 0))
		var after: int = int(min(max_stat, before + 1))
		stats[stat_name] = after
		gains.append({"stat": stat_name, "before": before, "after": after})
	return gains


func _stat_to_raise(stats: Dictionary, preferred_stat: String) -> String:
	if not preferred_stat.is_empty() and stats.has(preferred_stat):
		return preferred_stat
	var best_stat := ""
	var best_value := 100000
	for key in stats.keys():
		var value := _to_int(stats.get(key, 0))
		if best_stat.is_empty() or value < best_value:
			best_stat = str(key)
			best_value = value
	return best_stat


func _max_local_stat() -> int:
	var rules = snapshot.get("checks", {}).get("xp_rules", []) if typeof(snapshot.get("checks", {})) == TYPE_DICTIONARY else []
	if typeof(rules) == TYPE_ARRAY and not rules.is_empty() and typeof(rules[0]) == TYPE_DICTIONARY:
		var max_stat := _to_int(rules[0].get("max_stat", 7))
		if max_stat > 0:
			return max_stat
	return 7


func _calculate_pve_outcome(total: int, dc: int) -> String:
	if total >= dc:
		return "success"
	if total >= dc - 2:
		return "partial_success"
	return "failure"


func _normalize_modifiers(modifiers: Variant) -> Array:
	if typeof(modifiers) != TYPE_ARRAY:
		return []
	var normalized := []
	for index in range(modifiers.size()):
		var modifier = modifiers[index]
		if typeof(modifier) != TYPE_DICTIONARY:
			continue
		var source := str(modifier.get("source", modifier.get("type", "system")))
		normalized.append({
			"source": source,
			"label": str(modifier.get("label", source)),
			"value": _to_int(modifier.get("value", 0))
		})
	return normalized


func _player_stat_value(stat_name: String) -> int:
	var stats := _player_stats(current_player())
	return _to_int(stats.get(stat_name, 0))


func _player_stats(player: Dictionary) -> Dictionary:
	if player.has("stats") and typeof(player.get("stats", {})) == TYPE_DICTIONARY:
		return player.get("stats", {})
	var raw := str(player.get("stats_json", "{}"))
	var parsed = JSON.parse_string(raw)
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


func _first_combat_rule() -> Dictionary:
	var rules = snapshot.get("checks", {}).get("combat_rules", []) if typeof(snapshot.get("checks", {})) == TYPE_DICTIONARY else []
	if typeof(rules) == TYPE_ARRAY and not rules.is_empty() and typeof(rules[0]) == TYPE_DICTIONARY:
		return rules[0]
	return {
		"base_damage": 1,
		"failure_cooldown_min": 30,
		"timeout_outcome": "fail_and_cooldown"
	}


func _default_scene_hp(tier: int) -> int:
	if tier <= 1:
		return 6
	if tier == 2:
		return 10
	if tier == 3:
		return 14
	return 18


func _cooldown_until_string(seconds: int) -> String:
	var unix_time := int(Time.get_unix_time_from_system()) + seconds
	return Time.get_datetime_string_from_unix_time(unix_time, true)


func _store_pve_cooldown(qr_id: String, cooldown_until: String) -> void:
	var player_id := str(session.get("player_id", ""))
	if player_id.is_empty() or qr_id.is_empty():
		return
	pve_cooldowns[_pve_cooldown_key(player_id, qr_id)] = {
		"player_id": player_id,
		"qr_id": qr_id,
		"cooldown_until": cooldown_until,
		"reason": "pve_failure",
		"created_at": Time.get_datetime_string_from_system(true)
	}
	save_pve_cooldowns()


func _cleanup_pve_cooldowns() -> void:
	var now := Time.get_unix_time_from_system()
	var changed := false
	for key in pve_cooldowns.keys():
		var cooldown = pve_cooldowns.get(key, {})
		if typeof(cooldown) != TYPE_DICTIONARY:
			pve_cooldowns.erase(key)
			changed = true
			continue
		var until_text := str(cooldown.get("cooldown_until", ""))
		var unix := Time.get_unix_time_from_datetime_string(until_text)
		if unix > 0 and unix <= now:
			pve_cooldowns.erase(key)
			changed = true
	if changed:
		save_pve_cooldowns()


func _pve_cooldown_key(player_id: String, qr_id: String) -> String:
	return "%s::%s" % [player_id, qr_id]


func _to_int(value: Variant) -> int:
	if value == null or str(value).is_empty():
		return 0
	return int(value)


func _next_client_sequence() -> int:
	var next_sequence := int(settings.get("last_client_sequence", 0)) + 1
	settings["last_client_sequence"] = next_sequence
	save_settings()
	return next_sequence


func _refresh_sequence_from_queue() -> void:
	var max_sequence := int(settings.get("last_client_sequence", 0))
	for event in event_queue:
		if typeof(event) == TYPE_DICTIONARY:
			max_sequence = max(max_sequence, int(event.get("client_sequence", 0)))
	if max_sequence != int(settings.get("last_client_sequence", 0)):
		settings["last_client_sequence"] = max_sequence
		save_settings()


func _find_event_index(event_id: String) -> int:
	for index in range(event_queue.size()):
		var event = event_queue[index]
		if typeof(event) == TYPE_DICTIONARY and str(event.get("event_id", "")) == event_id:
			return index
	return -1


func _replace_event(event: Dictionary) -> void:
	var index := _find_event_index(str(event.get("event_id", "")))
	if index < 0:
		return
	event_queue[index] = event
	save_event_queue()
	_update_sync_status_counts(true)


func _event_by_id(event_id: String) -> Dictionary:
	var index := _find_event_index(event_id)
	if index < 0:
		return {}
	var event = event_queue[index]
	return event if typeof(event) == TYPE_DICTIONARY else {}


func _latest_event() -> Dictionary:
	if event_queue.is_empty():
		return {}
	for index in range(event_queue.size() - 1, -1, -1):
		var event = event_queue[index]
		if typeof(event) == TYPE_DICTIONARY:
			return event
	return {}


func _compact_event_queue() -> void:
	if event_queue.size() <= EVENT_HISTORY_LIMIT:
		return
	var unsynced := []
	var history := []
	for event in event_queue:
		if typeof(event) != TYPE_DICTIONARY:
			continue
		if str(event.get("local_status", "")) == "synced":
			history.append(event)
		else:
			unsynced.append(event)

	var remaining_history_slots = max(EVENT_HISTORY_LIMIT - unsynced.size(), 0)
	if history.size() > remaining_history_slots:
		history = history.slice(history.size() - remaining_history_slots, history.size())
	event_queue = history + unsynced


func _update_sync_status_counts(should_save: bool) -> void:
	var queued := 0
	var pending := 0
	var synced := 0
	var errors := 0
	var review := 0
	for event in event_queue:
		if typeof(event) != TYPE_DICTIONARY:
			continue
		var status := str(event.get("local_status", "offline"))
		if status == "offline":
			queued += 1
		elif status == "pending":
			pending += 1
		elif status == "synced":
			synced += 1
		elif status == "sync_error":
			errors += 1
		elif status == "needs_master_review":
			review += 1

	sync_status["queued_count"] = queued
	sync_status["pending_count"] = pending
	sync_status["synced_count"] = synced
	sync_status["sync_error_count"] = errors
	sync_status["review_count"] = review
	if pending > 0:
		sync_status["status"] = "pending"
	elif errors > 0:
		sync_status["status"] = "sync_error"
	elif review > 0:
		sync_status["status"] = "needs_master_review"
	elif queued > 0:
		sync_status["status"] = "offline"
	elif synced > 0:
		sync_status["status"] = "synced"
	else:
		sync_status["status"] = "offline"
	if should_save:
		save_sync_status()


func _truthy(value: Variant) -> bool:
	if typeof(value) == TYPE_BOOL:
		return value
	return str(value).to_lower() == "true"


func _new_event_id(prefix: String) -> String:
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	return "%s-%d-%d" % [prefix, Time.get_unix_time_from_system(), rng.randi()]


func _load_json(path: String, fallback: Variant) -> Variant:
	if not FileAccess.file_exists(path):
		return _copy_fallback(fallback)

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _copy_fallback(fallback)

	var parsed = JSON.parse_string(file.get_as_text())
	if parsed == null:
		return _copy_fallback(fallback)
	return parsed


func _copy_fallback(fallback: Variant) -> Variant:
	if typeof(fallback) == TYPE_DICTIONARY or typeof(fallback) == TYPE_ARRAY:
		return fallback.duplicate(true)
	return fallback


func _save_json(path: String, data: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(data, "\t"))


func _new_device_id() -> String:
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	return "device-%d-%d" % [Time.get_unix_time_from_system(), rng.randi()]
