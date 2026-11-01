"""UI примитивы для нуар-стиля — с кастомизацией и поддержкой кириллицы."""
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pygame

from ..config import *

# ── ШРИФТЫ ───────────────────────────────────────────────────────────────
_FONT_CACHE = {}

def _get_bundled_font_path(bold=False) -> Path | None:
    candidates = [
        FONTS_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path(__file__).parent.parent / "assets" / "fonts" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path("src/detective_game/assets/fonts") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    for sys_path in [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if sys_path.exists():
            return sys_path
    return None

def get_font(size, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    bundled = _get_bundled_font_path(bold=bold)
    if bundled and bundled.exists():
        try:
            font = pygame.font.Font(str(bundled), size)
            _FONT_CACHE[key] = font
            return font
        except Exception:
            pass
    for font_name in ["DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial", "Segoe UI"]:
        try:
            font = pygame.font.SysFont(font_name, size, bold=bold)
            if font:
                _FONT_CACHE[key] = font
                return font
        except Exception:
            continue
    try:
        font = pygame.font.Font(None, size)
        _FONT_CACHE[key] = font
        return font
    except Exception:
        font = pygame.font.SysFont(None, size, bold=bold)
        _FONT_CACHE[key] = font
        return font

# ── УТИЛИТЫ РИСОВАНИЯ ────────────────────────────────────────────────────
def draw_gradient_rect(surface, rect, color_top, color_bottom, radius=6):
    """Вертикальный градиент с закруглением."""
    # Создаем временную поверхность
    temp = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    for y in range(rect.h):
        t = y / max(1, rect.h - 1)
        r = int(color_top[0] * (1-t) + color_bottom[0] * t)
        g = int(color_top[1] * (1-t) + color_bottom[1] * t)
        b = int(color_top[2] * (1-t) + color_bottom[2] * t)
        pygame.draw.line(temp, (r,g,b), (0,y), (rect.w,y))
    # Маска закругления
    pygame.draw.rect(temp, (255,255,255,255), (0,0,rect.w,rect.h), border_radius=radius)
    # Применяем маску через скругление (упрощенно — просто рисуем градиент и сверху рамку)
    surface.blit(temp, rect.topleft)
    # Закругление через overlay (упрощенно)
    pygame.draw.rect(surface, (0,0,0,0), rect, border_radius=radius)

def draw_panel(surface, rect, color=COLOR_PANEL, border=COLOR_BORDER, radius=8, with_shadow=True):
    if with_shadow:
        shadow = pygame.Rect(rect.x+4, rect.y+4, rect.w, rect.h)
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (0,0,0,100), (0,0,rect.w,rect.h), border_radius=radius)
        surface.blit(s, shadow.topleft)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)

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

# ── КНОПКИ — КАСТОМИЗИРУЕМЫЕ ─────────────────────────────────────────────
BUTTON_STYLES = {
    "primary":   {"bg": COLOR_ACCENT, "bg_hover": COLOR_ACCENT_HOVER, "bg_top": (232,200,80), "bg_bottom": (180,145,40), "text": (10,10,10), "border": COLOR_ACCENT, "shadow": True},
    "secondary": {"bg": COLOR_PANEL_LIGHT, "bg_hover": (50,50,65), "bg_top": (45,45,58), "bg_bottom": (30,30,42), "text": COLOR_TEXT, "border": COLOR_BORDER, "shadow": False},
    "ghost":     {"bg": (0,0,0,0), "bg_hover": (40,40,50), "bg_top": (30,30,40), "bg_bottom": (20,20,30), "text": COLOR_TEXT_DIM, "border": COLOR_BORDER, "shadow": False},
    "danger":    {"bg": COLOR_RED, "bg_hover": (220,70,70), "bg_top": (210,60,60), "bg_bottom": (160,40,40), "text": (255,255,255), "border": COLOR_RED, "shadow": True},
    "success":   {"bg": COLOR_GREEN, "bg_hover": (100,200,120), "bg_top": (90,190,110), "bg_bottom": (60,150,80), "text": (255,255,255), "border": COLOR_GREEN, "shadow": True},
}

class Button:
    """Кастомизируемая кнопка с поддержкой стилей, иконок и hover-анимации."""
    def __init__(self, rect, text, accent=False, enabled=True, style: str = None, icon: str = None, tooltip: str = None, gradient: bool = True):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.accent = accent
        self.enabled = enabled
        self.icon = icon
        self.tooltip = tooltip
        self.gradient = gradient
        # Стиль: primary = accent, secondary = обычный
        if style:
            self.style = style
        else:
            self.style = "primary" if accent else "secondary"
        self.hovered = False
        self.clicked = False
        self.pressed = False
        self.hover_progress = 0.0  # 0..1 для анимации

    def update(self, mouse_pos, mouse_pressed):
        was_hovered = self.hovered
        self.hovered = self.rect.collidepoint(mouse_pos) and self.enabled
        # Анимация hover
        target = 1.0 if self.hovered else 0.0
        self.hover_progress += (target - self.hover_progress) * 0.25
        
        self.clicked = self.hovered and mouse_pressed and not self.pressed
        self.pressed = self.hovered and mouse_pressed

    def draw(self, surface, font):
        style = BUTTON_STYLES.get(self.style, BUTTON_STYLES["secondary"])
        
        if not self.enabled:
            bg = (50,50,60)
            tcol = COLOR_TEXT_DARK
            border = COLOR_BORDER
        else:
            # Интерполируем цвет hover
            if self.hover_progress > 0.01:
                bg = style["bg"]
                bg_h = style["bg_hover"]
                t = self.hover_progress
                bg = tuple(int(bg[i]*(1-t) + bg_h[i]*t) for i in range(3))
                if len(bg) == 3 and style.get("bg_top"):
                    # Градиентный hover
                    bg_top = style["bg_top"]
                    bg_bottom = style["bg_bottom"]
                    # Смешиваем
                    if self.hover_progress > 0.5:
                        bg_top_h = tuple(min(255, c+15) for c in bg_top)
                        bg_bottom_h = tuple(min(255, c+15) for c in bg_bottom)
                        t2 = (self.hover_progress - 0.5)*2
                        bg_top = tuple(int(bg_top[i]*(1-t2) + bg_top_h[i]*t2) for i in range(3))
                        bg_bottom = tuple(int(bg_bottom[i]*(1-t2) + bg_bottom_h[i]*t2) for i in range(3))
                    # Рисуем градиент
                    if self.gradient:
                        grad_surf = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
                        for y in range(self.rect.h):
                            tt = y / max(1, self.rect.h-1)
                            r = int(bg_top[0]*(1-tt) + bg_bottom[0]*tt)
                            g = int(bg_top[1]*(1-tt) + bg_bottom[1]*tt)
                            b = int(bg_top[2]*(1-tt) + bg_bottom[2]*tt)
                            pygame.draw.line(grad_surf, (r,g,b), (0,y), (self.rect.w,y))
                        surface.blit(grad_surf, self.rect.topleft)
                        pygame.draw.rect(surface, style["border"], self.rect, width=1, border_radius=8)
                        # Свечение при hover
                        if self.hovered:
                            glow = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
                            pygame.draw.rect(glow, (*style["bg"][:3], 30), (0,0,self.rect.w,self.rect.h), border_radius=8)
                            surface.blit(glow, self.rect.topleft)
                    else:
                        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
                        pygame.draw.rect(surface, style["border"], self.rect, width=1, border_radius=8)
                else:
                    pygame.draw.rect(surface, bg, self.rect, border_radius=8)
                    pygame.draw.rect(surface, style["border"], self.rect, width=1, border_radius=8)
            else:
                bg = style["bg"]
                if isinstance(bg, tuple) and len(bg)==3 and style.get("bg_top") and self.gradient:
                    # Градиент без hover
                    grad_surf = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
                    for y in range(self.rect.h):
                        tt = y / max(1, self.rect.h-1)
                        r = int(style["bg_top"][0]*(1-tt) + style["bg_bottom"][0]*tt)
                        g = int(style["bg_top"][1]*(1-tt) + style["bg_bottom"][1]*tt)
                        b = int(style["bg_top"][2]*(1-tt) + style["bg_bottom"][2]*tt)
                        pygame.draw.line(grad_surf, (r,g,b), (0,y), (self.rect.w,y))
                    surface.blit(grad_surf, self.rect.topleft)
                    pygame.draw.rect(surface, style["border"], self.rect, width=1, border_radius=8)
                else:
                    if isinstance(bg, tuple) and len(bg)==4:  # transparent
                        pass
                    else:
                        pygame.draw.rect(surface, bg if isinstance(bg,tuple) and len(bg)==3 else COLOR_PANEL_LIGHT, self.rect, border_radius=8)
                        pygame.draw.rect(surface, style["border"], self.rect, width=1, border_radius=8)
            tcol = style["text"]
            border = style["border"]
        
        # Эффект нажатия — сдвиг текста
        offset = 1 if self.pressed and self.enabled else 0
        
        # Текст + иконка
        full_text = f"{self.icon} {self.text}" if self.icon and self.icon not in self.text else self.text
        txt = font.render(full_text, True, tcol if 'tcol' in locals() else COLOR_TEXT)
        # Тень текста для глубины
        if self.enabled and self.style in ["primary", "danger", "success"]:
            shadow = font.render(full_text, True, (0,0,0,80))
            surface.blit(shadow, (self.rect.centerx - txt.get_width()//2 + 1, self.rect.centery - txt.get_height()//2 + 1 + offset))
        surface.blit(txt, (self.rect.centerx - txt.get_width()//2, self.rect.centery - txt.get_height()//2 + offset))
        
        # Тень кнопки
        if style.get("shadow") and self.enabled and not self.pressed:
            shadow_rect = pygame.Rect(self.rect.x+2, self.rect.y+2, self.rect.w, self.rect.h)
            s = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
            pygame.draw.rect(s, (0,0,0,60), (0,0,self.rect.w,self.rect.h), border_radius=8)
            # Не рисуем тень если уже есть градиент — излишне

# Для обратной совместимости — алиас
def draw_button(surface, rect, text, font, hovered=False, enabled=True, accent=False):
    style = "primary" if accent else "secondary"
    btn = Button(rect, text, accent=accent, enabled=enabled, style=style)
    btn.hovered = hovered
    btn.draw(surface, font)
    return font.render(text, True, (10,10,10) if accent else COLOR_TEXT)

# ── ТЕКСТОВОЕ ПОЛЕ ───────────────────────────────────────────────────────
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
        pygame.draw.rect(surface, col, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if self.active else 1, border_radius=8)
        txt = self.text if self.text else self.placeholder
        tcol = COLOR_TEXT if self.text else COLOR_TEXT_DIM
        surf = font.render(txt, True, tcol)
        surface.blit(surf, (self.rect.x+14, self.rect.y + (self.rect.h - surf.get_height())//2))
        if self.active:
            self.cursor_timer = (self.cursor_timer + 1) % 60
            if self.cursor_timer < 30:
                cx = self.rect.x + 14 + font.size(self.text)[0] + 2
                pygame.draw.line(surface, COLOR_ACCENT, (cx, self.rect.y+10), (cx, self.rect.y+self.rect.h-10), 2)

# ── ВЫПАДАЮЩИЙ СПИСОК ────────────────────────────────────────────────────
class Dropdown:
    def __init__(self, rect, options: List[Tuple[str, str]], selected: str = None, label: str = ""):
        """
        options: [(value, display_name), ...]
        selected: value
        """
        self.rect = pygame.Rect(rect)
        self.options = options
        self.selected = selected if selected is not None else (options[0][0] if options else None)
        self.label = label
        self.open = False
        self.hovered = False
        self.scroll = 0

    def get_display(self):
        for val, name in self.options:
            if val == self.selected:
                return name
        return self.options[0][1] if self.options else ""

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.rect.collidepoint(event.pos):
                    self.open = not self.open
                    return True
                elif self.open:
                    # Проверяем клик по опциям
                    for i, (val, name) in enumerate(self.options):
                        opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + i*32, self.rect.w, 32)
                        if opt_rect.collidepoint(event.pos):
                            self.selected = val
                            self.open = False
                            return True
                    # Клик вне — закрыть
                    self.open = False
        return False

    def draw(self, surface, font, draw_list=True):
        # Label
        if self.label:
            lbl_font = get_font(11, bold=True)
            lbl = lbl_font.render(self.label, True, COLOR_TEXT_DIM)
            surface.blit(lbl, (self.rect.x, self.rect.y - 16))
        
        # Основное поле
        bg = COLOR_PANEL_LIGHT if self.hovered or self.open else COLOR_PANEL
        border = COLOR_ACCENT if self.open else COLOR_BORDER
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=2 if self.open else 1, border_radius=6)
        
        # Текст — обрезаем если не влезает
        disp = self.get_display()
        txt_font = font
        # Подгоняем чтобы влезло в rect.w - 30 (10 паддинг + 20 стрелка)
        max_w = self.rect.w - 30
        if txt_font.size(disp)[0] > max_w:
            while len(disp) > 2 and txt_font.size(disp + "...")[0] > max_w:
                disp = disp[:-1]
            disp = disp + "..."
        txt = txt_font.render(disp, True, COLOR_TEXT)
        surface.blit(txt, (self.rect.x+10, self.rect.y + (self.rect.h - txt.get_height())//2))
        
        # Стрелка
        arrow = "▲" if self.open else "▼"
        arr_font = get_font(10)
        arr = arr_font.render(arrow, True, COLOR_TEXT_DIM)
        surface.blit(arr, (self.rect.right - 20, self.rect.y + (self.rect.h - arr.get_height())//2))
        
        # Выпадающий список — рисуем только если draw_list=True, иначе отложено (overlay)
        if self.open and draw_list:
            list_h = len(self.options) * 32
            list_rect = pygame.Rect(self.rect.x, self.rect.bottom + 2, self.rect.w, list_h)
            # Тень
            shadow = pygame.Surface((list_rect.w, list_rect.h), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0,0,0,120), (0,0,list_rect.w,list_rect.h), border_radius=6)
            surface.blit(shadow, (list_rect.x+2, list_rect.y+2))
            # Фон
            pygame.draw.rect(surface, COLOR_PANEL, list_rect, border_radius=6)
            pygame.draw.rect(surface, COLOR_BORDER, list_rect, width=1, border_radius=6)
            
            mouse = pygame.mouse.get_pos()
            for i, (val, name) in enumerate(self.options):
                opt_rect = pygame.Rect(list_rect.x, list_rect.y + i*32, list_rect.w, 32)
                hovered = opt_rect.collidepoint(mouse)
                is_selected = val == self.selected
                if hovered:
                    pygame.draw.rect(surface, COLOR_ACCENT if is_selected else COLOR_PANEL_LIGHT, opt_rect, border_radius=4)
                elif is_selected:
                    pygame.draw.rect(surface, (40,40,60), opt_rect, border_radius=4)
                
                opt_font = get_font(11, bold=is_selected)
                opt_txt = opt_font.render(name, True, COLOR_ACCENT if is_selected else COLOR_TEXT)
                surface.blit(opt_txt, (opt_rect.x+10, opt_rect.y + (opt_rect.h - opt_txt.get_height())//2))
                if is_selected:
                    check = get_font(10).render("✓", True, COLOR_ACCENT)
                    surface.blit(check, (opt_rect.right-20, opt_rect.y + (opt_rect.h - check.get_height())//2))

# ── ПЕРЕКЛЮЧАТЕЛЬ (TOGGLE) ──────────────────────────────────────────────
class Toggle:
    def __init__(self, rect, checked=False, label=""):
        self.rect = pygame.Rect(rect)
        self.checked = checked
        self.label = label
        self.hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked
                return True
        return False

    def draw(self, surface, font):
        # Фон переключателя
        bg_col = COLOR_ACCENT if self.checked else (60,60,70)
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=self.rect.h//2)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=self.rect.h//2)
        # Кружок
        circle_r = self.rect.h - 4
        cx = self.rect.right - circle_r//2 - 2 if self.checked else self.rect.x + circle_r//2 + 2
        cy = self.rect.centery
        pygame.draw.circle(surface, (255,255,255), (cx, cy), circle_r//2)
        # Тень
        pygame.draw.circle(surface, (0,0,0,40), (cx+1, cy+1), circle_r//2, width=1)
        # Label
        if self.label:
            lbl = font.render(self.label, True, COLOR_TEXT)
            surface.blit(lbl, (self.rect.right+10, self.rect.y + (self.rect.h - lbl.get_height())//2))

# ── СЛАЙДЕР ──────────────────────────────────────────────────────────────
class Slider:
    def __init__(self, rect, min_val=0.0, max_val=1.0, value=0.5, label=""):
        self.rect = pygame.Rect(rect)
        self.min = min_val
        self.max = max_val
        self.value = value
        self.label = label
        self.dragging = False
        self.hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_value(event.pos)
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_value(event.pos)
            return True
        return False

    def _update_value(self, pos):
        t = (pos[0] - self.rect.x) / max(1, self.rect.w)
        t = max(0, min(1, t))
        self.value = self.min + t * (self.max - self.min)

    def draw(self, surface, font):
        # Label
        if self.label:
            lbl = get_font(10, bold=True).render(self.label, True, COLOR_TEXT_DIM)
            surface.blit(lbl, (self.rect.x, self.rect.y - 15))
            val_txt = get_font(10).render(f"{int(self.value*100)}%", True, COLOR_ACCENT)
            surface.blit(val_txt, (self.rect.right - val_txt.get_width(), self.rect.y - 15))
        # Трек
        track_rect = pygame.Rect(self.rect.x, self.rect.centery-3, self.rect.w, 6)
        pygame.draw.rect(surface, (50,50,60), track_rect, border_radius=3)
        # Заполнение
        fill_w = int((self.value - self.min) / (self.max - self.min) * self.rect.w) if self.max != self.min else 0
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.centery-3, fill_w, 6)
            pygame.draw.rect(surface, COLOR_ACCENT, fill_rect, border_radius=3)
        # Ползунок
        t = (self.value - self.min) / (self.max - self.min) if self.max != self.min else 0
        cx = self.rect.x + int(t * self.rect.w)
        pygame.draw.circle(surface, COLOR_ACCENT, (cx, self.rect.centery), 10)
        pygame.draw.circle(surface, (255,255,255), (cx, self.rect.centery), 10, width=2)
        pygame.draw.circle(surface, (255,255,255), (cx, self.rect.centery), 4)

def draw_noir_overlay(surface):
    w, h = surface.get_size()
    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(80):
        alpha = int(80 * (i/80)**1.5)
        pygame.draw.rect(vignette, (0,0,0, alpha//8), (i, i, w-i*2, h-i*2), width=1, border_radius=12)
    surface.blit(vignette, (0,0))

# ── АВАТАРЫ — ИСПРАВЛЕНО ОТОБРАЖЕНИЕ ─────────────────────────────────────
_AVATAR_CACHE = {}

def _load_avatar_image(avatar_id, size):
    """Загружает аватара с aspect-fill (cover) вместо stretch."""
    cache_key = (avatar_id, size[0], size[1])
    if cache_key in _AVATAR_CACHE:
        return _AVATAR_CACHE[cache_key]
    candidates = [
        IMAGES_DIR / f"{avatar_id}.png",
        Path(__file__).parent.parent / "assets" / "images" / f"{avatar_id}.png",
        Path(f"src/detective_game/assets/images/{avatar_id}.png"),
    ]
    for path in candidates:
        if path.exists():
            try:
                orig = pygame.image.load(str(path))
                # Aspect-fill: масштабируем чтобы покрыть rect, затем кроп
                orig_w, orig_h = orig.get_size()
                target_w, target_h = size
                scale = max(target_w / orig_w, target_h / orig_h)
                new_w, new_h = int(orig_w * scale), int(orig_h * scale)
                scaled = pygame.transform.smoothscale(orig, (new_w, new_h))
                # Кроп по центру
                x_off = (new_w - target_w) // 2
                y_off = (new_h - target_h) // 2
                # Фокус чуть выше центра для портретов (лица)
                y_off = max(0, y_off - int(target_h * 0.1))
                cropped = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
                cropped.blit(scaled, (-x_off, -y_off))
                _AVATAR_CACHE[cache_key] = cropped
                return cropped
            except Exception as e:
                print(f"[Avatar] load failed {avatar_id}: {e}")
                continue
    return None

def draw_avatar(surface, rect, avatar_data, selected=False):
    """Рисует аватар — aspect-fill изображение или заглушку."""
    avatar_id = avatar_data.get("id", "")
    img = _load_avatar_image(avatar_id, (rect.w, rect.h))
    
    if img:
        # Создаем скругленную маску
        # Рисуем изображение с закруглением через маску
        mask_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(mask_surf, (255,255,255,255), (0,0,rect.w,rect.h), border_radius=10)
        # Накладываем изображение
        surface.blit(img, rect.topleft)
        # Маска границ (обрезаем углы)
        # Простой способ: рисуем рамку поверх
        border = COLOR_ACCENT if selected else COLOR_BORDER
        border_w = 3 if selected else 1
        pygame.draw.rect(surface, border, rect, width=border_w, border_radius=10)
        # Подсветка выбранного
        if selected:
            glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(glow, (212,175,55,40), (0,0,rect.w,rect.h), border_radius=10)
            surface.blit(glow, rect.topleft)
            # Внешнее свечение
            pygame.draw.rect(surface, COLOR_ACCENT, rect.inflate(4,4), width=2, border_radius=12)
    else:
        color = avatar_data.get("color", (80,80,100))
        border = COLOR_ACCENT if selected else COLOR_BORDER
        pygame.draw.rect(surface, color, rect, border_radius=10)
        pygame.draw.rect(surface, border, rect, width=3 if selected else 1, border_radius=10)
        font_big = get_font(28, bold=True)
        init = avatar_data["name"][0]
        txt = font_big.render(init, True, (255,255,255))
        surface.blit(txt, txt.get_rect(center=rect.center))
    
    # Плашка с именем — градиентная
    font_small = get_font(10, bold=True)
    name_surf = font_small.render(avatar_data["name"], True, (255,255,255))
    bg_rect = pygame.Rect(rect.x, rect.bottom - 22, rect.w, 22)
    # Градиент плашки
    grad = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
    for y in range(bg_rect.h):
        alpha = int(200 * (1 - y/bg_rect.h*0.3))
        pygame.draw.line(grad, (0,0,0,alpha), (0,y), (bg_rect.w,y))
    surface.blit(grad, bg_rect.topleft)
    pygame.draw.rect(surface, (0,0,0,120), bg_rect, width=1, border_radius=4)
    surface.blit(name_surf, name_surf.get_rect(center=bg_rect.center))
    
    if selected:
        check_font = get_font(11, bold=True)
        check = check_font.render("✓", True, (0,0,0))
        bg = pygame.Surface((20,20), pygame.SRCALPHA)
        pygame.draw.circle(bg, COLOR_ACCENT, (10,10), 10)
        surface.blit(bg, (rect.right - 14, rect.y + 6))
        surface.blit(check, check.get_rect(center=(rect.right - 4, rect.y + 16)))

def draw_map_pin(surface, pos, location, visited=False, current=False):
    x, y = pos
    type_colors = {
        "hub": (200,180,60), "police": (70,100,180), "crime": (200,60,60),
        "bar": (180,120,40), "apartment": (80,150,80), "public": (100,140,160),
        "bank": (160,140,60), "vault": (140,140,140), "office": (100,100,140),
        "mansion": (140,100,60), "shop": (120,100,160), "warehouse": (90,90,90), "port": (50,120,140),
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
        font = get_font(11, bold=True)
        txt = font.render("✓", True, (255,255,255))
        surface.blit(txt, (x+8, y-10))
    font_small = get_font(10, bold=True)
    name = location["name"]
    txt = font_small.render(name, True, COLOR_TEXT if visited else COLOR_TEXT_DIM)
    bg = pygame.Surface((txt.get_width()+8, txt.get_height()+4), pygame.SRCALPHA)
    pygame.draw.rect(bg, (0,0,0,180), (0,0,bg.get_width(), bg.get_height()), border_radius=4)
    surface.blit(bg, (x - bg.get_width()//2, y + radius + 4))
    surface.blit(txt, (x - txt.get_width()//2, y + radius + 6))

# ── ПРОГРЕСС-БАР ─────────────────────────────────────────────────────────
def draw_progress_bar(surface, rect, progress: float, color=COLOR_ACCENT, bg_color=(50,50,60), radius=4):
    """Рисует прогресс-бар 0.0-1.0."""
    pygame.draw.rect(surface, bg_color, rect, border_radius=radius)
    if progress > 0:
        fill_w = int(rect.w * max(0, min(1, progress)))
        fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.h)
        # Градиент
        for x in range(fill_w):
            t = x / max(1, fill_w-1)
            r = int(color[0] * (0.8 + 0.2*t))
            g = int(color[1] * (0.8 + 0.2*t))
            b = int(color[2] * (0.8 + 0.2*t))
            pygame.draw.line(surface, (r,g,b), (fill_rect.x+x, fill_rect.y), (fill_rect.x+x, fill_rect.y+fill_rect.h))
        pygame.draw.rect(surface, color, fill_rect, border_radius=radius)
    # Текст процента
    if progress > 0.05:
        pct_font = get_font(9, bold=True)
        pct = pct_font.render(f"{int(progress*100)}%", True, (255,255,255))
        surface.blit(pct, pct.get_rect(center=rect.center))
