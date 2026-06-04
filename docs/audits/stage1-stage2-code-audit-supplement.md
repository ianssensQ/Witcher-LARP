# Stage 1 + Stage 2 code audit supplement

Updated through Pass 2: 2026-06-04 13:34 +03:00.

Baseline: `docs/audits/stage1-stage2-code-audit.md`.

Baseline findings `AUD-001`..`AUD-005` are known issues and are not duplicated
here. This supplement audits current code above the baseline. Product code,
`tasks.json`, generated views and `docs/core-engine-v1.2.md` were not edited.
No TaskOS tasks were created.

## Pass Log

| Pass | Date | HEAD checked | Dirty status before audit edits | Method | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-06-04 12:35 +03:00 | `4798e77` | clean | `rg -n`, small code/doc snippets, one 4-agent wave, manual dedupe/recheck | 6 new substantial bugs |
| 2 | 2026-06-04 13:31 +03:00 | `9767186` | clean | `rg -n`, small code/doc snippets, no subagents available in this tool context, manual dedupe/recheck | 12 new substantial bugs |

## Method And Context Strategy

- Initial orientation used only `AGENTS.md`,
  `docs/audits/stage1-stage2-code-audit.md` and `docs/active-tasks.md`.
- Canonical docs were not read end to end. Requirements were confirmed through
  targeted `rg -n` hits and small fragments.
- Each pass used risk areas distinct from the previous pass.
- Pass 1 recorded a subagent wave in the original supplement. In this
  continuation no subagent tool was available, so Pass 2 candidates were found
  through direct `rg -n` slices and manually rechecked in code before inclusion.
- Stage 2B UI absence was treated as out of scope. Missing full mobile/lord/Gwent
  UI was not counted as a Stage 1/2/2A bug.

## Baseline Issues Not Duplicated

- `AUD-001` P1: offline act unlock cannot work from pre-game snapshot.
- `AUD-002` P1: non-PvE paper recovery does not restore domain state.
- `AUD-003` P1: player snapshot exposes final hooks before reveal.
- `AUD-004` P2: mobile sync maps `rejected` to `needs_master_review`.
- `AUD-005` P2: `/api/pvp/tables` exposes queue/stakes without auth.

## New Findings By Pass

### Pass 1

### AUD-NEXT-001 - P1 - Attacker capture can leave defeated defender garrison active

- Severity: P1
- Source requirement: `docs/architecture.md:371`; `docs/architecture.md:375`.
- Code/data/test location: `backend/witcher_larp/lord_battle_service.py:750`,
  `:803`, `:874`, `:914`; `backend/witcher_larp/lord_runtime.py:432`, `:439`;
  lord battle tests do not assert defeated defender garrison cleanup.
- Expected / Actual: expected losing defender garrison is destroyed, retreated or
  routed to review before ownership flips; actual surviving defender garrison
  can remain active after attacker capture handoff.
- Gameplay impact: captured territory can contain active hidden military power
  from the old owner, distorting lord visibility, battles and final evidence.
- Recommendation: settle all losing-side garrisons before
  `capture_pending_garrison` becomes controlled.
- Confirmation method: force attacker victory over a territory with a surviving
  defender garrison, complete attacker garrison handoff, and assert no active
  defender garrison remains without review.
- Pass number: 1

### AUD-NEXT-002 - P2 - `/api/qr/lookup` is unauthenticated and trusts caller-supplied player identity

- Severity: P2
- Source requirement: `docs/PRD.md:71`; `docs/app-technical-plan-v0.1.md:92`;
  `docs/architecture.md:349`.
- Code/data/test location: `backend/witcher_larp/app.py:413`, `:420`;
  `backend/witcher_larp/qr_runtime.py:57`, `:328`;
  `tests/test_fastapi_contract.py` calls the endpoint without auth.
- Expected / Actual: expected player QR lookup derives `player_id` from
  authenticated player code; actual anonymous caller can submit any `player_id`,
  receive QR context and write attempt/log rows under that identity.
- Gameplay impact: players can preview scene mechanics and pollute another
  player's QR attempt/rate-limit history.
- Recommendation: require player-code auth, overwrite body identity from auth,
  and keep diagnostics on a separate scoped endpoint.
- Confirmation method: unauthenticated lookup should return `401` and create no
  `qr_attempts`; authenticated lookup should record the authenticated player.
- Pass number: 1

### AUD-NEXT-003 - P2 - Player-code auth response leaks exact numeric reputation

- Severity: P2
- Source requirement: `docs/app-technical-plan-v0.1.md:94`; `docs/PRD.md:97`,
  `:163`; `docs/architecture.md:213`.
