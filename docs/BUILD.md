# BUILD — как собрать игру

## Требования

- Python 3.10+
- Windows 10/11 для финального exe (на Linux/macOS соберётся, но exe будет для текущей ОС)
- 2GB RAM, 500MB диска

## Установка зависимостей

```bash
pip install -r requirements.txt
pip install pyinstaller  # только для сборки exe
# или dev-набор
pip install -e .[dev]
```

## Запуск из исходников

```bash
python -m detective_game
# или установленный скрипт
detective-game
```

Первый запуск создаст папку сохранений и попросит кастомизировать детектива.

## Сборка exe (Windows)

### Вариант 1 — скрипт

```powershell
# PowerShell (Windows)
.\tools\build.ps1
# или
tools\build.bat
```

```bash
# Bash (Linux/macOS, для теста)
bash tools/build.sh
```

Скрипт делает:

```bash
pyinstaller \
  --name DetectiveBlackville \
  --onefile \
  --windowed \
  --icon src/detective_game/assets/images/icon.ico \
  --add-data "src/detective_game/assets:detective_game/assets" \
  --add-data "src/detective_game/cases:detective_game/cases" \
  --hidden-import pygame \
  --collect-all pygame \
  src/detective_game/main.py
```

Результат: `dist/DetectiveBlackville.exe` (~40–60 MB).

### Вариант 2 — вручную

```bash
pip install pyinstaller

# Windows (PowerShell) — разделитель ;
pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm \
  --add-data "src/detective_game/assets;detective_game/assets" \
  --add-data "src/detective_game/cases;detective_game/cases" \
  --hidden-import pygame \
  src/detective_game/main.py

# Linux/macOS — разделитель :
pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm \
  --add-data "src/detective_game/assets:detective_game/assets" \
  --add-data "src/detective_game/cases:detective_game/cases" \
  src/detective_game/main.py
```

> **Важно для автообновления и версии:** перед сборкой запускайте
> `python tools/generate_version_info.py`, добавьте `--add-data "VERSION;."`
> (Windows) / `"VERSION:."` (Linux) и собирайте `--onedir` из `launcher.py`
> (как в `.github/workflows/release.yml`). Без этого exe не найдёт версию и
> будет всегда считать себя `0.1.0` — игра станет бесконечно предлагать
> обновление.

### Проверка

```bash
ls -lh dist/
./dist/DetectiveBlackville  # Linux/macOS
dist\DetectiveBlackville.exe  # Windows
```

Запустится окно 1280×720.

## Сборка дистрибутива (zip)

```bash
# после pyinstaller
cd dist
zip -r DetectiveBlackville-v0.1.0-Windows.zip DetectiveBlackville.exe README.txt
# README.txt — короткая инструкция для игрока
```

Шаблон `README.txt` генерируется скриптом `tools/make_readme.py`.

## Инсталлятор (опционально)

Если нужен инсталлятор:

- **Inno Setup** (Windows) — скрипт `tools/installer.iss` → `DetectiveBlackville-Setup.exe`
- Установи Inno Setup → `iscc tools/installer.iss`

## Кроссплатформенно

- Linux: `pyinstaller --onefile` даст бинарь для Linux (не exe)
- macOS: даст `.app` (нужен `py2app` или `pyinstaller --windowed` + `codesign`)
- Для универсального релиза — три джоба в `build.yml` (windows/mac/linux)

## Отладка сборки

| Ошибка | Решение |
|--------|---------|
| `ModuleNotFoundError: pygame` | `pip install pygame` перед сборкой |
| `Failed to execute script` | Собери без `--windowed`, увидишь traceback в консоли |
| `assets not found` | Проверь `--add-data` пути, в коде используй `importlib.resources` или `Path(__file__).parent / "assets"` |
| Большой exe ( >100MB ) | Убедись, что не пакуешь `.venv`, добавь `--exclude-module` для лишнего |
| Антивирус ругается | Подпиши exe (сертификат) или добавь в исключения — ложное срабатывание PyInstaller |

## CI-сборка

Не собирай вручную для релиза — пушь тег, CI сделает:

```bash
echo "0.1.1" > VERSION
# обнови pyproject.toml
git commit -am "chore: bump 0.1.1"
git tag v0.1.1
git push origin arena/80b28f87-detective-game
git push origin v0.1.1
# → через 5 мин в Releases появится zip
```

См. `docs/CI_CD.md`.

