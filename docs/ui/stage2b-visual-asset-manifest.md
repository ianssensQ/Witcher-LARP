# Stage 2B visual asset manifest

Manifest fields: asset id, surface, runtime binding, source/owner,
license status, prompt/reference note, target path, fallback label and
acceptance note.

## Policy

- Production files must be original/local/generated or simple in-house UI art.
- Third-party screenshots, official card art, faction emblems, logos and gallery
  images are not allowed in production asset paths.
- Curated references are layout and interaction grammar only.
- If an image fails, the UI must remain playable through fallback labels,
  IDs, icons, state badges and readable controls.

## Source hierarchy

1. Primary visual source: Figma file
   `https://www.figma.com/design/7BNdyJtd7QSH52QzXjT0Ol`.
2. Repo-local fallback prototype: `prototypes/stage2b/index.html`.
3. Repo-local fallback visual assets: `prototypes/stage2b/assets/`.
4. Future production assets: original/local/generated files under the target app
   asset paths listed below.

## Figma and local prototype assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `figma_stage2b_visual_acceptance` | all Stage 2B surfaces | `Shared2-Shared3` plus hidden `Ops0`, `L1-L10`, shared mobile `W1-W11` with `W6A/W6B/W6C`, future `Sorc1-Sorc7`, `A1-A11` | Figma/Codex after user approval | `in_house_ui` | Editable design frames for implementation handoff; no official Witcher/Gwent/Heroes art | `https://www.figma.com/design/7BNdyJtd7QSH52QzXjT0Ol` | Stage 2B visual acceptance | Primary composition, density, hierarchy and art-direction source |
| `proto_venue_map_v1_svg` | `L2 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv`, future `lord_map_layout`, `lord_map_intel` | Codex/local SVG | `in_house_ui` | Painted-map fallback for repo-local prototype with explicit visual/data topology | `prototypes/stage2b/assets/venue-map-v1.svg` | `venue_map_v1` | Keeps topology, owner, contested, hidden enemy details and route-cost labels visible |
| `proto_lord_portrait_svg` | `L1 /lords/home` | lord role/domain context | Codex/local SVG | `in_house_ui` | Original lord portrait mood reference | `prototypes/stage2b/assets/lord-portrait.svg` | lord portrait | Supports lord home tone without official character art |
| `proto_witcher_portrait_svg` | `W1` character sheet | player snapshot | Codex/local SVG | `in_house_ui` | Original witcher portrait mood reference | `prototypes/stage2b/assets/witcher-portrait.svg` | witcher portrait | Character-sheet-first mobile composition includes visible portrait art |
| `proto_sorceress_portrait_svg` | `Sorc1` dossier | sorceress state | Codex/local SVG | `in_house_ui` | Original sorceress portrait mood reference | `prototypes/stage2b/assets/sorceress-portrait.svg` | sorceress portrait | Silver/violet dossier composition includes visible portrait art |
| `proto_castle_tree_art_svg` | `L6 Building Tree` | `buildings.csv` | Codex/local SVG | `in_house_ui` | Castle backdrop and tier-tree direction | `prototypes/stage2b/assets/castle-tree-art.svg` | building tree | Demonstrates visual art behind Olden Era-like tree grammar |
| `proto_territory_cards_strip_svg` | `L4-L5 Territory Fort` | `territories.csv`, garrison state | Codex/local SVG | `in_house_ui` | Territory/fort card art-direction strip | `prototypes/stage2b/assets/territory-cards-strip.svg` | territory cards | Confirms every territory needs readable card art/fallback label |
| `proto_personal_gwent_table_svg` | `W10 Personal Gwent` | Gwent table read model | Codex/local SVG | `in_house_ui` | Portrait mobile Gwent table fallback | `prototypes/stage2b/assets/personal-gwent-table.svg` | Gwent table | Shows rows/weather/hand visual hierarchy without copied Gwent art |
| `proto_admin_evidence_board_svg` | `A1-A11 Admin Studio` | review/final/paper/NPC state | Codex/local SVG | `in_house_ui` | Evidence-board art direction for ops console | `prototypes/stage2b/assets/admin-evidence-board.svg` | evidence board | Makes Admin final/recovery surfaces visually inspectable |

