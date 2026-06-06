# Stage 2B state matrix

Этот документ делает обязательные состояния UI явными для всех поверхностей
Stage 2B. Состояния не должны быть спрятаны в Swagger, логах или устной
инструкции мастера.

## Global states

| State | Meaning | Required UI behavior | Applies to |
| --- | --- | --- | --- |
| `offline` | Клиент не видит сервер или игрок вне Wi-Fi | Показать stale/last snapshot label, разрешить только offline-safe действия, сохранить очередь | mobile, lord outage notice |
| `pending sync` | Событие поставлено в очередь или отправляется | Показать счетчик/строку события, запретить повторную отправку того же результата без idempotency | mobile |
| `synced` | Сервер принял событие | Показать accepted/synced state, оставить краткую историю | mobile, Admin |
| `sync_error` | Сеть/сервер не принял batch | Оставить событие retryable, не удалять локальный log | mobile |
| `needs_master_review` | Сервер или клиент отправил событие на review | Показать review badge и что делать игроку; мастер видит очередь и причину | all |
| `rejected` | Сервер/мастер отклонил действие | Показать readable reason if visible; не применять локальный эффект | all |
| `duplicate` | Idempotency нашла уже примененное действие | Показать already synced/applied, не дублировать награду/ставку/захват | all mutation screens |
| `cooldown` | PvE провален и QR закрыт для игрока на 30 минут | Показать таймер/причину, не стартовать сцену повторно | `W2-W5` |
| `locked reward` | Награда/asset ждет master approval или lock | Показать locked badge, заблокировать spend/trade/stake/final use | mobile, Admin |
| `wrong token` | Код/токен невалиден или не имеет scope | Оставить на login/current panel, не показать чужие данные | shared, lord, Admin |
| `hidden data` | Данные существуют, но role не имеет права видеть | Показывать redacted/unknown/hidden label, не raw value | lord/player |
| `final lock` | Финальный lock запрещает новые действия или меняет review route | Заблокировать новые PvP/orders/final intent where applicable, показать allowed recovery path | mobile, lord, Admin |
| `paper outage only` | Нормальный UI/сеть недоступны | Включить инструкцию продолжения на бумаге; recovery только через Admin | lord, master |

## Shared auth/sync state matrix

| Screen | Success | Invalid input | Offline/error | Review/locked | Acceptance marker |
| --- | --- | --- | --- | --- | --- |
| `Shared1 Connection` | `/health` ok, route to login | malformed URL stays on screen | server unreachable, retry, keep last snapshot | none | wrong IP does not wipe local data |
| `Shared2 Login` | valid code routes by role | invalid code/token message on same screen | auth unreachable keeps mobile offline data | forbidden scope shown without data leak | lord token cannot access other lord |
| `Shared3 Snapshot / Sync Queue` | snapshot saved or events synced | no player_code blocks sync | sync_error retryable | needs_master_review and locked reward counters visible | queued event survives restart |

## Witcher mobile state matrix

| Screen | Success | Invalid input | Offline/error | Review/locked | Hidden/visibility |
| --- | --- | --- | --- | --- | --- |
| `W1 Home` | Character/resources/act visible | none | stale snapshot badge | final lock hint where relevant | exact reputation number hidden |
| `W2 QR / Manual ID` | valid QR opens presence screen | unknown code/manual rate limit stays here | can use snapshot offline | future act locked, cooldown | hidden future content not revealed |
| `W3 Physical Presence` | confirmation starts scene | no QR context error | local context persists | honesty issue queues review | master review reason may be summarized |
| `W4 PvE Scene` | one app d20 generated | second roll blocked | offline allowed | scene already rolled state | no editable d20 |
| `W5 PvE Result` | success/failure shown | none | pending sync visible | locked reward, rejected, review, duplicate | master-only correction reason redacted if needed |
| `W6 Inventory` | owned assets and use buttons visible | invalid use stays on screen | stale inventory marked | locked asset disables spend/trade/stake | lock internals hidden |
| `W7 Orders` | accepted/submitted states visible | invalid object/order stays | online-only submit if server needed | object conflict/review | addressed orders scoped |
| `W8 Trade` | accepted/declined/pending states | invalid recipient/asset/price stays | online-only; no offline trade | pending lock, contested_review | only participants see transfer |
| `W9 Personal Goals` | known progress visible | none | stale snapshot | locked final hook label if revealed | hidden `goal_flags` absent |
| `W10 Personal Gwent` | table/match/result visible | invalid stake/deck/action stays | online-only | queued, refusal, review, locked stake | opponent hidden hand rules respected |

## Sorceress mobile state matrix

| Screen | Success | Invalid input | Offline/error | Review/locked | Hidden/visibility |
| --- | --- | --- | --- | --- | --- |
| `Sorc1 Home` | mana/potions/favorites visible | none | stale state badge | final lock hint | exact hidden effects absent |
| `Sorc2 Spell Catalog` | cast result/mana update | invalid target/insufficient mana | online action; stale catalog allowed read-only | needs_master_review for sensitive effect | effect visibility follows spell |
| `Sorc3 Potion Market` | purchase updates inventory | insufficient gold/unavailable | online-only purchase | duplicate purchase result if idempotent | wholesale visible to sorceress |
| `Sorc4 Potion Transfer` | pending/accepted transfer visible | invalid recipient/favorite target | online-only | pending lock/contested review | participant scoped |
| `Sorc5 Favorites` | pending/accepted favorite | duplicate/cap/change-limit errors | online-only consent | pending consent | target sees request, not all sorceress data |
| `Sorc6 Alignment Evidence` | evidence recorded | invalid evidence state | online-only | review route if sensitive | visibility field controls who sees it |
| `Sorc7 Locked Magical Intent` | locked intent visible | invalid final target | online-only | after final lock can require review | master final summary sees full evidence |

