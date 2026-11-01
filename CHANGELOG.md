# Changelog

All notable changes to **Detective: Blackville** will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/) + [SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.0...v0.1.1
[0.1.1]: https://github.com/ignatus4405-glitch/detective_game/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.0
[0.1.1]: https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.1
