# Техническая архитектура - Witcher LARP App

## Stage-gate architecture

Архитектура делится на шесть проверяемых этапов, которые отражены в `tasks.json` через `project.stages`, поле `stage` и отдельные gate-задачи.

1. **Core Game Engine** (`TASK-018`) - локальный FastAPI/SQLite runtime, Godot mobile shell, lord runtime panels, event log, rule engines, auto timers, backup hooks и final summary runtime.
2. **Admin Studio** (`TASK-023`) - браузерная мастерская панель и студия: import/validation UI, snapshot controls, game ops, event review, corrections, NPC tools, visibility audit, backups и final summary view.
3. **Playable Role UI** (`TASK-050`) - полноценные игровые UI поверх Stage 1 runtime и Stage 2 Admin Studio: mobile gameplay UI на реальных Android/iOS устройствах, lord action UI с валидной картой, personal PvP/Gwent UI, paper recovery/correction forms и UI-first acceptance без Swagger для игроков/лордов.
4. **PvE Generation Engine** (`TASK-028`) - генератор внутри Admin Studio: draft quest model, templates, tier/stat/reward controls, QR modes, artifact/reputation/NPC/order flags, compiler в authoring matrix/runtime CSV и validation harness.
5. **Unique Quest Production** (`TASK-032`) - production-контур контента: 40+ QR/PvE-квестов, ручная полировка, full content pack, QR print/manual checklist и content smoke.
6. **Balance Simulation** (`TASK-037`) - симулятор archetype players и отчеты по progression, rewards, PvP, lord battles, economy, magic, artifacts, NPC deals и rehearsal readiness.

Техническая граница важна: Stage 1 не должен зависеть от генератора квестов, Stage 2 должен быть готов до Stage 2B, Stage 2B доказывает UI-first тестирование ролей без Swagger и готовность всего non-PvE gameplay на реальных игровых поверхностях, Stage 3 строит генератор уже поверх playable UI, а Stage 5 балансирует полный content pack, а не технические заглушки.

## Ключевые решения

- Домашний Wi-Fi является online-зоной игры; интернет не нужен.
- Production profile фиксирован как 15 человек всего: 13 игроков (4 лорда, 4 чародейки, 5 ведьмаков) и 2 NPC-мастера.
- Авторитетное состояние живет на локальном сервере FastAPI + SQLite на мастерском ноутбуке.
- Python/backend/tooling окружение управляется через `uv`: зависимости описаны в `pyproject.toml`, `.venv` создается через `uv sync`, команды запускаются через `uv run`.
- Мобильный клиент Godot 4 работает offline-first и хранит данные в `user://`.
- Лорды и мастера используют веб-панели в браузере.
- Контент готовится в CSV, импортируется в SQLite и экспортируется в mobile snapshot; full pack содержит 40+ QR/PvE, минимум 15 always-available/repeatable сцен и 25+ unique objects.
- `docs/game-mechanics.md` задает уточненную механику PvE, заказов, личного Гвинта, лордских боев, артефактов, NPC-сделок и фабрики QR-контента.
- `docs/app-technical-plan-v0.1.md` является актуальным техническим планом реализации, а не frozen source.
- `docs/core-engine-v1.2.md` является историческим source document; runtime, CSV и приемка используют текущий production profile из канонических docs/tasks.
- QR-коды содержат короткий opaque ID, который нельзя угадать по названию сцены; режим потребления задается в контенте.
- Сервер применяет автоматические тики от фактического старта акта.
- Offline act unlock поддерживается через server sync или мастерский `act_unlock_code`/QR, заранее включенный в snapshot и раскрываемый после старта акта и физического объявления акта на участке.
- QR/manual ID подчиняется жесткому physical-presence honesty policy: код можно запускать только у соответствующего prop/локации.
- PvE checks используют `single_d20`: одна проверка = один app-generated d20, все преимущества/помехи учитываются как логируемые modifiers.
- Cascade-prone offline rewards проходят `pending_master_approval` перед торговлей, ставкой, передачей лорду, финальной сводкой или влиянием на других игроков.
- PvP throttling является runtime-контуром: `pvp_tables`, queued challenges, режим `normal/limited/paused` и запрет новых вызовов после final lock.
- PvE, full Gwent PvP, trade_transfers, favorites lifecycle, reputation и бои лордов являются rule engines, а финал является master-led summary/export, а не автоматическим подсчетом победителей.

## Схема системы

```text
Телефоны ведьмаков и чародеек
  Godot 4 client
  player code -> snapshot -> offline PvE shell / online PvP prep -> event_queue
        |
        | sync в домашнем Wi-Fi
        v
Мастерский ноутбук
  FastAPI server
  SQLite authoritative state
  CSV importer / snapshot exporter
  rule engines / auto timers / backup jobs
  master web panel
        |
        | браузер по локальному IP
        v
4 ноутбука лордов
  lord web panels
```

## Implementation layout

Python/backend/tooling часть проекта использует `uv` как единственный основной
путь окружения. `pyproject.toml` хранит зависимости, `.python-version`
фиксирует Python 3.12, `.venv` создается через `uv sync`, а команды запускаются
через `uv run`. `requirements.txt` допускается только как legacy compatibility.

Ожидаемая раскладка реализации:

- `backend/witcher_larp/` - FastAPI app, SQLite access, CSV importer, snapshot
  exporter, rule engines, backup/recovery and API routes.
- `mobile/` - Godot 4 project, GDScript UI/runtime, export presets,
  `user://` persistence, QR/manual flow and offline `event_queue`.
