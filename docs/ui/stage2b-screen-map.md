# Stage 2B screen map

Документ фиксирует карту экранов для `TASK-045`: какие поверхности должны
существовать до реализации Playable Role UI, какие роли ими пользуются, какие
состояния должны быть видимы и какие экраны позднее нужно визуально принять в
`TASK-067`.

Формат намеренно flow-first: это не финальный дизайн и не wireframes. Один
экран включает штатные состояния ошибки, offline, review и locked, если они не
меняют основной пользовательский маршрут.

## Conventions

- `W*` - экраны ведьмака на Godot mobile.
- `Sorc*` - дополнительные экраны чародейки на Godot mobile.
- `L*` - экраны графа/лорда в браузере на компьютере.
- `A*` - мастерские и NPC-master экраны в Admin Studio.
- `Shared*` - общие auth/sync/error экраны.
- `Ops*` - скрытые технические/мастерские экраны, не входящие в обычный
  player flow.
- Swagger, curl, API docs и ручная SQLite-правка не являются пользовательским
  маршрутом приемки для игроков и лордов.
- Бумажный режим является outage recovery и не заменяет отсутствующий штатный
  экран.
- Для первой мобильной реализации ведьмаки и чародейки используют общий
  `Mobile Adventurer V0` flow из
  `docs/ui/mobile-witcher-sorceress-shared-flow-v0.1.md`: `W1-W11` применяются
  к обеим ролям, а чародейская магия/зелья/favorites/alignment остаются
  выключенным future layer.

## Screen flow diagrams

### Общий вход

```mermaid
flowchart TD
  BOOT["Auto-connect bootstrap в фоне"] -->|"server ok / last good server"| S2["Shared2 Вход по коду"]
  BOOT -->|"нет связи, есть snapshot"| S2O["Shared2 state: offline badge / игра по последнему snapshot"]
  BOOT -->|"нет связи, нет snapshot"| S2H["Shared2 state: обратиться к мастеру"]
  OPS0["Ops0 скрытая настройка подключения"] -. "только мастер/техник" .-> BOOT
  S2 -->|"неверный player_code или role_token"| S2E["Shared2 state: invalid code message"]
  S2 -->|"код ведьмака или чародейки OK"| M1["W1 Mobile Home / Journal"]
  S2 -->|"token графа OK"| L1["L1 Castle / Territory Home"]
  S2 -->|"token мастера OK"| A1["A1 Admin Overview"]
```

### Mobile Adventurer V0: ведьмак и чародейка

```mermaid
flowchart TD
  W1["W1 Home / Journal"] -->|"QR / Manual ID"| W2["W2 QR / Manual ID"]
  W2 -->|"valid code"| W3["W3 Physical Presence"]
  W2 -->|"unknown code"| W2E["W2 state: invalid / manual_rate_limit"]
  W2 -->|"future act"| W11["W11 Act Unlock"]
  W3 -->|"confirm"| W4["W4 PvE Scene"]
  W3 -->|"flag issue"| W3R["W3 state: queued needs_master_review"]
  W4 -->|"roll app d20"| W5["W5 PvE Result"]
  W5 -->|"sync later"| Shared3["Shared3 Sync Queue"]
  W5 -->|"reward / locked reward"| W6B["W6B Bag"]
  W1 -->|"inventory / gear"| W6A["W6A Gear Inventory"]
  W1 -->|"bag"| W6B
  W1 -->|"orders"| W7["W7 Orders"]
  W1 -->|"trade"| W8["W8 Trade"]
  W1 -->|"goals"| W9["W9 Personal Goals"]
  W1 -->|"Gwent / PvP"| W10["W10 Personal Gwent"]
  W10 -->|"deck"| W6C["W6C Gwent Deck"]
  W1 -->|"sync strip"| Shared3
  W11 -->|"valid unlock code"| W1
```

### Чародейка: future layer после V0

```mermaid
flowchart TD
  W1["W1 Shared Home / Journal"] -. "future: enable magic module" .-> S1["Sorc1 Magic Hub"]
  S1 -. "future" .-> S2["Sorc2 Spell Catalog"]
  S1 -. "future" .-> S3["Sorc3 Potion Market"]
  S1 -. "future" .-> S5["Sorc5 Favorites"]
  S1 -. "future" .-> S6["Sorc6 Alignment / Intent"]
```

