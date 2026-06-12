# Stage 2B device evidence

This file is the persistent evidence target for later `TASK-058` and `TASK-050`
smoke proof. `TASK-067` creates the contract and prototype; real-device proof is
recorded after implementation.

## Visual acceptance screenshots

Primary visual reference:

- Figma: `https://www.figma.com/design/7BNdyJtd7QSH52QzXjT0Ol`

Expected screenshot files:

- `reports/stage2b/screenshots/shared-auth-sync.png`
- `reports/stage2b/screenshots/lord-map-command-table.png`
- `reports/stage2b/screenshots/lord-building-tree.png`
- `reports/stage2b/screenshots/lord-territory-inspector.png`
- `reports/stage2b/screenshots/lord-battle-board.png`
- `reports/stage2b/screenshots/witcher-mobile-flow.png`
- `reports/stage2b/screenshots/sorceress-mobile-flow.png`
- `reports/stage2b/screenshots/personal-gwent-mobile.png`
- `reports/stage2b/screenshots/admin-recovery-final.png`

## Later device/browser proof

| Surface | Required proof | Status |
| --- | --- | --- |
| Android phone | APK launch, local server, snapshot, QR camera/manual fallback, restart persistence, sync retry | pending implementation |
| iPhone | free provisioning/TestFlight path, local network permission, snapshot, QR/manual fallback, restart persistence, sync retry | pending implementation |
| 4 lord laptops | simultaneous panels, scoped tokens, map/action/battle smoke | pending implementation |
| Master laptop | Admin review, paper recovery, final summary, backup status | pending implementation |
| Paper fallback | lord action or lord battle outage recovery drill | pending implementation |
