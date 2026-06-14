# Lord home asset pack v1

Purpose: approval assets for `/lords/home` before implementing the working UI.
The shared castle background is reused from `../castle-city-v2.png`.

## Runtime assets

## Territory backgrounds

- `territories/territory-home-black-mire-v1.png`
- `territories/territory-home-dark-grove-v1.png`
- `territories/territory-home-east-pashni-v1.png`
- `territories/territory-home-east-sloboda-v1.png`
- `territories/territory-home-gray-watch-v1.png`
- `territories/territory-home-hay-posad-v1.png`
- `territories/territory-home-magic-corner-v1.png`
- `territories/territory-home-mist-lake-v1.png`
- `territories/territory-home-north-alpine-ridge-v1.png`
- `territories/territory-home-north-fort-v1.png`
- `territories/territory-home-river-gate-v1.png`
- `territories/territory-home-science-manufactory-v1.png`
- `territories/territory-home-south-garden-v1.png`
- `territories/territory-home-south-pond-v1.png`
- `territories/territory-home-southwest-krep-v1.png`
- `territories/territory-home-well-market-v1.png`
- `territories/territory-home-west-cliffs-v1.png`
- `territories/territory-home-west-ostrog-v1.png`
- `territories/territory-home-west-pashni-v1.png`

These are selected-territory home backgrounds for all 19 capturable
territories. The four residences/castles intentionally reuse the shared
`../castle-city-v2.png` background. The UI grammar stays the same for every
territory.

## Core UI assets

- `minimap-v1.png` - bottom-left thematic minimap. It is not a 1:1 copy of the
  full strategic map.
- `actions/action-*.png` - circular action medallions used by
  `src/routes/LordHomeRoute.tsx` and `src/routes/LordMapRoute.tsx`.
- `actions/action-castle-v1.png` - main castle navigation medallion cropped
  from `actions/action-icons-sheet-v1.png`.
- `ui/lord-home-hud-overlay-v6.png` - accepted home HUD overlay.
- `ui/mp-widget-frame-transparent-v5.png` plus
  `ui/mp-widget-fill-field-1-v5.png` ... `ui/mp-widget-fill-field-8-v5.png` -
  runtime MP widget layers used by `src/LordMpHud.tsx`.
- `ui/recruit-modal-frame-v2.png` and `ui/recruit-modal-orbit-only-v1.png` -
  recruit modal frame and CSS orbit layer.

## Reference assets kept intentionally

- `actions/action-icons-sheet-v1.png` - approval sheet for circular action
  medallions. It is not imported by runtime code.

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
- Old MP widget drafts, raw building generations, mobile prototype assets and
  provider response JSON are local/ignored artifacts and are intentionally not
  part of the production lord runtime.