### Граф: замок и территории на компьютере

```mermaid
flowchart TD
  L0["/lords/login"] -->|"Вход: role token OK"| L1["L1 Castle / Territory Home"]
  L0 -->|"Обучение"| L12["L12 Tutorial / Mock Lord"]
  L1 -->|"левая иконка зданий"| L6["L6 Building Tree"]
  L1 -->|"левая иконка карты или мини-карта снизу слева"| L2["L2 Illustrated Map"]
  L2 -->|"клик видимой территории"| L3["L3 Route Preview / Move / Claim"]
  L3 -->|"confirm route"| L3M["L3 state: pending move / horse animation"]
  L3M -->|"arrival owned/route waypoint"| L1U["L1 state: hero moved / selected territory updates"]
  L3M -->|"arrival neutral/enemy"| L3B["L3 state: battle banner / prebattle"]
  L3 -->|"invalid / no MP / forbidden target"| L3E["L3 state: validation error"]
  L1 -->|"доска объявлений"| L9["L9 Orders"]
  L1 -->|"иконка рейдов"| L8["L8 Raid"]
  L1 -->|"красная иконка боя активна"| L10["L10 Lord Battle"]
  L1 -->|"клик юнита найма"| L7["L7 Recruit Unit Modal"]
  L1 -->|"drag/drop армия <-> гарнизон"| L5["L5 Army Transfer"]
  L1 -->|"круг территории справа"| L1T["L1 state: same UI, selected territory"]
  L1 -->|"network outage"| L11["L11 Paper Continuation Notice"]
```

### Мастер / NPC-master

```mermaid
flowchart TD
  A1["A1 Admin Overview"] -->|"acts"| A2["A2 Acts / Timers"]
  A1 -->|"review"| A3["A3 Event / Sync Review"]
  A3 -->|"locked reward"| A4["A4 Reward Approvals"]
  A1 -->|"paper form"| A5["A5 Paper Recovery"]
  A1 -->|"lord ops"| A6["A6 Lord Ops"]
  A1 -->|"PvP ops"| A7["A7 PvP Ops"]
  A1 -->|"NPC scene"| A8["A8 NPC Tools"]
  A1 -->|"visibility"| A9["A9 Reputation / Visibility Audit"]
  A1 -->|"backup"| A10["A10 Backup / Recovery"]
  A1 -->|"final"| A11["A11 Final Summary"]
```

## Shared screens

| Screen | Surface | Purpose | Primary actions | Read source | Mutation/event | Visibility | States | Visual acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Ops0 Connection Bootstrap` | Godot mobile diagnostic, browser panels if needed | Скрыто настроить/проверить локальный сервер до игры | Проверить `/health`, принять connection QR payload, сохранить fallback URL | `/health`, saved local settings | Save local server URL | master/tech only; not normal player flow | server unreachable, retry, stale local data | diagnostic state only, not player-first screenshot |
| `Shared2 Login` | Godot mobile, browser panels | Войти по игровому коду | Ввести `player_code` или `role_token`; увидеть короткий auto-connect/offline badge | local session, auth response, background `/health` | `POST /api/auth/player-code`, `POST /api/auth/role-token` | scoped by returned role | wrong token, invalid code, rejected device, offline snapshot/help state | TASK-067 auth screenshots |
| `Shared3 Snapshot / Sync Queue` | Godot mobile | Показать snapshot и очередь событий | Refresh snapshot, sync queue, retry failed sync | `GET /api/content/snapshot`, `user://event_queue.json`, `user://sync_status.json` | `POST /api/events/sync` | current player only | offline, pending, synced, sync_error, needs_master_review, duplicate, rejected | TASK-067 mobile sync states |

## Shared witcher/sorceress mobile screens

