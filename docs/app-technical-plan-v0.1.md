# Witcher LARP - технический план приложения v0.1

## Назначение документа

Этот документ описывает актуальную техническую реализацию приложения для однодневной LARP-игры на участке. Он больше не является frozen source: при изменении технической каноники его нужно обновлять вместе с `docs/PRD.md`, `docs/architecture.md`, `docs/game-mechanics.md`, `docs/roadmap.md` и `tasks.json`. Историческим исходником остается только [core-engine-v1.2.md](core-engine-v1.2.md), если пользователь отдельно не попросит его менять.

Task queue reading contract: use `docs/active-tasks.md` or `uv run python scripts\taskctl.py ready` for ordinary orientation; keep `tasks.json` as the canonical full dependency graph; keep `progress.txt` as the completion log.

Цель плана - зафиксировать оптимальный путь реализации с учетом ограничений: Wi-Fi только в доме, игроки ходят по участку с телефонами, нужно поддержать iOS и Android, лорды играют с ноутбуков, а мастерский ноутбук держит локальный сервер.

Production profile текущей игры: 15 человек всего = 13 игроков + 2 NPC-мастера. Игроки: 4 лорда, 4 гибридные мобильные чародейки и 5 свободных ведьмаков.

## Текущая игровая каноника для реализации

Техническая реализация должна поддерживать не только MVP-вертикаль, а playable 10-hour full-game build:

- fixed schedule: 0:00-0:30 registration/snapshot, 0:30-2:15 Act 1, 2:15-2:30 buffer, 2:30-4:45 Act 2, 4:45-5:00 buffer, 5:00-7:15 Act 3, 7:15-7:30 final lock, 7:30-9:30 Final Act, 9:30-10:00 debrief/export/emergency buffer;
- offline act unlock: телефоны открывают новый акт через sync в доме или мастерский `act_unlock_code`/QR, раскрываемый только после старта акта и физического объявления акта голосом/криком на участке;
- QR/manual ID имеет жесткое правило честности: запуск сцены разрешен только при физическом присутствии у prop/локации;
- PvE checks используют `single_d20`: одна проверка = один app-generated d20, а преимущества/помехи/зелья/магия/предметы считаются как системные modifiers с логом;
- NPC-мастера работают roleplay first; admin-review закрывается в буферах, кроме P0/P1 блокеров;
- P0/P1 означают срочность review: P0 - остановить и решить сейчас, P1 - решить до следующего акта или финала;
- `personal_goals`, `goal_tracks`, `goal_flags`, `final_hooks`: игрок видит известные цели и прогресс, мастер видит hidden flags;
- QR modes: `unique_object`, `repeatable_scene`, `always_available_scene`; full pack 40+ QR/PvE, минимум 15 repeatable/always-available и 25+ unique objects;
- content matrix V0: Act 1 = 12 слотов, Act 2 = 14, Act 3 = 14; каждый акт покрывает monster hunt, investigation, moral choice, puzzle/check, order object, artifact/rare card, sorceress magic hook и lord strategic hook;
- V0 balance defaults: XP thresholds `0,10,25,45,70,100,135,175,220,270`, PvE DC T1/T2/T3/T4 = `10-12/13-15/16-18/19-21`, rewards T1/T2/T3/T4 = `10g/20g/35g/55g` и `3-5/6-9/10-14/15-20XP`;
- failure cooldown 30 минут на конкретный QR для конкретного игрока;
- cascade-prone offline rewards получают `pending_master_approval` и не могут быть потрачены/переданы/засчитаны в финал до мастерского подтверждения;
- full Gwent personal PvP по core rules Witcher 3 Gwent с кастомными LARP-картами, 30-minute PvP window на явку/старт и no match time limit после старта;
- personal PvP soft cap: целевой матч 20 минут, с 25-й минуты мастер может ускорить сцену, назначить финальный раунд или отправить спор в review;
- PvP refusal/safety table: активная сцена, safety stop, небезопасный путь, форс-мажор и перегруз столов переводят вызов в deferred/review, а не в автоматическое наказание;
- PvP throttling: default 2 `pvp_tables`, queued challenges, max 2 started mandatory matches per player per act без master approval, режимы `normal/limited/paused` и запрет новых вызовов после final lock;
- online-only `trade_transfers`: two confirmations, pending asset lock, atomic owner change, audit log;
- venue map v1: 4 резиденции находятся в активном новом доме; старый дом и соседний сарай исключены из игры; лордский weighted graph использует беседки-крепости, поля, деревни-сараи, колодец-город ресурсодобычи, испанский уголок-город магии, двухэтажный сарай-город науки, леса, озера, болото и горы;
- territory forts v1: каждая захватываемая территория имеет тематический форт с одной original/local/generated картинкой/карточкой, garrison capacity и transfer active army <-> fort, если активная армия находится на своей не-contested территории;
- visual direction v1: `TASK-067` фиксирует IP-safe лордскую поверхность `/lords/home` как главный экран замка/выбранной территории, максимально близкий к принятому Heroes-like референсу: full-screen background, thin top resource strip, left circular action dock, bottom-left minimap, bottom-center active-army/garrison/recruit lanes, bottom-right act plaque and MP semicircle. Захваченные территории используют тот же UI с другим фоном, локальным доходом, гарнизоном, накопительным наймом и минимальным деревом построек; если герой-армия не в выбранной локации, верхняя линия армии пустая и locked. Отдельно остаются illustrated fantasy strategy map для лордского `venue_map_v1`, thematic territory forts/cards, Witcher 3 Gwent-like table grammar для личного PvP ведьмаков/чародеек и visually distinct 5x6 lord battle board; это layout/interaction references only, все production assets должны быть original/local/generated, без копирования официальных артов, логотипов, скриншотов или gallery images;
- map tech rule: иллюстрированная карта участка является UI-слоем поверх `map_nodes`/`map_edges` и route costs для лордского графа перемещения героев/армий; лорды не используют QR, а QR/manual physical-presence confirmation относится к ведьмакам и чародейкам на локациях и не требует online-карты;
- deterministic lord battle 5x6: `attack`, `defense`, `hp`, `initiative`, `move_range`, `attack_range`, `tier`, `unit_class`, damage `max(1, attack - defense + modifiers)`, 60s turn timer, auto-resolve;
- lord battle appendix: V1 фиксирует `unit_power`, `deployed_army_power`, `domain_army_power`, partial stack wounds, deployment caps, line of sight, hero targeting, neutral AI priority and auto-resolve score;
- lord defaults: старт `80g`, base income `25g/hour`, territory income T1/T2/T3 = `8/14/22g`, building cost T1/T2/T3/T4 = `40/75/120/180g`, lord HP `clamp(30 + floor(deployed_army_power / 10), 35, 70)`, anti-snowball `>=130%/-30%` и `>=170%/-50%`;
- favorites lifecycle: consent, max 1 primary + 1 secondary per sorceress, max 2 sorceresses per favored player, change 1 per act, no passive runtime bonus by default;
- sorceress alignment: стартовая связь с лордом не запрещает интригу, двойную игру, нового патрона или открытое предательство; финал считает evidence фактической лояльности;
- mana defaults: maximum mana `6 + level`, hourly regen `2 + floor(level/3) + bonuses`, spell cost T1/T2/T3/T4 = `1/2/3/4`;
- spell/potion V0 catalog: T1-T4 spell roles для hint/boost/reveal/ward/curse/ritual, potion wholesale `8g/18g/40g`, resale bands `12-15g/25-30g/55-70g`, стартовое золото ведьмаков `20g`, чародеек `30g`, max 1 potion per scene by default;
- rarity model: `Common/Uncommon/Rare/Legendary`, rare Gwent cards 6 всего и максимум 2 на акт, artifacts 8 всего, legendary artifacts 2 всего не раньше Act 2, plot/strategic keys 6 всего;
- reputation thresholds: `-5..-4` Тьма, `-3..-2` Запятнанный, `-1..+1` Нейтральный, `+2..+3` Добро, `+4..+5` Свет;
- финал содержит NPC-led турнир: система готовит `final_summary`, missing evidence, locks, NPC prices, locked magical intent, personal hooks и export, но сетку, веса evidence, спорные трактовки, победителей и объявления решают NPC-мастера;
- Final Act идет как master-led процедура 7:30-9:30: final lock, NPC-led турнир с 1-3 выбранными сценами/станциями, P0/P1 review, master ruling, личные эпилоги и export snapshot;
- immediate paper fallback: если конкретное критичное действие нельзя провести в приложении/сети, мастер сразу фиксирует его на бумаге и после восстановления вносит как `source=paper_recovered`; если падает Wi-Fi или сервер, лорды продолжают играть на бумаге с ведьмаками через листы владения, армии, заказов, рейдов и боев.
- game-day ops checklist обязателен: devices, Wi-Fi, local IP, snapshot, act unlock codes, physical act announcement, QR/manual IDs, props, player-facing handouts, paper forms, safety zones, PvP tables, final stations/staffing and morning smoke.

