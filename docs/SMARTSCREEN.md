# SmartScreen и Защитник Windows — как убрать уведомление

> **Почему Windows ругается?** Любой неподписанный `.exe` без репутации (мало скачиваний) вызывает SmartScreen: *«Система Windows защитила ваш компьютер»* или *«Неизвестный издатель»*. Это нормально для PyInstaller-сборок и не означает вирус. Исправления ниже делают предупреждение реже и дают пользователю понятную инструкцию.

## Что мы уже сделали в сборке (технические фиксы)

1. **Используем `launcher.py` вместо прямого `main.py`**
   - Было: `pyinstaller src/detective_game/main.py` → relative import ломается (`attempted relative import...`) и exe даже не стартует
   - Стало: `launcher.py` (корень, absolute import) → `from detective_game.main import main` — корректный запуск

2. **Метаданные версии** (`--version-file`)
   - `tools/version_info.txt` → CompanyName=Blackville Studio, ProductName, FileVersion/ProVersion из `VERSION`, Copyright MIT
   - SmartScreen реже триггерит на файлы с заполненными метаданными, чем на «анонимные» exe

3. **Манифест с `asInvoker`** (`--manifest`)
   - `tools/app.manifest` → `requestedExecutionLevel level="asInvoker"` (не требует UAC), + `supportedOS` для Win7–11, `dpiAware`
   - Exe без манифеста часто определяется как legacy/требующий админских прав — это красный флаг

4. **Иконка** (`--icon`)
   - `src/detective_game/assets/images/icon.ico` — наличие иконки повышает доверие эвристик

5. **Явный сбор пакета** (`--collect-all`, `--paths src`, `--hidden-import`)
   - Убирает ложные `ImportError` и скрытые падения, из-за которых exe выглядел «битым»

6. **SHA256 и README в релизе**
   - Каждый релиз прикладывает `SHA256SUMS.txt` — пользователь может проверить целостность: `certUtil -hashfile DetectiveBlackville.exe SHA256`

## Что видит пользователь и что делать (инструкция для README и релиза)

### Вариант A — Запуск напрямую (Windows 10/11)
1. Скачай `DetectiveBlackville-Windows.zip` → распакуй
2. Правый клик по `DetectiveBlackville.exe` → **Свойства** → внизу поставь галочку **Разблокировать** (если есть) → Применить
3. Двойной клик → если появился синий экран *«Система Windows защитила...»*:
   - Нажми **Подробнее** (More info) → **Выполнить в любом случае** (Run anyway)
4. Если Защитник ругается: `Параметры → Безопасность Windows → Журнал защиты` → Разрешить

### Вариант B — Установщик (рекомендуется, меньше срабатываний)
Установщик `DetectiveBlackville-Setup.exe` (Inno Setup) имеет больше репутации, чем raw exe:
```bash
iscc tools/installer.iss  # собирает Setup
```
Установи → запусти из меню Пуск.

### Вариант C — PowerShell разблокировка (для продвинутых)
```powershell
Unblock-File -Path .\DetectiveBlackville.exe
.\DetectiveBlackville.exe
```

## Для разработчика — как убрать SmartScreen полностью (долгосрочно)

| Метод | Эффект | Стоимость |
|-------|--------|-----------|
| **EV Code Signing сертификат** (SSL.com, DigiCert) — подпись `signtool sign /fd SHA256 /tr http://timestamp.digicert.com` | ✅ SmartScreen сразу доверяет, «Издатель: Blackville Studio» вместо «Неизвестен» | ~$200–400/год |
| **Обычный OV сертификат** + накопление репутации | ⚠️ Сначала всё равно SmartScreen, но после 50+ скачиваний и положительной репутации предупреждение уходит | ~$70–100/год |
| **Microsoft Store** (MSIX) | ✅ Проходит модерацию, SmartScreen не триггерит | Бесплатно (аккаунт $19) |
| **Submit to Microsoft Defender** — https://www.microsoft.com/wdsi/filesubmission | ⚠️ Ускоряет анализ, но не гарантия | Бесплатно |
| **SmartScreen reputation building** — много установок без жалоб | ⚠️ Пассивно, требует времени | Бесплатно |

> В текущем open-source проекте EV-сертификата нет, поэтому мы:
> 1. Делаем всё возможное без подписи (метаданные + манифест + иконка + стабильный exe без ошибок импорта)
> 2. Даём понятную инструкцию в `dist/README.txt` и `README.md`
> 3. Предлагаем установщик + хеши

## Проверка после фикса

1. Собери: `.\tools\build.ps1` (Windows) или `bash tools/build.sh`
2. Запусти `dist/DetectiveBlackville.exe` — должен открыться без `Failed to execute script 'main'` — если всё ещё ошибка, смотри `launcher.py` → `detective_game.main` должен собираться с `--collect-all detective_game`
3. Правый клик → Свойства → Подробно → должны быть заполнены Имя продукта, версия, автор
4. `sigcheck -a dist\DetectiveBlackville.exe` (Sysinternals) покажет VersionInfo и Manifest

## FAQ

**Q: Раньше была ошибка `attempted relative import with no known parent package` — почему?**
A: PyInstaller собирал `src/detective_game/main.py` напрямую как скрипт, у него `__package__ == None`, поэтому `from .config import *` падает. Фикс: точка входа `launcher.py` в корне + `--paths src` + absolute import.

**Q: SmartScreen всё ещё появляется?**
A: На первых 5–50 скачиваниях неподписанного exe это нормально. После того как пользователи нажмут «Выполнить в любом случае» и не оставят жалоб, репутация вырастет и предупреждение уйдёт. С подписью OV/EV уходит сразу.

**Q: Антивирус ругается?**
A: PyInstaller onefile иногда ложно определяется как `Win32/Packed`. Загрузи exe на VirusTotal — если 1–2 детекта из 70, это фолс-позитив. Отправь файл в https://www.microsoft.com/wdsi/filesubmission для вайтлиста.

**Q: Как полностью убрать предупреждение без сертификата?**
A: Никак — это политика Microsoft. Единственный безкостовый путь — публикация через Microsoft Store как MSIX.
