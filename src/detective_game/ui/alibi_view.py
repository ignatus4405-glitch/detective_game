"""Перекрёстное алиби: источники слева, сетка мест справа."""
from __future__ import annotations

import pygame

from .. import deduction
from ..config import *
from ..save_system import save_game
from .widgets import Button, draw_panel, draw_text_wrapped, get_font


def draw(game) -> None:
    case = game.current_case or {}
    spec = deduction.alibi_spec(case) or {}
    screen = game.screen
    header = pygame.Rect(20, 15, 1240, 54)
    draw_panel(screen, header)
    screen.blit(get_font(22, bold=True).render("ПЕРЕКРЁСТНОЕ АЛИБИ", True, COLOR_ACCENT), (40, 29))
    chip = get_font(11, bold=True).render("ЭКСПЕРТ · ВРЕМЯ НЕ ИДЁТ", True, COLOR_GREEN)
    screen.blit(chip, (header.right - chip.get_width() - 20, 35))
    main = pygame.Rect(20, 82, 1240, 574)
    draw_panel(screen, main)
    draw_text_wrapped(screen, spec.get("question", ""), get_font(14, bold=True), COLOR_TEXT, pygame.Rect(40, 96, 1200, 42))
    left = pygame.Rect(40, 148, 650, 430)
    right = pygame.Rect(710, 148, 530, 430)
    draw_panel(screen, left, color=(22, 24, 31))
    draw_panel(screen, right, color=(22, 24, 31))
    screen.blit(get_font(12, bold=True).render("ИСТОЧНИКИ", True, COLOR_ACCENT), (left.x + 14, left.y + 12))
    facts = deduction.alibi_facts(case, game.state)
    scroll = max(0, min(getattr(game, "alibi_scroll", 0), max(0, len(facts) - 4)))
    game.alibi_scroll = scroll
    y = left.y + 38
    for fact in facts[scroll:scroll + 4]:
        row = pygame.Rect(left.x + 12, y, left.w - 24, 80)
        pygame.draw.rect(screen, (31, 34, 42) if fact["unlocked"] else (25, 26, 32), row, border_radius=6)
        color = COLOR_TEXT if fact["unlocked"] else COLOR_TEXT_DARK
        text = fact["text"] if fact["unlocked"] else "Источник ещё не найден: " + fact["source_name"]
        draw_text_wrapped(screen, text, get_font(11), color, pygame.Rect(row.x + 10, row.y + 8, row.w - 20, 52))
        src = get_font(9, bold=True).render(("✓ " if fact["unlocked"] else "• ") + fact["source_name"], True, COLOR_GREEN if fact["unlocked"] else COLOR_TEXT_DARK)
        screen.blit(src, (row.x + 10, row.bottom - 20))
        y += 86
    game.alibi_rects = {"cells": {}}
    if len(facts) > 4:
        for key, label, x in (("up", "↑", left.right - 70), ("down", "↓", left.right - 38)):
            rect = pygame.Rect(x, left.bottom - 30, 28, 22)
            game.alibi_rects[key] = rect
            Button(rect, label).draw(screen, get_font(12, bold=True))
    screen.blit(get_font(12, bold=True).render("КТО ГДЕ БЫЛ", True, COLOR_ACCENT), (right.x + 14, right.y + 12))
    people, places = spec.get("people", []), spec.get("places", [])
    grid_x, grid_y = right.x + 150, right.y + 62
    cell_w, cell_h = 116, 64
    for j, place in enumerate(places):
        lab = get_font(11, bold=True).render(place["name"], True, COLOR_TEXT_DIM)
        screen.blit(lab, lab.get_rect(center=(grid_x + j * cell_w + cell_w // 2, grid_y - 18)))
    answers = game.state.alibi_assignments or {}
    for i, person in enumerate(people):
        lab = get_font(13, bold=True).render(person["name"], True, COLOR_TEXT)
        screen.blit(lab, (right.x + 18, grid_y + i * cell_h + 22))
        for j, place in enumerate(places):
            rect = pygame.Rect(grid_x + j * cell_w, grid_y + i * cell_h, cell_w - 8, cell_h - 8)
            game.alibi_rects["cells"][(person["id"], place["id"])] = rect
            active = answers.get(person["id"]) == place["id"]
            pygame.draw.rect(screen, (62, 53, 31) if active else (34, 36, 45), rect, border_radius=6)
            pygame.draw.rect(screen, COLOR_ACCENT if active else COLOR_BORDER, rect, width=2 if active else 1, border_radius=6)
            mark = get_font(18, bold=True).render("●" if active else "·", True, COLOR_ACCENT if active else COLOR_TEXT_DARK)
            screen.blit(mark, mark.get_rect(center=rect.center))
    note = "Одно место — один человек. Повторный клик снимает отметку."
    draw_text_wrapped(screen, note, get_font(10), COLOR_TEXT_DIM, pygame.Rect(right.x + 18, right.y + 278, right.w - 36, 34))
    message = getattr(game, "alibi_message", "")
    if message:
        draw_text_wrapped(screen, message, get_font(11), COLOR_GREEN if game.state.alibi_solved else COLOR_ACCENT, pygame.Rect(right.x + 18, right.y + 318, right.w - 36, 96))
    game.alibi_rects["back"] = pygame.Rect(40, 668, 160, 36)
    game.alibi_rects["check"] = pygame.Rect(1000, 668, 240, 36)
    Button(game.alibi_rects["back"], "← НАЗАД").draw(screen, get_font(12, bold=True))
    Button(game.alibi_rects["check"], "ПРОВЕРИТЬ АЛИБИ", accent=True, enabled=deduction.alibi_ready(case, game.state) and not game.state.alibi_solved).draw(screen, get_font(12, bold=True))


def handle_click(game, pos) -> bool:
    rects = getattr(game, "alibi_rects", {}) or {}
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.screen_name = getattr(game, "alibi_return", "notebook")
        return True
    for key, delta in (("up", -1), ("down", 1)):
        if rects.get(key) and rects[key].collidepoint(pos):
            game.alibi_scroll = max(0, getattr(game, "alibi_scroll", 0) + delta)
            return True
    for (person, place), rect in (rects.get("cells") or {}).items():
        if rect.collidepoint(pos) and not game.state.alibi_solved:
            deduction.alibi_assign(game.state, person, place)
            game.alibi_message = ""
            save_game(game.state)
            return True
    if rects.get("check") and rects["check"].collidepoint(pos):
        result = deduction.alibi_check(game.current_case, game.state)
        game.alibi_message = result.get("message", "")
        game.audio.play_sfx("success" if result["status"] in ("ok", "already") else "tick")
        save_game(game.state)
        return True
    return False


def handle_key(game, event) -> bool:
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        game.screen_name = getattr(game, "alibi_return", "notebook")
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
        game.alibi_scroll = max(0, getattr(game, "alibi_scroll", 0) + (-1 if event.button == 4 else 1))
        return True
    return False
