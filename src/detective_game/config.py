"""Глобальные настройки и константы."""
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    """Возвращает директорию пакета, учитывая PyInstaller _MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # В сборке: _MEIPASS/detective_game
        meipass = Path(sys._MEIPASS)
        # assets добавлены как detective_game/assets → _MEIPASS/detective_game/assets
        candidate = meipass / "detective_game"
        if (candidate / "assets").exists():
            return candidate
        # Fallback: если собирали с --add-data на корень
        return meipass
    return Path(__file__).parent

BASE_DIR = _get_base_dir()
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"
FONTS_DIR = ASSETS_DIR / "fonts"
CASES_DIR = BASE_DIR / "cases"

# Окно
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60
TITLE = "ДЕТЕКТИВ: БЛЭКВИЛ — Код Города"

# Цвета — нуар палитра
COLOR_BG = (12, 12, 16)
COLOR_BG_LIGHT = (24, 24, 32)
COLOR_PANEL = (28, 28, 36)
COLOR_PANEL_LIGHT = (38, 38, 50)
COLOR_ACCENT = (212, 175, 55)  # золотистый нуар
COLOR_ACCENT_HOVER = (232, 195, 75)
COLOR_ACCENT_DIM = (160, 130, 40)
COLOR_TEXT = (235, 235, 225)
COLOR_TEXT_DIM = (160, 160, 150)
COLOR_TEXT_DARK = (90, 90, 90)
COLOR_RED = (200, 50, 50)
COLOR_GREEN = (80, 180, 100)
COLOR_BLUE = (70, 130, 200)
COLOR_BORDER = (60, 60, 70)
COLOR_SHADOW = (0, 0, 0, 120)

# Шрифты — будут использоваться дефолтные pygame, позже добавим
FONT_SIZE_SMALL = 14
FONT_SIZE_NORMAL = 18
FONT_SIZE_MEDIUM = 22
FONT_SIZE_LARGE = 28
FONT_SIZE_TITLE = 48

# GitHub
GITHUB_REPO = "ignatus4405-glitch/detective_game"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"

# Сохранения
SAVE_DIR_NAME = "BlackvilleDetective"
SAVE_FILE = "savegame.json"
SETTINGS_FILE = "settings.json"
DETECTIVE_FILE = "detective.json"
