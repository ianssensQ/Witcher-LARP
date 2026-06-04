# Business Test Coverage Gaps

Дата среза: 2026-06-03.

Команды проверки:

- `uv run pytest -q` — 146 passed.
- `uv run --with coverage coverage run -m pytest -q` — 146 passed.
- `uv run --with coverage coverage report -m --include="backend/witcher_larp/*"` — backend total 91%, 6059 statements, 544 missed.

## Что закрыто бизнес-тестами

- Seed/import contract: production profile, QR/PvE/check policy, buildings/units, orders, Gwent cards/decks, trade transfers, tokens/throttle, reputation, XP, spells, favorites, reward approvals, final summary, paper forms.
- Seed diagnostics: empty fixture manifest, unknown override file, CSV extra columns, missing id column, empty CSV, missing id value, duplicate id with row/record context.
- FastAPI contracts: static lord entrypoints, auth negative paths, player snapshot secret filtering, QR lookup errors, event sync, master act/timer/backup routes, PvP wrappers, lord battle listing/errors, sorceress/potion/trade/favorite/alignment routes.
- Offline event sync/snapshot: actor validation, idempotency by `event_id`, client-requested master review, unsupported events, reward lookup, invalid/valid act unlock, act unlock gates, QR honesty/manual review, revealed unlock code propagation into scoped mobile snapshot, PvE field validation and replay contract.
- Paper recovery: clean auto-apply, missing audit fields, duplicate/conflict review, unknown form type review, invalid timestamp rejection, corrupted `paper_forms.required_fields_json` routed to master review.
- PvE: single d20, modifiers log, physical presence, 30-minute cooldown, unique QR consume-once, future act physical announcement before server sync, replay mismatch variants, pending/auto reward side effects.
- Reward approvals: pending reward locks block PvP stake/trade/final summary use, approve/correct/reject lifecycle, corrected reward replacement, rejected lock release, missing audit reason rejection, duplicate same-action decision idempotency and conflicting final decision rejection.
- PvP/Gwent: challenge tokens/table flow, active challenge cap, start window timeout, refusals, no match time limit after start, deck validation, hand consumption, weather/horn/scorch/decoy, tie review, invalid finish review without stake transfer, stake lock reuse, final-lock master override without normal token spend, malformed deck state, Stage 2 custom card rejection, personal-card conversion rejects.
- Sorceress runtime: mana spend/no-spend, target validation, final-lock magical intent review, potion stock/gold/price bands, one potion per scene, trade consent/locks, trade terminal idempotency/errors, favorites consent/idempotency/errors, alignment evidence/errors.
- NPC/reputation runtime: Good/Evil threshold visibility, King/Wanderer events, hidden prices, severity P0/P1 review routes, rejection of missing NPC role/type, unsupported severity rejection and prevention of reputation deltas for non-witcher/non-sorceress targets.
- Lord runtime/battle: route MP spend, contested claims, pending tick awards, hidden foreign garrisons, building prerequisites/cross-deps, recruit hold/purchase/reserve spawn, reserve-to-active only at residence, raid/anti-snowball, order caps/object conflict, create/auth guardrails, neutral and lord-vs-lord flows, deployment, idempotent action retry by `action_id`, missing attacker/defender, 5x6 movement/LoS/damage/retaliation, hero attack guardrails and damage, timeout auto-resolve, deterministic auto-resolve tie, surrender, no-retreat-node audit, neutral AI movement fallback, capture handoff, HP formula, corrupted active-stack diagnostics.
- Operational backup: manual backup API success, pre-final backup before final act, fallback from unknown transition trigger to configured manual job, backup artifact manifest with SQLite/event-log payload, failed manual backup job recorded as `needs_master_review`.
- Final summary: master-led evidence aggregation, no automatic winner calculation, final lock order policy, paper/NPC/magical-intent evidence, persisted master notes and rejection of empty final master notes.

## Оставшиеся непокрытые зоны и почему

### `lord_runtime.py`, `lord_battle_service.py`, `pvp_service.py`, `sorceress_service.py`

Крупные игровые сервисы остаются в диапазоне 87-89%. Непокрытые строки в основном относятся к редким negative/resilience веткам: поврежденные persisted JSON/state tables, отсутствующие seed-таблицы, fallback rules без импортированного контента, unsupported unit/card/effect branches, дополнительные capture/claim variants, редкие idempotency/error paths и low-level helper errors.

Почему не закрыто полностью: эти ветки требуют искусственно ломать БД или seed-контент. Это полезно для robustness, но уже слабее доказывает основную бизнес-логику, чем добавленные end-to-end сценарии.

Риск: средний для operational resilience, низко-средний для обычного игрового дня.

### `pve_runtime.py`, `event_service.py`, `validation.py`

PvE/event/validation покрыты ключевыми игровыми контрактами. `validation.py` вырос до 94%, `csv_loader.py` до 97%; оставшиеся строки — parsing/helper/table-missing ветки, OSError fallback при чтении reference headers, отдельные low-level traversal branches и редкие side-effect fallbacks.

Почему не закрыто полностью: основная offline/PvE бизнес-логика уже проверяется через реальные sync/runtime paths; оставшееся ближе к диагностике поврежденного импорта.

Риск: средний для качества диагностики и recovery, низкий для happy-path PvE.

### `app.py`

После HTTP-contract слоя покрытие `app.py` выросло до 95%. Оставшиеся строки — в основном повторяющиеся `try/except` wrappers, отдельные authorization negatives и response-shape branches поверх сервисов, которые уже проверены напрямую.

Почему не закрыто полностью: дальнейшее добивание `app.py` даст много похожих API negative tests с низкой новой бизнес-ценностью.

Риск: низкий для правил игры, средний для полной формализации API-контракта.

### Инфраструктура

`backup_service.py` теперь покрыт до 99%; единственная непокрытая строка — отсутствие таблицы `backup_jobs`, то есть поврежденная/неполная runtime-схема, а не штатный импортированный seed. `csv_loader.py`, `snapshot_exporter.py`, `repository.py`, `config.py`, `content_schema.py` по-прежнему содержат непокрытые filesystem/env/error/fallback ветки.

Почему не закрыто полностью: эти проверки требуют симулировать OS errors, отсутствующие файлы/таблицы и backup edge cases. Это важно для эксплуатации, но не равно бизнес-логике игры.

Риск: низкий для игровых правил, средний для operational reliability.

## Стоит ли продолжать

До 90% backend coverage был смысл продолжать: добавленные тесты закрывали реальные бизнес и API-контракты, а не только проценты. Дальше отдача снижается. Следующий осмысленный шаг — не бесконечно добивать coverage, а выбрать один конкретный риск:

1. remaining lord battle resilience: defender-held claim/capture variants, unsupported unit class and low-level actor/auth helper errors.
2. remaining import/validation diagnostics: OSError/reference-header fallback, deeper cycle traversal branches and malformed JSON fixture variants.
3. operational reliability: snapshot/export filesystem failures and restart-recovery edge cases beyond already-covered backup fallback/missing-job review.

Без такого фокуса дальнейшее покрытие будет в основном числовым упражнением, а не существенным ростом уверенности в бизнес-логике.
