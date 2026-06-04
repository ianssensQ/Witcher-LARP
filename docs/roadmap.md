# Роадмап - Witcher LARP App

Роадмап теперь организован как шесть жестких этапов. Каждый этап заканчивается отдельной gate-задачей в `tasks.json`, и следующий этап считается открытым только после приемки предыдущего gate. Исключение - безопасная инфраструктурная подготовка, которая не меняет смысл этапов и не подменяет их приемку.

`TASK-000` остается выполненным TaskOS baseline. Рабочая очередь после baseline начинается с `TASK-001`, `TASK-002`, `TASK-003`.

Проверка пробелов между документацией, архитектурой и задачами теперь живет в
основных документах, а не в отдельном audit-файле: технический контракт
реализации описан в `docs/architecture.md`, platform/network риски - в
`docs/app-technical-plan-v0.1.md`, а порядок работ - здесь и в `tasks.json`.
Если реальные устройства или домашний Wi-Fi еще не проверены, это считается
launch risk, а не поводом менять архитектуру Stage 1.

## Stage 1 - Core Game Engine

Gate: `TASK-018`.

2026-06-02: gate Stage 1 переоткрыт после ревью бизнес-логики. Старый
remediation/test block `TASK-038`-`TASK-044` закрыт, но повторное ревью нашло
оставшиеся P0/P1 несостыковки.

2026-06-03: перед повторной приемкой добавлена новая волна задач
`TASK-051`-`TASK-056` на серьезные issues по auth/secrets, offline
PvE/QR/act unlock, rewards/locks/paper recovery, PvP/Gwent, lord runtime и
sorceress/final locks. После них отдельная задача `TASK-057` ревьюит и
переписывает тесты, которые не поймали эти баги. `TASK-018` снова имеет статус
`pending` и не считается принятым, пока `TASK-051`-`TASK-057` не завершены.

2026-06-03: после дополнительного полноценного ревью Stage 1 добавлен свежий
pre-gate блок `TASK-059`-`TASK-065`: app-generated d20, PvE modifier/stat
authority, QR/act secrecy, mobile offline queue/bundled snapshot fallback,
PvP/Gwent stake+winner authority, lord orders escrow/route movement и
master review/reputation scoping. `TASK-066` идет после этих fixes и отдельно
переписывает тесты, которые не поймали свежие баги. `TASK-018` остается
`pending`, пока `TASK-059`-`TASK-066` не закрыты.

Цель: реализовать основной runtime-движок игры для всех классов и ролей без зависимости от будущей генерации контента.

Production profile для всех этапов: 15 человек всего, 13 игроков + 2 NPC-мастера; игроки - 4 лорда, 4 гибридные мобильные чародейки и 5 свободных ведьмаков.

Что входит:

