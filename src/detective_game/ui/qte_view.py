"""Экран редкого QTE «драка в баре».

Логика — в :mod:`detective_game.qte`. Игрок жмёт стрелку, которая появилась
на экране, пока не истекла шкала. Три точных нажатия — победа и уважение бара,
два промаха — потерянное время (дело при этом не ломается).
"""

from __future__ import annotations

import random

import pygame

from .. import qte
from ..config import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
)
from ..save_system import save_game
from .widgets import Button, draw_panel, get_font

ARROWS = {"left": "←", "right": "→", "up": "↑", "down": "↓"}
KEYS = {
    "left": (pygame.K_LEFT, pygame.K_a),
    "right": (pygame.K_RIGHT, pygame.K_d),
    "up": (pygame.K_UP, pygame.K_w),
    "down": (pygame.K_DOWN, pygame.K_s),
}


def chance_for(case_id: str) -> bool:
    """Бывает ли драка в этом деле (стабильно для дела)."""
    return random.Random(f"fight:{case_id}").random() < 0.35


def available(game) -> bool:
    """Можно ли затеять драку: бар, дело идёт, ещё не было."""
    case = game.current_case or {}
    if str(getattr(game, "location_id", "")) != "bar":
        return False
    return bool(case.get("id")) and not getattr(game.state, "fight_done", False)


def start(game) -> bool:
    case_id = str((game.current_case or {}).get("id", ""))
    if not available(game):
        return False
    game.qte = qte.BarFight(seed=f"{case_id}:{game.state.case_time_minutes}")
    game.qte_settled = False
    game.screen_name = "qte"
    game.audio.play_music("chase")
    return True


def update(game, dt: float) -> None:
    fight = getattr(game, "qte", None)
    if not fight:
        return
    if not fight.finished:
        fight.update(dt)
    if fight.finished and not getattr(game, "qte_settled", False):
        game.qte_settled = True
        game.state.fight_done = True
        reward = qte.reward(fight.success)
        if reward["reputation"]:
            game.state.reputation += int(reward["reputation"])
        if reward["money"]:
            game.state.money += int(reward["money"])
        if reward["time"]:
            game.state.case_time_minutes += int(reward["time"])
        game.add_notification(
            "Драка выиграна: +1 репутация, +$40"
            if fight.success
            else "Драка проиграна: потеряно 20 минут"
        )
        game.audio.play_sfx("success" if fight.success else "fail")
        save_game(game.state)


def draw(game) -> None:
    fight = getattr(game, "qte", None)
    surface = game.screen
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    if not fight:
        game.screen_name = "location"
        return
    panel = pygame.Rect(width // 2 - 320, 120, 640, 420)
    draw_panel(surface, panel)
    title = get_font(24, bold=True).render("ДРАКА В БАРЕ", True, COLOR_ACCENT)
    surface.blit(title, title.get_rect(center=(panel.centerx, panel.y + 38)))
    sub = get_font(12).render(
        "Жмите стрелку, пока шкала не кончилась. Два промаха — и вы на улице.",
        True,
        COLOR_TEXT_DIM,
    )
    surface.blit(sub, sub.get_rect(center=(panel.centerx, panel.y + 70)))
    if not fight.finished:
        prompt = fight.prompt or ""
        # фигура «противника» и подсказка
        pygame.draw.circle(surface, (70, 52, 48), (panel.centerx, panel.y + 170), 52)
        glyph = get_font(64, bold=True).render(ARROWS.get(prompt, "?"), True, COLOR_ACCENT)
        surface.blit(glyph, glyph.get_rect(center=(panel.centerx, panel.y + 170)))
        key = get_font(12, bold=True).render(
            qte.PROMPT_KEYS.get(prompt, ""), True, COLOR_TEXT
        )
        surface.blit(key, key.get_rect(center=(panel.centerx, panel.y + 240)))
        # шкала времени
        bar = pygame.Rect(panel.x + 60, panel.y + 280, panel.w - 120, 22)
        pygame.draw.rect(surface, (34, 34, 44), bar, border_radius=11)
        ratio = fight.progress
        color = COLOR_GREEN if ratio > 0.5 else (COLOR_ACCENT if ratio > 0.22 else COLOR_RED)
        fill = pygame.Rect(bar.x, bar.y, int(bar.w * ratio), bar.h)
        if fill.w:
            pygame.draw.rect(surface, color, fill, border_radius=11)
        pygame.draw.rect(surface, COLOR_BORDER, bar, width=1, border_radius=11)
        pips = f"блоки {fight.hits}  •  промахи {fight.misses}/{qte.MAX_MISSES}"
        surface.blit(
            get_font(12, bold=True).render(pips, True, COLOR_TEXT_DIM),
            (bar.x, bar.bottom + 12),
        )
        surface.blit(
            get_font(13, bold=True).render(fight.message[:90], True, COLOR_TEXT),
            (bar.x, bar.bottom + 38),
        )
    else:
        colour = COLOR_GREEN if fight.success else COLOR_RED
        head = get_font(20, bold=True).render(
            "ВЫ УСТОЯЛИ" if fight.success else "ВАС ВЫТОЛКАЛИ", True, colour
        )
        surface.blit(head, head.get_rect(center=(panel.centerx, panel.y + 170)))
        text = fight.result_text
        surface.blit(
            get_font(12).render(text[:100], True, COLOR_TEXT_DIM),
            (panel.x + 40, panel.y + 205),
        )
        reward_bits = []
        if fight.success:
            reward_bits.append("+1 репутация")
            reward_bits.append("+$40")
        else:
            reward_bits.append("−20 минут")
        surface.blit(
            get_font(12, bold=True).render("  •  ".join(reward_bits), True, colour),
            (panel.x + 40, panel.y + 240),
        )
    mouse = game._to_logical(pygame.mouse.get_pos())
    y = height - 58
    if fight.finished:
        btn = Button((width - 210, y, 190, 40), "ПРОДОЛЖИТЬ", accent=True)
        btn.update(mouse, pygame.mouse.get_pressed()[0])
        btn.draw(surface, get_font(12, bold=True))
        game.qte_rects = {"next": btn.rect}
    else:
        back = Button((20, y, 150, 40), "← УЙТИ")
        back.update(mouse, pygame.mouse.get_pressed()[0])
        back.draw(surface, get_font(12, bold=True))
        game.qte_rects = {"back": back.rect}


def handle_click(game, pos) -> bool:
    rects = getattr(game, "qte_rects", {}) or {}
    if rects.get("next") and rects["next"].collidepoint(pos):
        _finish(game)
        return True
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.qte = None
        game.screen_name = "location"
        return True
    return False


def _finish(game) -> None:
    game.qte = None
    game.screen_name = "location"
    game._music_screen = None


def handle_key(game, event) -> bool:
    """Клавиши QTE: стрелки/WASD — удар, ESC — уйти, Enter — продолжить."""
    fight = getattr(game, "qte", None)
    if not fight or event.type != pygame.KEYDOWN:
        return False
    if fight.finished:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            _finish(game)
            return True
        return False
    if event.key == pygame.K_ESCAPE:
        game.qte = None
        game.screen_name = "location"
        return True
    for direction, keys in KEYS.items():
        if event.key in keys:
            hit = fight.press(direction)
            game.audio.play_sfx("dial" if hit else "fail")
            return True
    return False


__all__ = [
    "available",
    "chance_for",
    "draw",
    "handle_click",
    "handle_key",
    "start",
    "update",
]
