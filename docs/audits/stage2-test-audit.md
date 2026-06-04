# Stage 2 test audit

Дата: 2026-06-03.

Цель: зафиксировать, какие green tests пропустили замечания Stage 2 code
review, и какие regression/contract tests теперь считаются заменой слабых
проверок перед `TASK-050`.

## Карта регрессий

| Review issue | Старая слабая проверка | Новая/усиленная проверка |
| --- | --- | --- |
| PvE reward forgery: клиент мог прислать чужой `reward_id` или каскадную награду без server authority. | `tests/test_event_sync.py::test_pve_completion_without_replayable_roll_log_needs_review` проверял только наличие roll log; smoke не проверял, что награда берется из сценария и не применяется при mismatch. | `tests/test_event_sync.py::test_pve_completion_rejects_forged_reward_id_without_applying_reward`, `tests/test_pve_runtime.py::test_missing_client_reward_id_uses_scenario_bound_auto_reward`, `tests/test_pve_runtime.py::test_scenario_bound_pending_reward_creates_approval_lock_once`, `tests/test_reward_approvals.py::test_second_pending_reward_for_same_asset_routes_to_review_without_double_lock`. |
| One-sided Gwent round: один участник мог закрыть round без второго игрока. | `tests/test_pvp_runtime.py::test_api_full_gwent_rounds_finish_and_duplicate_result` был happy path через master payload и не моделировал два мобильных клиента; `tests/test_stage1_fresh_regressions.py::test_task063_064_pvp_stakes_winner_lord_route_and_escrow_are_authoritative` закреплял старый one-sided round в broader regression. | `tests/test_pvp_runtime.py::test_api_player_gwent_round_waits_for_opponent_submission`, `tests/test_pvp_runtime.py::test_api_master_incomplete_gwent_round_goes_to_review_without_stake_transfer`; Stage1 fresh regression rewritten to use both participants before asserting match winner. |
| Non-owned personal card conversion: игрок мог конвертировать карту, которой не владеет, или pending reward card. | Старый API smoke проверял неизвестного лорда/статус ответа, но не состояние ownership, reserve и locks. | `tests/test_pvp_runtime.py::test_personal_card_conversion_rejects_non_owned_card_without_minting`, `tests/test_pvp_runtime.py::test_personal_card_conversion_rejects_pending_reward_locked_card`, `tests/test_pvp_runtime.py::test_api_personal_card_to_lord_conversion_is_permanent_and_idempotent`. |
| Reserve-to-fort teleport: reserve мог попасть в удаленный fort без active army на территории. | Lord panel contract проверял наличие garrison form и один movement call, но не локальность армии и не сохранность reserve. | `tests/test_lord_runtime.py::test_movement_without_active_army_cannot_create_contested_claim`, `tests/test_lord_runtime.py::test_local_active_army_fort_transfers_reject_remote_reserve_and_contested_state`, `tests/test_lord_panel_contract.py::test_lord_panel_action_controls_execute_role_scoped_apis`. |
| Lord order impersonation: лорд мог принять/сдать/закрыть заказ за игрока. | Order tests проверяли cap/conflict happy path, но не auth boundary для player actions. | `tests/test_lord_runtime.py::test_order_caps_object_conflict_success_race_and_escrow_release` теперь проверяет lord impersonation accept/submit/complete, player mismatch and master-only completion. |
| Bad generated seed validation: cross-row ошибки проходили через одиночные overlay tests. | `tests/test_seed_validation.py::test_business_policy_overlays_report_specific_validation_codes` ловил простые single-file policies, но не QR scenario act mismatch, domain/token role mismatch и canonical battle rule drift. | `tests/test_seed_validation.py::test_task073_business_validation_rejects_cross_row_seed_breaks`, fixture overlays under `tests/fixtures/seed_invalid_*`. |

## UI and manual gaps

| Gap | Статус после аудита |
| --- | --- |
| Admin paper recovery | Backend recovery уже покрыт `tests/test_paper_recovery.py`; Admin contract дополнен `tests/test_admin_studio_contract.py::test_admin_paper_recovery_uses_master_sync_and_conflict_review`, который идет через `/api/events/sync` с master role token, проверяет trusted actor context, `source=paper_recovered` и review for conflicting `paper_lord_battle`. |
| Lord battle UI | `tests/test_lord_panel_contract.py::test_lord_panel_action_controls_execute_role_scoped_apis` теперь не ограничивается строками в HTML: он создает lord battle через role token, проверяет 5x6 board, owner isolation и выполняет battle action. Runtime глубина остается в `tests/test_lord_battle_runtime.py`. |
| Mobile QR camera | Native camera scan нельзя честно доказать в pytest без target Android/iOS device and scanner plugin. Это explicit manual blocker, not a green test: `mobile/README.md` names target-device plugin smoke; `docs/app-technical-plan-v0.1.md` keeps `launch-risk: qr-camera` and ties real-device proof to `TASK-047`/`TASK-058`/`TASK-050`. Manual fallback через opaque manual ID не засчитывается как camera proof. |
| Four-lord/browser smoke | API-level coverage is `tests/test_lord_panel_contract.py::test_all_four_lord_panels_can_load_their_own_state`; real simultaneous browser/LAN smoke remains Stage 2B evidence in `TASK-050`/`TASK-058`, not a substituted pytest. |

