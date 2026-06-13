# Повторяемые QR/PvE квесты

Статус: мастерская памятка по текущему `data/seed`.

Эти QR/PvE сцены являются общими: после прохождения игрок получает награду в приложении, но не забирает физический QR-знак, лист или карточку. Фраза для игроков:

> После награды не забирайте этот QR-знак или лист. Это общий повторяемый квест: оставьте его на месте для других игроков.

`repeatable_scene` и `always_available_scene` оба относятся к ordinary/anti-idle слою. Если мастер отдельно не выдал физический предмет как награду, сам QR-носитель остается на месте.

| Акт | Тип | QR | Ручной код | Локация | Сцена |
| --- | --- | --- | --- | --- | --- |
| act1 | repeatable_scene | `qr_a1_001` | `QR-A1-TRV-001-K7Q2` | `node_forest_dark` | Дети болотной тропы: Акт 1 / scn_a1_001 |
| act1 | repeatable_scene | `qr_a1_002` | `QR-A1-SNP-002-M4Y8` | `node_village_barn` | Дети болотной тропы: Акт 1 / scn_a1_002 |
| act1 | repeatable_scene | `qr_a1_003` | `QR-A1-OAT-003-P9C3` | `node_field_oats` | Три колокола мертвой часовни: Акт 1 / scn_a1_003 |
| act1 | always_available_scene | `qr_a1_004` | `QR-A1-KTG-004-R2T6` | `node_well_city` | Цена спасенного ребенка: Акт 1 / scn_a1_004 |
| act1 | always_available_scene | `qr_a1_005` | `QR-A1-MAG-005-V8N1` | `node_spanish_magic` | Невеста из колодца: Акт 1 / scn_a1_005 |
| act1 | repeatable_scene | `qr_a1_013` | `QR-A1-VSL-013-Y1M8` | `node_village_east_shed` | Невеста из колодца: Акт 1 / scn_a1_013 |
| act1 | always_available_scene | `qr_a1_014` | `QR-A1-SCI-014-Q6P2` | `node_science_barn` | Невеста из колодца: Акт 1 / scn_a1_014 |
| act1 | repeatable_scene | `qr_a1_015` | `QR-A1-NSD-015-W9A4` | `node_forest_south_garden` | Соль вокруг порога: Акт 1 / scn_a1_015 |
| act2 | repeatable_scene | `qr_a2_013` | `QR-A2-TRV-013-B4K8` | `node_forest_dark` | Дети болотной тропы: Акт 2 / scn_a2_013 |
| act2 | repeatable_scene | `qr_a2_014` | `QR-A2-SNP-014-C7M1` | `node_village_barn` | Дети болотной тропы: Акт 2 / scn_a2_014 |
| act2 | repeatable_scene | `qr_a2_015` | `QR-A2-OAT-015-F2P9` | `node_field_oats` | Камень с лишним именем: Акт 2 / scn_a2_015 |
| act2 | always_available_scene | `qr_a2_016` | `QR-A2-SCI-016-G6R3` | `node_science_barn` | Проклятая невеста и трусливый жених: Акт 2 / scn_a2_016 |
| act2 | always_available_scene | `qr_a2_017` | `QR-A2-MAG-017-H1V5` | `node_spanish_magic` | Невеста из колодца: Акт 2 / scn_a2_017 |
| act2 | repeatable_scene | `qr_a2_027` | `QR-A2-NSD-027-V5P2` | `node_forest_south_garden` | Дети болотной тропы: Акт 2 / scn_a2_027 |
| act2 | always_available_scene | `qr_a2_028` | `QR-A2-ZPR-028-X8S7` | `node_lake_mist` | Дети болотной тропы: Акт 2 / scn_a2_028 |
| act2 | repeatable_scene | `qr_a2_029` | `QR-A2-LNZ-029-B3A6` | `node_lake_south_pond` | Три колокола мертвой часовни: Акт 2 / scn_a2_029 |
| act3 | repeatable_scene | `qr_a3_027` | `QR-A3-TRV-027-B8R2` | `node_forest_dark` | Соль вокруг порога: Акт 3 / scn_a3_027 |
| act3 | repeatable_scene | `qr_a3_028` | `QR-A3-SNP-028-C3T9` | `node_village_barn` | Серебро за молчание: Акт 3 / scn_a3_028 |
| act3 | repeatable_scene | `qr_a3_029` | `QR-A3-OAT-029-D7V4` | `node_field_oats` | Невеста из колодца: Акт 3 / scn_a3_029 |
| act3 | always_available_scene | `qr_a3_030` | `QR-A3-SCI-030-F1X6` | `node_science_barn` | Невеста из колодца: Акт 3 / scn_a3_030 |
| act3 | always_available_scene | `qr_a3_031` | `QR-A3-MAG-031-G9Z1` | `node_spanish_magic` | Камень с лишним именем: Акт 3 / scn_a3_031 |
| act3 | repeatable_scene | `qr_a3_041` | `QR-A3-KTG-041-U3N7` | `node_well_city` | Леший без леса: Акт 3 / scn_a3_041 |
| act3 | always_available_scene | `qr_a3_042` | `QR-A3-TRV-042-X7R2` | `node_forest_dark` | Леший без леса: Акт 3 / scn_a3_042 |
| final_act | repeatable_scene | `qr_fa_001` | `QR-FA-MAG-001-R1K8` | `node_spanish_magic` | Невеста из колодца: Финал / scn_fa_001 |