## Ограничения площадки

- Игра проходит один день на участке около 70 соток.
- Wi-Fi есть только в доме; интернет во время игры не должен быть обязательным.
- В доме есть мастерский ноутбук с сервером и 4 отдельных ноутбука лордов.
- Игроки вне дома используют телефоны и должны иметь возможность играть офлайн.
- Нужно поддержать и Android, и iOS; iPhone будет много.
- Apple Developer Program пока не покупаем.
- Mac доступен примерно на неделю до игры.
- Установочную репетицию нужно провести за 3-5 дней до игры.
- Отдельный роутер пока не добавляем; домашний Wi-Fi нужно проверить заранее.
- Контент первой сборки минимальный, затем расширяется таблицами.

## Итоговая архитектура

Оптимальная архитектура для первой версии:

```text
Телефоны игроков iOS/Android
  Godot 4 mobile client
  offline-first состояние + event_queue
        |
        | синхронизация при возвращении в Wi-Fi
        v
Мастерский ноутбук в доме
  локальный сервер Python/FastAPI + SQLite
  веб-панель мастера
        |
        | браузер по локальному Wi-Fi
        v
4 ноутбука лордов
  веб-панель лорда
```

### Godot mobile client

Мобильное приложение игроков делается на Godot 4.

Клиент отвечает за:

- ввод `player_code`, скачивание snapshot и отображение персонажа;
- локальное сохранение состояния в `user://`;
- отображение известных personal_goals, goal_tracks, описательной репутации и скрытых от игрока final hooks только после раскрытия;
- сканирование QR или ручной ввод QR-ID;
- подтверждение physical-presence-only перед запуском QR/manual ID;
- ввод мастерского act unlock code/QR для открытия следующего акта вне Wi-Fi;
- PvE-бои с QR modes `unique_object`, `repeatable_scene`, `always_available_scene`;
- отображение locked/pending статуса для наград, которым нужен master approval;
- фиксацию full Gwent PvP-вызовов и проведение матча в online-зоне;
- trade transfer UI: создать, подтвердить, отклонить, увидеть pending lock;
- favorite consent UI для чародеек и фаворитов;
- локальную очередь событий `event_queue`;
- синхронизацию с сервером, когда телефон снова оказался в домашнем Wi-Fi;
- понятный статус: `offline`, `pending sync`, `synced`, `sync error`.

### Локальный сервер

Сервер запускается на мастерском ноутбуке в доме.

Рекомендуемый стек:

- Python;
- FastAPI;
- SQLite;
- простой HTML/JS web UI для лордов и мастера.

