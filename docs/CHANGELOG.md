# CHANGELOG — для агентов (внутренний)

> Детальная история для продолжения работы. Релизный чейнджлог — `CHANGELOG.md` в корне.

## [Unreleased]

## [0.1.5] — 2026-11-01

### Fixed
- CI/Release: Generate README теперь не блокирует сборку (continue-on-error)

## [0.1.4] — 2026-11-01

### Fixed
- Исправлен Generate README and hashes в build/release.yml (робастный PowerShell)

## [0.1.3] — 2026-11-01

### Fixed
- **Фикс установщика:** `attempted relative import` → `launcher.py` + robust BASE_DIR (_MEIPASS)
- **SmartScreen:** `tools/version_info.txt` + `tools/app.manifest` + иконка → меньше триггеров Defender; `docs/SMARTSCREEN.md`
- **UX ошибки:** `launcher.py` теперь показывает MessageBox + пишет crash.log вместо 'Failed to execute script'

## [0.1.2] — 2026-11-01

### Fixed
- Release workflow починен (Create release assets делился, sed→awk, Compress-Archive в pwsh)

## [0.1.1] — 2026-11-01

### Fixed
- Починил CI: ruff, build/release установка пакета, PyInstaller
- Добавлены скриншоты меню и карты

### Planned
- Звуки и музыка (pygame.mixer)
- Сетевой hot-seat / WebSocket для команд
- Редактор кейсов GUI
- Локализация en

## [0.1.0] — 2026-11-01

### Added
- Первый релиз: 2 дела («Загадочное похищение», «Тень ячейки №314»)
- Кастомизация детектива: имя + 6 аватаров + 3 бэкграунда
- Карта Блэквила с районами, локации открываются по цепочке улик
- Экран локации: улики + персонажи + допросы
- Блокнот: улики/досье/заметки
- Финальное обвинение с 4 концовками
- Сохранения в %APPDATA%/BlackvilleDetective
- Автообновление через GitHub Releases (баннер)
- CI: ci.yml (ruff+pytest), build.yml (PyInstaller exe), release.yml (релиз на тег)
- Документация: README, ARCHITECTURE, AGENT_GUIDE, CI_CD, BUILD, UPDATE_SYSTEM, CASE_FORMAT
- Тесты: test_game_state, test_data, test_updater, test_save

### Changed
- —

### Fixed
- —

### Technical
- Python 3.10+, Pygame 2.5, PyInstaller 6.0
- Версия в VERSION + pyproject.toml + __init__.py (синхронизируются CI)
- Сборка только на windows-latest (кроссплатформенно — позже)