- platform/network spike, FastAPI/SQLite scaffold, runtime CSV, import и snapshot;
- uv-managed Python/backend/tooling contract: `pyproject.toml`, `.python-version`, `.venv` через `uv sync`, запуск через `uv run`;
- implementation layout: `backend/witcher_larp`, `mobile/`, `backend/witcher_larp/web`, `data/seed`, `data/snapshots`, `data/backups`, `tests/fixtures`;
- player codes, role tokens, mobile snapshot, event queue и sync;
- seed/runtime profile 4/4/5 + 2 NPC-мастера;
- 10-часовой fixed schedule seed: registration/snapshot, Act 1, buffer, Act 2, buffer, Act 3, final lock, Final Act, debrief/export/emergency buffer;
- offline act unlock seed: server sync или master `act_unlock_code`/QR для Act 2, Act 3 и Final Act;
- physical act announcement seed: после запуска на сервере каждый акт явно объявляется голосом/криком на участке;
- QR/manual ID seed: opaque non-guessable IDs, physical-presence-only правило и review path для suspected honesty violation;
- single-d20 PvE checks: одна проверка = один app-generated d20, преимущества/помехи идут как логируемые modifiers, без ручного ввода и reroll;
- venue map v1 seed: 4 резиденции в активном новом доме, excluded old house + adjacent shed, лордский weighted graph по крепостям, полям, деревням, городам ресурса/магии/науки, лесам, озерам, болоту и горам;
- V0 balance defaults: XP thresholds, PvE DC by tier, reward budgets, lord economy defaults, lord HP formula, mana regen/costs;
- rarity fields and caps in seed/runtime data: `Common/Uncommon/Rare/Legendary`, `power_budget`, `act_cap`, `visibility`, `counterplay`;
- reward approval seed для cascade-prone offline rewards: `pending_master_approval`, `approved`, `corrected/rejected`;
- paper recovery event contract for critical fallback forms with `source=paper_recovered`, including lord action and lord battle paper continuation;
- QR/manual flow и offline PvE runtime с `qr_mode` values `unique_object`, `repeatable_scene`, `always_available_scene`;
- personal_goals, goal_tracks, goal_flags и final_hooks runtime;
- online-only trade_transfers: two confirmations, pending asset lock, atomic owner change and audit log;
- свободный ведьмачий/чародейский PvE в любых зонах независимо от владельца территории;
- 3 сюжетных акта + финальный акт, auto timers, backup hooks;
- лордская weighted map, movement pool, territories, тематические форты с active army <-> fort transfer, гарнизоны, recruit market, default building tree, 6 классов army unit cards, raid engine, заказы, escrow, anti-snowball 30/50 и deterministic battle engine 5x6 с 60s turn timer/auto-resolve, V1 power formulas, stack wounds, deployment caps, line of sight and hero targeting;
- full Gwent personal PvP, 3 challenge tokens per act, накопление токенов, max 1 active challenge, timeout/refusal/tie review и 30-minute PvP window на явку/старт в назначенной online-зоне;
- PvP throttling: default 2 `pvp_tables`, queued challenges, max 2 started mandatory matches per player per act без master approval, режимы `normal/limited/paused`, final lock behavior;
- PvP refusal/safety table: active scene/deferred, unsafe route/force majeure, safety stop, valid-ignore review and overload throttle behavior;
- чародейки: PvE/PvP, hourly mana regen, wholesale/resale potion market, зелья, заклинания, primary/secondary фавориты, `sorceress_alignment`, locked magical intent;
- favorites lifecycle: consent, 1 primary + 1 secondary, max 2 sorceresses per favored player, 1 change per act, no passive runtime bonus;
- репутация Добро/Зло с диапазоном -5..+5, стартом 0 и thresholds Тьма/Запятнанный/Нейтральный/Добро/Свет, NPC Король/Свет, Странник/Тьма-Дьявол, NPC deal capture;
- NPC-led final tournament summary runtime: evidence по ролям, missing locks, pending disputes, NPC prices, locked magical intent, personal hooks, final lock and export snapshot без автоматического объявления победителей.
- 7:30-9:30 master-led Final Act runbook with NPC-led tournament, review severity P0/P1/P2/P3 and game-day ops checklist hooks.

Когда тестировать:

- после platform/network spike;
- после schema/import/snapshot;
- после mobile QR/PvE vertical slice;
- после каждого rule engine: PvE, PvP, lord strategic map, lord battle, raid engine, sorceress magic, reputation/NPC;
- перед `TASK-018` одним seed scripted role-flow.

Чем подтверждаем:

- seed CSV imports без ошибок;
- Python/backend/tooling commands use uv and do not require global Python packages;
- Stage 1 uses static FastAPI-served HTML/CSS/JS panels without implicit Node frontend build tooling;
- implementation layout directories are documented before code depends on them;
- seed фиксирует 4 лордов, 4 чародеек, 5 ведьмаков и 2 NPC-мастеров;
- seed фиксирует venue_map_v1 и исключает старый дом/соседний сарай из игровых узлов;
- seed фиксирует personal_goals, goal_flags, trade_transfers, full Gwent cards/matches and final_summary;
- seed фиксирует V0 balance defaults, rarity fields/caps and paper recovery event contract;
- seed фиксирует act_unlock_codes, reward_approval_rules, pvp_tables/throttle, spell/potion V0 catalog, final_summary fields and ops checklist;
- seed фиксирует physical act announcements, opaque QR/manual IDs, QR honesty policy, single-d20 check policy, PvP refusal/safety table and player-facing handout manifest;
- телефон скачивает snapshot по `player_code`;
- offline PvE проходит без Wi-Fi, пишет roll log, ставит 30-минутный cooldown после провала и sync later;
- offline PvE использует ровно один app-generated d20 на проверку и логирует все modifiers преимущества/помехи;
- offline PvE будущего акта открывается только через server sync или master unlock code;
- новый акт физически объявлен на участке до раскрытия unlock code;
- QR/manual ID opaque/non-guessable, нельзя применить без physical-presence-only подтверждения, suspected violation уходит в review;
- unique/rare/order/final offline rewards уходят в pending master approval и не могут быть потрачены до подтверждения;
- ведьмак/чародейка проходит QR/PvE на территории любого владельца;
- лорд создает order, сервер держит escrow;
- active army получает movement pool до cap, проходит weighted route и не копит MP выше cap;
- первый arrival создает contested territory, факт захвата виден всем лордам;
- нейтральная территория захватывается через 5x6 бой против server AI с возможностью master takeover;
- победитель оставляет гарнизон, а income/influence tick и pending reward начисляются корректно;
- владелец территории может перебросить текущие войска из активной армии в тематический форт и обратно без MP, если армия стоит на этой территории и состояние не contested/in_battle;
- recruit market обновляется, hold сохраняет выбранное предложение, новые войска попадают в reserve;
- default building tree покупается за gold по prerequisites, открывает recruit/capacity/raid effects, не имеет act cap и отображается как Olden Era-like дерево узлов с prerequisite lines/detail card;
- каждый из 6 классов юнитов (`infantry`, `guard`, `ranged`, `cavalry`, `heavy_siege`, `specialist`) имеет smoke fixture в 5x6;
- raid engine применяет timed debuff или loot gold/cards/influence через token/gold/resistance check;
- anti-snowball rule применяет 30%/50% income cut при слишком сильной армии;
- diplomacy signals дают видимые причины для союзов, заговоров и коалиций против лидера;
- два лорда завершают deterministic бой 5x6 с 60s timeout и auto-resolve path;
- PvP challenge тратит жетон, проверяет накопление 3 токенов за акт, max 1 active challenge и 30-minute PvP окно на явку/старт;
- PvP throttle проверяет 2 pvp tables, queued challenge, per-act started match cap, mode `normal/limited/paused` and final lock behavior;
- full Gwent fixture проходит deck validation, 10-card hand, mulligan, 3 rows, pass, weather/decoy/scorch/horn, tie handling and stake transfer;
- PvP timeout/refusal/tie path уходит в master review, а Stage 5 отдельно проверяет PvP volume и no-match-limit risk для 15-person profile;
- trade_transfer блокирует asset до accept/decline и атомарно меняет владельца;
- чародейка покупает зелье по wholesale/resale rules, передает/продает его, получает hourly mana regen, применяет валидное заклинание с тратой маны, ведет consent-based primary/secondary favorites без passive runtime bonus, меняет `sorceress_alignment` только через evidence event и фиксирует locked magical intent в final lock;
- spell/potion seed покрывает T1-T4 spell roles, potion wholesale 8/18/40 and max 1 potion per scene default;
- NPC/reputation event меняет видимое/скрытое состояние, Король может выдать influence/ruling, Странник - сделку с ценой;
- final summary собирает evidence по ролям, missing locks, pending disputes, NPC prices, locked magical intent, personal hooks, final lock state and export snapshot для NPC-led final tournament/master ruling;
- paper recovery fixture создает `paper_recovered` событие с `paper_form_id`, source form type, operator, reason и conflict path, включая paper_lord_action/paper_lord_battle;
- restart не теряет состояние.

## Stage 2 - Admin Studio

Gate: `TASK-023`.

Цель: сделать полную браузерную админ-панель/студию управления до генерации PvE-контента, чтобы генератор сразу встраивался в удобную UI-модель.

Что входит:

- Admin Studio shell и master role-token access;
- UI для content import/validation, snapshot_version и QR checklist;
- UI/contract для paper recovery ввода критичных бумажных событий и review конфликтов;
- UI для act unlock codes, reward approvals, review severity P0/P1/P2/P3 и PvP throttle mode;
- game ops dashboard: акты, auto timers, event log, sync status, review queue;
- lord map ops: просмотр/коррекция map state, MP, гарнизонов, contested battles, pending rewards, recruit market и raid effects;
- ops для PvP challenge review, anti-snowball status, potion market и raid loot/effects;
- manual corrections с reason/operator;
- backups и restart recovery controls;
- NPC tools, reputation numeric/log view, artifact visibility audit;
- diplomacy/standing visibility для мастерского контроля союзов, заговоров и коалиций;
- final summary view/export.

