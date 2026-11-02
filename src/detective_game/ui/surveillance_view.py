"""Экран слежки: маршрут, дистанция и две шкалы риска.

Логика — в :mod:`detective_game.surveillance`. Управление: →/D — догонять,
←/A — отставать, ничего не зажато — идти ровно. Держите маркер дистанции в
зелёной зоне: ближе — заметят, дальше — потеряете.
"""

from __future__ import annotations

import pygame

from .. import surveillance
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
from .widgets import Button, draw_panel, draw_text_wrapped, get_font

PANEL_DARK = (20, 20, 27)


def start(game) -> bool:
    """Начать слежку: сначала маршрут, если он есть."""
    case = game.current_case or {}
    spec = surveillance.spec_for(case)
    if not spec or not surveillance.available(case, game.state):
        return False
    routes = surveillance.routes_for(case)
    game.tail_spec = spec
    if routes:
        game.route_rects = {}
        game.route_message = "Выберите маршрут: верный даст фору, крюк — сузит дистанцию."
        game.screen_name = "route"
        game.audio.play_music("chase")
        return True
    return begin_tail(game, spec)


def begin_tail(game, spec) -> bool:
    """Создать слежку по готовой спецификации."""
    game.tail = surveillance.Tail(spec)
    game.tail_reward = None
    game.tail_rewarded = False
    game.tail_rects = {}
    game.screen_name = "tail"
    game.audio.play_music("chase")
    return True


def choose_route(game, route) -> None:
    """Игрок выбрал маршрут до начала слежки."""
    case = game.current_case or {}
    spec = getattr(game, "tail_spec", None) or surveillance.spec_for(case)
    result = surveillance.plan(case, spec, route)
    game.state.case_time_minutes += int(result.get("minutes", 0) or 0)
    game.add_notification(
        f"Маршрут «{route.get('title')}»: {result.get('message', '')}".strip()
    )
    game.audio.play_sfx("page" if result.get("correct") else "tick")
    begin_tail(game, result["spec"])


