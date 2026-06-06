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

## Shared auth and sync

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Connection check | any | no server or changed LAN IP | Press health/check connection | Normalize URL, save locally only after user action | `GET /health` | none | ok or unreachable | success returns to login; unreachable stays on `Shared1` with retry | Last mobile snapshot remains usable but stale/offline |
| Player login | witcher/sorceress | `Shared2` | Submit `player_code` | Generate/load device id; request auth; on success request snapshot | `POST /api/auth/player-code`, `GET /api/content/snapshot` | `{player_code, device_id}` then query `player_code` | auth ok + snapshot or 401/404 | ok -> `W1`/`Sorc1`; invalid code stays `Shared2`; snapshot fail keeps old data | Test wrong code and valid seed code |
| Role-token login | lord/master | `Shared2` | Submit `role_token` | Store token in browser session | `POST /api/auth/role-token` | `{token}` | role_type `lord`/`npc_master` or 401 | lord -> `L1 Castle / Territory Home` at `/lords/home`; master -> `A1`; invalid stays `Shared2` | Test lord token cannot open another lord |
| Mobile sync | player | queued local events | Press Sync Queue | Select retryable events; mark pending; send batch | `POST /api/events/sync` | `actor_id` is server-authenticated; events include `event_id`, `client_sequence`, payload | accepted, duplicate, rejected, needs_master_review, pending_master_approval | queue counters update; review/locked remain visible | Network error marks `sync_error`, never deletes events |

## Witcher mobile flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QR/manual lookup | witcher | `W2` with current snapshot | Scan QR text or submit manual ID | Normalize opaque code; look up local snapshot; optionally call runtime lookup when online | snapshot `qr_objects`; optional `POST /api/qr/lookup` | `{code, player_id, device_id, source, physical_presence_confirmed}` if online | valid, unknown, future act locked, cooldown, review | valid -> `W3`; invalid stays `W2`; future act/cooldown show locked reason | Manual ID fallback required even if camera works |
| Physical presence | witcher | valid QR context | Confirm Physical Presence | Persist context and queue start/review event where required | local `user://qr_event_context.json`; later `/api/events/sync` | `qr_scene_started` or `qr_attempt` event with physical presence flag | server accepts or sends review after sync | `W4` if valid; `W3` review state if flagged | Honesty violation creates review, not silent success |
| Offline PvE result | witcher | `W4` scene started | Roll PvE d20 | Generate one immutable d20; compute modifiers from snapshot; enqueue result | snapshot `pve_scenarios`, `mobs`, `rewards`; later `/api/events/sync` | `pve_completed` with roll log, qr_id, scenario_id, reward_status | accepted, duplicate, rejected, pending approval, review | `W5` success/failure/cooldown/locked; sync badge updates later | No editable d20; one roll per scene context |
| Inventory/potion use | witcher | `W6` | Use potion | Validate owned potion and scene context from visible state | player inventory read model blocker; `POST /api/players/{player_id}/potions/use` | `{potion_id, scene_id, source}` | applied or validation error | inventory count/effect updates; invalid stays `W6` | Missing player inventory read model blocks final UI |
| Order accept/submit | witcher | `W7` order board | Accept or submit order | Use player auth, keep object conflict state visible | player order board read model blocker; `POST /api/lords/{lord_id}/orders` | `{action, order_id, player_id/result_event_id, source}` | accepted/submitted/contested_review/error | order state changes or review badge | No Swagger order acceptance |
| Trade transfer | witcher | `W8` | Create/accept/decline trade | Lock asset on create; target confirms online | trade read model blocker; `/api/trade-transfers*` | transfer id, from/to, asset, quantity, price, mode | pending_locked, accepted, declined, contested_review | pending lock visible to both participants | No offline trade transfer |
| Personal goals | witcher | `W9` | Open goals | Render only known goals/tracks | snapshot `personal_goals`, `goal_tracks` | none | no mutation | hidden flags absent; stale snapshot label if offline | Master-only flags never shown |

## Sorceress mobile flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cast spell | sorceress | `Sorc2` | Choose spell and target, press Cast | Validate target shape locally for UI hints; server remains authority | `GET /api/sorceresses/{id}/state`; `POST /api/sorceresses/{id}/spells/cast` | `{spell_id, target_type, target_id, visibility, cast_id, source}` | accepted, invalid target, insufficient mana, needs_master_review | cast result, mana updated, review badge if needed | Hidden effects visible only to allowed roles |
| Buy potion | sorceress | `Sorc3` | Press Buy | Submit selected potion/quantity | sorceress state; `POST /api/sorceresses/{id}/potions/buy` | `{potion_id, quantity, source}` | purchased or gold/unavailable error | inventory/gold updates or error stays on market | Wholesale prices visible to sorceress |
| Transfer potion | sorceress | `Sorc4` | Send transfer | Create locked transfer or auto-accept only under allowed auth | `POST /api/sorceresses/{id}/potions/transfer` | `{to_player_id, potion_id, quantity, price_gold, mode, transfer_id, auto_accept}` | pending_locked, accepted, invalid target, favorite error | pending trade visible; target can accept/decline | Trade read model blocker must be resolved before UI coding |
| Favorite consent | sorceress/favored player | `Sorc5` or player pending state | Request or accept favorite | Request by sorceress; accept by favored player | sorceress state; player pending favorite read blocker; `/api/favorites*` | `{sorceress_id, favored_player_id, slot, favorite_id}` then accept payload | pending, accepted, duplicate, cap exceeded, change limit | consent state visible to both sides | No passive runtime bonus unless content uses it |
| Alignment evidence | sorceress | `Sorc6` | Record evidence | Submit event with chosen visibility/final flag | `POST /api/sorceresses/{id}/alignment-evidence` | `{alignment_state, evidence_type, payload, visibility, final_flag, source}` | recorded or validation/review | visible/public/private evidence state | Master sees full final evidence |
| Locked magical intent | sorceress | `Sorc7` | Cast/record final-hook intent | If final lock active, server may route to review | sorceress state; spell/alignment endpoints | spell or evidence payload | accepted locked or needs_master_review | locked intent list updates or review badge | Final summary must include this evidence |

