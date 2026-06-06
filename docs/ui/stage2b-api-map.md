# Stage 2B API and read-model map

Этот документ связывает каждый экран Stage 2B с read source, mutation endpoint
или offline queued event. UI не должен выдумывать авторитетное состояние:
локальная правда допустима только для offline queue, чернового ввода и последнего
известного snapshot с явной stale/offline меткой.

## Endpoint groups

| Group | Endpoints | UI owners |
| --- | --- | --- |
| Auth | `POST /api/auth/player-code`, `POST /api/auth/role-token` | Shared login |
| Health/snapshot/sync | `GET /health`, `GET /api/content/snapshot`, `POST /api/events/sync`, `POST /api/qr/lookup` | mobile shared, QR/PvE |
| Lord runtime | `GET /api/lords/{lord_id}/state`, `POST /api/lords/{lord_id}/move`, `/garrisons/transfer`, `/buildings`, `/recruit`, `/raids`, `/orders` | lord castle/territory home, map, player order actions |
| Lord battles | `POST /api/lord-battles`, `GET /api/lord-battles`, `GET /api/lord-battles/{id}`, `POST /api/lord-battles/{id}/actions` | lord battle board, master ops |
| Sorceress | `GET /api/sorceresses/{id}/state`, spells, potions, alignment endpoints | sorceress mobile |
| Trade | `POST /api/trade-transfers`, accept, decline | mobile trade/potion transfer |
| Favorites | `POST /api/favorites`, `POST /api/favorites/{id}/accept` | sorceress/favored player mobile |
| PvP/Gwent | `POST /api/pvp/challenges`, `GET /api/pvp/tables`, start, rounds, finish, refusal, card conversion | personal Gwent |
| Master/Admin | `GET /api/master/state`, overview, acts, timers, review, reward approvals, corrections, NPC, reputation, visibility audit, backups, final summary | Admin Studio |

## Screen read and mutation mapping