Python/backend/tooling окружение управляется через `uv`: `pyproject.toml`
является каноном зависимостей, `.python-version` фиксирует Python 3.12, а
локальная `.venv` создается и обновляется командой `uv sync`. Ручной
`python -m venv` и прямой `pip install -r requirements.txt` не являются
основным путем разработки.

Текущий runtime scaffold:

- пакет приложения: `backend.witcher_larp`;
- bootstrap SQLite: `backend/witcher_larp/database.py`;
- FastAPI factory и endpoint `/health`: `backend/witcher_larp/app.py`;
- команда запуска на мастерском ноутбуке после `uv sync`: `uv run python -m backend.witcher_larp`;
- переменные окружения: `WITCHER_LARP_HOST`, `WITCHER_LARP_PORT`, `WITCHER_LARP_DB`;
- зависимости локального backend: `pyproject.toml`; `requirements.txt` остается только legacy-совместимостью.

Рабочая раскладка реализации:

- `backend/witcher_larp/` - FastAPI, SQLite, importer, snapshot exporter, API,
  rule engines, backup/recovery;
- `mobile/` - Godot 4 project, GDScript mobile UI/runtime, export presets,
  offline `event_queue`, QR/manual input and `user://` persistence;
- `backend/witcher_larp/web/` - static HTML/CSS/JS панели мастера и лордов,
  served by FastAPI without Node build tooling in Stage 1;
- `data/seed/` - editable runtime CSV;
- `data/snapshots/` - exported mobile snapshots;
- `data/backups/` - SQLite/export backups;
- `tests/fixtures/` - valid and broken CSV/API/recovery fixtures.

После `TASK-050` функциональная приемка игроков и лордов идет UI-first:
ведьмаки/чародейки тестируют мобильное приложение, лорды - браузерные action
панели, мастера - Admin Studio. Swagger, curl и ручные API остаются
developer diagnostics и не считаются штатным пользовательским путем.
Перед кодингом этих поверхностей `TASK-045` должен создать UI blueprint, а не
только общую матрицу намерений: `docs/ui/stage2b-screen-map.md`,
`docs/ui/stage2b-flow-map.md`, `docs/ui/stage2b-api-map.md` и
`docs/ui/stage2b-state-matrix.md`. В них каждый экран ведьмака, чародейки,
лорда, мастера/NPC и shared auth/sync/error state связывается с read source,
mutation endpoint или offline queued event, payload/response, visibility
boundary и итоговым состоянием UI. Если экрану нужен Gwent/trade/favorite/review
state, locked asset, hidden-data redaction или final-lock state без понятного
endpoint/snapshot field, это blocker соответствующей UI-задачи, а не локальная
догадка клиента.

Перед реализацией `TASK-046`-`TASK-049` `TASK-067` должен дать визуальную
приемку будущей картинки: `prototypes/stage2b/` или Open Design artifact,
`docs/ui/stage2b-visual-acceptance.md` и
`docs/ui/stage2b-visual-asset-manifest.md`/`visual_assets.csv`. Codex может
делать такой дизайн прямо в локальном прототипе/Open Design; image generation
используется для original raster assets вроде замков, фортов, карт и портретов
карт, а текстовые UI-макеты остаются code/Open Design, чтобы подписи и состояния
были точными.
Для Stage 2B это жесткий gate: Android APK и iOS build/free provisioning должны
быть установлены и проверены на реальных телефонах, включая camera QR scan
физического QR и ручной QR-ID fallback, 4 лордские панели должны
одновременно пройти browser smoke, а весь gameplay без generated/full PvE
content должен проходить через UI. Бумажный fallback проверяется как outage
recovery, но не считается заменой отсутствующего штатного UI.

Сервер отвечает за:

- авторитетное состояние партии;
- прием событий от телефонов;
- валидацию наград, personal goals, goal_flags, full Gwent PvP-вызовов, trade_transfers, заказов и спорных действий;
- act unlock validation, reward approvals, PvP tables/throttle и severity review;
- состояние лордов, владений, рынка, заказов, армий и боев;
- deterministic lord battle 5x6, master-led final summary, reputation thresholds и favorites lifecycle;
- журнал событий;
- мастерские ручные корректировки;
- раздачу веб-панелей по локальному Wi-Fi.

### Веб-панели лордов и мастера

Лорды не устанавливают отдельное приложение. Каждый лорд открывает локальный адрес сервера в браузере на своем ноутбуке.

Панель лорда должна показывать:

- владение;
- ресурсы;
- армию;
- гарнизоны;
- карту территорий;
- рынок;
- заказы;
- рейды;
- бои лордов.

Панель мастера должна показывать:

- всех игроков;
- очередь событий;
- состояние синхронизации;
- спорные события;
- ручную выдачу наград;
- запуск актов;
- выдачу act unlock code/QR после старта акта;
- подтверждение или correction pending reward approvals;
- глобальные объявления;
- инструменты Короля и Странника;
- аварийную коррекцию баланса.

## События и синхронизация

Телефон не пытается быть источником глобальной истины. Он только фиксирует локальные действия и отправляет их серверу.

Минимальная структура события:

```json
{
  "event_id": "uuid",
  "player_id": "witcher_03",
  "device_id": "iphone_ostro_01",
  "type": "pve_completed",
  "payload": {},
  "created_at": 1770000000,
  "client_sequence": 42,
  "sync_status": "pending"
}
```

Правила:

- `event_id` уникален и защищает от повторного применения события.
- `client_sequence` задает порядок действий на одном устройстве.
- `created_at` нужен для логов и разборов, но не должен быть единственным источником истины.
- Сервер отвечает статусом: `accepted`, `rejected`, `needs_master_review`.
- После успешной синхронизации клиент оставляет событие в локальном логе до конца игры.
- Если сервер недоступен, клиент продолжает игру и повторяет синхронизацию позже.