## Shared UI assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ui_shared_dark_shell` | Shared auth/sync | `Shared2-Shared3` plus hidden `Ops0` | Codex/UI | `in_house_ui` | Dark tactile fantasy, role-neutral code login, background auto-connect and sync shell | `prototypes/stage2b/style.css` | Shared auth/sync | Server unreachable, wrong token and sync states visible without making players type server URL |
| `ui_state_badges` | all | state matrix | Codex/UI | `in_house_ui` | Badge system for offline, review, locked, duplicate, cooldown | future UI CSS | state text | Every required state has readable badge |

## Lord assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `lord_castle_home_background_v1` | `L1 Castle / Territory Home` | `domain_*`, selected residence territory | Art generation/Codex | `original_generated` | Shared full-screen painted lord castle background, Heroes-like composition, UI-safe top/bottom/side zones, no copied art and no baked text | future `assets/lord/castle_home_v1.png` | Замок лорда | Background remains visible under sparse UI and supports 16:9 desktop |
| `lord_territory_home_background_set_v1` | `L4 Territory Detail` | `territories.csv`, `map_nodes.csv`, selected `territory_id` | Art generation/Codex | `original_generated` | Same camera/UI grammar as castle home, distinct territory mood for fort/field/village/well/magic/science/forest/lake/swamp/mountain | future `assets/lord/territories/home_*.png` | Территория | Territory switch changes art without changing interaction grammar |
| `lord_home_top_resource_strip_v1` | `L1` top bar | lord resources, income, act/sync | Codex/UI | `in_house_ui` | Thin brass/dark strip; resources centered; gold supports `current (+income/hour)`; top-right `?` and logout sockets | future UI CSS/components | Ресурсы | Minimal chrome, no heavy dashboard card |
| `lord_home_left_action_dock_v1` | `L1` left dock | action availability, battle alert | Codex/UI | `in_house_ui` | Circular icon sockets for buildings, map, notice board, raids and battle; no permanent text; hover/focus reveals Russian label | future UI CSS/components | Действия | Battle icon is red/active only when available |
| `lord_home_bottom_frame_v1` | `L1`, `L5`, `L7` | active army, garrison, recruit stock | Codex/UI | `in_house_ui` | Bottom-center frame with two unit lanes and recruit slots, matching reference density; top lane can render locked empty state | future UI CSS/components | Армия и гарнизон | No text overlap; drag/drop affordance stays inside painted slots |
| `lord_home_minimap_bottom_left_v1` | `L1`, `L2` shortcut | selected territory, hero location, owned territory hints | Art generation/Codex + UI | `original_generated` | Thematic minimap placed bottom-left exactly like the reference; not the full strategic map image one-to-one | future `assets/lord/minimap_v1.png` | Мини-карта | Must stay bottom-left; opens map screen |
| `lord_home_act_mp_bottom_right_v1` | `L1` bottom-right | current act, time to next act, movement MP | Codex/UI | `in_house_ui` | Compact act plaque at bottom-right with semicircle MP gauge above it | future UI CSS/components | Акт и ходы | Must stay bottom-right; MP arc never replaces minimap |
| `lord_recruit_modal_v1` | `L7 Recruit Unit Modal` | selected unit, stock, cost, stats | Codex/UI + generated unit art | `in_house_ui` | Unit widget with art, one-unit stats, quantity slider, auto cost and `Нанять` button | future UI CSS/components | Найм войск | Purchase target is selected territory garrison |
| `lord_map_venue_v1_painted` | `L2 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv`, `lord_map_layout.json` | Art generation/Codex | `original_generated` | Large Olden Era-like fantasy-over-real strategy map over seed topology: roads, forts, fields, villages, wells, magic/science landmarks, forests, lakes, swamp, mountains; no QR anchors and no baked text | future `assets/lord/venue_map_v1.png` | `venue_map_v1` | Pan camera can frame all important zones; route costs, owner, contested, hidden enemy details and excluded zones remain legible through live overlays |
| `lord_map_layout_manifest_v1` | `L2-L3 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv`, map raster bounds | Codex/manual layout | `in_house_ui` | Hand-authored JSON/SVG alignment layer over `lord_map_venue_v1_painted` | future `assets/lord/lord_map_layout.json` | map layout | Contains art asset id, canvas bounds, node coordinates, edge polylines, territory hit-zones, label anchors, minimap transform, intel marker anchors and viewport defaults |
| `lord_map_intel_marker_v1` | `L2-L3 Illustrated Map` | `lord_map_intel`, enemy army/garrison visibility levels, current hero position | Codex/UI | `in_house_ui` | Unknown/presence-only markers for enemy armies and garrisons without revealing exact composition | future UI CSS/SVG layer | Разведданные | Full graph stays visible; hidden enemy details stay redacted unless intel allows |
| `lord_map_horse_marker_v1` | `L2-L3 Illustrated Map` | active army location and pending move route | Art generation/Codex + UI | `original_generated` / `in_house_ui` | Small readable horse/standard marker, one per lord; current lord marker has stronger highlight | future `assets/lord/horse_marker_v1.png` + UI layer | Лошадь лорда | Marker stays readable on dark/bright terrain and animates along route polyline without resizing layout |
| `lord_map_route_layer_v1` | `L2-L3 Illustrated Map` | route preview, edge costs, pending move route | Codex/UI | `in_house_ui` | Live line/path overlay with valid, blocked, no-MP and pending states | future UI CSS/SVG layer | Маршрут | Cheapest route, cost and forced stop on enemy/contested land are obvious before confirm |
| `lord_map_tactical_popup_v1` | `L2-L3 Illustrated Map` | selected territory/army summary with enemy detail redaction | Codex/UI | `in_house_ui` | Compact tactical card over map: name, owner, visible bonus, route cost, Move/cancel; no build/recruit/raid controls | future UI component | Территория | Popup is readable over art and does not hide the clicked territory completely |
| `lord_map_battle_banner_v1` | `L2-L3`, `L10 transition` | `territory_claim`, prebattle/deployment state | Codex/UI | `in_house_ui` | Urgent but compact battle banner with transition to 5x6 board | future UI component | Бой за территорию | Arrival on neutral/enemy immediately shows prebattle/battle entry and disables further move |
| `lord_domain_north_mark` | `/lords/home` and map | `domain_north`, `p_lord_1` | Codex/UI | `in_house_ui` | Original heraldry, green/steel material, no official emblem | future `assets/lord/domain_north.svg` | North Watch | Domain is distinct from River/Forest/Hill |
| `lord_domain_river_mark` | `/lords/home` and map | `domain_river`, `p_lord_2` | Codex/UI | `in_house_ui` | Original heraldry, blue/silver river material | future `assets/lord/domain_river.svg` | River Gate | Domain is distinct and readable |
| `lord_domain_forest_mark` | `/lords/home` and map | `domain_forest`, `p_lord_3` | Codex/UI | `in_house_ui` | Original heraldry, moss/blackwood material | future `assets/lord/domain_forest.svg` | Forest March | Domain is distinct and readable |
| `lord_domain_hill_mark` | `/lords/home` and map | `domain_hill`, `p_lord_4` | Codex/UI | `in_house_ui` | Original heraldry, ochre/stone material | future `assets/lord/domain_hill.svg` | Hill Crown | Domain is distinct and readable |
| `lord_castle_backdrop` | `L1`, `L6 Building Tree` | lord domain state | Art generation/Codex | `original_generated` | Layered painted residence background and tree backdrop, original architecture | future `assets/lord/castle_backdrop.png` | Castle development | Does not obscure tree nodes or prerequisites |
| `lord_building_tree_nodes` | `L6 Building Tree` | `buildings.csv`, selected `territory_id` | Codex/UI | `in_house_ui` | Olden Era-like tree grammar: tier columns, node cards, lines, selected detail; supports full residence tree and smaller territory trees | future UI CSS/components | building id and name | locked/unlocked/purchased states visible |
| `territory_res_north_card` | `L4 Territory Fort` | `territory_res_north`, `node_res_north` | Art generation/Codex | `original_generated` | Northern residence card, fortified manor, original art | future `assets/territories/territory_res_north.png` | North Residence | Owner/garrison/capacity states readable |
| `territory_res_river_card` | `L4 Territory Fort` | `territory_res_river`, `node_res_river` | Art generation/Codex | `original_generated` | River residence card, bridge gate, original art | future `assets/territories/territory_res_river.png` | River Residence | Owner/garrison/capacity states readable |
| `territory_res_forest_card` | `L4 Territory Fort` | `territory_res_forest`, `node_res_forest` | Art generation/Codex | `original_generated` | Forest residence card, timber hall, original art | future `assets/territories/territory_res_forest.png` | Forest Residence | Owner/garrison/capacity states readable |
| `territory_res_hill_card` | `L4 Territory Fort` | `territory_res_hill`, `node_res_hill` | Art generation/Codex | `original_generated` | Hill residence card, stone crown motif, original art | future `assets/territories/territory_res_hill.png` | Hill Residence | Owner/garrison/capacity states readable |
| `territory_capturable_card_set_v1` | `L4 Territory Fort`, `L2 tactical popup` | 19 capturable territories from `docs/game-mechanics.md`: fort, field, village, well/resource, magic, science, forest, lake, swamp and mountain nodes | Art generation/Codex | `original_generated` | Original card/background set for every capturable territory: Slavic fantasy naming, tier identity, physical landmark memory and bonus type; no text baked into art | future `assets/territories/capturable/*.png` | territory name | Every capturable territory has a distinct fallback image/card, visible tier, owner/contested state and garrison capacity binding |
| `lord_unit_tile_set` | `L1`, `L5`, `L7`, `L10` | `army_unit_cards.csv`, recruit stock | Codex/UI + Art generation/Codex | `in_house_ui` / `original_generated` | Unit tiles/cards for infantry, guard, ranged, cavalry, heavy siege, specialist, including lane icons and recruit modal art | future UI CSS/components + `assets/lord/units/*.png` | unit class + stats | Class, tier, ATK/DEF/HP/init/count/rate/stock readable |
| `lord_war_table_board` | `L10 Lord Battle` | lord battle board width 5 height 6 | Codex/UI | `in_house_ui` | Tactical war table, visually distinct from personal Gwent | future UI CSS/components | 5x6 board | Legal move, target, active, timer and auto-resolve visible |
| `lord_command_slip_set` | `L8`, `L9` | raid rules, orders, escrow state | Codex/UI | `in_house_ui` | Paper command slips with status badges | future UI CSS/components | raid/order label | Caps, locks, object conflicts and review visible |