- `backend/witcher_larp/web/` - static HTML/CSS/JS panels for master and lords
  served by FastAPI in Stage 1. No Node/React/Vite build is part of Stage 1
  unless a later task explicitly introduces it.
- `data/seed/` - editable runtime CSV seed/content packs.
- `data/snapshots/` - exported mobile snapshots with `snapshot_version`.
- `data/backups/` - SQLite/export backups before acts, final lock and manual
  backup actions.
- `tests/fixtures/` - valid and intentionally broken CSV/API/recovery fixtures.
- `scripts/` - local project automation wrappers such as TaskOS.

Stage 1 acceptance should prove this technical shape, not only gameplay logic:
`uv` command path, FastAPI/SQLite state, static browser panels, Godot mobile
shell, CSV import, snapshot export, event sync and paper recovery must all have
at least one seed-level vertical slice.

Stage 2B acceptance proves a different boundary: normal player/lord gameplay
must be operable through the Godot mobile app and browser panels. Swagger,
curl, raw API docs and direct SQLite edits remain developer diagnostics and do
not count as player/lord workflow acceptance after `TASK-050`.
Stage 2B also closes the mobile hardware gap for gameplay testing: Android APK
and iOS build/free provisioning smoke must pass on real devices before
`TASK-050`. Missing device proof is a blocker, not a deferred launch-risk
fallback. Paper fallback is tested as outage recovery only and does not replace
missing normal UI.

Stage 2B also has a visual/asset boundary in `TASK-067`. The lord panel uses an
original castle/city-development screen with an Olden Era-like building tree,
each capturable territory has a thematic fort image/card, personal PvP for
witchers/sorceresses uses a Gwent-like table grammar, the lord battle uses a
visually distinct 5x6 army board, and the plot map is an illustrated layer over
`venue_map_v1` for lord/count hero-army movement only. Lords do not use QR for
movement; witcher/sorceress QR/manual location flows do not require an online
map. These are data-bound UI treatments, not new rule engines: no production
screen may depend on copied third-party art, official card images, logos,
screenshots, GPS, cloud services, or internet access during the game.

### Task implementation contract

Implementation planning is synchronized through `tasks.json`, generated
TaskOS views and the canonical docs listed in `taskos.toml`. `tasks.json`
remains the canonical full dependency graph; `docs/active-tasks.md` is the
compact generated view for ordinary unfinished-work orientation; `progress.txt`
is the completion log and does not replace the graph. Every active
implementation task must expose technical work in visible TaskOS fields, not
only gameplay logic. For Stage 1 this means naming the expected module
boundary, data location, API group, fixture family and verification command.

Concrete defaults:

- backend modules live under `backend/witcher_larp/`;
- static master/lord panels live under `backend/witcher_larp/web/`;
- seed CSV files live under `data/seed/`;
- exported mobile snapshots live under `data/snapshots/`;
- backup artifacts live under `data/backups/`;
- valid/invalid import and recovery fixtures live under `tests/fixtures/`;
- mobile shell code lives under `mobile/`;
- project Python commands run through `uv run python`, with dependencies from
  `pyproject.toml` and environment setup through `uv sync`.

Ревизия пробелов от 2026-05-30 закрыта внутри основных документов: отдельной
архитектурной развилки не найдено, production profile, offline-first телефоны,
FastAPI/SQLite server, browser panels, local Wi-Fi, paper fallback и stage
gates согласованы. Исправленные пробелы: TaskOS-задачи получили видимые
technical notes, `taskos.toml` синхронизирован с основными каноническими
документами, а backend dependency messages используют `uv sync`/`uv run
python`, а не raw `pip`.

## Компоненты

### Godot mobile client

Клиент отвечает за:

- ввод предвыданного `player_code` и привязку устройства к персонажу;
- скачивание актуального `snapshot_version` в доме перед игрой;
- отображение персонажа, статов, описательной репутации и локальных ресурсов;
- отображение известных `personal_goals`, прогресса `goal_tracks` и раскрытых final hooks без hidden `goal_flags`;
- QR scan и manual QR-ID;
- offline act unlock через server sync или мастерский unlock code;
- offline PvE с app-generated single-d20 проверками, немедленным результатом и полным логом броска/modifiers;
- предупреждение physical-presence-only при QR/manual ID и локальный лог подтверждения игрока;
- локальный cooldown 30 минут на конкретный QR после провала;
- отображение `pending_master_approval` для наград, которые нельзя тратить/передавать до подтверждения;
- PvE-квесты в любых игровых зонах независимо от владельца территории;
- подготовку full Gwent PvP в online-зоне: challenge, deck/hand UI, rows, pass, round log и stake result;
- trade transfer UI в online-зоне: request, pending lock status, accept/decline и history;
- контур чародейки: мана, зелья, заклинания, consent-based фавориты;
- `event_queue` с `event_id`, `device_id`, `client_sequence`, `created_at`, payload и локальным статусом;
- sync statuses: `offline`, `pending`, `synced`, `sync_error`, `needs_master_review`.

Телефон не является глобальным источником истины. Он показывает локальный результат и отправляет проверяемый журнал серверу.

### Local server

Сервер отвечает за:

- авторитетное состояние игроков, доменов, территорий, армий, заказов, актов, репутации и финала;
- personal goals, goal_tracks, hidden goal_flags, final_hooks и final_summary;
- trade_transfers с pending locks и atomic owner changes;
- idempotent event intake;
- применение rule engines для PvE sync, full Gwent PvP, deterministic 5x6 lord battles, favorites lifecycle и репутации;
- act unlock validation, reward approval locks и severity-based review;
- PvP table allocation, queued challenges and throttle mode;
- CSV import, SQLite persistence и mobile snapshot export;
- автоматические тики дохода, маны, жетонов и окон армий;
- role/player code validation;
- master review, ручные коррекции и аудит причин;
- автобэкапы по расписанию и перед ключевыми переходами;
- restart recovery и post-game export.

