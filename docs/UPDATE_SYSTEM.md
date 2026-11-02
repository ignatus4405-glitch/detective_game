# UPDATE_SYSTEM — автообновление

## Идея

Игра проверяет GitHub Releases при старте, показывает ненавязчивый баннер и умеет
**скачать и установить обновление сама** — как лаунчер Steam/Epic.

## Поток

```
Запуск игры
   │
   ▼
UpdateChecker (daemon thread) ──GET──▶ https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest
   │                                      │
   │◀────── JSON {tag_name, html_url, body, assets} ──────┘
   │
   ▼
Сравнить _parse_version(tag) > _parse_version(__version__)
   │
   ├─ новее ──▶ Баннер: «Доступна vX.Y.Z» → [⬇ Скачать] [Открыть] [×]
   │              └─ после скачивания: [▶ Установить] [Папка]
   │
   ├─ не новее ──▶ Тихо, ничего не показывать
   │
   └─ ошибка сети / лимит GitHub ──▶ «Не удалось проверить: …» (а не «последняя версия»)
```

Проверку можно повторить: **Настройки → Проверить обновления**.
Авто-проверка при старте отключается тумблером **«Авто-проверка обновлений»**.

## Как обновляется с 0.1.28 (архив вместо инсталлятора)

Инсталлятор Inno на чужой машине слишком часто «тихо не срабатывает»: нет прав
на папку, антивирус придержал скачанный Setup, файлы заняты, `/DIR` не совпал с
реальной папкой. Снаружи это выглядит ровно так, как жаловались игроки:
**открылось окно консоли → снова запустилась старая версия → снова предлагает
обновиться**.

Теперь по умолчанию игра обновляет файлы сама:

```
[Скачать] ──▶ DetectiveBlackville-Windows.zip   (SHA256 сверяется)
                    │
                    ▼
        распаковка в %TEMP%\blackville_stage_<версия>\files   (ещё в работающей игре)
                    │  проверки: есть exe, VERSION внутри == ожидаемой
                    ▼
        скрытый помощник (VBS + bat, БЕЗ окна консоли)
                    │  ждёт выхода игры по PID (не дольше ~2 минут)
                    ▼
        xcopy "%BLK_STAGE%\*" "<папка игры>" /E /I /Y /Q /H /R
                    │  синхронизирует VERSION у корня и в _internal
                    ▼
        запускает <папка игры>\DetectiveBlackville.exe
                    │
                    ▼
        при следующем старте: «Обновление установлено — теперь vX»
```

Почему так надёжнее:

- копирование идёт **в ту самую папку, из которой запущена игра** — «поставилось
  в другую папку» физически невозможно;
- не нужен UAC, если папка доступна на запись;
- помощник запускается скрыто (`wscript.exe //B` + `CreateObject("WScript.Shell").Run …, 0`),
  окна консоли больше нет;
- VERSION синхронизируется в обоих местах, поэтому игра не может «не заметить»
  обновление и снова предложить его же;
- если папка защищена (Program Files), остаётся старый путь: Setup.exe с
  запросом прав администратора.

Если что-то не получилось, игрок видит **красный баннер** с кнопками «Журнал» и
«Скачать вручную», а не молчаливое «открылась старая версия».

## Почему раньше «игра не обновлялась» (фикс 0.1.24)

1. **Версия в сборке всегда была `0.1.0`.** `get_version()` искал `VERSION` в
   `<repo>/VERSION`, но PyInstaller-сборка не включает этот файл, а в onedir-сборке
   PyInstaller 6 модули лежат в `<app>/_internal/…`. Итог: только что установленная
   игра продолжала считать себя `0.1.0` и снова предлагала «обновиться» до той же
   версии. Теперь:
   - `VERSION` кладётся в бандл (`--add-data "VERSION;."` → `<app>/_internal/VERSION`);
   - `tools/generate_version_info.py` генерирует `src/detective_game/_build_version.py`
     с `BUILD_VERSION` (вшивается в exe);
   - `get_version()` проверяет все варианты расположения (см. `_version_candidates`),
     затем вшитую версию, затем метаданные pip.
2. **Установка шла не в ту папку.** Инсталлятор ставил копию в
   `%LOCALAPPDATA%\Programs\BlackvilleDetective` (или Program Files), а игрок
   запускал старый exe из распакованного zip → «не обновилось». Теперь апдейтер
   передаёт инсталлятору `/DIR="<папка запущенного exe>"`.
3. **Тихая установка без прав.** Если папка игры недоступна на запись (Program
   Files), `Setup.exe /SILENT` молча падал. Теперь в этом случае запускается
   видимый мастер с запросом UAC (`ShellExecuteW … "runas"`).
4. **Установка поверх работающей игры.** Helper-bat ждёт завершения процесса игры
   (по PID), и только потом запускает инсталлятор. Плюс игра создаёт mutex
   `BlackvilleDetectiveMutex` — его проверяет `AppMutex` в инсталляторе.
