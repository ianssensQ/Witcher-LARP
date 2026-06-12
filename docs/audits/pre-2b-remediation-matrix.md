# Pre-2B remediation matrix для AUD-NEXT-001..046

Дата решения: 2026-06-04.

Источник: `docs/audits/stage1-stage2-code-audit-supplement.md` и
`docs/audits/stage1-stage2-business-coverage-matrix.md`.

Эта матрица является рабочим gate-checklist для `TASK-082`-`TASK-087`.
Она не закрывает баги сама по себе: закрытие происходит только через
backend/domain/import/sync/snapshot evidence в owner-задачах или через явное
решение `TASK-087` об accepted residual risk с owner/workaround.

## Правила классификации

- Все P1 остаются blocking до backend/domain/import fix. Заранее downgrade для
  P1 не применяется.
- P2 считается blocking перед Stage 2B, если есть прямой обход через
  API/sync/snapshot/import, утечка hidden data, потеря authoritative state или
  риск ложной final evidence.
- UI-only guardrail допустим только для low-risk non-blocking P2 и всегда
  помечается как `mitigation`, а не `fixed`.
- Paper recovery без `roll` или `roll_log` не может auto-accept. Такой recovery
  идет в review с явным `master override reason`.
- Visibility policy: игроки видят только публичные bands/labels; лорды видят
  свои точные данные, а чужие pressure/hidden signals только coarse или не видят
  вовсе.
- `AUD-NEXT-034` закрывается в `TASK-083`: допустима честная runbook boundary
  вместо готового restore, если Admin ready-поверхность больше не обещает
  непроверенный restore.

## Owner checklist

| Owner | Область | AUD-NEXT ids |
| --- | --- | --- |
| `TASK-082` | visibility/auth projection | `002`, `003`, `029`, `035`, `043` |
| `TASK-083` | sync/recovery/restore | `004`, `007`, `009`, `020`, `028`, `033`, `034`, `040`, `041` |
| `TASK-084` | timers/final/review lifecycle | `010`, `011`, `015`, `016`, `019`, `027`, `039`, `042` |
| `TASK-085` | gameplay authority | `001`, `005`, `006`, `008`, `012`, `013`, `014`, `017`, `018`, `021`, `022`, `023`, `024`, `025`, `026`, `030`, `038` |
| `TASK-086` | import/content invariant gates | `031`, `032`, `036`, `037`, `044`, `045`, `046` |

## Issue matrix