Когда тестировать:

- после первого Admin shell;
- после import/validation UI;
- после game ops dashboard;
- после NPC/final tools;
- перед `TASK-023` полным Admin smoke.

Чем подтверждаем:

- мастер входит в Admin Studio по role-token;
- valid content pack импортируется из UI;
- broken CSV показывает читаемые ошибки;
- import/validation UI показывает rarity caps, power budget, visibility/counterplay gaps and paper recovery conflicts;
- building/unit validation ловит cycle, missing prerequisite, invalid unit class/tier/capacity и bad recruit unlock;
- snapshot собирается из UI;
- мастер запускает акт, видит timer/tick status и решает review event;
- мастер получает/показывает unlock code после старта акта, подтверждает pending reward approval и меняет PvP throttle mode;
- мастер видит лордскую карту, contested territory, pending tick reward и может поправить owner/garrison/MP/raid effect с reason;
- мастер видит anti-snowball state, challenge timeout review, potion market transfers и raid loot/effects;
- correction сохраняется с причиной;
- NPC deal фиксируется через UI;
- backup запускается и виден мастеру;
- final summary открывается и экспортируется.

## Stage 2A - Stage 2 Review Remediation

Gate: `TASK-080`.

2026-06-03: после ревью кода Stage 2 перед следующим playable/UI-гейтом
добавлен pre-Stage-2B remediation/test block. `TASK-068`-`TASK-073` закрывают
серьезные runtime/validation issues: PvE reward authority, one-sided Gwent
round authority, personal card ownership conversion, lord active-army/garrison/
movement rules, lord order lifecycle authority and seed business validation.
`TASK-074` отдельно ревьюит и переписывает тесты, которые не поймали эти баги.

2026-06-04: added a second pre-Stage-2B remediation block: `TASK-075` paper
recovery/event-sync role scope, `TASK-076` cross-lord order races and gold PvP
stakes, `TASK-077` lord battle/captured-territory UI, `TASK-078` Admin Studio
recovery/Game Ops blockers, `TASK-079` mobile reputation visibility, followed by
`TASK-080` test review/rewrite. Этот блок остается закрытым Stage 2A follow-up;
после дополнительного audit pass 1-11 перед UI добавлен отдельный gate
`STAGE-2A2`.

## Stage 2A2 - Audit Remediation and UI Guardrails

Gate: `TASK-087`.

2026-06-04: после накопительного audit `AUD-NEXT-001..046` добавлен отдельный
pre-Stage-2B stage. Его смысл - не "спрятать ручки UI", а закрыть существенные
bugs там, где нужен backend/domain authority, и явно пометить UI guardrails как
mitigation. `TASK-081` классифицирует все findings на backend fix, UI
guardrail, test coverage или accepted residual risk. `TASK-082` закрывает
player/lord visibility leaks, `TASK-083` - offline sync, paper recovery и
restore authority, `TASK-084` - timers/final lock/review lifecycle,
`TASK-085` - gameplay authority для PvP/Gwent, assets, lord и sorceress
runtime, `TASK-086` - import/content invariant gates. `TASK-087` принимает
stage и блокирует Playable Role UI, пока по `AUD-NEXT-001..046` не останется
unresolved P0/P1 или blocking P2 без owner/workaround.

`TASK-045`, `TASK-058` и `TASK-050` зависят от `TASK-087`, поэтому Stage 2B
начинается только после этого audit-remediation gate.

2026-06-04: `TASK-087` принят по
`docs/audits/pre-2b-remediation-matrix.md`. Все `AUD-NEXT-001..046` имеют
closure evidence через `TASK-082`-`TASK-086` или явную residual-risk запись;
единственный принятый non-blocking P2 boundary - `AUD-NEXT-034`, где Admin
Studio честно помечает `restore_backup` как `pending_backend`, а полноценный
backup/restore rehearsal остается owner-risk для `TASK-036`.

## Stage 2B - Playable Role UI

Gate: `TASK-050`.