5. **Ошибки проверки скрывались.** Любая сетевая ошибка выглядела как «у вас
   последняя версия ✓». Теперь `check_for_updates()` поднимает `UpdateCheckError`,
   а UI показывает причину.

## Реализация

### `src/detective_game/updater.py`

```python
check_for_updates(timeout=6.0) -> dict | None   # raise UpdateCheckError при сбое
download_update(url, progress_callback) -> Path | None
run_installer(path, silent=None, autolaunch=True, install_dir=None, target_version=None) -> bool
install_downloaded_update(path, silent=None, target_version=None) -> bool
consume_update_result() -> {"status": "installed"|"failed", ...} | None

class UpdateChecker:  # daemon thread, не блокирует UI
    start(); start_download(); install(); result; error; downloaded_path
```

- `requests` опционален: если его нет, используется `urllib` (stdlib) — проверка и
  скачивание работают всё равно.
- Таймаут 6 сек, `User-Agent: Blackville-Detective-Game`.
- Без токена — публичный API (60 запросов/час с IP, хватает).

### Установка

```
UpdateChecker.install()
   │
   ├─ папка игры (sys.executable) доступна на запись → /SILENT /DIR /LOG /AUTOLAUNCH=1
   │     └─ helper-bat: ждёт PID игры → Setup.exe /wait → перезапуск игры
   │
   └─ папка недоступна (Program Files) → видимый мастер + UAC
```

Аргументы Inno Setup (`build_installer_args`):

| Аргумент | Зачем |
|---|---|
| `/SILENT /SUPPRESSMSGBOXES` | без окон и диалогов |
| `/CLOSEAPPLICATIONS /NORESTART` | не мешать обновлению файлов; не перезагружать ПК |
| `/AUTOLAUNCH=1` | `[Run] Check: ShouldAutoLaunch` перезапускает игру |
| `/DIR="<папка>"` | ставим **туда, откуда запущена игра** |
| `/LOG="%TEMP%\blackville_update.log"` | журнал для диагностики |

### Результат установки

Перед запуском установщика пишется маркер
`%APPDATA%\BlackvilleDetective\update_state.json`. При следующем старте игра
сравнивает версию и показывает:

- `Обновление установлено — теперь vX.Y.Z`
- `Обновление до vX.Y.Z не установилось (у вас vA.B.C). Журнал: …`

### `src/detective_game/config.py`

```python
GITHUB_REPO = "ignatus4405-glitch/detective_game"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
```

### Версионирование

- `VERSION` — единственный источник (semver), синхронизируется с `pyproject.toml`
- `__version__` = `get_version()`: VERSION-файл → `_build_version.BUILD_VERSION` →
  `importlib.metadata` → `0.1.0`
- Тег = `vX.Y.Z`, сравнение — кортежи интов

## CI

`release.yml` собирает Setup.exe, zip и `latest.json`:

```json
{
  "version": "0.1.0",
  "tag": "v0.1.0",
  "url": "https://github.com/ignatus4405-glitch/detective_game/releases/tag/v0.1.0",
  "notes": "Добавлено дело Тень ячейки №314",
  "published_at": "2026-11-01T12:00:00Z"
}
```

Важно: в PyInstaller-командах должен быть
`--add-data "VERSION;."` (Windows) и шаг `python tools/generate_version_info.py`
до сборки — иначе версия в exe снова станет `0.1.0`.

## Тестирование

```bash
pytest tests/test_updater.py tests/test_version.py -v

# вручную: подменить версию
echo "0.0.1" > VERSION
python -m detective_game  # покажет баннер, если есть релиз новее

# проверить API
curl -s https://api.github.com/repos/ignatus4405-glitch/detective_game/releases/latest | jq .tag_name
```

## Fallback

- Нет сети / лимит GitHub → внятное сообщение, игра работает дальше
- Нет `Setup.exe` в релизе → скачивается zip, игра предлагает распаковать вручную
- Нет прав на папку → мастер установки с UAC
- Пользователь отменил UAC → «Не удалось запустить установщик»

## Если обновление всё же не встало

1. Проверьте `%TEMP%\blackville_update.log` (путь игра пишет при следующем старте).
2. Убедитесь, что запускаете тот exe, куда ставится обновление: с 0.1.24 установщик
   получает `/DIR` текущей папки, но старые версии могли поставить вторую копию в
   `%LOCALAPPDATA%\Programs\BlackvilleDetective`.
3. Переход со старых версий (≤0.1.23) из портативного zip: один раз запустите
   `DetectiveBlackville-Setup-X.Y.Z.exe` вручную и выберите ту же папку.
4. При обновлении из Program Files Windows спросит UAC — без подтверждения
   установка невозможна, игра покажет «Не удалось запустить установщик».

## Roadmap

- [ ] `latest.json` на GitHub Pages для обхода лимитов API
- [ ] Кэш проверки (`settings.json:last_update_check`) — не чаще раза в сутки
- [ ] Принудительные обновления для критических фиксов
- [ ] Проверка SHA256 скачанного установщика
- [ ] Подпись релизов (code signing)
