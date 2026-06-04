# Stage 1 + Stage 2 code audit supplement

Updated through Pass 9: 2026-06-04 15:51 +03:00.

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
| 3 | 2026-06-04 13:50 +03:00 | `bf7d891` | clean | `rg -n`, backend auth/visibility/recovery/lord-runtime slices, no subagents available in this tool context, manual dedupe/recheck | 2 new substantial bugs |
| 4 | 2026-06-04 14:05 +03:00 | `bf7d891` | dirty: Pass 3 audit docs pending commit due escalated git limit | `rg -n`, production profile/lord-battle/sorceress/final-summary/mobile-sync slices, no subagents available in this tool context, manual dedupe/recheck | 1 new substantial bug |
| 5 | 2026-06-04 14:08 +03:00 | `bf7d891` | dirty: audit docs pending commit due escalated git limit | `rg -n`, order/PvP/NPC/reputation/Admin-correction/import-gate slices, no subagents available in this tool context, manual dedupe/recheck | 1 new substantial bug |
| 6 | 2026-06-04 14:22 +03:00 | `bf7d891` | dirty: audit docs pending commit due escalated git limit | `rg -n`, lord movement/fort capacity/snapshot secrecy/mobile PvE/import-gate slices, no subagents available in this tool context, manual dedupe/recheck | 1 new substantial bug |
| 7 | 2026-06-04 14:26 +03:00 | `bf7d891` | dirty: audit docs pending commit due escalated git limit | `rg -n`, trade/assets lock lifecycle, reward approval corrections, review/final blockers, game-ops corrections and timer idempotency slices, no subagents available in this tool context, manual dedupe/recheck | 3 new substantial bugs |
| 8 | 2026-06-04 14:33 +03:00 | `bf7d891` | dirty: audit docs pending commit due escalated git limit | `rg -n`, NPC/reputation/final evidence, sorceress spell runtime, Gwent effects, lord economy build/recruit/anti-snowball and QR/manual honesty slices, no subagents available in this tool context, manual dedupe/recheck | 0 new substantial bugs |
| 9 | 2026-06-04 15:51 +03:00 | `59e158b` | clean | `rg -n`, one 4-agent wave, act/final-lock, snapshot visibility, sync-retry recovery, Gwent sequencing, validation/import and final-evidence slices, manual dedupe/recheck | 4 new substantial bugs |

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

### AUD-NEXT-019 - P2 - Raid effects never expire or apply timed debuff state

- Severity: P2
- Source requirement: `docs/architecture.md:241`; `docs/architecture.md:365`;
  `docs/architecture.md:367`; `docs/active-tasks.md:176`;
  `docs/active-tasks.md:1156`; `data/seed/raid_rules.csv:2`.
- Code/data/test location: `backend/witcher_larp/lord_runtime.py:632`;
  `backend/witcher_larp/lord_runtime.py:679`;
  `backend/witcher_larp/lord_runtime.py:692`;
  `backend/witcher_larp/lord_runtime.py:2256`;
  `backend/witcher_larp/final_summary_service.py:316`;
  `backend/witcher_larp/final_summary_service.py:1101`;
  `tests/test_lord_runtime.py:540`; `tests/test_lord_runtime.py:979`.
- Expected / Actual: raid rules declare a timed debuff/loot duration and the
  lord flow requires raid debuff/loot expiry. The runtime writes
  `ends_at_offset_min` from `duration_min`, but no automatic transition updates
  `raid_effects.status` away from `active`; the only nearby `expire` action is
  for lord orders, while diplomacy/final-summary code counts active raid rows
  indefinitely.
- Gameplay impact: lord diplomacy pressure, raid status, optional loot/debuff
  evidence and final domain summaries can all show stale active raids after the
  intended duration, distorting lord strategy and master rulings.
- Recommendation: store absolute start/end times or bind raid effects to timer
  ticks, apply/remove the debuff or loot state, expire rows automatically, and
  cover the duration boundary plus final-summary projection in tests.
- Confirmation method: `rg -n "raid_effects|duration_min|ends_at_offset_min|UPDATE raid_effects|expired"`
  across `backend/witcher_larp` and tests found insert/count paths but no
  runtime expiry path; add a test that starts a raid, advances beyond duration
  and expects non-active status plus cleared debuff/loot evidence.
- Pass number: 3

### AUD-NEXT-020 - P2 - Conflicted paper PvE recovery cannot apply PvE side effects after master ruling

- Severity: P2
- Source requirement: `docs/architecture.md:323`;
  `docs/architecture.md:343`; `docs/architecture.md:449`;
  `docs/architecture.md:457`; `docs/active-tasks.md:348`;
  `docs/active-tasks.md:369`; `docs/active-tasks.md:382`.
- Code/data/test location: `backend/witcher_larp/event_service.py:601`;
  `backend/witcher_larp/event_service.py:615`;
  `backend/witcher_larp/event_service.py:627`;
  `backend/witcher_larp/event_service.py:923`;
  `backend/witcher_larp/review_service.py:411`;
  `backend/witcher_larp/review_service.py:423`;
  `tests/test_paper_recovery.py:31`; `tests/test_paper_recovery.py:96`;
  `tests/test_paper_recovery.py:228`.
