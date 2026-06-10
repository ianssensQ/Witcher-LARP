# Stage 2B flow map

Этот документ фиксирует release-critical маршруты как цепочки:
`нажал -> клиент отправил или поставил в очередь -> сервер/snapshot решил ->
экран изменился`.

## Flow record rule

Каждый UI flow обязан иметь:

- actor and starting state;
- UI trigger/control;
- client behavior, including offline queue if relevant;
- backend endpoint/service or snapshot source;
- payload/idempotency key;
- response or review decision;
- resulting visible state;
- fallback/recovery path;
- acceptance smoke step.

Для первой мобильной реализации ведьмаки и чародейки используют общий
`Mobile Adventurer V0` маршрут из
`docs/ui/mobile-witcher-sorceress-shared-flow-v0.1.md`. Все `W*` flows ниже
относятся к обеим ролям; отдельные `Sorc*` flows являются future layer и не
блокируют первый Godot mobile gameplay UI.

## Shared auth and sync

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Auto-connect bootstrap | mobile player | app launch | none; background startup | Try built-in game-day URL, saved setup URL and last good server URL; show only compact connection/offline badge on login | `GET /health`, local settings | none | ok, unreachable, no snapshot | ok -> `Shared2`; unreachable with snapshot -> `Shared2` offline badge; no snapshot -> help state | Player never manually enters server URL in normal flow |
| Diagnostic connection setup | master/tech | hidden `Ops0` | Open diagnostic/settings route or scan setup QR | Normalize URL, save locally only after master/tech action | `GET /health`, local settings | connection QR or URL | ok or unreachable | success returns to `Shared2`; unreachable stays in diagnostic retry | Last mobile snapshot remains usable but stale/offline |
| Player login | witcher/sorceress | `Shared2` | Submit `player_code` | Generate/load device id; request auth; on success request snapshot | `POST /api/auth/player-code`, `GET /api/content/snapshot` | `{player_code, device_id}` then query `player_code` | auth ok + snapshot or 401/404 | ok -> `W1`; invalid code stays `Shared2`; snapshot fail keeps old data | Test wrong code and valid seed code; first player action is code entry |
| Role-token login | lord/master | `Shared2` | Submit `role_token` | Store token in browser session | `POST /api/auth/role-token` | `{token}` | role_type `lord`/`npc_master` or 401 | lord -> `L1 Castle / Territory Home` at `/lords/home`; master -> `A1`; invalid stays `Shared2` | Test lord token cannot open another lord |
| Mobile sync | player | queued local events | Press Sync Queue | Select retryable events; mark pending; send batch | `POST /api/events/sync` | `actor_id` is server-authenticated; events include `event_id`, `client_sequence`, payload | accepted, duplicate, rejected, needs_master_review, pending_master_approval | queue counters update; review/locked remain visible | Network error marks `sync_error`, never deletes events |

