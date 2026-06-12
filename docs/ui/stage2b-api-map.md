# Stage 2B API and read-model map

Этот документ связывает каждый экран Stage 2B с read source, mutation endpoint
или offline queued event. UI не должен выдумывать авторитетное состояние:
локальная правда допустима только для offline queue, чернового ввода и последнего
известного snapshot с явной stale/offline меткой.

Лордская стратегическая карта является частью текущего React/Vite lord frontend.
Backend read model отдает layout из `data/seed/lord_map_layout.json`; удаленный
FastAPI-static lord UI не является рабочим направлением.

## Endpoint groups

| Group | Endpoints | UI owners |
| --- | --- | --- |
| Auth | `POST /api/auth/player-code`, `POST /api/auth/role-token` | Shared login |
| Health/snapshot/sync | `GET /health`, `GET /api/content/snapshot`, `POST /api/events/sync`, `POST /api/qr/lookup` | mobile auto-connect, hidden diagnostics, QR/PvE |
| Lord runtime | `GET /api/lords/{lord_id}/state`, `POST /api/lords/{lord_id}/move`, `/garrisons/transfer`, `/buildings`, `/recruit`, `/raids`, `/orders`; state includes map layout/intel/pending move slices when implemented | lord castle/territory home, map, player order actions |
| Lord battles | `POST /api/lord-battles`, `GET /api/lord-battles`, `GET /api/lord-battles/{id}`, `POST /api/lord-battles/{id}/actions` | lord battle board, master ops |
| Sorceress future layer | `GET /api/sorceresses/{id}/state`, spells, potions, alignment endpoints | deferred magic/favorites/alignment UI after shared mobile V0 |
| Trade | `POST /api/trade-transfers`, accept, decline | mobile trade/potion transfer |
| Favorites | `POST /api/favorites`, `POST /api/favorites/{id}/accept` | deferred sorceress future layer |
| PvP/Gwent | `POST /api/pvp/challenges`, `GET /api/pvp/tables`, start, rounds, finish, refusal, card conversion | personal Gwent |
| Master/Admin | `GET /api/master/state`, overview, acts, timers, review, reward approvals, corrections, NPC, reputation, visibility audit, backups, final summary | Admin Studio |

## Screen read and mutation mapping

