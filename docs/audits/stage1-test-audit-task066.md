# TASK-066 Stage 1 Fresh Regression Test Audit

Дата: 2026-06-03.

## Почему старая зеленая suite пропустила свежие баги

- PvE d20 проверялся как наличие `roll_log` и happy-path результата, но не как неизменяемый app-generated check: повторный event с тем же `check_id` и измененный roll не были отдельными регрессиями.
- PvE modifier/stat authority был слабым на клиентские подмены: suite могла принять `result=success`, если smoke видел валидный сценарий, но не перепроверял server-derived modifiers, canonical stat и отсутствие side effects при review.
- QR/act secrecy проверяла актовый unlock в позитивном сценарии, но не доказывала, что future-act QR lookup и player snapshot не раскрывают `scenario_id`, manual code/hash и unlock secret до физического объявления/reveal.
- Mobile fallback был покрыт source-string проверками Godot queue, но не доказывал через `/api/events/sync`, что сервер доверяет auth header, а не payload actor, и что duplicate/idempotency не ломает `client_sync_state`.
- PvP/Gwent tests раньше фокусировались на успешном матче: non-owned stake, no-side-effect failure и losing participant winner override не были обязательным Stage 1 regression evidence.
- Lord runtime smoke видел движение и orders happy path, но не доказывал, что invalid weighted route не списывает MP, а order escrow реально резервирует и возвращает ресурсы.
- Review/reputation checks были разнесены: не было единого теста, что player не может закрыть master review, master correction создает `master_corrections` и side effect, а Good/Evil reputation scoped только к ведьмакам/чародейкам.

## Новая regression matrix

- `tests/test_stage1_fresh_regressions.py::test_task059_060_pve_roll_and_modifier_bypasses_enter_review` покрывает TASK-059 и TASK-060: first app roll accepted, duplicate same `check_id` goes to review, changed d20 for same `check_id` goes to review, forged client modifier goes to review, and only the valid attempt creates `pve_attempts`.
- `tests/test_stage1_fresh_regressions.py::test_task061_062_future_act_secrecy_and_mobile_sync_auth_contract` покрывает TASK-061 и TASK-062: future-act QR response is locked without scenario/manual payload, scoped snapshot hides unlock secrets, sync uses authenticated player context over forged payload actor, and duplicate sync is idempotent.
- `tests/test_stage1_fresh_regressions.py::test_task063_064_pvp_stakes_winner_lord_route_and_escrow_are_authoritative` покрывает TASK-063 и TASK-064: non-owned stake rejects without token/challenge side effects, loser winner override goes to review without stake transfer, invalid route preserves MP, and order escrow reserve/cancel updates ledger and domain gold.
- `tests/test_stage1_fresh_regressions.py::test_task065_review_corrections_and_reputation_are_master_scoped` покрывает TASK-065: player review attempt is rejected, master correction records `master_corrections` and applies the corrected PvE side effect, foreign reputation read is forbidden, player view hides numeric value, master view sees it, and lord reputation mutation is rejected.

## Manual/device gaps kept out of green pytest

- Real Android/iOS install-launch-camera QR smoke remains TASK-001/TASK-018 or Stage 2B hardware evidence, not automated proof.
- Venue-like Wi-Fi outage, four physical lord panels and real phone restart/sync remain launch/rehearsal checks.
- Visual browser interaction quality for lord/mobile surfaces remains a UI/device gate; automated tests here prove API/state contracts and static serving, not tactile usability.
- TASK-018 must treat any missing real-device evidence as named launch-risk/manual acceptance evidence instead of substituting this green regression suite.
