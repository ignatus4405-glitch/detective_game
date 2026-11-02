# Changelog

All notable changes to **Detective: Blackville** will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/) + [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.17] — 2026-11-02

### Fixed
- **Меню по центру в экранном режиме:** `draw_menu`, `draw_city_background`, `draw_notifications` теперь используют реальный размер окна `W,H = screen.get_size()` вместо фиксированных 1280×720. Панель 720×520 всегда центрируется (`W//2-360, H//2-260`), туман и сетка покрывают весь экран в полноэкранном/бордерлес режиме.

### Added
- **Генерация имени в кастомизации:** добавлены пулы `AVATAR_NAME_POOLS` (6 вариантов на аватар) и `get_random_name_for_avatar()`. При клике на портрет имя автоматически генерируется для этого образа; добавлена кнопка **🎲** рядом с полем ввода — случайное имя для выбранного фото с уведомлением.
- **Кнопки с ярлычками:** `Button` теперь поддерживает `tooltip` с автопозиционированием над кнопкой (тёмная плашка + золотая рамка + стрелочка). Добавлены тултипы: «Продолжить сохранённую игру», «Начать новую историю», «Экран, звук и обновления», «Внешность и прошлое детектива», «Выйти…», «← Назад», «Сохранить…». Для «Прошлого» — тултип при наведении на каждую кнопку показывает её бонус; для поля ввода — подсказка про 🎲.

### Changed
- **Убран ценник в задании:** в `draw_case_select` кнопка теперь только **«ВЗЯТЬ ДЕЛО»** без ` — price`. При наведении цена показывается маленьким тултипом над кнопкой.


## [0.1.16] — 2026-11-02

### Fixed
- **Настройки:** убрана дублирующая нижняя кнопка «← В МЕНЮ» (перекрывала «Применить»/«Сбросить прогресс», см. скрин 0.1.15). Навигация остаётся через верхнюю «← НАЗАД» в шапке.


## [0.1.15] — 2026-11-02

### Fixed
- **Критический краш настроек:** `draw_settings` использовал `mouse/pressed` до объявления → `UnboundLocalError: cannot access local variable 'mouse'` при открытии настроек (см. скрин). Перемещён `mouse = pygame.mouse.get_pos()` в начало функции.
- **Автообновление из игры:** `updater._find_download_url` теперь с приоритетом ищет `DetectiveBlackville-Setup-*.exe` (инсталлятор Inno Setup) вместо `Full.zip`; `download_update` теперь корректно качает `.exe` и `.zip`; добавлены `run_installer()` / `install_downloaded_update()` — запуск инсталлятора с автозакрытием игры; баннер на главном экране и панель в настройках показывают прогресс, «✓ Скачано» и кнопку **▶ УСТАНОВИТЬ** (запускает инсталлятор и выходит из игры), а также «Папка»; баннер больше не скрывается на главном экране и корректно обрабатывает `Setup.exe`.


## [0.1.14] — 2026-11-02

### Fixed
- **Ярлык не открывался:** `:` в `MyAppName` приводил к невалидному имени `Детектив: Блэквил — Код Города.lnk` → Windows обрезал до `Детектив` без `.lnk` и показывал «Каким образом вы хотите открыть этот файл?». Теперь введён `MyAppLnkName="Детектив Блэквил"` без запрещённых символов для всех `[Icons]` (`{group}`, `{autodesktop}`, `{userdesktop}`), ярлыки создаются с правильной иконкой и `WorkingDir`.



## [0.1.13] — 2026-11-02

### Added
- Кнопка «← НАЗАД» в шапке настроек и внизу по центру — всегда видна, возвращает в меню; исправлено положение предыдущей кнопки (была за пределами окна `right.bottom+12`)

### Fixed
- **Шрифт в настройках:** убран дубль лейблов (`Dropdown` label `Разрешение`/`Экран` → `""`), ручные лейблы `РАЗРЕШЕНИЕ ЭКРАНА`/`ЭКРАН (МОНИТОР)`/`РЕЖИМ ОКНА` теперь `get_font(11,bold)` с `COLOR_TEXT` вместо `10/COLOR_TEXT_DIM`, читаемость улучшена
- **Ярлык при установке:** `desktopicon` теперь `Flags: checkedonce` (включён по умолчанию), добавлены `WorkingDir` и дублирующий `userdesktop` ярлык — ярлык гарантированно создаётся и в per-user режиме
- **Разработчик:** `Blackville Studio` → `Sams_studio128` в `installer.iss` (`MyAppPublisher`/`VersionInfo*`), `pyproject.toml`, `version_info.txt`, `__init__.py`, `main.py`, `app.manifest`, `SMARTSCREEN.md`

## [0.1.12] — 2026-11-02

### Fixed
- **Критический фикс путей установщика:** `LicenseFile=..\LICENSE`, `SetupIconFile=..\src\…\icon.ico`, `Source: ..\dist\…` в `tools/installer.iss` — теперь ISCC находит файлы при запуске из `tools/` и корректно собирает `DetectiveBlackville-Setup-v0.1.12.exe`; ранее искал в `tools/dist` и падал с `cannot find path`

## [0.1.11] — 2026-11-02