QR-конфликты по уникальным PvE в базовой модели не должны возникать: если игрок победил моба, он забирает физический QR с локации; если проиграл, оставляет QR на месте и получает личный cooldown 30 минут.

## Боевые системы

Нужно делать отдельные боевые движки для трех типов боя, но с общими примитивами:

- HP;
- урон;
- проверки;
- карты;
- эффекты;
- ставки;
- награды;
- текстовый лог;
- результат боя.

### PvE

PvE - пошаговый нарративный бой, не автобой.

В первой версии нужно реализовать:

- визуальную карточку моба;
- временный `scene_hp` игрока и HP врага/опасности сцены;
- урон;
- проверки `app-generated single_d20 + стат + бонусы + логируемые modifiers`;
- выбор действий;
- ветки успеха и провала;
- награду при победе;
- cooldown при поражении;
- запись результата в `event_queue`.

PvE combat v1 не использует постоянное здоровье персонажа. Для каждой сцены клиент считает временный `player_scene_hp = 6 + level + armor_or_ward_bonus`, минимум 7; после исхода сцены это HP сбрасывается. Враг/опасность сцены имеет `scene_hp`, `combat_dc`, `scene_damage`, `round_limit` и `timeout_outcome`. Default `scene_hp` по тирам: T1 = 6, T2 = 10, T3 = 14, T4 = 18; default `round_limit` = 5. Атака или опасное действие - это app-generated `single_d20` против `combat_dc`; успех наносит `base_damage`, каждые полные 5 очков margin дают +1 damage, провал наносит `scene_damage` или двигает сцену к плохому исходу. Зелье или подготовка дают только логируемый modifier/снятие помехи, без reroll.

Для MVP лучше начать с собственного JSON/CSV-формата сценариев, а Dialogic рассматривать позже. Это снижает риск мобильной сборки и ускоряет импорт контента из таблиц.

### Личный PvP

Личный PvP нужен для ведьмаков и чародеек.

Первая версия реализует full Gwent по core rules Witcher 3 Gwent с кастомным LARP-набором карт:

- фиксирует участников;
- проверяет жетоны вызова;
- проверяет максимум 1 active challenge на игрока;
- фиксирует ставку;
- проверяет колоду: минимум 22 unit cards, до 10 special cards, 1 leader;
- выдает 10-card hand и до 2 mulligan;
- поддерживает 3 rows, pass, best-of-3 rounds, tie = оба теряют раунд;
- поддерживает weather, clear weather, decoy, scorch, commander's horn и core abilities;
- назначает `30-minute PvP window` на явку/старт матча;
- проверяет `pvp_tables`, queued challenges, per-act mandatory match cap и throttle mode;
- после старта не ставит отдельный match time limit, но пишет timestamps для Stage 5 volume report;
- проводит бой в доме/у лордов в online-зоне;
- сохраняет лог;
- применяет результат к серверному состоянию.

Вне дома телефон может только зафиксировать вызов через QR/код. Сам бой проводится в доме, чтобы не плодить спорные офлайн-результаты. Timeout, отказ, некорректная ставка или спорная ничья уходят в master review.

Отказ от PvP обрабатывается по refusal/safety table: активная сцена или небезопасный путь дают deferred window, safety/comfort stop ставит матч на паузу без наказания, декоративные вызовы могут быть ограничены throttle, а игнор валидного вызова без причины решается мастером в review.

### Бои лордов

Бой лордов - отдельный карточно-стратегический режим.

Первая версия должна поддержать:

- героя лорда с HP;
- руку карт;
- карты-отряды;
- базовые параметры отряда: `attack`, `defense`, `hp`, `initiative`, `move_range`, `attack_range`, `tier`, `unit_class`;
- инициативу с tiebreaker `initiative desc`, `tier desc`, deterministic battle seed;
- атаку;
- damage `max(1, attack - defense + modifiers)`;
- ортогональное движение, attack_range и line of sight;
- 60s turn timer, timeout auto-defend/skip и repeated-timeout auto-resolve;
- уничтожение карт;
- победу по HP героя или уничтожению армии;
- текстовый лог боя.

Красивые анимации и сложные эффекты можно отложить, но правила боя должны быть deterministic и близки к финальной задумке. Neutral target должен закрываться за <=10 минут, lord-vs-lord за <=20 минут.

## Контент и CSV

Контент готовится таблицами, а не руками в коде.

Минимальные CSV для первой версии:

- `players.csv` - игроки, роли, production profile 4/4/5 + 2 NPC, стартовые параметры, level rules.
- `personal_goals.csv`, `goal_tracks.csv`, `goal_flags.csv`, `final_hooks.csv` - сюжетные цели, прогресс, hidden flags и финальные связи.
- `mobs.csv` - монстры, HP, урон, награды, QR-ID, сценарий.
- `pve_scenarios.csv` - шаги PvE-сцен, проверки, тексты, переходы.
- `qr_objects.csv` - QR-ID, `qr_mode`, act availability, linked scenario/object, cooldown.
- `act_unlock_codes.csv` - offline unlock codes/QR для Act 2, Act 3 и Final Act.
- `physical_announcements.csv` или runbook manifest - кто и как объявляет старт каждого акта в физическом мире.
- `reward_approval_rules.csv` - `auto_approve_safe` и `master_approval_required` для offline rewards.
- `items.csv` - предметы и бонусы.
- `cards.csv` - общий реестр карт и conversion tiers.
- `gwent_cards.csv`, `gwent_decks.csv`, `gwent_matches.csv` - full Gwent карты, колоды, матчевые fixtures.
- `pvp_tables.csv`, `pvp_throttle_rules.csv` - столы, очереди, throttle modes and final lock behavior.
- `army_unit_cards.csv` - карты-отряды лордов с параметрами 5x6.
- `territories.csv`, `territory_forts.csv`, `map_nodes.csv`, `map_edges.csv`, `movement_rules.csv` - территории, тематические форты/гарнизонные capacity, граф, доходы, защита, владелец.
- `orders.csv` - шаблоны заказов, escrow, order caps и object conflict.
- `trade_transfers.csv` - online-only transfer rules, pending locks and audit.
- `favorite_rules.csv` - consent, caps, change limits and final trace.
- `reputation_rules.csv` - range -5..+5, start 0, thresholds and visibility.
- `final_summary.csv` или runtime view, `final_master_notes.csv`, `final_procedures.csv` - финальные evidence inputs, missing locks, master notes and export fields.
- `ops_checklists.csv` или runbook manifest - game-day ops checklist.
- `player_handouts.csv` или runbook manifest - общие правила, single-d20, QR honesty policy, памятки ролей, PvP/refusal и NPC scene book.