- Code/data/test location: `backend/witcher_larp/app.py:461`, `:1897`, `:1936`;
  `backend/witcher_larp/snapshot_exporter.py:53`, `:380`;
  `tests/test_fastapi_contract.py:145`.
- Expected / Actual: expected auth response omits exact reputation or returns
  redacted `reputation_state`; actual nested `player.reputation` exposes the raw
  value.
- Gameplay impact: players can optimize against hidden Good/Evil thresholds and
  NPC/final consequences.
- Recommendation: sanitize auth identity through the same public player
  projection used by snapshots, or remove nested raw player data.
- Confirmation method: auth regression asserts no exact `reputation` or `value`
  is present for a player-code response.
- Pass number: 1

### AUD-NEXT-004 - P2 - Rejected paper recovery attempts poison later corrected input for the same paper form

- Severity: P2
- Source requirement: `docs/architecture.md:323`, `:343`, `:449`;
  `docs/app-technical-plan-v0.1.md:620`.
- Code/data/test location: `backend/witcher_larp/event_service.py:539`, `:575`,
  `:592`, `:1123`; `tests/test_paper_recovery.py:115`, `:220`.
- Expected / Actual: expected malformed rejected intake does not reserve
  `paper_form_id`; actual later corrected intake with the same form id is treated
  as duplicate review.
- Gameplay impact: a master typo can convert clean recovery into avoidable
  review and ambiguity during outage recovery.
- Recommendation: exclude rejected rows from paper duplicate detection or split
  invalid intake attempts from recovered-form claims.
- Confirmation method: submit invalid timestamp for `paper_form_id`, then
  resubmit valid data; corrected PvE paper form should apply normally.
- Pass number: 1

### AUD-NEXT-005 - P2 - Player-controlled `mandatory=false` bypasses PvP token pacing and started-match cap

- Severity: P2
- Source requirement: `docs/architecture.md:355`; `docs/PRD.md:139`.
- Code/data/test location: `backend/witcher_larp/app.py:285`, `:1450`;
  `backend/witcher_larp/pvp_service.py:273`, `:2226`; no regression prevents
  ordinary players from creating full `mandatory=false` challenges.
- Expected / Actual: expected ordinary full PvP challenges consume token budget,
  or non-mandatory flow is master-only; actual player can create full
  stake-locking `mandatory=false` challenge without spending tokens or started
  cap.
- Gameplay impact: PvP volume and stake locks can exceed the intended 15-person
  pacing model.
- Recommendation: spend tokens for all ordinary full PvP challenges or restrict
  non-mandatory challenges to master-approved flows.
- Confirmation method: create challenge with valid player code and
  `"mandatory": false`; token count should not remain unchanged in fixed code.
- Pass number: 1

### AUD-NEXT-006 - P2 - Queued PvP challenges still count as active and can block the target before a table exists

- Severity: P2
- Source requirement: `docs/PRD.md:77`; `docs/architecture.md:260`, `:355`.
- Code/data/test location: `backend/witcher_larp/pvp_service.py:23`, `:237`,
  `:239`, `:2854`; `tests/test_pvp_runtime.py:2068`.
- Expected / Actual: expected queued challenge does not block target/goal before
  a table and start window exist; actual `queued` is in active challenge states.
- Gameplay impact: queued challenges can become soft denial under limited/paused
  tables and stall interception pressure.
- Recommendation: clarify queue semantics and either remove `queued` from active
  blockers or add visible bounded master policy.
- Confirmation method: under limited throttle, create queued challenge involving
  a target and attempt another valid challenge involving that target.
- Pass number: 1

### Pass 2

### AUD-NEXT-007 - P1 - Future-act offline PvE can be accepted by late sync after act reveal

- Severity: P1
- Source requirement: `docs/PRD.md:58`, `:59`; `docs/architecture.md:349`.
- Code/data/test location: `backend/witcher_larp/event_service.py:275`;
  `backend/witcher_larp/pve_runtime.py:300`, `:515`;
  `tests/test_pve_runtime.py:516`.
- Expected / Actual: expected Act 2/3/Final offline event created before
  physical announcement/reveal is rejected or reviewed even if it syncs later;
  actual validation uses current server act history at sync time.
- Gameplay impact: players can pre-play future-act QR content and sync it after
  reveal, polluting authoritative PvE attempts, rewards, unique consumption and
  final evidence out of schedule.
- Recommendation: validate `event.created_at` or app roll time against
  `act_history`/unlock reveal time and require timestamped accepted unlock proof
  for offline master-code paths.
