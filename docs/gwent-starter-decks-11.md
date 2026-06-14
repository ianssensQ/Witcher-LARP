# Стартовые колоды Гвинта на 11 игроков

Черновик фиксирует только стартовые legal deck blueprints. Прогрессия карт по
актам, наградные пулы, редкие карты и пересчет экономики после merge ветки с
лордами остаются отдельной задачей.

## Принципы

- Это starter templates/copies, а не расход 242 уникальных физических карт из
  `gwent_cards.csv`. Одна и та же карта-шаблон может быть напечатана или
  создана как отдельный стартовый instance для разных игроков.
- Каждая seed-колода содержит 1 leader и 22 unit cards. Простые
  special/weather карты ниже оставлены как optional later suggestions и не
  входят в стартовый `gwent_decks.csv`.
- На старте не выдаются герои, шпионы, `scorch`, `commanders_horn`, нейтральные
  герои 15 силы и полные сильные payoff-пакеты.
- `unit_power` ниже - простая сумма printed strength unit-карт без учета
  погоды, связок, сбора, морали, лидеров и добора.
- Если personal PvP участников окажется меньше 11, используются первые N
  подходящих пакетов, а остальные остаются loaner/training decks.

## Сводка

| Deck ID | Вкус | Leader | Unit cards | Seed specials | Unit power |
| --- | --- | --- | ---: | ---: | ---: |
| `starter_01_northern_fog` | Север, осадный туман | `gwent_leader_foltest_king` | 22 | 0 | 84 |
| `starter_02_northern_clear` | Север, дисциплина рядов | `gwent_leader_wolf` | 22 | 0 | 82 |
| `starter_03_nilfgaard_rain` | Нильфгаард, дождь и гарнизон | `gwent_leader_emhyr_imperial` | 22 | 0 | 83 |
| `starter_04_nilfgaard_scout` | Нильфгаард, разведка руки | `gwent_leader_emhyr_emperor` | 22 | 0 | 83 |
| `starter_05_nilfgaard_white_flame` | Нильфгаард, подавление лидера | `gwent_leader_emhyr_white_flame` | 22 | 0 | 82 |
| `starter_06_scoiatael_frost_a` | Скоя'таэли, морозная засада A | `gwent_leader_francesca_pureblood` | 22 | 0 | 84 |
| `starter_07_scoiatael_frost_b` | Скоя'таэли, морозная засада B | `gwent_leader_francesca_pureblood` | 22 | 0 | 84 |
| `starter_08_scoiatael_frost_c` | Скоя'таэли, лесная смена | `gwent_leader_francesca_pureblood` | 22 | 0 | 84 |
| `starter_09_monsters_destroyer` | Чудовища, болотная стая | `gwent_leader_eredin_destroyer` | 22 | 0 | 81 |
| `starter_10_monsters_weather` | Чудовища, туманная охота | `gwent_leader_eredin_king` | 22 | 0 | 83 |
| `starter_11_monsters_return` | Чудовища, кладбищенский круг | `gwent_leader_eredin_bringer` | 22 | 0 | 86 |

## Deck Blueprints

### `starter_01_northern_fog`

- Leader: `gwent_leader_foltest_king`
- Optional later specials: `gwent_weather_fog`; `gwent_clear_weather`
- Units:

```text
gwent_unit_01
nr_yarpen_zigrin
nr_poor_fucking_infantry_1
nr_poor_fucking_infantry_2
nr_poor_fucking_infantry_3
gwent_unit_03
nr_blue_stripes_commando_2
gwent_unit_02
nr_ves
gwent_unit_08
nr_sheldon_skaggs
gwent_unit_07
nr_sile_de_tansarville
gwent_unit_10
gwent_unit_12
gwent_unit_13
gwent_unit_11
gwent_unit_14
nr_trebuchet_2
gwent_unit_05
nr_kaedweni_siege_expert_2
gwent_unit_09
```

### `starter_02_northern_clear`

- Leader: `gwent_leader_wolf`
- Optional later specials: `gwent_weather_rain`; `gwent_clear_weather`
- Units:

```text
gwent_unit_01
nr_yarpen_zigrin
nr_poor_fucking_infantry_1
nr_poor_fucking_infantry_2
gwent_unit_03
nr_blue_stripes_commando_2
nr_blue_stripes_commando_3
gwent_unit_02
nr_ves
gwent_unit_08
nr_sheldon_skaggs
gwent_unit_07
nr_sile_de_tansarville
gwent_unit_10
gwent_unit_12
nr_crinfrid_reavers_dragon_hunter_2
gwent_unit_13
gwent_unit_11
gwent_unit_14
gwent_unit_05
nr_kaedweni_siege_expert_2
nr_kaedweni_siege_expert_3
```

### `starter_03_nilfgaard_rain`

- Leader: `gwent_leader_emhyr_imperial`
- Optional later specials: `gwent_weather_rain`; `gwent_clear_weather`
- Units:

```text
ng_albrich
ng_assire_var_anahid
ng_cahir
ng_cynthia
ng_etolian_auxiliary_archers_1
ng_fringilla_vigo
ng_impera_brigade_guard_1
ng_impera_brigade_guard_2
ng_morteisen
ng_nausicaa_cavalry_rider_1
ng_nausicaa_cavalry_rider_2
ng_puttkammer
ng_rainfarn
ng_renuald_aep_matsen
ng_rotten_mangonel
ng_siege_engineer_1
ng_siege_engineer_2
ng_sweers
ng_vanhemar
ng_vreemde
ng_young_emissary_1
ng_zerrikanian_fire_scorpion
```

### `starter_04_nilfgaard_scout`

- Leader: `gwent_leader_emhyr_emperor`
- Optional later specials: `gwent_weather_frost`; `neutral_clear_weather_2`
- Units:

```text
ng_albrich
ng_assire_var_anahid
ng_cahir
ng_cynthia
ng_etolian_auxiliary_archers_1
ng_fringilla_vigo
ng_impera_brigade_guard_1
ng_impera_brigade_guard_2
ng_morteisen
ng_nausicaa_cavalry_rider_1
ng_nausicaa_cavalry_rider_2
ng_puttkammer
ng_rainfarn
ng_renuald_aep_matsen
ng_rotten_mangonel
ng_siege_engineer_1
ng_siege_engineer_2
ng_sweers
ng_vanhemar
ng_vreemde
ng_young_emissary_2
ng_zerrikanian_fire_scorpion
```

### `starter_05_nilfgaard_white_flame`

- Leader: `gwent_leader_emhyr_white_flame`
- Optional later specials: `gwent_weather_fog`; `gwent_clear_weather`
- Units:

```text
ng_albrich
ng_assire_var_anahid
ng_cahir
ng_cynthia
ng_fringilla_vigo
ng_impera_brigade_guard_1
ng_impera_brigade_guard_2
ng_impera_brigade_guard_3
ng_morteisen
ng_nausicaa_cavalry_rider_1
ng_nausicaa_cavalry_rider_2
ng_nausicaa_cavalry_rider_3
ng_puttkammer
ng_rainfarn
ng_renuald_aep_matsen
ng_rotten_mangonel
ng_siege_engineer_1
ng_siege_engineer_2
ng_sweers
ng_vanhemar
ng_vreemde
ng_zerrikanian_fire_scorpion
```

### `starter_06_scoiatael_frost_a`

- Leader: `gwent_leader_francesca_pureblood`
- Optional later specials: `gwent_weather_frost`; `gwent_clear_weather`
- Units:

```text
gwent_unit_17
sc_ciaran
sc_dennis_cranmer
sc_dol_blathanna_archer
sc_dol_blathanna_scout_1
sc_dol_blathanna_scout_2
gwent_unit_18
sc_dwarven_skirmisher_2
sc_elven_skirmisher_1
sc_elven_skirmisher_2
sc_havekar_healer_1
sc_havekar_healer_2
sc_havekar_smuggler_1
sc_havekar_smuggler_2
sc_ida_emean
sc_mahakaman_defender_1
sc_mahakaman_defender_2
sc_mahakaman_defender_3
sc_riordain
sc_toruviel
sc_vrihedd_brigade_recruit
sc_vrihedd_brigade_veteran_1
```

### `starter_07_scoiatael_frost_b`

- Leader: `gwent_leader_francesca_pureblood`
- Optional later specials: `gwent_weather_fog`; `neutral_clear_weather_2`
- Units:

```text
gwent_unit_17
sc_ciaran
sc_dennis_cranmer
sc_dol_blathanna_archer
sc_dol_blathanna_scout_2
sc_dol_blathanna_scout_3
sc_dwarven_skirmisher_2
sc_dwarven_skirmisher_3
sc_elven_skirmisher_2
sc_elven_skirmisher_3
sc_havekar_healer_2
sc_havekar_healer_3
sc_havekar_smuggler_2
sc_havekar_smuggler_3
sc_ida_emean
sc_mahakaman_defender_2
sc_mahakaman_defender_3
sc_mahakaman_defender_4
sc_riordain
sc_toruviel
sc_vrihedd_brigade_recruit
sc_vrihedd_brigade_veteran_2
```

### `starter_08_scoiatael_frost_c`

- Leader: `gwent_leader_francesca_pureblood`
- Optional later specials: `gwent_weather_rain`; `gwent_clear_weather`
- Units:

```text
gwent_unit_17
sc_ciaran
sc_dennis_cranmer
sc_dol_blathanna_archer
sc_dol_blathanna_scout_1
sc_dol_blathanna_scout_3
gwent_unit_18
sc_dwarven_skirmisher_3
sc_elven_skirmisher_1
sc_elven_skirmisher_3
sc_havekar_healer_1
sc_havekar_healer_3
sc_havekar_smuggler_1
sc_havekar_smuggler_3
sc_ida_emean
sc_mahakaman_defender_1
sc_mahakaman_defender_4
sc_mahakaman_defender_5
sc_toruviel
sc_vrihedd_brigade_recruit
sc_vrihedd_brigade_veteran_1
sc_riordain
```

### `starter_09_monsters_destroyer`

- Leader: `gwent_leader_eredin_destroyer`
- Optional later specials: `gwent_weather_frost`; `gwent_clear_weather`
- Units:

```text
mo_botchling
mo_celaeno_harpy
mo_cockatrice
mo_earth_elemental
mo_endrega
mo_fiend
mo_fire_elemental
mo_foglet
mo_forktail
mo_frightener
mo_gargoyle
mo_grave_hag
mo_griffin
mo_harpy
mo_ice_giant
mo_plague_maiden
mo_werewolf
mo_wyvern
mo_arachas_1
mo_arachas_2
mo_ghoul_1
mo_ghoul_2
```

### `starter_10_monsters_weather`

- Leader: `gwent_leader_eredin_king`
- Optional later specials: `gwent_weather_fog`; `neutral_clear_weather_2`
- Units:

```text
mo_botchling
mo_celaeno_harpy
mo_cockatrice
mo_earth_elemental
mo_endrega
mo_fiend
mo_fire_elemental
mo_foglet
mo_forktail
mo_frightener
mo_gargoyle
mo_grave_hag
mo_griffin
mo_harpy
mo_ice_giant
mo_plague_maiden
mo_werewolf
mo_wyvern
mo_vampire_bruxa
mo_vampire_ekimmara
gwent_unit_19
gwent_unit_20
```

### `starter_11_monsters_return`

- Leader: `gwent_leader_eredin_bringer`
- Optional later specials: `gwent_weather_rain`; `gwent_clear_weather`
- Units:

```text
mo_botchling
mo_celaeno_harpy
mo_cockatrice
mo_earth_elemental
mo_endrega
mo_fiend
mo_fire_elemental
mo_foglet
mo_forktail
mo_frightener
mo_gargoyle
mo_grave_hag
mo_griffin
mo_harpy
mo_ice_giant
mo_plague_maiden
mo_werewolf
mo_wyvern
mo_crone_brewess
mo_crone_weavess
mo_nekker_3
mo_ghoul_3
```

## Позже перенести в данные

Когда будем делать seed/runtime перенос, лучше не перезаписывать полный
`gwent_decks.csv` вручную. Нужна явная модель instance ownership:

- `card_template_id` ссылается на строку из `gwent_cards.csv`;
- `card_instance_id` уникален для стартовой копии или добытой карты;
- starter deck allocation создает owned collection и active deck;
- редкие и добытые карты входят как отдельные instances с approval/trade locks.
