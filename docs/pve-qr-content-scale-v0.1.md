# PvE/QR content scale v0.1

## Назначение

Документ фиксирует первый фрагмент расширения QR/PvE-контента под 10-часовую
игру, где до 12 игроков могут брать миссии через QR/manual ID. Это не меняет
физический production profile игры само по себе: цель фрагмента - расширить
контентную емкость и отделить стабильные печатные QR от изменяемой начинки
квестов.

Runtime seed CSV в `data/seed/` теперь собираются из authoring-слоя через
`scripts/pve_authoring.py compile-seed`. Authoring-слой в `data/authoring/`
остается источником для подготовки печати, проверки покрытия и freeze-контроля
стабильных физических QR.

## Новый целевой объем

Для 12 QR-активных игроков прежний минимум `40+` сцен становится нижней
границей, а не комфортным объемом. Целевой V1-пак:

- 72 QR/PvE слота на 10 часов;
- Act 1: 20 слотов;
- Act 2: 22 слота;
- Act 3: 22 слота;
- Final Act: 8 финальных слотов или станций;
- 24 repeatable/always-available слота;
- 48 unique object слотов;
- все QR имеют `physical_presence_required=true`;
- каждый печатный `manual_code` содержит акт, локационный код, номер и
  opaque-хвост.

Такой объем дает запас для групповой игры, неудачных маршрутов, занятых
локаций, одноразовых объектов и игроков, которые активно ищут PvE-контент.

## Контроль однотипности

Сюжетная тема определяется как часть `scenario_title` до первого двоеточия.
Для V1-пакета одна тема может использоваться максимум 2 раза. Это оставляет
место для намеренных парных вариантов, но запрещает массовые повторения вроде
12 одинаковых охот под разными QR.

Валидатор `scripts/pve_authoring.py validate` проверяет этот лимит. Генерацию
иллюстраций для iOS нужно вести по уже дедуплицированной матрице: если тема
уникальна, ей нужен собственный scene/monster asset; если тема повторяется
ровно дважды, допускается осознанное переиспользование ассета или легкая
вариация под акт/локацию.

## Первый фрагмент реализации

Созданы три authoring-файла и runtime compiler:

- `data/authoring/location_codes.csv` - словарь коротких кодов локаций для
  печатных QR;
- `data/authoring/pve_qr_registry.csv` - стабильный реестр физических QR;
- `data/authoring/pve_authoring_matrix.csv` - черновая матрица 72 PvE-сцен.
- `scripts/pve_authoring.py compile-seed` - компилятор `authoring -> data/seed`
  для `qr_objects.csv` и `pve_scenarios.csv`.

`location_codes.csv` исключает no-play зоны и привязывает 3-4 буквенные коды к
`map_nodes`. Резиденции оставлены доступными только как служебные или
master-supervised точки.

`pve_qr_registry.csv` фиксирует то, что нельзя менять после печати:

- `qr_id`;
- `manual_code`;
- `quest_id`;
- `act_id`;
- `loc_code`;
- `location_node_id`;
- `qr_mode`;
- `consumption_rule`;
- подпись и заметку для размещения;
- `take_policy`;
- `print_batch`;
- `status`.

`pve_authoring_matrix.csv` содержит изменяемую начинку квестов:

- `scenario_id`;
- tier;
- scene type;
- primary/secondary stat;
- DC;
- combat profile;
- reward profile;
- черновой hook;
- hidden truth tag;
- success/failure text;
- reward approval policy;
- act unlock policy;
- role-load tag;
- ops checklist tag.

## Правило freeze после печати

После перехода QR из `draft` в `printed` запрещено менять:

- `manual_code`;
- `qr_id`;
- `quest_id`;
- `act_id`;
- `loc_code`;
- `location_node_id`;
- `qr_mode`;
- `consumption_rule`.

Можно менять:

- тексты;
- монстра или combat profile;
- DC в рамках тира;
- награду и approval policy;
- репутационные и NPC-флаги;
- personal/final hooks;
- order/object links;
- polish fields.

## Текущий pipeline

Перед печатью выполняется один и тот же порядок:

1. `uv run python scripts/pve_authoring.py validate`
2. `uv run python scripts/pve_authoring.py compile-seed`
3. `uv run python scripts/pve_authoring.py print-html`
4. `uv run python scripts/pve_authoring.py freeze`
5. `uv run python scripts/pve_authoring.py check-freeze`
6. `uv run pytest tests/test_pve_authoring_tools.py tests/test_seed_contract.py`

Печатный лист: `reports/pve-qr-print/pve72_v1.html`.

Freeze-файл: `data/authoring/freezes/pve72_v1.json`.
