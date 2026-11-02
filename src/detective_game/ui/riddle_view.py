"""Экран кодового замка: текст загадки, ввод цифр и подсказка.

Логика — в :mod:`detective_game.riddle`; здесь раскладка, клики и клавиатура.
Клики обрабатываются только в :func:`handle_riddle_click`, отрисовка ничего
не меняет — иначе одно нажатие срабатывало бы дважды за кадр.
"""

from __future__ import annotations

import pygame

from .. import riddle as riddle_logic
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

KEYPAD = [
    ("1", "2", "3"),
    ("4", "5", "6"),
    ("7", "8", "9"),
    ("C", "0", "OK"),
]


def draw_riddle(game) -> None:
    surface = game.screen
    item = getattr(game, "riddle", None)
    if not item:
        return
    width, height = surface.get_size()
    surface.fill(COLOR_BG)

    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    surface.blit(
        get_font(22, bold=True).render("КОДОВЫЙ ЗАМОК", True, COLOR_ACCENT),
        (header.x + 18, header.y + 8),
    )
    surface.blit(
        get_font(11).render(item["title"], True, COLOR_TEXT_DIM),
        (header.x + 18, header.y + 40),
    )
    surface.blit(
        get_font(11).render(
            "Соберите код из загадки. Ошибка стоит времени — подсказка дешевле.",
            True,
            COLOR_TEXT_DARK,
        ),
        (header.right - 470, header.y + 40),
    )

    body = pygame.Rect(20, 90, width - 40, height - 160)
    draw_panel(surface, body)
    left = pygame.Rect(body.x + 20, body.y + 20, int(body.w * 0.52) - 30, body.h - 40)
    right = pygame.Rect(left.right + 20, body.y + 20, body.right - left.right - 40, body.h - 40)

    draw_panel(surface, left, color=(24, 24, 32), radius=10)
    inner = pygame.Rect(left.x + 16, left.y + 12, left.w - 32, left.h - 120)
    y = inner.y
    clue = getattr(game, "riddle_clue", None) or {}
    if clue.get("title"):
        surface.blit(get_font(10, bold=True).render("УЛИКА", True, COLOR_TEXT_DARK), (inner.x, y))
        title = get_font(14, bold=True).render(str(clue["title"]), True, COLOR_TEXT)
        surface.blit(title, (inner.x, y + 14))
        y += 36
        desc_rect = pygame.Rect(inner.x, y, inner.w, 52)
        draw_text_wrapped(surface, str(clue.get("desc", "")), get_font(11), COLOR_TEXT_DIM, desc_rect)
        y += 60
        pygame.draw.line(surface, COLOR_BORDER, (inner.x, y), (inner.right, y))
        y += 12
    surface.blit(get_font(11, bold=True).render("ЗАГАДКА", True, COLOR_ACCENT), (inner.x, y))
    draw_text_wrapped(
        surface,
        item["prompt"],
        get_font(15),
        COLOR_TEXT,
        pygame.Rect(inner.x, y + 20, inner.w, max(40, inner.bottom - (y + 20))),
    )
    hint_text = str(getattr(game, "riddle_hint", "") or "")
    if hint_text:
        hint_rect = pygame.Rect(left.x + 16, left.bottom - 84, left.w - 32, 68)
        draw_panel(surface, hint_rect, color=(30, 30, 24), border=COLOR_ACCENT, radius=8)
        surface.blit(
            get_font(10, bold=True).render("ПОДСКАЗКА", True, COLOR_ACCENT),
            (hint_rect.x + 10, hint_rect.y + 6),
        )
        draw_text_wrapped(
            surface,
            hint_text,
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(hint_rect.x + 10, hint_rect.y + 24, hint_rect.w - 20, hint_rect.h - 30),
        )

    # ввод и клавиатура
    draw_panel(surface, right, color=(24, 24, 32), radius=10)
    length = max(1, riddle_logic.answer_length(item))
    value = str(getattr(game, "riddle_input", "") or "")
    boxes = []
    box_w, gap = 54, 8
    total = length * box_w + (length - 1) * gap
    x0 = right.centerx - total // 2
    for index in range(length):
        box = pygame.Rect(x0 + index * (box_w + gap), right.y + 30, box_w, 62)
        pygame.draw.rect(surface, (34, 34, 44), box, border_radius=8)
        pygame.draw.rect(surface, COLOR_BORDER, box, width=1, border_radius=8)
        if index < len(value):
            digit = get_font(30, bold=True).render(value[index], True, COLOR_TEXT)
            surface.blit(digit, digit.get_rect(center=box.center))
        boxes.append(box)
    game.riddle_rects = {"digits": boxes, "keys": {}, "hint": None, "back": None}

    message = str(getattr(game, "riddle_message", "") or "")
    if message:
        if message.startswith("Замок"):
            col = COLOR_GREEN
        elif message.startswith("Подсказка"):
            col = COLOR_ACCENT
        elif message.startswith("Не тот код"):
            col = COLOR_RED
        else:
            col = COLOR_TEXT_DIM
        surface.blit(
            get_font(11, bold=True).render(message[:80], True, col),
            (right.x + 20, right.y + 104),
        )
    attempts = int(getattr(game, "riddle_attempts", 0) or 0)
    if attempts:
        surface.blit(
            get_font(10).render(f"неудачных попыток: {attempts}", True, COLOR_TEXT_DARK),
            (right.x + 20, right.y + 122),
        )

    key_w, key_h, key_gap = 84, 52, 10
    grid_w = 3 * key_w + 2 * key_gap
    gx = right.centerx - grid_w // 2
    gy = right.y + 150
    mouse = game._to_logical(pygame.mouse.get_pos())
    for row_index, row in enumerate(KEYPAD):
        for col_index, label in enumerate(row):
            rect = pygame.Rect(
                gx + col_index * (key_w + key_gap), gy + row_index * (key_h + key_gap), key_w, key_h
            )
            hovered = rect.collidepoint(mouse)
            accent = label == "OK"
            clear = label == "C"
            bg = (52, 46, 30) if hovered and not clear else ((30, 30, 40) if not clear else (38, 28, 30))
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(
                surface,
                COLOR_ACCENT if accent else ((190, 90, 80) if clear else COLOR_BORDER),
                rect,
                width=2 if accent else 1,
                border_radius=8,
            )
            font = get_font(18 if label.isdigit() else 14, bold=True)
            text = font.render(label, True, COLOR_TEXT if not clear else (220, 140, 130))
            surface.blit(text, text.get_rect(center=rect.center))
            game.riddle_rects["keys"][label] = rect

    hint_btn = Button(
        (right.x + 20, right.bottom - 46, 200, 32),
        f"ПОДСКАЗКА (+{riddle_logic.HINT_MINUTES} мин)",
        enabled=not bool(hint_text),
    )
    back_btn = Button((right.right - 180, right.bottom - 46, 160, 32), "← УЙТИ")
    for btn in (hint_btn, back_btn):
        btn.update(mouse, pygame.mouse.get_pressed()[0])
        btn.draw(surface, get_font(11, bold=True))
    game.riddle_rects["hint"] = hint_btn.rect
    game.riddle_rects["back"] = back_btn.rect


