"""Макет экранов игры в логических координатах.

Одна правда для отрисовки и обработки кликов: раньше экран кастомизации
считал прямоугольники дважды — в `draw_customization` от логического холста
1280×720, а в `handle_event` от физического размера окна. Из-за этого на
любом масштабе (fullscreen, 1920×1080, letterbox) портреты «не нажимались»,
а кнопки уезжали.
"""

from dataclasses import dataclass, field
from math import ceil
from typing import List, Optional, Sequence, Tuple

import pygame

Point = Tuple[int, int]


@dataclass
class CustomizationLayout:
    """Прямоугольники экрана «Кастомизация детектива» (логические координаты)."""

    width: int
    height: int
    header: pygame.Rect
    panel: pygame.Rect
    name_label: Point
    name_input: pygame.Rect
    name_button: pygame.Rect
    name_hint: Point
    divider_y: int
    avatars_label: Point
    avatars_hint: Point
    avatar_rects: List[pygame.Rect] = field(default_factory=list)
    avatar_size: int = 0
    desc: pygame.Rect = field(default_factory=pygame.Rect)
    past_label: Point = (0, 0)
    bg_rects: List[pygame.Rect] = field(default_factory=list)
    bg_hint: pygame.Rect = field(default_factory=pygame.Rect)
    btn_back: pygame.Rect = field(default_factory=pygame.Rect)
    btn_save: pygame.Rect = field(default_factory=pygame.Rect)

    def avatar_at(self, pos) -> Optional[int]:
        """Индекс портрета под точкой (логические координаты) или None."""
        if not pos:
            return None
        for i, rect in enumerate(self.avatar_rects):
            if rect.collidepoint(pos):
                return i
        return None

    def background_at(self, pos) -> Optional[int]:
        """Индекс кнопки «Прошлое» под точкой или None."""
        if not pos:
            return None
        for i, rect in enumerate(self.bg_rects):
            if rect.collidepoint(pos):
                return i
        return None


def _clamp(value, low, high):
    return max(low, min(high, value))


