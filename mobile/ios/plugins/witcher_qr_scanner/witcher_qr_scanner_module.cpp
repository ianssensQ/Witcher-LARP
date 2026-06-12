#include "witcher_qr_scanner_module.h"

#include "core/version.h"

#if VERSION_MAJOR == 4
#include "core/config/engine.h"
#else
#include "core/engine.h"
#endif

#include "witcher_qr_scanner.h"

static WitcherQrScanner *witcher_qr_scanner = nullptr;

void register_witcher_qr_scanner_types() {
	witcher_qr_scanner = memnew(WitcherQrScanner);
	Engine::get_singleton()->add_singleton(Engine::Singleton("WitcherQrScanner", witcher_qr_scanner));
}

void unregister_witcher_qr_scanner_types() {
	if (witcher_qr_scanner) {
		memdelete(witcher_qr_scanner);
		witcher_qr_scanner = nullptr;
	}
}
