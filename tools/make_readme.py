"""Генерирует README.txt для дистрибутива с инструкцией по SmartScreen."""
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip().lstrip("v")
# хеш будет дописан build скриптом, тут шаблон

text = f"""ДЕТЕКТИВ: БЛЭКВИЛ — Код Города
Версия {VERSION}
=============================
https://github.com/ignatus4405-glitch/detective_game

СПАСИБО ЧТО СКАЧАЛИ!

ЗАПУСК:
  1. Распакуйте архив в любую папку (например, C:\\Games\\Blackville)
  2. Правый клик по DetectiveBlackville.exe → Свойства → [Разблокировать] внизу (если есть) → ОК
  3. Запустите DetectiveBlackville.exe
  4. При первом запуске создайте детектива (имя + образ) — используется в диалогах

ЕСЛИ WINDOWS РУГАЕТСЯ (SMARTSCREEN):
  Это нормально для неподписанного exe без репутации — не вирус.
  На синем экране "Система Windows защитила ваш компьютер":
    → Нажмите "Подробнее" (More info)
    → "Выполнить в любом случае" (Run anyway)
  Подробнее: https://github.com/ignatus4405-glitch/detective_game/blob/main/docs/SMARTSCREEN.md

  Альтернатива — установщик (меньше срабатываний):
    Запустите DetectiveBlackville-Setup.exe (если скачали Full.zip)

ПРОВЕРКА ЦЕЛОСТНОСТИ:
  В архиве есть SHA256SUMS.txt — сверьте:
    PowerShell: Get-FileHash DetectiveBlackville.exe -Algorithm SHA256
    cmd: certUtil -hashfile DetectiveBlackville.exe SHA256
  Должно совпасть с SHA256SUMS.txt

УПРАВЛЕНИЕ:
  - Мышка — всё
  - ESC — назад
  - На карте кликните на локацию чтобы посетить
  - Блокнот — улики/досье/заметки
  - Финальное обвинение — выберите виновного

СОХРАНЕНИЯ:
  Windows: %APPDATA%\\BlackvilleDetective\\ (не удаляются при переустановке)
  Linux: ~/.local/share/BlackvilleDetective/
  macOS: ~/Library/Application Support/BlackvilleDetective/

ОБНОВЛЕНИЯ:
  Игра сама проверяет GitHub Releases и показывает баннер если есть новая версия.
  Вручную: Настройки → Проверить обновления
  Скачать новую версию: https://github.com/ignatus4405-glitch/detective_game/releases

ПРОБЛЕМЫ:
  • "Failed to execute script 'main'" — исправлено в {VERSION}, если видите — скачайте новый релиз
  • Чёрный экран — проверьте что разрешение 1280×720 поддерживается
  • Не сохраняется — проверьте права на %APPDATA%
  Вопросы: https://github.com/ignatus4405-glitch/detective_game/issues

ЛИЦЕНЗИЯ: MIT (c) 2026 Blackville Studio
Оригинал вдохновения: https://kodgoroda.games

Приятного расследования, детектив!
— Blackville Studio, 2026
"""

out_dir = ROOT / "dist"
out_dir.mkdir(exist_ok=True)
( out_dir / "README.txt").write_text(text, encoding="utf-8")
print(f"✓ README.txt generated for {VERSION}")
print(text[:400])
