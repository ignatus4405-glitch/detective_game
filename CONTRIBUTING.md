# Contributing — как контрибьютить (для агентов и людей)

Спасибо что помогаете расследованию в Блэквиле!

## Быстрый старт

```bash
git clone https://github.com/ignatus4405-glitch/detective_game.git
cd detective_game
pip install -e .[dev]
pytest -q
python -m detective_game
```

## Workflow

1. Создай ветку от `main`: `git checkout -b feat/my-feature`
2. Пиши код + тесты
3. Обнови `docs/CHANGELOG.md` (секция Unreleased)
4. Запусти проверки:

```bash
ruff check src/
pytest -q
python -c "import detective_game; print(detective_game.__version__)"
```

5. Коммит в стиле Conventional Commits:

```
feat: добавил дело "Ночной поезд"
fix: поправил открытие локации при leads_to
docs: обновил CASE_FORMAT
chore: bump version to 0.1.1
```

6. Пуш → CI соберёт exe. При зелёном CI — PR в `main`.

## Добавление дела

См. `docs/CASE_FORMAT.md` и `docs/AGENT_GUIDE.md` (чек-лист).

Коротко: добавь `src/detective_game/cases/my_case.json` → перезапусти → проверь что дело открывается.

## Версионирование

- `VERSION` — единственный источник. Бампни его при фиче/фиксе.
- Синхронизируй `pyproject.toml:project.version` с `VERSION`.
- Тег `vX.Y.Z` триггерит релиз (см. `docs/CI_CD.md`).

## Стиль

- Python 3.10+, ruff (line 100)
- Комментарии на русском (как в коде), доки — двуязычно
- Цвета — из `config.py`, не хардкодь

## Куда писать

- Issues: https://github.com/ignatus4405-glitch/detective_game/issues
- Discussions: идеи новых дел

Удачи, детектив!