### Master panel

Панель мастера показывает:

- состояние актов, таймеров и автоматических тиков;
- события, sync statuses и review queue;
- pending reward approvals и severity P0/P1/P2/P3;
- игроков, домены, цифровую карту территорий, армии и спорные действия;
- инструменты Короля/Света и Странника/Тьмы;
- точные значения репутации и журнал причин;
- hidden goal_flags, personal final hooks, final_summary evidence и trade transfer locks;
- ручные коррекции с обязательной причиной;
- backup/export status;
- финальную сводку.

### Lord panel

Панель лорда показывает только разрешенное состояние его владения:

- ресурсы, доход, влияние;
- weighted map, movement pool, цифровые территории, active army, reserve и гарнизоны;
- развитие резиденции;
- recruit market, building tree, raid tokens и raid effects;
- standings/diplomacy signals для союзов, заговоров и коалиций против лидера;
- публичные и адресные заказы, escrow награды;
- trade/order object conflicts, если они раскрыты владельцу;
- синхронные бои лордов;
- видимые последствия действий ведьмаков, чародеек и NPC.

### Visibility model

- Master: видит все состояние, точные репутации, логи причин и master corrections.
- Lord: видит свое владение, owner/bonus чужих территорий, свои гарнизоны, раскрытые чужие гарнизоны, заказы, бои и эффекты.
- Player: видит себя, публичное состояние, описательную репутацию и явно раскрытые эффекты.
- Hidden effects: могут применяться сервером сразу, но отображаются только ролям с правом видеть эффект.

## Данные и CSV

Перед runtime CSV используется authoring-only матрица контента. Она нужна мастерам и контент-мейкеру, не обязана попадать в приложение напрямую и проверяет разнообразие 40+ QR/PvE-квестов.

Минимальные поля матрицы: `quest_id`, акт, локация, тир, тип сцены, opaque `manual_id`, видимый hook, скрытая правда, основной/вторичный стат, `combat_profile`, `reward_budget`, `check_policy`, `modifier_sources`, `rarity`, `power_budget`, `act_cap`, `visibility`, `counterplay`, `qr_mode`, `honesty_policy`, `act_unlock_policy`, `reward_approval_policy`, `artifact_flags`, `reputation_flags`, `npc_flags`, `personal_goal_hooks`, `goal_flags`, `order_target`, `order_status_effect`, `trade_lock_behavior`, `final_hook`, `final_summary_category`, `pvp_throttle_tag`, `ops_checklist_tag`, `player_facing_handout_tag`, `role_load_tag`, `sync_outcome`, `failure_text`, `success_text`, тестовый статус.

Минимальный CSV-набор:

- `players.csv` - игроки, роли, production profile 4/4/5 + 2 NPC, статы, стартовые связи, `player_code`, XP/level curve profile, правило +1 stat per level и max stat 7.
- `role_tokens.csv` - игровые коды для мастеров и лордов.
- `personal_goals.csv` - видимые цели игроков, прогресс, role hooks, XP/reputation/final linkage.
- `goal_tracks.csv` - счетчики, чеклисты, состояния, пороги и видимость прогресса.
- `goal_flags.csv` - hidden/master-only флаги, источники, причины, unlock conditions и финальные последствия.
- `final_hooks.csv` - связь целей, артефактов, NPC-сделок, репутации и заказов с финальной процедурой.
- `domains.csv` - 4 владения, лорды, стартовые ресурсы, влияние.
- `buildings.csv` - именованное дерево резиденций: `building_id`, `branch`, `name`, `gold_cost`, `prerequisites`, `effects`, `unlock_tags`, `capacity_delta`, `raid_unlock`, `recruit_unlock`, `visual_tag`, `art_prompt`.
- `venue_map_profile.csv` или seed manifest - физические зоны участка, игровые названия, `no_play_excluded`, safety notes, online/offline hints и связь с map node IDs.
- `map_nodes.csv` - узлы стратегической карты: 4 стартовые резиденции в активном новом доме, нейтральные территории, города, форты, особые места; старый дом и соседний сарай помечаются как excluded и не становятся игровыми узлами; для лордского UI/печати фиксируются `visual_label`, physical landmark, route flavor and art prompt, без QR-привязок.
- `map_edges.csv` - связи узлов, movement point cost, terrain tags, travel/safety notes, route flavor и ограничения маршрута.
- `territories.csv` - цифровые территории, owner, tier, primary bonus type, defense profile, visibility, special effect and linked `fort_id`.
- `territory_forts.csv` - тематический форт каждой захватываемой территории: `fort_id`, `territory_id`, `theme`, `visual_tag`, `art_prompt`, `garrison_capacity`, optional `defense_bonus`; каждая территория получает одну оригинальную картинку/карточку форта.
- `movement_rules.csv` - default movement pool cap, refill interval, act modifiers.
- `recruit_markets.csv` - источники найма, refresh rules, hold slots, offer weights, required building/territory tags, reserve spawn.
- `raid_rules.csv` - raid subtree, token/gold costs, targets, defense/magic checks, debuff duration, optional loot effects `gold/cards/influence`.
- `mobs.csv` - мобы, HP, урон, награды, QR-ID, сценарий.
- `pve_scenarios.csv` - шаги PvE, проверки, тексты, переходы.
- `qr_objects.csv` - opaque QR/manual ID, тип, `qr_mode` (`unique_object`, `repeatable_scene`, `always_available_scene`), act availability, linked scenario/object, failure cooldown, manual-entry rate-limit policy и role load tags.
- `items.csv` - предметы, требования, бонусы.
- `cards.csv` - общий реестр card assets и conversion tiers; личные карты при передаче лорду конвертируются в army unit card по тиру.
- `gwent_cards.csv` - кастомные LARP-карты full Gwent: faction/tag, row, strength, unit/special/leader type, weather/decoy/scorch/horn/core ability, deck limits, rarity, power_budget, `visual_tag`, `art_prompt` и visibility.
- `gwent_decks.csv` - стартовые и валидируемые колоды: минимум 22 unit cards, до 10 special cards, 1 leader.
- `army_unit_cards.csv` - army unit cards; обязательны `unit_class`, `tier`, `count`, `attack`, `hp`, `defense`, `initiative`, `move_range`, `attack_range`, `tags`, `source`, `visual_tag`, `art_prompt`.
- `potions.csv` - зелья, эффекты, wholesale price, recommended resale band, stock policy и правила передачи/продажи чародейками.
- `spells.csv` - spell cards для заклинаний, ритуалов и интриг: мана, цели, окна применения, видимость, стратегические эффекты и counterplay; mana regen зависит от уровня чародейки и бонусов.
- `artifacts.csv` - редкие предметы, условия, финальное влияние.
- `rarity_rules.csv` - `Common/Uncommon/Rare/Legendary`, act caps, total caps, power budget, visibility/counterplay requirements.
- `orders.csv` - публичные/адресные заказы, escrow, object_id, trade/intercept flags, status machine, запрет двух активных заказов одного игрока на один объект и cap 2 public + 1 addressed active orders per lord.
- `trade_transfers.csv` - online-only transfer rules, pending lock timeout, asset types, two-confirmation flow and audit reasons.
- `acts.csv` - акты, стартовые параметры, доступность контента.
- `act_unlock_codes.csv` - offline unlock tokens/QR для Act 2, Act 3 и Final Act, раскрываемые мастером после старта акта.
- `physical_announcements.csv` или runbook-only manifest - кто и как громко объявляет старт Act 1/2/3/Final Act на участке.
- `auto_timers.csv` - 10-часовой fixed schedule, 3 сюжетных акта + финальный акт, буферы, final lock, тики дохода, hourly mana regen, 3 challenge tokens per act, movement pool refill и recruit market refresh.
- `pvp_tables.csv` / `pvp_throttle_rules.csv` - количество столов/слотов, queued behavior, режимы `normal/limited/paused`, max started mandatory matches per player per act.
- `npc_events.csv` - события Короля/Странника, адресность, полномочия Короля, сделки Странника, последствия.
- `anti_snowball_rules.csv` - пороги силы армии относительно средней и income multiplier, включая default штрафы 30% и 50%.
- `sorceress_alignment_rules.csv` или equivalent seed - `start_lord_support`, `independent_intrigue`, `double_game`, `declared_new_patron`, `open_betrayal`, `locked_magical_intent`, evidence requirements and final summary policy.
- `final_procedures.csv` - NPC-led tournament runbook, final lock behavior, optional final scene/station templates, personal epilogue hooks and export fields.
- `final_summary_rules.csv` - какие evidence, locks, NPC prices, personal hooks, order conflicts, artifacts and paper recovery events попадают в финальную сводку для мастеров.
- `reward_approval_rules.csv` - какие offline rewards являются `auto_approve_safe`, а какие требуют `master_approval_required`.
- `ops_checklists.csv` или runbook-only manifest - game-day setup, morning smoke, act unlock, QR/prop, PvP table and final station checks.
- `player_handouts.csv` или runbook-only manifest - общие правила, single-d20 checks, QR honesty policy, памятки ролей, PvP refusal/safety и NPC scene book.
- `xp_rules.csv` - XP за монстров, автоквесты, заказы, личные цели, значимые события, замедление левелинга и +1 stat per level.
- `reputation_rules.csv` - изменения Добро/Зло, диапазон -5..+5, старт 0, описательные состояния, видимость и threshold access.
- `backup_jobs.csv` - расписание и триггеры резервных копий, если нужно задавать их контентом.
- `paper_forms.csv` или runbook-only manifest - разрешенные бумажные формы: `paper_pve_result`, `paper_pvp_stake`, `paper_lord_action`, `paper_lord_battle`, `paper_order_resolution`, `paper_npc_deal`, `paper_final_evidence`.
- `visual_assets.csv` или asset manifest - original/local/generated UI assets for lord castle/building tree, territory forts, lord battle board, lord venue map, personal Gwent table/cards, buildings, units, artifacts, spells and potions; stores owner/source, license_status, file path, target surfaces and screenshot acceptance notes.

