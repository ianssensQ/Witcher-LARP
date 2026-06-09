# Lord map implementation blueprint v0.1

Документ фиксирует, как продуктово и технически внедрять лордскую стратегическую карту после принятого V1-контракта в `docs/game-mechanics.md`.

Реальная схема участка и черновая расшифровка подписей зафиксированы отдельно:
`docs/lord-map-real-plot-topology-v0.1.md`. Stage 1 seed topology уже выровнен
по принятым там физическим локациям, объединениям и route clusters.

Текущий принятый sparse-граф после dev-аудита:
`docs/lord-map-technical-graph-v0.3.md`. Audit trail рассинхронизации
player-facing PNG и старого technical graph: `docs/lord-map-technical-audit-v0.2.md`.
Перед новой генерацией карты сначала держать `map_edges.csv` и
`lord_map_layout.json` на v0.3 topology, затем перегенерировать PNG под этот
граф.

Текущий строгий visual-sync pipeline для сравнения и дальнейшего runtime-внедрения:
AI/OpenRouter генерирует только roadless-base без дорог, а
`scripts/build_lord_map_strict_v4_baked_roads.py` запекает дороги в PNG/WebP
строго из `data/seed/map_edges.csv`. Поэтому player-facing картинка не должна
содержать AI-дороги, лишние тропы, технические подписи или runtime-пунктир.
В v6 четыре стартовые резиденции сохраняют castle-square, резидентские
стартовые дороги рисуются от самих кругов, `node_mountain_gray` опущен ниже,
`node_fort_west` перенесен выше-правее, а дорога
`node_village_barn -> node_mountain_gray` читается непрерывной. Контрольный
аудит v6: `reports/map-debug-crops/lord_map_ai_strict_v6-road-audit.json`
должен иметь 26/26 edges, `0` missing/extra edges, `0` пересечений и `0`
видимых нерезидентских дорожных сегментов внутри центрального замка.

## Цель карты

Карта лорда - это не GPS/QR-трекинг и не отдельная мини-игра. Это экран управления одной активной лошадью/герой-армией лорда поверх иллюстрированной карты площадки:

- лорд видит свою позицию, ресурсы, MP, весь граф дорог/территорий, владение, contested/battle overlays и отредактированные разведданные;
- лорд кликает по разрешенной территории или узлу дороги;
- UI показывает самый дешевый доступный маршрут и стоимость в MP;
- после подтверждения сервер создает `pending_move`, списывает MP и сам завершает arrival по времени, если вкладка закрылась или сеть моргнула;
- при arrival на нейтральную или чужую capturable territory сервер создает claim/prebattle, а UI открывает боевой баннер/переход к лордскому бою;
- центральный активный дом является реальным центром участка и содержит 4 raid-only резиденции/замка лордов, на которые нельзя нападать обычным движением и которые нельзя захватывать.

## Что уже есть в коде

Текущее состояние проекта после Stage 1 seed update:

- `data/seed/movement_rules.csv` уже совпадает с новым правилом: MP cap `6`, refill `+3/hour`.
- `data/seed/map_nodes.csv`, `map_edges.csv`, `territories.csv` отражают принятую карту: 4 raid-only резиденции в центральном доме, 19 capturable territories, 2 excluded зоны и принятый weighted route graph.
- `data/seed/territory_forts.csv` существует, зарегистрирован в `backend/witcher_larp/content_schema.py`, а seed validation проверяет, что у каждой capturable territory ровно один fort row и garrison capacity соответствует tier default.
- `backend/witcher_larp/web/lord/assets/lord_map_layout.json` существует как technical layout: canvas 2400x1500, 25 node anchors, hit-zones, 29 edge polylines, central house rect, minimap transform и visibility policy.
- `pending_lord_moves` и `lord_map_intel` еще не существуют в `backend/witcher_larp/runtime_schema.py`.
- `backend/witcher_larp/lord_runtime.py::move_lord` сейчас делает синхронное перемещение: валидирует route по `map_edges`, списывает MP, сразу обновляет `domain_runtime_state.current_node_id` и `active_army_runtime.location_node_id`, затем создает claim при необходимости.
- `backend/witcher_larp/lord_panel.py::build_lord_state` отдает лорду `domain`, `movement`, территории, `active_army`, `map_nodes`, `map_edges`, `lord_map_layout` и action surfaces, но еще не отдает enemy intel read model и active `pending_move`.
- `backend/witcher_larp/web/lord/*` сейчас является статическим HTML/CSS/JS panel shell с technical SVG map render: pan camera, minimap viewport navigation, route graph, clickable hit-zones, selected route preview, MP cost и marker активной армии уже работают от `lord_map_layout`. Painted raster background, horse bitmap asset и pending movement animation еще не реализованы.