Сервер импортирует CSV в SQLite перед игрой. Godot-клиент получает упакованный snapshot контента для офлайн-работы.

QR-коды должны содержать только короткий opaque ID, который нельзя угадать по названию монстра, локации или награды:

```text
q7f3k2a
a2_mire_9xq
pvp_8r4d
obj_4k8p
```

Нельзя зашивать в QR длинный JSON: такие коды хуже сканируются на улице и сложнее чинятся вручную. Человекочитаемые названия хранятся в CSV/панелях, а manual ID имеет rate limit, локальный лог попыток и review-сигнал при серии неверных вводов.

## iOS/Android дистрибуция

### Android

Android - самый простой путь:

- собрать APK из Godot;
- передать файл игрокам;
- установить за 3-5 дней до игры;
- проверить камеру, сохранение, офлайн-режим и синхронизацию.

### iOS без Apple Developer Program

Это главный риск проекта.

Важно: бесплатная установка через Xcode не делает приложение "онлайн-сервисом" и не публикует его в App Store. Она только позволяет запустить нашу сборку на конкретном iPhone ограниченное время. Онлайн-режим внутри игры появляется отдельно: iPhone должен находиться в домашнем Wi-Fi и подключаться к локальному серверу на мастерском ноутбуке.

План без покупки Apple Developer Program:

1. Получить Mac минимум на неделю.
2. Собрать iOS-проект из Godot.
3. Открыть проект в Xcode.
4. Протестировать free provisioning на 1-2 iPhone.
5. Использовать Apple ID владельцев телефонов, а не один общий Apple ID.
6. Проверить Developer Mode, доверие профилю, запуск приложения и доступ к камере.
7. Если установка стабильна, масштабировать на 9 мобильных ролей и один запасной/тестовый iPhone, если он нужен мастерам.
8. Установить финальную сборку за 1-2 дня до игры.

### Обновления iOS-сборки

Тестовую сборку можно обновлять поверх старой, если не менять Bundle Identifier.

Правила:

- с самого начала выбрать один Bundle Identifier, например `com.ianssensq.witcherlarp`;
- не менять Bundle Identifier между тестовыми и финальными сборками;
- ставить обновление на тот же iPhone через тот же Apple ID владельца;
- не удалять приложение перед обновлением, если нужно сохранить локальные данные;
- хранить прогресс, настройки и `event_queue` в пользовательском хранилище приложения.

Если новая сборка ставится поверх старой с тем же Bundle Identifier, iPhone воспринимает ее как обновление. Локальные данные приложения должны сохраниться, а срок бесплатной подписи для новой установленной сборки начинается заново. Поэтому финальную сборку нужно поставить или обновить на всех iPhone за 1-2 дня до игры.

Если Bundle Identifier поменять, iPhone увидит новую сборку как отдельное приложение: появится отдельная иконка, старые данные не перенесутся автоматически, а старое приложение останется на устройстве.

### Что значит "онлайн" на iPhone

Для нашей игры "онлайн на iPhone" означает подключение к локальному серверу в доме, а не доступ к интернету.

Режимы работы:

- вне дома и вне Wi-Fi: iPhone работает офлайн, считает PvE, хранит события локально;
- в доме в Wi-Fi: iPhone видит сервер, отправляет `event_queue`, получает обновления состояния;
- без связи с сервером: приложение не должно блокировать уже доступные офлайн-действия;
- для PvP и спорных действий: игрок приходит в дом, подключается к Wi-Fi, и результат фиксируется через сервер.

Для iOS обязательно проверить:

- приложение запускается после установки через Xcode/free provisioning;
- камера доступна для QR;
- iPhone видит локальный сервер в Wi-Fi;
- iOS не блокирует локальную сеть;
- после обновления сборки данные не потерялись;
- после истечения бесплатной подписи приложение больше не считается надежным способом запуска, поэтому финальную сборку нужно обновить перед игрой.

Ограничения этого пути:

- приложение, установленное через бесплатную подпись, живет ограниченное время;
- каждый iPhone требует физической установки и участия владельца;
- возможны лимиты free provisioning;
- процесс нельзя оставлять на день игры;
- нужен запас времени на повторную установку.

Sideloadly или аналогичные инструменты можно держать как запасной вариант, но основным путем считается Xcode/free provisioning, потому что он ближе к официальному процессу Apple.

### Когда стоит купить Apple Developer Program

Если бесплатная iOS-установка не масштабируется на 9 мобильных ролей плюс запасное устройство или начинает срывать сроки, нужно вернуться к Apple Developer Program.

Платный путь снимает часть установочных рисков:

- TestFlight;
- более нормальная работа с тестовыми устройствами;
- меньше ручной установки кабелем;
- возможность повторных сборок без хаоса перед игрой.

## Сеть на площадке

