# Generated assets v2

Project-bound original generated raster assets for the Stage 2B visual
prototype. These images are IP-safe originals: they use reference grammar only
and do not include copied official Witcher, Gwent, Heroes, Olden Era screenshots,
logos, emblems or card art.

Generated with the built-in `image_gen` path and copied from Codex generated
image storage into this workspace.

## Current runtime asset groups

| File | Purpose | Notes |
| --- | --- | --- |
| `lords-login/` | Lord login screen | Runtime set is declared in `lords-login/manifest.json`. |
| `lords-home/` | Lord home, orders, raids, buildings and shared MP HUD | Runtime/reference split is declared in `lords-home/README.md`. |
| `lords-map/lord-map-ai-strict-v6-roadless-base.webp` | Lord strategic map base | Runtime map art for `/lords/map`. |
| `lords-map/lord-map-ai-strict-v6-baked-roads.webp` | Lord strategic map roads | Runtime road layer for `/lords/map`. |
| `lords-battle/` | Lord battle screen | Runtime table/board art for `/lords/battle`. |
| `lord-map-v2.png` | Lord home map panel | Runtime art used inside `/lords/home` map panel. |
| `castle-city-v2.png` | Castle/city management background | Runtime castle home background. |
| `building-tree-bg-v6-holes.png` | Castle upgrade tree background | Runtime building tree backdrop. |

## Reference assets kept intentionally

| File | Purpose | Notes |
| --- | --- | --- |
| `gwent-table-v2.png` | Personal Gwent-like board background | Kept for pending personal PvP/Gwent UI work; not imported by current lord runtime. |
| `building-tree-bg-v2.png` | Source background for building tree hole variants | Kept as regeneration source for `scripts/build-building-tree-bg-holes.mjs`; runtime imports `building-tree-bg-v6-holes.png`. |

Old map owner previews, map cutouts, login button/input explorations, raw image
outputs and provider response JSON were removed from git. Future raw/generated
responses are ignored; accepted runtime assets should be copied into the
runtime groups above and documented here.

## Prompts

### lord-map-v2

Create a high-resolution original fantasy strategy territory map background for
a tabletop LARP command UI. 16:9 landscape composition, painted game-map look,
top-down/isometric hybrid. Include distinct territories with mountains, river,
lake, dense forest, fields, swamp, ruined neutral fort, small villages, one
central stone city, several small forts, winding roads and route choke points.
Leave clean open areas where UI node markers and labels can be overlaid later;
no baked text, no logos, no official game symbols, no copyrighted characters.
Rich but readable detail, dark tactical fantasy mood, muted greens, slate
mountains, amber torch accents, parchment-map edge fog, crisp landmarks,
professional game UI asset quality.

### castle-city-v2

Create a high-resolution original fantasy castle and city management background
for a strategy UI. Wide 16:9 painted scene, bright readable fantasy settlement
similar in function to a castle development screen but fully original.
Foreground medieval town with workshops, market roofs, stables, barracks, mage
tower, chapel, walls and roads; right side a tall sunlit castle keep; distant
hills, river, clouds, warm late-afternoon light. Leave several clean visual
zones for UI overlays and building markers; no baked text, no logos, no
official game symbols, no copyrighted characters. Professional game concept art
quality, crisp architecture, rich but not cluttered, warm stone, blue roofs,
brass highlights, readable silhouettes for upgrade nodes.

### gwent-table-v2

Create a high-resolution original dark wooden fantasy card game table background
for a Gwent-like UI, but fully original and IP-safe. 16:9 landscape game board,
polished dark walnut surface with carved horizontal lanes: three rows for
opponent at top and three rows for player at bottom, subtle empty card slots,
left sidebar area for leader portraits and score medallions, right side deck
and graveyard stack zones, center weather/special slot column. No cards, no
characters, no text, no official icons, no logos. Brass trim, worn leather
insets, dim candlelight, tactical board readability, strong empty zones for live
UI cards and labels, professional dark fantasy game interface asset.

### building-tree-bg-v2

Create a high-resolution original fantasy castle building-tree UI background,
16:9 landscape. A cool blue-green arcane parchment and stone interface backdrop
with faint castle silhouette, subtle stars/dust, soft grid columns for upgrade
nodes, delicate glowing prerequisite line paths, empty rounded node sockets, and
a right-side detail-card zone. Also include two subtle bottom lanes for army and
garrison slots, like hex/square recessed slots, but no text and no official
symbols. Professional strategy game upgrade screen quality, readable dark
fantasy UI surface, aged brass trim, cold moonlit blue shadows, designed for
live React/Figma UI overlays.