- Expected / Actual: conflicting `paper_pve_result` should be saved for master
  ruling and, once approved/corrected, apply the same QR/PvE reward/cooldown
  side effects through ordinary checks. Instead non-clean conflict status exits
  before `_decide_paper_pve_result` builds `recovered_pve_payload`, and review
  side effects are gated to rows whose stored `event_type` is `pve_completed`;
  the stored review row is `paper_recovered`, so approval closes audit without
  a PvE attempt or reward/cooldown mutation.
- Gameplay impact: a phone/Wi-Fi outage followed by a legitimate conflicting
  paper QR result can be accepted by masters yet still lose the player's PvE
  progress, reward approval state and cooldown history.
- Recommendation: preserve parsed recovered PvE payload metadata for
  `paper_pve_result` conflicts and let review approval/correction invoke the
  PvE side-effect path for `paper_recovered` rows with
  `recovered_event_type=pve_completed`, with duplicate/resource checks intact.
- Confirmation method: targeted audit script submitted a conflicting
  `paper_pve_result`, approved the review via `decide_event_review`, and
  observed `decision_event_status='accepted'`, `pve_attempts_for_event=0` and
  no player runtime state; add a regression test for approved/corrected
  conflicted paper PvE recovery.
- Pass number: 3

### AUD-NEXT-021 - P2 - Favorite requests can deadlock consent lifecycle for an act

- Severity: P2
- Source requirement: `docs/architecture.md:338`;
  `docs/architecture.md:379`; `docs/architecture.md:453`;
  `docs/active-tasks.md:236`; `docs/active-tasks.md:868`;
  `data/seed/favorite_rules.csv:2`.
- Code/data/test location: `backend/witcher_larp/app.py:1339`;
  `backend/witcher_larp/app.py:1368`;
  `backend/witcher_larp/sorceress_service.py:19`;
  `backend/witcher_larp/sorceress_service.py:931`;
  `backend/witcher_larp/sorceress_service.py:1005`;
  `backend/witcher_larp/sorceress_service.py:1275`;
  `backend/witcher_larp/sorceress_service.py:1330`;
  `tests/test_sorceress_runtime.py:889`;
  `tests/test_sorceress_runtime.py:908`.
- Expected / Actual: favorites are specified as a consent-based lifecycle with
  requested/accepted/changed/removed states, max primary/secondary slots, max 2
  sorceresses per favored player and one change per act. Runtime/API only expose
  create and accept; `ACTIVE_FAVORITE_STATUSES` includes `pending`, and
  `_assert_favorite_caps` counts pending rows for duplicate, slot, favored-player
  and per-act change limits. There is no favorite decline, cancel, remove or
  change route to clear a non-consenting request.
- Gameplay impact: a player can simply not accept a favorite request and still
  consume the sorceress's slot/change budget for the act, blocking potion/spell
  favorite targeting and distorting final favorite/alignment evidence without a
  master-visible resolution path.
- Recommendation: add explicit decline/cancel/remove/change transitions with
  audit history and event log entries, and decide whether rejected/withdrawn
  requests count toward per-act change limits; cover refusal/nonresponse and
  re-request cases in API/runtime tests.
- Confirmation method: `rg -n "favorite_changed|favorite_removed|decline|remove|cancel|/api/favorites"`
  shows source requirements and only create/accept routes in implementation;
  add a regression test that creates a pending favorite, declines/removes it,
  and verifies the sorceress can use the slot according to the configured act
  limit.
- Pass number: 4

### AUD-NEXT-022 - P2 - PvP match corrections can bypass stake settlement

- Severity: P2
- Source requirement: `docs/architecture.md:178`;
  `docs/architecture.md:355`; `docs/architecture.md:357`;
  `docs/architecture.md:413`; `docs/active-tasks.md:354`;
  `docs/active-tasks.md:370`; `docs/active-tasks.md:381`.
- Code/data/test location: `backend/witcher_larp/game_ops_service.py:127`;
  `backend/witcher_larp/game_ops_service.py:295`;
  `backend/witcher_larp/game_ops_service.py:342`;
  `backend/witcher_larp/pvp_service.py:969`;
  `backend/witcher_larp/pvp_service.py:984`;
  `backend/witcher_larp/pvp_service.py:1041`;
  `backend/witcher_larp/pvp_service.py:2062`;
  `tests/test_game_ops_service.py:68`;
  `tests/test_pvp_runtime.py:630`; `tests/test_pvp_runtime.py:1769`.
- Expected / Actual: Admin corrections are the recovery path for PvP timeout and
  final evidence, while PvP finish must settle stake transfer exactly once. The
  normal `finish_gwent_match` path refuses to apply stakes for
  `needs_master_review` matches and only calls `_apply_stake_once` for
  `awaiting_finish`; the game-ops correction target for `pvp_match` can patch
  `status`, `winner_id`, `review_reason` and `duration_seconds` directly with a
  generic SQL update, but it never calls the PvP settlement path, releases a
  table, resolves the challenge, or updates `pvp_stake_ledger`.