| Screen | Purpose | Primary actions | Read source | Mutation/event | Visibility | States | Visual acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `W1 Home / Journal` | Главный экран ведьмака или чародейки V0 | Open QR, gear inventory, bag, orders, trade, goals, Gwent, sync queue | player-scoped snapshot; player reputation endpoint when online | none | player-visible only; descriptive reputation | stale snapshot, offline, sync badge, final lock hint | shared mobile home screenshot with witcher and sorceress skins |
| `W2 QR / Manual ID` | Найти QR/manual сцену | Scan QR text, enter manual ID | snapshot `qr_objects`, optional `POST /api/qr/lookup` | local QR context event if review needed | no hidden scene truth beyond visible snapshot row | unknown_qr, manual_rate_limit, future act locked, cooldown | QR/manual states |
| `W3 Physical Presence` | Подтвердить честность сцены | Confirm physical presence, flag issue | local QR context | queued `qr_scene_started` or `qr_attempt` | current player and master review | needs_master_review, honesty_violation_suspected | presence confirmation |
| `W4 PvE Scene` | Провести offline PvE | Roll app-generated d20 | snapshot `pve_scenarios`, `mobs`, `rewards`, player stats | local `pve_completed` event | current player; master sees roll log after sync | no editable d20, one-roll-only, scene already rolled | PvE roll/result |
| `W5 PvE Result` | Показать итог сцены | Review reward, return home, sync later | local PvE event, sync response | `POST /api/events/sync` through Shared3 | player sees local result; locked reward is explicit | success, failure cooldown, locked reward, pending sync, rejected | reward/cooldown/locked |
| `W6A Gear Inventory` | Оружие, защита, экипировка и активные бонусы | Equip, unequip, inspect requirements | player-scoped snapshot and player inventory read model blocker | player equipment endpoint/blocker; local draft until sync where allowed | no master-only locks/reasons | locked gear, stale gear, rejected equip | gear/inventory states |
| `W6B Bag` | Предметы, зелья, артефакты, квестовые объекты и locked rewards | Use potion/item, start trade, inspect locked asset | player-scoped snapshot and player inventory read model blocker | `POST /api/players/{player_id}/potions/use`; trade endpoints | no master-only locks/reasons | locked asset, pending transfer, rejected use | bag/trade states |
| `W6C Gwent Deck` | Карты и колода Гвинта | Add/remove card, auto-build, inspect deck validity | snapshot plus Gwent deck/card read model | deck save/validation endpoint blocker; PvP/Gwent endpoints | current player; opponent hand hidden | invalid deck, locked card, stale deck | deck states |
| `W7 Orders` | Заказы лордов | Accept, submit success | player order board read model blocker | `POST /api/lords/{lord_id}/orders` with player auth | public/addressed visible only | active cap, object conflict, contested_review | orders list/state |
| `W8 Trade` | Торговля online-only | Create, accept, decline transfer | trade transfer read model blocker | `POST /api/trade-transfers`, accept, decline | participants and master only | pending_locked, accepted, declined, contested_review | trade states |
| `W9 Personal Goals` | Личные цели и прогресс | Inspect known goals | snapshot `personal_goals`, `goal_tracks` | none in player UI | hidden `goal_flags` redacted | locked final hook, stale snapshot | goals screenshot |
| `W10 Personal Gwent` | Личный PvP/Gwent | Challenge, queue/table, start, round, pass, finish, refusal | `GET /api/pvp/tables`; Gwent match read model blocker | `POST /api/pvp/challenges`, start, rounds, finish, refusal | participants and master only | queued, active challenge cap, table full, needs_master_review, locked stake | mobile Gwent table |
| `W11 Act Unlock` | Открыть будущий акт вне Wi-Fi после мастерского объявления | Enter unlock code, scan unlock QR, return | snapshot `act_unlock_codes`, local act state | queued/local unlock event and later sync validation | current player only; hidden future content redacted | invalid code, future act still hidden, accepted unlock | act unlock state |

## Sorceress mobile screens

В V0 чародейка не имеет обязательных отдельных экранов. Она использует
`W1-W11` с чародейским portrait/accent/role label. Future screens
`Sorc1-Sorc7` остаются в backlog для магии, рынка зелий, favorites, alignment
evidence and locked magical intent после принятия общего мобильного gameplay.

## Lord desktop screens

