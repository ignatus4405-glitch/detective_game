"""Витрина дел с постерами, выбором сложности и краткими правилами."""
from __future__ import annotations

import pygame

from .. import deduction
from ..config import *
from ..data import case_cover
from .artwork import blit_rounded, cover_image
from .widgets import Button, draw_panel, draw_text_wrapped, get_font


def draw_case_select(game) -> None:
    screen = game.screen
    cases = game.cases
    game.case_index = max(0, min(game.case_index, len(cases) - 1))
    case = cases[game.case_index]
    header = pygame.Rect(20, 15, 1240, 54)
    draw_panel(screen, header)
    screen.blit(get_font(22, bold=True).render("АРХИВ ДЕЛ", True, COLOR_ACCENT), (40, 29))
    sub = get_font(11).render(f"{len(cases)} дел · новые истории отмечены NEW", True, COLOR_TEXT_DIM)
    screen.blit(sub, (header.right - sub.get_width() - 20, 35))
    left = pygame.Rect(20, 84, 350, 572)
    right = pygame.Rect(386, 84, 874, 572)
    draw_panel(screen, left)
    draw_panel(screen, right)
    rects = {"cases": {}, "modes": {}, "start": None, "back": None}
    y = left.y + 14
    row_h = 104
    for idx, item in enumerate(cases):
        rect = pygame.Rect(left.x + 12, y, left.w - 24, row_h)
        rects["cases"][idx] = rect
        active = idx == game.case_index
        pygame.draw.rect(screen, (55, 47, 30) if active else (29, 31, 40), rect, border_radius=7)
        pygame.draw.rect(screen, COLOR_ACCENT if active else COLOR_BORDER, rect, width=2 if active else 1, border_radius=7)
        thumb = pygame.Rect(rect.x + 10, rect.y + 10, 92, row_h - 20)
        img = cover_image(case_cover(item), thumb.size, dim=0.15)
        blit_rounded(screen, img, thumb, radius=5)
        tx = thumb.right + 12
        title = item["title"]
        draw_text_wrapped(screen, title, get_font(13, bold=True), COLOR_TEXT, pygame.Rect(tx, rect.y + 10, rect.right - tx - 10, 36))
        meta = f"{item.get('difficulty', '')} · {item.get('duration', '')}"
        screen.blit(get_font(10).render(meta, True, COLOR_TEXT_DIM), (tx, rect.y + 52))
        tag = "NEW" if item.get("is_new") else ("ПРОЙДЕНО" if item["id"] in game.state.completed_cases else "ДОСТУПНО")
        color = COLOR_GREEN if tag != "ДОСТУПНО" else COLOR_TEXT_DARK
        screen.blit(get_font(9, bold=True).render(tag, True, color), (tx, rect.y + 72))
        y += row_h + 8
    poster = pygame.Rect(right.x + 16, right.y + 16, right.w - 32, 238)
    img = cover_image(case_cover(case), poster.size, dim=0.18)
    if blit_rounded(screen, img, poster, radius=8):
        shade = pygame.Surface((poster.w, 90), pygame.SRCALPHA)
        for row in range(90):
            pygame.draw.line(shade, (8, 10, 16, int(220 * row / 89)), (0, row), (poster.w, row))
        screen.blit(shade, (poster.x, poster.bottom - 90))
    pygame.draw.rect(screen, COLOR_BORDER, poster, width=1, border_radius=8)
    screen.blit(get_font(26, bold=True).render(case["title"], True, COLOR_TEXT), (poster.x + 20, poster.bottom - 62))
    screen.blit(get_font(12).render(case.get("subtitle", ""), True, COLOR_ACCENT), (poster.x + 20, poster.bottom - 28))
    desc_y = poster.bottom + 16
    draw_text_wrapped(screen, case.get("description", ""), get_font(13), COLOR_TEXT, pygame.Rect(right.x + 24, desc_y, right.w - 48, 62))
    mode_y = desc_y + 76
    screen.blit(get_font(11, bold=True).render("РЕЖИМ РАССЛЕДОВАНИЯ", True, COLOR_TEXT_DIM), (right.x + 24, mode_y))
    supported = deduction.supported(case)
    x = right.x + 24
    for mode, label in (("classic", "КЛАССИКА"), ("expert", "ЭКСПЕРТ")):
        rect = pygame.Rect(x, mode_y + 22, 180, 38)
        rects["modes"][mode] = rect
        active = (game.case_mode if supported else "classic") == mode
        pygame.draw.rect(screen, (62, 52, 30) if active else (31, 33, 42), rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_ACCENT if active else COLOR_BORDER, rect, width=2 if active else 1, border_radius=6)
        t = get_font(12, bold=True).render(label, True, COLOR_ACCENT if active else COLOR_TEXT_DIM)
        screen.blit(t, t.get_rect(center=rect.center))
        x += 192
    rules = ("Черновик доски без подсказок · перекрёстное алиби · пять звеньев обвинения · без таймера реплик"
             if supported and game.case_mode == "expert" else
             "Подсказки на доске · обычные допросы · обвинение по имени, мотиву и способу")
    if not supported:
        rules = "Учебное дело: короткие диалоги, подсказки и мягкие правила."
    draw_text_wrapped(screen, rules, get_font(11), COLOR_TEXT_DIM, pygame.Rect(right.x + 420, mode_y + 18, right.w - 444, 54))
    info_y = mode_y + 82
    chips = [f"{len(case.get('locations', []))} локаций", f"{len(case.get('clues', []))} улик", f"{len(case.get('suspects', []))} подозреваемых"]
    x = right.x + 24
    for text in chips:
        t = get_font(10, bold=True).render(text, True, COLOR_ACCENT)
        rect = pygame.Rect(x, info_y, t.get_width() + 20, 24)
        pygame.draw.rect(screen, (37, 34, 27), rect, border_radius=12)
        screen.blit(t, (rect.x + 10, rect.y + 6))
        x += rect.w + 10
    rects["start"] = pygame.Rect(right.right - 280, right.bottom - 62, 256, 42)
    Button(rects["start"], "НАЧАТЬ ДЕЛО →", accent=True).draw(screen, get_font(13, bold=True))
    rects["back"] = pygame.Rect(20, 670, 160, 34)
    Button(rects["back"], "← В МЕНЮ").draw(screen, get_font(12, bold=True))
    game.case_select_rects = rects