## Shared witcher/sorceress mobile flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QR/manual lookup | witcher/sorceress | `W2` with current snapshot | Scan QR text or submit manual ID | Normalize opaque code; look up local snapshot; optionally call runtime lookup when online | snapshot `qr_objects`; optional `POST /api/qr/lookup` | `{code, player_id, device_id, source, physical_presence_confirmed}` if online | valid, unknown, future act locked, cooldown, review | valid -> `W3`; invalid stays `W2`; future act opens `W11` or shows locked reason | Manual ID fallback required even if camera works |
| Physical presence | witcher/sorceress | valid QR context | Confirm Physical Presence | Persist context and queue start/review event where required | local `user://qr_event_context.json`; later `/api/events/sync` | `qr_scene_started` or `qr_attempt` event with physical presence flag | server accepts or sends review after sync | `W4` if valid; `W3` review state if flagged | Honesty violation creates review, not silent success |
| Offline PvE result | witcher/sorceress | `W4` scene started | Roll PvE d20 | Generate one immutable d20; compute modifiers from snapshot; enqueue result | snapshot `pve_scenarios`, `mobs`, `rewards`; later `/api/events/sync` | `pve_completed` with roll log, qr_id, scenario_id, reward_status | accepted, duplicate, rejected, pending approval, review | `W5` success/failure/cooldown/locked; sync badge updates later | No editable d20; one roll per scene context |
| Offline act unlock | witcher/sorceress | `W11` after future-act lock or act announcement | Enter master unlock code or scan unlock QR | Store local unlock proof and keep future content hidden until validation allows it | snapshot `act_unlock_codes`; later `/api/events/sync` | `act_unlocked_offline` with act id, code proof, player/device/source | accepted, invalid, rejected on sync | unlocked act returns to `W1`; invalid stays `W11`; rejected re-locks future content | Code is usable only after physical act announcement |
| Gear equip/use | witcher/sorceress | `W6A` | Equip/unequip gear or inspect weapon/protection | Validate owned gear, locks and stat requirements from visible state | player inventory/equipment read model blocker | `{asset_id, slot, source}` | applied or validation error | gear state updates; invalid stays `W6A` | Missing player gear read model blocks final UI |
| Bag item use | witcher/sorceress | `W6B` | Use item/potion or inspect artifact/locked reward | Validate owned item and scene context from visible state | player inventory read model blocker; item/potion endpoint where needed | `{asset_id, scene_id, source}` | applied or validation error | bag count/effect updates; invalid stays `W6B` | Missing player bag read model blocks final UI |
| Deck edit | witcher/sorceress | `W6C` from `W10` or quick tab | Add/remove card or auto-build | Validate owned cards, leader and deck constraints before PvP | Gwent card/deck read model blocker | `{deck_id, card_ids, leader_card_id, source}` | saved, invalid deck or validation error | deck validity badge updates; invalid stays `W6C` | PvP preflight must use the same deck validity |
| Order accept/submit | witcher/sorceress | `W7` order board | Accept or submit order | Use player auth, keep object conflict state visible | player order board read model blocker; `POST /api/lords/{lord_id}/orders` | `{action, order_id, player_id/result_event_id, source}` | accepted/submitted/contested_review/error | order state changes or review badge | No Swagger order acceptance |
| Trade transfer | witcher/sorceress | `W8` | Create/accept/decline trade | Lock asset on create; target confirms online | trade read model blocker; `/api/trade-transfers*` | transfer id, from/to, asset, quantity, price, mode | pending_locked, accepted, declined, contested_review | pending lock visible to both participants | No offline trade transfer |
| Personal goals | witcher/sorceress | `W9` | Open goals | Render only known goals/tracks | snapshot `personal_goals`, `goal_tracks` | none | no mutation | hidden flags absent; stale snapshot label if offline | Master-only flags never shown |

## Sorceress mobile flows

These flows are intentionally deferred from the first mobile implementation.
When the magic module is enabled, restore `Sorc1-Sorc7` from product backlog and
bind them to sorceress state endpoints. Until then, sorceresses pass the
`Shared witcher/sorceress mobile flows` above.

