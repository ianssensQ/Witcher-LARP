# Lord map real plot topology v0.1

> Текущий принятый sparse-граф после балансировки:
> `docs/lord-map-technical-graph-v0.3.md`. Dev-аудит рассинхронизации текущей
> PNG-карты и старого технического графа вынесен в
> `docs/lord-map-technical-audit-v0.2.md`. Этот v0.1-док остается историей
> первичного seed-topology и route clusters.

Документ фиксирует рабочую расшифровку пользовательской схемы участка для Stage 1 seed topology. Stage 1 seed уже обновлен по принятым решениям: 4 неприступные резиденции в центральном доме, 19 capturable territories, 2 excluded зоны без gameplay.

## Принятые решения

- Центральный активный дом находится в центре схемы и является стартовым cluster для 4 замков/резиденций графов.
- Резиденции графов находятся внутри центрального дома, не захватываются и не являются целью обычного movement.
- Карта строится по строгой схеме участка, адаптированной под gameplay.
- Весь граф дорог/территорий виден игрокам сразу.
- Скрываются только детали чужих армий/гарнизонов через future `lord_map_intel`.
- Прежний каталог на 19 capturable territories сохраняется; мелкие физические подписи можно объединять в более крупные игровые территории.
- Горных территорий остается 3, как в прежнем каталоге: центральная/северная/западная игровые горы могут опираться на две реальные альпийские горки и gameplay-разделение.
- Candidate route clusters ниже приняты как основа для seed-графа.
- Чужая лошадь/армия скрыта до разведки. Всем видна только карта территорий, дороги, владельцы и contested/claim факты.

## Ориентация

До отдельного подтверждения используем ориентацию самой схемы:

- верх схемы = верх карты;
- левый большой зеленый участок = западный/левый field cluster;
- правый большой зеленый участок = восточный/правый field cluster;
- нижние сад/пруд/двухэтажный сарай = южный cluster.

Это рабочие названия для seed IDs, не обязательно player-facing compass naming.

## Локации, прочитанные со схемы

| Seed node id | Подпись на схеме | Игровой тип | Комментарий |
| --- | --- | --- | --- |
| `node_res_north`, `node_res_river`, `node_res_forest`, `node_res_hill` | центральный активный дом, комнаты графов | residence | 4 raid-only замка/резиденции внутри дома |
| `node_fort_east` | беседка, в игре крепость | fort | верхняя беседка над центральным домом |
| `node_field_oats` | поле, сельская местность с полями и деревнями | field | верхнее/северное поле слева от колодца |
| `node_well_city` | колодец, независимый город ресурсодобычи | resource_city | справа от верхнего поля |
| `node_mountain_gray` | альпийская горка, в игре гора | mountain | рядом с колодцем и центральным домом |
| `node_fort_west` | беседка, в игре крепость | fort | беседка слева/сверху от центрального дома |
| `node_village_east_shed` | сарай, в игре деревня | village | справа от центрального дома, рядом с бассейном |
| `node_lake_mist` | бассейн, в игре озеро | lake | справа от центрального дома |
| `node_field_west_large` | поле, сельская местность с полями и деревнями | field | большой левый зеленый участок |
| `node_swamp_black` | прудик, в игре болото | swamp | левый нижний пруд |
| `node_forest_dark` | ботанический сад и теплица, в игре лес/деревенская окраина | forest | большой левый нижний зеленый участок |
| `node_mountain_west_alpine` | альпийская горка, в игре гора | mountain | у нижней левой части центрального дома |
| `node_village_barn` | сарай, в игре деревня | village | серый сарай ниже центрального дома |
| `node_fort_southwest` | беседка, в игре крепость | fort | нижняя левая беседка |
| `node_spanish_magic` | испанский уголок, независимый город магии | magic_city | ниже центрального дома; соседняя нераспознанная подпись не заводится отдельной территорией |
| `node_science_barn` | двухэтажный сарай и теплица, независимый город науки | science_city | нижний центр, рядом с садиком |
| `node_field_east_large` | поле, сельская местность с полями и деревнями | field | большой правый зеленый участок |
| `node_forest_south_garden` | садик, в игре лес | forest | нижний правый зеленый участок |
| `node_lake_south_pond` | пруд, в игре озеро | lake | нижний правый водоем |

Черновик дает 21 capturable location, если считать каждую подписанную игровую зону отдельной территорией. По подтвержденному решению пользователя seed сохраняет 19 capturable territories, а мелкие физические объекты объединяются с соседними игровыми территориями.

## Принятые объединения

Для сохранения 19 capturable territories принимаем такие объединения:

- теплица у ботанического сада входит в `node_forest_dark`: деревенская точка внутри ботанического леса;
- теплица у двухэтажного сарая входит в `node_science_barn`: деревенский suburb у города науки;
- нераспознанная деревенская подпись около испанского уголка входит в соседний magic/science cluster и не получает отдельный node.

