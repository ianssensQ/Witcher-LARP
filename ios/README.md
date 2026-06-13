# Witcher LARP iOS Client

This is the native SwiftUI mobile client. It is the current production mobile
path for iPhone players. The old Godot mobile client remains in `mobile/` only
as legacy/reference material.

## Scope

Current player release scope is iOS with PvP Gwent enabled:

- player-code login;
- player-scoped snapshot download and restart-safe local persistence;
- QR/manual-code PvE with physical-presence confirmation;
- local event queue and later Wi-Fi sync;
- orders, inventory, bag, trade-transfer controls and server-synced act gating;
- player-facing PvP/Gwent and deck setup tabs with bot training, challenges,
  fullscreen table and deck review.

The iOS app uses the same local FastAPI/SQLite game server as the master and
lord browser panels:

```text
http://192.168.68.118:8002
```

If the master laptop IP changes, change only the host and keep port `8002`.

## Build Host

Build and install from a Mac with Xcode:

```bash
open ios/WitcherLARP.xcodeproj
```

Optional XcodeGen regeneration path:

```bash
cd ios
xcodegen generate
open WitcherLARP.xcodeproj
```

If XcodeGen is not available:

```bash
brew install xcodegen
```

Or create a new iOS App project in Xcode and add the files from
`ios/WitcherLARP` and `ios/Resources`. Use SwiftUI lifecycle, bundle id
`local.witcherlarp.app` or the chosen team bundle id, and deployment target
iOS 16.0 or newer.

## Release Boundary

The Release target is the player build. It includes `GwentTableView.swift`.
PvP/Gwent and deck setup are separate player pages. QR is opened from the
journal button, not from the bottom tab bar. Debug still keeps the local demo
launch arguments for screenshot/testing work.

Normal player tabs:

- `Журнал`;
- `PvP`;
- `Колода`;
- `Инвентарь`;
- `Заказы`.

## Xcode Screen Review

Fast path without a running backend:

1. Open `ios/WitcherLARP.xcodeproj`.
2. Select the `WitcherLARP` scheme.
3. Choose an iPhone simulator or a connected iPhone.
4. Press Run.
5. Open `Настройки` on the login screen only if the LAN address changed.
6. In Debug, use `Открыть демо экранов` for local screen review.
7. Review `Журнал`, `PvP`, `Колода`, `Инвентарь` and `Заказы`.
8. In `Журнал`, use `Сканировать QR`.
9. In the QR screen, scan or enter `QR-A1-K7Q2`, then apply the code.
10. In `Заказы`, use the QR path first, then submit an order when proof exists.
11. In journal settings, verify pending event count, server status and send button.

## Backend Smoke

Before handing out phones, run the no-PvP HTTP smoke against the same server the
iPhones will use:

```bash
scripts/ios_no_pvp_http_smoke.py --server http://192.168.68.118:8002
```

Default smoke is read-oriented: `/health`, `POST /api/auth/player-code`, and
player-scoped `GET /api/content/snapshot`. It verifies that the snapshot is
scoped to the player, contains QR/PvE content and does not leak
`player_codes` or `role_tokens`.

For rehearsal, after confirming that light runtime rows are acceptable, run the
full iOS contract smoke:

```bash
scripts/ios_no_pvp_http_smoke.py \
  --server http://192.168.68.118:8002 \
  --include-qr-lookup \
  --include-empty-sync \
  --json-report /private/tmp/ios-no-pvp-smoke-report.json
```

`--include-qr-lookup` writes a `qr_attempts` row. `--include-empty-sync` may
update client sync bookkeeping. Do not run those flags against the live game DB
unless that tiny mutation is expected.

## Build Checks

Useful local checks:

```bash
xcodebuild -quiet \
  -project ios/WitcherLARP.xcodeproj \
  -scheme WitcherLARP \
  -sdk iphonesimulator \
  -configuration Debug \
  -derivedDataPath /private/tmp/witcher-ios-debug-dd \
  CODE_SIGNING_ALLOWED=NO build

xcodebuild -quiet \
  -project ios/WitcherLARP.xcodeproj \
  -scheme WitcherLARP \
  -sdk iphonesimulator \
  -configuration Release \
  -derivedDataPath /private/tmp/witcher-ios-release-dd \
  CODE_SIGNING_ALLOWED=NO build

.venv/bin/python -m pytest tests/test_ios_project_scaffold.py -q
```

`uv` is the project-standard Python entrypoint when available. In Codex desktop
sessions where `uv` is absent from PATH, use the existing `.venv/bin/python`.