- Gameplay impact: a master can correct a reviewed/timeout PvP result to a
  winner while the stake remains locked/not applied and the challenge/table
  state remains inconsistent, corrupting player assets, final PvP evidence and
  recovery authority.
- Recommendation: route PvP match corrections through a domain-specific review
  settlement helper that validates winner/outcome, calls `_apply_stake_once`,
  resolves/reviews challenge/table resources and records the same event-log
  evidence as `finish_gwent_match`.
- Confirmation method: `rg -n "pvp_match|winner_id|stake_transfer|game_ops_correction|finish_gwent_match"`
  shows the generic correction target and the separate stake-settlement path;
  add a regression test that moves a match to `needs_master_review`, resolves it
  through the correction API, and asserts stake ledger, asset/gold ownership,
  challenge status and final-summary PvP evidence are consistent.
- Pass number: 5

### Pass 6

### AUD-NEXT-023 - P2 - Fort garrison capacity is not modeled or enforced

- Severity: P2
- Source requirement: `docs/architecture.md:238`, `:275`, `:284`, `:361`,
  `:363`, `:367`.
- Code/data/test location: `backend/witcher_larp/content_schema.py:6`,
  `:80`; `backend/witcher_larp/lord_runtime.py:389`, `:416`, `:432`,
  `:2156`; `tests/test_seed_contract.py:91`, `:130`;
  `tests/test_lord_runtime.py:409`; no `territory_forts.csv`,
  `garrison_capacity` or fort-capacity runtime path is present in seed data,
  import validation or lord transfer tests.
- Expected / Actual: expected each capturable territory has a fort record with
  validated `garrison_capacity`, and fort transfers reject moves that exceed
  that capacity while preserving minimum garrison rules; actual runtime only
  checks active-army capacity on `fort_to_active`, then increments garrisons via
  `_upsert_garrison` with no fort-capacity source or cap.
- Gameplay impact: lords can overstack fort defenses, changing battle balance,
  territory control pressure and final territorial evidence outside the planned
  rule model.
- Recommendation: add a `territory_forts` content/runtime source or explicit
  fort capacity field, validate one fort and positive capacity for each
  capturable territory, and check `current_garrison + count <= garrison_capacity`
  before garrison upsert/capture handoff; cover over-cap rejection and
  minimum-garrison capture tests.
- Confirmation method: `rg -n "territory_forts|garrison_capacity|fort_id|defense_bonus"`
  found no fort-capacity implementation, and targeted code review of the
  transfer path confirmed no capacity check before `_upsert_garrison`; a
  regression test should attempt to transfer above fort capacity and expect
  rejection.
- Pass number: 6

### Pass 7

### AUD-NEXT-024 - P2 - Trade transfer corrections can bypass settlement and lock release

- Severity: P2
- Source requirement: `docs/architecture.md:170`, `:255`, `:335`, `:453`;
  `docs/active-tasks.md:354`.
- Code/data/test location: `backend/witcher_larp/game_ops_service.py:123`,
  `:295`, `:342`; `backend/witcher_larp/sorceress_service.py:701`,
  `:721`, `:750`, `:808`, `:843`; `tests/test_game_ops_service.py:68`;
  `tests/test_trade_transfers.py:19`, `:70`.
- Expected / Actual: expected master correction of a trade result preserves the
  same atomic owner/gold movement and asset-lock audit semantics as normal
  accept/decline/cancel; actual `trade_transfer` game-ops correction is a
  generic SQL patch that can change `status`, `price_gold`, participants or
  asset fields without calling `accept_trade_transfer`,
  `decline_trade_transfer`, gold movement or `settle_owned_asset_lock`.
- Gameplay impact: Admin recovery can mark a trade accepted, declined or
  contested while the asset remains locked, gold is not moved, or ownership
  still belongs to the previous player, corrupting inventory/trade/final
  evidence.
- Recommendation: route trade corrections through a domain-specific settlement
  helper, restrict direct patch fields to audit-only metadata, and reject
  terminal status changes unless the helper can settle/release locks and record
  the same event-log evidence as the normal trade APIs.
- Confirmation method: targeted review of `CORRECTION_TARGETS["trade_transfer"]`
  and `_apply_table_correction` showed only a generic update; normal
  accept/decline paths were rechecked and are the only paths that move gold and
  settle locks. Add a regression that corrects a pending trade to `accepted` and
  asserts ownership, gold and active locks are consistent.
- Pass number: 7

### AUD-NEXT-025 - P2 - Corrected reward approvals can grant replacement assets despite active locks

- Severity: P2
- Source requirement: `docs/architecture.md:33`, `:173`, `:333`, `:349`,
  `:453`; `docs/active-tasks.md:354`.
- Code/data/test location: `backend/witcher_larp/reward_service.py:43`,
  `:114`, `:273`, `:308`; `backend/witcher_larp/asset_service.py:208`,
  `:291`, `:355`; `tests/test_reward_approvals.py:33`, `:171`, `:257`.
- Expected / Actual: expected a corrected reward decision validates replacement
  item/card/artifact assets against the same active reward/trade/stake locks
  before granting them; actual `correct` releases the original approval locks,
  then grants `reward_asset_entries(..., correction)` through
  `grant_asset_ownership` without `assert_reward_assets_unlocked` or
  per-asset lock availability checks.