def customization_layout(
    width: int = 1280,
    height: int = 720,
    avatars: int = 6,
    backgrounds: int = 3,
    columns: int = 3,
) -> CustomizationLayout:
    """Считает раскладку кастомизации, которая гарантированно не пересекается.

    Порядок блоков сверху вниз: заголовок → панель [имя → сетка портретов →
    описание → прошлое → подсказка → кнопки «Назад»/«Сохранить»]. Размер
    портретов вычисляется от свободного места, поэтому блоки не наезжают друг
    на друга ни на 720p, ни на больших окнах.
    """
    width = max(640, int(width))
    height = max(480, int(height))
    avatars = max(1, int(avatars))
    backgrounds = max(1, int(backgrounds))
    columns = _clamp(int(columns), 1, avatars)

    margin_x = _clamp(width // 40, 12, 30)
    header_top = 15
    header_h = 50
    panel_top = header_top + header_h + 10
    panel_h = max(360, height - panel_top - 25)

    header = pygame.Rect(margin_x, header_top, width - 2 * margin_x, header_h)
    panel = pygame.Rect(margin_x, panel_top, width - 2 * margin_x, panel_h)

    pad = 25
    inner_x = panel.x + pad
    inner_w = panel.w - 2 * pad

    # --- Имя детектива ---
    name_label = (inner_x, panel.y + 14)
    name_btn_w = 120
    name_input = pygame.Rect(inner_x, panel.y + 40, inner_w - name_btn_w - 10, 40)
    name_button = pygame.Rect(name_input.right + 10, name_input.y, name_btn_w, name_input.h)
    name_hint = (inner_x, name_input.bottom + 6)
    divider_y = name_hint[1] + 18

    # --- Заголовок сетки портретов ---
    avatars_label = (inner_x, divider_y + 10)
    avatars_hint = (inner_x, avatars_label[1] + 20)
    grid_top = avatars_hint[1] + 18

    # --- Нижний блок (футер) ---
    footer_h = 38
    btn_back = pygame.Rect(inner_x, panel.bottom - 8 - footer_h, 160, footer_h)
    btn_save = pygame.Rect(panel.right - pad - 170, btn_back.y, 170, footer_h)
    bg_hint = pygame.Rect(inner_x, btn_back.y - 6 - 16, inner_w, 16)

    bg_btn_h = 34
    bg_gap = 15
    bg_btn_w = min(150, (inner_w - (backgrounds - 1) * bg_gap) // backgrounds)
    bg_total_w = backgrounds * bg_btn_w + (backgrounds - 1) * bg_gap
    bg_y = bg_hint.y - 8 - bg_btn_h
    bg_start_x = panel.centerx - bg_total_w // 2
    bg_rects = [
        pygame.Rect(bg_start_x + i * (bg_btn_w + bg_gap), bg_y, bg_btn_w, bg_btn_h)
        for i in range(backgrounds)
    ]
    past_label = (inner_x, bg_y - 22)

    desc_h = 28
    desc = pygame.Rect(inner_x, past_label[1] - 8 - desc_h, inner_w, desc_h)
    grid_bottom = desc.y - 10

    # --- Сетка портретов: размер подбирается под свободное место ---
    gap = 12
    rows = ceil(avatars / columns)
    avail_w = (inner_w - (columns - 1) * gap) // columns
    avail_h = (grid_bottom - grid_top - (rows - 1) * gap) // rows
    size = max(48, min(avail_w, avail_h))
    total_w = columns * size + (columns - 1) * gap
    total_h = rows * size + (rows - 1) * gap
    start_x = panel.centerx - total_w // 2
    start_y = grid_top + max(0, (grid_bottom - grid_top - total_h) // 2)
    avatar_rects = [
        pygame.Rect(
            start_x + (i % columns) * (size + gap),
            start_y + (i // columns) * (size + gap),
            size,
            size,
        )
        for i in range(avatars)
    ]

    return CustomizationLayout(
        width=width,
        height=height,
        header=header,
        panel=panel,
        name_label=name_label,
        name_input=name_input,
        name_button=name_button,
        name_hint=name_hint,
        divider_y=divider_y,
        avatars_label=avatars_label,
        avatars_hint=avatars_hint,
        avatar_rects=avatar_rects,
        avatar_size=size,
        desc=desc,
        past_label=past_label,
        bg_rects=bg_rects,
        bg_hint=bg_hint,
        btn_back=btn_back,
        btn_save=btn_save,
    )


def rects_overlap(a: pygame.Rect, b: pygame.Rect) -> bool:
    """Пересекаются ли прямоугольники (общая площадь > 0)."""
    return bool(a.colliderect(b))


def layout_contains(outer: pygame.Rect, inner: pygame.Rect) -> bool:
    """Полностью ли `inner` внутри `outer`."""
    return outer.contains(inner)


def ensure_unique_hits(rects: Sequence[pygame.Rect]) -> bool:
    """Центр каждого прямоугольника попадает только в него самого."""
    for i, rect in enumerate(rects):
        for j, other in enumerate(rects):
            if i == j:
                continue
            if other.collidepoint(rect.center):
                return False
    return True


@dataclass
class CaseCard:
    """Геометрия карточки дела: содержимое масштабируется вместе с карточкой."""

    rect: pygame.Rect
    poster: pygame.Rect
    title_pos: Point
    subtitle_pos: Point
    meta_pos: Point
    desc: pygame.Rect
    intro: pygame.Rect
    button: pygame.Rect


@dataclass
class CaseSelectLayout:
    header: pygame.Rect
    cards: List[CaseCard]
    btn_back: pygame.Rect


def case_select_layout(width: int = 1280, height: int = 720, count: int = 3) -> CaseSelectLayout:
    """Раскладка экрана выбора дела: все карточки видны на любом разрешении.

    Раньше карточки шли фиксированным шагом 620px от левого края, поэтому при
    1280px третье дело просто не рисовалось (и не нажималось).
    """
    width = max(640, int(width))
    height = max(480, int(height))
    header = pygame.Rect(30, 20, width - 60, 60)
    margin = _clamp(width // 40, 12, 30)
    top = header.bottom + 15
    bottom = height - 55
    cols = _clamp(int(count), 1, 3)
    if width < 900:
        cols = min(cols, 2)
    if width < 620:
        cols = 1
    rows = ceil(max(1, count) / cols)
    gap = 16
    card_w = (width - 2 * margin - (cols - 1) * gap) // cols
    card_h = (bottom - top - (rows - 1) * gap) // rows
    cards: List[CaseCard] = []
    for i in range(count):
        row, col = divmod(i, cols)
        rect = pygame.Rect(margin + col * (card_w + gap), top + row * (card_h + gap), card_w, card_h)
        pad = 14
        poster_h = _clamp(int(card_h * 0.30), 48, 180)
        poster = pygame.Rect(rect.x + pad, rect.y + pad, rect.w - 2 * pad, poster_h)
        text_x = rect.x + pad + 4
        title_pos = (text_x, poster.bottom + 8)
        subtitle_pos = (text_x, title_pos[1] + 24)
        meta_pos = (text_x, subtitle_pos[1] + 20)
        button = pygame.Rect(rect.x + pad + 4, rect.bottom - 8 - 34, rect.w - 2 * pad - 8, 34)
        desc_top = meta_pos[1] + 18
        # интро-панель показываем, только если реально есть место над кнопкой
        intro_h = int(card_h * 0.16)
        intro_top = button.y - 10 - intro_h
        if intro_top - desc_top >= 70:
            intro = pygame.Rect(rect.x + pad, intro_top, rect.w - 2 * pad, intro_h)
            desc_bottom = intro.y - 8
        else:
            intro = pygame.Rect(rect.x + pad, button.y, rect.w - 2 * pad, 0)
            desc_bottom = button.y - 8
        desc = pygame.Rect(text_x, desc_top, rect.w - 2 * pad - 8, max(0, desc_bottom - desc_top))
        cards.append(
            CaseCard(
                rect=rect,
                poster=poster,
                title_pos=title_pos,
                subtitle_pos=subtitle_pos,
                meta_pos=meta_pos,
                desc=desc,
                intro=intro,
                button=button,
            )
        )
    btn_back = pygame.Rect(margin, height - 42, 150, 30)
    return CaseSelectLayout(header=header, cards=cards, btn_back=btn_back)


@dataclass
class SettingsLayout:
    header: pygame.Rect
    back: pygame.Rect
    left: pygame.Rect
    right: pygame.Rect
    left_bottom: int
    apply: pygame.Rect
    reset: pygame.Rect
    wipe: pygame.Rect
    right_bottom: int
    check_updates: pygame.Rect


def settings_layout(width: int = 1280, height: int = 720) -> SettingsLayout:
    """Раскладка экрана настроек: кнопки внутри панелей.

    Раньше «СБРОСИТЬ ПРОГРЕСС» рисовалась от `right.bottom - 48`, но при
    пересчёте панели на нестандартной высоте окна она вылезала за панель —
    на скриншотах обрезана снизу.
    """
    width = max(640, int(width))
    height = max(480, int(height))
    margin = _clamp(width // 40, 10, 30)
    header = pygame.Rect(margin, 12, width - 2 * margin, 54)
    panes_top = header.bottom + 12
    panes_bottom = height - 12
    panes_h = panes_bottom - panes_top
    left = pygame.Rect(margin, panes_top, width // 2 - margin - 10, panes_h)
    right = pygame.Rect(width // 2 + 10, panes_top, width - (width // 2 + 10) - margin, panes_h)

    btn_h = 34
    gap = 8
    inner_w = left.w - 2 * 20
    half_w = (inner_w - gap) // 2
    btn_y = left.bottom - 10 - btn_h
    apply = pygame.Rect(left.x + 20, btn_y, half_w, btn_h)
    reset = pygame.Rect(apply.right + gap, btn_y, half_w, btn_h)
    wipe = pygame.Rect(right.x + 16, right.bottom - 10 - btn_h, right.w - 32, btn_h)

    back = pygame.Rect(header.x + 10, header.y + 12, 110, 30)
    check_updates = pygame.Rect(right.x + 20, right.bottom - 10 - btn_h - 46, right.w - 40, 36)
    return SettingsLayout(
        header=header,
        back=back,
        left=left,
        right=right,
        left_bottom=btn_y,
        apply=apply,
        reset=reset,
        wipe=wipe,
        right_bottom=wipe.y,
        check_updates=check_updates,
    )