## Simulator Visual Smoke

After a Release simulator build, run the visual smoke against a booted iOS
Simulator. It installs the `.app`, seeds local player storage from the live
`8002` snapshot, launches the app and screenshots the real Home screen:

```bash
scripts/ios_no_pvp_sim_visual_smoke.py \
  --server http://192.168.68.118:8002 \
  --app /private/tmp/witcher-ios-release-dd/Build/Products/Release-iphonesimulator/WitcherLARP.app \
  --artifact-dir /private/tmp/ios-no-pvp-sim-visual-smoke
```

The smoke writes `release-home.png` and
`ios-no-pvp-sim-visual-smoke.json`. It catches blank launches and verifies that
the visible app body is not empty. It complements, but does not replace, the
real iPhone permission/QR/restart checks.

## Machine Release Gate

Run the combined no-PvP iOS machine gate before real-device sign-off:

```bash
scripts/ios_no_pvp_release_gate.py \
  --server http://192.168.68.118:8002 \
  --artifact-dir /private/tmp/ios-no-pvp-release-gate
```

The gate compiles the smoke script, runs `tests/test_ios_project_scaffold.py`,
builds Debug and Release for the iOS simulator and runs the read-oriented
no-PvP HTTP smoke against `8002`. It writes
`ios-no-pvp-release-gate.json` in the artifact directory. A machine-passed
report with `ready_for_players: false` means the remaining blocker is real
iPhone evidence, not a simulator/build/backend contract failure.

When a booted Simulator is available, add `--include-sim-visual-smoke` to the
gate to include the screenshot/nonblank Home check in the same report:

```bash
scripts/ios_no_pvp_release_gate.py \
  --server http://192.168.68.118:8002 \
  --include-sim-visual-smoke \
  --artifact-dir /private/tmp/ios-no-pvp-release-gate
```

When Xcode sees a connected iPhone, add an unsigned device-target build:

```bash
scripts/ios_no_pvp_release_gate.py \
  --server http://192.168.68.118:8002 \
  --device-id 00008110-000C75203AE1401E \
  --artifact-dir /private/tmp/ios-no-pvp-release-gate
```

To also verify local Apple Development signing and the provisioning profile:

```bash
scripts/ios_no_pvp_release_gate.py \
  --server http://192.168.68.118:8002 \
  --device-id 00008110-000C75203AE1401E \
  --signed-device-build \
  --artifact-dir /private/tmp/ios-no-pvp-release-gate
```

To install the signed app through the same gate, add the explicit install flag:

```bash
scripts/ios_no_pvp_release_gate.py \
  --server http://192.168.68.118:8002 \
  --device-id 00008110-000C75203AE1401E \
  --include-sim-visual-smoke \
  --signed-device-build \
  --install-signed-device-app \
  --artifact-dir /private/tmp/ios-no-pvp-release-gate
```

Installation changes the connected iPhone. After it succeeds, complete the
real-device smoke below on that phone and then re-run the gate with
`--real-device-evidence ... --require-real-device-evidence`.
When install is performed by this gate, `installed_release_build` is recorded as
machine-proven in the report; Local Network, Camera, login, restart, QR and sync
retry still require the real-device checklist.

To prepare the real-device checklist file:

```bash
scripts/ios_no_pvp_release_gate.py \
  --skip-builds \
  --skip-http \
  --write-real-device-template /private/tmp/ios-real-device-smoke.json
```

After filling that file from an actual iPhone run, use
`--real-device-evidence /private/tmp/ios-real-device-smoke.json
--require-real-device-evidence` for the final sign-off gate.

## First Real iPhone Smoke

1. Start the FastAPI server on the master laptop at `0.0.0.0:8002`.
2. Connect the iPhone to the same local Wi-Fi.
3. Install from Xcode/free provisioning, TestFlight or the install gate above.
4. Allow Local Network and Camera permissions.
5. Log in with a seed player code, for example `WC-WOLF-6GF4`.
6. Verify the journal survives app restart.
7. Scan a physical QR or enter manual QR ID.
8. Apply the QR/manual object code and create one offline PvE event.
9. Restart the app and verify the pending event remains visible in journal settings.
10. Restore Wi-Fi/server access and send pending events.
11. Refresh the journal and verify the result/order state is readable.

## Remaining Release Evidence

The app is not fully signed off until the real-device smoke above passes on the
actual game Wi-Fi and the actual `8002` server. Simulator builds, device builds,
signed install and read-only HTTP smoke are necessary evidence, but they do not
replace camera, Local Network permission, restart persistence and sync retry on
a real iPhone.
