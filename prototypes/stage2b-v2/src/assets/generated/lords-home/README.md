# Lord home asset pack v1

Purpose: approval assets for `/lords/home` before implementing the working UI.
The shared castle background is reused from `../castle-city-v2.png`.

## Preview

- `lord-home-asset-board-v1.png` - approval board with all new assets.

## Territory backgrounds

- `territories/territory-home-north-fort-v1.png`
- `territories/territory-home-river-gate-v1.png`
- `territories/territory-home-mist-lake-v1.png`

These are alternate selected-territory home backgrounds. The UI grammar stays
the same for every territory.

## Core UI assets

- `minimap-v1.png` - bottom-left thematic minimap. It is not a 1:1 copy of the
  full strategic map.
- `actions/action-icons-sheet-v1.png` - approval sheet for circular action
  medallions: buildings, map, orders, raids, battle alert, tutorial, logout,
  territory.
- `ui/lord-home-chrome-overlay-v1.svg` - 1280x720 layout chrome guide:
  top resources, left action dock, bottom-left minimap frame, bottom-center
  army/garrison/recruit lanes, bottom-right act/MP, right territory bubbles.
- `ui/mp-widget-base-empty-v4.png` - generated bottom-right MP/act widget
  source asset with eight empty divisions.
- `ui/mp-widget-empty-slots-v4.png` + `ui/mp-widget-frame-cutout-v4.png` -
  runtime split of the generated asset: dark empty panes below and the metal
  frame above.
- `ui/mp-widget-fill-segment-1-v4.png` ... `ui/mp-widget-fill-segment-8-v4.png`
  - full-size transparent blue MP segment layers aligned to the generated
  asset.
- `ui/mp-widget-segment-polygons-v4.json` - editable 700x560 polygon
  coordinates used for the Figma handoff and runtime fill layers.
- `ui/recruit-modal-frame-v1.svg` - recruit modal frame for unit art, stats,
  slider/cost and hire action.

## Unit icons

- `units/unit-infantry-v1.png`
- `units/unit-guard-v1.png`
- `units/unit-ranged-v1.png`
- `units/unit-cavalry-v1.png`
- `units/unit-heavy-siege-v1.png`
- `units/unit-specialist-v1.png`

## Layout locks

- Minimap is bottom-left.
- Act plaque and MP arc are bottom-right.
- Unit purchase target is the selected territory garrison.
- Raster assets contain no runtime text labels; text belongs to the UI layer.