- Gameplay impact: a master correction can mint or duplicate an asset that is
  already locked in another pending reward, trade or stake flow, undermining
  cascade-prone reward locks and final object evidence.
- Recommendation: before applying corrected assets, validate each corrected
  asset against active locks; either create fresh approval locks for replacement
  assets until the corrected decision is fully settled or reject/reroute to
  review if any replacement asset is locked.
- Confirmation method: `rg -n` showed lock checks during approval creation and
  normal pending-reward conflict tests, but no corrected-asset conflict test or
  runtime check before `grant_asset_ownership`; add a regression with one
  pending reward locking an item and a second approval corrected to that same
  item.
- Pass number: 7

### AUD-NEXT-026 - P2 - Pending trade locks never time out

- Severity: P2
- Source requirement: `docs/architecture.md:255`, `:335`, `:453`;
  `docs/active-tasks.md:406`, `:1045`.
- Code/data/test location: `backend/witcher_larp/sorceress_service.py:173`,
  `:701`, `:808`; `backend/witcher_larp/timer_service.py`;
  `backend/witcher_larp/validation.py:1232`; `tests/test_trade_transfers.py:70`,
  `:162`; `tests/test_seed_contract.py:298`, `:774`;
  `data/seed/trade_transfers.csv:2`.
- Expected / Actual: expected pending trade locks have a configured timeout and
  a runtime path that moves stale `pending_locked` transfers to a terminal
  timeout/cancelled state while releasing the asset lock; actual `timed_out` is
  only treated as already-final by `decline_trade_transfer`, the seed schema has
  no timeout field, validation allows no `timed_out` seed status, and no timer,
  service or API path sets the timeout/release.
- Gameplay impact: a missed or abandoned online trade can lock an item/card/
  artifact/potion indefinitely, blocking later trade, PvP stake, reward use or
  final object settlement until a manual correction is invented.
- Recommendation: add transfer timeout configuration/content, an idempotent
  expiry helper invoked by timers/Admin operations, lock release with audit
  reason `timed_out`, and tests for pending transfer expiry across restart.
- Confirmation method: `rg -n "timed_out|pending_locked|trade_transfer.*timeout"`
  found terminal handling and tests for accept/decline only, with no expiry
  helper or timer; add a regression that advances past timeout and expects the
  transfer terminal plus lock released.
- Pass number: 7

### Pass 8

No new substantial Stage 1/2/2A bugs were verified in this pass.

### Pass 9

### AUD-NEXT-027 - P1 - Direct Final Act start can skip final lock side effects

- Severity: P1
- Source requirement: `docs/app-technical-plan-v0.1.md:17`;
  `docs/app-technical-plan-v0.1.md:48`; `docs/PRD.md:107`;
  `docs/architecture.md:34`; `docs/architecture.md:355`;
  `docs/architecture.md:385`; `data/seed/acts.csv:6`;
  `data/seed/acts.csv:7`; `data/seed/auto_timers.csv:5`;
  `data/seed/auto_timers.csv:6`.
- Code/data/test location: `backend/witcher_larp/app.py:807`;
  `backend/witcher_larp/app.py:817`;
  `backend/witcher_larp/act_service.py:30`;
  `backend/witcher_larp/act_service.py:47`;
  `backend/witcher_larp/act_service.py:64`;
  `backend/witcher_larp/act_service.py:164`;
  `backend/witcher_larp/timer_service.py:37`;
  `backend/witcher_larp/timer_service.py:226`;
  `backend/witcher_larp/timer_service.py:338`;
  `backend/witcher_larp/pvp_service.py:236`;
  `backend/witcher_larp/lord_runtime.py:736`;
  `backend/witcher_larp/sorceress_service.py:361`;
  `tests/test_act_timer_runtime.py:160`;
  `tests/test_final_summary_runtime.py:285`.
- Expected / Actual: expected the fixed flow `Act 3 -> final_lock -> Final Act`
  always applies final lock before Final Act play, closing new PvP challenges,
  ordinary lord orders and post-lock magical intent paths. Actual master act
  start accepts any `act_id` directly; starting `final_act` without an
  `act_history` row for `final_lock` applies only timers for existing act
  history rows, so `timer_final_lock` never sets `final_lock_state.locked_at`.
- Gameplay impact: masters can accidentally enter Final Act with final lock
  visibly skipped while final backup runs, leaving PvP, lord orders and locked
  magical intent open during the final procedure.
- Recommendation: enforce act sequence transitions or make `final_act` start
  idempotently apply/require the `final_lock` act and timer first; add a
  regression that direct `final_act` start from Act 3 leaves final-lock gates
  closed.
- Confirmation method: `rg -n` confirmed the route passes arbitrary `act_id`,
  `start_act` has no sequence guard, final lock is only the `final_lock` timer,
  and existing final-lock tests start `final_lock` explicitly before checking
  locked behavior.
- Pass number: 9

### AUD-NEXT-028 - P2 - Duplicate event retry hides original review, rejection or pending status

