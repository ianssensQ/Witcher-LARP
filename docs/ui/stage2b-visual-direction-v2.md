# Stage 2B visual direction v2

Этот документ фиксирует новый художественный и UX-контракт для Stage 2B
визуального прототипа. Он заменяет неудачную визуальную попытку как направление,
но не удаляет старые файлы и не меняет TaskOS-статусы.

Цель: получить профессиональные Figma-экраны и React/Tailwind-прототип,
максимально близкие по композиции, плотности и ощущению к референсам:

- Figma board: много экранов, сгруппированных по потокам, как на reference
  screenshot с мобильными экранами.
- Castle/city: светлая painted fantasy city/castle scene with readable UI zones.
- Strategy map: illustrated fantasy map with territories, roads, landmarks,
  fog/unknown areas and controlled overlay UI.
- Personal Gwent: dark wooden table, leader area, score columns, graveyard,
  deck, weather/special zones, three rows per side and hand at bottom.
- Building tree: Olden Era-like node tree, prerequisite lines, detail card,
  plus army and garrison slot lanes.

## Non-negotiables

- No copied official Witcher, Gwent, Heroes, Olden Era screenshots, logos,
  faction emblems, card art or UI chrome in production assets.
- References define grammar: composition, hierarchy, affordances, density,
  mood and screen logic.
- All map, castle, fort, card portraits, heraldry, unit cards and textures are
  original generated/local assets.
- Active UI must sit on top of generated art cleanly: strong readability,
  deliberate contrast, no text lost inside painterly backgrounds.
- The prototype must be data-shaped: screen IDs, state badges, runtime entity
  labels and interactions must map back to the existing Stage 2B screen matrix.

## Visual System

### Mood

Dark tactical fantasy interface with painted assets, brass/copper framing,
aged parchment panels, dark wood game-table surfaces, cold silver/violet magic
accents and muted military map colors.

The UI should feel like an in-world command tool, not a generic SaaS dashboard
and not a decorative landing page.

### Palette

- Background: near-black umber, dark walnut, charcoal leather.
- Structural lines: aged brass, dull gold, oxidized copper.
- Text: parchment white, warm grey, muted ink.
- Lord accents: heraldic red, deep green, river blue, old gold.
- Witcher accents: steel blue, monster-blood red, muted amber.
- Sorceress accents: silver, violet, moonlit blue.
- Admin accents: amber severity, red blockers, cold blue system state.

### Typography

- UI text: compact, readable sans-serif for Russian labels.
- Display labels: restrained fantasy serif or small caps only for titles,
  card names and castle/building labels.
- No giant hero typography inside tool surfaces.
- Screen density must stay game-operator friendly: desktop panels are dense,
  mobile panels are stacked and readable.

### Surfaces

- Panels: 4-8px radius, brass/copper 1px lines, subtle inner shadows.
- Cards: physical object feel: bevel, paper/wood texture, small icon slots.
- Buttons: compact command controls with icons where useful.
- Badges: state-first, color-coded but not neon.
- Maps/painted backgrounds: art layer is primary, UI overlays are anchored,
  readable and sparse.

## Screen Package v2

### 01 Lord Castle / Territory Home

Desktop target: 1280x720, 1440x900 and 1600x1000.

Composition, максимально близко к предоставленному референсу:

- Full-screen painted castle/territory background is the main visual object.
  UI overlays must be sparse so the art remains visible.
- Top thin resource strip: resources centered; gold shows `current (+income/hour)`;
  small `?` onboarding replay and door/logout controls sit at the top right.
- Left vertical dock: circular icon buttons without permanent labels. Hover/focus
  glows and reveals the action name: buildings, map, notice board, raids, battle.
- Right vertical territory bubbles: owned territories appear as circular art
  buttons; clicking one switches to the same UI for that territory.
- Bottom-left: thematic minimap, placed exactly on the lower-left side as in the
  reference, not next to the act panel.
- Bottom-center: two horizontal lanes. Top lane is active army/hero army; it is
  empty and locked when the hero-army is not in the selected territory. Bottom
  lane is the selected location garrison.
- Bottom-center/right inside the same frame: recruit slots for this location.
  Each visible unit slot shows `+X/hour` and `(stock)`. Locked empty slots stay
  visible until buildings unlock the unit.
- Bottom-right: compact act number and time-to-next-act plaque. Above it sits
  a semicircle MP gauge for movement points in the current tick.
- Unit click opens a recruit modal with unit art, one-unit stats, cost slider
  and `Нанять`; purchased units go into the selected territory garrison.
- Building screen uses Olden Era-like node/tree grammar. Residence has the full
  tree; territories use the same interaction pattern with a smaller local tree.
- Map mode remains a separate illustrated `venue_map_v1` screen for route
  selection and hero movement, not the default lord home.
- Battle mode remains a separate 5x6 tactical board, visually distinct from
  personal Gwent, with HP, initiative, unit cards, turn timer and auto-resolve.

Required states:

- castle selected / owned territory selected;
- hero-army present / hero-army elsewhere with top lane locked;
- recruit slot available / locked / insufficient stock / insufficient gold;
- owned / neutral / enemy / contested territory;
- no movement points on MP arc and map route;
- invalid route;
- hidden enemy garrison;
- building locked / purchasable / purchased;
- insufficient gold / missing prerequisite;
- battle timer / timeout / master takeover.

### 02 Personal Gwent

Mobile and tablet-first target: 390x844, 430x932, plus desktop preview.

Composition:

- Wooden board background with two player sidebars.
- Leader portrait + faction crest + current score.
- Three rows per side: melee, ranged, siege.
- Weather/special slot column.
- Deck and graveyard stacks.
- Hand at bottom with readable card cards.
- Pass/play controls, round state and stake lock.

Required states:

- queued challenge;
- active table;
- player turn;
- opponent turn;
- passed;
- weather active;
- locked stake;
- refusal/review.

### 03 Mobile Witcher Field Journal

Phone target: 390x844 and 430x932.

Composition:

- Character sheet first: portrait, school/role mark, HP/resources, reputation
  label, current act and sync strip.
- Bottom tab/navigation: journal, QR, inventory, contracts, Gwent.
- QR/manual flow: scanner/manual code, physical-presence oath, PvE scene,
  immutable d20 result, reward/cooldown/sync status.
- Inventory/contracts as object-like cards, not generic lists.

Required states:

- offline snapshot;
- future act locked;
- manual code invalid/rate limited;
- cooldown;
- locked reward;
- pending sync / sync error / needs master review.

### 04 Mobile Sorceress Arcane Dossier

Phone target: 390x844 and 430x932.

Composition:

- Arcane dossier home with portrait, mana, potions, alignment, favorites.
- Spell catalog as annotated cards with target/visibility indicators.
- Potion market with apothecary-like cards.
- Favorites/pacts as consent cards.
- Locked magical intent as final dossier section.

Required states:

- insufficient mana;
- invalid target;
- pending favorite consent;
- cap exceeded;
- pending transfer lock;
- final lock review.

### 05 Admin Ops Evidence Board

Desktop target: 1440x900 and 1600x1000.

Composition:

- Dense master console, not fantasy ornament overload.
- Left nav by operation: overview, acts, review, rewards, paper, lord ops,
  PvP, NPC, visibility, backups, final.
- Main triage table with P0/P1/P2/P3 severity.
- Paper recovery form with conflict preview.
- Final evidence board with missing locks, NPC prices, magical intent and
  export state.

Required states:

- wrong token;
- review pending;
- duplicate;
- rejected;
- missing reason;
- paper conflict;
- unresolved final locks.

### 06 Figma Board Structure

The new Figma file should contain pages or large named sections:

- `00 Direction / References`
- `01 Foundations / Tokens`
- `02 Components / Game UI Kit`
- `03 Lord Castle / Territory Home`
- `04 Personal Gwent`
- `05 Witcher Mobile`
- `06 Sorceress Mobile`
- `07 Admin Ops`
- `08 Asset Board / Generated Originals`
- `09 Handoff / Implementation Notes`

Frames should be arranged like a production design board:

- overview row;
- flow rows;
- state variants near the base screen;
- comments/labels for endpoint or snapshot binding;
- asset callouts next to screens;
- no isolated single pretty mockup without neighboring states.

## React/Tailwind Prototype Strategy

Create `prototypes/stage2b-v2/` as an isolated visual prototype.

Base stack:

- Vite + React + TypeScript;
- Tailwind;
- shadcn-style component primitives;
- lucide-react icons;
- original generated assets in `prototypes/stage2b-v2/src/assets/`;
- mock data in `prototypes/stage2b-v2/src/data/`;
- screen routes/tabs for `lords`, `gwent`, `witcher`, `sorceress`, `admin`.

Prototype purpose:

- produce pixel-checked screenshots;
- feed `generate_figma_design` as reference;
- keep layout, states and labels deterministic;
- provide an implementation-safe handoff after Figma approval.

## Generated Asset List

Priority 1:

- `lord-castle-home-v1`: main shared lord castle background, 16:9,
  high-detail painted fantasy, UI-safe empty bottom/side zones, no labels baked
  into image.
- `lord-territory-home-v1-*`: territory backgrounds for playable owned
  territories, same camera grammar as the castle home, distinct local identity,
  no labels baked into image.
- `lord-ui-chrome-v1`: top resource strip, left circular action sockets,
  bottom army/garrison/recruit frame, bottom-left minimap frame, bottom-right
  act plaque and semicircle MP gauge.
- `lord-unit-icons-v1`: unit icons/cards for infantry, guard, ranged, cavalry,
  heavy siege and specialist, plus locked empty recruit slot art.
- `lord-map-v2`: separate illustrated fantasy territory map, 16:9, high detail,
  roads, mountains, rivers, forest, fort nodes, no labels baked into image.
- `gwent-table-v2`: dark wooden card table background with empty rows and
  side panels, no official UI symbols.
- `building-tree-bg-v2`: subtle blue-green arcane/castle upgrade background.

Priority 2:

- Four lord crests/heraldry.
- Territory fort/card thumbnails for forest, river, mountain, village, magic,
  fields, swamp, neutral ruins as secondary cards behind the territory home.
- Building node icons/painted cutouts for residence and local territory trees.
- Witcher and sorceress portraits.
- Gwent-like original card backs and card portrait set.

Asset rules:

- Generate at high resolution first, downscale for UI.
- Keep text out of raster assets unless explicitly needed.
- UI labels stay live HTML/Figma text.
- Save originals and optimized versions separately.

## Acceptance Criteria For Stage 2 Before Asset Generation

Proceed to asset generation only if this direction is accepted:

- Lord first screen is `/lords/home`: castle/selected-territory home matching
  the reference composition. The minimap is bottom-left; act plaque and MP arc
  are bottom-right. The map is a separate movement screen.
- Gwent screen follows the board grammar of the reference: rows, leader,
  score, deck, graveyard, weather/special and hand.
- Mobile screens feel like game artifacts, not CRUD cards.
- Admin remains dense and operational.
- All copied IP is avoided; similarity is composition/mood, not asset reuse.