## Целевая data model

### Seed CSV

Минимальный V1 seed должен описывать 25 map nodes plus optional route waypoints:

- 4 raid-only резиденции/замка лордов в центральном активном доме;
- 19 capturable territory nodes из V1-каталога;
- 2 excluded nodes: старый дом и соседний сарай, без edges/territories/routes.
- optional non-territory route waypoints у центрального дома/дорожек, только если они нужны для строгой адаптированной схемы участка.

`territories.csv` должен содержать 23 territory rows:

- 4 residence territories, owned by starting domains, `bonus_type=residence`, не capturable обычным movement;
- 19 capturable territories с tier, primary bonus, neutral defense profile и будущей ссылкой на fort metadata.

`map_edges.csv` должен стать каноническим weighted graph по строгой адаптированной схеме участка:

- edge cost `1` для коротких соседних переходов;
- edge cost `2` для длинных/лесных/горных/болотных переходов;
- bidirectional defaults = `true`;
- excluded nodes не получают edges;
- центральный дом не является capturable territory; optional route waypoint у дома не имеет владельца, гарнизона, дохода, боя и отдельного UI-таргета;
- route validator не должен проводить лошадь сквозь нейтральную, чужую или contested территорию без остановки.

v6 convenience pass добавляет три ребра без новых территорий: `node_mountain_north_alpine -> node_lake_mist`
за 2 MP, `node_mountain_west_alpine -> node_spanish_magic` за 1 MP и
`node_forest_dark -> node_field_oats` за 2 MP.

`territory_forts.csv` нужен как отдельный seed-слой для UI и геймплея гарнизонов:

```csv
fort_id,territory_id,name,theme,garrison_capacity,art_prompt_id,background_asset_id,card_asset_id
```

Если мы хотим минимальный backend-diff, `garrison_capacity` можно сначала оставить в fort table, а позже добавить runtime guard для transfer capacity. Если нужен строгий контракт сразу, validation должна проверять, что каждая capturable territory имеет ровно один fort row.

### Layout manifest

Stage 2 technical layout уже заведен как runtime asset:

```text
backend/witcher_larp/web/lord/assets/lord_map_layout.json
```

Он служит координатной основой для будущей красивой карты. В нем есть:

- `canvas` 2400x1500;
- `central_house` как неприступная область с резиденциями графов;
- `nodes` для всех 25 seed nodes: residences, 19 capturable territories и 2 excluded silhouettes;
- `hit_zone` для каждого node;
- `edges` для всех 29 seed edges, где первая и последняя точки совпадают с anchors соответствующих seed nodes;
- `visibility`, где весь graph видим, а чужая армия/гарнизон скрываются до intel;
- `minimap` source transform.

Layout contract покрыт тестами: `tests/test_lord_map_layout_contract.py` сверяет JSON с `data/seed/map_nodes.csv` и `map_edges.csv`, а `tests/test_lord_panel_contract.py` проверяет, что layout раздается через `/static/lord/assets/lord_map_layout.json` и включается в `/api/lords/{lord_id}/state`.

`lord_map_layout.json` должен быть hand-authored alignment layer, а не gameplay source of truth. Gameplay truth остается в CSV/runtime.

Рекомендуемое место для runtime UI:

```text
backend/witcher_larp/web/lord/assets/lord_map_layout.json
backend/witcher_larp/web/lord/assets/lord_map_venue_v1.png
backend/witcher_larp/web/lord/assets/horse_marker_*.png
backend/witcher_larp/web/lord/assets/intel_marker_*.png
```

Минимальная структура:

```json
{
  "layout_id": "venue_map_v1",
  "art_asset": "assets/lord_map_venue_v1.png",
  "canvas": { "width": 2400, "height": 1500 },
  "viewport": { "default_x": 0.5, "default_y": 0.5, "mobile_zoom": 1.1, "desktop_zoom": 0.78 },
  "central_house": { "x": 1200, "y": 760, "w": 260, "h": 180 },
  "nodes": {
    "node_res_north": {
      "x": 1130,
      "y": 720,
      "label_anchor": { "x": 1130, "y": 675 },
      "hit_zone": { "type": "circle", "cx": 1130, "cy": 720, "r": 52 }
    }
  },
  "edges": {
    "edge_north_field": {
      "points": [[1130, 720], [1060, 600], [980, 420]]
    }
  },
  "minimap": { "x": 24, "y": 24, "width": 260, "height": 164 }
}
```

Важное ограничение: layout может хранить координаты и hit-zones, но не должен решать, кому принадлежит территория, сколько стоит route, можно ли туда идти и какие enemy details видит лорд. Это делает сервер.

