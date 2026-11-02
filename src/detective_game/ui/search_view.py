"""Обыск локации: хотспоты поверх иллюстрации и таймер.

Логика — в :mod:`detective_game.search`. Здесь рисуем точки поверх картинки
локации, ловим клики и показываем находки. Точки всегда в одних и тех же
местах (сид генератора — от id дела и локации), поэтому их можно запомнить.

Обыск стоит 10 игровых минут: либо нашёл всё, что было, либо ушёл.
"""

from __future__ import annotations

import math

import pygame

from .. import search
from ..config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_PANEL,
    COLOR_TEXT,
    COLOR_TEXT_DARK,
    COLOR_TEXT_DIM,
)
from ..save_system import save_game
from .widgets import get_font

SEARCH_MINUTES = 10


def is_active(game) -> bool:
    return getattr(game, "search", None) is not None


def start(game, location_id: str | None = None) -> None:
    """Начать обыск локации."""
    case = game.current_case or {}
    location_id = str(location_id or getattr(game, "location_id", "") or "")
    game.search = search.Search(case, location_id, game.state)
    game.search_visual = getattr(game, "search_visual", None)
    game.search_message = ""
    game.audio.play_sfx("page")


def stop(game, reason: str = "", minutes: int | None = None) -> None:
    """Закончить обыск: время за попытку и уведомление."""
    session = getattr(game, "search", None)
    if not session:
        return
    spent = SEARCH_MINUTES if minutes is None else max(0, int(minutes))
    game.state.case_time_minutes += spent
    caught = bool(getattr(session, "caught", False))
    if caught:
        text = f"Патруль заметил вас — обыск прерван. Потеряно {spent} минут."
    elif session.expired or reason == "time":
        text = f"Время вышло — хозяин вернулся. Попытка стоила {spent} минут."
    elif session.clue_spots_left == 0 and session.found_count:
        text = f"Вы нашли всё, что здесь было. +{spent} минут."
    else:
        text = f"Вы закончили обыск. +{spent} минут."
    if reason and not caught:
        text = reason
    game.add_notification(text)
    game.search = None
    game.search_message = ""
    save_game(game.state)


def title_text(session) -> str:
    return f"{session.found_count}/{session.total} точек  •  осталось улик: {session.clue_spots_left}"


def _spot_center(visual: pygame.Rect, spot) -> tuple:
    return (
        int(visual.x + float(spot["x"]) * visual.w),
        int(visual.y + float(spot["y"]) * visual.h),
    )