- Severity: P2
- Source requirement: `docs/architecture.md:160`;
  `docs/architecture.md:321`; `docs/architecture.md:322`;
  `docs/architecture.md:325`; `docs/architecture.md:349`;
  `docs/app-technical-plan-v0.1.md:223`.
- Code/data/test location: `backend/witcher_larp/event_service.py:73`;
  `backend/witcher_larp/event_service.py:82`;
  `mobile/scripts/app_state.gd:17`; `mobile/scripts/app_state.gd:595`;
  `mobile/scripts/app_state.gd:596`; `tests/test_event_sync.py:553`;
  `tests/test_pve_runtime.py:911`; `tests/test_pve_runtime.py:912`.
- Expected / Actual: expected idempotent retry after a lost HTTP response
  preserves the original server decision (`accepted`, `rejected`,
  `needs_master_review` or `pending_master_approval`) so the phone and player
  still see the real recovery state. Actual duplicate lookup returns only
  generic `duplicate`, and the mobile queue maps `accepted` or `duplicate` to
  local `synced`, erasing original review/rejected/pending visibility after a
  retry.
- Gameplay impact: during Wi-Fi loss or app restart, a player can lose visible
  indication that a PvE/manual/reward event is waiting for master review or
  approval; masters still have server-side state, but the player's recovery
  workflow falsely looks complete.
- Recommendation: return the stored event status/reason for duplicate event ids
  or add duplicate metadata that the client maps back to the original terminal
  or review state; add lost-response retry tests for `needs_master_review`,
  `pending_master_approval` and `rejected`.
- Confirmation method: `rg -n` confirmed server duplicate responses select only
  `server_event_id`, mobile retry includes `pending`/`sync_error`, and mobile
  marks `duplicate` as `synced`; this is separate from baseline `AUD-004`
  first-time rejected-status mapping.
- Pass number: 9

### AUD-NEXT-029 - P1 - Player snapshots expose master-only artifact metadata

- Severity: P1
- Source requirement: `docs/architecture.md:145`;
  `docs/architecture.md:146`; `docs/architecture.md:252`;
  `docs/architecture.md:265`; `docs/architecture.md:385`;
  `docs/app-technical-plan-v0.1.md:45`;
  `docs/app-technical-plan-v0.1.md:92`.
- Code/data/test location: `backend/witcher_larp/snapshot_exporter.py:36`;
  `backend/witcher_larp/snapshot_exporter.py:52`;
  `backend/witcher_larp/snapshot_exporter.py:152`;
  `backend/witcher_larp/snapshot_exporter.py:238`;
  `backend/witcher_larp/snapshot_exporter.py:443`;
  `backend/witcher_larp/game_ops_service.py:268`;
  `backend/witcher_larp/game_ops_service.py:901`;
  `data/seed/artifacts.csv:4`; `data/seed/artifacts.csv:6`;
  `data/seed/artifacts.csv:8`; `tests/test_snapshot_exporter.py:51`;
  `tests/test_fastapi_contract.py:113`.
- Expected / Actual: expected player-scoped mobile snapshots hide master-only
  and hidden-until-reveal artifact metadata while preserving only player-safe
  content. Actual scoped snapshots remove only `player_codes` and `role_tokens`
  at top level, leaving the full `artifacts` table including `master_only`,
  `hidden_until_used`, `npc_price`, `needs_final_review` and
  `final_counter_evidence` rows.
- Gameplay impact: any player code can download the snapshot and learn hidden
  dark/legendary artifacts, final counter-evidence and NPC/final hints before
  ownership or reveal, undermining secrecy, NPC deals and final procedure.
- Recommendation: scope or redact artifact catalog rows/fields for players
  using the same artifact visibility policy as Admin visibility audit; add
  snapshot/API tests asserting no `master_only` or unrevealed hidden artifacts
  appear in player snapshots.
- Confirmation method: backend snapshot builder includes `artifacts`, player
  scoping filters only secret tables and private player fields, seed artifacts
  contain hidden/master-only final metadata, and existing snapshot tests assert
  only code/token/reputation redaction.
- Pass number: 9

### AUD-NEXT-030 - P2 - Caller-supplied Gwent round numbers can skip ahead and poison match progression

- Severity: P2
- Source requirement: `docs/app-technical-plan-v0.1.md:29`;
  `docs/app-technical-plan-v0.1.md:275`;
  `docs/architecture.md:336`; `docs/architecture.md:355`;
  `docs/architecture.md:357`; `docs/active-tasks.md:306`.
- Code/data/test location: `backend/witcher_larp/app.py:301`;
  `backend/witcher_larp/app.py:1517`; `backend/witcher_larp/app.py:1521`;
  `backend/witcher_larp/pvp_service.py:512`;
  `backend/witcher_larp/pvp_service.py:514`;
  `backend/witcher_larp/pvp_service.py:809`;
  `backend/witcher_larp/pvp_service.py:3134`;
  `backend/witcher_larp/pvp_service.py:3136`;
  `tests/test_pvp_runtime.py:251`; `tests/test_pvp_runtime.py:617`.