| Issue | Sev | Primary owner | Bucket | Blocking | Evidence для закрытия | UI/test mitigation |
| --- | --- | --- | --- | --- | --- | --- |
| `AUD-NEXT-001` | P1 | `TASK-085` | backend authority / lord battle | yes | Capture settlement removes or reviews losing defender garrisons before territory ownership flips. | Lord UI may show contested cleanup state, but fixed only after runtime rejects stale active defender garrison. |
| `AUD-NEXT-002` | P2 | `TASK-082` | visibility/auth projection | yes | `/api/qr/lookup` requires player-code auth, derives `player_id` from auth context and creates no anonymous/wrong-player attempts. | QR UI hides manual identity fields only as mitigation; API auth regression is required. |
| `AUD-NEXT-003` | P2 | `TASK-082` | visibility/auth projection | yes | Player auth/snapshot payloads expose only public reputation band/label, never exact hidden numeric value. | UI can avoid showing numbers, but network JSON must be redacted. |
| `AUD-NEXT-004` | P2 | `TASK-083` | sync/recovery | yes | Rejected malformed paper intake does not reserve `paper_form_id`; corrected same-form recovery can apply/review normally. | Admin UI can warn about rejected attempts, but duplicate authority is backend-side. |
| `AUD-NEXT-005` | P2 | `TASK-085` | backend authority / PvP | yes | Ordinary player-created full PvP challenges cannot bypass token pacing or started-match caps with `mandatory=false`. | PvP UI removes unsafe `mandatory` control; direct API regression must reject or charge tokens. |
| `AUD-NEXT-006` | P2 | `TASK-085` | backend authority / PvP | yes | Queued challenges no longer block targets as active before table/start authority exists, or have bounded server policy. | UI can show queue state, but server active-blocker semantics must be authoritative. |
| `AUD-NEXT-007` | P1 | `TASK-083` | sync/recovery | yes | Offline PvE is validated against event creation/reveal time and accepted unlock proof, not only current sync-time act. | Mobile can show future-act lock, but stale queued events must be rejected/reviewed by backend. |
| `AUD-NEXT-008` | P1 | `TASK-085` | backend authority / rewards | yes | Reward approval requests require accepted/reviewable PvE provenance owned by actor, or master-only authority. | UI hides standalone reward grant fields; backend must reject minting without provenance. |
| `AUD-NEXT-009` | P2 | `TASK-083` | sync/recovery | yes | Unique QR consume insert result is authoritative; conflict loser gets no accepted side effects. | Client retry messaging is mitigation; atomic backend conflict handling is required. |
| `AUD-NEXT-010` | P1 | `TASK-084` | final authority | yes | Final summary keeps latest valid pre-lock magical intent as authority and separates later disputes. | UI can disable post-lock intent, but summary must ignore invalid overwrite attempts. |
| `AUD-NEXT-011` | P2 | `TASK-084` | final summary evidence | yes | Seed Gwent fixture is not counted as real PvP evidence; runtime/paper/master evidence clears the final missing item. | Admin UI can label fixture rows, but final summary test must prove evidence source. |
| `AUD-NEXT-012` | P1 | `TASK-085` | backend authority / assets | yes | Owned asset locks are scoped by owner and asset type; unrelated owners are not blocked by same asset id. | Trade/PvP UI may show lock owner, but lock ledger authority is backend-side. |
| `AUD-NEXT-013` | P1 | `TASK-085` | final authority / assets | yes | Final summary exposes current owned final-relevant artifacts/items/cards after approvals, trades and PvP. | UI can surface owner ledger, but summary data must come from authoritative ownership. |
| `AUD-NEXT-014` | P1 | `TASK-085` | backend authority / Gwent visibility | yes | Gwent start accepts only actor-owned mulligans for non-masters and returns viewer-scoped private payloads. | UI hides opponent hand controls; API must reject foreign mutation and redact hands. |
| `AUD-NEXT-015` | P2 | `TASK-084` | review lifecycle / final summary | yes | Final summary and review queue filter open blockers only; resolved reviews remain history, not unresolved disputes. | Admin UI can separate history/open tabs, but backend summary filter is required. |
| `AUD-NEXT-016` | P2 | `TASK-084` | final summary evidence | yes | Pending lord tick rewards appear in final evidence/dispute sections while unresolved. | UI can badge pending income, but final summary JSON must include it. |
| `AUD-NEXT-017` | P1 | `TASK-085` | backend authority / lord orders | yes | Lord-token order source is normalized to `lord_panel`; only authenticated master/recovery routes can override final lock. | Lord UI removes source field, but direct payload bypass must fail. |
| `AUD-NEXT-018` | P2 | `TASK-085` | backend authority / sorceress | yes | Potion use validates real PvE scene/check context and enforces one-potion cap per real scene. | UI scene picker is mitigation; backend rejects fake scene ids. |
| `AUD-NEXT-019` | P2 | `TASK-084` | timer lifecycle / lord runtime | yes | Raid effects expire or transition through timed debuff/loot lifecycle and stop appearing as active after duration. | Lord UI can show countdown, but runtime/final projections must reconcile expiry. |
| `AUD-NEXT-020` | P2 | `TASK-083` | paper recovery | yes | Approved/corrected conflicted paper PvE replays ordinary PvE side effects through domain checks. | Admin review UI can show recovered payload, but approval must mutate runtime state correctly. |
| `AUD-NEXT-021` | P2 | `TASK-085` | backend authority / sorceress consent | yes | Favorite lifecycle supports decline/cancel/remove/change or equivalent state transitions without deadlocking caps. | UI actions help operators, but service caps must ignore/settle non-consenting rows correctly. |
| `AUD-NEXT-022` | P2 | `TASK-085` | backend authority / PvP corrections | yes | PvP match corrections route through settlement helper and apply/release stake/table/challenge state exactly once. | Admin UI can constrain correction form, but generic direct patch cannot be authority. |
| `AUD-NEXT-023` | P2 | `TASK-085` | backend authority / lord logistics | yes | Fort capacity is modeled/validated and transfer/capture paths reject over-cap garrisons. | Lord UI can show capacity, but runtime must enforce it. |
| `AUD-NEXT-024` | P2 | `TASK-085` | backend authority / trade corrections | yes | Trade corrections settle/release locks and gold/asset ownership through domain helper, not generic SQL patch. | Admin UI can limit fields, but terminal correction requires domain settlement. |
| `AUD-NEXT-025` | P2 | `TASK-085` | backend authority / reward corrections | yes | Corrected reward assets are checked against active locks before grant or rerouted to review. | Admin UI can warn on conflicts, but reward service must reject locked replacement grants. |
| `AUD-NEXT-026` | P2 | `TASK-085` | backend authority / trade lifecycle | yes | Pending trade locks have timeout/cancel lifecycle that releases locks with audit evidence. | UI can show timeout clock, but service/timer path must perform release. |
| `AUD-NEXT-027` | P1 | `TASK-084` | final lock authority | yes | Direct Final Act start applies or requires final-lock side effects before final play begins. | Admin UI wizard is mitigation; backend route must not skip final lock. |
| `AUD-NEXT-028` | P2 | `TASK-083` | sync/recovery | yes | Duplicate event retry returns original status/reason so client preserves review/rejected/pending visibility. | Mobile UI can display retry status, but server duplicate response must carry original decision. |
| `AUD-NEXT-029` | P1 | `TASK-082` | visibility/snapshot projection | yes | Player snapshots redact master-only and unrevealed artifact rows/fields. | Mobile UI hiding sections is not enough; snapshot JSON must omit hidden metadata. |
| `AUD-NEXT-030` | P2 | `TASK-085` | backend authority / Gwent sequence | yes | Player-submitted Gwent round number must equal server next round; skip/backfill is master correction only. | UI stepper prevents honest mistakes, but API rejects out-of-sequence rounds. |
| `AUD-NEXT-031` | P1 | `TASK-086` | import validation | yes | Import rejects PvE tier/DC values outside approved ranges before runtime consumes them. | Import UI can show friendly errors, but CLI/validator is authority. |
| `AUD-NEXT-032` | P1 | `TASK-086` | import validation | yes | Lord army unit validation rejects zero HP and out-of-range battle stats before battle runtime. | Content UI validation is secondary; seed validation and runtime guard are required. |
| `AUD-NEXT-033` | P2 | `TASK-083` | sync/recovery / mobile queue | yes | Mobile event queue is partitioned by player/session and wrong-actor sync is rejected or held for recovery. | Mobile UI can warn on account switch, but sync payload/server checks must bind actor. |
| `AUD-NEXT-034` | P2 | `TASK-083` | sync/recovery / restore readiness | blocking until boundary | Either guarded restore is implemented, or Admin ready surface/runbook honestly marks restore out of scope. | UI must not present restore as ready if it is only a stub. |
| `AUD-NEXT-035` | P1 | `TASK-082` | visibility/snapshot projection | yes | Player snapshots redact future/unique QR/manual IDs and sensitive scenario links. | Mobile UI cannot rely on hidden controls; snapshot payload must be safe. |
| `AUD-NEXT-036` | P2 | `TASK-086` | import validation / trade seed | yes | Seed terminal/pending trade transfers require source debit/provenance or contested review; no asset/potion minting. | Import UI may explain contested rows, but validator/runtime import must block unsafe grants. |
| `AUD-NEXT-037` | P2 | `TASK-086` | import validation / signed resources | yes | Signed economy/resource ranges are constrained for runtime consumers. | Admin content UI can pre-check numbers, but seed validation remains authority. |
| `AUD-NEXT-038` | P2 | `TASK-085` | backend authority / corrections | yes | Master correction APIs use per-target invariant validators or typed actions and reject impossible resource states. | Admin UI field constraints are mitigation; API must reject impossible patches. |
| `AUD-NEXT-039` | P2 | `TASK-084` | timer reconciliation | yes | Role endpoints reconcile due timer-derived state after restart before timer-dependent reads/actions. | UI refresh prompts are mitigation; server read boundary must be authoritative. |
| `AUD-NEXT-040` | P2 | `TASK-083` | sync/recovery / client sequence | yes | Client sequence gaps, duplicates and out-of-order batches are detected and rejected/reviewed deterministically. | Mobile UI can display sequence recovery state, but sync service must detect gaps. |
| `AUD-NEXT-041` | P2 | `TASK-083` | paper recovery | yes | Clean paper PvE requires real `roll`/`roll_log` or review with explicit master override reason; no synthetic d20 auto-accept. | Admin form must ask for roll evidence, but backend controls accept/review decision. |
| `AUD-NEXT-042` | P2 | `TASK-084` | NPC/review lifecycle | yes | NPC P0/P1 runtime events have close/resolution lifecycle or route through review statuses. | Admin UI can expose close action, but final summary must filter open statuses only. |
| `AUD-NEXT-043` | P2 | `TASK-082` | visibility/lord projection | yes | Lord and master diplomacy projections are split; lord state omits or coarse-buckets foreign order pressure. | Lord UI cannot hide data that remains in JSON; projection contract test required. |
| `AUD-NEXT-044` | P1 | `TASK-086` | import validation / map | yes | Import requires positive integer `map_edges.mp_cost` and runtime guards movement cost. | Map UI can flag bad edge data, but validator/runtime must reject unsafe cost. |
| `AUD-NEXT-045` | P1 | `TASK-086` | import validation / timers | yes | `auto_timers.csv` validates timer enums/effects and required final-lock/pre-final-backup timers. | Admin content UI may show timer errors; validator blocks unknown/no-op critical effects. |
| `AUD-NEXT-046` | P2 | `TASK-086` | import validation / order caps | yes | Canonical active order cap semantics cannot be disabled by imported status flags. | Admin UI can show status-rule warnings, but runtime/validator must enforce canonical cap counting. |

