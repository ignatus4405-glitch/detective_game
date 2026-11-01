"""Генерирует README.txt для дистрибутива."""
from pathlib import Path
VERSION = Path("VERSION").read_text().strip()
text = f"""ДЕТЕКТИВ: БЛЭКВИЛ — Код Города
Версия {VERSION}
=============================

Спасибо что скачали игру!

ЗАПУСК:
  1. Распакуйте архив в любую папку
  2. Запустите DetectiveBlackville.exe
  3. При первом запуске создайте детектива (имя + образ)

УПРАВЛЕНИЕ:
  - Мышка — всё
  - ESC — назад
  - На карте кликните на локацию чтобы посетить

СОХРАНЕНИЯ:
  Windows: %APPDATA%\\BlackvilleDetective\\

ОБНОВЛЕНИЯ:
  Игра сама проверяет GitHub Releases и показывает баннер.
  Скачать новую версию: https://github.com/ignatus4405-glitch/detective_game/releases

ПОДДЕРЖКА:
  Issues: https://github.com/ignatus4405-glitch/detective_game/issues

Приятного расследования!
— Blackville Studio, 2026
"""
Path("dist/README.txt").write_text(text, encoding="utf-8") if Path("dist").exists() else None
print(text)