- Expected / Actual: expected Gwent records rounds in best-of-3 sequence and
  rejects out-of-sequence round numbers unless a master correction/review path
  explicitly handles them. Actual participant payload can supply `round_number`
  1..3; the service uses it directly, inserts a pending row for that number,
  and future default progression uses `MAX(round_number)+1`.
- Gameplay impact: one authenticated participant can submit round 3 as the
  first pending round; after that ordinary next-round submission defaults to 4
  and fails the best-of-3 bound, stalling the match and stake flow until manual
  cleanup/backfill.
- Recommendation: require caller-supplied `round_number` to equal
  `_next_round_number` for player submissions, reserve skip/backfill for a
  master correction path, and add regression coverage for first submission with
  round 3 plus subsequent normal submission.
- Confirmation method: `rg -n` and small code snippets confirmed API accepts
  optional `round_number`, `record_gwent_round` only checks `1..3`, pending
  inserts use the supplied number, and existing tests cover normal/duplicate
  round 1 flow but not out-of-sequence round numbers.
- Pass number: 9

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

## Pass 3 Checked Without New Issues

- Admin/master token boundaries: master-only routes use `_require_master_token`
  and negative coverage includes missing, invalid, lord and master tokens
  (`backend/witcher_larp/app.py:1874`,
  `tests/test_admin_studio_contract.py:91`). No new issue beyond baseline
  `AUD-002` and existing `AUD-NEXT-004`/`AUD-NEXT-015`.
- Lord role-token and lord-battle visibility: lord panel state checks role type
  and owner id, mutating lord routes use `_require_lord_token`, and lord battle
  list/get paths scope visibility to attacker/defender domains or NPC master
  (`backend/witcher_larp/app.py:613`, `:643`, `:1665`, `:1680`, `:1846`;
  `tests/test_lord_panel_contract.py:123`, `:399`).
- Player content snapshot secrecy: `/snapshot` requires player code, snapshot
  export redacts private payload keys, and reputation/final-facing data remains
  separated except known baseline final-hook leakage
  (`backend/witcher_larp/app.py:402`;
  `backend/witcher_larp/snapshot_exporter.py:52`, `:387`;
  `tests/test_snapshot_exporter.py:114`).
- NPC hidden-price handling: master NPC deal routes require master token, while
  player-visible NPC actions redact hidden prices to master-only markers
  (`backend/witcher_larp/app.py:989`;
  `backend/witcher_larp/npc_service.py:245`, `:611`;
  `tests/test_reputation_npc_runtime.py:126`).
- Sorceress, favorite and trade participant scopes: runtime endpoints require
  player-or-master auth, and service checks constrain accept/close actions to
  transfer or favorite participants (`backend/witcher_larp/app.py:1119`,
  `:1261`; `backend/witcher_larp/sorceress_service.py:712`, `:826`, `:1016`;
  `tests/test_sorceress_runtime.py:996`).
- PvP/Gwent endpoint visibility: route token requirements and Gwent/lord
  visibility were rechecked without finding an additional exposure beyond
  baseline `AUD-005` and existing `AUD-NEXT-014`.
- Backup artifacts: a targeted audit script created an event and backup inside
  one `connect()` scope; both manifest and copied SQLite contained the marker,
  so no restart-recovery issue was confirmed for this slice.

## Pass 4 Checked Without New Issues

- Production profile validation: `profiles.csv`, `players.csv` and
  `role_tokens.csv` are checked for 15 total people, 13 players, 2 NPC masters,
  4 lords, 4 sorceresses, 5 witchers and exact NPC-master token owners
  (`backend/witcher_larp/validation.py:400`,
  `backend/witcher_larp/validation.py:554`,
  `tests/test_seed_contract.py:560`).
- Lord battle settlement/timeout: attack, surrender, repeated timeout
  auto-resolve, burned cards, capture handoff, retreat and pending tick awards
  have service paths and tests; no new issue beyond `AUD-NEXT-001`
  (`backend/witcher_larp/lord_battle_service.py:746`,
  `backend/witcher_larp/lord_battle_service.py:803`,
  `tests/test_lord_battle_runtime.py:181`,
  `tests/test_lord_battle_runtime.py:1081`).
- Sorceress mana timers: hourly `lord_income_and_mana` applies mana regen capped
  by max mana and has restart/idempotency coverage
  (`backend/witcher_larp/timer_service.py:252`,
  `backend/witcher_larp/timer_service.py:299`,
  `tests/test_act_timer_runtime.py:97`).
- Final summary/export policy: summary remains master-led without automatic
  winner calculation and includes locked intent, paper recovery, pending
  disputes and export metadata; existing missing evidence issues remain covered
  by earlier findings (`backend/witcher_larp/final_summary_service.py:38`,
  `tests/test_final_summary_runtime.py:38`).
- Mobile sync/retry was rechecked for statuses outside baseline `AUD-004`; no
  new substantial issue found beyond the known rejected-to-review mapping.

## Pass 5 Checked Without New Issues

- Lord order cap/object conflict/escrow: order creation, accept/submit/complete,
  object conflict close-out and escrow reserve/refund/award paths were rechecked
  without a new issue beyond existing recovery gaps
  (`backend/witcher_larp/lord_runtime.py:789`,
  `backend/witcher_larp/lord_runtime.py:1510`,
  `backend/witcher_larp/lord_runtime.py:1627`;
  `tests/test_lord_runtime.py:919`).
