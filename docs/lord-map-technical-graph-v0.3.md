# Lord map technical graph v0.3

Актуальная техническая карта лордского movement-графа после sparse-балансировки.
Этот документ является текущим topology contract для `data/seed/map_edges.csv`,
`backend/witcher_larp/web/lord/assets/lord_map_layout.json` и будущей
перегенерации PNG-карты.

## Дизайн-цели

- У одной локации максимум 3 связи; текущий осознанный компромисс - `node_fort_east`
  имеет 4 связи, потому что стал северным gateway к `node_well_city` после удаления
  дороги через замок.
- У каждой резиденции лорда 2 стартовых выхода.
- Сильные территории не лежат на первом клике без промежуточного захвата.
- Слабые tier-1 территории работают как ворота к tier-2/tier-3 территориям.
- Граф должен провоцировать столкновения лордов за узкие места, а не давать
  каждому игроку отдельную безопасную ветку.
- Любой лорд должен иметь маршрут до любой не-резиденции без прохода через
  основные резиденции других лордов. Резиденции являются стартами и raid-целями,
  а не обязательными транзитными мостами.
- Текущий PNG больше не является источником правды. Следующий art pass должен
  рисоваться под этот граф.

## Визуализация

Текущий final no-castle-cut overlay:

```text
reports/map-debug-crops/lord-map-sparse-graph-v0.3-planar-no-castle-cut-overlay.png
```

На нем зеленые линии - canonical edges v0.3 no-castle-cut, синие линии - стартовые
выходы из резиденций, подпись на ребре - MP cost.
Геометрический аудит layout-полилиний: `0` пересечений, `0` нерезидентских дорог
пересекают прямоугольник центрального замка.

## Player-facing asset pipeline v6

Текущий gameplay/layout-канон не меняется: `lord_map_layout.json` остается
`version: 8`, `mode: sparse_graph_v0_3_planar_no_castle_cut`, а source of truth
для связей остается `data/seed/map_edges.csv`.

Для новой player-facing карты принят более жесткий pipeline:

- OpenRouter/AI генерирует только roadless fantasy-base: центральный замок,
  4 стартовые резиденции и 19 визуальных территорий без дорог, тропинок,
  пунктиров, shortcut-линий и технических подписей.
- `scripts/build_lord_map_strict_v4_baked_roads.py` запекает видимые дороги
  поверх roadless-base строго из `map_edges.csv` и `STRICT_V4_EDGE_DISPLAY_PATHS`.
- Дороги являются частью итогового PNG/WebP, а не runtime/debug overlay.
- Четыре стартовые резиденции внутри центрального замка ставятся симметричным
  castle-square: верх-лево, верх-право, низ-лево, низ-право. Резидентские
  стартовые ребра рисуются от самих кругов; клиппинг центрального замка
  применяется только к нерезидентским транзитным дорогам.
- Сравнительный dotted-вариант допустим только как отдельный review asset,
  не как player-facing runtime-карта.
- Аудит обязан проходить перед использованием ассета: 26 ожидаемых ребер,
  26 нарисованных ребер, `0` missing/extra edges, `0` пересечений,
  `0` видимых нерезидентских дорожных сегментов внутри прямоугольника
  центрального замка.

Текущий v6-pass сохраняет v5 castle-square для стартовых резиденций и правит
две визуальные игровые точки: `node_mountain_gray` опущен ниже к дороге от
`node_village_barn`, а `node_fort_west` перенесен выше-правее к северным
пашням. Дорога `node_village_barn -> node_mountain_gray` должна читаться
непрерывной от круга до круга.

Текущие v6-артефакты:

```text
backend/witcher_larp/web/lord/assets/lord_map_ai_strict_v6_roadless_base.webp
backend/witcher_larp/web/lord/assets/lord_map_ai_strict_v6_baked_roads.webp
backend/witcher_larp/web/lord/assets/lord_map_ai_strict_v6_baked_roads_dotted.webp
backend/witcher_larp/web/lord/assets/lord_map_ai_strict_v6_territory_sockets_owner_preview.webp
backend/witcher_larp/web/lord/assets/lord_map_ai_strict_v6_manifest.json
reports/map-debug-crops/lord_map_ai_strict_v6-road-debug.webp
reports/map-debug-crops/lord_map_ai_strict_v6-road-audit.json
```

v4/v5-артефакты сохранены как предыдущие comparison passes.

## Visual layout pass

После проверки sparse-графа два узла были перенесены из старых PNG-дырок в
места, где граф читается как будущая карта:

- `node_mountain_gray` / Серый дозор: `30.10%, 53.36%` -> `62.00%, 55.78%`.
  Теперь он лежит между Холмом, Сенным посадом и Колодезным торгом, а не тянет
  диагонали через половину карты.