## Gate checklist для TASK-087

- Все `AUD-NEXT-001..046` имеют ровно один primary owner в `TASK-082`-`TASK-086`.
- Нет unresolved P1 без backend/domain/import evidence или отдельного documented
  downgrade с evidence.
- Blocking P2 закрыты owner-задачей или имеют явное accepted residual-risk
  решение с owner/workaround.
- Ни один issue не закрыт только потому, что обычный UI скрывает опасное поле,
  кнопку или route.
- Для visibility issues проверяется фактический API/snapshot/lord-state JSON, а
  не только rendered UI.
- Для sync/recovery issues проверяются direct sync/retry/paper paths, включая
  offline/restart и неправильного actor.
- Для import/content issues `uv`/CLI validation остается источником истины даже
  при наличии дружелюбной Admin UI-ошибки.

## Решение gate TASK-087

Дата решения: 2026-06-04.

Статус: pre-Stage-2B gate accepted. После `taskctl done TASK-087` и `taskctl
sync` Stage 2B может начинаться с `TASK-045`; `TASK-058` и `TASK-050` остаются
зависимыми от своих UI/device acceptance-задач.

Проверка покрытия:

- Matrix sanity check: 46 строк `AUD-NEXT-001..046`, пропусков и дублей нет;
  primary owners распределены как `TASK-082:5`, `TASK-083:9`, `TASK-084:8`,
  `TASK-085:17`, `TASK-086:7`.
