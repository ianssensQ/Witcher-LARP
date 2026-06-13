# Prompt: Gwent progression scaling after lord branch merge

Используй этот prompt в новом чате после слияния ветки с лордами.

Нужно пересчитать прогрессию личных карт Гвинта под фактический игровой состав
на 11 игроков. Не переписывай `docs/core-engine-v1.2.md` без отдельной просьбы.
Сначала прочитай:

- `AGENTS.md`;
- `docs/game-mechanics.md`, особенно разделы про личный Гвинт, редкость,
  rewards, trade и лордскую конверсию карт;
- `docs/PRD.md`;
- `docs/architecture.md`;
- `docs/app-technical-plan-v0.1.md`;
- `docs/roadmap.md`;
- `data/seed/gwent_cards.csv`;
- `data/seed/gwent_decks.csv`;
- `data/seed/gwent_rules.csv`;
- `data/seed/rewards.csv`;
- `data/seed/rarity_rules.csv`.

Цель: сохранить предложенную модель "слабый равный старт -> актовая
прогрессия -> редкие карты с visibility/counterplay", но пересчитать ее под
11 игроков и текущий lord runtime после merge.

Разбери отдельно:

1. Ролевой состав 11 игроков: сколько лордов, ведьмаков, чародеек и NPC-мастеров
   реально участвуют в personal PvP.
2. Нужны ли физические уникальные карты, цифровые card instances или печатные
   starter duplicates. При 11 игроках legal deck по 22 unit cards на каждого
   нельзя наивно собрать из 198 уникальных строк без решения про копии/шаблоны.
3. Стартовый набор: сколько starter decks нужно, как сделать их равными по
   power level, какие эффекты запрещены на старте.
4. Актовые пулы Act 1/2/3: какие card tiers открываются, сколько card upgrades
   получает активный игрок за акт, какие награды идут через QR, trophy exchange,
   lord orders, NPC deals, trade и PvP stakes.
5. Rare Gwent cards: оставить ли cap `6 всего, максимум 2 на акт` или изменить
   его для 11 игроков; для любого изменения указать counterplay и review cost.
6. PvP volume: проверить 11-player match load, `pvp_tables`, 3 challenge tokens
   per act, max 1 active challenge и soft cap 20/25 минут.
7. Data changes: какие поля/таблицы нужны для `owned collection`, starter
   allocation, card draft, pending approval, active deck lock и deck validation.
8. Test plan: какие seed validation, snapshot, PvP, trade/reward approval и UI
   checks должны подтвердить новую модель.

Выход нового чата:

- краткая рекомендация по модели starter duplicates vs digital instances;
- таблица стартовых deck skeletons для 11-player профиля;
- таблица актовых card pools и источников получения;
- список конкретных docs/CSV/code changes;
- риски и tuning knobs для rehearsal.