| Screen | Purpose | Primary actions | Read source | Mutation/event | Visibility | States | Visual acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `L1 Castle / Territory Home` | Главный экран после входа: замок или выбранная территория | Hover/click circular action icons, switch owned territory, open minimap/map, drag army/garrison, open recruit modal, logout, replay tutorial | `GET /api/lords/{lord_id}/state` plus selected `territory_id` | none directly; actions open scoped screens/modals | lord-scoped | wrong token, stale state, active battle alert, selected territory unavailable | lord castle/territory home |
| `L2 Illustrated Map` | Полноэкранная стратегическая карта `venue_map_v1` в стиле Olden Era-like tactical map | Pan camera, click territory/army, inspect tactical popup, preview route, return to selected territory UI | `GET /api/lords/{lord_id}/state` with `map_nodes`, `map_edges`, territories, `lord_map_layout`, `lord_map_intel`, pending move slice | none until move confirm | full graph visible; enemy details redacted; master sees all in Admin | full graph, owner/neutral/contested, excluded zones hidden/no-play, hidden enemy army/garrison details, pending move read-only | illustrated map with pan/minimap/intel overlays |
| `L3 Route Preview / Move / Claim` | Движение лошади, server-authoritative arrival и запуск захвата | Confirm cheapest route, cancel preview, watch horse animation, open battle/prebattle banner | lord state route graph plus pending move/arrival status | `POST /api/lords/{lord_id}/move` | lord-scoped; contested visible to lords | no MP, invalid route, forbidden target, route stopped by enemy/contested, pending_move, arrival_autocomplete, battle required | move/claim states |
| `L4 Territory Detail` | Тот же UI для конкретной захваченной территории | Inspect local income, garrison, recruit stock, local building tree | lord state selected territory, garrisons, recruit stock, building tree | none until action | own garrison visible; enemy hidden/redacted | owner, contested, capacity, hero not here locks top army lane | territory home variant |
| `L5 Army Transfer` | Переброска армии и гарнизона из нижних рядов | Active to garrison, garrison to active, reserve to active where allowed | lord state active army location, reserve, garrisons | `POST /api/lords/{lord_id}/garrisons/transfer` | lord-scoped | capacity, minimum garrison, active battle lock, selected territory not hero location | transfer UI/modal |
| `L6 Building Tree` | Дерево построек выбранной локации | Select building, inspect bonus branch, buy/upgrade | lord state buildings/catalog scoped by selected `territory_id` | `POST /api/lords/{lord_id}/buildings` | lord-scoped | locked, unlocked, purchased, missing prerequisite, insufficient gold | castle/territory tree |
| `L7 Recruit Unit Modal` | Покупка накопленных войск выбранной локации | Open unit widget, choose quantity by slider, hire into garrison | lord state recruit stock for selected `territory_id` | `POST /api/lords/{lord_id}/recruit` | lord-scoped | locked slot, insufficient stock/gold, purchased to garrison | recruit unit modal |
| `L8 Raid` | Рейд без 5x6 боя | Choose target, start raid | lord state raid tokens/effects/targets | `POST /api/lords/{lord_id}/raids` | effects visible by rules | invalid target, no token/gold, debuff/loot, expiry | raid screen |
| `L9 Orders` | Заказы графа | Create public/addressed order | lord state orders | `POST /api/lords/{lord_id}/orders` | public/addressed; escrow redactions as needed | active cap, escrow lock, object conflict, review | order screen |
| `L10 Lord Battle` | Синхронный бой 5x6 | Deploy, move, attack, defend, surrender, auto | `GET /api/lord-battles`, `GET /api/lord-battles/{id}` | `POST /api/lord-battles`, `POST /api/lord-battles/{id}/actions` | battle participants and master | legal action, timer, timeout, auto-resolve, takeover | 5x6 board |
| `L11 Paper Continuation Notice` | Outage-only fallback | Read continuation instructions | last known lord state and printed sheets | later `paper_lord_action`/`paper_lord_battle` via Admin | paper operator/master | outage only, not normal acceptance | paper notice |
| `L12 Tutorial / Mock Lord` | Обучение лорда перед игрой | Walk through mock castle, territory, map, orders, raid, recruit and battle states | static mock state plus fixture lord state | no mutation | training only | can be replayed from `?` button | tutorial flow |

