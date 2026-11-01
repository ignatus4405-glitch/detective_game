"""Сохранения и настройки — кроссплатформенно."""
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .config import DETECTIVE_FILE, SAVE_DIR_NAME, SAVE_FILE, SETTINGS_FILE
from .game_state import DetectiveProfile, GameState


def get_save_dir() -> Path:
    """Определяем директорию сохранения в зависимости от ОС."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / SAVE_DIR_NAME
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / SAVE_DIR_NAME
    else:
        # Linux / sandbox
        xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(xdg) / SAVE_DIR_NAME

def ensure_save_dir():
    p = get_save_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_game(state: GameState):
    d = get_save_dir()
    ensure_save_dir()
    path = d / SAVE_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

def load_game() -> Optional[GameState]:
    path = get_save_dir() / SAVE_FILE
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GameState.from_dict(data)
    except Exception:
        return None

def has_save() -> bool:
    return (get_save_dir() / SAVE_FILE).exists()

def delete_save():
    path = get_save_dir() / SAVE_FILE
    if path.exists():
        path.unlink()

def save_detective(profile: DetectiveProfile):
    ensure_save_dir()
    path = get_save_dir() / DETECTIVE_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.__dict__, f, ensure_ascii=False, indent=2)

def load_detective() -> Optional[DetectiveProfile]:
    path = get_save_dir() / DETECTIVE_FILE
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DetectiveProfile(**data)
    except Exception:
        return None

def save_settings(settings: dict):
    ensure_save_dir()
    path = get_save_dir() / SETTINGS_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def load_settings() -> dict:
    path = get_save_dir() / SETTINGS_FILE
    if not path.exists():
        return {"sfx_volume": 0.7, "music_volume": 0.5, "fullscreen": False, "lang": "ru"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sfx_volume": 0.7, "music_volume": 0.5, "fullscreen": False, "lang": "ru"}