Нераспознанная подпись не заводится отдельной территорией: она не подтверждена как самостоятельная важная локация и входит в соседний magic/science cluster.

## Принятый 19-territory seed catalog

Для совместимости с существующим lord runtime часть старых IDs сохраняется, но их
name/type/route meaning обновляются под реальную схему участка.

| Seed node id | Игровое имя | Физическая база на схеме | Тип |
| --- | --- | --- | --- |
| `node_fort_east` | Северная Застава | верхняя беседка | fort |
| `node_fort_west` | Западный Острог | беседка у центрального дома | fort |
| `node_fort_southwest` | Южная Крепь | нижняя левая беседка | fort |
| `node_field_oats` | Северные Овсы | верхнее поле | field |
| `node_field_west_large` | Левобережные Пашни | большое левое поле | field |
| `node_field_east_large` | Правые Пашни | большое правое поле | field |
| `node_village_barn` | Сенной Посад | сарай ниже центрального дома | village |
| `node_village_east_shed` | Восточная Слобода | сарай справа от центрального дома | village |
| `node_well_city` | Колодезный Торг | колодец | resource_city |
| `node_spanish_magic` | Чародейский Угол | испанский уголок + соседняя нераспознанная деревенская подпись | magic_city |
| `node_science_barn` | Двухъярусная Мануфактура | двухэтажный сарай + соседняя теплица | science_city |
| `node_forest_dark` | Травничья Роща | ботанический сад + теплица | forest |
| `node_forest_south_garden` | Нижний Сад | садик справа внизу | forest |
| `node_lake_mist` | Зеркальный Пруд | бассейн | lake |
| `node_lake_south_pond` | Лунная Заводь | правый нижний пруд | lake |
| `node_swamp_black` | Черная Топь | левый прудик/болото | swamp |
| `node_mountain_north_alpine` | Северный Кряж | gameplay-северная горная зона около верхней части схемы | mountain |
| `node_mountain_gray` | Серый Дозор | альпийская горка у колодца/центрального дома | mountain |
| `node_mountain_west_alpine` | Волчий Утес | альпийская горка слева/ниже центрального дома | mountain |

## Принятые route clusters

Эти adjacency принимаются как основа seed-графа по визуальной близости на схеме.

### Центральный дом

- `node_res_north` -> `node_fort_east`
- `node_res_north` -> `node_field_oats`
- `node_res_river` -> `node_well_city`
- `node_res_river` -> `node_lake_mist`
- `node_res_forest` -> `node_forest_dark`
- `node_res_forest` -> `node_swamp_black`
- `node_res_hill` -> `node_mountain_gray`
- `node_res_hill` -> `node_fort_west`

### Север и верхний центр

- `node_fort_west` -> `node_field_oats`
- `node_field_oats` -> `node_fort_east`
- `node_fort_east` -> `node_mountain_north_alpine`
- `node_field_oats` -> `node_well_city`
- `node_well_city` -> `node_mountain_gray`
- `node_mountain_gray` -> `node_village_east_shed`

### Западный cluster

- `node_fort_west` -> `node_field_west_large`
- `node_field_west_large` -> `node_swamp_black`
- `node_swamp_black` -> `node_forest_dark`
- `node_forest_dark` -> `node_mountain_west_alpine`
- `node_mountain_west_alpine` -> `node_village_barn`
- `node_village_barn` -> `node_fort_southwest`

### Южный cluster

- `node_village_barn` -> `node_spanish_magic`
- `node_spanish_magic` -> `node_science_barn`
- `node_science_barn` -> `node_forest_south_garden`
- `node_forest_south_garden` -> `node_lake_south_pond`

### Восточный cluster

- `node_village_east_shed` -> `node_lake_mist`
- `node_lake_mist` -> `node_field_east_large`
- `node_field_east_large` -> `node_science_barn`
- `node_field_east_large` -> `node_forest_south_garden`

## Итог после seed update

1. Подписи можно объединять.
2. Нераспознанная подпись не считается отдельной территорией.
3. Горные территории остаются как в прежнем каталоге: 3.
4. Candidate route clusters принимаются как basis для seed-графа.
5. Чужая лошадь/армия скрыта до разведки; всем видна карта с территориями и владельцами.

Stage 1 seed update выполнен: `data/seed/map_nodes.csv`, `map_edges.csv`, `territories.csv`, `territory_forts.csv` и seed contract validation выровнены под эти решения. Stage 2 technical layout тоже заведен в `backend/witcher_larp/web/lord/assets/lord_map_layout.json`: он хранит координаты, hit-zones, полилинии дорог, anchors лошади и minimap transform. Следующий практический слой - generated/painted map background поверх этого canvas.