| Screen | Read source | Mutation/event | Payload fields required | Response fields UI must use | Visibility boundary | Contract status |
| --- | --- | --- | --- | --- | --- | --- |
| `Shared1 Connection` | `/health`, local settings | local save server URL | server URL | health `status`, database status | shared | covered |
| `Shared2 Login` | auth response | `POST /api/auth/player-code`, `POST /api/auth/role-token` | `player_code`, `device_id`; or `token` | role/player id, role_type, owner_id, snapshot path | returned auth scope only | covered |
| `Shared3 Snapshot / Sync Queue` | `GET /api/content/snapshot`, `user://event_queue.json`, `user://sync_status.json` | `POST /api/events/sync` | authenticated actor, event batch, event ids, client sequence | per-event status, duplicate/rejected/review/approval state | current player; master via Admin | covered |
| `W1 Home` | player-scoped snapshot, `GET /api/players/{id}/reputation` online | none | none | character, level, XP, gold, descriptive reputation, act state | no hidden goal flags or exact reputation | partial: needs mobile current player state read model for post-sync resource changes |
| `W2 QR / Manual ID` | snapshot `qr_objects`, optional `/api/qr/lookup` | local QR context event; optional lookup | opaque code, player/device/source, physical flag | QR status, qr_mode, act lock, review reason | no hidden future content beyond allowed snapshot | covered |
| `W3 Physical Presence` | local QR context | queued `qr_scene_started` or `qr_attempt` | qr_id, player_id, source, physical_presence_confirmed, review reason | local_status; later sync status | player/master review | covered |
| `W4 PvE Scene` | snapshot `pve_scenarios`, `mobs`, `rewards`, player stats | local `pve_completed` | generated d20, modifiers, scenario, QR, reward status | local result; later sync result | current player; master sees roll log | covered |
| `W5 PvE Result` | local event + sync response | `/api/events/sync` through Shared3 | event id/client sequence | accepted, duplicate, rejected, pending approval, review | locked reward visible, master reason redacted if needed | covered |
| `W6 Inventory` | snapshot plus mobile player inventory read model | `POST /api/players/{id}/potions/use`, trade endpoints | asset/potion ids, scene id, transfer payload | owned/locked/pending/error states | current player; master-only lock reasons redacted | blocker: TASK-047 needs authoritative player inventory/read model after sync |
| `W7 Orders` | player order board read model | `POST /api/lords/{lord_id}/orders` with player auth | action, order_id, object_id/result_event_id | accepted/submitted/conflict/review | public/addressed only | blocker: TASK-047 needs player-visible order board/read model |
| `W8 Trade` | trade transfer read model | `/api/trade-transfers*` | from/to, asset, quantity, price, mode, transfer id | pending_locked, accepted, declined, contested_review | participants and master | blocker: TASK-047 needs incoming/outgoing transfer read model |
| `W9 Personal Goals` | snapshot `personal_goals`, `goal_tracks` | none | none | known goal progress, revealed hooks | hidden `goal_flags` redacted | covered for snapshot; online progress read model may be needed if goals mutate mid-act |
| `W10 Personal Gwent` | `GET /api/pvp/tables`; match/challenge read model | `/api/pvp/challenges*`, rounds, finish, refusal | challenge, stake, mulligans, plays, passed, finish outcome | table/queue, match state, round state, stake transfer/review | participants and master | blocker: TASK-048 needs GET current challenge/match read model for restart/resume |
| `Sorc1 Home` | `GET /api/sorceresses/{id}/state`, snapshot | none | none | mana, potions, spells, favorites, locked intents | current sorceress/master | covered |
| `Sorc2 Spell Catalog` | sorceress state | `POST /api/sorceresses/{id}/spells/cast` | spell_id, target_type, target_id, visibility, cast_id, source | accepted/review/error, mana/effect | effect visibility by rule | covered |
| `Sorc3 Potion Market` | sorceress state | `POST /api/sorceresses/{id}/potions/buy` | potion_id, quantity, source | purchase result, inventory/gold | sorceress/master | covered |
| `Sorc4 Potion Transfer` | sorceress state plus trade read model | `POST /api/sorceresses/{id}/potions/transfer` | target, potion, quantity, price, mode, transfer id | pending/accepted/error | participants/master | blocker follows trade read model |
| `Sorc5 Favorites` | sorceress state; favored-player pending favorites read model | `/api/favorites*` | sorceress, favored player, slot, favorite id | pending/accepted/cap error | sorceress, favored player, master | blocker: TASK-047 needs favored-player pending consent read model |
| `Sorc6 Alignment Evidence` | sorceress state | `POST /api/sorceresses/{id}/alignment-evidence` | alignment state, evidence type/payload, visibility, final flag | recorded/review/error | by visibility; master full | covered |
| `Sorc7 Locked Magical Intent` | sorceress state `locked_magical_intent` | spell/alignment endpoints | final hook or locked intent payload | accepted locked or needs_master_review | master final summary full | covered |
| `L1 Castle / Territory Home` | `GET /api/lords/{lord_id}/state`; local selected `territory_id` | none directly; opens scoped modals/screens | role token, optional selected territory route/query | lord/domain resources, total income per hour, current act/timer, movement MP/refill, selected territory, background asset id, local income, active army location, army lane lock, garrison slots, recruit stock, building tree, orders/raid/battle alerts | lord-scoped | covered for existing state; TASK-046 extends read model for selected territory UI, recruit stock and location lock |
| `L2 Illustrated Map` | lord state graph/territories from `GET /api/lords/{lord_id}/state` | none until move | none | nodes, edges, route cost, owner, contested, hero location | enemy hidden data redacted | covered; visual binding owned by TASK-067; detailed map UX is separate from castle/territory home |
| `L3 Move / Claim` | lord state route graph | `POST /api/lords/{lord_id}/move` | to_node_id, route_node_ids, source | moved/claim/error, MP | lord-scoped; contested visible to lords | covered |
| `L4 Territory Detail` | selected territory slice from lord state | none | selected `territory_id` | background asset id, owner/status, local income, fort/capacity, garrison redactions, local recruit stock, local building tree, hero-present flag | own garrison visible, enemy hidden | partial: TASK-046 must expose selected territory fields or derive them deterministically from lord state |
| `L5 Army Transfer` | lord state active army location, armies/reserve/garrisons | `POST /api/lords/{lord_id}/garrisons/transfer` | territory_id, card_id, count, operation, source | transfer/error, updated counts, location/battle lock reason | lord-scoped | covered for transfer; TASK-046 UI must not enable active-army row when hero is elsewhere |
| `L6 Building Tree` | lord state building catalog/tree scoped by residence or selected territory | `POST /api/lords/{lord_id}/buildings` | building_id, optional territory_id, source | purchased/error, resources/effects, unlocked recruit/building slots | lord-scoped | covered for residence catalog; TASK-046 adds minimal territory tree binding |
| `L7 Recruit Unit Modal` | lord state accumulated recruit stock for selected territory | `POST /api/lords/{lord_id}/recruit` | action, territory_id, card_id, quantity, source | purchased/error, updated garrison, updated stock, locked slot state | lord-scoped | partial: TASK-046 replaces offer-list UI with accumulated-stock read/write shape |
| `L8 Raid` | lord state raid tokens/effects/targets | `POST /api/lords/{lord_id}/raids` | target_territory_id, rule_id, source | debuff/loot/error | visibility by effect rules | covered |
| `L9 Orders` | lord state orders | `POST /api/lords/{lord_id}/orders` | create/cancel fields | order status, escrow/review | public/addressed/player scoped | covered for lord; player read blocker remains |
| `L10 Lord Battle` | `/api/lord-battles*` | battle create/action endpoints | create/action payload, actor side/domain | board, turn, timer, result/review | participants/master | covered |
| `L11 Paper Continuation` | last known lord state, printed sheets | later Admin paper recovery | paper form fields | paper recovered/review result | master recovery | covered as outage-only |
| `L12 Tutorial / Mock Lord` | static mock data plus optional current lord labels | none | none | mock castle/territory/map/recruit/order/raid/battle states | training only | covered as non-authoritative UI |
| `A1-A11 Admin` | master endpoints listed above | master endpoints listed above | operator/reason required for corrections/review | master read models | master-only | covered; restore rehearsal residual risk remains TASK-036 |