- Confirmation method: create Act 2 PvE event before Act 2 announcement, reveal
  Act 2, sync old event, and assert no accepted PvE side effects.
- Pass number: 2

### AUD-NEXT-008 - P1 - Standalone reward approval requests can mint pending rewards without PvE provenance

- Severity: P1
- Source requirement: `docs/architecture.md:349`;
  `docs/app-technical-plan-v0.1.md:564`.
- Code/data/test location: `backend/witcher_larp/event_service.py:200`, `:468`,
  `:824`; `backend/witcher_larp/reward_service.py:226`;
  `tests/test_reward_approvals.py`.
- Expected / Actual: expected pending reward approval is bound to an accepted or
  reviewable PvE/paper source; actual player sync can request any known pending
  reward id and create a grantable approval.
- Gameplay impact: rare assets, gold and final evidence rewards can be minted
  through master queue without completing the source scene.
- Recommendation: require source event/scenario/check provenance and verify it
  belongs to the actor; make standalone approval creation master-only.
- Confirmation method: sync `reward_approval_requested` for
  `reward_final_evidence` without a matching PvE attempt; fixed behavior should
  reject or review as missing provenance and create no grantable approval.
- Pass number: 2

### AUD-NEXT-009 - P2 - Unique QR conflict is ignored during concurrent sync side effects

- Severity: P2
- Source requirement: `docs/architecture.md:349`, `:453`.
- Code/data/test location: `backend/witcher_larp/pve_runtime.py:352`, `:418`,
  `:423`, `:436`; `tests/test_event_sync.py:371`.
- Expected / Actual: expected atomic consume claim decides authority and losing
  event skips side effects; actual `ON CONFLICT(qr_id) DO NOTHING` ignores the
  losing insert and still records an accepted PvE attempt path.
- Gameplay impact: during Wi-Fi recovery bursts, duplicate unique-object events
  can both look accepted and create duplicate attempts/reward evidence.
- Recommendation: inspect the consume insert result and convert conflict losers
  to review/reject before writing accepted side effects.
- Confirmation method: two SQLite connections validate the same unique QR before
  commit; fixed behavior accepts one and gives the other no accepted side
  effects.
- Pass number: 2

### AUD-NEXT-010 - P1 - Late post-lock magical intent can overwrite locked final evidence

- Severity: P1
- Source requirement: `docs/PRD.md:104`, `:169`; `docs/architecture.md:263`,
  `:339`, `:385`.
- Code/data/test location: `backend/witcher_larp/sorceress_service.py:359`,
  `:405`; `backend/witcher_larp/final_summary_service.py:661`, `:688`, `:895`.
- Expected / Actual: expected valid pre-final locked intent remains final
  authority and later post-lock attempts are disputes; actual latest
  review-pending post-lock record can change final summary state from `locked`
  to `review_pending`.
- Gameplay impact: a late invalid spell attempt can dirty a valid final signal
  and create a false blocker during the NPC-led final.
- Recommendation: prefer latest valid locked intent at/before final lock as
  authority and expose later review/disputed attempts separately.
- Confirmation method: lock intent before final lock, cast another locked-intent
  spell after final lock, and assert summary remains `locked` with separate
  dispute evidence.
- Pass number: 2

### AUD-NEXT-011 - P2 - Final summary counts seed Gwent fixture as real PvP evidence

- Severity: P2
- Source requirement: `docs/PRD.md:139`, `:171`;
  `docs/app-technical-plan-v0.1.md:325`.
- Code/data/test location: `data/seed/gwent_matches.csv:2`;
  `backend/witcher_larp/final_summary_service.py:879`, `:1180`.
- Expected / Actual: expected final readiness counts runtime Gwent, paper PvP or
  explicit master evidence; actual imported seed fixture clears missing
  `pvp_gwent` even if no match happened.
- Gameplay impact: masters can miss absent PvP/Gwent evidence before final.
- Recommendation: treat `gwent_matches.csv` as fixture/context only; clear
  missing PvP evidence from runtime match statuses or recovered/master evidence.
- Confirmation method: import seed without starting PvP and assert `pvp_gwent`
  remains missing; finish a runtime match and assert it clears.
- Pass number: 2

### AUD-NEXT-012 - P1 - Asset locks are global by asset id for items/cards/artifacts

- Severity: P1
- Source requirement: `docs/PRD.md:67`; `docs/architecture.md:170`, `:255`,
  `:357`.
- Code/data/test location: `backend/witcher_larp/asset_service.py:270`, `:291`,
  `:300`, `:480`; `backend/witcher_larp/sorceress_service.py:589`;
  `backend/witcher_larp/pvp_service.py:1251`.
