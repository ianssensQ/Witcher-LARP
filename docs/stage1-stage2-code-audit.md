# Stage 1 + Stage 2 code audit

Дата: 2026-06-04 11:13 +03:00.

Аудит проведен по текущему рабочему дереву на `HEAD 317e9c1` плюс
незакоммиченные изменения. Рабочее дерево уже было грязным до аудита; этот
файл является новым артефактом, код, `tasks.json` и generated views не
исправлялись.

Цель аудита: проверить существенное соответствие текущего кода продуктовой
логике Stage 1 Core Game Engine, Stage 2 Admin Studio и Stage 2A remediation.
Отсутствие полноценного Stage 2B Playable Role UI не считается багом этого
аудита, потому что `TASK-045`/`TASK-050` еще pending.

## Sources

- `docs/PRD.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/app-technical-plan-v0.1.md`
- `docs/active-tasks.md`
- `docs/admin-studio-acceptance-checklist.md`
- `docs/stage1-test-audit-task057.md`
- `docs/stage1-test-audit-task066.md`
- `docs/stage2-test-audit.md`
- `tasks.json`
- `progress.txt`
- `docs/core-engine-v1.2.md` used as historical context only

## Method

- Five independent read-only review slices were used: business logic,
  backend/API/runtime, player-facing UI surfaces, offline/sync/recovery, and
  TaskOS/test-scope.
- Findings from subagents were deduplicated and manually rechecked against
  source code before inclusion.
- No implementation fixes were made.
- Full automated suite was run after inspection: `uv run pytest -q` -> 221
  passed, 1 warning, 6:17.

## Executive Summary

No P0 issue was found.

Found 5 substantial issues:

- 3 P1 issues: offline act unlock cannot work from the pre-game snapshot,
  non-PvE paper recovery does not restore domain state, and player snapshots
  expose final hooks before reveal.
- 2 P2 issues: mobile sync UI conflates rejected events with real master
  review, and `/api/pvp/tables` exposes queued PvP challenge/stake details
  without authentication.

## Requirement Matrix

| Requirement area | Audit status |
| --- | --- |
| Production profile 15 total: 4 lords, 4 sorceresses, 5 witchers, 2 NPC masters | Covered by seed and validation. No issue found. |
| 3 story acts + Final Act, final lock, timers | Covered by seed, act service and timer tests. No issue found. |
| Player/role code auth for protected state/mutations | Mostly covered. One read endpoint leak remains: AUD-005. |
| Offline PvE: single d20, QR/manual honesty, cooldown, sync/review | Covered. No core authority issue found. |
| Offline act unlock via sync or master code/QR | Broken for true offline code path. See AUD-001. |
| Reward approval locks and cascade-prone rewards | Covered by event/reward tests. No new issue found. |
| Personal goals, goal tracks, hidden flags, final hooks | Goal flags are filtered, but final hooks leak. See AUD-003. |
| Good/Evil reputation visibility | Covered: exact value hidden from player, master sees exact/log. No issue found. |
| Personal PvP/Gwent runtime | Core runtime covered, but table queue endpoint leaks details. See AUD-005. |
| Trade transfers and asset locks | Covered by tests. No issue found. |
| Lord runtime: map, movement, garrisons, economy, orders, raids, battles | Core runtime covered by tests. No new issue found. |
| Sorceress runtime: mana, potions, spells, favorites, alignment | Covered by service/tests. No new issue found. |
| NPC/reputation/final summary | Core runtime covered; final hook player leak affects this area. See AUD-003. |
| Paper fallback/recovery | PvE auto-applies; other clean paper forms do not restore domain state. See AUD-002. |
| Admin Studio Stage 2 | Covered for localhost/API/static/browser smoke. LAN evidence remains manual Stage 2B/field evidence, not a code bug here. |
| Stage 2B player/lord UI-first gameplay | Out of scope for current code bug list because Stage 2B tasks are pending. |

## Issue Log

