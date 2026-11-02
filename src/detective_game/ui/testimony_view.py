"""Экран сопоставления показаний: перекрёстный допрос.

Логика — в :mod:`detective_game.testimony`. Здесь два списка: слева услышанные
реплики (только те, что игрок реально открыл в допросах), справа — уже
найденные противоречия. Выбираем две реплики и жмём «СОПОСТАВИТЬ»: если они
противоречат друг другу, вывод отправляется на доску, репутация растёт.

Кнопка живёт на доске версий — там же, где связки.
"""

from __future__ import annotations

import pygame

from .. import testimony
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

ROW_HEIGHT = 62
MAX_ROWS = 7
SCROLL_WHEEL = 2


def rows(game):
    """Строки списка реплик и прямоугольники под них."""
    case = game.current_case or {}
    return testimony.statements(case, game.state)


def scroll_limit(game) -> int:
    """Максимальное смещение списка реплик."""
    return max(0, len(rows(game)) - MAX_ROWS)


def scroll(game, delta: int) -> int:
    """Прокрутить список реплик и вернуть новое смещение."""
    limit = scroll_limit(game)
    current = int(getattr(game, "testimony_scroll", 0) or 0)
    current = max(0, min(current + int(delta), limit))
    game.testimony_scroll = current
    return current


def visible_rows(game):
    """(видимые строки, смещение, всего строк) — с прокруткой."""
    everything = rows(game)
    limit = max(0, len(everything) - MAX_ROWS)
    offset = max(0, min(int(getattr(game, "testimony_scroll", 0) or 0), limit))
    game.testimony_scroll = offset
    return everything[offset : offset + MAX_ROWS], offset, len(everything)


