"""Экран головоломки: отрисовка и обработка кликов/клавиш.

Вся логика — в :mod:`detective_game.puzzles`; здесь только картинка и ввод.
Прямоугольники, по которым кликают, сохраняются в ``game.puzzle_rects`` — те
же, что и нарисованы (иначе на других разрешениях клики уезжают).
"""

from __future__ import annotations

import pygame

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
from ..puzzles import SHAPE_COLORS, SHAPES, WIRE_COLORS, Puzzle, difficulty_label
from .widgets import Button, draw_panel, get_font, wrap_text

PANEL = (26, 26, 34)
PANEL_DARK = (20, 20, 27)


def _draw_shape(surface, name: str, center, size: int, color) -> None:
    cx, cy = center
    half = size // 2
    if name == "круг":
        pygame.draw.circle(surface, color, (cx, cy), half)
        pygame.draw.circle(surface, (20, 20, 26), (cx, cy), half, width=2)
    elif name == "квадрат":
        rect = pygame.Rect(cx - half, cy - half, size, size)
        pygame.draw.rect(surface, color, rect, border_radius=6)
        pygame.draw.rect(surface, (20, 20, 26), rect, width=2, border_radius=6)
    elif name == "треугольник":
        points = [(cx, cy - half), (cx - half, cy + half), (cx + half, cy + half)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (20, 20, 26), points, 2)
    else:  # ромб
        points = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (20, 20, 26), points, 2)


def _draw_header(surface, puzzle: Puzzle, width: int) -> None:
    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    title = get_font(22, bold=True).render(puzzle.title, True, COLOR_ACCENT)
    surface.blit(title, (header.x + 18, header.y + 10))
    meta = get_font(11).render(
        f"СЛОЖНОСТЬ {difficulty_label(puzzle)}   •   {puzzle.progress_text}", True, COLOR_TEXT_DIM
    )
    surface.blit(meta, (header.x + 18, header.y + 40))
    # подсказка справа, в две строки максимум
    hint_font = get_font(11)
    hint_rect = pygame.Rect(header.right - 470, header.y + 8, 452, header.h - 16)
    draw_panel(surface, hint_rect, color=PANEL_DARK, radius=6)
    surface.blit(
        get_font(9, bold=True).render("ПОДСКАЗКА", True, COLOR_ACCENT),
        (hint_rect.x + 8, hint_rect.y + 4),
    )
    lines = wrap_text(puzzle.hint, hint_font, hint_rect.w - 16)[:2]
    for i, line in enumerate(lines):
        surface.blit(
            hint_font.render(line, True, COLOR_TEXT_DIM),
            (hint_rect.x + 8, hint_rect.y + 20 + i * 14),
        )


def _draw_footer(surface, puzzle: Puzzle, width: int, height: int) -> dict:
    rects = {}
    y = height - 58
    cancel = pygame.Rect(20, y, 150, 40)
    rects["cancel"] = cancel
    pygame.draw.rect(surface, (30, 30, 38), cancel, border_radius=8)
    pygame.draw.rect(surface, COLOR_BORDER, cancel, width=1, border_radius=8)
    cancel_txt = get_font(12, bold=True).render("НАЗАД", True, COLOR_TEXT)
    surface.blit(cancel_txt, cancel_txt.get_rect(center=cancel.center))
    esc = get_font(10).render("ESC — выйти", True, COLOR_TEXT_DARK)
    surface.blit(esc, (cancel.right + 12, cancel.y + 14))
    if puzzle.finished:
        label = "ПРОДОЛЖИТЬ"
        button = pygame.Rect(width - 230, y, 210, 40)
        rects["continue"] = button
        pygame.draw.rect(surface, COLOR_ACCENT, button, border_radius=8)
        txt = get_font(13, bold=True).render(label, True, (12, 12, 12))
        surface.blit(txt, txt.get_rect(center=button.center))
    elif puzzle.kind == "safe":
        button = pygame.Rect(width - 230, y, 210, 40)
        rects["submit"] = button
        pygame.draw.rect(surface, COLOR_ACCENT, button, border_radius=8)
        txt = get_font(13, bold=True).render("ПРОВЕРИТЬ", True, (12, 12, 12))
        surface.blit(txt, txt.get_rect(center=button.center))
    elif puzzle.kind == "sequence":
        button = pygame.Rect(width - 230, y, 210, 40)
        rects["retry_show"] = button
        pygame.draw.rect(surface, (44, 44, 54), button, border_radius=8)
        pygame.draw.rect(surface, COLOR_BORDER, button, width=1, border_radius=8)
        txt = get_font(12, bold=True).render("ПОКАЗАТЬ СНОВА", True, COLOR_TEXT)
        surface.blit(txt, txt.get_rect(center=button.center))
    msg = puzzle.message
    if msg:
        color = COLOR_GREEN if puzzle.success else (COLOR_RED if puzzle.failed else COLOR_TEXT_DIM)
        surface.blit(get_font(12, bold=bool(msg)).render(msg, True, color), (190, y + 12))
    return rects


