"""Вкладка «ВЕРСИИ»: доска связок «улика → подозреваемый».

Логика — в :mod:`detective_game.board`; здесь только раскладка, клики и
обратная связь. Прямоугольники сохраняются в ``game.board_rects``: клики
проверяются по тем же точкам, что нарисованы.
"""

from __future__ import annotations

import pygame

from .. import board
from ..config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_TEXT_DARK,
    COLOR_TEXT_DIM,
)
from ..save_system import save_game
from .widgets import draw_panel, draw_text_wrapped, get_font

PANEL_DARK = (22, 22, 30)
HINT_COST = 5


def _message(game) -> str:
    return str(getattr(game, "board_message", "") or "")


def say(game, text: str) -> None:
    game.board_message = text


def draw_board(game, rect: pygame.Rect) -> None:
    """Нарисовать доску версий во вкладке блокнота."""
    case = game.current_case or {}
    state = game.state
    rects = {"clues": {}, "suspects": {}, "hint": None}
    progress = board.progress(case, state)

    # шапка вкладки
    title = get_font(15, bold=True).render("ДОСКА ВЕРСИЙ", True, COLOR_ACCENT)
    game.screen.blit(title, (rect.x + 20, rect.y + 14))
    meta = get_font(11).render(
        f"связок {progress['correct']}/{progress['total']}  •  ошибок {progress['wrong']}"
        f"  •  версий собрано {progress['suspects_done']}/{progress['suspects_total']}",
        True,
        COLOR_TEXT_DIM,
    )
    game.screen.blit(meta, (rect.x + 20, rect.y + 36))

    # две колонки
    top = rect.y + 64
    left = pygame.Rect(rect.x + 20, top, 470, rect.bottom - top - 130)
    right = pygame.Rect(left.right + 20, top, rect.right - left.right - 40, rect.bottom - top - 130)
    draw_panel(game.screen, left, color=PANEL_DARK, radius=8)
    draw_panel(game.screen, right, color=PANEL_DARK, radius=8)

    game.screen.blit(
        get_font(12, bold=True).render("УЛИКИ", True, COLOR_TEXT), (left.x + 14, left.y + 12)
    )
    game.screen.blit(
        get_font(10).render("выберите улику", True, COLOR_TEXT_DARK),
        (left.x + 70, left.y + 14),
    )
    game.screen.blit(
        get_font(12, bold=True).render("ПОДОЗРЕВАЕМЫЕ", True, COLOR_TEXT),
        (right.x + 14, right.y + 12),
    )
    hint = get_font(10).render("нажмите, чтобы связать", True, COLOR_TEXT_DARK)
    game.screen.blit(hint, (right.right - hint.get_width() - 14, right.y + 14))

    selected = getattr(game, "board_clue", None)
    mouse = pygame.mouse.get_pos()
    y = left.y + 36
    clues = [c for c in case.get("clues", []) if c.get("id") in (state.collected_clues or set())]
    if not clues:
        draw_text_wrapped(
            game.screen,
            "Улик пока нет. Обыскивайте локации и допрашивайте людей.",
            get_font(12),
            COLOR_TEXT_DARK,
            pygame.Rect(left.x + 14, y, left.w - 28, 60),
        )
    for clue in clues:
        if y + 34 > left.bottom - 10:
            break
        chip = pygame.Rect(left.x + 12, y, left.w - 24, 30)
        rects["clues"][clue["id"]] = chip
        is_sel = clue["id"] == selected
        hovered = chip.collidepoint(mouse)
        bg = (58, 50, 30) if is_sel else ((40, 40, 50) if hovered else (32, 32, 42))
        pygame.draw.rect(game.screen, bg, chip, border_radius=6)
        pygame.draw.rect(
            game.screen,
            COLOR_ACCENT if is_sel else COLOR_BORDER,
            chip,
            width=2 if is_sel else 1,
            border_radius=6,
        )
        pygame.draw.circle(
            game.screen,
            COLOR_ACCENT if clue.get("importance") == "high" else COLOR_TEXT_DIM,
            (chip.x + 16, chip.centery),
            5,
        )
        txt = get_font(11, bold=is_sel).render(
            str(clue.get("title", clue["id"]))[:40], True, COLOR_TEXT
        )
        game.screen.blit(txt, (chip.x + 30, chip.y + 7))
        y += 34

    # карточки подозреваемых
    y = right.y + 36
    inner = right.w - 24
    for item in case.get("suspects", []):
        if y + 84 > right.bottom - 10:
            break
        card = pygame.Rect(right.x + 12, y, inner, 78)
        rects["suspects"][str(item.get("id"))] = card
        done = board.conclusion_for(case, state, item) is not None
        bg = (30, 44, 34) if done else (32, 32, 42)
        if card.collidepoint(mouse) and selected:
            bg = (44, 44, 58)
        pygame.draw.rect(game.screen, bg, card, border_radius=8)
        pygame.draw.rect(
            game.screen, COLOR_GREEN if done else COLOR_BORDER, card, width=1, border_radius=8
        )
        name = get_font(13, bold=True).render(str(item.get("name", "?")), True, COLOR_TEXT)
        game.screen.blit(name, (card.x + 12, card.y + 9))
        evidence = [str(cid) for cid in item.get("evidence", [])]
        linked = sum(
            1
            for cid in evidence
            if board.link_key(cid, str(item.get("id"))) in (state.board_links or set())
        )
        counter = f"{linked}/{len(evidence)}" if evidence else "—"
        ccol = COLOR_GREEN if done else (COLOR_TEXT_DIM if evidence else COLOR_TEXT_DARK)
        cnt = get_font(12, bold=True).render(counter, True, ccol)
        game.screen.blit(cnt, (card.right - cnt.get_width() - 14, card.y + 10))
        draw_text_wrapped(
            game.screen,
            str(item.get("motive", ""))[:70],
            get_font(10),
            COLOR_TEXT_DIM,
            pygame.Rect(card.x + 12, card.y + 30, card.w - 24, 30),
        )
        if done:
            tag = get_font(10, bold=True).render("ВЕРСИЯ СОБРАНА", True, COLOR_GREEN)
            game.screen.blit(tag, (card.x + 12, card.y + 56))
        y += 86

    # нижняя полоса: выбранная улика, подсказка, сообщение
    bar = pygame.Rect(rect.x + 20, rect.bottom - 58, rect.w - 40, 44)
    draw_panel(game.screen, bar, color=(28, 28, 36), radius=8)
    if selected:
        clue = next((c for c in case.get("clues", []) if c["id"] == selected), None)
        label = f"Выбрано: «{clue.get('title') if clue else selected}» — нажмите подозреваемого"
        col = COLOR_ACCENT
    else:
        label = "Выберите улику слева, затем подозреваемого справа."
        col = COLOR_TEXT_DIM
    game.screen.blit(get_font(11, bold=bool(selected)).render(label[:80], True, col), (bar.x + 14, bar.y + 6))
    message = _message(game)
    if message:
        mcol = COLOR_GREEN if "принята" in message or "сходятся" in message else (
            COLOR_RED if "Не сходится" in message else COLOR_TEXT_DIM
        )
        game.screen.blit(get_font(10).render(message[:118], True, mcol), (bar.x + 14, bar.y + 24))
    hint_rect = pygame.Rect(bar.right - 170, bar.y + 7, 156, 30)
    rects["hint"] = hint_rect
    hovered = hint_rect.collidepoint(mouse)
    pygame.draw.rect(game.screen, (52, 46, 32) if hovered else (40, 38, 32), hint_rect, border_radius=6)
    pygame.draw.rect(game.screen, COLOR_ACCENT, hint_rect, width=1, border_radius=6)
    hint_label = get_font(10, bold=True).render(f"НАВОДКА (+{HINT_COST} мин)", True, COLOR_ACCENT)
    game.screen.blit(hint_label, hint_label.get_rect(center=hint_rect.center))
    game.board_rects = rects