Stage 2B starts with `TASK-045` only after the pre-stage remediation gate
`TASK-087` is complete.

Цель: сделать основные игровые интерфейсы ролей полноценными до генерации и балансировки контента, чтобы весь задуманный gameplay без generated/full PvE content можно было тестировать как приложение, а не как Swagger/API smoke.

Что входит:

- UI contract и role journey matrix для мастера, лорда, ведьмака, чародейки и NPC-мастера;
- `TASK-067` visual reference/asset brief: лордский замок/город и точное building-tree взаимодействие в логике Heroes Olden Era, thematic territory forts, personal PvP/Gwent стол ведьмаков/чародеек в экранной грамматике Witcher 3 Gwent, визуально отдельный 5x6 lord battle board и карта участка как иллюстрированная fantasy strategy map поверх лордского `venue_map_v1`; все production assets оригинальные/local/generated, без копирования официальных артов, логотипов и скриншотов;
- no-Swagger acceptance rule: штатные player/lord действия принимаются только через app/panels, а Swagger/curl/manual API остаются developer diagnostics;
- полноценный lord action UI: валидная иллюстрированная `venue_map_v1`, route/MP, contested claims, thematic forts, active army <-> fort transfer, гарнизоны, reserve, Heroes-like castle/city-development screen/building tree для buildings, recruit, orders/escrow, raids и 5x6 lord battle board;
- mobile gameplay UI для ведьмаков и чародеек: персонаж, snapshot, QR/manual PvE на физических локациях, offline act unlock, single_d20, scene_hp, cooldown, reward approval, inventory, orders, trade, reputation, event_queue/sync; online-карта для этих ролей не является обязательной;
- sorceress mobile UI: mana, spells, potion wholesale/transfer/use, favorite consent, alignment evidence and locked magical intent;
- personal PvP/Gwent UI: challenge, pvp table/queue, deck/hand/mulligan, rows/pass/rounds, stake result, refusal/safety and review paths;
- Admin paper recovery/correction forms for `paper_pve_result`, `paper_pvp_stake`, `paper_lord_action`, `paper_lord_battle`, `paper_order_resolution`, `paper_npc_deal` and `paper_final_evidence`;
- hard Android/iOS device gate: APK/iOS build ставятся, запускаются, видят локальный сервер, сканируют физический QR камерой, имеют ручной QR-ID fallback, скачивают snapshot, переживают restart и retry sync на реальных телефонах;
- non-PvE hardening (`TASK-058`): 4 лордские панели, валидная карта, personal Gwent, заказы/trade, магия/зелья/фавориты, Admin recovery/final_summary и дефект-триаж;
- UI-first restart/offline/retry/review/locked-state smoke.

Когда тестировать:

- после `TASK-023`, когда Admin Studio уже есть как базовая мастерская панель;
- после UI contract matrix;
- после `TASK-067` visual reference/asset brief;
- после lord action UI;
- после mobile gameplay UI;
- после PvP/Gwent UI;
- после paper recovery/correction forms;
- после `TASK-058` non-PvE gameplay hardening на реальных поверхностях;
- перед `TASK-050` одним UI scripted role-flow и отдельным non-PvE gameplay script.

Чем подтверждаем:

- ведьмак проходит login/snapshot -> QR/manual PvE -> cooldown/reward approval -> restart/offline -> sync через мобильный UI;
- чародейка проходит PvE плюс potion buy/transfer/use, spell, favorite consent and locked magical intent через мобильный UI;
- Android и iOS real-device smoke проходят до приемки, включая camera QR scan физического QR и ручной QR-ID fallback; отсутствие device smoke блокирует Stage 2B и не записывается как launch-risk fallback;
- лорд проходит route -> contested claim -> battle -> garrison -> fort transfer -> building -> recruit -> reserve -> raid -> order через браузерную панель, а карта читаема и совпадает с `venue_map_v1`;
- лордский замок/city-development screen/building tree, thematic territory forts, визуально отдельный lord battle board, personal Gwent table и illustrated lord venue map проходят screenshot/readability/IP-safe asset acceptance на целевых поверхностях;
- два игрока проходят personal PvP/full Gwent через UI на двух реальных мобильных клиентах, включая stake, pass/rounds, refusal/review edge case and idempotent finish;
- мастер вводит paper recovery/correction forms из Admin Studio, duplicate/conflict уходит в review без silent overwrite;
- 4 lord panels открываются одновременно;
- после restart состояние видно в Admin/mobile/lord UI;
- ни один player/lord acceptance step не требует Swagger, raw curl, прямого API docs или SQLite edits;
- бумажный fallback проверяется как outage recovery, но не заменяет отсутствующий штатный UI;
- перед Stage 3 нет известных P0/P1 и блокирующих P2 дефектов в non-PvE gameplay.