def _draw_safe(surface, puzzle: Puzzle, body: pygame.Rect) -> dict:
    rects = {"keypad": {}}
    # слоты ввода
    slot_y = body.y + 30
    slot_w, gap = 82, 14
    total = len(puzzle.code) * slot_w + (len(puzzle.code) - 1) * gap
    start_x = body.x + 40
    for i in range(len(puzzle.code)):
        rect = pygame.Rect(start_x + i * (slot_w + gap), slot_y, slot_w, 96)
        filled = i < len(puzzle.entry)
        pygame.draw.rect(surface, (34, 34, 44) if filled else (24, 24, 31), rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_ACCENT if filled else COLOR_BORDER, rect, width=2, border_radius=8)
        if filled:
            digit = get_font(44, bold=True).render(str(puzzle.entry[i]), True, COLOR_ACCENT)
            surface.blit(digit, digit.get_rect(center=rect.center))
        else:
            dash = get_font(26, bold=True).render("—", True, COLOR_TEXT_DARK)
            surface.blit(dash, dash.get_rect(center=rect.center))
    # история подсказок
    hist_top = slot_y + 120
    surface.blit(
        get_font(11, bold=True).render("ПОДСКАЗКИ", True, COLOR_TEXT_DIM), (body.x + 40, hist_top)
    )
    if not puzzle.history:
        surface.blit(
            get_font(11).render("Пока пусто — введите код и нажмите «Проверить».", True, COLOR_TEXT_DARK),
            (body.x + 40, hist_top + 26),
        )
    marks = {"=": ("верно", COLOR_GREEN), "↑": ("больше", COLOR_TEXT_DIM), "↓": ("меньше", COLOR_TEXT_DIM)}
    for row, (digits, feedback) in enumerate(puzzle.history[-4:]):
        y = hist_top + 22 + row * 30
        for i, item in enumerate(feedback):
            x = body.x + 40 + i * 96
            color = COLOR_GREEN if item.correct else COLOR_TEXT_DIM
            pygame.draw.rect(surface, (24, 24, 31), (x, y, 86, 24), border_radius=5)
            surface.blit(get_font(12, bold=True).render(item.digit, True, COLOR_TEXT), (x + 8, y + 5))
            label, _ = marks[item.mark]
            surface.blit(get_font(10).render(label, True, color), (x + 26, y + 7))
    # клавиатура
    pad_x = body.x + 470
    pad_y = slot_y + 6
    key_w, key_h, key_gap = 96, 56, 10
    for n in range(10):
        row, col = divmod(n, 3)
        if n == 9:
            row, col = 3, 1
        rect = pygame.Rect(pad_x + col * (key_w + key_gap), pad_y + row * (key_h + key_gap), key_w, key_h)
        pygame.draw.rect(surface, (36, 36, 46), rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_BORDER, rect, width=1, border_radius=8)
        surface.blit(
            get_font(22, bold=True).render(str(n), True, COLOR_TEXT),
            get_font(22, bold=True).render(str(n), True, COLOR_TEXT).get_rect(center=rect.center),
        )
        rects["keypad"][n] = rect
    clear = pygame.Rect(pad_x, pad_y + 3 * (key_h + key_gap), key_w, key_h)
    pygame.draw.rect(surface, (44, 34, 34), clear, border_radius=8)
    pygame.draw.rect(surface, COLOR_BORDER, clear, width=1, border_radius=8)
    surface.blit(get_font(12, bold=True).render("СТЕРЕТЬ", True, COLOR_TEXT), (clear.x + 18, clear.y + 20))
    rects["clear"] = clear
    return rects