- PvP finish/refusal regular path: normal awaiting-finish flow applies stake
  once, invalid/partial/tie review flows intentionally leave stake unapplied
  pending master action; the new issue is limited to the Admin correction path
  for reviewed matches (`backend/witcher_larp/pvp_service.py:969`,
  `tests/test_pvp_runtime.py:1713`).
- NPC/reputation authority: master-only endpoints, NPC role/type validation,
  hidden price redaction, P0/P1 review routing and reputation clamping remain
  covered (`backend/witcher_larp/npc_service.py:81`,
  `backend/witcher_larp/npc_service.py:320`,
  `tests/test_reputation_npc_runtime.py:95`).
- Content/import gates for this slice were rechecked through targeted `rg` on
  order status, reputation range, NPC event flags and PvP rules; no new
  structural import bug was verified.

## Pass 6 Checked Without New Issues

- Lord active-army movement and retreat: the runtime uses one active army per
  domain, moves all active-army rows with the lord, and retreat updates both
  `active_army_runtime.location_node_id` and `domain_runtime_state.current_node_id`;
  no split-army/desync issue was verified
  (`backend/witcher_larp/lord_runtime.py:220`,
  `backend/witcher_larp/lord_battle_service.py:874`).
- Player snapshot reputation secrecy: player-scoped reputation payloads redact
  exact values and expose only band/label data, with tests asserting no raw
  `value` in player endpoints; the known final-hook snapshot leak remains
  baseline `AUD-003` (`backend/witcher_larp/snapshot_exporter.py:387`,
  `tests/test_fastapi_contract.py:1419`).
- Mobile PvE roll/result contract: targeted review of `qr_runtime`,
  `pve_runtime`, mobile app state and tests found server-side result generation,
  replay handling and offline sync coverage beyond existing stale-act issue
  `AUD-NEXT-007` (`backend/witcher_larp/pve_runtime.py:383`,
  `tests/test_pve_runtime.py:32`, `tests/test_event_sync.py:258`).
- Import/content minima gates: QR mix, building cycles, Gwent deck limits,
  trade transfer schema, reputation ranges, reward approval policy and favorite
  rule shape are validated in seed checks; the new issue is limited to missing
  fort/garrison-capacity data and enforcement
  (`backend/witcher_larp/validation.py:1`, `tests/test_seed_contract.py:1`).

## Pass 7 Checked Without New Issues

- Normal trade accept/decline path: participant consent, pending-only status,
  gold movement, inventory/ownership settlement and lock release are covered by
  `accept_trade_transfer`/`decline_trade_transfer` and transfer tests; new
  issues are limited to Admin correction and timeout lifecycle gaps
  (`backend/witcher_larp/sorceress_service.py:701`,
  `tests/test_trade_transfers.py:19`).
- Normal reward approval approve/reject path: pending approvals lock assets,
  reject releases locks, duplicate/conflicting approvals route to review, and
  tests cover pending reward assets blocked from PvP stake/trade; new issue is
  limited to replacement assets supplied in the `correct` branch
  (`backend/witcher_larp/reward_service.py:71`,
  `tests/test_reward_approvals.py:33`).
- Review/final blocker lifecycle: unresolved reviews and locked magical intent
  remain visible in final summary; missing generic non-PvE side effects and
  resolved review blocker behavior are already covered by baseline `AUD-002`,
  `AUD-NEXT-015` and `AUD-NEXT-020`
  (`backend/witcher_larp/final_summary_service.py:56`,
  `tests/test_final_summary_runtime.py:179`).
- Auto timer idempotency: applied timer ticks are keyed by timer/due time and
  restart tests cover income/mana/token idempotency; no new timer replay issue
  was verified in this slice (`backend/witcher_larp/timer_service.py:69`,
  `tests/test_act_timer_runtime.py:82`).

## Pass 8 Checked Without New Issues

- QR/manual honesty and opaque-code policy: lookup normalizes only printed
  manual/opaque codes, future-act lookups redact scene payloads until physical
  announcement, missing physical presence and manual-rate-limit attempts enter
  review, and sync preserves those review reasons. No new issue beyond
  `AUD-NEXT-002` and stale/future-act findings was verified
  (`backend/witcher_larp/qr_runtime.py:57`,
  `backend/witcher_larp/event_service.py:508`,
  `tests/test_fastapi_contract.py:289`,
  `tests/test_fastapi_contract.py:362`,
  `tests/test_event_sync.py:396`).
- NPC/reputation/final evidence authority: NPC event endpoints are master-only,
  NPC role/type and severity are validated, hidden prices redact outside master
  views, reputation applies only to witchers/sorceresses and final summary
  includes NPC deals/reputation/master notes. No additional NPC/final authority
  issue was verified (`backend/witcher_larp/npc_service.py:81`,
  `backend/witcher_larp/npc_service.py:320`,
  `backend/witcher_larp/final_summary_service.py:395`,
  `tests/test_reputation_npc_runtime.py:27`,
  `tests/test_admin_studio_contract.py:545`).