Импорт проверяет обязательные поля, уникальность ID, ссылки между CSV, валидность `qr_mode`, opaque/non-guessable manual IDs, валидность production profile, venue map exclusions, stat caps/level rules, `single_d20` check policy, отсутствие reroll-эффектов в PvE check rules, PvE scene HP/combat defaults, physical-presence honesty policy для QR/manual ID, act unlock coverage, physical announcement coverage, reward approval policy, reputation range/start/thresholds, mana regen source, spell/potion catalog минимумов и resale bands, full Gwent deck/card constraints, card conversion tier, PvP throttle/refusal rules, rarity caps, power budget, trade transfer lock rules, favorites caps/lifecycle, sorceress alignment values, order caps/status machine, 10-hour schedule, final summary inputs, player-facing handout coverage, валидность токенов и выдает читаемый отчет. Для лордского каталога importer дополнительно ловит циклы building tree, missing prerequisites, unknown `branch`, invalid `gold_cost`, bad `recruit_unlock`, invalid `unit_class`, invalid tier/capacity/range, territory without `territory_fort`, bad `garrison_capacity` и recruit offers, которые ссылаются на несуществующие здания, территории или карты.

## SQLite model

Core tables:

- `players`, `devices`, `player_codes`, `role_tokens`;
- `snapshot_versions`, `client_sync_state`;
- `acts`, `act_unlock_codes`, `auto_timers`, `timer_ticks`, `global_modifiers`, `pending_tick_rewards`;
- `domains`, `buildings`, `venue_map_profiles`, `map_nodes`, `map_edges`, `territories`, `territory_forts`, `movement_pools`, `territory_claims`;
- `armies`, `army_cards`, `army_reserves`, `garrisons`, `recruit_markets`, `recruit_offers`;
- `qr_objects`, `pve_scenarios`, `mobs`, `items`, `cards`, `potions`, `spells`, `artifacts`;
- `personal_goals`, `goal_tracks`, `goal_progress`, `goal_flags`, `final_hooks`;
- `gwent_cards`, `gwent_decks`, `gwent_matches`, `gwent_rounds`, `gwent_rows`, `gwent_play_logs`;
- `orders`, `escrow_ledger`, `objects_of_interest`, `reward_approvals`;
- `pvp_challenges`, `challenge_tokens`, `pvp_tables`, `pvp_throttle_state`, `trade_transfers`, `asset_locks`, `lord_battles`, `battle_logs`, `raid_rules`, `raid_attempts`, `raid_effects`, `anti_snowball_rules`;
- `events`, `event_reviews`, `master_corrections`, `paper_recovery_events`, transfer/favorite/goal/Gwent event payloads;
- `reputation_changes`, `npc_events`, `favorites` with primary/secondary role and max-favorite caps, `sorceress_alignment_changes`;
- `potion_market_offers`, `potion_market_rules`, `backup_jobs`, `backup_runs`, `final_procedures`, `final_summary`, `final_master_notes`, `final_results`.

Для первой версии достаточно repeatable migrations. База должна пересобираться из CSV для подготовки и сохранять игровое состояние после restart во время партии.

## Event model

Минимальное клиентское событие:

```json
{
  "event_id": "uuid",
  "player_id": "witcher_03",
  "device_id": "iphone_01",
  "type": "pve_completed",
  "payload": {
    "qr_id": "qr_grave_014",
    "scenario_id": "pve_grave_wraith",
    "result": "success",
    "roll_log": []
  },
  "created_at": 1770000000,
  "client_sequence": 42
}
```

Ответ сервера:

- `accepted` - событие применено;
- `rejected` - событие невозможно или невалидно;
- `needs_master_review` - событие сохранено и ждет мастера.
- `paper_recovered` - событие внесено мастером с бумажной формы после сбоя и проходит те же idempotency/conflict checks.

Повторный `event_id` не применяет эффект второй раз. `client_sequence` помогает находить пропуски, но не заменяет серверное состояние.

Ключевые event types v1:

- `pve_completed` - QR/PvE result, roll log, reward/cooldown and optional goal/reputation/final hook changes;
- `act_unlocked_offline` - ввод мастерского unlock code/QR для открытия акта на offline-телефоне;
- `physical_act_announced` - мастер/NPC отметил, что старт акта был объявлен голосом/сигналом в физическом мире;
- `honesty_violation_reviewed` - master ruling по подозрению на запуск QR/manual ID без физического присутствия;
- `reward_approval_requested`, `reward_approved`, `reward_corrected`, `reward_rejected` - master approval lifecycle для cascade-prone offline rewards;
- `goal_progress_changed` - изменение видимого `goal_track` или master-only `goal_flag`;
- `trade_transfer_requested`, `trade_transfer_accepted`, `trade_transfer_declined`, `trade_transfer_cancelled` - online-only transfer lifecycle and asset lock audit;
- `pvp_challenge_created`, `pvp_challenge_queued`, `pvp_throttle_changed`, `gwent_match_started`, `gwent_round_finished`, `gwent_match_finished`, `pvp_timeout_reviewed` - full Gwent PvP lifecycle;
- `lord_battle_started`, `lord_battle_turn_timeout`, `lord_battle_auto_resolved`, `lord_battle_finished` - deterministic 5x6 battle lifecycle;
- `favorite_requested`, `favorite_accepted`, `favorite_changed`, `favorite_removed` - consent-based favorites lifecycle;
- `sorceress_alignment_changed`, `magical_intent_locked`, `final_trial_scored` - чародейская лояльность/интрига, locked magical intent и финальные станции;
- `reputation_changed`, `npc_deal_recorded`, `final_master_note_recorded` - master-visible story/final evidence.
- `paper_recovered` - ручной ввод критичного бумажного события с `paper_form_id`, исходным типом события, operator, timestamp, recovery reason и `conflict_status`.

Paper recovery никогда не перетирает уже примененное цифровое событие молча. Если `paper_form_id`, asset/order/object state или временной порядок конфликтует с серверным состоянием, запись сохраняется в `event_reviews` и требует master ruling.

## Rule engines

### PvE