## Lord desktop flows

| Flow | Actor | Start | UI trigger | Client behavior | Backend/read source | Payload | Response decision | Visible state | Fallback / acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Load castle home | lord | valid token from `/lords/login` | Open `/lords/home` or refresh | Fetch scoped state and select residence or requested owned `territory_id` | `GET /api/lords/{lord_id}/state` | role token header, optional local `territory_id` route/query | state or 401/403/404 | full-screen castle/territory background, top resources, left action icons, bottom-left minimap, bottom-center army/garrison/recruit lanes, bottom-right act timer and MP arc | Wrong lord token cannot view state; stale state marked, not silently trusted |
| Switch owned territory | lord | `L1` with right-side territory bubbles | Click territory circle | Change selected `territory_id`, reuse same home UI with local territory bindings | `GET /api/lords/{lord_id}/state` | no mutation | selected owned territory or unavailable | background, income, garrison, recruit stock and local building tree update; active army lane locks if hero is elsewhere | No remote ownership mutation from switching view |
| Open tutorial replay | lord | `L1` or `/lords/login` | Click `?` or `Обучение` | Load mock lord state and highlight controls | static mock fixture plus optional current state labels | none | tutorial route/view | all main buttons are explained through mock states without API mutation | Onboarding content can be expanded after lord e2e flow exists |
| Move and claim | lord | `L2/L3` from bottom-left minimap/map icon | Select route and press Move | Preview route from graph; submit full route; return to selected territory UI after response | lord state graph; `POST /api/lords/{lord_id}/move` | `{to_node_id, route_node_ids, source}` | moved, contested claim, invalid route, no MP | hero marker/location updates; MP arc updates; selected territory can change to arrival node; errors stay on map/action screen | Route must use weighted path, not only target node |
| Army/garrison transfer | lord | `L1` bottom lanes | Drag/drop unit between active army and garrison or reserve; confirm count | Lock top active-army row when selected territory is not hero location; submit count only when allowed | lord state active army location, garrisons/reserve; `POST /api/lords/{lord_id}/garrisons/transfer` | `{territory_id, card_id, count, operation, source}` | transferred or capacity/minimum/battle/location lock error | active army and garrison lanes update; locked top lane remains empty on non-local territory | Enemy garrisons redacted; no optimistic unit move |
| Buy/upgrade building | lord | `L1/L6` selected castle or territory | Click building icon/tree node, press Buy/Upgrade | Show prereq/cost/effect hints; submit building id scoped to selected location | lord state building catalog; `POST /api/lords/{lord_id}/buildings` | `{building_id, territory_id, source}` | purchased, insufficient gold, missing prereq, duplicate | local tree node becomes purchased, recruit slot or income effect updates | Residence tree is full; territory tree can start minimal |
| Recruit accumulated unit | lord | `L1` recruit strip | Click unit icon, adjust slider, press Hire | Render unit art/stats/cost and max quantity from accumulated stock; purchase goes to selected territory garrison | lord state recruit stock; `POST /api/lords/{lord_id}/recruit` | `{action:purchase_stock, territory_id, card_id, quantity, source}` | purchased, locked slot, insufficient stock/gold, unavailable | garrison count and accumulated stock update; empty locked slots remain visible | This replaces offer-list UX on the castle/territory home even if backend keeps offer compatibility |
| Raid | lord | `L1` left raid icon | Choose target, Start raid | Submit target/rule | lord state raid tokens/effects; `POST /api/lords/{lord_id}/raids` | `{target_territory_id, rule_id, source}` | debuff/loot applied or validation error | raid effect/expiry visible by rules | Raid never starts 5x6 battle |
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

- Witcher: login -> snapshot -> QR/manual -> physical confirmation -> PvE d20
  -> result/cooldown/locked reward -> restart/offline -> sync.
- Sorceress: login -> spell -> potion buy -> potion transfer/use -> favorite
  request/accept -> alignment evidence -> locked magical intent.
- Lord: token login -> castle home -> switch territory -> recruit accumulated
  unit -> army/garrison transfer -> building -> order -> raid -> map route ->
  contested claim -> battle -> return to castle/territory home.
- Personal Gwent: challenge -> table/queue -> start -> rounds/pass -> finish or
  refusal/review.
- Admin/NPC: act start/announcement/code -> review -> reward approval -> paper
  recovery -> NPC event -> visibility audit -> final summary.

Any script step that still requires Swagger, curl or direct SQLite is a blocker
for Stage 2B UI acceptance.
