# Lord map technical audit v0.2

> Текущий принятый sparse-граф после балансировки вынесен в
> `docs/lord-map-technical-graph-v0.3.md`. Этот документ остается audit trail:
> что было не так в PNG/technical sync и какие shortcuts мы нашли.

Документ фиксирует dev-аудит текущей лордской PNG-карты против технического
графа. Цель этого шага - сначала сделать понятной и принятой техническую карту,
а уже потом перегенерировать/дорисовывать PNG так, чтобы визуальная карта и
`map_edges.csv` были одной и той же картой.

## Статус

Текущий граф нельзя считать визуально принятым.

Причина: игрок видит нарисованный пунктир на PNG, а приложение считает движение
по `data/seed/map_edges.csv` и `lord_map_layout.json`. Эти слои сейчас местами
расходятся. В layout технические ребра скрыты (`svg_edges_visible=false`), поэтому
рассинхрон не виден игроку, но проявляется в маршрутах и стоимости MP.

Сгенерированный overlay-аудит:

```text
reports/map-debug-crops/lord-map-technical-overlay-v1.png
```

На overlay:

- красные линии - текущие technical edges из `lord_map_layout.json`;
- голубые круги - технические capturable nodes;
- желтые круги - технические residence nodes.

## Аудированные источники

| Источник | Роль | Наблюдение |
| --- | --- | --- |
| `backend/witcher_larp/web/lord/assets/lord_map_playable_v1_holes.png` | текущая player-facing PNG | игрок видит именно этот пунктир и кружки |
| `backend/witcher_larp/web/lord/assets/lord_map_layout.json` | координаты, hit-zones, edge polylines | содержит 3-точечные technical polylines, но они не трассируют нарисованные дороги |
| `data/seed/map_nodes.csv` | seed node catalog | 4 residence + 19 capturable + 2 excluded |
| `data/seed/map_edges.csv` | gameplay graph source | содержит часть визуально спорных shortcut edges |
| `data/seed/territories.csv` | стартовое владение | только 4 residence owned, остальные нейтральные |
| `prototypes/stage2b-v2/src/App.tsx` | Stage 2B prototype graph duplicate | дублирует graph вручную, это риск рассинхронизации |

## Домены и стартовые узлы

| Домен | Цвет UI | Стартовый узел армии | Территория | Правило |
| --- | --- | --- | --- | --- |
| `domain_north` / North Watch | красный | `node_res_north` | `territory_res_north` | резиденция, не захватывается обычным походом |
| `domain_river` / River Gate | синий | `node_res_river` | `territory_res_river` | резиденция, не захватывается обычным походом |
| `domain_forest` / Forest March | зеленый | `node_res_forest` | `territory_res_forest` | резиденция, не захватывается обычным походом |
| `domain_hill` / Hill Crown | желтый | `node_res_hill` | `territory_res_hill` | резиденция, не захватывается обычным походом |

Чужие резиденции не должны быть обычными целями movement. Их можно показывать как
владения другого лорда, но обычная кнопка похода туда запрещена.

## Текущее техническое соседство

Это фактический graph из `data/seed/map_edges.csv` на момент аудита.

