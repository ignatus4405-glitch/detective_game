"""Менеджер настроек экрана — разрешение, монитор, режим окна."""
from pathlib import Path

import pygame

from .config import WINDOW_HEIGHT, WINDOW_WIDTH
from .save_system import load_settings, save_settings

# Поддерживаемые разрешения — 16:9 + 16:10 + 4:3 для совместимости
SUPPORTED_RESOLUTIONS = [
    (1280, 720),   # HD — базовое
    (1366, 768),   # HD+ ноутбуки
    (1600, 900),   # HD+
    (1920, 1080),  # FullHD
    (1920, 1200),  # WUXGA
    (2560, 1440),  # QHD
    (2560, 1600),  # WQXGA
    (3440, 1440),  # UWQHD (ультраширокий)
]

WINDOW_MODES = [
    ("windowed", "Оконный", "🗔"),
    ("fullscreen", "Полный экран", "⛶"),
    ("borderless", "Без рамки", "▭"),
]

def get_available_resolutions():
    """Возвращает список доступных разрешений + текущее десктопа."""
    try:
        desktop_sizes = pygame.display.get_desktop_sizes()
        if desktop_sizes:
            for size in desktop_sizes:
                if tuple(size) not in SUPPORTED_RESOLUTIONS:
                    SUPPORTED_RESOLUTIONS.append(tuple(size))
    except Exception:
        pass
    # Сортируем по площади
    return sorted(set(SUPPORTED_RESOLUTIONS), key=lambda s: s[0]*s[1])

def get_available_monitors():
    """Возвращает список мониторов с их размерами."""
    monitors = []
    try:
        num = pygame.display.get_num_displays()
        sizes = pygame.display.get_desktop_sizes()
        for i in range(num):
            size = sizes[i] if i < len(sizes) else (1920,1080)
            name = f"Монитор {i+1} — {size[0]}×{size[1]}"
            # Пробуем получить имя через SDL? пока номер
            monitors.append({"id": i, "name": name, "size": tuple(size)})
    except Exception:
        monitors.append({"id": 0, "name": "Монитор 1 — 1920×1080", "size": (1920,1080)})
    if not monitors:
        monitors.append({"id": 0, "name": "Монитор 1 — 1920×1080", "size": (1920,1080)})
    return monitors

def apply_display_settings(settings: dict, screen=None):
    """Применяет настройки экрана, возвращает новый screen."""
    width, height = settings.get("resolution", (WINDOW_WIDTH, WINDOW_HEIGHT))
    # Поддержка как tuple так и list из JSON
    if isinstance(width, list):
        width, height = tuple(width)
    else:
        width, height = int(width), int(height)
    
    mode = settings.get("window_mode", "windowed")
    monitor = settings.get("monitor", 0)
    
    flags = 0
    if mode == "fullscreen":
        flags = pygame.FULLSCREEN
    elif mode == "borderless":
        flags = pygame.NOFRAME
    
    try:
        # pygame 2.1+ поддерживает display параметр для выбора монитора
        # Пробуем с display, если не поддерживается — без
        try:
            new_screen = pygame.display.set_mode((width, height), flags, display=monitor)
        except TypeError:
            # Старая версия pygame без display параметра
            new_screen = pygame.display.set_mode((width, height), flags)
        
        # Обновляем глобальные константы для совместимости? Не меняем, используем settings
        return new_screen
    except Exception as e:
        print(f"[Display] Failed to apply {width}x{height} mode={mode} monitor={monitor}: {e}")
        # Fallback к базовому
        try:
            return pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        except Exception:
            return screen

def get_current_settings():
    """Загружает настройки с дефолтами для экрана."""
    s = load_settings()
    defaults = {
        "resolution": [WINDOW_WIDTH, WINDOW_HEIGHT],
        "window_mode": "windowed",
        "monitor": 0,
        "vsync": 1,
        "fps_limit": 60,
        "sfx_volume": 0.7,
        "music_volume": 0.5,
        "lang": "ru",
        "auto_check_updates": True,
    }
    for k, v in defaults.items():
        if k not in s:
            s[k] = v
    return s

def save_current_settings(settings: dict):
    save_settings(settings)
