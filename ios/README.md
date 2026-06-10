# Witcher LARP iOS Client

This is the native SwiftUI mobile client. It replaces the Godot mobile client as
the production mobile path while keeping `mobile/` in the repo as legacy and
reference material.

## Build Host

The app must be built and installed on a Mac with Xcode. This Windows/Codex
workspace can prepare and review source files, but it cannot sign or run the
iOS app on an iPhone.

Preferred setup on the Mac:

```bash
cd ios
xcodegen generate
open WitcherLARP.xcodeproj
```

If XcodeGen is not available, create a new iOS App project in Xcode and add the
files from `ios/WitcherLARP` and `ios/Resources`. Use SwiftUI lifecycle,
bundle id `local.witcherlarp.app` or the chosen team bundle id, and deployment
target iOS 16.0 or newer.

## First Smoke

1. Start the backend on the master laptop with `uv run python -m backend.witcher_larp`.
2. Connect the iPhone to the same local Wi-Fi.
3. Install from Xcode/free provisioning or TestFlight.
4. Allow local network and camera permissions.
5. Set the server URL if the hidden local setting is not prefilled.
6. Log in with a seed player code.
7. Download snapshot.
8. Scan a physical QR or enter manual QR ID.
9. Create one offline PvE event.
10. Restart the app and sync the pending event.

The current source is a project scaffold and vertical-slice shell, not a finished
player UI.