## Shared witcher/sorceress mobile assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mobile_field_journal_shell` | `W1-W11` for witcher and sorceress V0 | player snapshot, event queue, act unlock | Codex/UI | `in_house_ui` | Dark field journal with character sheet first and role skin accents | future Godot theme | Field journal | Character, stats, role skin, sync strip and actions readable |
| `mobile_m1_journal_shell_v1` | `W1 Home / Journal`, `M1` | player snapshot, role skin, resources, sync status, goals/actions | Codex/image generation | `original_generated` | Original dark field-journal background shell inspired by Witcher-like dark fantasy UI mood; no official art, logos, medallions or copied chrome | `prototypes/stage2b-v2/src/assets/generated/mobile/m1-journal-shell-v1.png` | Field journal shell v1 | Candidate visual layer for M1: portrait frame, resource strip, action cards and bottom nav zones are reserved for live UI overlay |
| `mobile_m1_journal_layered_bg_v2` | `W1 Home / Journal`, `M1` | player snapshot, act state, offline status, journal cards | Codex/image generation | `original_generated` | New phone-first dark field-journal background with larger journal bands and reduced top chrome; no official art, logos, medallions or copied UI | `prototypes/stage2b-v2/src/assets/generated/mobile/m1-journal-v2/journal-bg-v2.png` | Field journal background v2 | Production prototype background for layered M1 route; fills 390x844 mobile viewport with live UI zones |
| `mobile_m1_journal_ui_kit_v2` | `W1 Home / Journal`, `M1` | character panel, order panel, goal panel, quick actions, bottom nav, sync sheet | Codex/image generation + chroma-key cleanup | `original_generated` | Separate UI-kit PNG layers: parchment card, metal plaque, portrait frame, action button and nav tab; original monster-hunter journal style, no official art or baked text | `prototypes/stage2b-v2/src/assets/generated/mobile/m1-journal-v2/` | Layered journal UI kit | Components are rendered as physical image layers while labels, states and hit-zones remain live React UI |
| `mobile_m1_witcher_portrait_v1` | `W1 Home / Journal`, `M1` | player profile portrait slot | Codex/image generation | `original_generated` | Original gritty monster-hunter portrait for the M1 frame; Witcher-like dark fantasy mood without official characters, names, medallions, logos or copied armor | `prototypes/stage2b-v2/src/assets/generated/mobile/m1-journal-v2/witcher-portrait-v1.png` | Witcher portrait | Portrait remains readable in the small journal frame and is rendered as a live image layer under text/UI |
| `witcher_qr_oath_panel` | `W2-W3` | `qr_objects.csv`, local QR context | Codex/UI | `in_house_ui` | Clear physical-presence oath, not dramatic ritual | future Godot screen | physical presence | Future act, cooldown and review states visible |
| `witcher_pve_scene_card` | `W4-W5` | `pve_scenarios.csv`, `mobs.csv`, `rewards.csv` | Codex/UI | `in_house_ui` | Scene card with app d20 log, DC, stat, scene HP, reward lock | future Godot screen | PvE result | One-roll-only and reward/cooldown state visible |
| `mobile_gear_inventory_set` | `W6A` | weapons, protection, equipment, active bonuses | Codex/UI | `in_house_ui` | Gear cards with slot, requirement, rarity and lock badges | future Godot screen | gear label | equipped/locked/stale states visible |
| `mobile_bag_item_set` | `W6B` | items, potions, artifacts, quest objects, locked rewards | Codex/UI | `in_house_ui` | Bag cards with rarity, use/trade affordance and lock badges | future Godot screen | asset label | locked/pending/trade states visible |
| `mobile_gwent_deck_set` | `W6C`, `W10` | `gwent_cards.csv`, `gwent_decks.csv` | Codex/UI | `in_house_ui` | Deck builder cards with leader, row/type/rarity and validity badges | future Godot screen | deck/card label | invalid deck, locked card and PvP preflight states visible |
| `witcher_contract_slips` | `W7-W8` | orders and trade transfers | Codex/UI | `in_house_ui` | Contract slips for orders/trade with escrow and review | future Godot screen | order/trade label | Pending lock and object conflict visible |
| `witcher_sealed_goal_journal` | `W9` | `personal_goals.csv`, `goal_tracks.csv` | Codex/UI | `in_house_ui` | Sealed journal entries for known goals and final hooks | future Godot screen | goal label | Hidden `goal_flags` stay redacted |
| `mobile_act_unlock_panel` | `W11` | `act_unlock_codes.csv`, local act state | Codex/UI | `in_house_ui` | Compact master-code panel for future act unlock, no hidden content art | future Godot screen | act unlock | Invalid/rejected unlock keeps future content redacted |
| `sorceress_mobile_skin_v0` | `W1-W11` for sorceress V0 | player snapshot role_type/display_name/accent | Codex/UI | `in_house_ui` | Same field journal layout with sorceress portrait, silver/violet accent and no magic controls | future Godot theme | Sorceress skin | Sorceress is visually distinct without requiring `Sorc1-Sorc7` |