## Runtime и API

### Новые runtime таблицы

`pending_lord_moves`:

```sql
CREATE TABLE pending_lord_moves (
  move_id TEXT PRIMARY KEY,
  domain_id TEXT NOT NULL,
  lord_id TEXT NOT NULL,
  from_node_id TEXT NOT NULL,
  to_node_id TEXT NOT NULL,
  route_node_ids_json TEXT NOT NULL DEFAULT '[]',
  mp_cost INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  source TEXT NOT NULL,
  started_at TEXT NOT NULL,
  arrival_at TEXT NOT NULL,
  completed_at TEXT,
  result_json TEXT NOT NULL DEFAULT '{}'
);
```

`lord_map_intel`:

```sql
CREATE TABLE lord_map_intel (
  domain_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  intel_level TEXT NOT NULL DEFAULT 'presence',
  revealed_at TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (domain_id, target_type, target_id)
);
```

`target_type` values for V1: `enemy_army`, `garrison`, `raid_effect`. Базовый граф карты не раскрывается по шагам: все nodes/edges видны с начала игры, а `lord_map_intel` управляет только точностью чужих деталей.

### Pending movement flow

Перед каждым `GET /api/lords/{lord_id}/state` и перед каждым move mutation сервер должен вызвать reconciliation:

1. Найти pending moves со `status='pending'` и `arrival_at <= now`.
2. Завершить arrival атомарно:
   - обновить `domain_runtime_state.current_node_id`;
   - обновить `active_army_runtime.location_node_id`;
   - обновить visible presence/intel hints по месту arrival, если правила разведки это требуют;
   - создать claim/prebattle через существующую `_create_claim_if_needed`;
   - записать event `lord_move_arrived`.
3. Вернуть актуальный `pending_move=null` или completed result в state.

При новом move:

1. Сервер валидирует, что у домена нет active pending move.
2. Сервер валидирует route по `map_edges`.
3. Сервер проверяет, что target не является excluded zone, чужой raid-only резиденцией или запрещенным technical waypoint.
4. Сервер строит route stop: если путь упирается в чужую/contested territory, target становится первым блокирующим узлом, а не дальним узлом за ним.
5. Сервер списывает MP сразу.
6. Сервер создает `pending_lord_moves` с deterministic `arrival_at`.
7. Сервер возвращает payload:

```json
{
  "status": "pending_move",
  "pending_move": {
    "move_id": "move_...",
    "route": ["node_res_north", "node_field_oats", "node_fort_east"],
    "mp_cost": 2,
    "started_at": "...",
    "arrival_at": "..."
  }
}
```

### Lord state payload additions

`GET /api/lords/{lord_id}/state` должен добавить:

```json
{
  "map_nodes": [],
  "map_edges": [],
  "lord_map_layout": {},
  "lord_map_intel": {
    "graph_visible": true,
    "enemy_armies": [],
    "hidden_detail_policy": "enemy_army_and_garrison_details_redacted"
  },
  "pending_move": null,
  "route_options": {
    "current_node_id": "node_res_north",
    "mp_available": 6
  }
}
```

`map_nodes` нужен именно целиком, потому что UI должен рисовать центральный дом, резиденции, все дороги, все территории and excluded silhouettes. Hidden gameplay details redact-ятся отдельно через `lord_map_intel` и garrison visibility rules.

## Frontend architecture

В V1 карту лучше внедрять как отдельный full-screen mode внутри lord static panel:

- `/lords/home` остается первым экраном castle/selected-territory;
- кнопка карты или minimap открывает `view=map`;
- карта держит локальное UI-состояние: pan offset, selected node, hovered node, route preview, pending animation progress;
- gameplay state всегда приходит из `currentState` с сервера;
- mutation только одна: confirm move.

Рендеринг:

- raster background: `lord_map_venue_v1.png`;
- route graph overlay: SVG layer по `lord_map_layout.edges`;
- hit-zones: transparent SVG/canvas layer по `lord_map_layout.nodes`;
- horse marker: absolute image anchored to active army node or interpolated along pending route;
- enemy intel layer: owner sees details, other lords see presence/unknown silhouettes unless `lord_map_intel` reveals more;
- tactical popup: компактная карточка территории с owner, tier, bonus, garrison visibility, claim/battle state, route cost and Move/Enter battle action;
- minimap: тот же background в малом масштабе + viewport rectangle.

Технически не стоит bake-ить тексты и labels в картинку. Текстовые названия, route costs, owner ribbons, contested markers and intel markers должны быть live overlays, чтобы не перегенерировать art при балансных правках.

## Asset generation order

Ассеты нельзя генерировать до согласования topology и ориентации карты. Правильный порядок:

1. Подтвердить реальные локации, ориентацию карты и центральный активный дом как cluster четырех резиденций.
2. Обновить seed graph и сделать rough `lord_map_layout.json` с временными координатами.
3. Нарисовать/сгенерировать low-detail draft map или SVG fallback, проверить все hit-zones.
4. После acceptance topology - сгенерировать final painted raster map.
5. Подогнать layout coordinates под final raster.
6. Сгенерировать horse marker, intel marker/unknown silhouette assets, territory card/background set.
7. Прогнать browser smoke на desktop and mobile viewports.

## Поэтапная реализация

### Stage 1 - Topology seed

Изменения:

- обновить `data/seed/map_nodes.csv` до 25 core nodes plus optional route waypoints;
- обновить `data/seed/territories.csv` до 23 territories;
- обновить `data/seed/map_edges.csv` под V1 graph;
- добавить `data/seed/territory_forts.csv`;
- зарегистрировать `territory_forts.csv` в `content_schema.py`;
- добавить validation: fort references known territory, no duplicate fort per territory, no missing fort for capturable territory;
- обновить seed contract tests.

Проверки:

```text
uv run pytest tests/test_seed_contract.py tests/test_seed_validation.py -q
uv run python scripts/taskctl.py validate
```

### Stage 2 - Layout manifest and read model

Изменения:

- добавить static `backend/witcher_larp/web/lord/assets/lord_map_layout.json`;
- добавить static fallback visual asset for topology review;
- расширить `build_lord_state`: `map_nodes`, `lord_map_layout`, map metadata;
- не добавлять intel/pending mutation yet, только read model placeholders.

Проверки:

```text
uv run pytest tests/test_lord_panel_contract.py -q
```

### Stage 3 - Pending movement backend

Изменения:

- добавить `pending_lord_moves` schema;
- вынести синхронный arrival из `move_lord` в helper;
- сделать `move_lord` создающим pending move;
- добавить reconciliation before state/move;
- сохранить backwards-compatible fields там, где tests/UI еще ждут `from_node_id`, `to_node_id`, `mp_spent`.

Проверки:

```text
uv run pytest tests/test_lord_runtime.py tests/test_lord_panel_contract.py -q
```

### Stage 4 - Enemy intel backend

Изменения:

- добавить `lord_map_intel`;
- считать весь graph видимым с начала игры;
- редактировать чужие army/garrison details в lord state;
- показывать enemy presence/unknown silhouette там, где правила допускают факт присутствия без состава;
- повышать intel level для owner/master/scouting/magic/NPC reveal rules.

Проверки:

```text
uv run pytest tests/test_lord_runtime.py tests/test_lord_panel_contract.py -q
```

### Stage 5 - Browser map UI

Изменения:

- перестроить `backend/witcher_larp/web/lord/index.html`, `lord.css`, `lord.js` под `/lords/home` + full-screen map mode;
- добавить pan camera, route preview, selected territory popup, enemy intel redaction, pending horse animation;
- оставить сервер authoritative после refresh/restart;
- добавить browser smoke/visual acceptance.

Проверки:

```text
uv run pytest tests/test_lord_panel_contract.py tests/test_lord_runtime.py -q
browser smoke: login -> home -> map -> target -> route preview -> pending move -> refresh -> arrival
```

### Stage 6 - Final art pass

Изменения:

- заменить fallback map на final generated/local painted map;
- подогнать `lord_map_layout.json`;
- добавить final horse/intel marker/territory card assets;
- выполнить visual audit по `docs/ui/stage2b-visual-acceptance.md`.

## Зафиксированные ответы перед Stage 1

Ответы пользователя от текущего планирования:

1. `central_court` как отдельной игровой территории нет. В реальности есть центральный активный дом, внутри которого сидят графы; их замки/резиденции находятся в этом доме, их нельзя захватывать и на них нельзя нападать обычным movement.
2. Карта должна идти по строгой схеме участка, адаптированной под игровой gameplay.
3. Весь граф дорог и территорий виден с начала игры; скрыты только детали чужих армий/гарнизонов.

После этих трех ответов следующий безопасный шаг - Stage 1: обновить seed topology и tests, еще без генерации финальных ассетов.

Дополнение после схемы участка: перед seed update нужно подтвердить вопросы из
`docs/lord-map-real-plot-topology-v0.1.md`, потому что схема содержит 21
возможную capturable location вместо прежнего каталога на 19 территорий.
Вопросы подтверждены: сохраняем 19 capturable territories, объединяем мелкие
физические подписи, оставляем 3 игровые горы, используем candidate route
clusters как basis, а чужую лошадь/армию скрываем до разведки.
