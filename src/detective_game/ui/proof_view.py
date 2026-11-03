"""Финальная доказательная цепочка: пять звеньев и опровержение версии защиты."""
from __future__ import annotations

import pygame

from .. import deduction, expertise
from ..config import *
from ..save_system import save_game
from .widgets import Button, draw_panel, draw_text_wrapped, get_font


def draw(game) -> None:
    case = game.current_case or {}
    spec = deduction.proof_spec(case)
    screen = game.screen
    header = pygame.Rect(20, 15, 1240, 54)
    draw_panel(screen, header)
    screen.blit(get_font(22, bold=True).render("ДОКАЗАТЕЛЬНАЯ ЦЕПОЧКА", True, COLOR_ACCENT), (40, 29))
    chip = get_font(11, bold=True).render("ЭКСПЕРТ · ПРОВЕРКА ТОЛЬКО В СУДЕ", True, COLOR_GREEN)
    screen.blit(chip, (header.right - chip.get_width() - 20, 35))
    main = pygame.Rect(20, 82, 1240, 574)
    draw_panel(screen, main)
    suspect = next((s for s in case.get("suspects", []) if s["id"] == game.accusation_selected), {})
    draw_text_wrapped(screen, f"Обвиняемый: {suspect.get('name', '—')}. Заполните пять звеньев и выберите, что разрушает версию защиты.", get_font(13), COLOR_TEXT, pygame.Rect(40, 96, 1200, 38))
    game.proof_rects = {"slots": {}, "clues": {}, "alternatives": {}}
    left = pygame.Rect(40, 144, 690, 350)
    right = pygame.Rect(750, 144, 490, 350)
    draw_panel(screen, left, color=(22, 24, 31))
    draw_panel(screen, right, color=(22, 24, 31))
    selected_slot = getattr(game, "proof_slot", "motive")
    y = left.y + 12
    for slot, num, label, question in deduction.SLOTS:
        rect = pygame.Rect(left.x + 12, y, left.w - 24, 60)
        game.proof_rects["slots"][slot] = rect
        active = slot == selected_slot
        pygame.draw.rect(screen, (55, 47, 29) if active else (32, 34, 42), rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_ACCENT if active else COLOR_BORDER, rect, width=2 if active else 1, border_radius=6)
        draw_text_wrapped(screen, f"{num}  {label}", get_font(12, bold=True), COLOR_ACCENT if active else COLOR_TEXT, pygame.Rect(rect.x + 12, rect.y + 8, 142, 44))
        clue_id = (game.state.proof_slots or {}).get(slot)
        clue = next((c for c in case.get("clues", []) if c["id"] == clue_id), None)
        text = clue["title"] if clue else question
        draw_text_wrapped(screen, text, get_font(11), COLOR_TEXT if clue else COLOR_TEXT_DIM, pygame.Rect(rect.x + 170, rect.y + 8, rect.w - 184, 44))
        y += 66
    screen.blit(get_font(12, bold=True).render("ДОПУСТИМЫЕ УЛИКИ", True, COLOR_ACCENT), (right.x + 14, right.y + 12))
    clues = [c for c in case.get("clues", []) if c["id"] in expertise.court_clues(case, game.state)]
    scroll = max(0, min(getattr(game, "proof_scroll", 0), max(0, len(clues) - 6)))
    game.proof_scroll = scroll
    y = right.y + 38
    for clue in clues[scroll:scroll + 6]:
        rect = pygame.Rect(right.x + 12, y, right.w - 24, 38)
        game.proof_rects["clues"][clue["id"]] = rect
        used = clue["id"] in (game.state.proof_slots or {}).values()
        pygame.draw.rect(screen, (43, 42, 34) if used else (34, 36, 45), rect, border_radius=5)
        pygame.draw.rect(screen, COLOR_ACCENT_DIM if used else COLOR_BORDER, rect, width=1, border_radius=5)
        draw_text_wrapped(screen, clue["title"], get_font(11, bold=used), COLOR_TEXT, pygame.Rect(rect.x + 10, rect.y + 5, rect.w - 20, 28))
        y += 42
    if len(clues) > 6:
        for key, label, x in (("up", "↑", right.right - 70), ("down", "↓", right.right - 38)):
            rect = pygame.Rect(x, right.bottom - 30, 28, 22)
            game.proof_rects[key] = rect
            Button(rect, label).draw(screen, get_font(12, bold=True))
    alt_y = 510
    screen.blit(get_font(12, bold=True).render("ВЕРСИЯ ЗАЩИТЫ: ЧТО ЕЁ ОПРОВЕРГАЕТ?", True, COLOR_ACCENT), (40, alt_y))
    x = 40
    alternatives = spec.get("alternatives", [])
    width = (1200 - 16 * (len(alternatives) - 1)) // max(1, len(alternatives))
    for alt in alternatives:
        rect = pygame.Rect(x, alt_y + 24, width, 76)
        game.proof_rects["alternatives"][alt["id"]] = rect
        active = game.state.proof_counter == alt["id"]
        pygame.draw.rect(screen, (58, 49, 30) if active else (30, 32, 40), rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_ACCENT if active else COLOR_BORDER, rect, width=2 if active else 1, border_radius=6)
        draw_text_wrapped(screen, alt["text"], get_font(11), COLOR_TEXT, pygame.Rect(rect.x + 10, rect.y + 8, rect.w - 20, 60))
        x += width + 16
    status = "Алиби подтверждено" if game.state.alibi_solved else "Алиби ещё не подтверждено"
    screen.blit(get_font(11, bold=True).render(status, True, COLOR_GREEN if game.state.alibi_solved else COLOR_ACCENT), (40, 626))
    game.proof_rects["back"] = pygame.Rect(40, 668, 160, 36)
    game.proof_rects["alibi"] = pygame.Rect(220, 668, 180, 36)
    game.proof_rects["submit"] = pygame.Rect(970, 668, 270, 36)
    Button(game.proof_rects["back"], "← НАЗАД").draw(screen, get_font(12, bold=True))
    Button(game.proof_rects["alibi"], "К АЛИБИ").draw(screen, get_font(12, bold=True))
    Button(game.proof_rects["submit"], "ПРЕДЪЯВИТЬ В СУДЕ", accent=True, enabled=deduction.proof_ready(case, game.state)).draw(screen, get_font(12, bold=True))