## Sorceress future-layer assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sorceress_arcane_dossier_shell` | future `Sorc1-Sorc7` | sorceress state | Codex/UI | `in_house_ui` | Silver/violet dossier, restrained accents | future Godot theme | Sorceress dossier | Future layer only after shared mobile V0 acceptance |
| `sorceress_spell_cards` | `Sorc2` | `spells.csv` | Codex/UI | `in_house_ui` | Spell cards with mana, target, role, counterplay, visibility | future Godot screen | spell label | Invalid target, insufficient mana and review visible |
| `sorceress_potion_cards` | `Sorc3-Sorc4` | `potions.csv`, `potion_markets.csv`, trade state | Art generation/Codex | `original_generated` | Apothecary bottle/cards by rarity, original art | future `assets/mobile/potions/` | potion label | Wholesale/resale/transfer lock visible |
| `sorceress_pact_cards` | `Sorc5` | `favorites.csv`, favorite rules | Codex/UI | `in_house_ui` | Pact cards for primary/secondary favorite consent | future Godot screen | pact label | Pending, accepted, cap exceeded states visible |
| `sorceress_evidence_dossier` | `Sorc6-Sorc7` | alignment evidence, locked magical intent | Codex/UI | `in_house_ui` | Evidence records with visibility, final flag and review states | future Godot screen | evidence label | Master-readable trail preserved |