## Stage 3 - PvE Generation Engine

Gate: `TASK-028`.

Цель: реализовать генератор PvE-контента внутри Admin Studio, а не как отдельный CLI-first инструмент. Stage 3 открывается после `TASK-050`, чтобы sample generated quests проверялись через mobile gameplay UI и Admin Studio, а не только через API.

Что входит:

- UI data model для draft quests;
- шаблоны сцен: monster hunt, investigation, moral choice, puzzle, artifact, order;
- controls для tier, act, location, primary/secondary stat, DC, combat profile, reward budget, QR mode;
- artifact/reputation/NPC/order flags;
- personal goal hooks, goal_flags, final_hooks and role_load_tag controls;
- preview success/failure text;
- compiler в authoring matrix и runtime CSV;
- validation report и sample generated quest run.

Когда тестировать:

- после draft data model;
- после UI controls;
- после compiler/export;
- после validation harness;
- перед `TASK-028` тестовым generated pack.

Чем подтверждаем:

- мастер создает PvE draft из Admin Studio;
- draft компилируется в authoring matrix/runtime CSV;
- generated pack импортируется существующим importer;
- validation ловит missing reward_budget, invalid tier, missing texts, invalid QR mode;
- validation ловит missing act_unlock_policy, reward_approval_policy, final_score_category или ops_checklist_tag для relevant scenes;
- validation ловит missing personal goal hook/final hook там, где сцена обещает сюжетный или финальный след;
- один generated QR/PvE квест проходит draft -> compile -> import -> mobile gameplay UI -> sync.

## Stage 4 - Unique Quest Production

Gate: `TASK-032`.

Цель: сгенерировать и вручную отполировать полный уникальный контент-пак для 10-часовой игры.

Что входит:

- 40+ QR/PvE-сцен: минимум 15 always-available/repeatable сцен и 25+ unique objects;
- из них минимум 15 always-available/repeatable сцен и 25+ уникальных объектов;
- content matrix: Act 1 = 12 слотов, Act 2 = 14, Act 3 = 14;
- balanced mix: монстры, расследования, моральные выборы, задачки, артефакты, заказы;
- tiers 1-4 по актам;
- personal goal hooks, hidden goal_flags, final_hooks and role-load tags;
- act unlock policy, reward approval policy, final score category, PvP throttle tags and ops checklist tags;
- предметы, редкие карты, зелья, заклинания, артефакты, сюжетные ключи и стратегические предметы;
- custom full Gwent card pack без копирования официального контента CDPR: row/leader/weather/special taxonomy, rarity, deck limits, power budget, original LARP names/portraits and art prompts;
- XP sources: монстры, автоквесты, заказы, личные цели и значимые события;
- именованные army unit cards, territory recruit sources и flavor offers для лордов;
- building/unit visual tags and art prompts для Heroes-like castle UI/building tree: экономика, найм, оборона, совет/заказы, магия/наука, reserve/capacity and raid support;
- territory fort manifest: one original fort image/card per capturable territory, `fort_theme`, `visual_tag`, `art_prompt`, `garrison_capacity`, optional defense bonus and transfer labels;
- venue map content manifest: node labels, physical landmarks, route flavor, print fallback and art prompt notes for the lord graph; QR props are handled in the QR checklist, not as lord map anchors;
- public/addressed orders, escrow rewards и cap 2 public + 1 addressed active orders per lord;
- NPC events, King rulings, Stranger deals, reputation rules, favorites lifecycle, final_summary fields, master final hooks and flags;
- master-led Final Act runbook and review severity rubric;
- QR print/manual-code checklist.
- Player-facing handouts: общие правила, opaque QR/manual IDs, QR honesty policy, single-d20 checks, памятки ведьмака/чародейки/лорда, PvP refusal/safety и NPC scene book.
- rarity caps: rare Gwent cards 6 total/max 2 per act, artifacts 8 total, legendary artifacts 2 total/not before Act 2, plot/strategic keys 6 total, potion caps by tier.