## Lord desktop flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Load castle home | lord | valid token from `/lords/login` | Open `/lords/home` or refresh | Fetch scoped state and select residence or requested owned `territory_id` | `GET /api/lords/{lord_id}/state` | role token header, optional local `territory_id` route/query | state or 401/403/404 | full-screen castle/territory background, top resources, left action icons, bottom-left minimap, bottom-center army/garrison/recruit lanes, bottom-right act timer and MP arc | Wrong lord token cannot view state; stale state marked, not silently trusted |
| Switch owned territory | lord | `L1` with right-side territory bubbles | Click territory circle | Change selected `territory_id`, reuse same home UI with local territory bindings | `GET /api/lords/{lord_id}/state` | no mutation | selected owned territory or unavailable | background, income, garrison, recruit stock and local building tree update; active army lane locks if hero is elsewhere | No remote ownership mutation from switching view |
| Open tutorial replay | lord | `L1` or `/lords/login` | Click `?` or `Обучение` | Load mock lord state and highlight controls | static mock fixture plus optional current state labels | none | tutorial route/view | all main buttons are explained through mock states without API mutation | Onboarding content can be expanded after lord e2e flow exists |
| Move and claim | lord | `L2` opened from left map icon or bottom-left minimap; no active `pending_move` | Pan map, click territory/army marker, press Move after route preview | Use `lord_map_layout` hit-zones for click, reject excluded zones/foreign raid-only residences locally, request/render cheapest route on the full visible graph, submit full route, then keep map read-only while horse animation follows saved polyline | lord state graph/intel/layout; `POST /api/lords/{lord_id}/move`; next `GET /api/lords/{lord_id}/state` returns `pending_move` or arrival result | `{to_node_id, route_node_ids, expected_cost, source}`; server records route, MP cost, start time, arrival time | pending_move, moved to owned node/route waypoint, contested claim/prebattle, invalid route, no MP, forbidden target, blocked by enemy/contested stop | horse marker animates quickly; MP arc updates after server accept; pending banner disables new move/battle actions; arrival on neutral/enemy shows battle banner/prebattle; hidden enemy details remain redacted unless intel allows; errors stay on map | Close tab/network drop does not lose the move: server auto-completes arrival by saved arrival time; route must use weighted path, stop at first enemy/contested territory, and never rely only on target node |
| Army/garrison transfer | lord | `L1` bottom lanes | Drag/drop unit between active army and garrison or reserve; confirm count | Lock top active-army row when selected territory is not hero location; submit count only when allowed | lord state active army location, garrisons/reserve; `POST /api/lords/{lord_id}/garrisons/transfer` | `{territory_id, card_id, count, operation, source}` | transferred or capacity/minimum/battle/location lock error | active army and garrison lanes update; locked top lane remains empty on non-local territory | Enemy garrisons redacted; no optimistic unit move |
| Buy/upgrade building | lord | `L1/L6` selected castle or territory | Click building icon/tree node, press Buy/Upgrade | Show prereq/cost/effect hints; submit building id scoped to selected location | lord state building catalog; `POST /api/lords/{lord_id}/buildings` | `{building_id, territory_id, source}` | purchased, insufficient gold, missing prereq, duplicate | local tree node becomes purchased, recruit slot or income effect updates | Residence tree is full; territory tree can start minimal |
| Recruit accumulated unit | lord | `L1` recruit strip | Click unit icon, adjust slider, press Hire | Render unit art/stats/cost and max quantity from accumulated stock; purchase goes to selected territory garrison | lord state recruit stock; `POST /api/lords/{lord_id}/recruit` | `{action:purchase_stock, territory_id, card_id, quantity, source}` | purchased, locked slot, insufficient stock/gold, unavailable | garrison count and accumulated stock update; empty locked slots remain visible | This replaces offer-list UX on the castle/territory home even if backend keeps offer compatibility |
| Raid | lord | `L1` left raid icon opens `L8` command-table screen with top HUD, left dock and bottom lord status bar | Choose raid rule node, choose target in detail panel, Start raid | Validate locked building, token/gold, target visibility and duplicate active effect before submit; keep stale/offline read-only | lord state `raid_tokens`, `raid_rules[]`, `raid_targets[]`, `active_raid_effects[]`, `raid_history[]`; `POST /api/lords/{lord_id}/raids` | `{target_territory_id, rule_id, expected_token_cost, expected_gold_cost, source}` | started/resisted/loot_applied/needs_master_review or validation error | token/gold spend visible, active effect and expiry appear in L8 and bottom HUD, history records latest outcome | Raid never starts 5x6 battle and never captures territory |
| Order creation | lord | `L1` notice-board icon | Create order | Validate cap hints; server holds escrow | lord state orders; `POST /api/lords/{lord_id}/orders` | `{action:create, object_id, target_player_id, visibility, escrow_reward_id, source}` | created, active cap error, escrow conflict | order appears or error/review | Player actions on same endpoint require player auth |
| Lord battle | lord | `L1` red battle icon only when active/attacked | Open battle or record action | Fetch battle, render legal state, submit action | `GET/POST /api/lord-battles*` | battle create/action payload with actor scope | action accepted, timeout, auto-resolve, finished, review | board, turn, timer, HP/losses update; battle icon returns inactive after finish | 5x6 board visually distinct from personal Gwent |
| Paper continuation | lord/master | outage | Read printed/onscreen notice | Continue on paper only while app/network unavailable | last known state, printed fallback | later `paper_lord_action` or `paper_lord_battle` via Admin | paper recovered, duplicate, conflict review | not a normal UI acceptance path | Must be rehearsed as outage recovery |