Отдельный роутер пока не добавляем, поэтому домашний Wi-Fi нужно проверить заранее.

### Platform/network spike и текущие launch risks

Дата последней локальной проверки: 2026-05-30. Локальная backend-часть
готова для smoke-проверок. Для Stage 1 реальные телефоны, Mac/Xcode и Wi-Fi
площадки могли оставаться launch-risk, но Stage 2B закрывает этот разрыв:
Android/iOS install-launch-connect-snapshot-restart-sync должен быть доказан
в `TASK-047`/`TASK-058`/`TASK-050`.

Зафиксированный локальный контур:

- `uv 0.11.14`;
- Python через `uv`: `3.12.10`;
- текущий IPv4 мастерского ноутбука в локальной сети: `192.168.1.9`;
- default port сервера: `8000`;
- canonical command path:

```powershell
uv sync
$env:WITCHER_LARP_HOST = "0.0.0.0"
$env:WITCHER_LARP_PORT = "8000"
uv run python -m backend.witcher_larp
```

Health URLs для smoke:

- мастерский ноутбук: `http://127.0.0.1:8000/health`;
- телефоны и лордские ноутбуки в той же Wi-Fi-сети:
  `http://192.168.1.9:8000/health` для текущего IP; на репетиции IP
  нужно заменить на фактический адрес game-day ноутбука.

Ранние hardware/venue risks, которые должны быть закрыты или явно заблокировать
Stage 2B/rehearsal:

- `launch-risk: android-export-smoke` - APK install/launch, camera permission
  и QR scan нужно проверить на Android игрока до `TASK-050`;
- `launch-risk: ios-free-provisioning` - установка через Xcode/free
  provisioning должна быть проверена на реальных iPhone до `TASK-050`;
- `launch-risk: venue-wifi-client-isolation` - телефоны и 4 лордских ноутбука
  должны открыть `/health` в домашнем Wi-Fi до hardening/rehearsal;
- `launch-risk: firewall` - Windows firewall для порта `8000` должен быть
  явно разрешен на game-day профиле;
- `launch-risk: qr-camera` - QR scan нужно проверить при освещении площадки.

Fallbacks:

- если iOS free provisioning не масштабируется, вернуться к Apple Developer
  Program/TestFlight или device provisioning;
- если домашний Wi-Fi изолирует клиентов или нестабилен, использовать
  отдельный роутер/точку доступа как аварийное решение;
- если телефон не видит сервер, игрок продолжает по offline snapshot и sync
  позже, а критические действия фиксируются на бумаге как `paper_recovered`;
- если камера не читает QR, используется ручной opaque QR-ID с rate limit и
  review path;
- если Wi-Fi/сервер падает во время лордского контура, лорды продолжают на
  бумажных листах владений, армий, заказов, рейдов и боев, после чего мастер
  восстанавливает события по timestamp.

Что проверить на репетиции:

- мастерский ноутбук имеет стабильный локальный IP;
- 4 ноутбука лордов открывают веб-панель сервера;
- iPhone и Android видят сервер в домашнем Wi-Fi;
- Wi-Fi не изолирует клиентов друг от друга;
- сервер доступен по IP и по QR-коду подключения;
- сеть выдерживает одновременную синхронизацию нескольких телефонов.

Если нет доступа к настройкам роутера, в клиенте должен быть экран подключения:

- сканировать QR с адресом сервера;
- вручную ввести IP;
- показать статус соединения;
- повторить попытку синхронизации.

## Реализационный фокус

Актуальная очередь реализации задается `docs/roadmap.md` и `tasks.json`, а не старой MVP-лесенкой. Сейчас фокус - **Stage 1 / Core Game Engine**: доказать, что все роли могут играть на runtime-движке с seed fixtures, без ожидания генератора квестов и финальной балансировки.

2026-06-02: Stage 1 acceptance переоткрыт после ревью соответствия кода
бизнес-логике. Первый remediation/test block `TASK-038`-`TASK-044` закрыт, но
повторное ревью показало, что старые тесты все еще пропустили серьезные
несостыковки.

2026-06-03: перед `TASK-018` добавлен второй remediation/test block:
`TASK-051` auth/secret leaks, `TASK-052` offline PvE/QR/act unlock integrity,
`TASK-053` rewards/assets/paper recovery/trade seed, `TASK-054` PvP/Gwent,
`TASK-055` lord runtime/economy/timers, `TASK-056` sorceress/final locks,
`TASK-057` review and rewrite of tests that missed those bugs. Stage 2 remains
blocked by `TASK-018`, and `TASK-018` is pending until `TASK-051`-`TASK-057`
are complete.

2026-06-03: после дополнительного Stage 1 code review перед `TASK-018`
добавлен третий remediation/test block: `TASK-059` app-generated d20,
`TASK-060` PvE modifier/stat authority, `TASK-061` QR/act secrecy,
`TASK-062` mobile offline queue/bundled snapshot fallback, `TASK-063`
PvP/Gwent stake/winner authority, `TASK-064` lord order escrow/route movement,
`TASK-065` master review/reputation scoping, затем `TASK-066` review and
rewrite of tests that missed these fresh bugs. Stage 2 remains blocked by
`TASK-018`, and `TASK-018` is pending until `TASK-059`-`TASK-066` are complete.

2026-06-03: после Stage 2 code review перед Stage 2B/`TASK-050`
добавлен pre-Stage-2B remediation/test block: `TASK-068` PvE reward authority and cascade
reward gates, `TASK-069` personal Gwent round authority, `TASK-070` personal
card conversion ownership, `TASK-071` lord active-army movement/capture/
garrison rules, `TASK-072` lord order lifecycle authority and validation
flags, `TASK-073` seed business validation hardening, затем `TASK-074` review
and rewrite of tests that missed these bugs. This block belongs to `STAGE-2A`,
not `STAGE-2B`, because Playable Role UI has not started yet.