- `node_village_east_shed` / Восточная слобода: `57.45%, 39.72%` -> `74.61%, 45.36%`.
  Теперь она вынесена на восточную дорогу и работает как понятный узел между
  Холмом, Колодезным торгом и Зеркальным прудом.

Эти координаты являются текущей опорой для следующей генерации PNG-карты.

## Стартовые ветки лордов

| Лорд / домен | Старт | Первый слабый выход | Второй выход | Ближайшие конфликты |
| --- | --- | --- | --- | --- |
| Север / `domain_north` | `node_res_north` | `node_field_oats` за 1 MP | `node_fort_east` за 2 MP | спор за `node_well_city`, западный проход к `node_fort_west` через овсы |
| Река / `domain_river` | `node_res_river` | `node_well_city` за 1 MP | `node_village_east_shed` за 1 MP | спор за `node_well_city`, `node_lake_mist` |
| Лес / `domain_forest` | `node_res_forest` | `node_village_barn` за 1 MP | `node_fort_southwest` за 1 MP | спор с Холмом за `node_mountain_gray`, западный проход к `node_swamp_black` |
| Холм / `domain_hill` | `node_res_hill` | `node_field_east_large` за 1 MP | `node_mountain_gray` за 2 MP | спор с Рекой за восточную цепочку, с Лесом за центр |

## Сильные территории за воротами

| Сильная территория | Почему сильная | Как теперь открывается |
| --- | --- | --- |
| `node_mountain_north_alpine` Северный кряж | tier-3 defense | через `node_fort_east` |
| `node_mountain_west_alpine` Волчий утес | tier-2 defense endpoint | через `node_fort_southwest`; на старте лес должен сначала взять Южную крепь |
| `node_science_barn` Двухъярусная мануфактура | research tier-2 | через `node_spanish_magic` или `node_field_east_large` |
| `node_forest_south_garden` Нижний сад | artifact tier-2 | через `node_science_barn` |
| `node_lake_south_pond` Лунная заводь | magic endpoint | через `node_forest_south_garden` |
| `node_well_city` Колодезный торг | resource tier-2 | через север/реку/центр, но не как стартовый freebie |
| `node_swamp_black` Черная топь | raid-cover tier-2 | через Травничью рощу или Южную крепь |

## Canonical edge list

| Edge id | From | To | MP |
| --- | --- | --- | --- |
| `edge_north_field` | `node_res_north` | `node_field_oats` | 1 |
| `edge_north_fort_east` | `node_res_north` | `node_fort_east` | 2 |
| `edge_fort_east_mountain_north` | `node_fort_east` | `node_mountain_north_alpine` | 2 |
| `edge_fort_west_field_north` | `node_fort_west` | `node_field_oats` | 1 |
| `edge_fort_west_field_west` | `node_fort_west` | `node_field_west_large` | 1 |
| `edge_fort_west_fort_east` | `node_fort_west` | `node_fort_east` | 2 |
| `edge_field_west_forest_dark` | `node_field_west_large` | `node_forest_dark` | 2 |
| `edge_swamp_forest_west` | `node_swamp_black` | `node_forest_dark` | 2 |
| `edge_swamp_fort_southwest` | `node_swamp_black` | `node_fort_southwest` | 2 |
| `edge_forest_fort_southwest` | `node_res_forest` | `node_fort_southwest` | 1 |
| `edge_fort_southwest_mountain_west` | `node_fort_southwest` | `node_mountain_west_alpine` | 2 |
| `edge_forest_village` | `node_res_forest` | `node_village_barn` | 1 |
| `edge_village_magic` | `node_village_barn` | `node_spanish_magic` | 2 |
| `edge_village_mountain_gray` | `node_village_barn` | `node_mountain_gray` | 2 |
| `edge_magic_science` | `node_spanish_magic` | `node_science_barn` | 2 |
| `edge_science_forest_south` | `node_science_barn` | `node_forest_south_garden` | 2 |
| `edge_forest_south_lake_south` | `node_forest_south_garden` | `node_lake_south_pond` | 1 |
| `edge_field_east_science` | `node_field_east_large` | `node_science_barn` | 2 |
| `edge_hill_field_east` | `node_res_hill` | `node_field_east_large` | 1 |
| `edge_hill_mountain` | `node_res_hill` | `node_mountain_gray` | 2 |
| `edge_village_east_well` | `node_village_east_shed` | `node_well_city` | 1 |
| `edge_village_east_lake` | `node_village_east_shed` | `node_lake_mist` | 1 |
| `edge_lake_field_east` | `node_lake_mist` | `node_field_east_large` | 1 |
| `edge_river_well` | `node_res_river` | `node_well_city` | 1 |
| `edge_river_village_east` | `node_res_river` | `node_village_east_shed` | 1 |
| `edge_fort_east_well` | `node_fort_east` | `node_well_city` | 2 |

