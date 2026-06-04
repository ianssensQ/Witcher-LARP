# Stage 1 + Stage 2 code audit supplement

Дата: 2026-06-04 12:35 +03:00.

HEAD: `4798e77`.

Dirty status: перед записью этого supplement и coverage matrix рабочее дерево было чистым.
После записи артефактов ожидаемо изменены только:

- `docs/audits/stage1-stage2-code-audit-supplement.md`
- `docs/audits/stage1-stage2-business-coverage-matrix.md`

## Baseline Used

Baseline: `docs/audits/stage1-stage2-code-audit.md`.

Baseline findings `AUD-001`..`AUD-005` использованы как уже известные и не
дублировались. Baseline был создан для более раннего `HEAD 317e9c1`; этот
supplement проверяет текущий `HEAD 4798e77` поверх baseline.

## Method And Context Strategy

- Сначала прочитаны только `AGENTS.md`,
  `docs/audits/stage1-stage2-code-audit.md` и `docs/active-tasks.md`.
- Канонические документы не открывались целиком. Требования подтверждались
  точечно через `rg -n`, затем открывались только маленькие фрагменты.
- Запущена ровно одна волна из 4 субагентов: Business Logic,
  Backend/Auth/Visibility, Sync/Recovery/Offline и Tests/TaskOS Scope.
- Главный агент дедуплицировал кандидатов и вручную перепроверил каждую новую
  находку в коде.
- Код, `tasks.json`, generated views и `docs/core-engine-v1.2.md` не
  редактировались. TaskOS-задачи не создавались.
- Stage 2B UI pending считался границей: отсутствие полноценного mobile/lord
  или personal Gwent UI не включалось как баг Stage 1/2/2A.

## Baseline Issues Not Duplicated

- `AUD-001` P1: offline act unlock не работает из pre-game snapshot.
- `AUD-002` P1: non-PvE paper recovery не восстанавливает domain state.
- `AUD-003` P1: player snapshot раскрывает `final_hooks` до reveal.
- `AUD-004` P2: mobile sync мапит `rejected` в `needs_master_review`.
- `AUD-005` P2: `/api/pvp/tables` без auth раскрывает queue/stakes.

## New Findings

### AUD-NEXT-001 - P1 - Attacker capture can leave defeated defender garrison active

Severity: P1

Source requirement:

- `docs/architecture.md:371` - lord battle includes surrender, hero HP result,
  persisted losses and capture/garrison settlement.
- `docs/architecture.md:375` - battle verification includes
  retreat/capture/garrison after lord battle result.

Code/data/test location:

- `backend/witcher_larp/lord_battle_service.py:750` finishes battle through
  losses, retreat and capture.
- `backend/witcher_larp/lord_battle_service.py:803` decrements only casualties
  from `garrison_runtime_state`.
- `backend/witcher_larp/lord_battle_service.py:874` retreats surviving losing
  active army only, not fort garrisons.
- `backend/witcher_larp/lord_battle_service.py:914` sets attacker victory to
  `capture_pending_garrison` without deactivating surviving defender garrisons.
- `backend/witcher_larp/lord_runtime.py:432` adds the attacker garrison, and
  `backend/witcher_larp/lord_runtime.py:439` changes territory owner, but does
  not clear old active foreign garrisons.
- Existing lord battle tests cover capture handoff and defender victory, but do
  not assert that losing defender garrisons are removed/reviewed after attacker
  victory.

Expected:

When an attacker wins a territory battle by surrender, hero HP or unit wipe, the
losing defender fort garrison must be settled before ownership changes:
destroyed, retreated by explicit rule, or routed to master review.

Actual:

Surviving defender garrisons remain `active`. The attacker can then complete
the capture by placing a new garrison and flipping `owner_domain_id`, leaving an
active foreign garrison in the captured territory.

Gameplay impact:

Lord state becomes contradictory: the new owner controls the territory while the
old owner still has active hidden military power in the same fort. This can
distort hidden garrison visibility, army power, final summary and later
capture/defense decisions.

Recommendation:

During attacker capture settlement, deactivate, burn, retreat or explicitly
review every losing-side garrison in the territory before allowing
`capture_pending_garrison` to become `controlled`. Add regression coverage for
surrender/hero-HP capture with a surviving defender garrison.