- Sorceress spell runtime: cast ids are idempotent before mana spend, target
  existence/type is validated before mutation, insufficient mana has no side
  effect, and post-final locked intent is routed to review without mana spend;
  no new issue beyond existing locked-intent/potion/favorite findings was
  verified (`backend/witcher_larp/sorceress_service.py:327`,
  `tests/test_sorceress_runtime.py:38`,
  `tests/test_sorceress_runtime.py:125`).
- Gwent effect resolution: weather, clear weather, horn, decoy, scorch,
  spy/medic/muster, rare specials and leader usage have runtime validators and
  tests; no additional game-mechanics issue beyond already recorded
  PvP visibility/correction/stake findings was verified
  (`backend/witcher_larp/gwent_effects.py:1`,
  `backend/witcher_larp/pvp_service.py:1400`,
  `tests/test_pvp_runtime.py:1104`,
  `tests/test_pvp_runtime.py:1196`,
  `tests/test_pvp_runtime.py:1338`).
- Lord economy build/recruit/anti-snowball: building purchase checks duplicate
  ownership, prerequisites and gold; recruit hold/purchase checks offer status,
  holder and gold; timer tick applies anti-snowball cuts. No new issue beyond
  existing fort-capacity, raid-expiry, final-lock and pending-tick findings was
  verified (`backend/witcher_larp/lord_runtime.py:471`,
  `backend/witcher_larp/lord_runtime.py:548`,
  `backend/witcher_larp/timer_service.py:255`,
  `tests/test_lord_runtime.py:193`,
  `tests/test_lord_runtime.py:539`).

## Pass 9 Checked Without New Issues

- Backup manual/status routes: `/api/backups/run` and
  `/api/master/backups/status` require master role token, and backup artifacts
  remain covered by earlier restart/manifest checks; no new auth or recovery
  issue was verified (`backend/witcher_larp/app.py:875`,
  `backend/witcher_larp/app.py:883`,
  `tests/test_admin_studio_contract.py:316`).
- Timer ordinary idempotency: sequential and restart timer replay remain
  covered by primary-keyed `applied_timer_ticks` and regression tests. A
  possible concurrent timer duplicate was not included because side effects and
  tick insert are in one SQLite transaction with a unique tick key; no
  substantial duplicate state mutation was proven in this pass
  (`backend/witcher_larp/timer_service.py:69`,
  `backend/witcher_larp/timer_service.py:372`,
  `tests/test_act_timer_runtime.py:97`).
- Review/correction closure: non-PvE review side effects, resolved review
  blockers and correction-settlement gaps remain covered by baseline `AUD-002`
  and existing `AUD-NEXT-015`, `AUD-NEXT-020`, `AUD-NEXT-022` and
  `AUD-NEXT-024`; no additional distinct review lifecycle issue was verified.
- Import/validation gates: production profile, role tokens, act/unlock coverage,
  QR/manual honesty, reward policy, final-summary policy, paper forms and
  lord/sorceress/PvP business validations were rechecked through targeted
  `rg -n`; no new content validation issue beyond already recorded matrix
  issues was verified.
- Tests/TaskOS subagent returned the Gwent round sequencing issue integrated as
  `AUD-NEXT-030`; no additional TaskOS/generated-view issue was integrated.

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
- Pass 3: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 3: `uv run pytest -q` -> 221 passed, 1 warning, 505.85s.
- Pass 4: checks were deferred while `uv`/`git` escalated commands were
  temporarily blocked; after Pass 6 docs, `uv run python scripts/taskctl.py
  validate` -> `tasks.json is valid (81 tasks)`, and `uv run pytest -q` -> 221
  passed, 1 warning, 222.02s.
- Pass 5: covered by the deferred post-Pass 6 validation/full-suite run above;
  no product code changed between Pass 4 and Pass 6.
- Pass 6: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 6: `uv run pytest -q` -> 221 passed, 1 warning, 222.02s.
- Pass 7: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 7: `uv run pytest -q` -> 221 passed, 1 warning, 224.06s.
- Pass 8: checks not rerun per user direction; no product code changed after
  the Pass 7 green `validate` and full-suite run.
- Pass 9: `uv run python scripts/taskctl.py validate` -> `tasks.json is valid
  (81 tasks)`.
- Pass 9: `uv run pytest -q` not run per user direction; product code was not
  changed.

## Convergence Log

- After Pass 1: 6 new substantial findings; consecutive zero-new passes = 0.
- After Pass 2: 12 new substantial findings; consecutive zero-new passes = 0.
- After Pass 3: 2 new substantial findings; consecutive zero-new passes = 0.
- After Pass 4: 1 new substantial finding; consecutive zero-new passes = 0.
- After Pass 5: 1 new substantial finding; consecutive zero-new passes = 0.
- After Pass 6: 1 new substantial finding; consecutive zero-new passes = 0.
- After Pass 7: 3 new substantial findings; consecutive zero-new passes = 0.
- After Pass 8: 0 new substantial findings; consecutive zero-new passes = 1.
- After Pass 9: 4 new substantial findings; consecutive zero-new passes = 0.