## Degree audit

| Узел | Degree | Соседи |
| --- | --- | --- |
| Северная резиденция | 2 | Северные овсы, Северная застава |
| Речная резиденция | 2 | Колодезный торг, Восточная слобода |
| Лесная резиденция | 2 | Сенной посад, Южная крепь |
| Холмовая резиденция | 2 | Правые пашни, Серый дозор |
| Северные овсы | 2 | Северная резиденция, Западный острог |
| Северная застава | 4 | Северная резиденция, Западный острог, Северный кряж, Колодезный торг |
| Северный кряж | 1 | Северная застава |
| Западный острог | 3 | Северные овсы, Северная застава, Левобережные пашни |
| Левобережные пашни | 2 | Западный острог, Травничья роща |
| Черная топь | 2 | Травничья роща, Южная крепь |
| Травничья роща | 2 | Левобережные пашни, Черная топь |
| Южная крепь | 3 | Лесная резиденция, Черная топь, Волчий утес |
| Волчий утес | 1 | Южная крепь |
| Сенной посад | 3 | Лесная резиденция, Чародейский угол, Серый дозор |
| Чародейский угол | 2 | Сенной посад, Двухъярусная мануфактура |
| Двухъярусная мануфактура | 3 | Чародейский угол, Правые пашни, Нижний сад |
| Нижний сад | 2 | Двухъярусная мануфактура, Лунная заводь |
| Лунная заводь | 1 | Нижний сад |
| Серый дозор | 2 | Холмовая резиденция, Сенной посад |
| Колодезный торг | 3 | Северная застава, Восточная слобода, Речная резиденция |
| Восточная слобода | 3 | Речная резиденция, Колодезный торг, Зеркальный пруд |
| Зеркальный пруд | 2 | Восточная слобода, Правые пашни |
| Правые пашни | 3 | Холмовая резиденция, Зеркальный пруд, Двухъярусная мануфактура |

## Residence bypass audit

Для каждого стартового лорда граф проверяется так: все остальные резиденции
исключаются из транзита, после чего каждая не-резиденция должна оставаться
достижимой. В v0.3 reachable этот аудит проходит для всех четырех стартов.

Ключевая правка после первого sparse-pass: `node_fort_east` и
`node_mountain_north_alpine` больше не являются приватной северной веткой.
Они доступны через обычную территорию `node_fort_west`, поэтому река, лес и
холм могут дойти до СевЗ/СевК, не проходя через `node_res_north`.

Ключевая правка no-castle-cut pass: дорога `node_field_oats -> node_well_city`
удалена, потому что визуально проходила прямо через центральный замок. Вместо
нее северо-восточный gateway идет через `node_fort_east -> node_well_city`.

- Река стартует в `node_well_city` и `node_village_east_shed`.
- Холм стартует в `node_field_east_large` и `node_mountain_gray`.
- `node_res_hill -> node_village_east_shed`, `node_res_river -> node_lake_mist`
  и `node_mountain_gray -> node_field_east_large` не используются в текущем
  technical layout, чтобы восточный блок оставался планарным.

После удаления остальных резиденций из транзита все не-резиденции остаются
достижимыми из каждого из четырех стартов.

## Удаленные shortcuts

Эти ребра удалены, потому что давали слишком много свободы и ломали прогрессию:

- `node_res_forest -> node_forest_dark`
- `node_res_forest -> node_swamp_black`
- `node_res_hill -> node_fort_west`
- `node_fort_west -> node_science_barn`
- `node_field_oats -> node_spanish_magic`
- `node_lake_mist -> node_swamp_black`
- `node_forest_dark -> node_mountain_west_alpine`
- `node_mountain_west_alpine -> node_village_barn`
- `node_village_barn -> node_fort_southwest`
- `node_field_east_large -> node_forest_south_garden`
- `node_fort_west -> node_swamp_black`
- `node_well_city -> node_mountain_gray`
- `node_field_oats -> node_well_city`
- `node_res_hill -> node_village_east_shed`
- `node_res_river -> node_lake_mist`
- `node_mountain_gray -> node_field_east_large`

## Movement rule dependency

Этот sparse graph сам по себе убирает лишние связи, но стратегическая прогрессия
полностью работает только вместе с правилом:

- свои территории можно использовать как транзит;
- нейтральная/чужая territory останавливает поход и не может быть промежуточным
  узлом;
- чужие резиденции не являются обычными movement targets.

Например, лесной лорд видит `node_fort_southwest` и `node_village_barn` как первые
цели. `node_mountain_west_alpine` стоит всего на 2 MP дальше Южной крепи, но на
старте недоступен как цель, потому что `node_fort_southwest` еще нейтральная и
не может быть транзитом.