2026-06-04: added a second pre-Stage-2B review follow-up block before
`TASK-050`: `TASK-075` paper recovery side effects and event-sync role scope,
`TASK-076` cross-lord order races and gold PvP stakes, `TASK-077` lord
battle/captured-territory UI blockers, `TASK-078` Admin Studio paper recovery
and Game Ops blockers, `TASK-079` mobile reputation visibility, then
`TASK-080` review/rewrite of tests that missed these issues. `TASK-045`,
`TASK-058` and `TASK-050` now depend on the later `TASK-087` gate, so Stage 2B
cannot start until the earlier fixes, the test audit and the new audit
remediation stage are complete.

2026-06-04: after iterative audit passes 1-11 produced `AUD-NEXT-001..046`, a
separate `STAGE-2A2` / `TASK-087` gate was added before Playable Role UI. This
gate explicitly separates backend/domain authority fixes from UI guardrails:
UI can remove unsafe controls and guide honest users, but it does not close an
issue while direct API/sync/snapshot paths can still mutate unsafe state or
expose hidden data. `TASK-081` classifies every finding, `TASK-082` closes
visibility leaks, `TASK-083` closes offline sync/paper recovery/restore gaps,
`TASK-084` closes timers/final/review lifecycle blockers, `TASK-085` closes
gameplay authority gaps for PvP/Gwent/assets/lord/sorceress runtime, and
`TASK-086` closes import/content invariant gates. `TASK-045`, `TASK-058` and
`TASK-050` stay blocked until `TASK-087` accepts the remediation state.

2026-06-04: `TASK-087` accepted the pre-2B remediation state using
`docs/audits/pre-2b-remediation-matrix.md` as the gate artifact. The accepted
state has no unresolved P0/P1 or blocking P2 without owner/workaround; UI
guardrails remain mitigation only. `AUD-NEXT-034` is the only explicit
non-blocking P2 boundary: restore stays `pending_backend` in Admin Studio, while
`TASK-036` owns backup/restore rehearsal and runbook proof before release.

Core Game Engine должен закрыть:

- platform/network spike для Android, iOS/free provisioning и домашнего Wi-Fi;
- FastAPI/SQLite scaffold, health endpoint, event log, backup hooks and restart recovery;
- runtime CSV/schema/import/snapshot pipeline;
- player codes, role tokens, Godot mobile shell, local storage, event_queue and sync status;
- QR/manual ID flow с opaque IDs, physical-presence honesty policy, rate limit and review path;
- offline PvE engine: app-generated `single_d20`, temporary `scene_hp`, tier defaults, 30-minute failure cooldown, reward approval locks and order/object outcomes;
- personal goals, goal_tracks, hidden goal_flags and final_hooks visibility;
- online-only trade_transfers with two confirmations, pending asset locks and atomic owner change;
- lord runtime panel shell, `/lords/home` castle/selected-territory UI, weighted map, MP, territories, thematic forts with active army <-> fort transfer, garrisons, accumulated recruit stock UI, named Olden Era-like residence building tree plus minimal territory trees, orders status machine, raids and anti-snowball;
- deterministic lord battle 5x6 with stack wounds, line of sight, 60s timer, auto-resolve and persistence;
- full Gwent personal PvP in online zone with challenge tokens, pvp_tables, throttle, refusal/safety and stake transfer;
- sorceress runtime: mana, spells, potion market, favorites lifecycle and `sorceress_alignment`;
- reputation/NPC runtime: King/Wanderer events, deals, hidden prices, severity P0/P1/P2/P3;
- NPC-led final tournament/final summary: evidence, missing locks, pending disputes, locked magical intent, personal hooks and export, without automatic winner calculation.

Stage 2-5 remain important, but they build on this core: Admin Studio, pre-2B audit remediation (`TASK-087`), Playable Role UI (`TASK-050`), PvE generator, full content pack and balance/rehearsal. They should not reintroduce alternative MVP stages or move core runtime rules into "later balance". Playable Role UI must be accepted before generated PvE/content/balance gates are treated as app-level tests. Stage 2B acceptance is now the hard real-device/non-PvE gameplay gate: Android/iOS install-launch-connect-snapshot-restart-sync, 4 lord panels, valid lord map, personal Gwent, orders/trade, sorceress gameplay and Admin recovery must pass before Stage 3 starts.

## Тестирование и репетиция

Обязательные проверки:

- Android APK устанавливается и запускается.
- iOS-сборка ставится через Mac/Xcode/free provisioning.
- Android и iOS видят локальный сервер, сканируют физический QR камерой, имеют ручной QR-ID fallback, скачивают snapshot, переживают restart и выполняют sync retry; отсутствие такой проверки блокирует Stage 2B.
- Приложение запускается после перезагрузки телефона.
- Камера читает QR.
- Есть ручной ввод QR-ID.
- Офлайн PvE не теряется после закрытия приложения.
- Очередь событий синхронизируется при появлении сервера.
- Сервер не теряет состояние после перезапуска.
- 4 ноутбука лордов одновременно работают с веб-панелью.
- Лордская карта в UI совпадает с `venue_map_v1`: playable nodes/edges, excluded old house/shed, route costs, ownership, contested, thematic fort/garrison and raid states.
- Перед `TASK-045` проходит `TASK-087`: `AUD-NEXT-001..046` распределены по backend fixes, UI guardrails или accepted residual risk; unresolved P0/P1 и blocking P2 без owner/workaround не допускаются.
- После `TASK-045` существуют `docs/ui/stage2b-screen-map.md`,
  `docs/ui/stage2b-flow-map.md`, `docs/ui/stage2b-api-map.md` и
  `docs/ui/stage2b-state-matrix.md`; every role screen/action has a read model,
  mutation/event, visibility boundary and offline/review/locked/error state.
