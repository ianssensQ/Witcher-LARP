# Witcher LARP Mobile

Godot 4 mobile shell for `TASK-007`. The project lives entirely under
`mobile/` and is safe to open directly from the Godot project manager.

## Runtime contract

- Main scene: `res://scenes/main.tscn`.
- Persistence: `user://settings.json`, `user://session.json` and
  `user://snapshot.json`.
- Login API: `POST /api/auth/player-code` with `player_code` and `device_id`.
- Snapshot API: `GET /api/content/snapshot`.
- Offline fallback: `res://assets/bundled_snapshot.json` is a public,
  non-playable dev fixture with production profile metadata only. It does not
  contain `player_codes`, `role_tokens` or scoped player rows; playable offline
  smoke requires a server-scoped snapshot saved to `user://snapshot.json`.
- QR/manual runtime: local lookup in snapshot `qr_objects`, persisted
  `user://qr_attempts.json` attempt log and `user://qr_event_context.json`
  context for later event_queue sync. A prepared scene records `qr_mode`,
  `consumption_rule`, physical-presence confirmation and review reasons such as
  `honesty_violation_suspected` or `manual_rate_limit`.
- Event queue runtime: QR presence confirmations, QR/manual review contexts and
  offline PvE results are appended to `user://event_queue.json` with `event_id`,
  `device_id`, `player_id`, `client_sequence`, `created_at`, `event_type`,
  `payload` and `local_status`. `user://sync_status.json` keeps visible
  `offline`, `pending`, `synced`, `sync_error` and `needs_master_review` counts.
  Sync sends the batch to `POST /api/events/sync` and keeps rejected/review
  records on device.

The first screen accepts a raw server URL such as `http://192.168.1.9:8000` or
a future QR payload in the form:

```text
witcher-larp://connect?server=http%3A%2F%2F192.168.1.9%3A8000
```

Invalid server responses keep existing local data. Unreachable auth or snapshot
endpoints do not create a playable login from the bundled artifact; use the last
saved server-scoped snapshot or reconnect to the local FastAPI server.

## Desktop smoke

1. Install Godot 4.x.
2. Open `mobile/project.godot`.
3. Run the main scene.
4. Save the LAN server URL, enter `WC-WOLF-6GF4` and press `Login + Snapshot`.
5. Quit and run again; the character and `snapshot_version` from the
   server-scoped `user://snapshot.json` should remain available without
   network.

Pressing `Bundled Snapshot` with a player code should report that the bundled
artifact has no player codes. That is intentional: this public fixture is useful
only for non-playable metadata inspection and must not be counted as Stage 1
playable offline proof.

## QR/manual smoke

1. Load a server-scoped snapshot with `WC-WOLF-6GF4`.
2. Enter `QR-A1-K7Q2` as `Manual ID`.
3. Confirm physical presence; the context should become `qr_scene_started` with
   `repeatable_scene`.
4. Enter a future-act code such as `QR-A2-B4K8`; it should stay blocked until
   sync or master unlock.
5. Enter several wrong manual IDs; the fifth bad attempt should move to
   `needs_master_review` with `manual_rate_limit`.

The current shell accepts QR payload text such as
`witcher-larp://qr?code=QR-A1-K7Q2` from a scanner/plugin/browser bridge and
keeps manual opaque ID as the guaranteed fallback. Predictable `qr_id` values
are not valid lookup secrets. Native camera decoding still needs a
target-device plugin smoke before release.

## Event queue smoke

1. Load a server-scoped snapshot with `WC-WOLF-6GF4`.
2. Enter `QR-A1-K7Q2`, press `Manual ID`, then `Confirm Physical Presence`.
3. Press `Roll PvE d20`; the app generates one immutable d20 roll and the Event
   Queue block should show one offline `pve_completed` event.
4. Quit and run again; the queued event should still be visible from
   `user://event_queue.json`.
5. With the FastAPI server reachable and imported seed data available, press
   `Sync Queue`; accepted or duplicate server responses become `synced`.
6. Stop the server or use a bad URL and press `Sync Queue`; the event becomes
   `sync_error` and remains retryable.

## Android export smoke

Preset: `Android Debug APK`

Expected path:

```text
mobile/builds/android/witcher_larp_mobile_debug.apk
```

Assumptions:

- Godot Android export templates are installed.
- Android SDK and `adb` are configured in the Godot editor.
- The phone is on the same venue Wi-Fi as the FastAPI server.
- Android `INTERNET` and network-state permissions are enabled by the preset.
- Camera permission is off in this shell; QR camera smoke belongs to the later
  QR task unless a scanner plugin is added.

Smoke:

1. Export the preset.
2. Install with `adb install -r builds/android/witcher_larp_mobile_debug.apk`.
3. Launch, save the LAN server URL, check `/health`, log in with a seed
   `player_code`, download or load fallback snapshot, restart the app.

If export/install cannot be completed, mark launch-risk owner as the tech
operator/master and fall back to Android-only, browser/manual QR flow or paper
recovery for game-day.

## iOS export smoke

Preset: `iOS Free Provisioning`

Expected path:

```text
mobile/builds/ios/witcher_larp_mobile_ios.zip
```

Assumptions:

- A Mac with Xcode is available.
- Free provisioning or TestFlight path is available for the target iPhone.
- iOS local network permission is expected on first LAN connection attempt.
- Camera permission is documented for future QR scanner smoke only.

Smoke:

1. Export the iOS preset from Godot on macOS.
2. Open the exported project in Xcode or follow the TestFlight path.
3. Launch on device, allow local network access, check `/health`, log in with a
   seed `player_code`, download or load fallback snapshot, restart the app.

If no Mac/Xcode path exists, keep iOS as explicit launch-risk with owner
tech operator/master and use Android, browser/manual QR flow or paper recovery.