| Узел | Текущие соседи |
| --- | --- |
| `node_res_north` Северная резиденция | Северная застава `(2)`, Северные овсы `(1)` |
| `node_res_river` Речная резиденция | Колодезный торг `(1)`, Зеркальный пруд `(2)` |
| `node_res_forest` Лесная резиденция | Травничья роща `(1)`, Черная топь `(2)` |
| `node_res_hill` Холмовая резиденция | Серый дозор `(1)`, Западный острог `(2)` |
| `node_field_oats` Северные овсы | Северная резиденция `(1)`, Западный острог `(1)`, Северная застава `(1)`, Колодезный торг `(1)`, Чародейский угол `(2)` |
| `node_fort_east` Северная застава | Северная резиденция `(2)`, Сенной посад `(2)`, Северные овсы `(1)`, Северный кряж `(2)` |
| `node_well_city` Колодезный торг | Речная резиденция `(1)`, Сенной посад `(1)`, Северные овсы `(1)`, Серый дозор `(1)` |
| `node_lake_mist` Зеркальный пруд | Речная резиденция `(2)`, Черная топь `(2)`, Восточная слобода `(1)`, Правые пашни `(1)` |
| `node_fort_west` Западный острог | Холмовая резиденция `(2)`, Двухъярусная мануфактура `(2)`, Северные овсы `(1)`, Левобережные пашни `(2)` |
| `node_mountain_gray` Серый дозор | Холмовая резиденция `(1)`, Черная топь `(3)`, Колодезный торг `(1)`, Восточная слобода `(1)` |
| `node_field_west_large` Левобережные пашни | Западный острог `(2)`, Черная топь `(2)` |
| `node_swamp_black` Черная топь | Лесная резиденция `(2)`, Зеркальный пруд `(2)`, Серый дозор `(3)`, Левобережные пашни `(2)`, Травничья роща `(2)` |
| `node_forest_dark` Травничья роща | Лесная резиденция `(1)`, Черная топь `(2)`, Волчий утес `(2)` |
| `node_mountain_west_alpine` Волчий утес | Травничья роща `(2)`, Сенной посад `(2)` |
| `node_village_barn` Сенной посад | Северная застава `(2)`, Колодезный торг `(1)`, Волчий утес `(2)`, Южная крепь `(1)`, Чародейский угол `(1)` |
| `node_fort_southwest` Южная крепь | Сенной посад `(1)` |
| `node_spanish_magic` Чародейский угол | Двухъярусная мануфактура `(2)`, Северные овсы `(2)`, Сенной посад `(1)` |
| `node_science_barn` Двухъярусная мануфактура | Западный острог `(2)`, Чародейский угол `(2)`, Правые пашни `(2)`, Нижний сад `(2)` |
| `node_village_east_shed` Восточная слобода | Серый дозор `(1)`, Зеркальный пруд `(1)` |
| `node_field_east_large` Правые пашни | Зеркальный пруд `(1)`, Двухъярусная мануфактура `(2)`, Нижний сад `(2)` |
| `node_forest_south_garden` Нижний сад | Правые пашни `(2)`, Двухъярусная мануфактура `(2)`, Лунная заводь `(1)` |
| `node_lake_south_pond` Лунная заводь | Нижний сад `(1)` |
| `node_mountain_north_alpine` Северный кряж | Северная застава `(2)` |

## Найденный рассинхрон

### 1. Technical polylines не совпадают с PNG-пунктиром

В `lord_map_layout.json` у каждого ребра только 3 точки: start, bend, end. Этого
недостаточно, чтобы повторить нарисованную извилистую дорогу. Поэтому даже
правильное по смыслу ребро в overlay выглядит как красная диагональ, которая
пересекает поля, лес, дом или другие дороги.

Вывод: после утверждения topology нужно пересобрать layout edges как реальные
polyline-пути вдоль нарисованного пунктира, а не просто как топологические
соединения между центрами узлов.

### 2. Есть визуально спорные shortcut edges

Эти ребра дают маршруты, которые игрок не считывает по PNG:

| Ребро | Почему спорно |
| --- | --- |
| `node_lake_mist` - `node_swamp_black` | соединяет правое озеро и левое болото через всю карту; визуально это выглядит как невозможный shortcut |
| `node_fort_west` - `node_science_barn` | дальняя диагональ от западного острога к южной мануфактуре; на PNG нет очевидной одной дороги |
| `node_field_oats` - `node_spanish_magic` | северное поле сразу в южный магический угол; визуально путь должен идти через центр/юг |
| `node_forest_dark` - `node_mountain_west_alpine` | дает путь до Волчьего утеса за `3 MP` от лесной резиденции; по визуальному ожиданию нужно идти через южный cluster, минимум через Южную крепь/Сенной посад |
| `node_res_forest` - `node_forest_dark` | старт лесного лорда телепортирует к дальнему нижнему лесу, хотя визуально от центральной лесной резиденции ближе южный/центральный выход |
| `node_res_forest` - `node_swamp_black` | аналогично: слишком дальний стартовый shortcut к левому болоту |
| `node_res_hill` - `node_fort_west` | холмовая резиденция получает прямой выход на западный острог, хотя визуально она находится правее центрального дома |

