# UPDATE_SYSTEM — автообновление

## Идея

Игра проверяет GitHub Releases при старте и уведомляет игрока о новой версии. Как в лаунчерах Steam/Epic — ненавязчивый баннер.

## Поток

```
Запуск игры
   │
   ▼
UpdateChecker (daemon thread) ──GET──▶ https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest
   │                                      │
   │◀────── JSON {tag_name, html_url, body} ──────┘
   │
   ▼
Сравнить _parse_version(tag) > _parse_version(__version__)
   │
   ├─ новее ──▶ Зелёный баннер вверху (60px): "Доступна v0.2.0! Нажмите, чтобы открыть"
   │              ├─ Клик по баннеру → webbrowser.open(html_url)
   │              └─ Крестик → dismiss до перезапуска
   │
   └─ не новее ──▶ Тихо, ничего не показывать
```

Проверку можно повторить: **Настройки → Проверить обновления**.

## Реализация

### `src/detective_game/updater.py`

```python
def check_for_updates() -> dict|None:
    GET /releases/latest
    if _parse_version(tag) > _parse_version(current):
        return {"latest": "0.2.0", "current": "0.1.0", "url": "...", "body": "..."}
    return None

class UpdateChecker:
    def start(): # daemon thread
```

- `requests` опционален — если нет, проверка тихо пропускается
- Таймаут 4 сек, `User-Agent: Blackville-Detective-Game`
- Без токена — публичный API (60 запросов/час с IP, хватает)

### `src/detective_game/config.py`

```python
GITHUB_REPO = "ignatus4405-glitch/detective_game"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
```

### `src/detective_game/main.py:draw_update_banner()`

Рендерит баннер если `checker.done and checker.result and not dismissed`.

## Версионирование

- `VERSION` файл — `0.1.0`
- `__version__` читает его или `importlib.metadata`
- Тег = `v0.1.0`

Сравнение версий — кортежи интов: `(0,2,0) > (0,1,0)`.

## CI — создание latest.json

`release.yml` генерирует `latest.json` рядом с exe:

```json
{
  "version": "0.1.0",
  "tag": "v0.1.0",
  "url": "https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.0",
  "notes": "Добавлено дело Тень ячейки №314",
  "published_at": "2026-11-01T12:00:00Z"
}
```

Клиент может проверять и его (если хостишь на своём CDN), но по умолчанию — GitHub API.

## Будущее (roadmap)

- [ ] Автоскачивание и установка (сейчас только уведомление + ссылка)
- [ ] `latest.json` на GitHub Pages для обхода лимитов API
- [ ] Проверка при каждом запуске + раз в сутки (кэш в `settings.json:last_update_check`)
- [ ] Принудительные обновления для критических фиксов
- [ ] Подпись релизов (checksum)

## Тестирование

```bash
# локально без сети — замокать requests
pytest tests/test_updater.py -v

# вручную: подменить версию
echo "0.0.1" > VERSION
python -m detective_game  # должен показать баннер если есть релиз новее

# проверить API
curl -s https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest | jq .tag_name
```

## Fallback

Если GitHub недоступен (офлайн, лимит):

- Проверка тихо падает, игра работает дальше
- Баннер не показывается
- В Настройках можно увидеть «Не удалось проверить» (todo)