## Lord desktop state matrix

| Screen | Success | Invalid input | Offline/error | Review/locked | Hidden/visibility |
| --- | --- | --- | --- | --- | --- |
| `L1 Castle / Territory Home` | scoped domain and selected territory visible | wrong token or unavailable territory blocked | refresh error keeps last visible state marked stale | active battle/raid/order alerts; selected territory can be contested | no other lord private state |
| `L2 Illustrated Map` | nodes/edges/ownership/hero location visible | excluded node not selectable | browser/server error shows stale map | contested visible; no MP disables route submit | enemy garrisons hidden |
| `L3 Move / Claim` | route applies, MP updates | invalid route/no MP stays | no move while server unreachable | battle required/contested | route costs visible |
| `L4 Territory Detail` | local background, income, garrison, recruit and building state visible | unavailable/not-owned territory returns to last valid selection | stale territory marked | contested/battle lock; top active-army lane locked if hero is elsewhere | hidden enemy garrison redacted |
| `L5 Army Transfer` | counts update | capacity/minimum/ownership/location errors | online-only | active battle lock; hero-not-here lock | only own units shown |
| `L6 Building Tree` | purchased node/effects for selected location | missing prereq/insufficient gold | online-only buy | locked/unlocked/purchased | no hidden economy of others |
| `L7 Recruit Unit Modal` | accumulated unit stock bought into garrison | locked slot/insufficient stock/insufficient gold | online-only | garrison spawn; empty locked recruit slots stay visible | own recruit stock only |
| `L8 Raid` | debuff/loot/expiry visible | invalid target/no token/gold | online-only | target lock/effect expiry | hidden details by effect rules |
| `L9 Orders` | created/accepted/submitted | active cap/escrow conflict | online-only | contested_review, escrow locked | addressed visibility respected |
| `L10 Lord Battle` | action/turn/result visible | illegal move/attack stays | cannot progress without server except paper outage | timer, timeout, auto-resolve, takeover | only participants/master see full board |
| `L11 Paper Continuation` | paper fallback instructions visible | not applicable | outage state | later recovery review | marked not normal UI acceptance |

## Master / NPC state matrix

| Screen | Success | Invalid input | Offline/error | Review/locked | Hidden/visibility |
| --- | --- | --- | --- | --- | --- |
| `A1 Admin Overview` | overview/blockers loaded | wrong token blocked | server local failure visible | blocking alerts | master-only |
| `A2 Acts / Timers` | act/timer/code updated | invalid act or missing announcement | timer endpoint error visible | code hidden until announcement, final lock | master-only unlock code |
| `A3 Event / Sync Review` | review decision applied | missing reason/action error | state refresh error visible | P0/P1/P2/P3 open until resolved | master-only reasons |
| `A4 Reward Approvals` | approved/rejected/corrected | missing reason/correction error | refresh error visible | pending approval lock | master-only details |
| `A5 Paper Recovery` | recovered/applied or review queued | duplicate/missing paper fields | submit error visible | conflict review | paper and digital never silently overwrite |
| `A6 Lord Ops` | correction applied | missing reason/operator | refresh error visible | pending reward/battle conflict | master sees hidden lord data |
| `A7 PvP Ops` | throttle/review updated | invalid mode/reason | refresh error visible | timeout/refusal/final lock | master-only review |
| `A8 NPC Tools` | event/deal recorded | invalid NPC payload | refresh error visible | hidden price/final flag review | hidden prices master-only |
| `A9 Reputation / Visibility Audit` | exact values/audit visible | invalid delta | refresh error visible | redaction failure blocks UI acceptance | exact reputation master-only |
| `A10 Backup / Recovery` | backup status/run visible | invalid trigger | backup failure visible | restore residual risk noted | master-only |
| `A11 Final Summary` | evidence/export/note visible | invalid note | refresh/export error visible | missing locks, pending disputes | no automatic winner |

## Device and responsive smoke matrix

| Surface | Required smoke before TASK-050 | Blocking rule |
| --- | --- | --- |
| Android real phone | install/launch/connect/snapshot/restart/sync, physical QR camera scan, manual QR fallback | Missing proof blocks Stage 2B acceptance |
| iPhone real device | free provisioning/TestFlight path, local network permission, launch/connect/snapshot/restart/sync, manual QR fallback and camera path if plugin exists | Missing proof blocks Stage 2B acceptance |
| 4 lord laptops | four simultaneous browser panels, scoped tokens, map/actions/battle smoke | One lord laptop failure is a Stage 2B blocker unless paper outage drill is explicitly invoked |
| Master laptop | Admin Studio review/recovery/final smoke, backup status | Swagger does not count as master UI smoke for release-critical ops |
| Paper fallback | at least one critical outage recovery event, including lord action or lord battle | Paper is recovery only, never substitute for missing normal UI |

## Acceptance gates

- Every role has a start-to-finish no-Swagger script.
- Every screen has success, invalid input, offline/pending/review/locked state.
- Every hidden-data boundary has an explicit redaction behavior.
- Every missing read source is listed in `stage2b-api-map.md` as a blocker.
- `TASK-067` must provide visual prototype/screenshots for the listed surfaces
  before implementation tasks treat the UI as accepted.
