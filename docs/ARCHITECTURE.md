# ARCHITECTURE — архитектура игры

> Версия документа: 0.1.0 — 2026-11-01

## 1. Высокоуровневый обзор

Игра — **однооконное Pygame-приложение** с конечным автоматом экранов. Все экраны рендерятся в одном `Game` классе (`src/detective_game/main.py`), переключение через `self.screen_name`.

```
┌─────────┐    ┌─────────────────┐    ┌──────────────┐    ┌──────────┐
│  Splash │───▶│ Customization  │───▶│ Case Select  │───▶│ City Map │◀─┐
└─────────┘    └─────────────────┘    └──────────────┘    └──────────┘  │
                                                              │ ◀───────┘
                                    ┌───────────────┐         │
                                    │   Location    │─────────┘
                                    │ (clues+chars) │
                                    └──────┬────────┘
                                           ▼
                                    ┌──────────────┐    ┌────────────┐
                                    │   Dialogue   │    │  Notebook  │
                                    └──────────────┘    │(clues/dossier/notes)
                                                        └─────┬──────┘
                                                              ▼
                                                       ┌────────────┐
                                                       │ Accusation │──▶ Ending
                                                       └────────────┘
```

Все данные кейса — **декларативные JSON** (или Python-дикт в `data.py:BUILTIN_CASES`). Логика прогрессии — «улики открывают локации».

## 2. Модули

| Файл | Ответственность |
|------|-----------------|
| `config.py` | Константы окна, цвета (нуар-палитра), пути, GitHub URLs |
| `game_state.py` | `DetectiveProfile`, `GameState` (dataclass), списки `AVATARS`/`BACKGROUNDS` |
| `save_system.py` | Кроссплатформенные сохранения в `APPDATA`/`.local/share` — JSON |
| `updater.py` | `check_for_updates()` → GitHub API, `UpdateChecker` (thread) |
| `data.py` | `BUILTIN_CASES`, `load_case()`, `list_cases()`, геттеры |
| `synth.py` | Синтез музыки и эффектов в WAV на чистом stdlib (5 тем, 9 sfx) |
| `audio.py` | `AudioEngine`: темы по экранам, кэш `<save>/music`, фоновая генерация, `play_voice()` |
| `puzzles.py` | `Puzzle` — логика четырёх головоломок, `for_clue()`, `difficulty_label()` |
| `ui/puzzle_view.py` | Экран головоломки: отрисовка и обработка кликов/клавиш |
| `ui/widgets.py` | Примитивы: `Button`, `TextInput`, `draw_panel`, `draw_avatar`, `draw_map_pin` |
| `main.py` | **God-class** `Game` — все экраны, ввод, рендер, навигация |

> **Почему God-class?** Для MVP проще один файл, чем десяток экранов. При росте >1500 строк — декомпозировать `main.py` на `screens/menu.py`, `screens/map.py` и т.д. (см. Roadmap).

## 3. Состояние (State)

```python
@dataclass GameState:
  detective: DetectiveProfile
  current_case_id: str|None
  visited_locations: set[str]
  collected_clues: set[str]
  interrogated: set[str]
  case_time_minutes: int
  game_day: int
  case_state: "not_started"|"in_progress"|"accusation"|"finished"
  accusation_result: str|None
  accusation_correct: bool|None
```

- `get_available_locations()` — вычисляет доступные локации: `initial=True` + те, куда ведёт собранная улика (`clue.leads_to`)
- Время — просто счётчик минут, растёт на +10 при сборе улики
- Сохранение — `save_game(state)` пишет `APPDATA/BlackvilleDetective/savegame.json` при каждом действии

## 4. Кейсы — формат данных

Каждый кейс — dict/JSON с ключами:

```json
{
  "id": "missing_chess",
  "title": "...", "subtitle": "...", "difficulty": "★★☆", "duration": "60–90 мин",
  "description": "кратко для карточки",
  "intro": "завязка при старте",
  "locations": [{"id":"park","name":"...","type":"crime","x":300,"y":200,"district":"Север","desc":"...","initial":true}],
  "clues": [{"id":"clue_camera","title":"...","desc":"...","location":"park","importance":"high","leads_to":["photo_lab"]}],
  "characters": [{"id":"elena","name":"...","role":"...","location":"apartment_morozov","bio":"...","portrait_color":[120,80,80],"dialogue":[{"q":"...","a":"..."}]}],
  "suspects": [{"id":"finch","name":"...","motive":"...","evidence":["clue_camera"],"is_culprit":true}],
  "endings": {"finch": {"success":true,"title":"...","text":"...","rank":"S"}}
}
```

Добавление нового дела = новый файл `src/detective_game/cases/my_case.json` → автоматически появится в `list_cases()`.

См. `docs/CASE_FORMAT.md`.

## 5. Рендер-пайплайн

Каждый кадр:

1. `screen.fill(COLOR_BG)` + `draw_city_background()` (сетка улиц)
2. `Game.draw()` — switch по `screen_name`, каждый `draw_*` рисует панели через `draw_panel()` с тенью
3. `draw_notifications()` — всплывашки 4 сек
4. `draw_update_banner()` — зелёный баннер если есть апдейт

Шрифты — `pygame.font.SysFont("Segoe UI", size)` (fallback `None`). Все координаты в абсолютных пикселях под 1280×720.

## 6. Автообновление

- `UpdateChecker` стартует в `Game.__init__` в отдельном daemon-thread
- `check_for_updates()` делает `GET /repos/{GITHUB_REPO}/releases/latest`, сравнивает `tag_name` с `__version__` через `_parse_version()`
- Если новее — баннер с `webbrowser.open(banner["url"])`
- Ручная проверка — кнопка в Настройках

Версионирование — семвер в `VERSION` (корень) и `pyproject.toml:project.version`. CI синхронизирует их.

## 7. Сборка (CI/CD)

См. `docs/CI_CD.md` — три workflow:

- `ci.yml` — lint+test на каждый push
- `build.yml` — PyInstaller на `windows-latest` → артефакт `DetectiveBlackville-Windows.zip`
- `release.yml` — на тег `v*` → GitHub Release + `latest.json` для лаунчера

Локальная сборка — `tools/build.ps1` / `build.sh` → `dist/DetectiveBlackville.exe`.

## 8. Долги и Roadmap

- [ ] Вынести экраны из `main.py` в `screens/` (когда файл >1500 строк)
- [ ] Добавить звуки (pygame.mixer) — шаги, джаз, дождь
- [ ] Сетевая игра — синхронизация через WebSocket (для команд как в KodGoroda)
- [ ] Редактор дел — GUI для создания кейсов без JSON
- [ ] Локализация (ru/en) — сейчас только ru
- [ ] Анимации и катсцены — пока статичные панели

## 9. Диаграмма зависимостей

```
main.py ──┬──► config.py
          ├──► game_state.py ──► config.py
          ├──► save_system.py ──► config.py + game_state.py
          ├──► updater.py ──► config.py + __init__.py
          ├──► data.py ──► config.py
          └──► ui/widgets.py ──► config.py
```

Нет циклических зависимостей. Тесты мокают `pygame`.