### 3. Стоимость MP сейчас читается как глобальная цена, а не как доступность

Если UI показывает `6 MP` на чужой/нейтральной дальней территории, игрок думает,
что туда можно идти прямо сейчас. Это неверно для будущего правила movement,
потому что нейтральные и чужие территории не должны быть транзитными.

## Правило movement v0.2

Маршрут нужно считать не просто Dijkstra по всем ребрам, а Dijkstra с блокерами.

Правила:

1. Своя резиденция - старт армии, но чужие резиденции не являются обычной целью
   похода.
2. Через свои территории можно проходить транзитом без боя.
3. Через нейтральные территории нельзя проходить транзитом. Нейтральная
   территория может быть только первой целью, где поход останавливается и
   начинается claim/PvE/захват.
4. Через чужие территории нельзя проходить транзитом. Чужая capturable territory
   может быть только первой боевой целью, если правила PvP это разрешают.
5. Contested/battle territory всегда останавливает маршрут.
6. В UI не нужно показывать MP-плашки на всех возможных математических путях.
   Нужно подсвечивать только реально доступные цели текущего хода. Стоимость
   показывать для наведенной/выбранной цели.

Пример для лесного лорда на старте:

- если у леса есть только `node_res_forest`, то доступными могут быть только
  ближайшие нейтральные узлы, напрямую связанные с лесной резиденцией;
- путь `Лесная резиденция -> Черная топь -> Зеркальный пруд` запрещен, пока
  `Черная топь` не стала своей территорией;
- путь к `Волчий утес` запрещен, если для него нужно проходить через нейтральные
  промежуточные территории.

## Техническая карта v0.2: что нужно принять перед CSV-правкой

Перед правкой seed нужно руками принять два слоя.

### A. Стартовые frontier edges резиденций

Текущие стартовые ребра выглядят неравномерно и местами не совпадают с тем, где
кружки резиденций лежат на PNG. Предлагаемый принцип:

| Резиденция | Должна иметь выходы к | Причина |
| --- | --- | --- |
| Северная | верхний/северный cluster: `node_field_oats`, `node_fort_east` | красный старт смотрит в верх/лево |
| Речная | восточный/водный cluster: `node_well_city`, `node_lake_mist` или `node_village_east_shed` | синий старт смотрит вправо к поселению/воде |
| Лесная | юго-западный/лесной cluster: нужно подтвердить между `node_fort_southwest`, `node_mountain_gray`, `node_swamp_black`, `node_forest_dark` | текущий shortcut к дальнему лесу спорный |
| Холмовая | юго-восточный/центральный cluster: нужно подтвердить между `node_village_barn`, `node_field_east_large`, `node_mountain_gray` | текущий выход в западный острог спорный |

### B. Capturable route graph

Текущий граф можно оставить как черновой список соседств, но перед генерацией PNG
нужно удалить или заменить shortcut edges из раздела "Найденный рассинхрон".

Минимальный набор обязательных решений:

1. Удалить или заменить `node_lake_mist` - `node_swamp_black`.
2. Удалить или заменить `node_fort_west` - `node_science_barn`.
3. Удалить или заменить `node_field_oats` - `node_spanish_magic`.
4. Удалить или заменить `node_forest_dark` - `node_mountain_west_alpine`.
5. Решить новый путь к `node_mountain_west_alpine`:
   - если визуально Волчий утес должен идти через Южную крепь, добавить связь
     `node_fort_southwest` - `node_mountain_west_alpine` или
     `node_fort_southwest` - `node_village_barn` - `node_mountain_west_alpine`
     как единственный читаемый route;
   - затем удалить прямой лесной shortcut.
