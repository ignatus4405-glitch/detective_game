# ДЕТЕКТИВ: БЛЭКВИЛ — Код Города

> **Нуар-расследование в стиле KodGoroda.games — теперь на Windows.**

Вы не смотрите детектив. Вы — его главный герой. Погрузитесь в атмосферу вымышленного американского городка Блэквил 80-х, исследуйте более 10 локаций, допрашивайте свидетелей, собирайте улики и выберите, кого обвинить. Каждое решение — шаг к правде или в пропасть.

![Game Badge](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows)
![Version](https://img.shields.io/github/v/release/ignatus4405-glitch/detective_game?style=for-the-badge)
![Build](https://img.shields.io/github/actions/workflow/status/ignatus4405-glitch/detective_game/build.yml?style=for-the-badge&label=СБОРКА)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python)

---

## 🎮 Геймплей — как в [KodGoroda.games](https://kodgoroda.games/#game)

| Механика KodGoroda | Реализация в игре |
|---|---|
| **Интерактивная карта 1000+ локаций** | Стилизованная карта Блэквила с районами (Центр, Порт, Север, Холмы). Локации открываются по цепочке улик — как в оригинале |
| **Поиск улик** | 10 улик на дело. Каждая открывает новые места/персонажей |
| **Допросы** | Диалоговые ветки с бонусами от бэкграунда детектива |
| **Блокнот/Досье** | Журнал улик, подозреваемые, хронология |
| **Финальное обвинение** | Выбор виновного → уникальные концовки с рангом S/A/B/C/D |
| **Командная игра 1–6 чел.** | Hot-seat / стрим-режим — обсуждайте версии за одним ПК (сетевая игра — в roadmap) |

### Дела в релизе

1. **Загадочное похищение** (★★☆, 60–90 мин) — исчезновение 9-летнего шахматиста Артёма. Труп фотографа, плёнка, серый плащ.
2. **Тень ячейки №314** (★★★, 45–70 мин) — ограбление банка за 10 минут тишины. Три подозреваемых, у всех был код.

---

## 🕵️ Кастомизация детектива

При первом запуске:

- **Имя** — вводится в текстовом поле, используется в диалогах
- **Аватар** — 6 образов (Рейн, Мара, Коул, Вивиан, Шедоу, Лора) — цветовые аватары в нуар-стиле
- **Прошлое** — влияет на диалоги:
  - `Частный сыщик` — улица доверяет
  - `Бывший коп` — видит детали в полицейских протоколах
  - `Репортёр` — разговорит бармена и свидетелей

Все сохраняется в `%APPDATA%/BlackvilleDetective/detective.json` и переживает переустановку.

---

## 🚀 Быстрый старт

### Windows (готовая сборка)

1. Скачайте `Detective-Blackville-vX.Y.Z-Windows.zip` из [Releases](https://github.com/ignatus4405-glitch/detective_game/releases)
2. Распакуйте → запустите `DetectiveBlackville.exe`
3. При первом запуске создайте детектива → выберите дело

### Из исходников (любая ОС)

```bash
git clone https://github.com/ignatus4405-glitch/detective_game.git
cd detective_game
pip install -r requirements.txt
# или pip install -e .[dev]

# Запуск
python -m detective_game
# или
detective-game
```

**Требования:** Python 3.10+, pygame 2.5+, Windows 10/11 (сборка), Linux/macOS — для разработки.

---

## 🔄 Автообновление

Игра сама проверяет GitHub Releases при старте:

```python
GET https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest
```

- Если `latest.tag_name > VERSION` — показывается зелёный баннер с кнопкой «Открыть релизы»
- Уведомление не блокирует игру, можно закрыть крестиком
- Ручная проверка — **Настройки → Проверить обновления**

Версия хранится в файле `VERSION` в корне репо и в `src/detective_game/__init__.py`. CI автоматически бампает `VERSION` и создаёт релиз при пуше тега `v*`.

Подробнее: [docs/UPDATE_SYSTEM.md](docs/UPDATE_SYSTEM.md)

---

## 🛠️ Сборка

### Локально в exe (Windows)

```bash
pip install pyinstaller
pyinstaller --name DetectiveBlackville --onefile --windowed --add-data "src/detective_game/assets;assets" --add-data "src/detective_game/cases;cases" src/detective_game/main.py
# exe появится в dist/
```

Скрипт: `tools/build.ps1` / `tools/build.sh` (см. [docs/BUILD.md](docs/BUILD.md))

### CI — GitHub Actions

Каждый пуш запускает:

1. **Lint & Test** (`ci.yml`) — ruff + pytest на ubuntu/windows
2. **Build** (`build.yml`) — сборка exe на `windows-latest`, загрузка артефакта
3. **Release** (`release.yml`) — при пуше тега `v*` → создание Release с `DetectiveBlackville-Windows.zip` + `latest.json`

Бейджи сборки отражают статус последнего workflow.

Подробнее: [docs/CI_CD.md](docs/CI_CD.md)

---

## 📁 Структура проекта

```
detective_game/
├── VERSION                # текущая версия (semver)
├── pyproject.toml         # зависимости и метаданные
├── src/detective_game/
│   ├── main.py            # главный цикл и все экраны
│   ├── config.py          # константы, цвета, пути
│   ├── game_state.py      # DetectiveProfile, GameState, AVATARS
│   ├── save_system.py     # сохранения в %APPDATA%/BlackvilleDetective
│   ├── updater.py         # проверка GitHub Releases
│   ├── data.py            # загрузка кейсов (JSON)
│   ├── assets/            # изображения, звуки, шрифты
│   ├── cases/             # JSON-описания дел (расширяемо)
│   └── ui/widgets.py      # кнопки, панели, аватарки
├── tests/                 # pytest
├── docs/                  # документация для агентов
├── tools/                 # скрипты сборки, генерации ассетов
└── .github/workflows/     # CI/CD
```

Расширение игры — добавить новый `cases/case_id.json` и он появится в выборе дел (см. [docs/CASE_FORMAT.md](docs/CASE_FORMAT.md)).

---

## 🤖 Для AI-агентов

> Этот репозиторий документирован так, чтобы любой агент мог продолжить работу без контекста.

Обязательно прочитайте:

1. **[docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md)** — чек-лист для продолжения, где что лежит, как запускать автосборку
2. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — архитектура экранов и стейт-машины
3. **[docs/CHANGELOG.md](docs/CHANGELOG.md)** — история изменений (ведётся вручную + ботом)
4. **[CHANGELOG.md](CHANGELOG.md)** — релизный чейнджлог (генерируется из коммитов)

После **каждого изменения** запускайте:

```bash
pytest -q
python -m detective_game --smoke-test  # если реализовано
```

и пушьте — CI сам соберёт exe. См. [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 Лицензия

MIT — см. [LICENSE](LICENSE). Ассеты-заглушки — CC0. Образ Блэквила вдохновлён KodGoroda.games, но все тексты и сюжеты оригинальны.

---

## 🙏 Благодарности

- [KodGoroda.games](https://kodgoroda.games) — за идею живой карты и атмосферы нуара 80-х
- Pygame community
- Всем детективам, кто тестировал ранние билды

> *«Город не спит. Он ждёт, когда ты ошибёшься.»* — надпись на столе детектива Рейна