| Screen | Read source | Mutation/event | Payload fields required | Response fields UI must use | Visibility boundary | Contract status |
| --- | --- | --- | --- | --- | --- | --- |
| `Ops0 Connection Bootstrap` | `/health`, local settings | local save fallback server URL | connection QR or URL, master/tech action | health `status`, database status | master/tech only; hidden from normal player flow | covered as diagnostic, not player-first UX |
| `Shared2 Login` | auth response plus background `/health` result | `POST /api/auth/player-code`, `POST /api/auth/role-token` | `player_code`, `device_id`; or `token` | role/player id, role_type, owner_id, snapshot path, connection/offline badge | returned auth scope only | covered |
| `Shared3 Snapshot / Sync Queue` | `GET /api/content/snapshot`, `user://event_queue.json`, `user://sync_status.json` | `POST /api/events/sync` | authenticated actor, event batch, event ids, client sequence | per-event status, duplicate/rejected/review/approval state | current player; master via Admin | covered |
| `W1 Home / Journal` | player-scoped snapshot, `GET /api/players/{id}/reputation` online | none | none | character, role skin, level, XP, gold, descriptive reputation, act state | no hidden goal flags or exact reputation | partial: needs mobile current player state read model for post-sync resource changes |
| `W2 QR / Manual ID` | snapshot `qr_objects`, optional `/api/qr/lookup` | local QR context event; optional lookup | opaque code, player/device/source, physical flag | QR status, qr_mode, act lock, review reason | no hidden future content beyond allowed snapshot | covered |
| `W3 Physical Presence` | local QR context | queued `qr_scene_started` or `qr_attempt` | qr_id, player_id, source, physical_presence_confirmed, review reason | local_status; later sync status | player/master review | covered |
| `W4 PvE Scene` | snapshot `pve_scenarios`, `mobs`, `rewards`, player stats | local `pve_completed` | generated d20, modifiers, scenario, QR, reward status | local result; later sync result | current player; master sees roll log | covered |
| `W5 PvE Result` | local event + sync response | `/api/events/sync` through Shared3 | event id/client sequence | accepted, duplicate, rejected, pending approval, review | locked reward visible, master reason redacted if needed | covered |
| `W6A Gear Inventory` | snapshot plus mobile player inventory/equipment read model | equipment save/use endpoint blocker | gear ids, slot, source | equipped/locked/stale/error states | current player; master-only lock reasons redacted | blocker: TASK-047 needs authoritative player gear/equipment read model after sync |
| `W6B Bag` | snapshot plus mobile player inventory read model | `POST /api/players/{id}/potions/use`, trade endpoints | asset/potion ids, scene id, transfer payload | owned/locked/pending/error states | current player; master-only lock reasons redacted | blocker: TASK-047 needs authoritative player bag/inventory read model after sync |
| `W6C Gwent Deck` | snapshot plus Gwent card/deck read model | deck save/validation endpoint blocker; PvP/Gwent endpoints | deck id, leader_card_id, card ids, source | saved/invalid deck, locked card, stale deck | current player; opponent hidden hand rules respected | blocker: TASK-047/TASK-048 need current deck read model and validation before PvP |
| `W7 Orders` | player order board read model | `POST /api/lords/{lord_id}/orders` with player auth | action, order_id, object_id/result_event_id | accepted/submitted/conflict/review | public/addressed only | blocker: TASK-047 needs player-visible order board/read model |
| `W8 Trade` | trade transfer read model | `/api/trade-transfers*` | from/to, asset, quantity, price, mode, transfer id | pending_locked, accepted, declined, contested_review | participants and master | blocker: TASK-047 needs incoming/outgoing transfer read model |
| `W9 Personal Goals` | snapshot `personal_goals`, `goal_tracks` | none | none | known goal progress, revealed hooks | hidden `goal_flags` redacted | covered for snapshot; online progress read model may be needed if goals mutate mid-act |
| `W10 Personal Gwent` | `GET /api/pvp/tables`; match/challenge read model | `/api/pvp/challenges*`, rounds, finish, refusal | challenge, stake, mulligans, plays, passed, finish outcome | table/queue, match state, round state, stake transfer/review | participants and master | blocker: TASK-048 needs GET current challenge/match read model for restart/resume |
| `W11 Act Unlock` | snapshot `act_unlock_codes`, local act unlock state | queued/local `act_unlocked_offline` event and later `/api/events/sync` validation | act id, unlock code/QR proof, player/device/source | accepted, invalid, rejected, relocked | current player only; future content redacted until valid | covered for local UI; server validation already part of sync/act unlock policy |
| `Sorc1-Sorc7 Future Layer` | sorceress state endpoints | spells, potions, favorites, alignment endpoints | future magic/potion/favorite/alignment payloads | future accepted/review/error states | sorceress/favored/master visibility | deferred: not a blocker for shared mobile V0/TASK-047 |
| `L1 Castle / Territory Home` | `GET /api/lords/{lord_id}/state`; local selected `territory_id` | none directly; opens scoped modals/screens | role token, optional selected territory route/query | lord/domain resources, total income per hour, current act/timer, movement MP/refill, selected territory, background asset id, local income, active army location, army lane lock, garrison slots, recruit stock, building tree, orders/raid/battle alerts | lord-scoped | covered for existing state; TASK-046 extends read model for selected territory UI, recruit stock and location lock |
| `L2 Illustrated Map` | lord state graph/territories plus `lord_map_layout` and `lord_map_intel` from `GET /api/lords/{lord_id}/state` or static manifest + scoped state | none until move confirm | none | node coordinates, edge polylines, territory hit-zones, minimap transform, full graph, route costs, owner, contested, hero location, enemy-army presence/details by intel level, pending move if active | enemy army/garrison details redacted unless visible by owner/master/scouting/magic/NPC reveal; master-only full map stays in Admin | partial: TASK-046/TASK-067 must add map layout manifest, intel read model and pending-move read model |
| `L3 Route Preview / Move / Claim` | lord state route graph, intel redactions and pending move status | `POST /api/lords/{lord_id}/move` | `to_node_id`, `route_node_ids`, `expected_cost`, `source` | `pending_move` with route/start/arrival, moved/claim/prebattle/error, MP, auto-completed arrival status | lord-scoped; contested visible to lords | partial: move endpoint must become pending-move/arrival-authoritative, not only synchronous location update |
| `L4 Territory Detail` | selected territory slice from lord state | none | selected `territory_id` | background asset id, owner/status, local income, fort/capacity, garrison redactions, local recruit stock, local building tree, hero-present flag | own garrison visible, enemy hidden | partial: TASK-046 must expose selected territory fields or derive them deterministically from lord state |
| `L5 Army Transfer` | lord state active army location, armies/reserve/garrisons | `POST /api/lords/{lord_id}/garrisons/transfer` | territory_id, card_id, count, operation, source | transfer/error, updated counts, location/battle lock reason | lord-scoped | covered for transfer; TASK-046 UI must not enable active-army row when hero is elsewhere |
| `L6 Building Tree` | lord state building catalog/tree scoped by residence or selected territory | `POST /api/lords/{lord_id}/buildings` | building_id, optional territory_id, source | purchased/error, resources/effects, unlocked recruit/building slots | lord-scoped | covered for residence catalog; TASK-046 adds minimal territory tree binding |
| `L7 Recruit Unit Modal` | lord state accumulated recruit stock for selected territory | `POST /api/lords/{lord_id}/recruit` | action, territory_id, card_id, quantity, source | purchased/error, updated garrison, updated stock, locked slot state | lord-scoped | partial: TASK-046 replaces offer-list UI with accumulated-stock read/write shape |
| `L8 Raid` | `GET /api/lords/{lord_id}/state` fields `raid_tokens`, `raid_rules[]`, `raid_targets[]`, `active_raid_effects[]`, `raid_history[]`, plus `building_catalog`/`owned_buildings` and `resources.gold` through `domain.gold` | `POST /api/lords/{lord_id}/raids` | `target_territory_id`, `rule_id`, `expected_token_cost`, `expected_gold_cost`, `source` | `started`, `resisted`, `loot_applied`, `validation_error`, `needs_master_review`, updated `raid_tokens`, updated `gold`, `active_raid_effects[]`, `audit_event_id` | lord sees own raid rules/tokens/costs/results; foreign target details are redacted unless visibility allows; master sees full log in Admin | covered; raid is not battle and never opens the 5x6 board |
| `L9 Orders` | lord state orders | `POST /api/lords/{lord_id}/orders` | create/cancel fields | order status, escrow/review | public/addressed/player scoped | covered for lord; player read blocker remains |
| `L10 Lord Battle` | `/api/lord-battles*` | battle create/action endpoints | create/action payload, actor side/domain | board, turn, timer, result/review | participants/master | covered |
| `L11 Paper Continuation` | last known lord state, printed sheets | later Admin paper recovery | paper form fields | paper recovered/review result | master recovery | covered as outage-only |
| `L12 Tutorial / Mock Lord` | static mock data plus optional current lord labels | none | none | mock castle/territory/map/recruit/order/raid/battle states | training only | covered as non-authoritative UI |
| `A1-A11 Admin` | master endpoints listed above | master endpoints listed above | operator/reason required for corrections/review | master read models | master-only | covered; restore rehearsal residual risk remains TASK-036 |