Телефон проводит PvE офлайн как один QR = один самостоятельный квест. Сцена поддерживает hook, 1-3 выбора/проверки, короткий бой на временном `scene_hp` при необходимости, награду, 30-минутный cooldown на конкретный QR после провала и полный roll/event log. Проверки используют `single_d20`: один app-generated d20 + стат + бонусы предметов/зелий/артефактов/магии + логируемые modifiers преимущества/помехи. PvE combat v1 хранит `player_scene_hp`, `scene_hp`, `combat_dc`, `scene_damage`, `round_limit`, `timeout_outcome`, `base_damage` и не создает постоянного здоровья персонажа. Владение территорией не блокирует прохождение ведьмачьих/чародейских QR-квестов. Будущие акты открываются только через server sync или master `act_unlock_code`, который валидируется при sync; code раскрывается после физического объявления акта. Сервер при sync проверяет QR, opaque/manual ID policy, режим потребления, physical-presence honesty policy, act availability, unlock source, player cooldown, заказной статус и reward approval policy. Cascade-prone rewards получают `pending_master_approval` и asset lock до решения мастера; `auto_approve_safe` награды могут применяться автоматически. Level-up grants +1 stat, max stat 7.

Проверяется после mobile shell и snapshot: QR/order scene -> act unlock -> checks/short combat -> app restart -> sync -> visible master event -> reward approval/cooldown 30 min/order outcome.

### Personal PvP

PvP валиден в доме/у лордов и считается как full Gwent по core rules Witcher 3 Gwent с кастомным LARP-набором карт. Сервер проверяет act, challenge token, ставку, участников, максимум 1 active challenge на игрока, deck minimum 22 unit cards, up to 10 special cards, leader, 10-card hand, up to 2 mulligan, 3 rows, pass, weather/decoy/scorch/horn/core abilities, round scoring and tie handling. Каждый ведьмак и чародейка получает 3 challenge tokens на сюжетный акт, токены копятся. Если challenge создан вне места боя, `pvp_challenges` хранит assigned battle zone и `30-minute PvP` окно на явку/старт; просрочка или отказ уходят в master review. PvP throttling проверяет доступный `pvp_table`, queued state, per-act started mandatory match cap и режим `normal/limited/paused`; после final lock новые вызовы запрещены без master override. После `gwent_match_started` отдельного лимита времени на матч нет. Личные карты не сгорают после раунда; при передаче лорду карта навсегда конвертируется по тиру в army unit card.

Проверяется после event intake и PvP engine: act token grant -> challenge -> active challenge cap -> pvp_table/queue/throttle -> stake lock -> assigned zone/window -> gwent_match_started -> mulligan -> best-of-3 rounds with tie/weather/decoy/scorch/horn -> result/stake transfer -> duplicate result ignored -> timeout/refusal review.

### Lord strategic map

Стратегическая карта лордов хранится как weighted graph. Venue map v1 фиксирует 4 резиденции в активном новом доме и исключает старый дом с соседним сараем через `no_play_excluded`; excluded zones не получают QR, territory ownership, orders, raids or battle routes. Каждая захватываемая территория имеет linked `territory_fort` с theme/art prompt и garrison capacity. Сервер валидирует route по `map_edges`, списывает movement points только за передвижение, пополняет movement pool каждые 30 минут до cap и не дает копить MP выше cap. Arrival на нейтральную или чужую территорию создает `territory_claim`; первый валидный claim переводит территорию в contested/in_battle и делает этот факт видимым всем лордам.

Владение землей требует гарнизон в тематическом форте. После победы атакующий должен оставить минимум одну выжившую army unit card в fort garrison; без гарнизона доход и основной бонус не активны. Owner может перебрасывать текущие army unit cards между активной армией и фортом, если активная армия находится на этой территории; transfer не тратит MP, но логируется, проверяет ownership, non-contested state, active battle lock, active army capacity, fort `garrison_capacity` и правило minimum garrison. Чужие гарнизоны скрыты от других лордов, но owner и primary bonus type видны. Если hourly income/influence tick попадает на ongoing claim, сервер создает `pending_tick_reward` и применяет его победителю боя ровно один раз без сдвига расписания.

Recruit market обновляется на hourly tick по зданиям, казармам и территориям. Купленные юниты попадают в reserve резиденции; active army забирает их только в резиденции. Building tree покупается за gold по prerequisites без act cap. Default catalog v1 содержит 4 ветки: казармы (`Training Yard`, `Barracks`, `Archery Range`, `Stables`, `Siege Yard`, `War Academy`), казна (`Market`, `Tax Office`, `Storehouse`, `Bank`, `Treasury Hall`), совет (`Notice Board`, `Envoy Hall`, `Map Room`, `Raid Office`, `War Council`), башня мага (`Mage Study`, `Alchemy Lab`, `Scrying Room`, `Wards`, `Ritual Chamber`). Anti-snowball rule режет income на 30% или 50%, если сила армии сильно или огромно выше средней. Diplomacy signals показывают мастеру/лордам поводы для союзов, заговоров и коалиций против лидера. Raid engine отделен от battle engine: raid token + gold -> target validation -> defense/magic check -> timed debuff and optional gold/cards/influence loot. Orders capped at 2 public + 1 addressed active orders per lord, and lord progression remains playable without witcher availability.

Проверяется после lord panels и act timers: movement refill to cap -> route spends MP -> contested claim visible -> neutral battle -> fort garrison required -> active army <-> fort transfer -> pending tick winner -> recruit refresh/hold/reserve -> building prerequisite -> anti-snowball 30/50 -> raid debuff/loot expiry.

