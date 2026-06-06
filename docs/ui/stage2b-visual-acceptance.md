# Stage 2B visual acceptance

Этот документ фиксирует визуальный контракт `TASK-067` перед реализацией
игровых UI задач. Он связывает утвержденные референсы, локальный прототип,
runtime data binding и будущие screenshot evidence.

## Прототип

- Primary editable Figma file:
  `https://www.figma.com/design/7BNdyJtd7QSH52QzXjT0Ol`.
- Локальный HTML/CSS прототип: `prototypes/stage2b/index.html`.
- CSS: `prototypes/stage2b/style.css`.
- Локальные fallback-ассеты: `prototypes/stage2b/assets/`.
- Язык прототипа: русский UI text, runtime IDs рядом с важными узлами,
  экранами, картами, зданиями и событиями.
- Референсы используются только как грамматика взаимодействия и layout.
  Production-ассеты должны быть original/local/generated.

## Figma visual source

Figma является основным visual acceptance источником для реализации Stage 2B.
Файл содержит editable frames:

- `00 Cover / TASK-067 visual direction`
- `01 Lord / castle and territory home`
- `02 Witcher / mobile field journal`
- `03 Sorceress / mobile arcane dossier`
- `04 Personal Gwent / mobile table`
- `05 Admin Studio / ops evidence board`
- `06 Asset board / implementation handoff`

HTML-прототип в репозитории остается локальным fallback: он показывает те же
runtime IDs, обязательные states и asset-binding точки, но не заменяет Figma как
источник композиции, плотности экранов, визуального веса карт/портретов/карты и
role-specific art direction.

## Visual reference matrix

| Reference grammar | Owned UI element | Data source | Acceptance screenshot |
| --- | --- | --- | --- |
| Темное тактильное fantasy UI | Shared auth/sync shell | `/health`, auth endpoints, local sync files | Figma cover + `reports/stage2b/screenshots/shared-auth-sync.png` |
| Heroes-like castle screen reference grammar | `L1 Castle / Territory Home` | `GET /api/lords/{lord_id}/state`, selected `territory_id`, lord resources, active army, garrison, recruit stock, act timer, MP | Figma `01 Lord` + `reports/stage2b/screenshots/lord-castle-home.png` |
| Painted fantasy strategy map | `L2 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv`, `movement_rules.csv` | Figma `01 Lord` + `reports/stage2b/screenshots/lord-map-command-table.png` |
| Olden Era-like building tree grammar | `L6 Building Tree` | `buildings.csv`, selected territory building catalog | Figma `01 Lord` + `reports/stage2b/screenshots/lord-building-tree.png` |
| Territory home/card grammar | `L4 Territory Detail`, `L5 Army Transfer` | `territories.csv`, `map_nodes.csv`, lord garrisons, active army location, reserve | Figma `01 Lord` + `reports/stage2b/screenshots/lord-territory-home.png` |
| War-table tactical board | `L10 Lord Battle` | `/api/lord-battles`, `army_unit_cards.csv`, `lord_battle_rules.csv` | Figma `01 Lord` + `reports/stage2b/screenshots/lord-battle-board.png` |
| Field journal mobile | `W1-W9` | player snapshot, QR/PvE/event queue, inventory/order/trade read models | Figma `02 Witcher` + `reports/stage2b/screenshots/witcher-mobile-flow.png` |
| Arcane dossier mobile | `Sorc1-Sorc7` | sorceress state, spells, potions, favorites, alignment evidence | Figma `03 Sorceress` + `reports/stage2b/screenshots/sorceress-mobile-flow.png` |
| Witcher 3 Gwent-like table grammar | `W10 Personal Gwent` | PvP/Gwent challenge, match and table read models | Figma `04 Personal Gwent` + `reports/stage2b/screenshots/personal-gwent-mobile.png` |
| Dense ops console | `A1-A11 Admin Studio` | master overview, review, paper recovery, NPC, final summary endpoints | Figma `05 Admin Studio` + `reports/stage2b/screenshots/admin-recovery-final.png` |

## Accepted visual direction

- Общий тон: темное тактильное фэнтези, role-neutral shared вход и sync,
  разные role accents без превращения ролей в разные приложения.
- Лорды: главный экран после входа - замок/выбранная территория на full-screen
  painted background, максимально близко к предоставленному Heroes-like
  референсу. Сверху тонкая строка ресурсов, слева круговые иконки действий без
  постоянных подписей, снизу слева мини-карта, снизу по центру две линии
  армии/гарнизона и блок найма, снизу справа плашка акта/таймера, над ней
  полукруглая шкала MP. Painted strategy `venue_map_v1` остается отдельным
  экраном карты для движения, а не главным lord home.
- Ведьмаки: field journal на телефоне, W1 character-sheet first, clear oath для
  physical presence, PvE scene card с app-generated d20/log, categorized
  inventory cards, contract slips, sealed journal goals и persistent sync strip.