### AUD-001 - P1 - Offline act unlock cannot work from pre-game snapshot

Source requirement:

- `docs/PRD.md:58` - future acts unlock via house sync or master
  `act_unlock_code`/QR preloaded in snapshot and revealed after act start.
- `docs/app-technical-plan-v0.1.md:18` and `:97` - phones open next act through
  sync or master code/QR outside Wi-Fi.
- `docs/architecture.md:30`, `:150`, `:349` - offline unlock code path is part
  of mobile/offline design.

Code/data evidence:

- `backend/witcher_larp/snapshot_exporter.py:283` builds act unlock snapshot rows.
- `backend/witcher_larp/snapshot_exporter.py:302` only includes `code_sha256`
  when the code is already revealed.
- `backend/witcher_larp/snapshot_exporter.py:333` still advertises policy
  `server_sync_or_revealed_master_code`.
- `mobile/scripts/app_state.gd:701` only matches hashes from rows already
  accepted by `_find_revealed_act_unlock`.
- `tests/test_snapshot_exporter.py:176` and `:177` explicitly assert that the
  hidden snapshot contains neither raw code nor verifier/hash.

Expected:

Before game start, a phone can download a snapshot containing a non-disclosing
verifier for future act unlock codes. After the physical act announcement, a
master can reveal the code verbally/QR, and the phone can unlock the act while
still outside Wi-Fi. Server authority is rechecked later during sync.

Actual:

The pre-game player snapshot contains no code and no verifier for future acts.
The mobile client only accepts unlock rows already marked `revealed`, which
requires a server-side reveal and a new sync/snapshot before the offline phone
can validate the code.

Gameplay impact:

At Act 2/Act 3/Final transition, players outside Wi-Fi cannot use the promised
master code fallback. Mobile roles may be forced back to the house or pushed
into paper/manual intervention, creating idle time at the exact moment the game
needs a clean act transition.

Recommendation:

Add a preloaded non-secret verifier, e.g. salted/HMAC verifier or sealed
per-act token, to player-scoped snapshots. Keep raw codes hidden. Add a mobile
contract test: pre-reveal snapshot + typed master code + no server unlocks the
act locally and queues `act_unlocked_offline` for later server verification.

### AUD-002 - P1 - Non-PvE paper recovery does not restore domain state

Source requirement:

- `docs/PRD.md:110` - paper fallback covers PvP stake, lord action, lord battle,
  order resolution, NPC deal and final evidence.
- `docs/architecture.md:449` - after recovery, paper events are applied by
  normal idempotency/resource/ownership checks or routed to review; no silent
  overwrite.
- `docs/app-technical-plan-v0.1.md:620` - server creates
  `source=paper_recovered`, applies ordinary checks or sends conflict to
  review.

Code/data evidence:

- `data/seed/paper_forms.csv:4` through `:8` define non-PvE paper forms.
- `backend/witcher_larp/event_service.py:539` handles `paper_recovered`.
- `backend/witcher_larp/event_service.py:618` sets `paper_auto_applied = False`
  for all non-`paper_pve_result` forms and returns `needs_master_review`.
- `backend/witcher_larp/review_service.py:411` applies review side effects only
  for accepted `pve_completed` events.
- `backend/witcher_larp/review_service.py:424` explicitly says other event
  types have audit-only review closure.
- `tests/test_paper_recovery.py:294` codifies this by expecting clean non-PvE
  paper forms to require explicit domain review.

Expected:

A clean paper lord action, lord battle, order resolution, NPC deal or final
evidence form should either restore the corresponding authoritative game state
through existing domain services or be rejected/reviewed for a concrete
conflict.

Actual:

Only `paper_pve_result` auto-applies domain side effects. Clean non-PvE forms
become review records, and approving/correcting those reviews does not mutate
lord territory, battle result, order state, NPC deal state, PvP stake or final
evidence by itself.

Gameplay impact:

After Wi-Fi/server outage, paper play can diverge from authoritative SQLite
state. Masters may need ad hoc manual corrections under pressure, and
restart/export/final summary may not match what actually happened on paper.

Recommendation:

Implement a paper recovery dispatcher per form type using existing domain
services and idempotency keys based on `paper_form_id`. Review approval should
either apply the corrected domain mutation or require a linked explicit
correction. Add clean-apply regression tests for each supported paper form.

### AUD-003 - P1 - Player-scoped snapshot exposes final hooks before reveal

Source requirement:

- `docs/app-technical-plan-v0.1.md:94` - player sees known goals/tracks and
  hidden final hooks only after reveal.
- `docs/architecture.md:148` - mobile displays known personal goals, tracks and
  revealed final hooks without hidden goal flags.
- `docs/architecture.md:192` - master sees hidden goal flags, personal final
  hooks and final summary evidence.

Code/data evidence:

- `backend/witcher_larp/snapshot_exporter.py:503` builds player-scoped goals.
- `backend/witcher_larp/snapshot_exporter.py:527` includes every `final_hooks`
  row linked from that player's personal goals.
- `data/seed/personal_goals.csv:1` links every goal to a `final_hook_id`.
- `data/seed/final_hooks.csv:1` has no visibility/reveal column.
- A direct player snapshot check for `WC-WOLF-6GF4` returned
  `hook_witcher_contract` with `evidence_category=pve_contract` and
  final summary text.

Expected:

The player snapshot should contain public goal text and visible goal progress.
Final hook categories, hidden final summary text, NPC price/final-scene vectors
and master evidence categories should remain hidden until explicitly revealed.

Actual:

Player-scoped snapshots filter `goal_flags`, but include linked final hook rows
immediately.

Gameplay impact:

Players can infer final scoring/evidence vectors earlier than intended and
optimize personal goals, NPC deals, magical intent or final preparation using
master-side information. This weakens personal-goal mystery and master-led
final summary.

Recommendation:

Add reveal/visibility state for final hooks or split player-facing hint text
from master evidence rows. In `_scope_goals`, include final hooks only after
explicit reveal. Add regression tests: player snapshot hides unrevealed
final hooks, while master final summary still includes the complete evidence
bundle.

### AUD-004 - P2 - Mobile sync maps rejected events to master-review status

Source requirement:

- `docs/architecture.md:321` - `rejected` means event is impossible/invalid.
- `docs/architecture.md:322` - `needs_master_review` means event is saved and
  waits for master.
- `docs/app-technical-plan-v0.1.md:223` - server statuses include
  `accepted`, `rejected`, `needs_master_review`.
- `docs/architecture.md:160` - mobile sync statuses must be explicit.

Code/data evidence:

- `backend/witcher_larp/event_service.py:792` records review only for
  `needs_master_review` or explicit audit review.
- `mobile/scripts/app_state.gd:597` maps server `rejected`,
  `pending_master_approval` and `needs_master_review` all to local
  `needs_master_review`.
- `mobile/scripts/app_state.gd:1223` only counts local `needs_master_review`;
  there is no rejected count/status.

Expected:

Rejected events should be terminal and user-actionable: fix input, retry as a
new event, or ask a master outside the queue. Master review should only be
shown when a real review item exists.

Actual:

The mobile queue shows `rejected` events as `needs_master_review`. Some
rejected events have no master review row.

Gameplay impact:

A player can wait for a master to resolve an invalid QR/payload/actor mismatch
that the master never sees in the review queue. This is mostly UX/state clarity,
not authority corruption.

Recommendation:

Add `rejected_count` and a `rejected` local status. Reserve
`needs_master_review` for real review rows, and keep `pending_master_approval`
separate from both.

### AUD-005 - P2 - `/api/pvp/tables` exposes PvP queue and stakes without auth

Source requirement:

- `docs/PRD.md:139` - personal PvP includes stakes, challenge state and online
  zone flow.
