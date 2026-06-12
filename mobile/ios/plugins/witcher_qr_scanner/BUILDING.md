# WitcherQrScanner iOS plugin

This plugin is the native iPhone QR decoder for the M2 order screen. It uses
AVFoundation on-device and does not call the backend while scanning. Godot then
passes the decoded text to `AppState.check_qr_order_gate(...)`, which checks the
last server-scoped snapshot saved on the phone.

The repository stores the source and `.gdip` descriptor. The
`witcher_qr_scanner.xcframework` binary must be built on macOS with Xcode before
an iPhone export can include the plugin.

## Build on macOS

1. Clone the official Godot iOS plugin build repo:

   ```bash
   git clone https://github.com/godot-sdk-integrations/godot-ios-plugins.git
   ```

2. Copy this directory into the cloned repo:

   ```bash
   cp -R mobile/ios/plugins/witcher_qr_scanner godot-ios-plugins/plugins/
   ```

3. Add `witcher_qr_scanner` to the `plugin` enum in the cloned repo
   `SConstruct`, next to `photo_picker`.

4. Provide Godot 4 headers in the cloned repo as described in that repo README.

5. Build the device/simulator xcframework:

   ```bash
   cd godot-ios-plugins
   ./scripts/generate_xcframework.sh witcher_qr_scanner release_debug 4.0
   ```

6. Copy the built framework next to this `.gdip` file:

   ```bash
   cp -R bin/witcher_qr_scanner.xcframework \
     /path/to/New\ project\ 2/mobile/ios/plugins/witcher_qr_scanner/
   ```

7. Export the `iOS Free Provisioning` preset from Godot on macOS, open the
   exported project in Xcode and run it on the target iPhone. The screen should
   ask for camera permission, show the camera in the upper scan area and emit
   `qr_scanned` when a QR is recognized.
