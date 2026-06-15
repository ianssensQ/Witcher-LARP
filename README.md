# Witcher LARP Control App

Локальное приложение управления однодневной LARP-игрой по мотивам "Ведьмака".
Проект не рассчитан на интернет во время игры: мастерский ноутбук поднимает
один FastAPI/SQLite-сервер в локальной Wi-Fi сети, лорды заходят в браузерные
панели, игроки с телефонами синхронизируются с сервером в online-зоне, а
критичные сбои закрываются бумажным fallback и последующим восстановлением.

Текущий рабочий профиль: 15 человек всего, из них 13 игровых ролей и 2
NPC-мастера. Игроки: 4 лорда, 4 чародейки и 5 ведьмаков. Игра делится на 3
сюжетных акта и финальный акт, использует репутацию Good/Evil, PvE QR/manual
сцены, заказы, личный PvP/Gwent, стратегию лордов и master-operated conflict
resolution.

## Быстрый запуск игры

Production-запуск для мастера и лордов - это один локальный процесс на
мастерском ноутбуке:

```bash
uv sync
cd prototypes/stage2b-v2
npm ci
cd ../..
uv run python scripts/build_lord_frontend.py
uv run python -m backend.witcher_larp
```

По умолчанию сервер стартует на `0.0.0.0:8002`, создает/использует SQLite базу
`data/game.db` и раздает Admin Studio, лордский frontend и API из одного
процесса.

Актуальные адреса для текущей локальной сети:

- Admin Studio мастера: `http://192.168.68.118:8002/admin`
- вход лордов: `http://192.168.68.118:8002/lords/login`
- игровые экраны лордов: `http://192.168.68.118:8002/lords/...`
- API/healthcheck: `http://192.168.68.118:8002/health`

Если IP мастерского ноутбука изменился, меняйте только host
`192.168.68.118` на новый LAN IPv4. Порт `8002` и единый сервер остаются теми
же. Dev/Vite-порты вроде `5174`, `5178` и похожих нужны только для визуальной
разработки и не считаются production-серверами для игры.

На Windows PowerShell переменные окружения для ручного переопределения выглядят
так:

```powershell
$env:WITCHER_LARP_HOST = "0.0.0.0"
$env:WITCHER_LARP_PORT = "8002"
$env:WITCHER_LARP_DB = "data/game.db"
uv run python -m backend.witcher_larp
```

На macOS/Linux:

```bash
WITCHER_LARP_HOST=0.0.0.0 WITCHER_LARP_PORT=8002 uv run python -m backend.witcher_larp
```

## Что открыть после старта

1. Откройте `/health` и убедитесь, что сервер отвечает `status: ok`.
2. Откройте `/admin` на мастерском ноутбуке.
3. В Admin Studio импортируйте seed/content pack из `data/seed/`, если база
   пустая или контент был изменен.
4. Проверьте, что лорды заходят через `/lords/login` и после role-token попадают
   на `/lords/home`.
5. Для телефонов используйте тот же server URL с портом `8002`; в iOS-клиенте
   адрес меняется только если сменился LAN IP мастерского ноутбука.

## Как устроен проект

| Путь | Что внутри |
| --- | --- |
| `backend/witcher_larp/` | FastAPI app, SQLite доступ, API, rule engines, импорт CSV, snapshot/export, review, backup, PvP, PvE, лордская стратегия. |
| `backend/witcher_larp/web/admin/` | Статическая Admin Studio, которую раздает FastAPI по `/admin`. |
| `prototypes/stage2b-v2/` | Текущий React/Vite frontend для лордского browser flow: `/lords/login`, `/lords/home` и панели лордов. Для production он собирается в `dist/` и раздается FastAPI. |
| `ios/` | Текущий нативный SwiftUI-клиент для iPhone игроков. |
| `mobile/` | Legacy/reference Godot 4 mobile client. Оставлен для истории, тестов и возможного переиспользования, но текущая iPhone-линия живет в `ios/`. |
| `data/seed/` | Редактируемый runtime seed pack: CSV и JSON с игроками, ролями, QR, PvE, картами, территориями, рынками и правилами. |
| `data/snapshots/` | Сгенерированные mobile snapshots. |
| `data/backups/` | Бэкапы SQLite/export перед актами, финалом и ручными контрольными точками. |
| `tests/` | Backend, API, seed, runtime, iOS scaffold и regression-тесты. |
| `scripts/` | Локальные утилиты: TaskOS wrapper, сборка лордского frontend, iOS smoke/gate scripts, генераторы ассетов и контента. |
| `docs/` | Продуктовая и техническая каноника, roadmap, UI workflow, audits и сгенерированные TaskOS views. |
| `tools/taskos/` | Vendored TaskOS, поэтому `scripts/taskctl.py` работает без глобальной установки TaskOS. |

## Backend и API

Окружение Python управляется через `uv`. Не создавайте `.venv` вручную и не
ставьте зависимости напрямую через `pip`, если нет отдельной причины.

```bash
uv sync
uv run python -m backend.witcher_larp
```

Полезные backend endpoints:

- `GET /health` - проверка сервера и SQLite.
- `POST /api/auth/player-code` - вход игрока по player code.
- `POST /api/auth/role-token` - вход лорда или NPC-мастера по role token.
- `GET /api/content/snapshot` - player-scoped snapshot для телефона.
- `POST /api/events/sync` - синхронизация очереди событий с телефона.
- `POST /api/master/content/import` - импорт seed/content pack через master API.
- `GET /api/lords/{lord_id}/state` - состояние лордской панели.