def _append(game, digit: str) -> None:
    item = getattr(game, "riddle", None)
    length = riddle_logic.answer_length(item)
    value = str(getattr(game, "riddle_input", "") or "")
    if len(value) >= length:
        return
    game.riddle_input = value + digit
    game.riddle_message = ""


def _erase(game) -> None:
    game.riddle_input = str(getattr(game, "riddle_input", "") or "")[:-1]
    game.riddle_message = ""


def submit(game) -> None:
    item = getattr(game, "riddle", None)
    if not item:
        return
    result = riddle_logic.check(game.state, item, getattr(game, "riddle_input", ""))
    status = result.get("status")
    if status == "ok":
        game.riddle_message = "Замок открыт"
        game.audio.play_sfx("success")
        clue = getattr(game, "riddle_clue", None)
        game.riddle = None
        game.riddle_clue = None
        game.riddle_input = ""
        game.riddle_hint = ""
        game.riddle_message = ""
        save_game(game.state)
        if clue is not None:
            game.open_puzzle(clue)
        else:
            game.screen_name = "location"
        return
    if status == "solved":
        clue = getattr(game, "riddle_clue", None)
        game.riddle = None
        game.riddle_clue = None
        if clue is not None:
            game.open_puzzle(clue)
        return
    if status == "wrong":
        game.riddle_attempts = int(getattr(game, "riddle_attempts", 0) or 0) + 1
        game.riddle_input = ""
        minutes = result.get("minutes", 0)
        game.riddle_message = f"Не тот код: −{minutes} мин. Попробуйте ещё."
        game.audio.play_sfx("fail")
        game.add_notification(f"Кодовый замок: неверный код, −{minutes} мин")
        save_game(game.state)
        return
    game.riddle_message = "Введите код"


def show_hint(game) -> None:
    if getattr(game, "riddle_hint", ""):
        return
    result = riddle_logic.hint(game.state, getattr(game, "riddle", None))
    if result.get("status") != "ok":
        return
    game.riddle_hint = result.get("text", "")
    game.riddle_message = f"Подсказка: −{result.get('minutes', 0)} мин"
    game.audio.play_sfx("page")
    save_game(game.state)


def leave(game) -> None:
    game.riddle = None
    game.riddle_clue = None
    game.riddle_input = ""
    game.riddle_hint = ""
    game.riddle_message = ""
    game.screen_name = "location"


def handle_riddle_click(game, pos) -> bool:
    rects = getattr(game, "riddle_rects", {}) or {}
    if rects.get("back") and rects["back"].collidepoint(pos):
        leave(game)
        return True
    if rects.get("hint") and rects["hint"].collidepoint(pos):
        show_hint(game)
        return True
    for label, rect in (rects.get("keys") or {}).items():
        if not rect.collidepoint(pos):
            continue
        if label == "OK":
            submit(game)
        elif label == "C":
            _erase(game)
        else:
            _append(game, label)
        return True
    return False


def handle_riddle_key(game, event) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_ESCAPE:
        leave(game)
        return True
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        submit(game)
        return True
    if event.key == pygame.K_BACKSPACE:
        _erase(game)
        return True
    typed = str(getattr(event, "unicode", "") or "")
    if len(typed) == 1 and typed.isdigit():
        _append(game, typed)
        return True
    name = pygame.key.name(event.key).lower()
    if name.startswith("kp") and name[2:].isdigit():
        name = name[2:]
    if len(name) == 1 and name.isdigit():
        _append(game, name)
        return True
    return False


__all__ = [
    "draw_riddle",
    "handle_riddle_click",
    "handle_riddle_key",
    "leave",
    "show_hint",
    "submit",
]