def draw_testimony(game) -> None:
    """Отрисовать экран сопоставления показаний."""
    surface = game.screen
    case = game.current_case or {}
    state = game.state
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    title = get_font(22, bold=True).render("СОПОСТАВЛЕНИЕ ПОКАЗАНИЙ", True, COLOR_ACCENT)
    surface.blit(title, (header.x + 18, header.y + 8))
    surface.blit(
        get_font(11).render(
            "Выберите две реплики, которые не могут быть правдой одновременно.",
            True,
            COLOR_TEXT_DIM,
        ),
        (header.x + 18, header.y + 40),
    )
    summary = testimony.summary(case, state)
    meta = get_font(12, bold=True).render(summary, True, COLOR_TEXT)
    surface.blit(meta, (header.right - meta.get_width() - 18, header.y + 22))

    body = pygame.Rect(20, 90, width - 40, height - 160)
    draw_panel(surface, body)
    left = pygame.Rect(body.x + 16, body.y + 16, int(body.w * 0.58) - 24, body.h - 32)
    right = pygame.Rect(left.right + 16, body.y + 16, body.right - left.right - 32, body.h - 32)

    mouse = game._to_logical(pygame.mouse.get_pos())
    pressed = pygame.mouse.get_pressed()[0]
    game.testimony_rects = {
        "rows": {},
        "compare": None,
        "reset": None,
        "back": None,
        "up": None,
        "down": None,
    }

    section = get_font(12, bold=True).render("УСЛЫШАННЫЕ РЕПЛИКИ", True, COLOR_TEXT)
    surface.blit(section, (left.x, left.y))
    shown, offset, total_rows = visible_rows(game)
    if total_rows > MAX_ROWS:
        counter = get_font(10, bold=True).render(
            f"{offset + 1}–{offset + len(shown)} из {total_rows}", True, COLOR_TEXT_DIM
        )
        surface.blit(counter, (left.x + section.get_width() + 12, left.y + 1))
        up = pygame.Rect(left.right - 54, left.y - 4, 24, 22)
        down = pygame.Rect(left.right - 26, left.y - 4, 24, 22)
        for rect, arrow, enabled, delta in (
            (up, "▲", offset > 0, -MAX_ROWS),
            (down, "▼", offset + MAX_ROWS < total_rows, MAX_ROWS),
        ):
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(
                surface,
                (48, 42, 28) if hovered and enabled else (28, 28, 36),
                rect,
                border_radius=5,
            )
            pygame.draw.rect(
                surface,
                COLOR_ACCENT if enabled else (62, 62, 74),
                rect,
                width=1,
                border_radius=5,
            )
            label = get_font(10, bold=True).render(
                arrow, True, COLOR_ACCENT if enabled else COLOR_TEXT_DARK
            )
            surface.blit(label, label.get_rect(center=rect.center))
            if enabled:
                game.testimony_rects["up" if delta < 0 else "down"] = rect
    if not rows(game):
        draw_text_wrapped(
            surface,
            "Пока нечего сопоставлять: сначала поговорите с людьми.",
            get_font(12),
            COLOR_TEXT_DIM,
            pygame.Rect(left.x, left.y + 30, left.w, 80),
        )
    y = left.y + 26
    for item in shown:
        rect = pygame.Rect(left.x, y, left.w, ROW_HEIGHT)
        selected = item["key"] in game.testimony_selected
        hovered = rect.collidepoint(mouse)
        border = COLOR_ACCENT if selected else (COLOR_BORDER if not hovered else COLOR_TEXT_DIM)
        pygame.draw.rect(surface, (46, 42, 30) if selected else (30, 30, 40), rect, border_radius=7)
        pygame.draw.rect(surface, border, rect, width=2 if selected else 1, border_radius=7)
        name = get_font(11, bold=True).render(item["char"].upper(), True, COLOR_ACCENT)
        surface.blit(name, (rect.x + 10, rect.y + 7))
        draw_text_wrapped(
            surface,
            item["text"][:110],
            get_font(11),
            COLOR_TEXT,
            pygame.Rect(rect.x + 10, rect.y + 24, rect.w - 20, 34),
        )
        game.testimony_rects["rows"][item["key"]] = rect
        y += ROW_HEIGHT + 6

    # выбранные реплики видны всегда — даже если список прокрутили
    if game.testimony_selected:
        picked = []
        for key in game.testimony_selected:
            item = testimony.statement(case, key) or {}
            picked.append(item.get("char", "?"))
        line = get_font(10, bold=True).render(
            "Выбрано: " + " + ".join(picked), True, COLOR_ACCENT
        )
        surface.blit(line, (left.x, left.bottom - 18))

    # правая колонка: найденные противоречия
    surface.blit(
        get_font(12, bold=True).render("НАЙДЕННЫЕ ПРОТИВОРЕЧИЯ", True, COLOR_TEXT),
        (right.x, right.y),
    )
    solved = testimony.solved(state, case)
    y = right.y + 26
    if not solved:
        draw_text_wrapped(
            surface,
            "Пока пусто. Правильная пара даст вывод и репутацию.",
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(right.x, y, right.w, 50),
        )
    for ded_id in solved:
        item = testimony.deduction(case, ded_id) or {}
        block = pygame.Rect(right.x, y, right.w, 84)
        if block.bottom > right.bottom - 90:
            break
        pygame.draw.rect(surface, (28, 38, 30), block, border_radius=7)
        pygame.draw.rect(surface, COLOR_GREEN, block, width=1, border_radius=7)
        surface.blit(
            get_font(11, bold=True).render(item.get("title", "Вывод"), True, COLOR_GREEN),
            (block.x + 10, block.y + 6),
        )
        draw_text_wrapped(
            surface,
            item.get("text", "")[:150],
            get_font(10),
            COLOR_TEXT_DIM,
            pygame.Rect(block.x + 10, block.y + 24, block.w - 20, 54),
        )
        y += 92
    hints = testimony.hints(case, state)
    if hints:
        hint = f"Непроверенных пар: {len(hints)} — обе реплики уже открыты"
        draw_text_wrapped(
            surface,
            hint,
            get_font(10),
            COLOR_ACCENT,
            pygame.Rect(right.x, right.bottom - 42, right.w, 40),
        )

    message = str(getattr(game, "testimony_message", "") or "")
    if message:
        col = COLOR_GREEN if message.startswith("Найдено") else COLOR_TEXT_DIM
        surface.blit(get_font(11, bold=True).render(message[:110], True, col), (body.x + 20, body.bottom - 26))

    # футер
    compare = Button(
        (20, height - 58, 200, 40),
        "СОПОСТАВИТЬ",
        accent=True,
        enabled=len(game.testimony_selected) == 2,
    )
    reset = Button((232, height - 58, 150, 40), "СБРОСИТЬ")
    back = Button((width - 170, height - 58, 150, 40), "← НАЗАД")
    for btn in (compare, reset, back):
        btn.update(mouse, pressed)
        btn.draw(surface, get_font(12, bold=True))
    game.testimony_rects["compare"] = compare.rect
    game.testimony_rects["reset"] = reset.rect
    game.testimony_rects["back"] = back.rect


