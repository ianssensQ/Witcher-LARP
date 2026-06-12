extends Node

signal qr_scanned(text: String)
signal scanner_error(message: String)
signal permission_changed(allowed: bool)

const PLUGIN_SINGLETON := "WitcherQrScanner"

var _plugin = null
var _is_running := false
var _last_rect := Rect2()


func is_native_scanner_available() -> bool:
	return Engine.has_singleton(PLUGIN_SINGLETON)


func is_scanning() -> bool:
	if _plugin and _plugin.has_method("is_scanning"):
		return bool(_plugin.call("is_scanning"))
	return _is_running


func request_camera_permission() -> bool:
	if not _ensure_plugin():
		return false
	if _plugin.has_method("request_camera_permission"):
		_plugin.call("request_camera_permission")
		return true
	return false


func start_scan_normalized(scan_rect: Rect2) -> bool:
	if not _ensure_plugin():
		return false
	if not _plugin.has_method("start_scan_normalized"):
		scanner_error.emit("Native QR scanner plugin does not expose start_scan_normalized.")
		return false

	var clamped_rect := _clamp_rect(scan_rect)
	if _is_running and clamped_rect == _last_rect:
		return true

	_last_rect = clamped_rect
	_plugin.call(
		"start_scan_normalized",
		clamped_rect.position.x,
		clamped_rect.position.y,
		clamped_rect.size.x,
		clamped_rect.size.y
	)
	_is_running = true
	return true


func stop_scan() -> void:
	if _plugin and _plugin.has_method("stop_scan"):
		_plugin.call("stop_scan")
	_is_running = false


func _ensure_plugin() -> bool:
	if not Engine.has_singleton(PLUGIN_SINGLETON):
		return false
	_plugin = Engine.get_singleton(PLUGIN_SINGLETON)
	_connect_plugin_signal("qr_scanned", Callable(self, "_on_native_qr_scanned"))
	_connect_plugin_signal("scanner_error", Callable(self, "_on_native_scanner_error"))
	_connect_plugin_signal("permission_changed", Callable(self, "_on_native_permission_changed"))
	return true


func _connect_plugin_signal(signal_name: StringName, target: Callable) -> void:
	if not _plugin.has_signal(signal_name):
		return
	if not _plugin.is_connected(signal_name, target):
		_plugin.connect(signal_name, target)


func _clamp_rect(scan_rect: Rect2) -> Rect2:
	var x: float = clamp(scan_rect.position.x, 0.0, 1.0)
	var y: float = clamp(scan_rect.position.y, 0.0, 1.0)
	var right: float = clamp(scan_rect.position.x + scan_rect.size.x, x, 1.0)
	var bottom: float = clamp(scan_rect.position.y + scan_rect.size.y, y, 1.0)
	return Rect2(Vector2(x, y), Vector2(max(0.05, right - x), max(0.05, bottom - y)))


func _on_native_qr_scanned(text: String) -> void:
	_is_running = false
	qr_scanned.emit(text)


func _on_native_scanner_error(message: String) -> void:
	_is_running = false
	scanner_error.emit(message)


func _on_native_permission_changed(allowed: bool) -> void:
	permission_changed.emit(allowed)
