"""Экран реконструкции: карточки событий по порядку.

Логика — в :mod:`detective_game.timeline`. Здесь раскладка карточек, стрелки
«выше/ниже», клик-выбор-обмен и проверка. Проверка стоит 10 игровых минут,
успех — +2 репутации и бонус к рангу финала.
"""

from __future__ import annotations

import pygame

from .. import timeline
from ..config import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_TEXT_DARK,
    COLOR_TEXT_DIM,
)
from ..save_system import save_game
from .widgets import Button, draw_panel, draw_text_wrapped, get_font

CHECK_MINUTES = 10


def _order(game):
    case = game.current_case or {}
    order = timeline.order(game.state, case)
    game.state.timeline_order = list(order)
    return order


def draw_timeline(game) -> None:
    """Отрисовать экран реконструкции."""
    surface = game.screen
    case = game.current_case or {}
    state = game.state
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    title = get_font(22, bold=True).render("ХРОНОЛОГИЯ ПРЕСТУПЛЕНИЯ", True, COLOR_ACCENT)
    surface.blit(title, (header.x + 18, header.y + 8))
    solved = timeline.is_solved(state, case)
    info = (
        "Хронология восстановлена — ранг финала будет выше."
        if solved
        else "Расставьте карточки по времени: клик — выбрать, второй клик — поменять местами."
    )
    surface.blit(get_font(11).render(info, True, COLOR_TEXT_DIM), (header.x + 18, header.y + 40))
    # прогресс справа
    matched = timeline.matched(state, case)
    order = _order(game)
    total = len(order)
    meta = get_font(12, bold=True).render(
        f"{matched}/{total} на своих местах  •  попыток: {state.timeline_attempts}",
        True,
        COLOR_GREEN if solved else COLOR_TEXT_DIM,
    )
    surface.blit(meta, (header.right - meta.get_width() - 18, header.y + 24))

    body = pygame.Rect(20, 90, width - 40, height - 160)
    draw_panel(surface, body)
    events = timeline.by_id(case)
    right_order = timeline.correct_order(case)
    rects = {"cards": {}, "up": {}, "down": {}}
    count = max(1, len(order))
    gap = 6
    card_h = min(66, (body.h - 120 - gap * (count - 1)) // count)
    top = body.y + 18
    selected = getattr(game, "timeline_selected", None)
    mouse = game._to_logical(pygame.mouse.get_pos())
    for index, event_id in enumerate(order):
        event = events.get(event_id)
        if not event:
            continue
        y = top + index * (card_h + gap)
        card = pygame.Rect(body.x + 18, y, body.w - 140, card_h)
        rects["cards"][index] = card
        is_sel = index == selected
        right_spot = index < total and right_order[index] == event_id
        if solved or right_spot:
            bg, border = (28, 44, 34), COLOR_GREEN
        elif is_sel:
            bg, border = (58, 50, 30), COLOR_ACCENT
        else:
            bg, border = (32, 32, 42), COLOR_BORDER
        if card.collidepoint(mouse):
            bg = tuple(min(255, c + 10) for c in bg)
        pygame.draw.rect(surface, bg, card, border_radius=7)
        pygame.draw.rect(surface, border, card, width=2 if is_sel else 1, border_radius=7)
        num = get_font(16, bold=True).render(str(index + 1), True, COLOR_ACCENT if is_sel else COLOR_TEXT_DIM)
        surface.blit(num, (card.x + 10, card.y + card_h // 2 - 9))
        time_txt = get_font(13, bold=True).render(event.get("time") or "--:--", True, COLOR_TEXT)
        surface.blit(time_txt, (card.x + 38, card.y + 8))
        draw_text_wrapped(
            surface,
            event.get("text", ""),
            get_font(11),
            COLOR_TEXT if not solved else (200, 220, 200),
            pygame.Rect(card.x + 110, card.y + 7, card.w - 120, card_h - 12),
        )
    # стрелки
    arrow_x = body.x + 18 + (body.w - 140) + 12
    for index in range(len(order)):
        y = top + index * (card_h + gap)
        up = pygame.Rect(arrow_x, y + 4, 34, card_h // 2 - 6)
        down = pygame.Rect(arrow_x, y + card_h // 2 + 2, 34, card_h // 2 - 6)
        rects["up"][index] = up
        rects["down"][index] = down
        for rect, glyph, enabled in (
            (up, "▲", index > 0),
            (down, "▼", index < len(order) - 1),
        ):
            col = (44, 44, 54) if enabled else (28, 28, 34)
            pygame.draw.rect(surface, col, rect, border_radius=5)
            pygame.draw.rect(surface, COLOR_BORDER if enabled else (40, 40, 48), rect, width=1, border_radius=5)
            gl = get_font(11, bold=True).render(glyph, True, COLOR_TEXT if enabled else COLOR_TEXT_DARK)
            surface.blit(gl, gl.get_rect(center=rect.center))
    # итог/сообщение
    message = str(getattr(game, "timeline_message", "") or "")
    if solved:
        message = "Все карточки на местах. Можно идти обвинять."
    if message:
        col = COLOR_GREEN if solved else (COLOR_RED if "Не сходится" in message else COLOR_TEXT_DIM)
        surface.blit(get_font(12, bold=True).render(message[:110], True, col), (body.x + 20, body.bottom - 58))

    # кнопки
    y = height - 58
    back = Button((20, y, 150, 40), "← НАЗАД")
    reset = Button((180, y, 150, 40), "СБРОСИТЬ")
    check_x = width - 370 if solved else width - 560
    check = Button((check_x, y, 170, 40), "ПРОВЕРИТЬ", accent=True, enabled=not solved)
    nxt = Button((width - 190, y, 170, 40), "ПРОДОЛЖИТЬ", accent=True, enabled=solved)
    for btn in (back, reset, check, nxt):
        btn.update(mouse, pygame.mouse.get_pressed()[0])
        btn.draw(surface, get_font(12, bold=True))
    # без реконструкции тоже можно идти дальше — просто ранг не вырастет
    skip = pygame.Rect(width - 190, y, 170, 40)
    if solved:
        game.timeline_rects = {
            **rects,
            "back": back.rect,
            "reset": reset.rect,
            "check": check.rect,
            "next": nxt.rect,
        }
    else:
        hovered = skip.collidepoint(mouse)
        pygame.draw.rect(surface, (44, 44, 54) if hovered else (32, 32, 40), skip, border_radius=8)
        pygame.draw.rect(surface, COLOR_BORDER, skip, width=1, border_radius=8)
        label = get_font(11, bold=True).render("ПРОПУСТИТЬ →", True, COLOR_TEXT_DIM)
        surface.blit(label, label.get_rect(center=skip.center))
        game.timeline_rects = {
            **rects,
            "back": back.rect,
            "reset": reset.rect,
            "check": check.rect,
            "next": nxt.rect,
            "skip": skip,
        }


def _return_screen(game) -> str:
    return str(getattr(game, "timeline_return", "map") or "map")


def handle_timeline_click(game, pos) -> bool:
    """Клик по карточке/стрелке/кнопке. True — клик обработан."""
    rects = getattr(game, "timeline_rects", {}) or {}
    case = game.current_case or {}
    state = game.state
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.screen_name = _return_screen(game)
        game.audio.play_sfx("page")
        return True
    if rects.get("reset") and rects["reset"].collidepoint(pos):
        timeline.reset(state, case)
        game.timeline_selected = None
        game.timeline_message = ""
        game.audio.play_sfx("page")
        save_game(state)
        return True
    if rects.get("check") and rects["check"].collidepoint(pos):
        result = timeline.check(state, case)
        state.case_time_minutes += CHECK_MINUTES
        if result["solved"]:
            game.timeline_message = "Хронология восстановлена!"
            game.add_notification("Реконструкция сошлась: +2 репутации, ранг финала выше")
            game.audio.play_sfx("success")
        else:
            game.timeline_message = f"Не сходится: {result['matched']} из {result['total']} на местах."
            game.audio.play_sfx("fail")
        save_game(state)
        return True
    if rects.get("skip") and rects["skip"].collidepoint(pos):
        game.screen_name = _return_screen(game)
        game.timeline_selected = None
        game.audio.play_sfx("page")
        return True
    if rects.get("next") and rects["next"].collidepoint(pos):
        game.screen_name = _return_screen(game)
        game.timeline_selected = None
        game.audio.play_sfx("page")
        return True
    for index, rect in (rects.get("up") or {}).items():
        if rect.collidepoint(pos):
            timeline.move(state, index, -1)
            game.timeline_selected = max(0, index - 1)
            game.timeline_message = ""
            game.audio.play_sfx("tick")
            save_game(state)
            return True
    for index, rect in (rects.get("down") or {}).items():
        if rect.collidepoint(pos):
            timeline.move(state, index, 1)
            game.timeline_selected = min(len(_order(game)) - 1, index + 1)
            game.timeline_message = ""
            game.audio.play_sfx("tick")
            save_game(state)
            return True
    for index, rect in (rects.get("cards") or {}).items():
        if not rect.collidepoint(pos):
            continue
        selected = getattr(game, "timeline_selected", None)
        if selected is None:
            game.timeline_selected = index
            game.audio.play_sfx("page")
        elif selected == index:
            game.timeline_selected = None
            game.audio.play_sfx("tick")
        else:
            timeline.swap(state, selected, index)
            game.timeline_selected = None
            game.timeline_message = ""
            game.audio.play_sfx("page")
            save_game(state)
        return True
    return False


def handle_timeline_key(game, event) -> bool:
    """Клавиши: стрелки — двигать выбранную карточку, Enter — проверить."""
    if event.type != pygame.KEYDOWN:
        return False
    order = _order(game)
    index = getattr(game, "timeline_selected", None)
    if event.key == pygame.K_ESCAPE:
        game.screen_name = _return_screen(game)
        return True
    if event.key in (pygame.K_UP, pygame.K_DOWN) and index is not None:
        timeline.move(game.state, index, -1 if event.key == pygame.K_UP else 1)
        game.timeline_selected = max(0, min(len(order) - 1, index + (-1 if event.key == pygame.K_UP else 1)))
        game.timeline_message = ""
        save_game(game.state)
        return True
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        check_rect = (getattr(game, "timeline_rects", {}) or {}).get("check")
        if check_rect and not timeline.is_solved(game.state, game.current_case):
            handle_timeline_click(game, check_rect.center)
        return True
    return False


__all__ = ["draw_timeline", "handle_timeline_click", "handle_timeline_key"]
