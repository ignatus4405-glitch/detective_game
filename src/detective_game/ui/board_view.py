"""Вкладка «ВЕРСИИ»: доска связок «улика → подозреваемый».

Логика — в :mod:`detective_game.board`; здесь только раскладка, клики и
обратная связь. Прямоугольники сохраняются в ``game.board_rects``: клики
проверяются по тем же точкам, что нарисованы.
"""

from __future__ import annotations

import pygame

from .. import board, deduction
from ..config import (
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_PANEL_LIGHT,
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
    if deduction.enabled(case, state):
        draw_expert_board(game, rect)
        return
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
    talk_rect = pygame.Rect(bar.right - 340, bar.y + 7, 160, 30)
    rects["testimony"] = talk_rect
    from .. import pressure, testimony

    talk_enabled = pressure.advanced(case) and testimony.available(case, state)
    talk_hovered = talk_rect.collidepoint(mouse)
    pygame.draw.rect(
        game.screen,
        (52, 46, 32) if talk_hovered and talk_enabled else (30, 30, 38),
        talk_rect,
        border_radius=6,
    )
    pygame.draw.rect(
        game.screen,
        COLOR_ACCENT if talk_enabled else (70, 70, 80),
        talk_rect,
        width=1,
        border_radius=6,
    )
    talk_label = get_font(10, bold=True).render(
        "ПОКАЗАНИЯ", True, COLOR_ACCENT if talk_enabled else COLOR_TEXT_DARK
    )
    game.screen.blit(talk_label, talk_label.get_rect(center=talk_rect.center))
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
    if deduction.enabled(game.current_case, game.state):
        return handle_expert_board_click(game, pos)
    rects = getattr(game, "board_rects", {}) or {}
    case = game.current_case or {}
    state = game.state
    talk = rects.get("testimony")
    if talk and talk.collidepoint(pos):
        from .. import pressure, testimony

        if pressure.advanced(case) and testimony.available(case, state):
            game.testimony_selected = []
            game.testimony_message = ""
            game.testimony_scroll = 0
            game.testimony_return = "notebook"
            game.screen_name = "testimony"
            game.audio.play_sfx("page")
        else:
            game.add_notification("Пока нечего сопоставлять: поговорите с людьми")
            game.audio.play_sfx("tick")
        return True
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


def draw_expert_board(game, rect):
    case, state = game.current_case, game.state
    mouse = pygame.mouse.get_pos()
    rects = {"clues": {}, "suspects": {}, "review": None, "alibi": None, "proof": None, "testimony": None}
    game.screen.blit(get_font(16, bold=True).render("ДОСКА ВЕРСИЙ · ЧЕРНОВИК", True, COLOR_ACCENT), (rect.x + 20, rect.y + 14))
    meta = f"Связей: {len(state.board_draft)} · проверка версии: {deduction.REVIEW_COST} мин · отдельные связи не оцениваются"
    game.screen.blit(get_font(11).render(meta, True, COLOR_TEXT_DIM), (rect.x + 20, rect.y + 38))
    top = rect.y + 66
    left = pygame.Rect(rect.x + 20, top, 500, rect.bottom - top - 126)
    right = pygame.Rect(left.right + 20, top, rect.right - left.right - 40, left.h)
    draw_panel(game.screen, left, color=PANEL_DARK)
    draw_panel(game.screen, right, color=PANEL_DARK)
    game.screen.blit(get_font(12, bold=True).render("УЛИКИ", True, COLOR_TEXT), (left.x + 14, left.y + 12))
    game.screen.blit(get_font(12, bold=True).render("ПОДОЗРЕВАЕМЫЕ", True, COLOR_TEXT), (right.x + 14, right.y + 12))
    clues = [c for c in case.get("clues", []) if c["id"] in state.collected_clues]
    scroll = max(0, min(getattr(game, "board_scroll", 0), max(0, len(clues) - 8)))
    game.board_scroll = scroll
    y = left.y + 38
    for clue in clues[scroll:scroll + 8]:
        chip = pygame.Rect(left.x + 12, y, left.w - 24, 32)
        rects["clues"][clue["id"]] = chip
        selected = game.board_clue == clue["id"]
        pygame.draw.rect(game.screen, (58, 50, 30) if selected else (32, 34, 43), chip, border_radius=5)
        pygame.draw.rect(game.screen, COLOR_ACCENT if selected else COLOR_BORDER, chip, width=1, border_radius=5)
        label = get_font(11, bold=selected).render(clue["title"][:44], True, COLOR_TEXT)
        game.screen.blit(label, (chip.x + 12, chip.y + 8))
        linked = sum(1 for cid, _sid in map(board.parse_key, state.board_draft) if cid == clue["id"])
        if linked:
            badge = pygame.Rect(chip.right - 30, chip.y + 6, 20, 20)
            pygame.draw.circle(game.screen, COLOR_ACCENT_DIM, badge.center, 10)
            n = get_font(10, bold=True).render(str(linked), True, COLOR_TEXT)
            game.screen.blit(n, n.get_rect(center=badge.center))
        y += 36
    if len(clues) > 8:
        for key, text, x in (("up", "↑", left.right - 72), ("down", "↓", left.right - 38)):
            r = pygame.Rect(x, left.bottom - 30, 28, 22)
            rects[key] = r
            pygame.draw.rect(game.screen, COLOR_PANEL_LIGHT, r, border_radius=4)
            t = get_font(12, bold=True).render(text, True, COLOR_ACCENT)
            game.screen.blit(t, t.get_rect(center=r.center))
    y = right.y + 38
    for item in case.get("suspects", []):
        card = pygame.Rect(right.x + 12, y, right.w - 24, 76)
        rects["suspects"][item["id"]] = card
        active = state.board_suspect == item["id"]
        linked = sum(1 for cid, sid in map(board.parse_key, state.board_draft) if sid == item["id"])
        pygame.draw.rect(game.screen, (49, 43, 30) if active else (32, 34, 43), card, border_radius=6)
        pygame.draw.rect(game.screen, COLOR_ACCENT if active else COLOR_BORDER, card, width=2 if active else 1, border_radius=6)
        game.screen.blit(get_font(13, bold=True).render(item["name"], True, COLOR_TEXT), (card.x + 12, card.y + 9))
        game.screen.blit(get_font(10).render(f"Связей в черновике: {linked}", True, COLOR_TEXT_DIM), (card.x + 12, card.y + 32))
        draw_text_wrapped(game.screen, item.get("motive", ""), get_font(10), COLOR_TEXT_DIM, pygame.Rect(card.x + 12, card.y + 49, card.w - 24, 24))
        y += 82
    bar = pygame.Rect(rect.x + 20, rect.bottom - 112, rect.w - 40, 98)
    draw_panel(game.screen, bar, color=(24, 26, 34))
    message = _message(game)
    if not message:
        message = "Выберите улику и человека. Клик по связи снимает её. Затем выберите подозреваемого без улики и проверьте всю версию."
    draw_text_wrapped(game.screen, message, get_font(11), COLOR_TEXT, pygame.Rect(bar.x + 14, bar.y + 8, bar.w - 28, 40))
    buttons = [("testimony", "ПОКАЗАНИЯ", 150), ("alibi", "АЛИБИ", 130), ("review", f"ПРОВЕРИТЬ ВЕРСИЮ (+{deduction.REVIEW_COST} мин)", 280), ("proof", "К ОБВИНЕНИЮ", 180)]
    x = bar.x + 14
    for key, label, width in buttons:
        r = pygame.Rect(x, bar.bottom - 38, width, 28)
        rects[key] = r
        pygame.draw.rect(game.screen, (54, 47, 30) if r.collidepoint(mouse) else (36, 38, 46), r, border_radius=5)
        pygame.draw.rect(game.screen, COLOR_ACCENT_DIM, r, width=1, border_radius=5)
        t = get_font(10, bold=True).render(label, True, COLOR_ACCENT)
        game.screen.blit(t, t.get_rect(center=r.center))
        x += width + 12
    game.board_rects = rects


def handle_expert_board_click(game, pos):
    rects = game.board_rects or {}
    state, case = game.state, game.current_case
    for key, delta in (("up", -1), ("down", 1)):
        if rects.get(key) and rects[key].collidepoint(pos):
            game.board_scroll = max(0, getattr(game, "board_scroll", 0) + delta)
            return True
    for clue_id, rect in (rects.get("clues") or {}).items():
        if rect.collidepoint(pos):
            game.board_clue = None if game.board_clue == clue_id else clue_id
            say(game, "")
            return True
    for suspect_id, rect in (rects.get("suspects") or {}).items():
        if rect.collidepoint(pos):
            if game.board_clue:
                result = board.link(state, case, game.board_clue, suspect_id)
                say(game, result["message"])
                game.board_clue = None
            else:
                state.board_suspect = suspect_id
                say(game, "Проверяется версия по выбранному подозреваемому.")
            save_game(state)
            return True
    if rects.get("review") and rects["review"].collidepoint(pos):
        if not state.board_suspect:
            say(game, "Сначала выберите подозреваемого кликом без выбранной улики.")
        else:
            result = board.review(case, state, state.board_suspect)
            say(game, board.review_text(result))
            save_game(state)
        return True
    if rects.get("alibi") and rects["alibi"].collidepoint(pos):
        game.alibi_return = "notebook"
        game.notebook_tab = "board"
        game.alibi_message = ""
        game.screen_name = "alibi"
        return True
    if rects.get("proof") and rects["proof"].collidepoint(pos):
        game.screen_name = "accusation"
        return True
    if rects.get("testimony") and rects["testimony"].collidepoint(pos):
        from .. import testimony
        if testimony.available(case, state):
            game.testimony_selected = []
            game.testimony_return = "notebook"
            game.screen_name = "testimony"
        else:
            say(game, "Сначала услышьте хотя бы две реплики в допросах.")
        return True
    return False


__all__ = ["draw_board", "handle_board_click", "say"]