### Fixed
- **Фикс пути установщика:** `OutputDir=..\Output` в `tools/installer.iss` (корректно относительно `tools/`), убран невалидный `cache` у `Inno-Setup-Action`, добавлен `continue-on-error` и verbose `ISCC path` — инсталлятор теперь точно в `Output/DetectiveBlackville-Setup-v0.1.11.exe`

## [0.1.10] — 2026-11-02

### Fixed
- **Инсталлятор собирается надёжно:** заменён `choco install innosetup` на `Minionguyjpro/Inno-Setup-Action@v1.2.2` (кэш, проверенный путь `ISCC.exe`), теперь `Build Windows installer` стабильно находит ISCC и публикует `DetectiveBlackville-Setup-v0.1.10.exe` в артефактах и релизе

## [0.1.9] — 2026-11-02

### Fixed
- **Установщик теперь попадает в релиз:** исправлен `OutputDir` в `tools/installer.iss` (`{#SourcePath}\..\Output` → корень репозитория) и шаблоны артефактов в `build.yml`/`release.yml` (`Output/… + tools/Output/…`), добавлена унификация пути + `continue-on-error` и PowerShell-совместимый `choco` (без `||`), инсталлятор теперь гарантированно публикуется как `DetectiveBlackville-Setup-v0.1.9.exe` в артефактах и релизе

## [0.1.8] — 2026-11-02

### Added
- **Полноценный установщик Windows:** GitHub Actions теперь автоматически собирает `DetectiveBlackville-Setup-v0.1.8.exe` через Inno Setup 6 (`choco install innosetup`), включает в Release как отдельный ассет; `build.yml` публикует его как артефакт `DetectiveBlackville-Installer`
- Установщик: установка в `{autopf}\BlackvilleDetective`, ярлыки в меню Пуск и на рабочий стол (опционально), реестр `HKCU\Software\BlackvilleDetective` (InstallPath/Version), корректный деинсталлятор, `AppMutex` против двойного запуска, modern wizard, иконка, поддержка x64

### Changed
- `tools/installer.iss` версия по умолчанию обновлена до `0.1.8`, улучшена документация сборки

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
- 6 нуар-портретов детективов (Рейн, Мара, Коул, Вивиан, Шедоу, Лора) — реальные изображения вместо цветных заглушек
- Bundled шрифт DejaVuSans с поддержкой кириллицы — исправлено отображение 'КАСТОМИЗАЦИЯ', 'ИМЯ ДЕТЕКТИВА' и т.д.

### Fixed
- Исправлена вёрстка экрана кастомизации: поля не перекрываются, подсказки видны, кнопки 'ПРОШЛОЕ' внутри панели, описание аватара в рамке
- Синхронизированы координаты кликов аватаров/бэкграундов с новой сеткой 140x140
- Кэш шрифтов и изображений для производительности

## [0.1.5] — 2026-11-01

### Fixed
- CI: Generate README and hashes теперь continue-on-error + robust PowerShell (Test-Path) — чинит падение сборки на Windows

## [0.1.4] — 2026-11-01

### Fixed
- Починил шаг Generate README and hashes в CI/Release (был `cat` без проверки → падение сборки) → теперь robust PowerShell с Test-Path

## [0.1.3] — 2026-11-01

### Fixed
- **Критический фикс установщика:** исправил `Failed to execute script 'main' — attempted relative import` → теперь собирается через `launcher.py` (absolute import) + `--paths src` + `--collect-all detective_game`
- **SmartScreen:** добавлены `version_info.txt` (CompanyName/ProductVersion) + `app.manifest` (asInvoker) + иконка + SHA256 — снижает ложные срабатывания Защитника; инструкция в `docs/SMARTSCREEN.md` и `dist/README.txt`
- **Улучшен handler ошибок:** вместо краша показывается дружелюбное окно (tkinter/MessageBox) + `crash.log` рядом с exe
- Конфиг путей теперь учитывает `sys._MEIPASS` для PyInstaller onefile

## [0.1.2] — 2026-11-01

### Fixed
- Исправлен Release workflow: разделил создание latest.json/notes/zip, починил shell (bash vs pwsh)

## [0.1.1] — 2026-11-01

### Fixed
- Починил CI: настроен ruff, исправлены импорты, добавлена установка пакета в build/release
- Build теперь проходит на Windows (PyInstaller + тесты)

## [0.1.0] — 2026-11-01

### Added
- Initial release — two playable cases:
  - **Загадочное похищение** (chess kid disappearance, 10 clues, 5 suspects)
  - **Тень ячейки №314** (bank heist, 8 clues)
- Detective customization (name, 6 avatars, 3 backgrounds with gameplay bonuses)
- Interactive city map with district visualization and clue-gated progression
- Location screen with evidence collection and character interrogations
- Notebook (clues / dossier / timeline notes)
- Accusation & multiple endings (rank S–F)
- Save/load system (cross-platform, %APPDATA% on Windows)
- Auto-update checker via GitHub Releases with in-game banner
- GitHub Actions: CI (lint+test), Build (Windows exe), Release (tag → Release)
- Full documentation for agents and players

[Unreleased]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.17...HEAD
[0.1.17]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.16...v0.1.17
[0.1.16]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.15...v0.1.16
[0.1.15]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.14...v0.1.15
[0.1.14]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.12...v0.1.13
[0.1.13]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.0...v0.1.1
 https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.0
[0.1.1]: https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.1
