# AGENT_GUIDE — руководство для AI-агента (и человека)

> Это **главный чек-лист** для продолжения работы. Прочитай его полностью перед любыми изменениями.

## 0. Контекст

- **Задача:** сделать Windows-игру-детектив по мотивам https://kodgoroda.games/#game (нуар 80-х, карта, улики, допросы)
- **Репо:** https://github.com/ignatus4405-glitch/detective_game
- **Ветка сессии:** `arena/80b28f87-detective-game` (рабочая)
- **Стек:** Python 3.10+ + Pygame, сборка PyInstaller → exe, CI на GitHub Actions
- **Версия:** смотри `VERSION` и `src/detective_game/__init__.py`

## 1. Где что лежит

| Путь | Что |
|------|-----|
| `VERSION` | Единственный источник версии (semver). Меняется вручную + ботом при релизе |
| `pyproject.toml` | Зависимости. Синхронизируй `project.version` с `VERSION` |
| `src/detective_game/main.py` | **Главный файл** — вся логика экранов. Начинай отсюда |
| `src/detective_game/config.py` | Цвета, размеры окна, пути, GitHub URLs |
| `src/detective_game/game_state.py` | Модели данных детектива и состояния |
| `src/detective_game/data.py` | Кейсы (дела) — `BUILTIN_CASES` + загрузка из `cases/*.json` |
| `src/detective_game/ui/widgets.py` | UI-примитивы |
| `src/detective_game/save_system.py` | Сохранения |
| `src/detective_game/updater.py` | Проверка обновлений |
| `tests/` | Тесты (pytest) |
| `docs/` | Документация (этот файл, ARCHITECTURE.md, CI_CD.md, BUILD.md, CASE_FORMAT.md) |
| `.github/workflows/` | CI/CD |
| `tools/` | Скрипты сборки |

## 2. Как запустить локально

```bash
# 1. Установить зависимости
pip install -r requirements.txt
# или
pip install -e .[dev]

# 2. Запустить игру
python -m detective_game
# 3. Запустить тесты
pytest -v
# 4. Линт
ruff check src/
```

Если `pygame` не ставится — `pip install pygame --pre` или проверь Python 3.10+.

Сохранения лежат в:
- Windows: `%APPDATA%\BlackvilleDetective\`
- Linux (sandbox): `~/.local/share/BlackvilleDetective/`
- macOS: `~/Library/Application Support/BlackvilleDetective/`

Удали: `rm -rf ~/.local/share/BlackvilleDetective` (Linux) или удали файл `savegame.json`.

## 3. Чек-лист после КАЖДОГО изменения

> **Документируй каждый шаг** — это требование ТЗ.

1. **Отредактируй код** (или добавь новый кейс в `src/detective_game/cases/`)
2. **Обнови `docs/CHANGELOG.md`** (или `CHANGELOG.md` для релизов) — добавь запись в `## [Unreleased]`
3. **Запусти тесты:** `pytest -q` — должны быть зелёными
4. **Проверь версию:** если менялась логика — бампни `VERSION` (patch для фиксов, minor для фич, major для ломающих)
5. **Синхронизируй** `pyproject.toml:project.version` с `VERSION` (CI проверяет)
6. **Коммит** с conventional message: `feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`
7. **Пуш** — `git push origin arena/80b28f87-detective-game` → CI сам соберёт exe (см. `.github/workflows/build.yml`)

```bash
pytest -q
# обнови CHANGELOG
git add -A
git commit -m "feat: добавил новое дело '...'"
git push origin arena/80b28f87-detective-game
```

## 4. Как добавить новое дело (кейс)

1. Скопируй `src/detective_game/cases/example.json` (или возьми структуру из `data.py:BUILTIN_CASES[0]`)
2. Заполни `locations`, `clues`, `characters`, `suspects`, `endings` (см. `docs/CASE_FORMAT.md`)
3. Положи в `src/detective_game/cases/my_case.json`
4. Запусти игру → дело появится в выборе автоматически
5. Протестируй: пройди его от начала до обвинения

