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
| `figma_stage2b_visual_acceptance` | all Stage 2B surfaces | `Shared1-Shared3`, `L1-L10`, `W1-W10`, `Sorc1-Sorc7`, `A1-A11` | Figma/Codex after user approval | `in_house_ui` | Editable design frames for implementation handoff; no official Witcher/Gwent/Heroes art | `https://www.figma.com/design/7BNdyJtd7QSH52QzXjT0Ol` | Stage 2B visual acceptance | Primary composition, density, hierarchy and art-direction source |
| `proto_venue_map_v1_svg` | `L2 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv` | Codex/local SVG | `in_house_ui` | Painted-map fallback for repo-local prototype | `prototypes/stage2b/assets/venue-map-v1.svg` | `venue_map_v1` | Keeps topology, owner, contested and route-cost labels visible |
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
| `ui_shared_dark_shell` | Shared auth/sync | `Shared1-Shared3` | Codex/UI | `in_house_ui` | Dark tactile fantasy, role-neutral login and sync shell | `prototypes/stage2b/style.css` | Shared auth/sync | Server unreachable, wrong token and sync states visible |
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
| `lord_map_venue_v1_painted` | `L2 Illustrated Map` | `map_nodes.csv`, `map_edges.csv`, `territories.csv` | Art generation/Codex | `original_generated` | Painted fantasy strategy map over seed topology, no QR anchors | future `assets/lord/venue_map_v1.png` | `venue_map_v1` | Route costs, owner, contested and excluded zones remain legible |
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
| `territory_fort_east_card` | `L4 Territory Fort` | `territory_fort_east`, `node_fort_east` | Art generation/Codex | `original_generated` | East Fort, frontier watch fort, original art | future `assets/territories/territory_fort_east.png` | East Fort | Contested and transfer states visible |
| `territory_fort_west_card` | `L4 Territory Fort` | `territory_fort_west`, `node_fort_west` | Art generation/Codex | `original_generated` | West Fort, western stone fort, original art | future `assets/territories/territory_fort_west.png` | West Fort | Contested and transfer states visible |
| `territory_field_oats_card` | `L4 Territory Fort` | `territory_field_oats`, `node_field_oats` | Art generation/Codex | `original_generated` | Oat fields strategic supply card, original art | future `assets/territories/territory_field_oats.png` | Oat Fields | Bonus type and route hints visible |
| `territory_village_barn_card` | `L4 Territory Fort` | `territory_village_barn`, `node_village_barn` | Art generation/Codex | `original_generated` | Barn village recruit card, original art | future `assets/territories/territory_village_barn.png` | Barn Village | Recruit bonus visible |
| `territory_well_city_card` | `L4 Territory Fort` | `territory_well_city`, `node_well_city` | Art generation/Codex | `original_generated` | Well resource city card, original art | future `assets/territories/territory_well_city.png` | Well City | Resource bonus visible |
| `territory_magic_corner_card` | `L4 Territory Fort` | `territory_magic_corner`, `node_spanish_magic` | Art generation/Codex | `original_generated` | Magical corner card with ritual stonework, original art | future `assets/territories/territory_magic_corner.png` | Magic Corner | Magic bonus visible |
| `territory_science_barn_card` | `L4 Territory Fort` | `territory_science_barn`, `node_science_barn` | Art generation/Codex | `original_generated` | Science barn research card, original art | future `assets/territories/territory_science_barn.png` | Science Barn | Research bonus visible |
| `territory_forest_dark_card` | `L4 Territory Fort` | `territory_forest_dark`, `node_forest_dark` | Art generation/Codex | `original_generated` | Dark forest strategic card, original art | future `assets/territories/territory_forest_dark.png` | Dark Forest | Tier and neutral defense readable |
| `territory_lake_mist_card` | `L4 Territory Fort` | `territory_lake_mist`, `node_lake_mist` | Art generation/Codex | `original_generated` | Mist lake alchemy card, original art | future `assets/territories/territory_lake_mist.png` | Mist Lake | Alchemy bonus visible |
| `territory_swamp_black_card` | `L4 Territory Fort` | `territory_swamp_black`, `node_swamp_black` | Art generation/Codex | `original_generated` | Black swamp raid-cover card, original art | future `assets/territories/territory_swamp_black.png` | Black Swamp | Raid-cover state visible |
| `territory_mountain_gray_card` | `L4 Territory Fort` | `territory_mountain_gray`, `node_mountain_gray` | Art generation/Codex | `original_generated` | Gray mountain rare metal card, original art | future `assets/territories/territory_mountain_gray.png` | Gray Mountain | Rare metal bonus visible |
| `lord_unit_tile_set` | `L1`, `L5`, `L7`, `L10` | `army_unit_cards.csv`, recruit stock | Codex/UI + Art generation/Codex | `in_house_ui` / `original_generated` | Unit tiles/cards for infantry, guard, ranged, cavalry, heavy siege, specialist, including lane icons and recruit modal art | future UI CSS/components + `assets/lord/units/*.png` | unit class + stats | Class, tier, ATK/DEF/HP/init/count/rate/stock readable |
| `lord_war_table_board` | `L10 Lord Battle` | lord battle board width 5 height 6 | Codex/UI | `in_house_ui` | Tactical war table, visually distinct from personal Gwent | future UI CSS/components | 5x6 board | Legal move, target, active, timer and auto-resolve visible |
| `lord_command_slip_set` | `L8`, `L9` | raid rules, orders, escrow state | Codex/UI | `in_house_ui` | Paper command slips with status badges | future UI CSS/components | raid/order label | Caps, locks, object conflicts and review visible |