## L8 Raid contract

`L8 Raid` is a lord command-table screen, not a map, order form or battle entry.
The read model is owned by `GET /api/lords/{lord_id}/state`:

- `raid_tokens`: spendable raid resource shown separately from MP.
- `raid_rules[]`: `rule_id`, `name`, `tier`, `category`, `description`,
  `token_cost`, `gold_cost`, `duration_minutes`, `effect_type`,
  `allowed_target_types`, `required_building_ids`, `visibility`, `counterplay`,
  and `locked_reason` when unavailable.
- `raid_targets[]`: `target_territory_id`, `name`, `owner_domain_id`, `tier`,
  `bonus_type`, `is_residence`, `is_raid_only`, `active_effects`,
  `raid_resistance_label`, `visibility_level`, `can_target`,
  and `disabled_reason`.
- `active_raid_effects[]` and `raid_history[]`: visible result/expiry records
  for source/target domains.

`POST /api/lords/{lord_id}/raids` accepts
`{target_territory_id, rule_id, expected_token_cost, expected_gold_cost, source}`.
Validation errors include no token, insufficient gold, locked rule, invalid
target, duplicate active effect, final lock, wrong lord token and stale expected
cost. The response returns the new active effect, updated token/gold totals,
result flags and an audit event id.

## Explicit read-model blockers