Confirmation method:

Create a lord-vs-lord battle on `territory_res_river`, force attacker victory
while `garrison_river_home` survives, complete attacker garrison handoff, then
query active garrisons for that territory. Expected: no active defender garrison
remains without review.

### AUD-NEXT-002 - P2 - `/api/qr/lookup` is unauthenticated and trusts caller-supplied player identity

Severity: P2

Source requirement:

- `docs/PRD.md:71` - QR/manual ID use requires physical presence and чужой or
  off-location use must block to master review.
- `docs/app-technical-plan-v0.1.md:92` - mobile flow begins with player-code
  login, snapshot and character display before QR/manual input.
- `docs/architecture.md:349` - server sync checks QR/manual ID policy,
  physical-presence honesty policy and act availability.

Code/data/test location:

- `backend/witcher_larp/app.py:69` accepts `player_id` and `device_id` in the
  QR lookup body.
- `backend/witcher_larp/app.py:413` exposes `POST /api/qr/lookup` without
  `X-Player-Code` or `X-Role-Token`.
- `backend/witcher_larp/app.py:420` passes caller-supplied `player_id` into
  `QrLookupRequest`.
- `backend/witcher_larp/qr_runtime.py:57` performs lookup and rate-limit
  decisions from that request.
- `backend/witcher_larp/qr_runtime.py:328` writes `qr_attempts` and `event_log`
  rows under the supplied `player_id`.
- `tests/test_fastapi_contract.py` calls `/api/qr/lookup` without auth in
  multiple contract tests.

Expected:

Player QR/manual lookup should require authenticated player-code context and
derive `player_id` from that auth. Anonymous diagnostics, if kept, should be
non-mutating and should not return player-scoped scene payload or write
player-scoped audit rows.

Actual:

Any device on the local network can submit a known QR/manual code, claim any
`player_id`, receive QR/scenario/event context, and write attempts/log rows
under the claimed identity.

Gameplay impact:

Players can preview scene and reward mechanics from observed/shared codes and
can pollute another player's QR attempt history or manual-rate-limit review
state. This weakens physical-presence and чужой-QR controls even though final
PvE event sync remains separately authenticated.

Recommendation:

Require player-code auth for `/api/qr/lookup`, overwrite body identity from
auth, and keep master/diagnostic lookup on a separate scoped endpoint if needed.
Add tests for missing auth, wrong player spoofing and authenticated attempt
ownership.

Confirmation method:

Call `/api/qr/lookup` without auth using `player_id=p_witcher_1`; expected
future behavior is `401` and no `qr_attempts` row. Then call with
`X-Player-Code: WC-WOLF-6GF4` and verify the attempt is recorded as
`p_witcher_1` regardless of body identity.

### AUD-NEXT-003 - P2 - Player-code auth response leaks exact numeric reputation

Severity: P2

Source requirement:

- `docs/app-technical-plan-v0.1.md:94` - player sees descriptive reputation and
  hidden final hooks only after reveal.
- `docs/PRD.md:97` and `docs/PRD.md:163` - players see only descriptive
  Good/Evil state, while masters see exact value and reason log.
- `docs/architecture.md:213` - master sees exact reputations.

Code/data/test location:

- `backend/witcher_larp/app.py:461` returns player-code auth payload.
- `backend/witcher_larp/app.py:1897` builds the auth identity.
- `backend/witcher_larp/app.py:1936` includes raw `player["reputation"]`.
- `backend/witcher_larp/snapshot_exporter.py:53` treats `reputation` as a
  private player key.
- `backend/witcher_larp/snapshot_exporter.py:380` projects players through a
  redacted `reputation_state`.
- `tests/test_fastapi_contract.py:145` checks the auth response does not expose
  the secret player code, but does not check reputation redaction.

Expected:

Player-code auth should return identity and permissions only, or the same
redacted `reputation_state` used in player snapshots.

Actual:

The auth response includes a nested `player` object with raw numeric
`reputation`.

Gameplay impact:

A player can see the exact hidden Good/Evil scalar and optimize around
thresholds, NPC consequences and final reputation signals instead of seeing only
the intended descriptive state.

Recommendation:

Sanitize `_authenticate_player_code` with the same public player projection used
by snapshots, or remove the nested raw `player` object and let the client fetch
the scoped snapshot after auth.

