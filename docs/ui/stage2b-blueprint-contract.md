# Stage 2B UI blueprint contract

Этот документ задает обязательные артефакты перед реализацией Playable Role UI.
Он не заменяет `tasks.json`: он объясняет, что именно должны создать
`TASK-045`, `TASK-067`, `TASK-058` и `TASK-050`, чтобы визуальная приемка была
проверяемой, а не устной.

## Required artifacts

- `docs/ui/stage2b-screen-map.md` - полный список экранов по ролям:
  ведьмак, чародейка, лорд, мастер/NPC, общие auth/sync/error states.
- `docs/ui/stage2b-flow-map.md` - сценарии "нажал -> клиент отправил ->
  сервер решил -> экран изменился" для всех release-critical маршрутов.
- `docs/ui/stage2b-api-map.md` - screen/API/read-model mapping: откуда экран
  читает данные, какой endpoint или snapshot field использует, какую mutation
  отправляет, какой payload/response ожидает, где visibility boundary.
- `docs/ui/stage2b-state-matrix.md` - offline, pending sync, rejected,
  needs_master_review, duplicate, cooldown, locked reward, wrong token,
  hidden/review-only data and final-lock states per screen.
- `docs/ui/stage2b-visual-acceptance.md` - ссылки на прототип/Open Design
  artifact, список экранов для user visual accept и обязательные скриншоты.
- `docs/ui/stage2b-visual-asset-manifest.md` или `visual_assets.csv` - asset
  id, surface, source/owner, license_status, prompt/reference, target path,
  fallback label and screenshot acceptance note.
- `prototypes/stage2b/` или Open Design project - визуальный прототип экранов
  до реализации `TASK-046`, `TASK-047`, `TASK-048` и `TASK-049`.
- `reports/stage2b/` - evidence после hardening: device evidence,
  UI-flow evidence, screenshot evidence and defects with owner/workaround.

## Screen map minimum

For every screen, record:

- `screen_id`
- role: `witcher`, `sorceress`, `lord`, `master`, `npc_master`, `shared`
- surface: Godot mobile, lord browser panel, Admin Studio, paper outage only
- purpose
- primary actions
- read model source
- mutation endpoint or local queued event
- visibility boundary
- offline/error/review/locked states
- acceptance screenshot or prototype route

## Flow map minimum

For every release-critical flow, record:

- actor and starting state
- UI trigger/control
- client-side behavior, including local queue if offline
- backend endpoint/service or snapshot source
- payload and idempotency key when relevant
- response/review decision
- resulting visible state
- fallback/recovery path
- acceptance test or smoke step

Examples:

- Witcher: login -> snapshot -> QR/manual PvE -> result -> cooldown/reward
  approval -> offline restart -> sync.
- Sorceress: potion buy/transfer/use -> spell -> favorite consent ->
  alignment evidence -> locked magical intent.
- Lord: login -> castle/selected territory home -> territory switch -> recruit
  accumulated units -> army/garrison transfer -> building -> order -> raid ->
  map route -> contested claim -> battle -> return to castle/territory home.
- Personal Gwent: challenge -> table/queue -> deck/hand/mulligan ->
  rows/pass/rounds -> finish/stake -> refusal/review.
- Admin: paper recovery form -> conflict preview -> event sync/review ->
  final summary evidence.

## API map rule

Every UI surface must name a read source, not only mutation endpoints. If a
screen needs current trade history, favorite state, Gwent match state, review
state, hidden-data redaction, locked assets or final-lock state and no endpoint
or snapshot field exists, the map must mark it as a blocker for the owning task.

UI must not invent local truth for authoritative state. Local state is allowed
only for offline queue, visual draft input, and display of the last known
snapshot with an explicit stale/offline label.

## Visual prototype rule

Before role UI implementation starts, the user should be able to visually accept
the intended experience from a static local prototype or Open Design artifact.
The prototype does not need final art, animation or complete runtime logic, but
it must show:

- all player class home screens and critical action screens;
- lord castle/territory home, bottom-left minimap, bottom-center
  army/garrison/recruit lanes, bottom-right act/MP controls, map, building tree,
  battle board, recruit/raid/order;
- personal Gwent table in mobile portrait;
- Admin paper recovery, review and final summary surfaces;
- major error/offline/review/locked states;
- responsive desktop/mobile framing.

Generated raster art may be used for original castles, forts, card portraits,
map texture and atmospheric assets. Text-heavy UI mockups should remain in
HTML/CSS/Open Design/Godot-style layouts so labels and state copy are exact.

## Acceptance rule

`TASK-050` cannot pass on chat-only claims. It reviews the persistent blueprint,
prototype and evidence artifacts listed above, plus real-device and browser
smoke evidence from `TASK-058`.