- `docs/architecture.md:42` - player code enters snapshot/online PvP prep.
- `docs/architecture.md:177` - server validates role/player codes.
- `docs/architecture.md:355` and `:357` - PvP runtime includes challenge,
  table/queue/throttle, stake lock and result flow.

Code/data evidence:

- `backend/witcher_larp/app.py:1459` defines `GET /api/pvp/tables` without
  `X-Player-Code` or `X-Role-Token`.
- `backend/witcher_larp/pvp_service.py:177` returns table state and queued
  challenges.
- `backend/witcher_larp/pvp_service.py:2354` serializes each queued challenge
  with `challenger_id`, `target_id`, `stake_json`, assigned zone and deadline.
- `tests/test_pvp_runtime.py:354` calls `/api/pvp/tables` without auth and
  accepts the response.

Expected:

Aggregate table availability may be visible to authenticated players, but
participant and stake details should be role-scoped: own challenge details for
players, full queue for masters.

Actual:

Any device on the local network can call `/api/pvp/tables` and inspect queued
challenge participants and stake payloads.

Gameplay impact:

This leaks who is challenging whom, which object/stake is contested, and where
PvP pressure is building. It can spoil hidden negotiations, object races and
interception play.

Recommendation:

Require player code or role token. Return redacted aggregate table state for
ordinary players, own challenge details for involved players, and full queue
only for masters.

## Not Counted As Current Code Bugs

- Full mobile gameplay UI for trade, inventory, orders, personal Gwent,
  potions, spells, favorites and alignment is Stage 2B (`TASK-047`/`TASK-048`),
  not done Stage 1/2 scope.
- Native camera QR scan and Android/iOS real-device smoke are Stage 2B gates
  (`TASK-047`/`TASK-058`/`TASK-050`). They are manual blockers later, not green
  pytest proof now.
- Full visual lord UX: illustrated map, castle/building tree, fort art and
  polished 5x6 board are Stage 2B/`TASK-067`.
- Real second-laptop Admin Studio LAN smoke remains required manual evidence
  before `TASK-058`/`TASK-050`. The current Stage 2 evidence is localhost/API
  and browser smoke; this is an acceptance evidence gap for field readiness,
  not a direct code mismatch found in this audit.
- `docs/core-engine-v1.2.md` remains a historical source. Current conflicts
  are judged against PRD/architecture/roadmap/app technical plan/tasks.

## Verified Without New Issue

- Seed profile/validation for 4 lords, 4 sorceresses, 5 witchers and 2 NPC
  masters.
- Act schedule, final lock, physical announcement authority and server-side
  reveal checks.
- Player-scoped snapshots hide player codes, role tokens, exact reputation and
  hidden goal flags.
- Offline PvE event authority: app-generated d20, immutable check identity,
  physical-presence review path, cooldown and cascade reward approval.
- Reward approvals and asset locks prevent pending cascade rewards from being
  traded/staked/finalized.
- Full Gwent core runtime: deck validation, hands/mulligans/rows, round
  submissions, tie/refusal/review, stake lock/refund/settle and idempotent
  finish.
- Trade transfers use two-party lock/accept/decline and atomic ownership
  movement.
- Lord route/movement/garrison/building/recruit/order/raid/battle runtime is
  covered by behavior tests.
- Sorceress mana, spells, potion wholesale/transfer/use, favorites caps/consent
  and locked magical intent evidence are implemented in service/runtime tests.
- Reputation is limited to witcher/sorceress, exact value is master-scoped, and
  players see descriptive labels.
- Final summary is master-led and does not auto-declare winners.
- Admin Studio has master-token auth, overview, import/snapshot controls,
  review/reward/throttle/correction/backups/NPC/reputation/final-summary
  surfaces.

## Checks Run

- `uv run pytest -q` -> 221 passed, 1 warning.
- `uv run python scripts/taskctl.py ready` -> next ready task `TASK-045`.
- `git status --short` reviewed before writing this audit; worktree was already
  dirty.

