# Нативный iOS-only план реализации

Статус: канонический с 2026-06-09.

Этот документ фиксирует мобильный поворот проекта: production-мобильный клиент
теперь делается как нативное iOS-приложение на SwiftUI. Существующий проект
`mobile/` на Godot остается в репозитории как legacy/reference-материал и не
удаляется, но больше не считается acceptance path для мобильного игрового
клиента.

## Граница продукта

- Production-цель для мобильного клиента: только iPhone.
- Реализация мобильного клиента: SwiftUI-приложение в `ios/`.
- Камера и QR: нативный iOS-слой через AVFoundation.
- Локальное состояние: приватные app-файлы/JSON для snapshot, settings и
  event queue.
- Авторитетный сервер не меняется: локальный FastAPI + SQLite на ноутбуке
  мастера.
- Sync-контракт не меняется: вход по коду игрока, загрузка snapshot,
  офлайн-очередь событий и `POST /api/events/sync`.
- Android выходит из scope текущего production-плана.
- Godot замораживается как legacy/reference, пока пользователь явно не вернет
  его в production-путь.

## Архитектура

```text
iPhone игроков
  нативный SwiftUI iOS-клиент
  код игрока -> snapshot -> офлайн QR/PvE -> event_queue
        |
        | sync в локальном Wi-Fi
        v
Ноутбук мастера
  FastAPI server
  SQLite authoritative state
  CSV importer / snapshot exporter
  master web panel
        |
        | браузер по локальному Wi-Fi
        v
4 ноутбука лордов
  lord web panels
```

## Первый вертикальный срез

Первый iOS milestone намеренно узкий:

1. Запуск приложения и скрытая/локальная настройка server URL.
2. Ввод `player_code`.
3. Вызов `POST /api/auth/player-code`.
4. Загрузка `GET /api/content/snapshot`.
5. Локальное сохранение snapshot и сессии.
6. Скан QR камерой или ручной ввод QR ID.
7. Подтверждение физического присутствия.
8. Один офлайн PvE-result с одним app-generated d20.
9. Сохранение результата в локальную `event_queue`.
10. Sync очереди через `POST /api/events/sync` при возврате в Wi-Fi.

Визуальная полировка не должна обгонять этот срез. Нарисованные фоны, bitmap
слои и крупные игровые состояния становятся ценными после того, как вход,
snapshot, QR/manual, офлайн-сохранение события и sync работают на реальном
iPhone.

## Структура репозитория

- `ios/README.md` - заметки по сборке и handoff нативного iOS-клиента.
- `ios/project.yml` - XcodeGen-спецификация проекта для Mac build host.
- `ios/WitcherLARP/` - SwiftUI source.
- `ios/Resources/` - Info.plist и asset catalogs.
- `mobile/` - legacy Godot-проект, сохранен как reference и больше не является
  production acceptance path.

## Acceptance gate

Stage 2B mobile acceptance теперь требует real iPhone smoke:

- install и launch через Xcode/free provisioning, TestFlight или другой явно
  выбранный iOS distribution path;
- local network permission работает против master laptop server;
- вход по коду игрока работает;
- snapshot загружается и переживает restart приложения;
- камера сканирует физический QR;
- manual QR-ID fallback работает;
- один офлайн PvE event переживает restart;
- event sync retry работает после возврата в локальный Wi-Fi.

Отсутствие Android evidence больше не блокирует acceptance. Отсутствие iPhone
evidence блокирует mobile gate.