- `TASK-082` закрыл visibility/auth projection: QR lookup требует player-code
  auth, snapshot/auth payloads редактируют hidden reputation/artifact/QR/manual
  data, lord projection не раскрывает точные чужие order-pressure значения.
- `TASK-083` закрыл offline sync, paper recovery и restore boundary: duplicate
  retry возвращает исходный статус, sequence gaps/out-of-order и wrong-actor
  sync отклоняются, future-act PvE проверяется по времени события, paper PvE
  требует roll evidence, conflicted paper approval проводит доменные side effects.
- `TASK-084` закрыл timers/final/review lifecycle: due timer state reconciles on
  role reads/actions, final lock/direct Final Act boundaries and
  final_summary/review/NPC lifecycle blockers are covered by runtime tests.
- `TASK-085` закрыл gameplay authority для PvP/Gwent, asset/reward/trade locks,
  lord battle/runtime, sorceress lifecycle, typed corrections и final_summary
  ownership evidence.
- `TASK-086` закрыл import/content invariant gates: PvE tier/DC, lord unit
  stats, seed trade provenance, signed economy ranges, positive map MP costs,
  auto timer effects and canonical active-order caps.

Residual risk:

- `AUD-NEXT-034` принят как non-blocking P2 boundary, не как реализованный
  restore feature. Owner/workaround: `TASK-036` должен доказать backup/restore
  rehearsal и game-day runbook; до этого Admin Studio честно показывает
  `restore_backup` как `pending_backend`, а рабочая recovery-процедура для
  Stage 2B опирается на backup status/manual backup, SQLite artifact copy,
  snapshot export/import и явный runbook step. Если restore становится
  release-critical UI/API feature, он снова блокирует `TASK-037`.

UI guardrail rule:

- Ни один issue не закрыт только потому, что обычный UI прячет поле, кнопку или
  route. Для закрытых строк evidence приходит из backend/domain/import/sync/
  snapshot/API checks; UI guardrails остаются дополнительной Stage 2B UX
  защитой для честных пользователей и операторов.

Gate result:

- Unresolved P0/P1 перед Stage 2B: none.
- Blocking P2 без owner/workaround: none.
- Accepted residual risk без owner/workaround: none.
