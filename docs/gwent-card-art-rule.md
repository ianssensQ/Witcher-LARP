# Правило арта для карт гвинта

Это рабочий договор для всех следующих карт гвинта в iOS-приложении.

## 1. Имя ассета

Для каждой карты используется строгое имя по `card_id`:

```text
ios/Resources/Assets.xcassets/gwent_card_art_<card_id>.imageset/gwent_card_art_<card_id>.png
```

Пример для `rare_gwent_02`:

```text
ios/Resources/Assets.xcassets/gwent_card_art_rare_gwent_02.imageset/gwent_card_art_rare_gwent_02.png
```

Если такой ассет существует, экран колоды, энциклопедия, рука в бою и карта на столе подхватят его автоматически. Swift-код под новую карту менять не нужно.

## 2. Генерация через OpenRouter

Dry-run без обращения к сети:

```bash
GWENT_DRY_RUN=1 \
GWENT_CARD_ID=rare_gwent_02 \
node scripts/generate-gwent-card-art-openrouter.mjs
```

Реальная генерация:

```bash
WITCHER_ASSET_ENV=.env \
GWENT_CARD_ID=rare_gwent_02 \
node scripts/generate-gwent-card-art-openrouter.mjs
```

Скрипт сам читает метаданные карты из `data/seed/gwent_cards.csv`: название, ряд, тип, силу, эффект и редкость. Если художественное описание нужно уточнить, добавляй:

```bash
GWENT_CARD_SUBJECT="оригинальный северный мечник в темной коже и кольчуге, без узнаваемых эмблем"
```

Можно также переопределять `GWENT_CARD_TITLE`, `GWENT_CARD_SCENE`, `GWENT_CARD_STYLE`, `GWENT_CARD_AVOID`.

## 3. Массовая генерация

Для генерации многих карт используется batch-скрипт с ограниченной параллельностью. Не запускай 200 запросов одновременно: нормальный рабочий диапазон `3-5`.

Проверить план без сети:

```bash
GWENT_BATCH_DRY_RUN=1 \
GWENT_LIMIT=20 \
node scripts/generate-gwent-card-art-batch-openrouter.mjs
```

Сгенерировать первые 20 отсутствующих карт в 4 параллельных запроса:

```bash
WITCHER_ASSET_ENV=.env \
GWENT_LIMIT=20 \
GWENT_CONCURRENCY=4 \
node scripts/generate-gwent-card-art-batch-openrouter.mjs
```

Сгенерировать конкретные карты:

```bash
WITCHER_ASSET_ENV=.env \
GWENT_CARD_IDS=rare_gwent_02,gwent_unit_13 \
GWENT_CONCURRENCY=2 \
node scripts/generate-gwent-card-art-batch-openrouter.mjs
```

Полезные переменные:

- `GWENT_CONCURRENCY` - сколько запросов к OpenRouter держать одновременно, по умолчанию `4`;
- `GWENT_LIMIT` и `GWENT_OFFSET` - размер и смещение пачки;
- `GWENT_CARD_IDS` или `GWENT_CARD_IDS_FILE` - явный список карт;
- `GWENT_SKIP_EXISTING=1` - пропускать готовые ассеты, включено по умолчанию;
- `GWENT_FORCE=1` - перегенерировать даже существующие ассеты;
- `GWENT_RETRIES=2` - число повторов при `429`, `5xx`, timeout и сетевых сбоях;
- `GWENT_DRY_RUN=1` - запустить дочерний генератор без сети и сохранить prompts; для уже существующих ассетов добавляй `GWENT_FORCE=1`;
- `GWENT_BATCH_REPORT=...` - путь к JSON-отчету.

Каждый запуск пишет отчет в `artifacts/openrouter/gwent-card-art-batch-*.json`.

## 4. Обязательное правило кадрирования

Карта в UI прижимает изображение к верху и при необходимости обрезает только низ. Поэтому исходная картинка должна быть подготовлена так:

- голова, волосы, лоб, уши, плечи, важное оружие и верх баннера полностью внутри кадра;
- верхние примерно 18% изображения остаются безопасным атмосферным фоном;
- глаза персонажа находятся около верхней трети, не у самого края;
- если что-то обрезается, это только низ: плащ, пояс, руки, основание предмета;
- текст, водяные знаки, рамки и UI-элементы внутри картинки запрещены.

Если модель всё равно срезала голову или важный верхний силуэт, ассет не принимается: перегенерируй или исправь композицию так, чтобы верх был безопасен, а лишнее уходило вниз.

## 5. Проверка после добавления

После генерации открой экран колоды и боевой стол. На карте должны читаться:

- уникальная картинка;
- сила или тип карты;
- ряд;
- значок основной способности;
- название на темной плашке.

Для технической проверки достаточно собрать iOS:

```bash
xcodebuild -project ios/WitcherLARP.xcodeproj -scheme WitcherLARP -configuration Debug -sdk iphonesimulator -derivedDataPath /private/tmp/WitcherLARPDerivedData -clonedSourcePackagesDirPath /private/tmp/WitcherLARPSourcePackages CODE_SIGNING_ALLOWED=NO build -quiet
```