6. Пересмотреть лесные стартовые ребра, чтобы лесной лорд не получал дальний
   shortcut в нижний левый угол карты.
7. Пересмотреть холмовые стартовые ребра, чтобы холмовая резиденция не получала
   прямой shortcut на западный острог, если это не видно на PNG.

## Draft v0.2 edge list

Это предлагаемый целевой graph для обсуждения перед записью в
`data/seed/map_edges.csv`. Он убирает самые спорные shortcuts и делает стартовые
выходы лордов ближе к тому, где их резиденции стоят на центральной части карты.

### Стартовые ребра резиденций

| Edge id | From | To | MP | Статус |
| --- | --- | --- | --- | --- |
| `edge_north_field` | `node_res_north` | `node_field_oats` | 1 | оставить |
| `edge_north_fort_east` | `node_res_north` | `node_fort_east` | 2 | оставить |
| `edge_river_well` | `node_res_river` | `node_well_city` | 1 | оставить |
| `edge_river_lake` | `node_res_river` | `node_lake_mist` | 2 | оставить, но layout-polyline вести по правой дороге |
| `edge_forest_fort_southwest` | `node_res_forest` | `node_fort_southwest` | 1 | добавить вместо дальнего лесного shortcut |
| `edge_forest_mountain_gray` | `node_res_forest` | `node_mountain_gray` | 2 | добавить/подтвердить как второй лесной выход |
| `edge_hill_village` | `node_res_hill` | `node_village_barn` | 1 | добавить вместо западного shortcut |
| `edge_hill_field_east` | `node_res_hill` | `node_field_east_large` | 2 | добавить/подтвердить как второй холмовой выход |

### Север и верхний центр

| Edge id | From | To | MP | Статус |
| --- | --- | --- | --- | --- |
| `edge_fort_west_field_north` | `node_fort_west` | `node_field_oats` | 1 | оставить |
| `edge_field_west_field_oats` | `node_field_west_large` | `node_field_oats` | 1 | добавить, если верхняя левая дорога читается как прямая связь |
| `edge_field_north_fort_east` | `node_field_oats` | `node_fort_east` | 1 | оставить |
| `edge_field_north_well` | `node_field_oats` | `node_well_city` | 1 | оставить |
| `edge_fort_east_mountain_north` | `node_fort_east` | `node_mountain_north_alpine` | 2 | оставить |
| `edge_fort_west_field_west` | `node_fort_west` | `node_field_west_large` | 2 | оставить/подтвердить |

### Запад и юго-запад

| Edge id | From | To | MP | Статус |
| --- | --- | --- | --- | --- |
| `edge_field_west_swamp` | `node_field_west_large` | `node_swamp_black` | 2 | оставить |
| `edge_swamp_forest_west` | `node_swamp_black` | `node_forest_dark` | 2 | оставить |
| `edge_swamp_mountain` | `node_swamp_black` | `node_mountain_gray` | 3 | оставить/подтвердить как тяжелый болотный переход |
| `edge_mountain_fort_southwest` | `node_mountain_gray` | `node_fort_southwest` | 1 | добавить, если центральная горная дорога ведет к Южной крепи |
| `edge_fort_southwest_mountain_west` | `node_fort_southwest` | `node_mountain_west_alpine` | 2 | добавить как основной путь к Волчьему утесу |

### Центральный и южный cluster