- Visual reference smoke passes before `TASK-050`: lord castle/selected-territory home screen matching the accepted reference layout, Olden Era-like building tree, thematic territory surfaces/forts, visually distinct lord battle board, personal PvP/Gwent table and illustrated lord venue map are readable on target surfaces, data-bound to runtime state and use only original/local/generated assets.
- Visual acceptance prototype/Open Design artifact passes before implementation
  acceptance: witcher, sorceress, lord, personal Gwent and Admin
  recovery/final screens are visually reviewable by the user before Stage 2B UI
  coding is treated as accepted.
- Мастер может вручную исправить спорное событие.
- Бой PvE, личный PvP на двух реальных мобильных клиентах и бой лордов проходят от начала до конца.
- После `TASK-050` PvE smoke, personal PvP/Gwent, лордские действия, магия/зелья/фавориты и paper recovery проходят через реальные UI-поверхности, а не через Swagger/manual API.
- Перед `TASK-050` проходит отдельный non-PvE hardening script: orders/trade/inventory/reputation, sorceress potion/spell/favorite/alignment, PvP/Gwent, lord map/fort transfer/economy/battle/raid/order, Admin recovery/final_summary и дефект-триаж.
- `TASK-058` writes persistent evidence to `reports/stage2b/`: device evidence,
  UI-flow evidence, screenshot evidence and defect triage with owner/workaround.
- Перед Stage 3 нет известных P0/P1 и блокирующих P2 дефектов в non-PvE gameplay; P2/P3 имеют owner, severity и workaround.
- Personal goals, goal_flags, trade_transfers, favorites lifecycle, locked magical intent, reputation thresholds and final_summary проходят scripted run.
- Offline act unlock, reward approval locks, PvP tables/throttle, spell/potion catalog, master-led final summary and final lock проходят scripted run.
- Paper fallback drill проходит на критичном событии, включая лордское действие или лордский бой: бумажная форма вводится в Admin Studio как `paper_recovered`, а конфликт с уже синхронизированным событием уходит в review.

## Аварийный бумажный режим

Бумажный режим включается сразу для конкретного критичного действия, если его нельзя провести в приложении, на сервере или через локальную сеть. Это не полноценная замена приложения, а страховка событий, потеря которых ломает игру.

Разрешенные формы:

- `paper_pve_result`;
- `paper_pvp_stake`;
- `paper_lord_action`;
- `paper_lord_battle`;
- `paper_order_resolution`;
- `paper_npc_deal`;
- `paper_final_evidence`.

Операционный порядок:

1. Мастер фиксирует событие на бумаге с `paper_form_id`, участниками, актом, объектом/ставкой/QR, результатом, оператором и временем.
2. Игра продолжается, если событие не является P0/P1 блокером.
3. После восстановления мастер вводит форму в Admin Studio.
4. Сервер создает событие `source=paper_recovered`, применяет его через обычные idempotency/conflict checks или отправляет в review.
5. Бумага и цифра никогда не перетирают друг друга молча; спорный объект, заказ, ставка, территория, лордский бой или финальный флаг закрывается master ruling.

Для лордов бумажный режим является рабочим продолжением игры, а не паузой. NPC-мастера выдают последний известный snapshot владения: золото, income, influence, территории, армия, reserve, гарнизоны, здания, raid tokens, активные заказы и contested claims. Лорды могут выдавать бумажные заказы ведьмакам, двигать армию по распечатанному `venue_map_v1`, заявлять захваты/рейды/строительство/рекрутинг через `paper_lord_action` и проводить лордские бои через `paper_lord_battle`. После восстановления мастер вводит действия по timestamp, а сервер применяет их через проверки ресурсов, ownership, garrison, pending tick и duplicate action или отправляет конфликт в review.

## Риски

### iOS-установка

Самый высокий риск. Бесплатная установка на 9 мобильных ролей плюс запасное устройство может упереться в лимиты Apple, настройки телефонов, Developer Mode, Apple ID, кабели и время.

Снижение риска:

- начинать iOS-spike первым;
- использовать реальные iPhone игроков;
- провести установочную репетицию;
- держать Mac доступным до игры;
- иметь запасной план с Apple Developer Program, если free provisioning не масштабируется.

### Домашний Wi-Fi

Риск: устройства могут не видеть друг друга из-за настроек роутера или client isolation.

Снижение риска:

- проверить сеть до игры;
- подключаться по IP/QR;
- иметь возможность быстро сменить адрес сервера в клиентах;
- при критической проблеме вернуться к отдельной точке доступа как аварийному решению.

### Объем боев

Риск: почти полноценные PvE, full Gwent PvP и бои лордов за короткий срок могут разрастись.

Снижение риска:

- делать отдельные движки, но общий набор примитивов;
- в первой версии сохранять текстовый лог и простой UI;
- откладывать анимации, сложные эффекты и визуальную полировку;
- сначала довести по одному полному сценарию каждого боя.
- Stage 5 отдельно меряет full Gwent volume, no-match-limit risk, 60s lord battle timeout и auto-resolve frequency.

### Контент

Риск: код будет готов, но не хватит проверенного контента.

Снижение риска:

- стартовать с минимального пакета;
- хранить контент в CSV;
- импортировать контент автоматически;
- тестировать баланс на малом наборе до расширения.
- не принимать full content pack без personal goal hooks, QR mix 15+25, custom Gwent cards, trade/favorite/final hooks and final_summary evidence fields.

## Источники для проверки платформенных решений

- Apple TestFlight: https://developer.apple.com/testflight/
- Apple membership comparison: https://developer.apple.com/support/compare-memberships/
- Apple Unlisted App Distribution: https://developer.apple.com/support/unlisted-app-distribution/
- Godot Android export: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_android.html
- Godot iOS export: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_ios.html