## Master / NPC-master desktop screens

| Screen | Purpose | Primary actions | Read source | Mutation/event | Visibility | States | Visual acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `A1 Admin Overview` | Мастерская сводка | Navigate, refresh, inspect blockers | `GET /api/master/admin/overview`, `GET /api/master/state` | none | master-only | wrong token, blocking alerts | admin overview |
| `A2 Acts / Timers` | Акты, объявления, коды | Start act, record announcement, reveal code | `GET /api/master/acts/state`, `GET /api/master/timers` | `POST /api/master/acts/{id}/start`, physical-announcement, unlock-code reveal | master-only | code hidden until announcement, final lock | acts/timers |
| `A3 Event / Sync Review` | Очередь событий и review | Approve/reject/correct events | `GET /api/master/state`, `GET /api/master/review-queue` | `POST /api/events/{event_id}/review` | master-only | P0/P1/P2/P3, duplicate, rejected | review queue |
| `A4 Reward Approvals` | Locked rewards | Approve, reject, correct | `GET /api/master/state` reward approvals | `POST /api/master/reward-approvals/{approval_id}` | master-only | pending, approved, rejected, corrected | reward approval |
| `A5 Paper Recovery` | Внести бумажное событие | Choose form, enter fields, submit | `GET /api/master/state` for context | `POST /api/events/sync` with `source=paper_recovered` | master-only | duplicate, conflict, needs_master_review | paper recovery |
| `A6 Lord Ops` | Операции карты/лордов | Inspect/correct map, garrisons, battles, pending rewards | `GET /api/master/state` | `POST /api/master/game-ops/corrections` | master-only | correction requires reason/operator | lord ops |
| `A7 PvP Ops` | PvP throttle and reviews | Set throttle, inspect tables/refusals | `GET /api/pvp/tables`, `GET /api/master/state` | `POST /api/master/pvp-throttle`, review endpoints | master-only | normal, limited, paused, timeout review | PvP ops |
| `A8 NPC Tools` | King/Wanderer events | Record/resolve event/deal | `GET /api/master/npc/events`, `GET /api/master/npc/deals` | `POST /api/master/npc/events`, resolve | master-only for hidden prices | hidden price, final flag, severity | NPC tools |
| `A9 Reputation / Visibility Audit` | Видимость и репутация | Inspect exact values, change reputation, audit redactions | `GET /api/master/reputation/{id}`, `GET /api/master/visibility-audit` | `POST /api/master/reputation/{id}/change` | master-only | redaction failure blocks UI acceptance | visibility audit |
| `A10 Backup / Recovery` | Backup status | Run backup, inspect status | `GET /api/master/backups/status` | `POST /api/backups/run` | master-only | restore remains TASK-036 residual-risk path | backup |
| `A11 Final Summary` | Финальная сводка | Inspect evidence, add note, export | `GET /api/master/final-summary` | `POST /api/master/final-summary/notes` | master-only by default | missing evidence, pending locks, locked magical intent | final summary |

## Visual acceptance handoff for TASK-067

`TASK-067` must turn this screen map into visual acceptance artifacts before
role UI implementation tasks start. Required screenshot/prototype set:

- mobile: `Shared2`, `Shared3`, `W1-W11` plus `W6A/W6B/W6C` for witcher and
  sorceress skins; hidden `Ops0` connection diagnostics are not a normal
  player-first screenshot; `Sorc1-Sorc7` are future-layer references, not first
  V0 blockers;
- lord desktop: `L1-L10` plus outage-only `L11` notice;
- Admin desktop: `A1-A11`;
- state variants: invalid code, server unreachable, offline snapshot, pending
  sync, sync error, needs master review, rejected, duplicate, cooldown, locked
  reward, wrong token, hidden-data redaction, final lock;
- visual reference surfaces: lord castle/territory home matching the reference
  composition, illustrated lord map, castle/territory building tree, thematic
  territory backgrounds/forts, personal Gwent table, visually distinct 5x6 lord
  battle board.

All production visual assets must be original/local/generated. References define
layout, density, mood and affordances only.
