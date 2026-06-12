# TASK-057 Stage 1 Test Audit

Дата: 2026-06-03.

## Почему старая зеленая suite пропустила баги

- Часть mobile/lord-panel проверок была source-string smoke: тест видел, что в файле есть нужный текст или форма, но не доказывал auth scope, state transition и side effects.
- Stage 1 gate закрывал много happy-path шагов одним scripted flow, но некоторые P0/P1 негативные ветки оставались в отдельных unit tests или вообще не были привязаны к gate evidence.
- Несколько проверок шли через internal service helpers. Это полезно для unit-level формул, но не ловит ошибки FastAPI auth boundary, role token/path mismatch и client payload spoofing.
- Финальная сводка раньше могла быть проверена как "есть locked_magical_intent", что не ловит global-any bug: один locked intent не должен закрывать missing lock у другой чародейки.

## Чем новая regression matrix отличается

- TASK-051 auth/secret boundary: behavioral API tests теперь проверяют authenticated actor context, master-only event rejection/audit, foreign path/payload rejection, scoped lord battle visibility и отсутствие секретов в snapshot/mobile artifacts.
- TASK-052 offline PvE/QR/act unlock: tests cover hidden unlock secrets, revealed-code positive path, early/future unlock negatives, replayable single-d20 validation, physical presence review, QR manual rate limit и server-owned cooldown.
- TASK-053 rewards/assets/paper: tests cover pending reward locks before PvP/trade/final use, duplicate asset locks, paper recovery duplicate/conflict routing and paper side-effect paths.
- TASK-054 PvP/Gwent: tests cover deck/effect preflight before token/table/stake side effects, card-in-hand validation, best-of-3 stake transfer, tie/refusal/timeout/deferred cleanup and idempotent finish.
- TASK-055 lord runtime: tests cover role-scoped lord panel APIs, route/battle/garrison capture prerequisites, influence/timer ticks, pending tick outcomes, recruit refresh and proactive 60s timeout before ordinary battle action.
- TASK-056 sorceress/final locks: tests cover runtime-owner mana, sorceress auth/scoping, favorite visibility/consent, restart/export evidence and per-sorceress locked_magical_intent/missing_locks in Stage 1 gate.

## Оставшиеся manual-only gaps

- Реальные Android/iOS install-launch-camera QR smoke, local Wi-Fi/LAN outage behavior on venue hardware and four physical lord panels remain launch/rehearsal evidence, not automated proof.
- Browser visual interaction moved to the current React/Vite lord frontend; deleted FastAPI-static lord UI must not be used as acceptance evidence.
- These manual checks belong to TASK-001/TASK-018 launch-risk or rehearsal notes; they should not replace the automated TASK-051 through TASK-056 regression suite.