Когда тестировать:

- после генерации draft pack;
- после ручной полировки;
- после сборки full content pack;
- перед `TASK-032` content smoke.

Чем подтверждаем:

- минимум 40 QR/PvE entries;
- coverage report подтверждает минимум 15 always-available/repeatable сцен и 25+ unique objects;
- coverage report подтверждает Act 1/2/3 = 12/14/14 slots and per-act scene hooks;
- каждый QR имеет act, location, tier, scene type, QR mode, reward budget, success/failure text и sync outcome;
- каждый QR имеет check policy `single_d20`, modifier sources и physical-presence honesty policy;
- каждый QR имеет act unlock policy, reward approval policy and ops checklist tag, если это физический prop;
- coverage report покрывает tiers, scene mix, stat distribution, rewards и QR modes;
- content pack импортируется без ошибок;
- content pack содержит personal goal hooks, hidden goal_flags, final_hooks and custom Gwent cards;
- full content pack включает building catalog, army unit catalog, recruit sources, visual tags/art prompts, territory fort manifest и territory flavor для лордов;
- custom Gwent card coverage проверяет rows, leaders, weather/special effects, rarity, deck limits, power budget and original art prompts;
- venue map manifest проверен против `venue_map_v1`, physical landmarks, route flavor and printed fallback; QR props are checked separately;
- artifact visibility проверена;
- rarity caps, power budget, visibility and counterplay проверены для редких карт, артефактов, зелий и сюжетных ключей;
- digital order race проходит через app-first flow;
- лордский content pack не делает ведьмаков единственным способом прогресса владения;
- один игрок не может держать два заказа на один объект, а объект можно перехватить через personal PvP;
- один лорд не может иметь больше 2 публичных и 1 адресного активного заказа;
- trade/order object content respects online-only transfer and pending asset locks;
- QR checklist пригоден setup operator.
- player-facing handouts готовы к печати и совпадают с runtime rules.

## Stage 5 - Balance Simulation

Gate: `TASK-037`.

Цель: проверить баланс игры через симуляцию действий и rehearsal так, чтобы всем ролям было интересно во время 10-часовой игры.

Что входит:

- archetype player simulator;
- 15-person profile simulator: 5 witchers, 4 hybrid sorceresses, 4 lords, 2 NPC-master load;
- reward/progression reports;
- PvE tier pressure и 30-минутный cooldown impact;
- full Gwent outcomes, challenge token pacing, 30-minute PvP start window, no-match-limit risk after match start, custom card value and deck complexity from weather/special/leader cards;
- PvP-volume go/no-go report with 90th percentile table wait, matches over 25 minutes, per-act mandatory starts, review load and tuning knobs for tokens/throttle/tables/card complexity;
- trade conflict/asset lock report;
- PvP timeout/refusal/tie volume для 3 challenge tokens per act;
- deterministic lord battle 5x6, 60s timeout/auto-resolve, economy и anti-snowball 30/50 reports;
- lord movement graph, physical route assumptions, thematic fort transfer/capacity, recruit market, Heroes-like building tree depth/prerequisites, unit classes/stats/caps, raid debuffs и pending tick rewards;
- lord venue map playability report: node density, edge costs, route legibility, physical route assumptions, printed fallback and no GPS/internet/QR dependency for lord movement;
- visual-content readability report: castle/building tree, thematic forts, lord battle board, personal Gwent and lord map surfaces do not hide costs, locks, counters, route costs, garrison capacity or state labels;
- diplomacy/coalition pressure против лидера;
- sorceress mana/spell/favorite impact;
- sorceress wholesale potion economy impact;
- spell/potion V0 catalog impact, potion per-scene cap and rare potion caps;
- primary/secondary favorites impact and caps;
- order pressure for 5 witchers and lord progression without critical witcher dependency;
- idle risk report for 9 mobile roles and 15+25 QR mix;
- artifact value и NPC deal prices;
- King ruling influence, Stranger hidden price и final_summary inputs;
- NPC-master split: King/order/admin-review and Stranger/deals/field interventions;
- full rehearsal, fixed 10-hour game-day runbook with buffers/final lock, fallbacks и release scripted run.
- Final Act 7:30-9:30 NPC-led tournament timebox rehearsal and game-day ops checklist.
- Master-led Final Act load rehearsal for two NPC masters.
- outage drill: immediate paper fallback, `paper_recovered` input, conflict review and no silent overwrite.