## Personal Gwent assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `personal_gwent_mobile_table` | `W10 Personal Gwent` | PvP/Gwent match read model | Codex/UI | `in_house_ui` | Witcher 3 Gwent-like table grammar adapted to portrait, original chrome | future Godot screen | Gwent table | Turn focus, score, rows, weather, hand and pass visible |
| `personal_gwent_card_faces` | `W10`, rewards | `gwent_cards.csv`, `gwent_decks.csv` | Art generation/Codex | `original_generated` | Original card portraits or symbolic card faces by faction/row/rarity | future `assets/gwent/cards/` | card id | Rarity, row, type, strength and effect visible |
| `personal_to_army_card_faces` | inventory/Gwent/lord conversion | `cards.csv`, `army_unit_cards.csv` | Art generation/Codex | `original_generated` | Original conversion card faces for army unit rewards | future `assets/gwent/conversion/` | conversion card id | Conversion rule and target unit visible |

## Admin assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `admin_ops_console_shell` | `A1-A11` | master overview and state | Codex/UI | `in_house_ui` | Dense ops console with dark fantasy accents | future Admin CSS | Admin Studio | Severity, blockers and navigation readable |
| `admin_triage_queue` | `A3`, `A4`, `A7` | review queue, reward approvals, PvP reviews | Codex/UI | `in_house_ui` | Severity triage list with selected detail pane | future Admin CSS/components | review row | P0/P1/P2/P3 visible until resolved |
| `admin_paper_recovery_forms` | `A5` | `paper_forms.csv`, `/api/events/sync` | Codex/UI | `in_house_ui` | Paper recovery forms with conflict preview, reason/operator | future Admin CSS/components | paper form label | Duplicate/conflict never silently overwrites |
| `admin_final_evidence_board` | `A8`, `A11` | NPC tools, final summary, paper recovery | Codex/UI | `in_house_ui` | Evidence board for final categories and unresolved locks | future Admin CSS/components | final evidence | Missing evidence and pending locks visible |

## Binding gap

`territory_forts.csv`, `lord_map_layout.json`, `pending_lord_moves` and
`lord_map_intel` are required before production map acceptance. Until those
catalog/read-models exist, every map/territory visual uses:

- `territories.csv` for `territory_id`, `bonus_type`, `tier`, owner and neutral
  defense profile.
- `map_nodes.csv` for `node_id`, `node_type`, playable/excluded status and
  territory binding.
- `map_edges.csv` for route cost and graph placement.
- Lord runtime garrison, active army and reserve state for capacity/transfer
  overlays.
- Prototype-only manual layout data for visual hit-zones; this must be replaced
  by the accepted `lord_map_layout` manifest before implementation smoke.
