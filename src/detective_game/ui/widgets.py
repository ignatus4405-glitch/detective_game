"""UI примитивы для нуар-стиля."""
from pathlib import Path

import pygame

from ..config import *

# Кэш шрифтов для производительности и корректного отображения кириллицы
_FONT_CACHE = {}

def _get_bundled_font_path(bold=False) -> Path | None:
    """Возвращает путь к bundled шрифту с поддержкой кириллицы."""
    # Проверяем несколько возможных путей
    candidates = [
        FONTS_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path(__file__).parent.parent / "assets" / "fonts" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path("src/detective_game/assets/fonts") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    # Системный дежавью как fallback
    for sys_path in [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if sys_path.exists():
            return sys_path
    return None

def get_font(size, bold=False):
    """Возвращает шрифт с поддержкой кириллицы, использует bundled DejaVuSans."""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    
    # Пробуем bundled шрифт
    bundled = _get_bundled_font_path(bold=bold)
    if bundled and bundled.exists():
        try:
            font = pygame.font.Font(str(bundled), size)
            _FONT_CACHE[key] = font
            return font
        except Exception:
            pass
    
    # Пробуем системные шрифты с поддержкой кириллицы
    for font_name in ["DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial", "Segoe UI"]:
        try:
            font = pygame.font.SysFont(font_name, size, bold=bold)
            # Проверяем что шрифт может отрендерить кириллицу (тестовая проверка)
            if font:
                _FONT_CACHE[key] = font
                return font
        except Exception:
            continue
    
    # Fallback — дефолтный
    try:
        font = pygame.font.Font(None, size)
        _FONT_CACHE[key] = font
        return font
    except Exception:
        font = pygame.font.SysFont(None, size, bold=bold)
        _FONT_CACHE[key] = font
        return font

def draw_panel(surface, rect, color=COLOR_PANEL, border=COLOR_BORDER, radius=8, with_shadow=True):
    if with_shadow:
        shadow = pygame.Rect(rect.x+4, rect.y+4, rect.w, rect.h)
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (0,0,0,100), (0,0,rect.w,rect.h), border_radius=radius)
        surface.blit(s, shadow.topleft)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)

def draw_button(surface, rect, text, font, hovered=False, enabled=True, accent=False):
    if not enabled:
        col = (50,50,60)
        tcol = COLOR_TEXT_DARK
    elif accent:
        col = COLOR_ACCENT if not hovered else COLOR_ACCENT_HOVER
        tcol = (10,10,10)
    else:
        col = COLOR_PANEL_LIGHT if not hovered else (50,50,65)
        tcol = COLOR_TEXT if enabled else COLOR_TEXT_DARK
    pygame.draw.rect(surface, col, rect, border_radius=6)
    pygame.draw.rect(surface, COLOR_ACCENT if accent else COLOR_BORDER, rect, width=1, border_radius=6)
    txt = font.render(text, True, tcol)
    surface.blit(txt, txt.get_rect(center=rect.center))
    return txt

def draw_text_wrapped(surface, text, font, color, rect, line_spacing=2):
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        test = cur + (" " if cur else "") + w
        if font.size(test)[0] <= rect.w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
            # если слово длиннее ширины — режем
            while font.size(cur)[0] > rect.w:
                lines.append(cur[:20])
                cur = cur[20:]
    if cur:
        lines.append(cur)
    y = rect.y
    for line in lines:
        if y + font.get_height() > rect.y + rect.h:
            break
        surf = font.render(line, True, color)
        surface.blit(surf, (rect.x, y))
        y += font.get_height() + line_spacing
    return y - rect.y

class Button:
    def __init__(self, rect, text, accent=False, enabled=True):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.accent = accent
        self.enabled = enabled
        self.hovered = False
        self.clicked = False

    def update(self, mouse_pos, mouse_pressed):
        self.hovered = self.rect.collidepoint(mouse_pos) and self.enabled
        self.clicked = self.hovered and mouse_pressed

    def draw(self, surface, font):
        draw_button(surface, self.rect, self.text, font, self.hovered, self.enabled, self.accent)

