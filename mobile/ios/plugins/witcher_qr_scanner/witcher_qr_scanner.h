#ifndef WITCHER_QR_SCANNER_H
#define WITCHER_QR_SCANNER_H

#include "core/version.h"

#if VERSION_MAJOR == 4
#include "core/object/object.h"
#include "core/string/ustring.h"
#else
#include "core/object.h"
#include "core/ustring.h"
#endif

#ifdef __OBJC__
@class GodotWitcherQrScanner;
#else
typedef void GodotWitcherQrScanner;
#endif

class WitcherQrScanner : public Object {
	GDCLASS(WitcherQrScanner, Object);

	static void _bind_methods();

	GodotWitcherQrScanner *scanner;

public:
	static WitcherQrScanner *get_singleton();

	void start_scan_normalized(float p_x, float p_y, float p_width, float p_height);
	void stop_scan();
	void request_camera_permission();
	bool is_scanning() const;

	void on_qr_scanned(const String &p_text);
	void on_scanner_error(const String &p_message);
	void on_permission_changed(bool p_allowed);

	WitcherQrScanner();
	~WitcherQrScanner();
};

#endif