- Чародейки: arcane dossier, сдержанные silver+violet accents, spell cards,
  apothecary potion cards, pact cards и evidence dossier для финальных следов.
- Admin/NPC-master: плотная ops console, triage + forms, conflict preview,
  reason/operator, paper recovery и final evidence board.

## Screen acceptance routes

| Prototype route | Screen coverage | Required state variants |
| --- | --- | --- |
| `index.html#shared` | `Shared1`, `Shared2`, `Shared3` | server unreachable, wrong token, offline snapshot, pending sync, sync_error, needs_master_review |
| `index.html#lords` | `L1-L12` | castle home, territory switch, hero-not-here army lock, bottom-left minimap, bottom-right act/MP, owner/neutral/contested, no MP, invalid route, garrison capacity, locked/unlocked/purchased building, recruit stock, escrow lock, battle legal/target/timer/auto |
| `index.html#witchers` | `W1-W9` | stale snapshot, future act locked, manual rate limit, cooldown, app d20, locked reward, inventory lock, order/trade review |
| `index.html#sorceresses` | `Sorc1-Sorc7` | insufficient mana, invalid target, pending transfer lock, pending consent, cap exceeded, visibility, final lock review |
| `index.html#gwent` | `W10 Personal Gwent` | queued/table active, rows, weather, hand, pass, locked stake, review/refusal |
| `index.html#admin` | `A1-A11` focus on `A3`, `A5`, `A8`, `A11` | P0/P1/P2/P3, duplicate/conflict preview, missing reason, paper recovery, unresolved final locks |

## Figma frame acceptance

| Figma frame | Implementation target | Must preserve |
| --- | --- | --- |
| `01 Lord / castle and territory home` | lord browser panel | full-screen castle/territory art, sparse overlaid UI, top resource strip, left circular action dock, bottom-left minimap, bottom-center army/garrison/recruit lanes, bottom-right act timer and MP arc, right territory bubbles, building tree and 5x6 battle table as linked screens |
| `02 Witcher / mobile field journal` | Godot mobile witcher shell | portrait/character sheet first, QR oath, PvE d20 log, categorized inventory, sealed goal journal, persistent sync strip |
| `03 Sorceress / mobile arcane dossier` | Godot mobile sorceress shell | silver/violet dossier tone, spell cards, potion cards, pact states, alignment evidence and magical intent locks |
| `04 Personal Gwent / mobile table` | Godot personal Gwent | portrait table, scores, rows/weather/hand, turn focus, pass/play controls, stake/review lock |
| `05 Admin Studio / ops evidence board` | admin browser console | dense triage, paper recovery forms, conflict preview, NPC tools, final evidence board |
| `06 Asset board / implementation handoff` | asset production backlog | asset ids, runtime binding, original/local/generated license status, fallback labels |

## Runtime binding notes

- `territory_forts.csv` is not present in the current seed. Territory/fort
  visuals bind to `territories.csv`, `map_nodes.csv`, `map_edges.csv`, garrison
  state and active army/reserve state until a separate fort catalog exists.
- Lord home is a castle/territory visual layer over the lord state; each owned
  territory reuses the same UI pattern with different background, local income,
  garrison, recruit stock and minimal building tree. The top active-army lane is
  empty/locked when the hero-army is not in the selected territory.
- Lord map is a separate visual layer over `venue_map_v1`; it is not QR, GPS or
  internet-dependent tracking. QR/manual physical presence remains mobile-only.
- The prototype shows only original code-native UI compositions. Any future
  raster map, castle, fort, card portrait or texture must be generated/local art
  with fallback labels from `stage2b-visual-asset-manifest.md`.
- Player and lord screens must keep hidden-data redaction: exact enemy garrison,
  hidden goal flags, master-only artifact state and exact reputation thresholds
  are not shown to unauthorized roles.

## Screenshot evidence contract

Future visual QA stores accepted mockups under `reports/stage2b/screenshots/`:

- `shared-auth-sync.png`
- `lord-castle-home.png`
- `lord-territory-home.png`
- `lord-map-command-table.png`
- `lord-building-tree.png`
- `lord-territory-inspector.png`
- `lord-battle-board.png`
- `witcher-mobile-flow.png`
- `sorceress-mobile-flow.png`
- `personal-gwent-mobile.png`
- `admin-recovery-final.png`

Real-device and browser proof after implementation is recorded in
`reports/stage2b/device-evidence.md`.

## IP-safety checklist

- No copied official Heroes, Gwent or Witcher screenshots in production paths.
- No official card art, faction emblems, logos, UI chrome or gallery images.
- References describe layout, density, hierarchy, states and affordances only.
- All future raster assets must have `license_status=original_generated`,
  `original_local` or `in_house_ui`.
- Every image-dependent surface must also have readable fallback labels.