def _draw_lockpick(surface, puzzle: Puzzle, body: pygame.Rect) -> dict:
    rects = {}
    bar_h = 44
    region_top = body.y + 110
    region_bottom = body.bottom - 120
    bar_y = region_top + max(0, (region_bottom - region_top - bar_h) // 2)
    bar = pygame.Rect(body.x + 50, bar_y, body.w - 100, bar_h)
    # инструкция прямо над шкалой — чтобы взгляд не бегал по экрану
    tip = wrap_text(
        "Отмычка дрожит в руке. Нажмите пробел или клик по шкале, когда бегунок "
        "в зелёной зоне — три точных движения, и замок откроется.",
        get_font(12),
        body.w - 100,
    )
    for i, line in enumerate(tip):
        surface.blit(
            get_font(12).render(line, True, COLOR_TEXT_DIM),
            (body.x + 50, bar.y - 24 - (len(tip) - i) * 18),
        )
    pygame.draw.rect(surface, (18, 18, 24), bar, border_radius=18)
    for target in puzzle.targets:
        zone = pygame.Rect(
            int(bar.x + (target - puzzle.target_width / 2) * bar.w),
            bar.y,
            max(6, int(puzzle.target_width * bar.w)),
            bar.h,
        )
        pygame.draw.rect(surface, (40, 92, 60), zone, border_radius=10)
        pygame.draw.rect(surface, COLOR_GREEN, zone, width=1, border_radius=10)
    # уже взятые замки — справа над шкалой
    for i in range(puzzle.hits):
        pygame.draw.circle(surface, COLOR_GREEN, (bar.right - 12 - i * 22, bar.y - 16), 6)
    # бегунок
    cx = int(bar.x + puzzle.cursor * bar.w)
    pygame.draw.circle(surface, COLOR_ACCENT, (cx, bar.centery), 13)
    pygame.draw.circle(surface, (12, 12, 16), (cx, bar.centery), 13, width=2)
    pygame.draw.line(surface, (12, 12, 16), (cx, bar.y - 6), (cx, bar.bottom + 6), 2)
    # прогресс и промахи
    pips = pygame.Rect(body.x + 50, bar.bottom + 30, 240, 26)
    for i in range(3):
        color = COLOR_GREEN if i < puzzle.hits else (52, 52, 62)
        pygame.draw.circle(surface, color, (pips.x + 10 + i * 26, pips.centery), 8)
    misses = get_font(12).render(
        f"промахи: {puzzle.misses}/{puzzle.attempts_total}",
        True,
        COLOR_RED if puzzle.misses else COLOR_TEXT_DIM,
    )
    surface.blit(misses, (pips.right + 20, pips.y + 5))
    rects["bar"] = bar
    return rects


def _draw_wires(surface, puzzle: Puzzle, body: pygame.Rect) -> dict:
    rects = {"wires": []}
    wire_top = body.y + 90
    wire_bottom = body.y + 320
    step = (body.w - 160) // 5
    for i, (name, _, color) in enumerate(WIRE_COLORS):
        x = body.x + 80 + i * step
        rect = pygame.Rect(x - 34, wire_top - 30, 68, wire_bottom - wire_top + 90)
        rects["wires"].append(rect)
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover and not puzzle.finished:
            pygame.draw.rect(surface, (34, 34, 44), rect, border_radius=8)
        cut = puzzle.cut_wire == i
        if cut:
            pygame.draw.line(surface, color, (x, wire_top), (x, wire_top + 90), 10)
            pygame.draw.line(surface, color, (x, wire_top + 150), (x, wire_bottom), 10)
            pygame.draw.line(surface, COLOR_RED, (x - 26, wire_top + 118), (x + 26, wire_top + 126), 3)
        else:
            pygame.draw.line(surface, color, (x, wire_top), (x, wire_bottom), 10)
            pygame.draw.line(surface, (16, 16, 22), (x - 3, wire_top), (x - 3, wire_bottom), 2)
        num = get_font(14, bold=True).render(str(i + 1), True, COLOR_TEXT)
        surface.blit(num, num.get_rect(center=(x, wire_top - 18)))
        label = get_font(10).render(name.upper(), True, COLOR_TEXT_DIM)
        surface.blit(label, label.get_rect(center=(x, wire_bottom + 22)))
    # условия
    cond = pygame.Rect(body.x + 40, body.bottom - 200, body.w - 80, 104)
    draw_panel(surface, cond, color=PANEL_DARK, radius=8)
    surface.blit(get_font(11, bold=True).render("ЧТО ИЗВЕСТНО", True, COLOR_ACCENT), (cond.x + 14, cond.y + 8))
    for i, line in enumerate(puzzle.constraints[:3]):
        surface.blit(
            get_font(12).render(f"• {line}", True, COLOR_TEXT),
            (cond.x + 14, cond.y + 30 + i * 22),
        )
    return rects


def _draw_sequence(surface, puzzle: Puzzle, body: pygame.Rect) -> dict:
    rects = {"shapes": {}}
    if puzzle.showing:
        current = puzzle.sequence_visible
        surface.blit(
            get_font(13, bold=True).render("ЗАПОМНИТЕ ПОСЛЕДОВАТЕЛЬНОСТЬ", True, COLOR_ACCENT),
            (body.x + 40, body.y + 30),
        )
        if current:
            _draw_shape(surface, current, (body.centerx, body.y + 170), 150, SHAPE_COLORS[current])
        prog = f"{puzzle.show_index + 1} / {len(puzzle.order)}"
        prog_surf = get_font(14, bold=True).render(prog, True, COLOR_TEXT_DIM)
        surface.blit(prog_surf, prog_surf.get_rect(center=(body.centerx, body.y + 290)))
        return rects
    surface.blit(
        get_font(13, bold=True).render("ПОВТОРИТЕ В ТОМ ЖЕ ПОРЯДКЕ", True, COLOR_ACCENT),
        (body.x + 40, body.y + 24),
    )
    size = 96
    gap = 40
    total = len(SHAPES) * size + (len(SHAPES) - 1) * gap
    start_x = body.centerx - total // 2
    for i, name in enumerate(SHAPES):
        center = (start_x + i * (size + gap) + size // 2, body.y + 170)
        rect = pygame.Rect(center[0] - size // 2 - 10, center[1] - size // 2 - 10, size + 20, size + 20)
        rects["shapes"][name] = rect
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surface, (34, 34, 44) if hover else PANEL_DARK, rect, border_radius=12)
        pygame.draw.rect(surface, COLOR_ACCENT if hover else COLOR_BORDER, rect, width=1, border_radius=12)
        _draw_shape(surface, name, center, size, SHAPE_COLORS[name])
    # введённая часть
    x0 = body.centerx - (len(puzzle.order) * 30) // 2
    for i in range(len(puzzle.order)):
        filled = i < len(puzzle.input)
        color = COLOR_GREEN if filled else (50, 50, 60)
        pygame.draw.circle(surface, color, (x0 + i * 30, body.y + 270), 8)
    return rects


def _draw_lock_icon(surface, center, size: int, opened: bool) -> None:
    """Простой навесной замок: дужка + корпус."""
    cx, cy = center
    body = pygame.Rect(cx - size // 2, cy - size // 4, size, int(size * 0.72))
    color = COLOR_GREEN if opened else COLOR_ACCENT
    pygame.draw.rect(surface, color, body, border_radius=4)
    pygame.draw.rect(surface, (18, 18, 24), body, width=2, border_radius=4)
    shackle = pygame.Rect(body.x + 4, body.y - int(size * 0.42), body.w - 8, int(size * 0.5))
    if opened:
        shackle.x += 6
        pygame.draw.arc(surface, color, shackle, 0.15, 3.0, 4)
    else:
        pygame.draw.arc(surface, color, shackle, 0.0, 3.15, 4)


def _draw_clue_card(surface, game, puzzle: Puzzle, body: pygame.Rect) -> None:
    """Полоска «что охраняет замок» — заполняет низ экрана и объясняет награду."""
    clue = getattr(game, "puzzle_clue", None) or {}
    card = pygame.Rect(body.x + 40, body.bottom - 96, body.w - 80, 82)
    draw_panel(surface, card, color=PANEL_DARK, radius=8)
    pygame.draw.rect(surface, COLOR_BORDER, card, width=1, border_radius=8)
    _draw_lock_icon(surface, (card.x + 34, card.centery), 34, puzzle.success)
    text_x = card.x + 66
    surface.blit(
        get_font(9, bold=True).render("ДОСТУП К УЛИКЕ", True, COLOR_ACCENT),
        (text_x, card.y + 8),
    )
    title = clue.get("title") or "Улика"
    surface.blit(get_font(14, bold=True).render(title, True, COLOR_TEXT), (text_x, card.y + 22))
    reward = (clue.get("puzzle") or {}).get("reward") or "Улика попадёт в блокнот"
    if puzzle.failed:
        reward = "Замок не поддался: вернитесь к нему позже"
    lines = wrap_text(reward, get_font(11), card.w - 90)[:2]
    for i, line in enumerate(lines):
        surface.blit(
            get_font(11).render(line, True, COLOR_TEXT_DIM),
            (text_x, card.y + 44 + i * 14),
        )


def draw_puzzle_screen(game) -> None:
    """Отрисовать экран головоломки (game.puzzle уже создан)."""
    puzzle: Puzzle = game.puzzle
    surface = game.screen
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    _draw_header(surface, puzzle, width)
    body = pygame.Rect(20, 92, width - 40, height - 164)
    draw_panel(surface, body)
    if puzzle.kind == "safe":
        rects = _draw_safe(surface, puzzle, body)
    elif puzzle.kind == "lockpick":
        rects = _draw_lockpick(surface, puzzle, body)
    elif puzzle.kind == "wires":
        rects = _draw_wires(surface, puzzle, body)
    else:
        rects = _draw_sequence(surface, puzzle, body)
    _draw_clue_card(surface, game, puzzle, body)
    rects["body"] = body
    rects.update(_draw_footer(surface, puzzle, width, height))
    game.puzzle_rects = rects


# ── ввод ─────────────────────────────────────────────────────────────


def handle_puzzle_key(game, event) -> bool:
    puzzle: Puzzle = game.puzzle
    if puzzle is None or event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_ESCAPE:
        game.close_puzzle()
        return True
    if puzzle.finished:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            game.finish_puzzle_flow()
            return True
        return False
    if puzzle.kind == "safe":
        if pygame.K_0 <= event.key <= pygame.K_9:
            puzzle.press_digit(event.key - pygame.K_0)
            game.audio.play_sfx("dial")
            return True
        if event.key == pygame.K_BACKSPACE:
            puzzle.backspace()
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            game.submit_puzzle_code()
            return True
    elif puzzle.kind == "lockpick":
        if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            game.strike_lockpick()
            return True
    elif puzzle.kind == "sequence":
        if event.key in (pygame.K_SPACE, pygame.K_RETURN) and not puzzle.showing:
            puzzle.restart_sequence()
            return True
    return False


def handle_puzzle_click(game, pos) -> bool:
    puzzle: Puzzle = game.puzzle
    if puzzle is None:
        return False
    rects = getattr(game, "puzzle_rects", {}) or {}
    if rects.get("cancel") and rects["cancel"].collidepoint(pos):
        game.close_puzzle()
        return True
    if puzzle.finished:
        if rects.get("continue") and rects["continue"].collidepoint(pos):
            game.finish_puzzle_flow()
            return True
        return True
    if rects.get("submit") and rects["submit"].collidepoint(pos):
        game.submit_puzzle_code()
        return True
    if rects.get("retry_show") and rects["retry_show"].collidepoint(pos):
        puzzle.restart_sequence()
        return True
    keypad = rects.get("keypad") or {}
    for digit, rect in keypad.items():
        if rect.collidepoint(pos):
            puzzle.press_digit(digit)
            game.audio.play_sfx("dial")
            return True
    if rects.get("clear") and rects["clear"].collidepoint(pos):
        puzzle.backspace()
        return True
    if puzzle.kind == "lockpick" and rects.get("bar") and rects["bar"].collidepoint(pos):
        game.strike_lockpick()
        return True
    for i, rect in enumerate(rects.get("wires") or []):
        if rect.collidepoint(pos):
            game.cut_wire(i)
            return True
    for name, rect in (rects.get("shapes") or {}).items():
        if rect.collidepoint(pos):
            game.tap_shape(name)
            return True
    return True


__all__ = ["draw_puzzle_screen", "handle_puzzle_click", "handle_puzzle_key", "Button"]