def draw_overlay(game, visual: pygame.Rect) -> None:
    """Хотспоты, таймер и кнопка «ЗАКОНЧИТЬ» поверх иллюстрации локации."""
    session = getattr(game, "search", None)
    if not session:
        return
    surface = game.screen
    game.search_visual = pygame.Rect(visual)
    # сектор, который сейчас проходит патруль
    if getattr(session, "patrol_on", False):
        px, py, pw, ph = session.patrol_rect()
        zone = pygame.Rect(
            visual.x + int(px * visual.w),
            visual.y + int(py * visual.h),
            int(pw * visual.w),
            int(ph * visual.h),
        )
        shade = pygame.Surface((zone.w, zone.h), pygame.SRCALPHA)
        shade.fill((190, 60, 60, 46))
        surface.blit(shade, zone.topleft)
        pygame.draw.rect(surface, (210, 90, 90), zone, width=2, border_radius=6)
        warn = get_font(10, bold=True).render("ПАТРУЛЬ", True, (240, 190, 190))
        chip = pygame.Rect(zone.x + 10, zone.y + 10, warn.get_width() + 14, 18)
        pygame.draw.rect(surface, (40, 16, 16), chip, border_radius=8)
        surface.blit(warn, (chip.x + 7, chip.y + 3))
    # рамка обыска
    pygame.draw.rect(surface, COLOR_ACCENT, visual, width=2, border_radius=8)
    mouse = game._to_logical(pygame.mouse.get_pos())
    pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 240.0)
    for spot in session.spots:
        cx, cy = _spot_center(visual, spot)
        radius = 12 if spot["kind"] == "clue" else 9
        halo = int(radius + 7 + 4 * pulse)
        ring = pygame.Surface((halo * 2, halo * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (250, 220, 130, 150), (halo, halo), halo, 2)
        surface.blit(ring, (cx - halo, cy - halo))
        col = COLOR_ACCENT if spot["kind"] == "clue" else (215, 215, 228)
        # тёмная подложка, чтобы точка читалась на любой иллюстрации
        pygame.draw.circle(surface, (14, 14, 20), (cx, cy), radius + 3)
        pygame.draw.circle(surface, col, (cx, cy), radius)
        pygame.draw.circle(surface, (60, 60, 70), (cx, cy), radius, 2)
        pygame.draw.circle(surface, (18, 18, 24), (cx, cy), max(2, radius // 3))
        if pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2).collidepoint(mouse):
            guarded = getattr(session, "patrol_on", False) and session.in_patrol(
                spot["x"], spot["y"]
            )
            if guarded:
                label = get_font(9, bold=True).render("ПАТРУЛЬ", True, (250, 220, 220))
                chip = pygame.Rect(0, 0, label.get_width() + 10, 16)
                chip.center = (cx, cy - radius - 14)
                pygame.draw.rect(surface, (150, 50, 50), chip, border_radius=8)
                surface.blit(label, (chip.x + 5, chip.y + 3))
            else:
                label = get_font(9, bold=True).render(
                    "ОБЫСКАТЬ" if spot["kind"] == "clue" else "ПРОВЕРИТЬ", True, (18, 18, 18)
                )
                chip = pygame.Rect(0, 0, label.get_width() + 10, 16)
                chip.center = (cx, cy - radius - 14)
                pygame.draw.rect(surface, col, chip, border_radius=8)
                surface.blit(label, (chip.x + 5, chip.y + 3))
    # таймер и счёт
    seconds = int(math.ceil(session.remaining))
    bar = pygame.Rect(visual.x + 10, visual.y + 10, visual.w - 20, 30)
    overlay = pygame.Surface((bar.w, bar.h), pygame.SRCALPHA)
    overlay.fill((8, 10, 16, 200))
    surface.blit(overlay, bar.topleft)
    pygame.draw.rect(surface, COLOR_BORDER, bar, width=1, border_radius=6)
    label = get_font(11, bold=True).render(f"ОБЫСК  •  {title_text(session)}", True, COLOR_TEXT)
    surface.blit(label, (bar.x + 10, bar.y + 8))
    timer_col = COLOR_GREEN if seconds > 20 else (COLOR_ACCENT if seconds > 10 else (210, 90, 90))
    timer = get_font(12, bold=True).render(f"{seconds // 60}:{seconds % 60:02d}", True, timer_col)
    surface.blit(timer, (bar.right - timer.get_width() - 10, bar.y + 7))
    inner = pygame.Rect(bar.x + 6, bar.bottom - 6, bar.w - 12, 3)
    pygame.draw.rect(surface, (40, 40, 50), inner)
    ratio = session.remaining / max(1.0, float(session.seconds))
    pygame.draw.rect(surface, timer_col, (inner.x, inner.y, int(inner.w * ratio), inner.h))
    # кнопка «закончить»
    finish = pygame.Rect(visual.right - 120, visual.bottom - 40, 110, 28)
    hovered = finish.collidepoint(mouse)
    pygame.draw.rect(surface, (50, 44, 34) if hovered else (30, 30, 38), finish, border_radius=6)
    pygame.draw.rect(surface, COLOR_ACCENT, finish, width=1, border_radius=6)
    ftext = get_font(10, bold=True).render("ЗАКОНЧИТЬ", True, COLOR_ACCENT)
    surface.blit(ftext, ftext.get_rect(center=finish.center))
    message = str(getattr(game, "search_message", "") or "")
    if message:
        msg = get_font(10).render(message[:64], True, COLOR_TEXT)
        chip = pygame.Rect(visual.x + 10, visual.y + 46, min(visual.w - 140, msg.get_width() + 16), 22)
        pygame.draw.rect(surface, (12, 14, 20), chip, border_radius=6)
        surface.blit(msg, (chip.x + 8, chip.y + 6))
    game.search_rects = {"finish": finish, "visual": pygame.Rect(visual)}


def handle_click(game, pos) -> bool:
    """Клик в обыске. True — клик был по обыску."""
    session = getattr(game, "search", None)
    if not session:
        return False
    rects = getattr(game, "search_rects", {}) or {}
    visual = rects.get("visual") or getattr(game, "search_visual", None)
    finish = rects.get("finish")
    if finish and finish.collidepoint(pos):
        stop(game)
        return True
    if not visual or not visual.collidepoint(pos):
        return False
    x = (pos[0] - visual.x) / max(1, visual.w)
    y = (pos[1] - visual.y) / max(1, visual.h)
    if getattr(session, "patrol_on", False) and session.in_patrol(x, y):
        session.caught = True
        session.skip()
        game.search_message = "Патруль заметил вас — обыск прерван."
        game.audio.play_sfx("fail")
        return True
    spot = session.at(x, y)
    if not spot:
        minutes = session.miss()
        game.search_message = (
            f"Здесь пусто. −{minutes} мин." if minutes else "Здесь пусто."
        )
        game.audio.play_sfx("tick")
        return True
    taken = session.take(spot)
    if not taken:
        return True
    if taken["kind"] == "clue":
        clue = next(
            (c for c in (game.current_case or {}).get("clues", []) if c["id"] == taken["clue"]),
            None,
        )
        name = clue.get("title", taken["clue"]) if clue else taken["clue"]
        game.search_message = f"Найдено: {name}"
        game.add_notification(f"Обыск: найдено «{name}» — теперь можно изучить")
        game.audio.play_sfx("clue")
    else:
        game.search_message = str(taken["label"])[:70]
        game.audio.play_sfx("tick")
    save_game(game.state)
    if session.finished:
        stop(game)
    return True


def button_rect(visual: pygame.Rect) -> pygame.Rect:
    """Кнопка «ОБЫСКАТЬ» в углу иллюстрации локации."""
    return pygame.Rect(visual.right - 120, visual.y + 12, 110, 28)


def draw_start_button(game, visual: pygame.Rect) -> None:
    """Кнопка запуска обыска, когда он ещё не идёт."""
    surface = game.screen
    mouse = game._to_logical(pygame.mouse.get_pos())
    rect = button_rect(visual)
    hovered = rect.collidepoint(mouse)
    pygame.draw.rect(surface, (52, 46, 32) if hovered else (24, 24, 32), rect, border_radius=6)
    pygame.draw.rect(surface, COLOR_ACCENT, rect, width=1, border_radius=6)
    label = get_font(10, bold=True).render("ОБЫСКАТЬ", True, COLOR_ACCENT)
    surface.blit(label, label.get_rect(center=rect.center))
    game.search_start_rect = rect


def handle_start_click(game, pos) -> bool:
    rect = getattr(game, "search_start_rect", None)
    if rect and rect.collidepoint(pos):
        start(game)
        return True
    return False


__all__ = [
    "button_rect",
    "draw_overlay",
    "draw_start_button",
    "handle_click",
    "handle_start_click",
    "is_active",
    "start",
    "stop",
]
