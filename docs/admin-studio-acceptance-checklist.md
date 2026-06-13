# Admin Studio acceptance checklist (TASK-023)

Дата проверки: 2026-06-03.

Статус: Stage 2 local/browser acceptance passed. Проверка с отдельного
ноутбука в реальной Wi-Fi сети остается повторяемым ручным шагом перед
venue/rehearsal smoke; она не заменяется Swagger, curl или правкой SQLite.

## Граница Stage 2

Stage 2 принимает браузерную Admin Studio как мастерскую панель поверх
существующего FastAPI/SQLite runtime. В этот gate входят:

- master role-token login and master-only data visibility;
- content import/validation, snapshot export, QR/manual and handout checklists;
- act controls, timers, review queue, reward approvals, PvP throttle and audited
  game-ops corrections;
- lord map overview and master corrections for territories, garrisons,
  buildings, recruit offers, reserve, pending rewards, anti-snowball, raid
  effects/loot and PvP timeout/review cases;
- King/Wanderer NPC tools, hidden prices, exact master reputation view and
  visibility audit;
- backup status/manual backup and final summary open/export flow.

Stage 2 does not accept generated PvE authoring, full player/lord gameplay UI,
real Android/iOS device smoke or balance/rehearsal readiness. Those stay in
TASK-028, TASK-050 and Stage 5.

## Evidence Recorded In Codex

| Check | Result |
| --- | --- |
| API/static contract | `uv run pytest tests/test_admin_studio_contract.py` passed: 6 tests. |
| Browser smoke | In-app browser opened `http://127.0.0.1:8794/admin`, logged in with master role token and rendered 6 sections. |
| Snapshot in UI | Browser dashboard showed `STAGE-2: Admin Studio`, snapshot `seed-v1-1c2108930fcf`, 6 sections and 0 attention items. |
| UI controls | Browser smoke verified import, snapshot export, QR/manual checklist, handout checklist, act controls, lord map ops, visibility audit, corrections, PvP throttle, review queue, King event, Wanderer hidden price, exact reputation, backup run and final summary controls. |
| Restart persistence | Test server restarted on the same SQLite DB; `/health` returned `ok`, snapshot stayed `seed-v1-1c2108930fcf`, PvP throttle stayed `limited`. |
| Screenshot artifact | Local evidence screenshot: `.test-data/admin-gate-browser-smoke.png`. |

## TASK-078 Remediation Evidence

- Admin Studio exposes typed `Paper recovery intake` controls for every seeded
  `paper_forms.csv` form type: `paper_pve_result`, `paper_pvp_stake`,
  `paper_lord_action`, `paper_lord_battle`, `paper_order_resolution`,
  `paper_npc_deal` and `paper_final_evidence`.
- Game Ops visibly renders recent event log, client sync status and
  anti-snowball state from `/api/master/state`.
- Potion/trade recovery is covered by typed Admin forms for potion market stock,
  trade transfer status/price/quantity and player economy corrections; the old
  JSON correction remains a diagnostics fallback, not the primary master flow.
- Real second-laptop/local-Wi-Fi smoke is still required evidence for
  `TASK-058`/`TASK-050`; localhost or in-app browser checks do not satisfy that
  release gate. The manual LAN script below is the required capture path.

## Acceptance Checklist

| Area | Pass condition | Evidence/status |
| --- | --- | --- |
| Login/access | Master can enter Admin Studio with `npc_master` role token; missing/invalid/lord tokens are rejected. | Covered by contract tests and browser smoke. |
| Content import/validation | Master can choose a content pack, run validation/import, inspect structured errors and export latest snapshot. | Covered by contract tests and browser smoke. |
| QR/manual checklist | Master sees printable/manual QR data, QR honesty policy and single-d20/no-reroll readiness. | Covered by contract tests and browser smoke. |
| Handouts | Master sees common, witcher, sorceress, lord and master handout readiness. | Covered by contract tests and browser smoke. |
| Acts/timers | Master can inspect current act/timers, start acts, record physical announcement and reveal unlock code only after announcement. | Covered by contract tests and browser smoke. |
| Review/reward queue | Master can inspect review queues and approve/reject/correct events and pending rewards with audit reason. | Covered by contract tests. |
| Paper recovery | Master can submit every supported paper form from typed Admin Studio fields with operator, reason, timestamp and conflict status. | Covered by TASK-078 contract tests; LAN smoke still required before TASK-050. |
| Event/sync ops | Master sees recent event log, client sync status and anti-snowball state in Game Ops. | Covered by TASK-078 service/API/UI contract tests. |
| Lord map ops | Master can inspect lord domains/territories and use audited corrections for territory/garrison/building/recruit/reserve/raid/PvP timeout cases. | Covered by contract tests and browser smoke. |
| Potion/trade corrections | Master can correct potion market, trade transfer and player economy state with operator/reason audit. | Covered by TASK-078 service/API/UI contract tests. |
| Visibility | Master exact view includes hidden garrisons, raid effects, artifact visibility and exact reputation; lord/player views stay redacted. | Covered by contract tests and browser smoke. |
| NPC tools | King rulings and Wanderer hidden-price deals can be recorded with severity/final routing. | Covered by contract tests and browser smoke. |
| Backups | Master can inspect backup status and trigger manual backup from Admin Studio/API surface. | Covered by contract tests and browser smoke. |
| Restart | Server restart preserves authoritative SQLite state needed by Admin Studio. | Covered by restart persistence check in Codex. |
| Final summary | Master can open/export final summary and add final notes. | Covered by contract tests and browser smoke. |
| Second laptop Wi-Fi smoke | Start server with `WITCHER_LARP_HOST=0.0.0.0`, open `http://<LAN-IP>:<PORT>/admin` from another laptop on the same Wi-Fi, log in with master token and confirm dashboard/sections render. | Manual venue/LAN checklist step; repeat before rehearsal/game-day because Codex cannot provide a physical second laptop. |

## Manual LAN Smoke Script

1. On the master laptop, import seed or confirm current game DB is ready.
2. Start the production server for LAN access:

   ```powershell
   $env:WITCHER_LARP_HOST = "0.0.0.0"
   $env:WITCHER_LARP_PORT = "8002"
   uv run python -m backend.witcher_larp
   ```

3. Find the master laptop LAN IP on the Wi-Fi network. Current smoke IP is
   `192.168.68.118`; if it changes, replace only the host and keep port `8002`.
4. From another laptop on the same Wi-Fi, open Admin Studio:
   `http://<LAN-IP>:8002/admin`.
5. Log in with a master role token.
6. From a lord laptop/browser, open the current lord game entry:
   `http://<LAN-IP>:8002/lords/login`.
7. Log in with a lord player code from Admin Studio, for example
   `LC-NORTH-7QK2`, and confirm the lord panel loads from the same server.
8. Confirm the dashboard shows Stage 2, current snapshot, all 6 sections and no
   unexpected blocking alert.
9. Click Content, Game Ops, Events, NPC, Backups and Final; confirm the controls
   named in the checklist render without requiring Swagger/manual API.
10. Do not use dev/Vite ports such as `5174` or `5178` for this smoke. The
   production server is the single `8002` FastAPI process that serves Admin
   Studio, lord screens and `/api`.
11. If the page does not load, triage as network/firewall/router setup first:
   local `/health`, host binding, Windows firewall, both devices on the same
   subnet, then retry.