## Witcher mobile assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `witcher_field_journal_shell` | `W1-W9` | player snapshot, event queue | Codex/UI | `in_house_ui` | Dark field journal with character sheet first | future Godot theme | Witcher journal | Character, stats, sync strip and actions readable |
| `witcher_qr_oath_panel` | `W2-W3` | `qr_objects.csv`, local QR context | Codex/UI | `in_house_ui` | Clear physical-presence oath, not dramatic ritual | future Godot screen | physical presence | Future act, cooldown and review states visible |
| `witcher_pve_scene_card` | `W4-W5` | `pve_scenarios.csv`, `mobs.csv`, `rewards.csv` | Codex/UI | `in_house_ui` | Scene card with app d20 log, DC, stat, scene HP, reward lock | future Godot screen | PvE result | One-roll-only and reward/cooldown state visible |
| `witcher_inventory_card_set` | `W6` | items, cards, artifacts, potions | Codex/UI | `in_house_ui` | Categorized cards with rarity and lock badges | future Godot screen | asset label | locked/pending/trade states visible |
| `witcher_contract_slips` | `W7-W8` | orders and trade transfers | Codex/UI | `in_house_ui` | Contract slips for orders/trade with escrow and review | future Godot screen | order/trade label | Pending lock and object conflict visible |
| `witcher_sealed_goal_journal` | `W9` | `personal_goals.csv`, `goal_tracks.csv` | Codex/UI | `in_house_ui` | Sealed journal entries for known goals and final hooks | future Godot screen | goal label | Hidden `goal_flags` stay redacted |

## Sorceress mobile assets

| Asset id | Surface | Runtime binding | Source/owner | License status | Prompt/reference note | Target path | Fallback label | Acceptance note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sorceress_arcane_dossier_shell` | `Sorc1-Sorc7` | sorceress state | Codex/UI | `in_house_ui` | Silver/violet dossier, restrained accents | future Godot theme | Sorceress dossier | Mana, spells, potions, favorites and final lock readable |
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

`territory_forts.csv` is mentioned by the task contract but is not present in
the current seed. Until that catalog exists, every territory/fort visual uses:

- `territories.csv` for `territory_id`, `bonus_type`, `tier`, owner and neutral
  defense profile.
- `map_nodes.csv` for `node_id`, `node_type`, playable/excluded status and
  territory binding.
- `map_edges.csv` for route cost and graph placement.
- Lord runtime garrison, active army and reserve state for capacity/transfer
  overlays.