def handle_click(game, pos) -> bool:
    rects = getattr(game, "proof_rects", {}) or {}
    for slot, rect in (rects.get("slots") or {}).items():
        if rect.collidepoint(pos):
            game.proof_slot = slot
            return True
    for clue_id, rect in (rects.get("clues") or {}).items():
        if rect.collidepoint(pos):
            deduction.proof_select(game.current_case, game.state, getattr(game, "proof_slot", "motive"), clue_id)
            save_game(game.state)
            return True
    for alt_id, rect in (rects.get("alternatives") or {}).items():
        if rect.collidepoint(pos):
            game.state.proof_counter = alt_id
            save_game(game.state)
            return True
    for key, delta in (("up", -1), ("down", 1)):
        if rects.get(key) and rects[key].collidepoint(pos):
            game.proof_scroll = max(0, getattr(game, "proof_scroll", 0) + delta)
            return True
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.screen_name = "accusation"
        return True
    if rects.get("alibi") and rects["alibi"].collidepoint(pos):
        game.alibi_return = "proof"
        game.alibi_message = ""
        game.screen_name = "alibi"
        return True
    if rects.get("submit") and rects["submit"].collidepoint(pos) and deduction.proof_ready(game.current_case, game.state):
        game.ask_confirm("ПРЕДЪЯВИТЬ ОБВИНЕНИЕ?", "Суд проверит всю цепочку целиком. После вердикта дело будет закрыто.", game._finish_case, yes="В СУД", danger=False)
        return True
    return False


def handle_key(game, event) -> bool:
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        game.screen_name = "accusation"
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
        game.proof_scroll = max(0, getattr(game, "proof_scroll", 0) + (-1 if event.button == 4 else 1))
        return True
    return False