These blockers must be resolved by the owning UI implementation task before the
screen can be accepted as playable:

| Blocker id | Owning task | Affected screens | Missing/ambiguous read source | Required shape |
| --- | --- | --- | --- | --- |
| `UI-BLOCKER-045-01` | `TASK-047` | `W1`, `W6A`, `W6B`, `W6C` | Current player state/inventory after sync/restart, including equipped gear, owned bag assets, locked assets, potion counts, Gwent cards/deck and spendable gold | `GET /api/players/{id}/state` or equivalent snapshot refresh field with `assets`, `gear`, `bag`, `deck`, `locks`, `gold`, `xp`, `level`, `reputation_descriptor` |
| `UI-BLOCKER-045-02` | `TASK-047`, `TASK-046` | `W7`, `L9` player side | Player-visible order board and player's accepted/submitted orders | read model with public/addressed orders, object_id redactions, status, escrow label, conflict/review state |
| `UI-BLOCKER-045-03` | `TASK-047` | `W8`, `Sorc4` | Incoming/outgoing trade transfers for a player after reload | read model with transfer id, participants, asset label, quantity, price, status, lock state |
| `UI-BLOCKER-045-04` | future sorceress layer | `Sorc5`, favored player consent view | Pending favorite requests visible to the favored player | read model with favorite id, sorceress label, slot, status, cap warning |
| `UI-BLOCKER-045-05` | `TASK-048` | `W10` | Current PvP challenge and Gwent match state after reload/restart | `GET` read model for challenge/match with table, players, stake, hand/rows/rounds/pass/review state scoped to participant |
| `UI-BLOCKER-045-06` | `TASK-047`, `TASK-048` | mobile final lock hints | Player-visible final-lock/PvP-lock state outside master summary | snapshot or endpoint field that says which actions are locked and why, without leaking master-only evidence |
| `UI-BLOCKER-046-01` | `TASK-046` | `L1`, `L4`, `L6`, `L7` | Castle/territory home needs selected-territory read model: background asset, local income, recruit stock `rate_per_hour/current_stock`, garrison slots, local building tree, and `active_army.location_territory_id` lock reason | extend `GET /api/lords/{lord_id}/state` or add derived frontend mapper with server fields for `territory_views[]`, `active_army_location`, `recruit_stock[]`, `building_tree_by_territory[]` |
| `UI-BLOCKER-046-02` | `TASK-046` | `L7` | Existing recruit offers do not express accumulated `+X/hour` and `(current stock)` purchase model | backend compatibility shape for `purchase_stock` or deterministic adapter from runtime recruit/stock tables; UI must not pretend stock exists without server state |
| `UI-BLOCKER-046-03` | `TASK-046`, `TASK-067` | `L2`, `L3` | Illustrated map needs a stable visual/data binding, not inferred image clicks | `lord_map_layout.json` or equivalent with canvas bounds, node coordinates, edge polylines, territory hit-zones, label anchors, minimap transform, viewport defaults and art asset id |
| `UI-BLOCKER-046-04` | `TASK-046` | `L2`, `L3`, `A6` | Enemy intel redaction and pending movement must survive reload/closed tab and be server-authoritative | `GET /api/lords/{lord_id}/state` includes `lord_map_intel` enemy army/garrison visibility levels, current `pending_move` route/start/arrival/status, auto-completed arrival result and action locks |

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
