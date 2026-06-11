# Witcher LARP Core Engine

Документация, продуктовая каноника и TaskOS-план реализации приложения для
10-часовой LARP-игры во вселенной "Ведьмака".

## Карта документов

Текущий канон реализации: 15 человек всего = 13 игроков и 2 NPC-мастера.
Игроки: 4 лорда, 4 чародейки и 5 ведьмаков.

| Документ | Статус | За что отвечает |
| --- | --- | --- |
| [docs/game-mechanics.md](docs/game-mechanics.md) | Канон игровых механик | Роли, статы, PvE/QR, заказы, PvP/Gwent, лорды, чародейки, репутация, NPC, финал и 10-часовой runbook. |
| [docs/PRD.md](docs/PRD.md) | Канон продукта | MVP, пользовательские сценарии, продуктовые ограничения и игровые решения, которые нельзя потерять. |
| [docs/architecture.md](docs/architecture.md) | Канон архитектуры | Данные, backend/frontend/mobile контуры, offline-first, синхронизация и runtime-модули. |
| [docs/roadmap.md](docs/roadmap.md) | Канон порядка работ | Milestone gates, этапы реализации, критерии приемки и порядок проверки готовности. |
| [docs/app-technical-plan-v0.1.md](docs/app-technical-plan-v0.1.md) | Актуальный технический план | Ограничения площадки, production profile, локальный сервер, телефоны, Wi-Fi, панели лордов и fallback-подходы. |
| [tasks.json](tasks.json) | TaskOS source of truth | Статусы задач, зависимости, stage metadata, canonical docs и historical sources. |
| [pyproject.toml](pyproject.toml) | Канон Python/uv окружения | Python-версия, backend/tooling зависимости и dev-группа для тестов. |
| [docs/core-engine-v1.2.md](docs/core-engine-v1.2.md) | Исторический источник | Исходная игровая механика и ранний профиль. Не считать актуальным каноном, если он расходится с документами выше. |
| [docs/kanban.md](docs/kanban.md) | Сгенерированное представление | Человекочитаемый kanban из `tasks.json`. Вручную не редактировать. |
| [docs/task-board.html](docs/task-board.html) | Сгенерированное представление | Локальный HTML-дашборд из `tasks.json`. Вручную не редактировать. |

Если документы расходятся, приоритет у текущих канонических источников:
`docs/game-mechanics.md`, `docs/PRD.md`, `docs/architecture.md`,
`docs/roadmap.md`, `docs/app-technical-plan-v0.1.md` и `tasks.json`.
`docs/core-engine-v1.2.md` использовать только для трассировки исходных идей.

## Python/uv окружение

Python/backend/tooling окружение управляется через `uv`, а не через ручной
`python -m venv` и `pip install`. `uv sync` создает и обновляет локальную
`.venv` по `pyproject.toml` и будущему `uv.lock`.

```powershell
uv sync
uv run python -m backend.witcher_larp
uv run pytest
```

## Актуальный продакшен-сервер

Текущий рабочий запуск админки и игры лордов называем продакшен-сервером:
один FastAPI/SQLite процесс на мастерском ноутбуке, порт `8002`, общая база и
общий API для мастера и лордов.

```powershell
uv sync
uv run python scripts/build_lord_frontend.py
$env:WITCHER_LARP_HOST = "0.0.0.0"
$env:WITCHER_LARP_PORT = "8002"
uv run python -m backend.witcher_larp
```

Актуальные адреса для текущей локальной сети:

- Admin Studio мастера: `http://192.168.0.103:8002/admin`;
- вход лордов: `http://192.168.0.103:8002/lords/login`;
- игровые экраны лордов: `http://192.168.0.103:8002/lords/...`;
- API: `http://192.168.0.103:8002/api/...`.

Если IP мастерского ноутбука изменился, замените только `192.168.0.103` на
новый LAN IPv4. Порт `8002` и единый сервер остаются актуальным запуском.
Dev/Vite-порты вроде `5174` и `5178` не использовать для игры мастера и
лордов: это не продакшен-серверы.

Ключевая раскладка реализации: `backend/witcher_larp/` для FastAPI/SQLite,
`mobile/` для Godot 4 клиента, `backend/witcher_larp/web/` для статических
панелей мастера и лордов, `data/seed/` для CSV, `data/snapshots/` для mobile
snapshot, `data/backups/` для backup/export и `tests/fixtures/` для тестовых
наборов.

## TaskOS loop

`tasks.json` - источник правды по статусам и зависимостям. Сгенерированные
`docs/kanban.md` и `docs/task-board.html` редактировать вручную не нужно.

Полезные команды:

```powershell
uv run python scripts/taskctl.py validate
uv run python scripts/taskctl.py sync
uv run python scripts/taskctl.py ready
uv run python scripts/taskctl.py claim
```