class TextInput:
    def __init__(self, rect, placeholder="", text="", max_len=24):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.text = text
        self.max_len = max_len
        self.active = False
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.unicode and len(self.text) < self.max_len and event.unicode.isprintable():
                self.text += event.unicode

    def draw(self, surface, font):
        col = COLOR_PANEL_LIGHT if self.active else COLOR_PANEL
        border = COLOR_ACCENT if self.active else COLOR_BORDER
        pygame.draw.rect(surface, col, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=2 if self.active else 1, border_radius=6)
        txt = self.text if self.text else self.placeholder
        tcol = COLOR_TEXT if self.text else COLOR_TEXT_DIM
        surf = font.render(txt, True, tcol)
        surface.blit(surf, (self.rect.x+12, self.rect.y + (self.rect.h - surf.get_height())//2))
        # курсор
        if self.active:
            self.cursor_timer = (self.cursor_timer + 1) % 60
            if self.cursor_timer < 30:
                cx = self.rect.x + 12 + font.size(self.text)[0] + 2
                pygame.draw.line(surface, COLOR_ACCENT, (cx, self.rect.y+10), (cx, self.rect.y+self.rect.h-10), 2)

def draw_noir_overlay(surface):
    """Градиент + виньетка для атмосферы."""
    w, h = surface.get_size()
    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(80):
        alpha = int(80 * (i/80)**1.5)
        pygame.draw.rect(vignette, (0,0,0, alpha//8), (i, i, w-i*2, h-i*2), width=1, border_radius=12)
    surface.blit(vignette, (0,0))

# Кэш для изображений аватаров
_AVATAR_CACHE = {}

def _load_avatar_image(avatar_id, size):
    """Загружает и кэширует изображение аватара, масштабирует под размер."""
    cache_key = (avatar_id, size[0], size[1])
    if cache_key in _AVATAR_CACHE:
        return _AVATAR_CACHE[cache_key]
    
    # Пробуем несколько путей
    candidates = [
        IMAGES_DIR / f"{avatar_id}.png",
        Path(__file__).parent.parent / "assets" / "images" / f"{avatar_id}.png",
        Path(f"src/detective_game/assets/images/{avatar_id}.png"),
    ]
    for path in candidates:
        if path.exists():
            try:
                img = pygame.image.load(str(path))
                # Масштабируем с сохранением пропорций, обрезаем по центру
                img = pygame.transform.smoothscale(img, size)
                _AVATAR_CACHE[cache_key] = img
                return img
            except Exception:
                continue
    return None

def draw_avatar(surface, rect, avatar_data, selected=False):
    """Рисует аватар — загружает изображение если есть, иначе цветную заглушку."""
    # Пытаемся загрузить изображение
    avatar_id = avatar_data.get("id", "")
    img = _load_avatar_image(avatar_id, (rect.w, rect.h))
    
    if img:
        # Рисуем изображение с закругленными углами
        # Создаем маску для скругления
        temp_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(temp_surf, (255,255,255,255), (0,0,rect.w,rect.h), border_radius=8)
        # Накладываем изображение
        surface.blit(img, rect.topleft)
        # Рисуем рамку
        border = COLOR_ACCENT if selected else COLOR_BORDER
        pygame.draw.rect(surface, border, rect, width=3 if selected else 1, border_radius=8)
        # Если выбран — подсветка
        if selected:
            highlight = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(highlight, (212,175,55,30), (0,0,rect.w,rect.h), border_radius=8)
            surface.blit(highlight, rect.topleft)
    else:
        # Fallback — цветная заглушка
        color = avatar_data.get("color", (80,80,100))
        border = COLOR_ACCENT if selected else COLOR_BORDER
        pygame.draw.rect(surface, color, rect, border_radius=8)
        pygame.draw.rect(surface, border, rect, width=3 if selected else 1, border_radius=8)
        # инициал
        font_big = get_font(28, bold=True)
        init = avatar_data["name"][0]
        txt = font_big.render(init, True, (255,255,255))
        surface.blit(txt, txt.get_rect(center=rect.center))
    
    # имя снизу — полупрозрачная плашка
    font_small = get_font(11, bold=True)
    name_surf = font_small.render(avatar_data["name"], True, (255,255,255))
    bg_rect = pygame.Rect(rect.x, rect.bottom - 20, rect.w, 20)
    s = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(s, (0,0,0,180), (0,0,bg_rect.w, bg_rect.h), border_radius=4)
    surface.blit(s, bg_rect.topleft)
    surface.blit(name_surf, name_surf.get_rect(center=bg_rect.center))
    
    # Индикатор выбора — галочка
    if selected:
        check_font = get_font(12, bold=True)
        check = check_font.render("✓", True, COLOR_ACCENT)
        # Кружок для галочки
        pygame.draw.circle(surface, COLOR_ACCENT, (rect.right - 12, rect.y + 12), 10)
        pygame.draw.circle(surface, (0,0,0), (rect.right - 12, rect.y + 12), 10, width=1)
        surface.blit(check, check.get_rect(center=(rect.right - 12, rect.y + 12)))

def draw_map_pin(surface, pos, location, visited=False, current=False):
    """Иконка локации на карте."""
    x, y = pos
    type_colors = {
        "hub": (200,180,60),
        "police": (70,100,180),
        "crime": (200,60,60),
        "bar": (180,120,40),
        "apartment": (80,150,80),
        "public": (100,140,160),
        "bank": (160,140,60),
        "vault": (140,140,140),
        "office": (100,100,140),
        "mansion": (140,100,60),
        "shop": (120,100,160),
        "warehouse": (90,90,90),
        "port": (50,120,140),
    }
    col = type_colors.get(location.get("type","public"), (150,150,150))
    if not visited:
        col = tuple(c//2 for c in col)
    radius = 18 if current else 14
    pygame.draw.circle(surface, (0,0,0,120), (x+3,y+3), radius+2)
    pygame.draw.circle(surface, col, (x,y), radius)
    pygame.draw.circle(surface, (255,255,255) if current else (200,200,200), (x,y), radius, width=2)
    if current:
        pygame.draw.circle(surface, COLOR_ACCENT, (x,y), radius+6, width=2)
    if visited:
        font = get_font(12, bold=True)
        txt = font.render("✓", True, (255,255,255))
        surface.blit(txt, (x+8, y-10))
    font_small = get_font(11, bold=True)
    name = location["name"]
    txt = font_small.render(name, True, COLOR_TEXT if visited else COLOR_TEXT_DIM)
    bg = pygame.Surface((txt.get_width()+8, txt.get_height()+4), pygame.SRCALPHA)
    pygame.draw.rect(bg, (0,0,0,180), (0,0,bg.get_width(), bg.get_height()), border_radius=4)
    surface.blit(bg, (x - bg.get_width()//2, y + radius + 4))
    surface.blit(txt, (x - txt.get_width()//2, y + radius + 6))