## Explicit read-model blockers

These blockers must be resolved by the owning UI implementation task before the
screen can be accepted as playable:

| Blocker id | Owning task | Affected screens | Missing/ambiguous read source | Required shape |
| --- | --- | --- | --- | --- |
| `UI-BLOCKER-045-01` | `TASK-047` | `W1`, `W6` | Current player state/inventory after sync/restart, including owned assets, locked assets, potion counts and spendable gold | `GET /api/players/{id}/state` or equivalent snapshot refresh field with `assets`, `locks`, `gold`, `xp`, `level`, `reputation_descriptor` |
| `UI-BLOCKER-045-02` | `TASK-047`, `TASK-046` | `W7`, `L9` player side | Player-visible order board and player's accepted/submitted orders | read model with public/addressed orders, object_id redactions, status, escrow label, conflict/review state |
| `UI-BLOCKER-045-03` | `TASK-047` | `W8`, `Sorc4` | Incoming/outgoing trade transfers for a player after reload | read model with transfer id, participants, asset label, quantity, price, status, lock state |
| `UI-BLOCKER-045-04` | `TASK-047` | `Sorc5`, favored player consent view | Pending favorite requests visible to the favored player | read model with favorite id, sorceress label, slot, status, cap warning |
| `UI-BLOCKER-045-05` | `TASK-048` | `W10` | Current PvP challenge and Gwent match state after reload/restart | `GET` read model for challenge/match with table, players, stake, hand/rows/rounds/pass/review state scoped to participant |
| `UI-BLOCKER-045-06` | `TASK-047`, `TASK-048` | mobile final lock hints | Player-visible final-lock/PvP-lock state outside master summary | snapshot or endpoint field that says which actions are locked and why, without leaking master-only evidence |
| `UI-BLOCKER-046-01` | `TASK-046` | `L1`, `L4`, `L6`, `L7` | Castle/territory home needs selected-territory read model: background asset, local income, recruit stock `rate_per_hour/current_stock`, garrison slots, local building tree, and `active_army.location_territory_id` lock reason | extend `GET /api/lords/{lord_id}/state` or add derived frontend mapper with server fields for `territory_views[]`, `active_army_location`, `recruit_stock[]`, `building_tree_by_territory[]` |
| `UI-BLOCKER-046-02` | `TASK-046` | `L7` | Existing recruit offers do not express accumulated `+X/hour` and `(current stock)` purchase model | backend compatibility shape for `purchase_stock` or deterministic adapter from runtime recruit/stock tables; UI must not pretend stock exists without server state |

If implementation discovers that an existing response already contains one of
these read models, update this table with the exact field and remove the blocker
only after a UI-first smoke can reload the screen without Swagger.

## Response handling requirements

- 401/403: stay on current screen, show wrong-token/forbidden state, do not
  clear valid offline mobile data.
- 404 missing snapshot/state: show not-imported/not-available state and route to
  master/admin recovery only for master users.
- 409/400 domain errors: stay on action screen, display server reason, do not
  locally apply optimistic authoritative changes.
- Duplicate: display already-applied/already-synced state and keep audit/history
  visible.
- `needs_master_review`: keep the action visible with review badge and do not
  expose master-only reason if player/lord is not allowed to see it.
- `pending_master_approval`: show locked reward/asset and prevent spend/trade/
  final-use controls.