def draw_route(game) -> None:
    """Экран прокладки маршрута перед слежкой."""
    surface = game.screen
    case = game.current_case or {}
    routes = surveillance.routes_for(case)
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    spec = getattr(game, "tail_spec", None) or surveillance.spec_for(case) or {}
    title = get_font(22, bold=True).render("ПЛАН СЛЕЖКИ", True, COLOR_ACCENT)
    surface.blit(title, (header.x + 18, header.y + 8))
    sub = get_font(11).render(
        f"{spec.get('target', 'Объект')}  •  {spec.get('place', '')}  •  выберите маршрут",
        True,
        COLOR_TEXT_DIM,
    )
    surface.blit(sub, (header.x + 18, header.y + 40))
    body = pygame.Rect(20, 90, width - 40, height - 160)
    draw_panel(surface, body)
    mouse = game._to_logical(pygame.mouse.get_pos())
    rects = {"cards": []}
    y = body.y + 24
    card_h = min(120, (body.h - 120) // max(1, len(routes)) - 12)
    for route in routes:
        card = pygame.Rect(body.x + 24, y, body.w - 48, card_h)
        hovered = card.collidepoint(mouse)
        bg = (44, 42, 34) if hovered else (30, 30, 40)
        pygame.draw.rect(surface, bg, card, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT if hovered else COLOR_BORDER, card, width=2 if hovered else 1, border_radius=10)
        name = get_font(17, bold=True).render(str(route["title"]), True, COLOR_TEXT)
        surface.blit(name, (card.x + 18, card.y + 14))
        minutes = get_font(12, bold=True).render(f"{route['minutes']} мин", True, COLOR_ACCENT)
        surface.blit(minutes, (card.right - minutes.get_width() - 20, card.y + 16))
        draw_text_wrapped(
            surface,
            str(route["note"]),
            get_font(12),
            COLOR_TEXT_DIM,
            pygame.Rect(card.x + 18, card.y + 44, card.w - 36, card.h - 56),
        )
        rects["cards"].append((route, card))
        y += card_h + 12
    message = str(getattr(game, "route_message", "") or "")
    if message:
        surface.blit(get_font(11).render(message[:120], True, COLOR_TEXT_DIM), (body.x + 24, body.bottom - 24))
    game.route_rects = rects
    back = Button((20, height - 58, 150, 40), "← ОТМЕНА")
    back.update(mouse, pygame.mouse.get_pressed()[0])
    back.draw(surface, get_font(12, bold=True))
    game.route_rects["back"] = back.rect


def handle_route_click(game, pos) -> bool:
    rects = getattr(game, "route_rects", {}) or {}
    if rects.get("back") and rects["back"].collidepoint(pos):
        game.screen_name = "map"
        return True
    for route, card in rects.get("cards") or []:
        if card.collidepoint(pos):
            choose_route(game, route)
            return True
    return False


def handle_route_key(game, event) -> bool:
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        game.screen_name = "map"
        return True
    return False


def abort(game) -> None:
    game.tail = None
    game.screen_name = "map"


def _advance(game) -> int:
    keys = pygame.key.get_pressed()
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        return 1
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        return -1
    return 0


def update(game, dt: float) -> None:
    """Шаг слежки + награда один раз."""
    tail = getattr(game, "tail", None)
    if not tail:
        return
    if not tail.finished:
        tail.update(dt, _advance(game))
    if not tail.finished or getattr(game, "tail_rewarded", False):
        return
    game.tail_rewarded = True
    if tail.success:
        reward = surveillance.apply_reward(game.current_case, game.state, tail.spec)
        game.tail_reward = reward
        game.audio.play_sfx("success")
        if reward.get("reveal"):
            game.add_notification("Слежка удалась: найдена новая улика")
        if reward.get("money"):
            game.add_notification(f"Гонорар за слежку: ${reward['money']}")
    else:
        game.audio.play_sfx("fail")
        game.add_notification(tail.last_event or "Слежка сорвалась")
    save_game(game.state)


def _draw_detective(surface, center) -> None:
    """Силуэт: шляпа, плечи, плащ — понятно без подписи."""
    cx, cy = center
    coat = (74, 92, 78)
    pygame.draw.circle(surface, (206, 182, 152), (cx, cy - 12), 8)  # голова
    pygame.draw.ellipse(surface, (24, 24, 30), (cx - 14, cy - 24, 28, 7))  # поля шляпы
    pygame.draw.rect(surface, (24, 24, 30), (cx - 8, cy - 30, 16, 9), border_radius=3)
    pygame.draw.polygon(
        surface,
        coat,
        [(cx - 12, cy - 4), (cx + 12, cy - 4), (cx + 15, cy + 20), (cx - 15, cy + 20)],
    )


def _bar(surface, rect, value, color, label, font):
    pygame.draw.rect(surface, (36, 36, 46), rect, border_radius=6)
    fill = pygame.Rect(rect.x, rect.y, int(rect.w * max(0.0, min(1.0, value))), rect.h)
    if fill.w:
        pygame.draw.rect(surface, color, fill, border_radius=6)
    pygame.draw.rect(surface, COLOR_BORDER, rect, width=1, border_radius=6)
    surface.blit(font.render(label, True, COLOR_TEXT), (rect.x, rect.y - 16))


def draw(game) -> None:
    tail = getattr(game, "tail", None)
    surface = game.screen
    width, height = surface.get_size()
    surface.fill(COLOR_BG)
    if not tail:
        game.screen_name = "map"
        return
    header = pygame.Rect(20, 15, width - 40, 64)
    draw_panel(surface, header)
    title = get_font(22, bold=True).render(tail.title.upper(), True, COLOR_ACCENT)
    surface.blit(title, (header.x + 18, header.y + 8))
    sub = get_font(11).render(
        f"{tail.target}  •  {tail.place}  •  {tail.progress_text}", True, COLOR_TEXT_DIM
    )
    surface.blit(sub, (header.x + 18, header.y + 40))

    body = pygame.Rect(20, 90, width - 40, height - 160)
    draw_panel(surface, body)

    # маршрут объекта
    route = pygame.Rect(body.x + 40, body.y + 96, body.w - 80, 26)
    pygame.draw.rect(surface, (30, 30, 40), route, border_radius=13)
    filled = pygame.Rect(route.x, route.y, int(route.w * tail.progress), route.h)
    if filled.w:
        pygame.draw.rect(surface, COLOR_ACCENT, filled, border_radius=13)
    pygame.draw.rect(surface, COLOR_BORDER, route, width=1, border_radius=13)
    target_x = route.x + int(route.w * tail.progress)
    pygame.draw.circle(surface, (230, 226, 210), (target_x, route.centery), 12)
    pygame.draw.circle(surface, (16, 16, 22), (target_x, route.centery), 12, 2)
    surface.blit(
        get_font(11, bold=True).render("ОБЪЕКТ", True, COLOR_TEXT), (route.x, route.y - 20)
    )
    goal = get_font(10).render("ЦЕЛЬ", True, COLOR_TEXT_DIM)
    surface.blit(goal, (route.right - goal.get_width(), route.y - 18))
    # детектив позади объекта — серый силуэт в плаще и шляпе
    det_x = max(route.x + 8, target_x - int(tail.gap * 420))
    _draw_detective(surface, (det_x, route.centery + 52))
    surface.blit(
        get_font(10, bold=True).render("вы", True, COLOR_GREEN),
        (det_x + 17, route.centery + 46),
    )

    # шкала дистанции с зелёной зоной
    dist = pygame.Rect(body.x + 40, body.y + 196, body.w - 80, 26)
    pygame.draw.rect(surface, (30, 30, 40), dist, border_radius=13)
    low, high = tail.band
    zone = pygame.Rect(
        int(dist.x + low * dist.w), dist.y, max(8, int((high - low) * dist.w)), dist.h
    )
    pygame.draw.rect(surface, (32, 74, 46), zone, border_radius=8)
    pygame.draw.rect(surface, COLOR_GREEN, zone, width=1, border_radius=8)
    marker_x = dist.x + int(tail.gap * dist.w)
    pygame.draw.circle(surface, COLOR_TEXT if tail.in_band else COLOR_RED, (marker_x, dist.centery), 11)
    pygame.draw.circle(surface, (16, 16, 22), (marker_x, dist.centery), 11, 2)
    dist_label = get_font(11, bold=True).render("ДИСТАНЦИЯ", True, COLOR_TEXT)
    surface.blit(dist_label, (dist.right - dist_label.get_width(), dist.y - 20))
    surface.blit(get_font(10).render("близко", True, COLOR_TEXT_DIM), (dist.x, dist.bottom + 4))
    far = get_font(10).render("далеко", True, COLOR_TEXT_DIM)
    surface.blit(far, (dist.right - far.get_width(), dist.bottom + 4))
    _ = body

    # шкалы риска
    font = get_font(10, bold=True)
    _bar(
        surface,
        pygame.Rect(body.x + 40, body.y + 272, body.w - 80, 18),
        tail.suspicion,
        COLOR_RED,
        f"ПОДОЗРЕНИЕ {int(tail.suspicion * 100)}%",
        font,
    )
    _bar(
        surface,
        pygame.Rect(body.x + 40, body.y + 322, body.w - 80, 18),
        tail.lost,
        COLOR_ACCENT,
        f"РИСК ПОТЕРЯТЬ {int(tail.lost * 100)}%",
        font,
    )

    # сообщение
    message = tail.message
    colour = COLOR_GREEN if tail.success else (COLOR_RED if tail.failed else COLOR_TEXT_DIM)
    lines = draw_text_wrapped(
        surface,
        message,
        get_font(13, bold=True),
        colour,
        pygame.Rect(body.x + 40, body.y + 360, body.w - 80, 52),
    )
    _ = lines
    # «что известно» — описание дела и подсказка по управлению
    info = pygame.Rect(body.x + 40, body.y + 420, body.w - 80, max(60, body.bottom - 100 - (body.y + 420)))
    draw_panel(surface, info, color=PANEL_DARK, radius=8)
    surface.blit(
        get_font(10, bold=True).render("ЧТО ИЗВЕСТНО", True, COLOR_ACCENT),
        (info.x + 14, info.y + 10),
    )
    description = str(tail.spec.get("description", "") or "")
    if not description:
        description = (
            f"{tail.target} идёт к цели. Держите маркер дистанции в зелёной зоне: "
            "ближе — обернётся, дальше — потеряете на повороте."
        )
    draw_text_wrapped(
        surface,
        description,
        get_font(11),
        COLOR_TEXT_DIM,
        pygame.Rect(info.x + 14, info.y + 28, info.w - 28, info.h - 36),
    )
    controls = get_font(11).render(
        "● вы   ● объект   •   → / D — догонять     ← / A — отставать     "
        "ничего — идти ровно     ESC — прервать",
        True,
        COLOR_TEXT_DIM,
    )
    surface.blit(controls, (body.x + 40, body.bottom - 62))

    # кнопки
    mouse = game._to_logical(pygame.mouse.get_pos())
    pressed = pygame.mouse.get_pressed()[0]
    y = height - 58
    if tail.finished:
        back = Button((20, y, 150, 40), "← КАРТА")
        nxt = Button((width - 210, y, 190, 40), "ПРОДОЛЖИТЬ", accent=True)
        for btn in (back, nxt):
            btn.update(mouse, pressed)
            btn.draw(surface, get_font(12, bold=True))
        game.tail_rects = {"back": back.rect, "next": nxt.rect}
        if tail.success and getattr(game, "tail_reward", None):
            reward = game.tail_reward
            bits = []
            if reward.get("reveal"):
                bits.append("новая улика в блокноте")
            if reward.get("money"):
                bits.append(f"+${reward['money']}")
            if reward.get("reputation"):
                bits.append(f"+{reward['reputation']} репутации")
            if bits:
                surface.blit(
                    get_font(11, bold=True).render("  •  ".join(bits), True, COLOR_GREEN),
                    (body.x + 40, body.bottom - 34),
                )
    else:
        back = Button((20, y, 150, 40), "← ПРЕРВАТЬ")
        back.update(mouse, pressed)
        back.draw(surface, get_font(12, bold=True))
        game.tail_rects = {"back": back.rect}


def handle_click(game, pos) -> bool:
    rects = getattr(game, "tail_rects", {}) or {}
    if rects.get("back") and rects["back"].collidepoint(pos):
        abort(game)
        return True
    if rects.get("next") and rects["next"].collidepoint(pos):
        game.tail = None
        game.screen_name = "map"
        return True
    return False


def handle_key(game, event) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_ESCAPE:
        if getattr(game, "tail", None) and game.tail.finished:
            game.tail = None
            game.screen_name = "map"
        else:
            abort(game)
        return True
    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
        if getattr(game, "tail", None) and game.tail.finished:
            game.tail = None
            game.screen_name = "map"
            return True
    return False


__all__ = [
    "abort",
    "begin_tail",
    "choose_route",
    "draw",
    "draw_route",
    "handle_click",
    "handle_key",
    "handle_route_click",
    "handle_route_key",
    "start",
    "update",
]
