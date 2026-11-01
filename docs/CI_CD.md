# CI/CD — сборка и авторелизы

## Обзор

Все сборки — через **GitHub Actions**. Локальная сборка — только для проверки.

| Workflow | Файл | Триггер | Runner | Артефакты |
|----------|------|---------|--------|-----------|
| **CI** | `ci.yml` | push/PR на `main`, `arena/*` | ubuntu, windows | — |
| **Build** | `build.yml` | push на `main`, `arena/*` | `windows-latest` | `DetectiveBlackville-Windows.zip` |
| **Release** | `release.yml` | push тега `v*` | `windows-latest` | GitHub Release + zip + latest.json |

## CI (`ci.yml`)

```yaml
- ruff check src/
- pytest (ubuntu + windows, Python 3.10/3.11)
- проверка синхронизации VERSION == pyproject.toml version
```

Если падает — чини линтер/тесты перед мерджем.

## Build (`build.yml`)

Каждый пуш на рабочие ветки:

1. `actions/checkout`
2. `actions/setup-python` (3.11)
3. `pip install -r requirements.txt pyinstaller`
4. `pyinstaller --onefile --windowed ... src/detective_game/main.py`
5. `Compress-Archive` → `DetectiveBlackville-Windows.zip`
6. `actions/upload-artifact` (retention 30d)

Артефакт скачивается из вкладки Actions → последний Run → Artifacts.

Также собирается `latest.json` с метаданными версии для автообновления клиента.

## Release (`release.yml`)

Триггер: `git push origin v0.1.1` (тег должен начинаться с `v`).

Шаги:

1. Сборка exe как в `build.yml`
2. Генерация чейнджлога из коммитов (`git log v0.1.0..v0.1.1`)
3. Создание GitHub Release через `softprops/action-gh-release`:
   - `tag_name: v0.1.1`
   - `files: DetectiveBlackville-Windows.zip, latest.json`
   - `body: CHANGELOG секция`
4. Обновление `VERSION` в ветке `main` (бот-коммит)

Файлы релиза доступны по:
- `https://github.com/ignatus4405-glitch/detective_game/releases/latest`
- `https://github.com/ignatus4405-glitch/detective_game/releases/download/v0.1.1/DetectiveBlackville-Windows.zip`

## Версионирование

- Источник: файл `VERSION` (например, `0.1.0`)
- Дублируется в `pyproject.toml:project.version` — CI проверяет синхрон
- Тег: `v0.1.0` (с префиксом `v`)
- `src/detective_game/__init__.py:__version__` читает `VERSION` или fallback на package metadata

### Бамп версии

```bash
# вручную
echo "0.2.0" > VERSION
# отредактируй pyproject.toml → version = "0.2.0"
# обнови CHANGELOG.md
git commit -m "chore: bump to 0.2.0"
git tag v0.2.0
git push origin arena/80b28f87-detective-game
git push origin v0.2.0
```

Или workflow `bump-version.yml` (если настроен) — `workflow_dispatch` с инпутом `level: patch|minor|major`.

## Автообновление клиента

Клиент при старте делает:

```
GET https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest
```

Сравнивает `tag_name` с локальной версией. Если новее — баннер.

Для офлайн-сборок можно положить `latest.json` рядом с exe:

```json
{"version":"0.1.0","url":"https://github.com/.../releases/latest","notes":"..."}
```

См. `docs/UPDATE_SYSTEM.md`.

## Секреты

- `GITHUB_TOKEN` — встроенный, права `contents: write` для релизов
- Для подписи exe (опционально) — `WINDOWS_CERT` + `WINDOWS_CERT_PASSWORD` (не настроено в MVP)

## Локальная эмуляция CI

```bash
# линтер
ruff check src/

# тесты
pytest -v

# сборка
pip install pyinstaller
pyinstaller --name DetectiveBlackville --onefile --windowed \
  --add-data "src/detective_game/assets:assets" \
  --add-data "src/detective_game/cases:cases" \
  --hidden-import pygame \
  src/detective_game/main.py

# проверка версии
python -c "import detective_game; print(detective_game.__version__)"
cat VERSION
grep version pyproject.toml
```

## Бейджи

В `README.md`:

```md
![Build](https://img.shields.io/github/actions/workflow/status/ignatus4405-glitch/detective_game/build.yml?style=for-the-badge)
![Release](https://img.shields.io/github/v/release/ignatus4405-glitch/detective_game)
```

Обновляются автоматом после каждого успешного run.

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `VERSION mismatch` | Синхронизируй `VERSION` и `pyproject.toml` |
| `pyinstaller: command not found` | `pip install pyinstaller` |
| Артефакт пустой | Проверь `dist/` — должен быть `DetectiveBlackville.exe` |
| Release не создался | Тег `v*` должен быть запушен, проверь `git ls-remote --tags origin` |
| `GITHUB_TOKEN` нет прав | В Settings → Actions → Workflow permissions → `Read and write` |