- Expected / Actual: expected owned-asset lock reserves a specific owner's
  quantity; actual item/card/artifact lock blocks every owner of the same asset
  id.
- Gameplay impact: one player's pending reward/trade/PvP stake can falsely
  freeze common assets for unrelated players.
- Recommendation: scope owned-asset locks by owner for all ownership asset
  types and reserve global locks for explicit global cases.
- Confirmation method: give two players the same item/card id, lock player A's
  copy, and assert player B can still trade/stake their copy.
- Pass number: 2

### AUD-NEXT-013 - P1 - Final summary omits current owned artifacts/items/cards

- Severity: P1
- Source requirement: `docs/PRD.md:169`; `docs/architecture.md:252`, `:265`,
  `:385`.
- Code/data/test location: `backend/witcher_larp/final_summary_service.py:57`,
  `:58`, `:323`, `:349`; `backend/witcher_larp/asset_service.py:57`;
  `backend/witcher_larp/game_ops_service.py:823`.
- Expected / Actual: expected final summary exposes current final-relevant asset
  ownership after approvals, trades and PvP settlement; actual it shows active
  locks/pending rewards but omits ordinary `asset_ownership`.
- Gameplay impact: NPC masters can miss who owns artifacts, plot keys, rare
  cards or final tokens unless inferred from event history.
- Recommendation: add owner-scoped asset ledger to final summary and role
  evidence, separate from lock/dispute sections.
- Confirmation method: approve or trade a final-relevant asset and assert final
  summary shows the current owner.
- Pass number: 2

### AUD-NEXT-014 - P1 - Gwent start lets one participant control and inspect the opponent opening hand

- Severity: P1
- Source requirement: `docs/PRD.md:139`; `docs/architecture.md:355`, `:357`.
- Code/data/test location: `backend/witcher_larp/app.py:1464`, `:1487`;
  `backend/witcher_larp/pvp_service.py:405`, `:1349`, `:2340`.
- Expected / Actual: expected non-master participant submits only own mulligans
  and sees only own private hand/draw pile; actual either participant can submit
  mulligans for both players and receives full `deck_state` for both.
- Gameplay impact: a player can inspect/manipulate opponent opening hand in a
  stake-bearing match, breaking Gwent fairness.
- Recommendation: pass authenticated actor to start service, reject foreign
  mulligan keys for non-masters, and return viewer-scoped match payloads.
- Confirmation method: start as challenger with target mulligan key; fixed
  behavior rejects target mutation and hides opponent hand/draw pile.
- Pass number: 2

### AUD-NEXT-015 - P2 - Resolved review items can remain final-summary blockers

- Severity: P2
- Source requirement: `docs/app-technical-plan-v0.1.md:21`, `:572`;
  `docs/architecture.md:385`.
- Code/data/test location: `backend/witcher_larp/npc_service.py:258`, `:263`;
  `backend/witcher_larp/final_summary_service.py:516`, `:909`;
  `backend/witcher_larp/game_ops_service.py:499`.
- Expected / Actual: expected approved/rejected/corrected reviews are history;
  actual review queue/final summary can still treat them as pending disputes and
  create `unresolved_review`.
- Gameplay impact: masters can close a P0/P1 review and still see it block final
  summary while Admin/GameOps open count is zero.
- Recommendation: split review history from open queue and filter final pending
  disputes to non-final statuses.
- Confirmation method: approve a P1 review, then assert review queue and final
  summary no longer contain it as unresolved.
- Pass number: 2

### AUD-NEXT-016 - P2 - Final summary omits unresolved lord pending tick rewards

- Severity: P2
- Source requirement: `docs/PRD.md:147`, `:169`; `docs/architecture.md:385`.
- Code/data/test location: `backend/witcher_larp/timer_service.py:505`;
  `backend/witcher_larp/lord_runtime.py:1161`;
  `backend/witcher_larp/game_ops_service.py:627`;
  `backend/witcher_larp/final_summary_service.py:38`, `:270`.
- Expected / Actual: expected unresolved lord income/influence pending tick
  rewards appear as pending/disputed final evidence; actual final summary omits
  them unless already awarded.
- Gameplay impact: if final lock happens with contested lord income pending,
  masters may miss unsettled economic evidence.
- Recommendation: include `pending_tick_reward_runtime` in lord evidence and
  pending dispute/missing-lock sections while status is `pending`.
- Confirmation method: create contested claim, let income tick create a pending
  reward, do not resolve battle, and assert final summary shows it.
- Pass number: 2

### AUD-NEXT-017 - P1 - Lord order final lock can be bypassed by client-controlled source