| Edge id | From | To | MP | Статус |
| --- | --- | --- | --- | --- |
| `edge_village_fort_southwest` | `node_village_barn` | `node_fort_southwest` | 1 | оставить |
| `edge_mountain_west_village` | `node_mountain_west_alpine` | `node_village_barn` | 2 | оставить/подтвердить |
| `edge_village_magic` | `node_village_barn` | `node_spanish_magic` | 1 | оставить |
| `edge_magic_science` | `node_spanish_magic` | `node_science_barn` | 2 | оставить |
| `edge_science_forest_south` | `node_science_barn` | `node_forest_south_garden` | 2 | оставить |
| `edge_forest_south_lake_south` | `node_forest_south_garden` | `node_lake_south_pond` | 1 | оставить |

### Восток

| Edge id | From | To | MP | Статус |
| --- | --- | --- | --- | --- |
| `edge_village_well` | `node_village_barn` | `node_well_city` | 1 | оставить/подтвердить, если центральная дорога читается |
| `edge_well_mountain_central` | `node_well_city` | `node_mountain_gray` | 1 | оставить/подтвердить |
| `edge_mountain_central_village_east` | `node_mountain_gray` | `node_village_east_shed` | 1 | оставить |
| `edge_village_east_lake` | `node_village_east_shed` | `node_lake_mist` | 1 | оставить |
| `edge_lake_field_east` | `node_lake_mist` | `node_field_east_large` | 1 | оставить |
| `edge_field_east_science` | `node_field_east_large` | `node_science_barn` | 2 | оставить/подтвердить |
| `edge_field_east_forest_south` | `node_field_east_large` | `node_forest_south_garden` | 2 | оставить |

### Удалить из v0.2 draft

| Current edge | Причина |
| --- | --- |
| `edge_forest_dark` / `node_res_forest` - `node_forest_dark` | слишком дальний стартовый shortcut |
| `edge_forest_swamp` / `node_res_forest` - `node_swamp_black` | слишком дальний стартовый shortcut |
| `edge_hill_fort_west` / `node_res_hill` - `node_fort_west` | холмовая резиденция получает западный shortcut |
| `edge_fort_west_science` / `node_fort_west` - `node_science_barn` | дальняя диагональ без читаемой одной дороги |
| `edge_field_magic` / `node_field_oats` - `node_spanish_magic` | север-юг shortcut через карту |
| `edge_lake_swamp` / `node_lake_mist` - `node_swamp_black` | восток-запад shortcut через карту |
| `edge_forest_west_mountain_west` / `node_forest_dark` - `node_mountain_west_alpine` | дает спорный путь до Волчьего утеса за 3 MP |

### Эффект v0.2 draft на пример лесного лорда

Если у лесного лорда на старте есть только `node_res_forest`, то видимые цели
первого похода:

- `node_fort_southwest` за `1 MP`;
- `node_mountain_gray` за `2 MP`, если это ребро принято.

`node_mountain_west_alpine` становится недоступен на старте, потому что путь к
нему идет через `node_fort_southwest`, а `node_fort_southwest` еще нейтральная
и не может быть транзитом. После захвата Южной крепи путь
`node_res_forest -> node_fort_southwest -> node_mountain_west_alpine` становится
читаемым и стоит `3 MP` суммарно.

## Правила синхронизации после принятия v0.2

После принятия технической карты порядок такой:

1. Обновить `data/seed/map_edges.csv`.
2. Обновить `backend/witcher_larp/web/lord/assets/lord_map_layout.json`:
   - удалить старые ребра;
   - добавить новые;
   - сделать polylines не 3-точечными диагоналями, а трассами вдоль будущего
     PNG-пунктира.
3. Убрать ручной дубль graph из `prototypes/stage2b-v2/src/App.tsx` или
   генерировать его из того же canonical source.
4. Обновить тесты контрактов, чтобы они сверяли:
   - seed edges;
   - layout edges;
   - отсутствие чужих резиденций как обычных movement targets;
   - запрет транзита через нейтральные/чужие территории.
5. Перегенерировать PNG под принятую technical topology.
6. Снова сделать overlay-аудит: technical edges поверх новой PNG должны идти по
   тому же пунктиру, который видит игрок.
