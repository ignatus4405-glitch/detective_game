"""Менеджер настроек экрана — разрешение, монитор, режим окна."""
import os
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
    ("windowed", "Оконный", ""),
    ("fullscreen", "Полный экран", ""),
    ("borderless", "Без рамки", ""),
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
    return sorted(set(SUPPORTED_RESOLUTIONS), key=lambda s: s[0]*s[1])

def get_available_monitors():
    """Возвращает список мониторов с их размерами."""
    monitors = []
    try:
        num = pygame.display.get_num_displays()
        sizes = pygame.display.get_desktop_sizes()
        for i in range(num):
            size = sizes[i] if i < len(sizes) else (1920, 1080)
            name = f"Монитор {i+1} — {size[0]}×{size[1]}"
            monitors.append({"id": i, "name": name, "size": tuple(size), "pos": (0, 0)})
        # Пытаемся получить позицию монитора (SDL2.0.4+)
        try:
            for i in range(num):
                # pygame 2.5+ может иметь get_display_bounds
                if hasattr(pygame.display, "get_display_bounds"):
                    b = pygame.display.get_display_bounds(i)
                    if b and len(b) >= 2:
                        monitors[i]["pos"] = (b[0], b[1])
        except Exception:
            pass
    except Exception:
        monitors.append({"id": 0, "name": "Монитор 1 — 1920×1080", "size": (1920, 1080), "pos": (0, 0)})
    if not monitors:
        monitors.append({"id": 0, "name": "Монитор 1 — 1920×1080", "size": (1920, 1080), "pos": (0, 0)})
    return monitors

def _get_monitor_origin(monitor: int):
    """Возвращает (x,y) левого верхнего угла монитора для SDL_WINDOWPOS."""
    try:
        if hasattr(pygame.display, "get_display_bounds"):
            b = pygame.display.get_display_bounds(monitor)
            if b:
                return b[0], b[1]
    except Exception:
        pass
    # Fallback: суммируем ширины предыдущих мониторов (горизонтальная раскладка)
    try:
        sizes = pygame.display.get_desktop_sizes()
        x = sum(s[0] for s in sizes[:monitor])
        return x, 0
    except Exception:
        pass
    return 0, 0

def apply_display_settings(settings: dict, screen=None):
    """Применяет настройки экрана, возвращает новый screen.

    Фикс: раньше выбор монитора не работал для оконного/borderless режимов на старых pygame,
    т.к. параметр display поддерживается только с 2.1 и только для fullscreen. Теперь для
    windowed/borderless используем SDL_VIDEO_WINDOW_POS через os.environ + повторно создаём окно.
    """
    width, height = settings.get("resolution", (WINDOW_WIDTH, WINDOW_HEIGHT))
    if isinstance(width, list):
        width, height = tuple(width)
    else:
        try:
            width, height = int(width), int(height)
        except Exception:
            width, height = WINDOW_WIDTH, WINDOW_HEIGHT

    mode = settings.get("window_mode", "windowed")
    try:
        monitor = int(settings.get("monitor", 0))
    except Exception:
        monitor = 0

    # Гарантируем что монитор в диапазоне
    try:
        num = pygame.display.get_num_displays()
        monitor = max(0, min(monitor, num - 1))
    except Exception:
        pass

    flags = 0
    if mode == "fullscreen":
        flags = pygame.FULLSCREEN
    elif mode == "borderless":
        flags = pygame.NOFRAME

    # Для windowed/borderless пытаемся позиционировать окно на выбранный монитор
    if mode in ("windowed", "borderless"):
        try:
            ox, oy = _get_monitor_origin(monitor)
            # Центрируем окно внутри монитора (если оно меньше монитора)
            try:
                mons = get_available_monitors()
                if monitor < len(mons):
                    mw, mh = mons[monitor]["size"]
                    # Центрируем
                    cx = ox + max(0, (mw - width) // 2)
                    cy = oy + max(0, (mh - height) // 2)
                    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{cx},{cy}"
                else:
                    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{ox},{oy}"
            except Exception:
                os.environ["SDL_VIDEO_WINDOW_POS"] = f"{ox},{oy}"
        except Exception:
            pass

    try:
        # Пробуем с display param (pygame >=2.1)
        try:
            new_screen = pygame.display.set_mode((width, height), flags, display=monitor)
        except TypeError:
            # Старый pygame — пробуем без display, но окно уже спозиционировано через env
            # Пересоздаём дважды чтобы SDL применила позицию (баг некоторых SDL)
            new_screen = pygame.display.set_mode((width, height), flags)
            # Для borderless — устанавливаем размер ещё раз для надёжности
            if mode == "borderless":
                try:
                    # Некоторые системы требуют пересоздания без флагов
                    pygame.display.set_mode((width, height), flags)
                except Exception:
                    pass
        # Очищаем env чтобы не влиять на следующие вызовы
        if "SDL_VIDEO_WINDOW_POS" in os.environ:
            try:
                del os.environ["SDL_VIDEO_WINDOW_POS"]
            except Exception:
                pass
        return new_screen
    except Exception as e:
        print(f"[Display] Failed to apply {width}x{height} mode={mode} monitor={monitor}: {e}")
        if "SDL_VIDEO_WINDOW_POS" in os.environ:
            try:
                del os.environ["SDL_VIDEO_WINDOW_POS"]
            except Exception:
                pass
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
