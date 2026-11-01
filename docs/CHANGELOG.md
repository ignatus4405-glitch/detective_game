# CHANGELOG — для агентов (внутренний)

> Детальная история для продолжения работы. Релизный чейнджлог — `CHANGELOG.md` в корне.

## [Unreleased]

## [0.1.10] — 2026-11-02

### Fixed
- Переход на `Minionguyjpro/Inno-Setup-Action@v1.2.2` с кэшем для стабильной сборки установщика

## [0.1.9] — 2026-11-02

### Fixed
- Исправлен OutputDir в installer.iss (теперь `..\Output` в корень) + обработка обоих путей в workflows, choco без `||`, установщик появляется в релизе

## [0.1.8] — 2026-11-02

### Added
- Установщик теперь собирается на CI: `choco install innosetup` → `iscc` → `Output/DetectiveBlackville-Setup-v0.1.8.exe` в каждом Build/Release, публикуется как артефакт `DetectiveBlackville-Installer` и файл релиза

### Changed
- Bump 0.1.7 → 0.1.8 для включающего CI-инсталлятор

## [0.1.7] — 2026-11-02

### Added
- **Устанавливаемая игра:** Inno Setup инсталлятор `DetectiveBlackville-Setup-v0.1.7.exe` → Program Files/BlackvilleDetective, ярлыки в меню Пуск/рабочий стол, корректный uninstall, реестр версии, AppMutex
- **Обновление из приложения:** кнопка «Проверить обновления» в настройках + баннер с прогресс-баром, скачивание `DetectiveBlackville-Windows.zip` прямо из игры (stream с прогрессом), открытие папки загрузок по клику, без браузера
- **Настройки экрана:** выбор разрешения (HD/QHD/FullHD/ультраширокий + авто-детект десктопа), выбор монитора при multi-monitor (`pygame.display.get_num_displays`), режимы окна — оконный / полный экран / без рамки (borderless fullscreen), применение без перезапуска
- **Кастомные кнопки:** градиентные noir-кнопки с hover-анимацией, свечением, тенью, состояниями primary/secondary/danger/success, иконками
- **Улучшение отображения картинок:** `draw_avatar` теперь aspect-fill (cover) вместо stretch — сохранение пропорций, фокус на лицо, скруглённые углы, золотая рамка + внешнее свечение для выбранного
- **Новые виджеты настроек:** Dropdown (выпадающий список), Toggle (переключатель), Slider (ползунок громкости) — всё в фирменном нуар-стиле

### Fixed
- Исправлено обрезание подсказки «Острый глаз...» в кастомизации — теперь прижата к низу панели с отступом 28px, не выходит за окно
- Миграция старых настроек `fullscreen` bool → `window_mode` enum для совместимости сохранений
- Папка сохранений и версия теперь внутри панели настроек, а не перекрывают контролы

## [0.1.6] — 2026-11-02

### Added
- Портреты 6 детективов (512px, noir, оптимизированы ~200KB)
- Шрифт DejaVuSans bundled (кириллица)

### Fixed
- Вёрстка кастомизации: панель 620px, сетка 140x140, отступы, подсказки
- Отображение: кэш, fallback SysFont, проверка glyph

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