- Severity: P1
- Source requirement: `docs/PRD.md:107`; `docs/app-technical-plan-v0.1.md:48`;
  `docs/architecture.md:385`, `:449`.
- Code/data/test location: `backend/witcher_larp/lord_runtime.py:42`, `:733`;
  `backend/witcher_larp/app.py:745`, `:787`;
  `tests/test_final_summary_runtime.py:319`, `:330`.
- Expected / Actual: expected only master/recovery authority can create
  paper/final-evidence orders after final lock; actual a normal lord-token
  request can set `source` to `paper_final_evidence`, `paper_recovered`,
  `master_api` or `master_override` and pass the source-only final-lock check.
- Gameplay impact: lords can reopen order/escrow flow after final lock, changing
  final evidence and master workload during the NPC-led final window.
- Recommendation: derive override source from authenticated master/recovery
  routes, not client payload; for lord-token creates, normalize source to
  `lord_panel` before final-lock checks.
- Confirmation method: after `final_lock`, POST `/api/lords/{lord_id}/orders`
  with a lord token and `source: "paper_final_evidence"`; fixed behavior should
  return `final_lock_orders_closed` unless authenticated as master/recovery.
- Pass number: 2

### AUD-NEXT-018 - P2 - Potion per-scene cap accepts arbitrary scene ids

- Severity: P2
- Source requirement: `docs/PRD.md:94`; `docs/app-technical-plan-v0.1.md:44`;
  `docs/architecture.md:379`; `docs/roadmap.md:120`.
- Code/data/test location: `backend/witcher_larp/sorceress_service.py:880`,
  `:896`, `:912`; `backend/witcher_larp/app.py:1229`, `:1247`;
  `tests/test_sorceress_runtime.py:275`, `:282`, `:958`.
- Expected / Actual: expected one potion per real PvE scene/check context;
  actual `use_potion_in_scene` never validates `scene_id`, so a player can use
  multiple potions by submitting different fake scene ids.
- Gameplay impact: potion economy and scene modifiers can be spammed around the
  intended one-potion cap, especially on hard PvE/final scenes.
- Recommendation: validate `scene_id` against `pve_scenarios`/QR context or
  bind potion use to an accepted scene event/check id; reject unknown or
  mismatched scene ids before consuming inventory.
- Confirmation method: audit probe on a temporary seed DB accepted two uses for
  `not_a_real_scene_1` and `not_a_real_scene_2` with `usage_count = 2`; fixed
  behavior should reject unknown scene ids and block the second potion in the
  same real scene.
- Pass number: 2

## Checked Without New Issues

- Production profile seed/validation for 4 lords, 4 sorceresses, 5 witchers and
  2 NPC masters.
- Final lock blocks default-source new lord orders and ordinary new PvP
  challenges; Pass 2 issue `AUD-NEXT-017` is the client-controlled source
  bypass for lord orders.
- Master/lord auth boundaries for Admin Studio, lord panels, lord battles,
  review queue, rewards, corrections, backups and final summary.
- Player-scoped snapshots hide player codes, role tokens, exact reputation and
  hidden goal flags. Baseline `AUD-003` remains the known final-hook exception.
- Offline PvE replay validates single d20, QR/scenario, cooldown and ordinary
  sequential unique-object consumption; Pass 2 issue is concurrency/stale-time
  authority, not the sequential happy path.
- Trade transfers and potion transfers enforce price/gold checks, two-party
  accept/decline, idempotency and ownership movement; Pass 2 issues are
  cross-owner false blocking and potion scene-id authority.
- Favorite consent, slot caps, favored-player cap and change-per-act checks are
  enforced.
- Backup manifests include SQLite and event log; Admin content import/snapshot
  and backup routes require master token.
- Stage 2B UI absence remains out of scope.

## Out Of Scope

- Full Stage 2B playable mobile UI, lord action UI and personal Gwent UI.
- Android/iOS real-device camera QR scan, install smoke and second-laptop LAN
  proof.
- Cosmetic, visual polish, copy, minor UX and UI layout gaps.
- Any rewrite of `docs/core-engine-v1.2.md`.
- Creating TaskOS tasks or editing generated views.
- Re-auditing baseline findings `AUD-001`..`AUD-005`.

## Checks Run

- Pass 1: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 1: `uv run pytest -q` -> 221 passed, 1 warning, 224.61s.
- Pass 2: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 2: `uv run pytest -q` -> 221 passed, 1 warning, 312.67s.

## Convergence Log

- After Pass 1: 6 new substantial findings; consecutive zero-new passes = 0.
- After Pass 2: 12 new substantial findings; consecutive zero-new passes = 0.