def _toggle(game, key: str) -> None:
    if key in game.testimony_selected:
        game.testimony_selected.remove(key)
    else:
        game.testimony_selected.append(key)
        if len(game.testimony_selected) > 2:
            game.testimony_selected.pop(0)
    game.testimony_message = ""


def _compare(game) -> None:
    case = game.current_case or {}
    keys = list(game.testimony_selected)
    if len(keys) != 2:
        return
    result = testimony.check(game.state, case, keys[0], keys[1])
    status = result.get("status")
    if status == "ok":
        item = result.get("deduction") or {}
        game.testimony_message = f"Найдено: «{item.get('title', 'противоречие')}»"
        game.add_notification(
            f"Противоречие: {item.get('title', '')} — +{result.get('reputation', 0)} к репутации"
        )
        game.audio.play_sfx("success")
        game.testimony_selected = []
        save_game(game.state)
    elif status == "already":
        game.testimony_message = "Это противоречие уже найдено"
        game.audio.play_sfx("tick")
    elif status == "wrong":
        game.testimony_message = "Эти реплики не противоречат друг другу — время и доверие потеряны"
        game.add_notification("Показания не противоречат: −2 мин, доверие −1")
        game.audio.play_sfx("fail")
        save_game(game.state)
    elif status == "same":
        game.testimony_message = "Это одна и та же реплика"
    else:
        game.testimony_message = "Сначала услышьте обе реплики в допросах"
        game.audio.play_sfx("tick")


def handle_testimony_click(game, pos) -> bool:
    """Клики по экрану (для тестов и событий)."""
    rects = getattr(game, "testimony_rects", {}) or {}
    if rects.get("up") and rects["up"].collidepoint(pos):
        scroll(game, -MAX_ROWS)
        return True
    if rects.get("down") and rects["down"].collidepoint(pos):
        scroll(game, MAX_ROWS)
        return True
    for key, rect in (rects.get("rows") or {}).items():
        if rect.collidepoint(pos):
            _toggle(game, key)
            return True
    if rects.get("compare") and rects["compare"].collidepoint(pos):
        _compare(game)
        return True
    if rects.get("reset") and rects["reset"].collidepoint(pos):
        game.testimony_selected = []
        game.testimony_message = ""
        return True
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.screen_name = "notebook"
        game.notebook_tab = "board"
        game.testimony_selected = []
        return True
    return False


def handle_testimony_scroll(game, steps: int) -> bool:
    """Прокрутка колесом мыши (steps > 0 — вниз)."""
    if scroll_limit(game) <= 0:
        return False
    scroll(game, int(steps))
    return True


def handle_testimony_key(game, event) -> bool:
    if event.type == pygame.MOUSEWHEEL:
        return handle_testimony_scroll(game, -SCROLL_WHEEL * int(event.y))
    if event.type != pygame.KEYDOWN:
        return False
    if event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
        scroll(game, MAX_ROWS if event.key == pygame.K_PAGEDOWN else 1)
        return True
    if event.key in (pygame.K_UP, pygame.K_PAGEUP):
        scroll(game, -MAX_ROWS if event.key == pygame.K_PAGEUP else -1)
        return True
    if event.key == pygame.K_ESCAPE:
        game.screen_name = "notebook"
        game.notebook_tab = "board"
        game.testimony_selected = []
        return True
    return False