## 5. Как бампнуть версию и выпустить релиз

Автоматика (рекомендуется):

```bash
# 1. Обнови VERSION
echo "0.2.0" > VERSION
# 2. Синхронизируй pyproject.toml
# 3. Обнови CHANGELOG.md — перенеси Unreleased в новую секцию
# 4. Коммит + тег + пуш
git add VERSION pyproject.toml CHANGELOG.md docs/CHANGELOG.md
git commit -m "chore: bump version to 0.2.0"
git tag v0.2.0
git push origin arena/80b28f87-detective-game
git push origin v0.2.0   # ← триггерит release.yml → создаст GitHub Release
```

Вручную: создать Release на GitHub с тегом `vX.Y.Z`, приложить `DetectiveBlackville-Windows.zip`.

Подробнее: `docs/UPDATE_SYSTEM.md` и `docs/CI_CD.md`.

## 6. CI/CD — что происходит автоматом

| Workflow | Триггер | Что делает |
|----------|---------|------------|
| `ci.yml` | push/PR на main/arena/* | ruff + pytest (ubuntu+windows) |
| `build.yml` | push на main/arena/* | PyInstaller → `DetectiveBlackville-Windows.zip` как артефакт |
| `release.yml` | push тега `v*` | Сборка exe + создание GitHub Release + `latest.json` |

Артефакты хранятся 30 дней. Бейджи в README отражают статус.

Если CI падает — смотри логи в Actions, чаще всего `pyproject.toml version != VERSION`.

## 7. Частые задачи

| Задача | Куда идти |
|--------|-----------|
| Поменять цвета/шрифты | `config.py` |
| Добавить аватар | `game_state.py:AVATARS` + нарисуй логику в `main.py:draw_avatar` |
| Добавить фон детектива | `game_state.py:BACKGROUNDS` + `Game.draw_customization()` |
| Поменять карту | `data.py` — координаты `x,y` в `locations` (0..1280,0..720) |
| Добавить улику | `data.py:clues` — не забудь `leads_to` для открытия локаций |
| Добавить персонажа | `data.py:characters` — `dialogue` массив |
| Поменять концовки | `data.py:endings` |
| Добавить звук | `assets/sounds/` + `pygame.mixer` в `main.py` |
| Починить автообновление | `updater.py` + `config.py:GITHUB_REPO` |

## 8. Правила коммитов

- Используй **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- Одно изменение — один коммит (не смешивай фичу и рефактор)
- Пиши на русском или английском, но консистентно
- В каждом коммите обновляй `docs/CHANGELOG.md` если менялась логика

## 9. Дебаг

- **Игра не стартует:** `python -m detective_game --help` → проверь `pygame` установлен, Python 3.10+
- **Чёрный экран:** проверь `WINDOW_WIDTH/HEIGHT` в `config.py`, видеокарта поддерживает 1280×720
- **Не сохраняются:** проверь права на `get_save_dir()` — в sandbox это `~/.local/share/BlackvilleDetective`
- **Не грузится кейс:** валидный JSON? `python -m json.tool src/detective_game/cases/my_case.json`
- **CI не собирается:** `pyinstaller` требует `pygame` — проверь `requirements.txt` и `pyproject.toml` синхронизированы

## 10. Контакты и ссылки

- Репо: https://github.com/ignatus4405-glitch/detective_game
- Оригинал вдохновения: https://kodgoroda.games
- Релизы: https://github.com/ignatus4405-glitch/detective_game/releases
- Issues: https://github.com/ignatus4405-glitch/detective_game/issues

> **После каждого изменения запусти автосборку (пуш) и проверь бейдж в README.** Это требование ТЗ — «после внесения изменений запускай автосборку».

Удачи, детектив! 🕵️