def handle_board_click(game, pos) -> bool:
    """Клик по доске: выбрать улику, связать с подозреваемым, взять наводку."""
    rects = getattr(game, "board_rects", {}) or {}
    case = game.current_case or {}
    state = game.state
    for clue_id, rect in (rects.get("clues") or {}).items():
        if rect.collidepoint(pos):
            game.board_clue = None if game.board_clue == clue_id else clue_id
            say(game, "")
            game.audio.play_sfx("page")
            return True
    for suspect_id, rect in (rects.get("suspects") or {}).items():
        if not rect.collidepoint(pos):
            continue
        clue_id = getattr(game, "board_clue", None)
        if not clue_id:
            say(game, "Сначала выберите улику.")
            game.audio.play_sfx("tick")
            return True
        result = board.link(state, case, clue_id, suspect_id)
        say(game, str(result.get("message", "")))
        status = result.get("status")
        if status == "ok":
            game.audio.play_sfx("clue")
            game.state.case_time_minutes += int(result.get("time", 5) or 0)
            conclusion = result.get("conclusion")
            if conclusion:
                game.add_notification(f"Версия собрана: {conclusion['title']}")
                game.audio.play_sfx("success")
            game.board_clue = None
            save_game(game.state)
        elif status == "wrong":
            game.audio.play_sfx("fail")
            game.state.case_time_minutes += int(result.get("time", 10) or 0)
            save_game(game.state)
        else:
            game.audio.play_sfx("tick")
        return True
    hint_rect = rects.get("hint")
    if hint_rect and hint_rect.collidepoint(pos):
        pair = board.hint_pair(case, state)
        if not pair:
            say(game, "Подсказывать нечего: все доступные связки уже на доске.")
            return True
        clue_id, suspect_id = pair
        clue = next((c for c in case.get("clues", []) if c["id"] == clue_id), {})
        item = board.suspect(case, suspect_id) or {}
        game.board_clue = clue_id
        say(game, f"Наводка: «{clue.get('title', clue_id)}» → {item.get('name', suspect_id)}")
        game.state.case_time_minutes += HINT_COST
        game.audio.play_sfx("page")
        save_game(game.state)
        return True
    return False


__all__ = ["draw_board", "handle_board_click", "say"]