Confirmation method:

Add an API regression test for `/api/auth/player-code` asserting that neither
`payload["player"]["reputation"]` nor any exact `value` field is present, while
descriptive `reputation_state` is available if player reputation is included.

### AUD-NEXT-004 - P2 - Rejected paper recovery attempts poison later corrected input for the same paper form

Severity: P2

Source requirement:

- `docs/architecture.md:323` - `paper_recovered` is a recovered event that
  passes the same idempotency/conflict checks.
- `docs/architecture.md:343` - paper recovery must not silently overwrite
  digital state; conflicts go to review.
- `docs/architecture.md:449` and `docs/app-technical-plan-v0.1.md:620` - paper
  forms are applied through ordinary checks or routed to review.

Code/data/test location:

- `backend/witcher_larp/event_service.py:539` handles `paper_recovered`.
- `backend/witcher_larp/event_service.py:575` rejects missing fields or bad
  timestamps before duplicate handling.
- `backend/witcher_larp/event_service.py:592` checks duplicate `paper_form_id`.
- `backend/witcher_larp/event_service.py:1123` scans all prior
  `paper_recovered` events regardless of status.
- `tests/test_paper_recovery.py:115` covers readable rejection diagnostics.
- `tests/test_paper_recovery.py:220` covers duplicate/conflict routing after
  an already reviewable paper event, but not rejected-then-corrected intake.

Expected:

A malformed/rejected paper intake, such as a bad timestamp or missing operator,
should not reserve the `paper_form_id`. A corrected clean intake for the same
physical form should proceed through normal recovery checks.

Actual:

The first rejected `paper_recovered` row remains in `events`. Later corrected
input with the same `paper_form_id` is treated as a duplicate and routed to
`needs_master_review`.

Gameplay impact:

A master typo during outage recovery can turn an otherwise clean recovery into
manual review. For PvE this can break the one paper form type that currently
auto-applies; for non-PvE it compounds baseline `AUD-002` by adding extra
master load and ambiguity.

Recommendation:

Exclude prior `rejected` rows from paper duplicate detection, or distinguish
invalid intake attempts from accepted/reviewable recovered-form claims.

Confirmation method:

Submit `paper_pve_result` with `paper_form_id=paper-x` and invalid timestamp,
then resubmit the same form with a valid timestamp. Expected future behavior:
the corrected event is `accepted` and PvE side effects apply once.

### AUD-NEXT-005 - P2 - Player-controlled `mandatory=false` bypasses PvP token pacing and started-match cap

Severity: P2

Source requirement:

- `docs/architecture.md:355` - server verifies challenge token; each witcher
  and sorceress receives 3 challenge tokens per story act, and PvP throttle
  enforces per-act started mandatory match cap.
- `docs/PRD.md:139` - the 3 challenge tokens per act rule is part of personal
  PvP/Gwent volume control.

Code/data/test location:

- `backend/witcher_larp/app.py:285` exposes `mandatory` in the player challenge
  payload.
- `backend/witcher_larp/app.py:1450` passes `payload.mandatory` directly into
  challenge creation.
- `backend/witcher_larp/pvp_service.py:273` spends a challenge token only when
  `request.mandatory` is true.
- `backend/witcher_larp/pvp_service.py:2226` skips started-cap checks for
  non-mandatory challenges.
- `rg` found no regression that a normal player cannot create a full
  stake-locking `mandatory=false` challenge.

Expected:

Normal player-created full Gwent challenges should consume/validate the
challenge token budget, or `mandatory=false` should be master-only/admin-only
with separate non-match semantics.

Actual:

An authenticated player can create a full stake-locking, table-assigning PvP
challenge with `mandatory=false`; no token is spent and started mandatory cap is
bypassed.

Gameplay impact:

PvP volume and table pressure can exceed the 15-person pacing model. Players can
create additional full Gwent matches and stake locks outside the intended token
budget.

Recommendation:

Require token spend for all ordinary player-created full PvP challenges, or
restrict `mandatory=false` to master-approved flows and make that branch
explicit in tests and UI contracts.

Confirmation method:

POST `/api/pvp/challenges` with a valid player code and `"mandatory": false`;
verify the challenge is assigned or queued and `player_runtime_state.challenge_tokens`
does not decrement. Future expected behavior should reject or master-gate this
path.

### AUD-NEXT-006 - P2 - Queued PvP challenges still count as active and can block the target before a table exists

Severity: P2

Source requirement:

- `docs/PRD.md:77` - PvP throttling says queued challenges do not block the
  target/goal, while started mandatory matches are capped per player per act.
- `docs/architecture.md:260` and `docs/architecture.md:355` - PvP runtime has
  queued behavior, active challenge cap, table assignment and throttle.

Code/data/test location:

- `backend/witcher_larp/pvp_service.py:23` includes `queued` in
  `ACTIVE_CHALLENGE_STATES`.
- `backend/witcher_larp/pvp_service.py:237` and `:239` reject new challenges if
  challenger or target has an active challenge.
- `backend/witcher_larp/pvp_service.py:2854` implements that active check using
  all `ACTIVE_CHALLENGE_STATES`, including `queued`.
- `tests/test_pvp_runtime.py:2068` covers queued start-window timing, but not
  the non-blocking target/goal behavior.

Expected:

A queued challenge that has no assigned table and no start window should not by
itself block the target/player/object from other valid PvP flow, unless the
design explicitly treats queued as an active engagement.

Actual:

Queued challenges are considered active for both challenger and target. A queued
challenge can therefore block another challenge involving the same player before
a table exists or the 30-minute window starts.

Gameplay impact:

Under limited/paused tables, queued challenges can be used as a soft denial or
can stall object/interception pressure despite the queue being intended as a
throttle buffer rather than a live match.

Recommendation:

Clarify queued semantics and enforce them in code: either remove `queued` from
the active-player blocker, or add an explicit master/timeout policy that makes
queued blocking visible and bounded.

Confirmation method:

Set PvP throttle to `limited`, create one assigned challenge and one queued
challenge involving `p_witcher_3`, then attempt another valid challenge involving
`p_witcher_3`. Expected future behavior should match the documented
non-blocking queue policy.

## Checked Without New Issues

- Production profile seed/validation for 4 lords, 4 sorceresses, 5 witchers and
  2 NPC masters.
- Act schedule, timers, physical announcement gates, final lock timer and
  backup hooks.
- Master/lord auth boundaries for Admin Studio, master state, lord panels,
  lord battle list/get/actions, review queue, rewards, corrections, backups and
  final summary.
- Player-scoped snapshots hide player codes, role tokens, exact reputation and
  hidden goal flags. Baseline `AUD-003` remains the known final-hook exception.
- Offline PvE sync authority: single d20 replay, QR/scenario checks, cooldown,
  unique consumption, reward approval locks and event idempotency.
- Reward approval locks and asset locks for cascade-prone rewards, trade,
  stakes and finalization.
- Gwent deck/hand/mulligan/round/effect/winner/stake settlement logic, except
  the PvP token/queue issues listed above.
- Trade transfers and potion transfers: two-party lock/accept/decline,
  idempotency and ownership movement.
- Lord route/MP movement, fort transfer, building, recruit, raid, order caps
  and order escrow, except the lord-battle capture/garrison issue above.
- Sorceress mana, potion economy, transfer pricing, consent favorites,
  alignment evidence and locked magical intent behavior.
- Reputation read endpoints are scoped to own player or master and hide exact
  values from ordinary player responses; the new leak is limited to player-code
  auth payload.
- NPC hidden prices, master-led final summary, missing locks, final notes and
  no automatic winner calculation.
- Backup/restart persistence evidence and TaskOS Stage 2A remediation evidence.

## Out Of Scope

- Full Stage 2B playable mobile UI, lord action UI and personal Gwent UI.
- Android/iOS real-device camera QR scan, install smoke and second-laptop LAN
  proof.
- Cosmetic, visual polish, copy, minor UX and UI layout gaps.
- Any rewrite of `docs/core-engine-v1.2.md`.
- Creating TaskOS tasks or editing generated views.
- Re-auditing baseline findings `AUD-001`..`AUD-005`.

## Checks Run

- `uv run python scripts/taskctl.py validate` -> `tasks.json is valid (81 tasks)`.
- `uv run pytest -q` -> 221 passed, 1 warning, 224.61s.