Когда тестировать:

- после full content pack;
- после первой deterministic simulation;
- после tuning reward/progression;
- после combat/economy/magic reports;
- за 3-5 дней до игры на real hardware;
- утром перед игрой коротким game-day smoke.

Чем подтверждаем:

- активный игрок в симуляции приходит примерно к уровню 7-9;
- уровень 10 остается редким достижением;
- награды ощущаются стоящими и не ломают экономику;
- нет очевидной доминирующей стратегии в full Gwent PvP, лордской экономике или магии;
- challenge tokens, potion economy, raid loot и 30/50 anti-snowball не создают exploit;
- rare rewards, legendary artifacts, plot keys and potion caps не создают exploit или доминирующую стратегию;
- 3 challenge tokens per act не создают чрезмерный PvP volume в 15-person profile: 90-й перцентиль ожидания стола <=10 минут, не больше 20% матчей уходят за 25 минут, per-act mandatory starts не перегружают буферы, а отсутствие лимита времени после старта Gwent не ломает расписание;
- custom Gwent decks имеют читаемую row/special/leader distribution and no single card family creates a dominant or overlong match pattern;
- PvP throttle normal/limited/paused, 2 pvp tables, queued challenges and per-act match cap do not create deadlocks;
- trade_transfers не создают double ownership, lost assets или конфликтные locks;
- 15 always-available/repeatable сцен и 25+ unique objects не создают idle risk для 9 мобильных ролей;
- offline act unlock and pending reward approval do not create idle risk or cascade exploits;
- лордам интересно двигаться по карте, атаковать, защищаться, перебрасывать войска в тематические форты и обратно, гарнизонить, строиться, рейдить, нанимать войска и создавать заказы;
- movement по карте участка остается играбельным для лордов без GPS/интернета/QR: illustrated map, route costs, physical route assumptions and paper fallback agree with runtime map data;
- цены зданий, prerequisites, recruit refresh, unit stats и caps дают осмысленный выбор без обязательной единственной ветки;
- чародейки влияют на игру без поломки баланса;
- primary/secondary favorites дают влияние без dogpile и без поломки финала;
- финальные процедуры имеют NPC-led tournament/final_summary входные данные, missing locks, NPC prices, locked magical intent, personal hooks and export snapshot;
- master-led Final Act timeboxes fit into 7:30-9:30 without a single scene consuming the whole finale;
- Final Act load feasible for two NPC masters without unmanned critical review;
- full scripted run проходит на мастерском ноутбуке, 4 lord panels и реальных телефонах;
- runbook проверяет разделение двух NPC-мастеров и order pressure при 5 ведьмаках;
- runbook проверяет review severity P0/P1/P2/P3, game-day ops checklist, act unlock codes, reward approvals and PvP throttle mode;
- runbook проверяет physical act announcements, opaque QR/manual IDs, QR honesty policy, single-d20 checks, PvP refusal/safety table and player-facing handouts;
- server restart, backups, restore и post-game export проверены;
- paper fallback/recovery проверен на QR/PvE, PvP stake, lord action, lord battle, order resolution, NPC deal and final evidence;
- dashboard, `tasks.json`, `docs/active-tasks.md`, kanban and generated files are synchronized.

## Общая проверка TaskOS

После изменения задач или документов выполнять:

```powershell
uv run python -m json.tool tasks.json
uv run python scripts\taskctl.py validate
uv run python scripts\taskctl.py sync
uv run python scripts\taskctl.py doctor
```

Готовность очереди подтверждается, если `doctor` показывает, что generated files are up to date, а dashboard показывает stage tags, stage filters, gate-задачи и корректные dependency-ready задачи.
For ordinary queue orientation, read `docs/active-tasks.md` or run `uv run python scripts\taskctl.py ready`; open full `tasks.json` only for graph edits or when the compact view is insufficient.