### Lord battle

Лордские бои синхронные в веб-панелях. Сервер хранит deterministic поле 5x6, стартовые линии, отдельные клетки лордов, "руку" deployment из доступных army unit cards, карты-отряды как стеки юнитов, `attack`, `defense`, `hp`, `initiative`, `move_range`, `attack_range`, `tier`, `unit_class`, инициативу по раундам, одну ответку за раунд, 60s turn timer, HP лорда с min/max cap от размера выставленной армии, сдачу в свой ход, сжигание уничтоженных army unit cards и итог. Damage: `max(1, attack - defense + modifiers)`. V1 runtime также хранит `unit_power`, `deployed_army_power`, `domain_army_power`, `count_alive`, `wounds_on_front_unit`, deployment cap, hero targeting and auto-resolve inputs. Initiative tiebreaker: `initiative desc`, `tier desc`, deterministic battle seed. Движение ортогональное, ranged/siege используют attack_range и line of sight. Timeout = auto-defend/skip; repeated timeout = auto-resolve/master takeover. Этот engine используется для нейтральной обороны, гарнизонов и столкновения армий; рейды не запускают 5x6 бой. V1 поддерживает классы `infantry`, `guard`, `ranged`, `cavalry`, `heavy_siege`, `specialist`; маги и монстры остаются нейтралами, редкими спецэффектами, NPC/артефактами или влиянием чародеек, а не массовыми лордскими юнитами.

Нейтральной обороной по умолчанию управляет deterministic server AI, мастер может подключиться к бою. Чужая земля защищается гарнизоном плюс active army владельца, если она находится на этой территории. Проигравшая активная армия с выжившими картами отступает на предыдущую свою территорию или в резиденцию.

Проверяется после lord panels и battle engine: neutral AI battle/master takeover <=10 min -> two browser sessions -> lord-vs-lord <=20 min -> 5x6 deployment -> initiative round -> 60s timeout -> repeated-timeout auto-resolve -> surrender/unit wipe/hero HP result -> persisted losses -> retreat/capture/garrison -> restart check.

### Sorceress magic

Spell card применяется сразу, если хватает маны и цель валидна. Сервер списывает ресурс, применяет эффект и решает видимость по role rules. Мана восстанавливается hourly tick от уровня чародейки и бонусов. V0 spell catalog должен покрывать T1-T4 hint/boost/reveal/ward/curse/ritual эффекты без прямого вмешательства в lord battle. Potion market принадлежит чародейскому контуру: только чародейки покупают зелья у NPC/магического рынка по wholesale price (`8g/18g/40g` для Common/Uncommon/Rare roles), после чего могут продать, обменять или подарить их ведьмакам/фаворитам через `trade_transfers`; resale bands `12-15g/25-30g/55-70g` логируются для баланса. По умолчанию 1 potion на сцену. Ритуалы и интриги используют тот же spell-card contract с counterplay и логом. Favorites support consent-based primary/secondary slots: max 1 primary and 1 secondary per sorceress, max 2 sorceresses per favored player, change at most 1 per act, no passive runtime bonus unless a spell/potion/NPC effect explicitly targets `favorite`. Sorceress alignment хранит поддержку стартового лорда, самостоятельную интригу, двойную игру, нового патрона или открытое предательство с evidence для финала.

Проверяется после sorceress engine: wholesale potion buy -> transfer/sell/gift -> favor/spell -> mana spent -> effect visible to allowed roles.

### NPC and final procedures

Король/Свет и Странник/Тьма являются event engines с живой мастерской сценой и цифровым следом. Король может утверждать политические решения, судить споры, выдавать поручения и influence. Странник/Дьявол хранит сделки, скрытые цены, темные артефакты и альтернативные пути к победе. Репутация хранит numeric range -5..+5, start 0 and thresholds: Тьма, Запятнанный, Нейтральный, Добро, Свет. Runbook делит 2 NPC-мастеров: Король/порядок/admin-review и Странник/сделки/полевые вмешательства с fallback-перекрытием; оба играют roleplay first, а admin-review закрывается в буферах, кроме severity P0/P1 событий. P0 означает "остановить и решить сейчас", P1 - "решить до следующего акта или финала". Final procedure содержит NPC-led финальный турнир, но не автообъявляет победителя: система готовит `final_summary` для мастеров, включая evidence по ролям, missing locks, pending disputes, NPC prices, locked magical intent, personal hooks, artifacts, orders, reputation and paper recovery. Final Act использует 7:30-9:30 runbook: final lock, 1-3 выбранные турнирные сцены/станции, P0/P1 review, master ruling, personal epilogues and export snapshot.

Проверяется после NPC/final runtime: King ruling -> influence/log -> Stranger deal -> hidden price/final flag -> severity review -> weighted lord/witcher/sorceress inputs -> final act timeboxes -> export.

### Auto timers

Таймеры стартуют от фактического старта акта. Сервер сам применяет доход, ману, жетоны и окна армий, логирует tick, готовит act unlock state/code и позволяет мастеру корректировать исключения.

Проверяется после act engine: start act -> wait/trigger due tick -> persisted tick -> visible state change.

## API MVP

Начальные endpoint-группы:

- `GET /health`
- `POST /api/auth/player-code`
- `POST /api/auth/role-token`
- `GET /api/content/snapshot`
- `POST /api/events/sync`
- `GET /api/events`
- `POST /api/events/{event_id}/review`
- `GET /api/players/{player_id}/goals`
- `POST /api/master/goals/{goal_id}/progress`
- `GET /api/master/state`
- `POST /api/master/acts/{act_id}/start`
- `GET /api/master/acts/{act_id}/unlock-code`
- `POST /api/master/reward-approvals/{approval_id}`
- `POST /api/master/pvp-throttle`
- `POST /api/master/corrections`
- `POST /api/master/npc-events`
- `GET /api/master/final-summary`
- `GET /api/lords/{lord_id}/state`
- `POST /api/lords/{lord_id}/move`
- `POST /api/lords/{lord_id}/garrisons/transfer`
- `POST /api/lords/{lord_id}/buildings`
- `POST /api/lords/{lord_id}/recruit`
- `POST /api/lords/{lord_id}/raids`
- `POST /api/lords/{lord_id}/orders`
- `POST /api/lord-battles`
- `POST /api/pvp/challenges`
- `GET /api/pvp/tables`
- `POST /api/pvp/challenges/{challenge_id}/start`
- `POST /api/pvp/matches/{match_id}/rounds`
- `POST /api/pvp/matches/{match_id}/finish`
- `POST /api/trade-transfers`
- `POST /api/trade-transfers/{transfer_id}/accept`
- `POST /api/trade-transfers/{transfer_id}/decline`
- `POST /api/favorites`
- `POST /api/favorites/{favorite_id}/accept`
- `POST /api/backups/run`

Auth первой версии: локальные игровые коды, выданные мастером. Внешние identity providers не нужны.

## Backup и recovery

Сервер делает autobackup:

- по расписанию во время игры;
- перед стартом/сменой акта;
- перед финальным актом;
- вручную из мастерской панели.

Backup должен включать SQLite-файл или export, import report, snapshot version и event log. Restart recovery считается успешным, если после перезапуска видны акты, события, репутация, лорды, таймеры и финальная сводка.

Immediate paper fallback включается для конкретного критичного действия сразу, если его нельзя провести в приложении, на сервере или через локальную сеть. Бумага покрывает `paper_pve_result`, `paper_pvp_stake`, `paper_lord_action`, `paper_lord_battle`, `paper_order_resolution`, `paper_npc_deal` и `paper_final_evidence`. Если падает Wi-Fi или сервер, лорды продолжают через бумажные листы владения, армии, заказов, рейдов и боев вместе с ведьмаками и NPC-мастерами. После восстановления мастер вводит формы в Admin Studio, сервер создает `source=paper_recovered`, требует `paper_form_id`, source form type, operator, timestamp и recovery reason, затем применяет события по timestamp через обычные idempotency/resource/ownership checks или отправляет конфликт в review. Цифровые события с тем же объектом, ставкой, заказом, территорией, боем или QR не перезаписываются без явного master ruling.

## Проверки

- Unit tests: PvE, offline act unlock, reward approval locks, +1 stat level-up, personal_goals/goal_flags visibility, full Gwent deck/round/tie/effects, PvP challenge tokens/window/refusal/tie/throttle, trade_transfers lock/accept/decline, deterministic lord battle 60s timeout/auto-resolve, fort garrison transfer/capacity/minimum rules, escrow, order object conflict and order cap, cooldown 30 min, QR consumption, auto timers, anti-snowball, reputation -5..+5 thresholds, hourly mana, favorites lifecycle and potion economy.
- Content tests: authoring matrix coverage, 40 QR slots with Act 1/2/3 = 12/14/14, 15+ always-available/repeatable and 25+ unique objects, `repeatable_scene`/`always_available_scene`/`unique_object` mix, opaque manual IDs, PvE tiers 1-4, PvE scene HP defaults, reward budgets, act unlock policy, reward approval policy, rarity caps, personal goal hooks, custom Gwent cards, unique objects, artifact visibility, spell/potion minimum catalog, NPC deal flags and final_summary inputs.
- Import tests: валидные seed CSV и ошибочные CSV.
- API integration tests: idempotent events, codes, snapshot, act unlock, reward approvals, review, timers, PvP throttle, backups.
- Recovery tests: `paper_recovered` import for QR/PvE, PvP stake, lord action, lord battle, order resolution, NPC deal and final evidence; duplicate/conflicting recovery must go to review.
- Browser smoke: master panel, 4 lord panels, синхронный lord battle.
- Device smoke: player code, snapshot download, QR/manual input, offline PvE, restart, sync retry.
- UI-first smoke after `TASK-050`: Android/iOS mobile gameplay UI, lord action UI with valid illustrated `venue_map_v1`, personal PvP/Gwent UI, Admin Studio paper recovery/corrections and final summary without Swagger for player/lord steps.
- Visual/reference smoke after `TASK-067`/before `TASK-050`: screenshots for lord castle/city-development screen with Olden Era-like building tree, thematic territory forts, lord battle board, personal Gwent table and lord venue map; check readability, state labels, data bindings, visual distinction between PvP surfaces and IP-safe original/local assets.
- Non-PvE hardening before `TASK-050`: real-device install/launch/connect/snapshot/restart/sync, 4 lord panels, lord map audit, personal Gwent, orders/trade, sorceress potions/spells/favorites/alignment, Admin recovery and no unresolved P0/P1/blocking P2 defects.
- Full rehearsal: мастерский ноутбук, 4 лордских ноутбука, реальные телефоны, домашний Wi-Fi, 15-person profile, 10-hour fixed schedule, 9 mobile-role load/idle risk, NPC-master load, order pressure, offline act unlock, pending reward approval, full Gwent volume/throttle, trade conflicts, favorites impact, visual/readability proof, master-led final summary, final lock and game-day ops checklist.