## Acceptance rule

После этого аудита Stage 2B не должен принимать green suite как доказательство
реального device/browser smoke. Pytest ловит server authority, state transitions
и static contract regressions; camera QR, четыре реальные lord panels и LAN
browser/device evidence остаются ручными gate-блокерами до `TASK-050`.

## TASK-080 completion matrix

This section is the explicit TASK-080 audit map. It names every TASK-075
through TASK-079 issue class, the weak pre-audit coverage, and the behavior
regression that now supersedes it.

| Issue class | Weak test that missed it | Superseding behavior regression |
| --- | --- | --- |
| TASK-075 paper recovery side effects | Metadata-only paper recovery checks could pass while no PvE reward, XP/gold or attempt was applied. | `tests/test_paper_recovery.py::test_clean_paper_recovery_auto_applies_as_audited_paper_source` and `tests/test_admin_studio_contract.py::test_admin_paper_recovery_uses_master_sync_and_conflict_review` assert `player_runtime_state`, `pve_attempts`, `source=paper_recovered`, duplicate review and conflict review. |
| TASK-075 event-sync role scope | Auth tests trusted submitted `actor_type` shortcuts instead of seeded role/code authority. | `tests/test_event_sync.py::test_player_only_sync_events_use_canonical_role_scope`, `tests/test_mobile_shell_contract.py::test_mobile_sync_uses_authenticated_actor_not_payload_identity` and `tests/test_fastapi_contract.py::test_event_sync_uses_role_token_identity_over_payload_actor_fields` use real role tokens/codes and assert canonical role rejection/review. |
| TASK-076 cross-lord order race | Order tests only covered same-lord object conflicts and happy-path escrow. | `tests/test_lord_runtime.py::test_cross_lord_order_race_closes_competitors_and_refunds_escrow` creates competing orders from different lords, completes one through master review, closes the loser and proves escrow refund/no double award. |
| TASK-076 PvP gold stakes | Stake tests focused on item ownership/locks, not gold debit/refund/settlement. | `tests/test_pvp_runtime.py::test_gold_stakes_reserve_refund_settle_and_reject_insufficient_balance` checks upfront gold reserve, safety refund, insufficient-balance no-op, winner settlement and duplicate finish idempotency. |
| TASK-077 lord panel blockers | Static UI contract could pass with raw JSON battle/action forms or missing captured-territory garrison targets. | `tests/test_lord_panel_contract.py::test_lord_panel_action_controls_execute_role_scoped_apis`, `test_capture_pending_foreign_territory_is_garrison_target_from_panel` and `test_lord_battle_panel_uses_board_controls_without_raw_json_acceptance` execute role-scoped APIs, assert 5x6 board controls and reject raw JSON/action-form acceptance. |
| TASK-078 Admin blockers and Game Ops | Admin smoke checked page sections but not typed recovery, master auth context, event sync status, economy state or day-ops mutations. | `tests/test_admin_studio_contract.py::test_admin_paper_recovery_uses_master_sync_and_conflict_review`, `test_game_ops_dashboard_state_and_mutations_cover_day_ops` and `tests/test_game_ops_service.py::*` assert typed paper recovery, trusted master context, anti-snowball/economy payloads, review/reward/throttle/correction/backup state and mutation side effects. |
| TASK-079 mobile reputation leak | Snapshot/mobile checks hid secret tables but did not prove exact Good/Evil value and changelog were absent from player scope. | `tests/test_snapshot_exporter.py::test_player_scoped_snapshot_hides_exact_reputation_value` and `tests/test_mobile_shell_contract.py::test_mobile_character_ui_uses_descriptive_reputation_only` assert descriptor-only `reputation_state`, no numeric value/changelog, and mobile UI avoids direct `player.reputation` rendering. |

Manual-only evidence remains explicit: real Android/iOS QR camera smoke, four
simultaneous lord laptops and local Wi-Fi/browser smoke are TASK-058/TASK-050
blockers. They are not counted as proven by green pytest.