## Master / NPC-master flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Start act and reveal code | master | `A2` | Start act, record physical announcement, reveal code | Enforce sequence in UI and server | `GET /api/master/acts/state`; act endpoints | `{operator, source, physical_announcement_state}` | act started, code hidden, code revealed | timer/code state updates | Code is hidden until physical announcement |
| Review event | master | `A3` | Approve/reject/correct | Submit decision with reason/operator | `GET /api/master/review-queue`; `POST /api/events/{id}/review` | `{action, operator, reason, severity, correction, source}` | accepted, rejected, corrected, conflict | queue count and event row update | P0/P1 remain visible until resolved |
| Reward approval | master | `A4` | Approve/reject/correct reward | Submit decision | `GET /api/master/state`; `POST /api/master/reward-approvals/{id}` | `{action, operator, reason, correction, source}` | approved/rejected/corrected | locked reward state changes | Locked rewards cannot be spent before approval |
| Paper recovery | master | `A5` | Choose paper form, submit | Build `source=paper_recovered` event batch | `POST /api/events/sync` | event includes `paper_form_id`, source form type, operator, timestamp, reason | applied, duplicate, needs_master_review, rejected | recovery result and review row visible | No silent overwrite of digital state |
| Lord ops correction | master | `A6` | Apply correction | Require reason/operator | `GET /api/master/state`; `POST /api/master/game-ops/corrections` | `{target_type, target_id, patch, operator, reason, source}` | correction stored or validation error | corrected state and audit row | Developer-only direct DB edit not allowed |
| PvP throttle/review | master | `A7` | Set throttle or review refusal/timeout | Submit mode/decision | `GET /api/pvp/tables`; `POST /api/master/pvp-throttle` | `{mode, operator, source}` | normal/limited/paused | table queue state updates | Final lock prevents new challenges |
| NPC event/deal | NPC-master | `A8` | Record King/Wanderer event | Submit event and visibility/severity | `/api/master/npc/events`, `/api/master/npc/deals` | NPC event payload | event recorded, resolved, review route | public/hidden state follows visibility | Hidden prices master-only |
| Reputation/visibility audit | master | `A9` | Inspect/change reputation | Read exact values; submit delta if needed | `/api/master/reputation/{id}`, `/api/master/visibility-audit` | `{delta, reason, visibility, source}` | changed or validation error | exact master-only log updates | Player only sees descriptive reputation |
| Backup | master | `A10` | Run backup | Submit backup trigger | `/api/master/backups/status`, `/api/backups/run` | `{trigger_type, operator, source}` | success/error | backup status updates | Restore rehearsal remains TASK-036 residual-risk path |
| Final summary | master | `A11` | Load final, add note, export | Fetch evidence, record note | `GET /api/master/final-summary`, `POST /api/master/final-summary/notes` | note payload | summary loaded, note recorded | evidence/missing locks visible | App does not auto-declare winners |

## No-Swagger acceptance scripts

- Witcher: app launch auto-connect -> code login -> snapshot -> QR/manual ->
  physical confirmation -> PvE d20
  -> result/cooldown/locked reward -> restart/offline -> sync.
- Sorceress V0: app launch auto-connect -> code login -> same shared mobile
  route as witcher -> QR/manual PvE -> gear/bag/deck -> orders/trade/
  reputation/sync -> Gwent entry. Magic/potion market/favorites/alignment are
  future-layer scripts, not Stage 2B V0 blockers.
- Lord: token login -> castle home -> switch territory -> recruit accumulated
  unit -> army/garrison transfer -> building -> order -> raid -> open map ->
  pan/click visible territory -> route preview -> horse pending move ->
  arrival/contested claim -> battle -> return to castle/territory home.
- Personal Gwent: challenge -> table/queue -> start -> rounds/pass -> finish or
  refusal/review.
- Admin/NPC: act start/announcement/code -> review -> reward approval -> paper
  recovery -> NPC event -> visibility audit -> final summary.

Any script step that still requires Swagger, curl or direct SQLite is a blocker
for Stage 2B UI acceptance.
