"""Художественные фоны: карты города, иллюстрации локаций.

Картинки лежат в ``assets/images`` (например ``maps/blackville.jpg``), грузятся
один раз и кэшируются по размеру и силе затемнения. ``cover`` обрезает картинку
по центру, чтобы она заполнила панель без полей и искажений.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

from ..config import IMAGES_DIR

_CACHE: Dict[tuple, pygame.Surface] = {}


def resolve(relpath: str) -> Path:
    """Путь к картинке: относительный считается от ``assets/images``."""
    path = Path(relpath)
    return path if path.is_absolute() else Path(IMAGES_DIR) / path


def cover_image(
    relpath: str,
    size: Tuple[int, int],
    dim: float = 0.0,
    tint: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[pygame.Surface]:
    """Картинка под размер панели (cover) с затемнением ``dim`` (0..1).

    ``tint`` — цветная вуаль (RGBA): одна и та же картинка в разных локациях
    выглядит по-разному, пока для типа нет отдельной иллюстрации.
    Возвращает ``None``, если файла нет или pygame не может его прочитать —
    вызывающий код рисует запасной фон.
    """
    if not relpath:
        return None
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    key = (str(relpath), width, height, round(float(dim), 2), tuple(tint) if tint else None)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        img = pygame.image.load(str(resolve(relpath)))
        if pygame.display.get_surface() is not None:
            img = img.convert()
    except Exception:
        return None
    img = _cover(img, (width, height))
    if tint:
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        layer.fill(tuple(tint))
        img.blit(layer, (0, 0))
    if dim > 0:
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((6, 8, 14, int(255 * dim)))
        img.blit(shade, (0, 0))
    _CACHE[key] = img
    return img


def _cover(img: pygame.Surface, size: Tuple[int, int]) -> pygame.Surface:
    width, height = size
    iw, ih = img.get_size()
    if iw <= 0 or ih <= 0:
        return pygame.Surface(size)
    scale = max(width / iw, height / ih)
    scaled = pygame.transform.smoothscale(
        img, (max(1, int(iw * scale)), max(1, int(ih * scale)))
    )
    out = pygame.Surface((width, height))
    out.blit(scaled, ((width - scaled.get_width()) // 2, (height - scaled.get_height()) // 2))
    return out


def blit_rounded(surface, img: Optional[pygame.Surface], rect: pygame.Rect, radius: int = 8) -> bool:
    """Кладёт картинку в прямоугольник со скруглёнными углами."""
    if img is None:
        return False
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    layer.blit(img, (0, 0))
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(layer, rect.topleft)
    return True


def clear_cache() -> None:
    """Сбрасывает загруженные картинки (после pygame.quit()/init())."""
    _CACHE.clear()
