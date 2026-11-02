#!/usr/bin/env python
"""Точка входа для PyInstaller — без relative import.

Фиксит: Failed to execute script 'main' due to attempted relative import with no known parent package
Раньше собирали src/detective_game/main.py напрямую → __package__ == None → from .config падает.
Теперь собираем launcher.py (корень, absolute import) → detective_game.main импортируется как пакет.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Для frozen — ensure sys._MEIPASS assets path handled in config.py
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    pass

def _show_error(title: str, msg: str):
    """Показать ошибку пользователю максимально дружелюбно."""
    # Попытка 1: tkinter (есть в stdlib, работает без pygame)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(title, msg)
        root.destroy()
        return
    except Exception:
        pass
    # Попытка 2: MessageBox Win32
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
        return
    except Exception:
        pass
    # Fallback: stderr
    print(f"[ERROR] {title}: {msg}", file=sys.stderr)

def main():
    try:
        from detective_game.main import main as game_main
        return game_main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Логируем в файл рядом с exe для отладки
        try:
            log_path = Path(sys.executable).parent / "crash.log" if getattr(sys, "frozen", False) else ROOT / "crash.log"
            log_path.write_text(tb, encoding="utf-8")
        except Exception:
            pass

        # Анализ типичной ошибки PyInstaller onefile — python DLL не найдена
        is_dll_error = "Failed to load Python DLL" in str(e) or "python3" in str(e).lower() and ".dll" in str(e).lower() or "_MEI" in tb
        if is_dll_error:
            friendly = (
                f"Не удалось загрузить Python DLL (ошибка распаковки игры):\n\n{e}\n\n"
                "Это известная проблема однофайловой сборки — антивирус или защита Windows заблокировала временную папку Temp\\_MEI*.\n\n"
                "Что делать:\n"
                "1. Добавьте папку игры в исключения антивируса / Защитника Windows\n"
                "2. Установите Microsoft Visual C++ Redistributable 2015-2022 (x64) с сайта Microsoft\n"
                "3. Удалите кэш: удалите папки %TEMP%\\_MEI* и %LOCALAPPDATA%\\Programs\\BlackvilleDetective, переустановите игру\n"
                "4. Попробуйте портативную версию (DetectiveBlackville-Windows.zip) — распаковать в D:\\Games\\ и запустить оттуда\n"
                "5. Запустите от имени администратора (правый клик → Запуск от имени администратора)\n\n"
                "Новая версия 0.1.22+ уже использует обычную установку без распаковки в Temp — обновите игру.\n"
                f"Сообщите об ошибке: https://github.com/ignatus4405-glitch/detective_game/issues\nПриложите crash.log рядом с exe\n\nТехнические детали:\n{tb[:1000]}"
            )
        else:
            friendly = (
                f"Произошла ошибка при запуске игры:\n\n{e}\n\n"
                "Что делать:\n"
                "1. Убедитесь что антивирус не удалил файлы из папки\n"
                "2. Попробуйте запустить от имени администратора (правый клик → Запуск от имени администратора)\n"
                "3. Удалите папку %APPDATA%\\BlackvilleDetective и перезапустите\n"
                "4. Сообщите об ошибке: https://github.com/ignatus4405-glitch/detective_game/issues\n"
                "   Приложите файл crash.log рядом с exe\n\n"
                f"Технические детали:\n{tb[:1200]}"
            )
        _show_error("Детектив: Блэквил — Ошибка", friendly)
        return 1

if __name__ == "__main__":
    sys.exit(main())
