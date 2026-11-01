# CASE_FORMAT — формат дел (кейсов)

Дело — JSON-файл в `src/detective_game/cases/<id>.json` (или встроенный dict в `data.py:BUILTIN_CASES`).

## Скелет

```json
{
  "id": "my_case",
  "title": "Короткое название",
  "subtitle": "Подзаголовок (1 строка)",
  "difficulty": "★★☆",
  "duration": "60–90 мин",
  "price": "990 ₽",
  "description": "Кратко для карточки выбора (2 предложения)",
  "intro": "Завязка — показывается при старте дела (3-4 предложения)",
  "recommended_time": 90,
  "locations": [...],
  "clues": [...],
  "characters": [...],
  "suspects": [...],
  "endings": {...}
}
```

## Локации (`locations`)

```json
{
  "id": "park",
  "name": "Парк Роузвуд",
  "type": "crime",
  "x": 300, "y": 200,
  "district": "Север",
  "desc": "Описание для экрана локации",
  "initial": true
}
```

- `type`: `hub`/`police`/`crime`/`bar`/`apartment`/`bank`/`vault`/`public`/`shop`/`warehouse`/`port`/`mansion`/`office` — влияет на цвет пина
- `x,y`: координаты 0..1280,0..720 (как на карте)
- `district`: для легенды (Центр, Порт, Запад, Север, Холмы, Юг, Восток)
- `initial`: если `true` — доступна с начала, иначе открывается когда собрана улика с `leads_to` содержащим её `id`

## Улики (`clues`)

```json
{
  "id": "clue_camera",
  "title": "Камера Ланского",
  "desc": "Длинное описание улики",
  "location": "park",
  "importance": "high",
  "leads_to": ["photo_lab"]
}
```

- `location`: id локации где лежит
- `importance`: `high`/`medium` — цвет индикатора
- `leads_to`: массив локаций которые откроются после сбора

## Персонажи (`characters`)

```json
{
  "id": "elena",
  "name": "Елена Морозова",
  "role": "Мать Артёма",
  "location": "apartment_morozov",
  "bio": "Краткая био (1 предложение)",
  "portrait_color": [120,80,80],
  "dialogue": [
    {"q": "Вопрос детектива", "a": "Ответ персонажа"}
  ]
}
```

- `portrait_color`: RGB для заглушки-аватара
- `dialogue`: массив реплик, показываются по очереди при допросе

## Подозреваемые (`suspects`)

```json
{
  "id": "finch",
  "name": "Эдвард Финч",
  "motive": "Короткий мотив",
  "evidence": ["clue_camera","clue_ticket"],
  "is_culprit": true
}
```

- `evidence`: список id улик, которые указывают на него (для подсказки в досье)
- `is_culprit`: `true` только у одного — правильный ответ

## Концовки (`endings`)

Ключ = `id` подозреваемого:

```json
{
  "finch": {"success": true, "title": "Правосудие", "text": "Длинный текст финала (3-5 предложений)", "rank": "S"},
  "roma_sus": {"success": false, "title": "Ошибка", "text": "...", "rank": "D"}
}
```

- `rank`: S/A/B/C/D/F — показывается на экране финала

## Пример готового файла

Сохрани как `src/detective_game/cases/tutorial.json` и перезапусти игру — дело появится.

См. встроенные примеры: `src/detective_game/data.py`.

## Лимиты (MVP)

- До 20 локаций, 15 улик, 8 персонажей, 5 подозреваемых — больше не тестировалось
- Координаты `x,y` не должны налезать друг на друга (<60px дистанция)
- ID должны быть уникальны и без пробелов

