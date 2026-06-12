# Аудит баланса лордской экономики - 2026-06-12

## Контур проверки

Проверены текущие runtime-правила и seed-данные для лордов: доход, стартовое
золото, recruit stock, вывод войск, нейтральная оборона, anti-snowball, здания
экономики и темп conquest в рамках профиля 4 лорда / 3 сюжетных акта.

## Что исправлено сразу

### 1. Бесплатный вывод stock в active army

До правки `army_reserve_runtime` использовался как накопленный recruit stock, но
операция `reserve_to_active` переводила этот stock в активную армию без оплаты.
Это ломало экономику: Север мог вывести 24 infantry в active army за 0g, после
первого income tick снова получить +24 infantry stock и продолжать войну почти
без денежных затрат.

Теперь `reserve_to_active` списывает `unit.cost * count` и возвращает
`gold_spent` в payload. Проверка после правки на стартовом stock:

| Дом | Отряд | Кол-во | Было золота | Списано | Стало |
| --- | --- | ---: | ---: | ---: | ---: |
| Северный Дозор | infantry T1 | 24 | 80 | 24 | 56 |
| Речные Врата | guard T1 | 14 | 80 | 28 | 52 |
| Лесной Марш | ranged T1 | 14 | 80 | 28 | 52 |
| Холмовая Корона | cavalry T2 | 5 | 80 | 25 | 55 |

### 2. Слишком слабая нейтральная оборона T2/T3

Нейтральные защитники выбирались по `tier <= profile_tier`, но сортировались от
младших tier к старшим. Из-за `LIMIT tier + 1` T2-территория часто получала
только T1-отряды, а T3 почти не использовала T3-защитников.

Теперь нейтральная оборона выбирает старшие доступные tier первой. Ожидаемый
порог после правки:

| Цель | Профиль | Максимальный tier защитника |
| --- | --- | ---: |
| T1 поле | neutral patrol | 1 |
| T2 форт | neutral guard | 2 |
| T3 гора | neutral beast | 3 |

## Остаточные перекосы

### Infantry все еще слишком эффективна

Текущая сила за золото:

| Отряд | Power | Cost | Power/gold |
| --- | ---: | ---: | ---: |
| infantry T1 | 10 | 1 | 10.0 |
| guard T1 | 12 | 2 | 6.0 |
| ranged T1 | 9 | 2 | 4.5 |
| cavalry T2 | 15 | 5 | 3.0 |
| heavy siege T3 | 20 | 8 | 2.5 |
| specialist T3 | 16 | 6 | 2.7 |

Даже после оплаты infantry остается лучшей покупкой по power/gold. Для
вариативности войны стоит поднять infantry cost до `2` или ввести cap размера
одного stack, иначе массовая infantry будет доминировать над guard/ranged.

### Экономика first пока бедная по liquid gold

Если лорд ничего не строит и держит только резиденцию, он получает примерно
`80 + 12 * 33 = 476g` за 3 акта.

Если лорд строит `Рынок` сразу, он выходит примерно на `496g` liquid за 12
тиков: рынок окупается, но поздно.

Если лорд строит `Рынок -> Налоговая палата` как можно раньше и не захватывает
новые земли, он получает примерно `443g` liquid: налоговая почти не работает на
одной резиденции. Это нормально для scaling-здания, но плохо для fantasy "начать
с экономики" без раннего conquest.

## Рекомендованный следующий tuning pass

1. Сделать infantry не универсально лучшей:
   - `unit_infantry_t1.cost = 2`;
   - `unit_guard_t1.cost = 3` только если guard начнет слишком хорошо держать
     оборону после infantry nerf;
   - оставить ranged/cavalry/heavy/specialist без изменения до симуляции боев.

2. Сделать экономику first жизнеспособной без обязательного раннего захвата:
   - `Рынок`: flat income `+8` вместо `+5`;
   - `Налоговая палата`: либо cost `60`, либо territory income bonus `50%`;
   - `Банк`: flat income `+15` вместо `+10`;
   - `Казначейский зал`: flat income `+25` вместо `+20`.

3. Добавить мягкое содержание войск на income tick:
   - считать upkeep только с owned active army + garrisons, не с recruit stock;
   - стартовая формула для playtest: `ceil(domain_army_power / 80)` gold per
     income tick;
   - применять upkeep до anti-snowball или показывать отдельной строкой в
     payload, чтобы мастер видел цену большой армии.

4. После числового tuning pass прогнать минимум 4 архетипа:
   - pure economy до конца Act 1;
   - early infantry conquest;
   - mixed economy -> T2 conquest;
   - raid/order strategy без раннего захвата.

## Проверки

- `uv run pytest tests/test_lord_runtime.py`
- `uv run pytest tests/test_lord_battle_runtime.py`
- `uv run pytest tests/test_lord_panel_contract.py`
- `uv run ruff check backend/witcher_larp/lord_runtime.py backend/witcher_larp/lord_battle_service.py tests/test_lord_runtime.py tests/test_lord_battle_runtime.py`