Swagger остается developer diagnostics. Для реальной игры мастер использует
Admin Studio, лорды - browser UI, игроки - мобильный клиент.

## Лордский frontend

В корне репозитория нет npm-проекта. Node-зависимости нужны только в
`prototypes/stage2b-v2/`.

Первичная установка:

```bash
cd prototypes/stage2b-v2
npm ci
```

Визуальная разработка:

```bash
cd prototypes/stage2b-v2
npm run dev
```

Для production-сервера после изменений лордского UI:

```bash
uv run python scripts/build_lord_frontend.py
uv run python -m backend.witcher_larp
```

FastAPI ожидает собранный `prototypes/stage2b-v2/dist/index.html`. Если `dist`
не собран, `/lords/...` вернет 503 с подсказкой запустить
`scripts/build_lord_frontend.py`.

## iOS клиент

Текущий production mobile path для iPhone игроков находится в `ios/`.

```bash
open ios/WitcherLARP.xcodeproj
```

В Xcode выберите схему `WitcherLARP`, симулятор или подключенный iPhone и
нажмите Run. В нормальном flow игрок вводит player code, скачивает snapshot с
локального сервера, играет с локальным состоянием и отправляет event queue при
возвращении в Wi-Fi.

Перед выдачей телефонов полезно прогнать HTTP smoke против того же сервера:

```bash
scripts/ios_no_pvp_http_smoke.py --server http://192.168.68.118:8002
```

Более подробные iOS команды и release gates описаны в `ios/README.md`.

## Legacy Godot client

`mobile/` - Godot 4 project. Его можно открыть через Godot Project Manager:

```text
mobile/project.godot
```

Он полезен как reference по offline-first flow, QR/manual сценам,
`event_queue`, snapshot persistence и старым Android/iOS export smoke. Для
текущей iPhone-приемки смотрите `ios/`.

## Данные и контент

Рабочий seed pack лежит в `data/seed/`. Это не тестовая копия, а редактируемый
источник runtime-данных для импорта:

- `players.csv`, `player_codes.csv`, `role_tokens.csv` - роли и входы.
- `qr_objects.csv`, `pve_scenarios.csv`, `rewards.csv` - QR/PvE контент.
- `domains.csv`, `territories.csv`, `map_nodes.csv`, `map_edges.csv` - лорды и
  стратегическая карта.
- `gwent_cards.csv`, `gwent_decks.csv`, `gwent_rules.csv` - личный Gwent/PvP.
- `acts.csv`, `act_unlock_codes.csv`, `auto_timers.csv` - акты и таймеры.

После изменения seed-данных импортируйте их через Admin Studio или master API.
Сгенерированные snapshots и backups хранятся отдельно в `data/snapshots/` и
`data/backups/`.

## Проверки

Основные проверки:

```bash
uv run pytest
uv run ruff check .
```

Точечные проверки:

```bash
uv run pytest tests/test_fastapi_contract.py -q
uv run pytest tests/test_lord_panel_contract.py -q
uv run pytest tests/test_ios_project_scaffold.py -q
```

iOS build/smoke команды лежат в `ios/README.md`. Для лордского frontend
проверяйте TypeScript/Vite через:

```bash
cd prototypes/stage2b-v2
npm run build
```

Если Vite build в Codex/Windows падает с `spawn EPERM` от esbuild, это обычно
ограничение filesystem sandbox, а не ошибка приложения. В таком случае
перезапустите ту же команду с escalated sandbox permissions.

## TaskOS

`tasks.json` - источник правды по статусам и зависимостям задач.
`docs/active-tasks.md`, `docs/kanban.md` и `docs/task-board.html` - сгенерированные
представления, вручную их не редактируют.

Полезные команды:

```bash
uv run python scripts/taskctl.py validate
uv run python scripts/taskctl.py sync
uv run python scripts/taskctl.py ready
uv run python scripts/taskctl.py claim
uv run python scripts/taskctl.py claim TASK-123
uv run python scripts/taskctl.py done TASK-123 --summary "..." --check "..."
uv run python scripts/taskctl.py block TASK-123 --reason "..."
uv run python scripts/taskctl.py release TASK-123 --reason "..."
```

## Документы, где искать правду

| Документ | Для чего |
| --- | --- |
| `docs/app-technical-plan-v0.1.md` | Актуальная техническая каноника, production profile, запуск на площадке, ограничения Wi-Fi/телефонов/серверов. |
| `docs/PRD.md` | MVP, пользовательские сценарии и продуктовые ограничения. |
| `docs/architecture.md` | Архитектура данных, backend/frontend/mobile контуры и stage gates. |
| `docs/roadmap.md` | Порядок реализации и milestone gates. |
| `docs/game-mechanics.md` | Уточненные игровые механики. |
| `docs/core-engine-v1.2.md` | Исторический исходник. Не менять и не считать главным, если он расходится с текущими документами. |
| `docs/ui/frontend-ux-ui-screen-workflow.md` | Правила визуальной работы над frontend screens, особенно лордскими экранами. |

Если документы расходятся, для запуска приложения сначала ориентируйтесь на
этот README и `docs/app-technical-plan-v0.1.md`, а для очередности работ - на
`tasks.json`.
