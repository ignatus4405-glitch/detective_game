"""Отрисовка и ввод экрана «Школа детектива».

Экран целиком интерактивный: слева список глав, справа — живая мини-игра.
Каждый элемент (пин на карте, карточка улики, вкладка блокнота, ответ в
допросе, подозреваемый, плеер и таймлайн «видео») кликается и общий макет
`ui/tutorial.tutorial_layout` используется и для рисования, и для кликов.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import pygame

from ..config import (
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_BORDER,
    COLOR_GREEN,
    COLOR_PANEL,
    COLOR_PANEL_LIGHT,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_TEXT_DARK,
    COLOR_TEXT_DIM,
    IMAGES_DIR,
)
from .tutorial import (
    CHAPTERS,
    DEMO_SCENES,
    DEMO_TOTAL,
    DIALOGUE_LINES,
    NOTEBOOK_TABS,
    SUSPECTS,
    TRAINING_CLUES,
    TRAINING_LOCATIONS,
    VERDICT_TEXT,
    TutorialLayout,
    TutorialState,
    demo_scene_starts,
    tutorial_layout,
)
from .widgets import (
    draw_icon,
    draw_panel,
    draw_progress_bar,
    draw_text_wrapped,
    get_font,
    render_text,
)

_IMAGE_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Мелкие помощники
# ---------------------------------------------------------------------------


def _image(name: str, size: Tuple[int, int], dim: float = 0.0) -> Optional[pygame.Surface]:
    """Картинка из assets/images/tutorial с кропом «cover» и затемнением."""
    key = (name, size, round(dim, 2))
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    if not name:
        return None
    path = Path(IMAGES_DIR) / "tutorial" / name
    try:
        img = pygame.image.load(str(path)).convert()
    except Exception:
        return None
    img = _cover(img, size)
    if dim > 0:
        shade = pygame.Surface(size, pygame.SRCALPHA)
        shade.fill((6, 8, 14, int(255 * dim)))
        img.blit(shade, (0, 0))
    _IMAGE_CACHE[key] = img
    return img


def _cover(img: pygame.Surface, size: Tuple[int, int]) -> pygame.Surface:
    w, h = max(1, size[0]), max(1, size[1])
    iw, ih = img.get_size()
    scale = max(w / iw, h / ih)
    scaled = pygame.transform.smoothscale(img, (max(1, int(iw * scale)), max(1, int(ih * scale))))
    out = pygame.Surface((w, h))
    out.blit(scaled, ((w - scaled.get_width()) // 2, (h - scaled.get_height()) // 2))
    return out


def _blit_rounded(surface, img: Optional[pygame.Surface], rect: pygame.Rect, radius: int = 6) -> bool:
    """Кладёт картинку в прямоугольник с закруглёнными углами.

    Без маски фото ложится «квадратом» поверх панели с радиусом и торчит
    углами — заметно на маленьких превью вроде карты в блокноте.
    """
    if img is None:
        return False
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    layer.blit(img, (0, 0))
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(layer, rect.topleft)
    return True


def _panel(surface, rect, bg=COLOR_PANEL, border=COLOR_BORDER, radius=10, width=1):
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)


def _text(surface, font, text, color, pos, shadow=False):
    surf = render_text(font, text, color)
    if shadow:
        sh = render_text(font, text, (0, 0, 0))
        surface.blit(sh, (pos[0] + 1, pos[1] + 1))
    surface.blit(surf, pos)
    return surf.get_width()


def _centered(surface, font, text, color, rect):
    surf = render_text(font, text, color)
    surface.blit(surf, surf.get_rect(center=rect.center))
    return surf


def _lerp(a: Tuple[float, float], b: Tuple[float, float], t: float) -> Tuple[int, int]:
    t = max(0.0, min(1.0, t))
    return int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t)


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


_NOTEBOOK_TIPS = (
    "★ — важная улика: такие чаще открывают новые локации. Серые можно не читать сразу.",
    "Сверяйте алиби с уликами: кто-то путается в датах — значит, врёт.",
    "Серый пин на карте откроется, когда найдёте нужную улику в другом месте.",
)


def _document_icon(surface, rect) -> None:
    """Иконка «записка» примитивами — так надёжнее, чем глифы шрифта."""
    pygame.draw.rect(surface, (34, 34, 44), rect, border_radius=6)
    pygame.draw.rect(surface, COLOR_BORDER, rect, width=1, border_radius=6)
    sheet = pygame.Rect(0, 0, max(24, int(rect.w * 0.34)), max(30, int(rect.h * 0.42)))
    sheet.center = rect.center
    pygame.draw.rect(surface, (206, 198, 176), sheet, border_radius=3)
    pygame.draw.rect(surface, (120, 112, 96), sheet, width=1, border_radius=3)
    for i in range(3):
        y = sheet.y + 10 + i * 7
        pygame.draw.line(surface, (120, 112, 96), (sheet.x + 6, y), (sheet.right - 6, y), 1)
    pygame.draw.circle(surface, COLOR_ACCENT, (sheet.right - 6, sheet.bottom - 6), 5)


def _hover(rect) -> bool:
    return rect.collidepoint(pygame.mouse.get_pos())


def _mouse_logical(game) -> Tuple[int, int]:
    try:
        return game._to_logical(pygame.mouse.get_pos())
    except Exception:
        return pygame.mouse.get_pos()


# ---------------------------------------------------------------------------
# Каркас: шапка, навигация, футер
# ---------------------------------------------------------------------------


def draw_tutorial_screen(game, state: TutorialState) -> None:
    screen = game.screen
    layout = tutorial_layout(game.LOGICAL_W, game.LOGICAL_H, state.key)

    _draw_header(game, layout, state)
    _draw_nav(game, layout, state)
    _draw_footer(game, layout, state)

    renderer = {
        "intro": _draw_intro,
        "map": _draw_map,
        "clues": _draw_clues,
        "notebook": _draw_notebook,
        "dialogue": _draw_dialogue,
        "accuse": _draw_accuse,
        "demo": _draw_demo,
    }.get(state.key, _draw_intro)
    renderer(game, layout, state)


def _draw_header(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    draw_panel(screen, layout.header)
    _text(
        screen,
        get_font(22, bold=True),
        "ШКОЛА ДЕТЕКТИВА",
        COLOR_ACCENT,
        (layout.header.x + 20, layout.header.y + 8),
    )
    _text(
        screen,
        get_font(12),
        "Интерактивный туториал — всё кликается",
        COLOR_TEXT_DIM,
        (layout.header.x + 22, layout.header.y + 36),
    )
    counter = f"ГЛАВА {state.chapter + 1} / {len(CHAPTERS)}"
    surf = render_text(get_font(13, bold=True), counter, COLOR_TEXT)
    screen.blit(surf, (layout.header.right - surf.get_width() - 20, layout.header.y + 20))


def _draw_nav(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    draw_panel(screen, layout.nav)
    mouse = _mouse_logical(game)
    for index, chapter in enumerate(CHAPTERS):
        if index >= len(layout.nav_items):
            break
        rect = layout.nav_items[index]
        active = index == state.chapter
        done = index in state.visited and not active
        hover = rect.collidepoint(mouse)
        bg = (46, 40, 24) if active else ((36, 36, 46) if hover else (32, 32, 40))
        border = COLOR_ACCENT if active else (COLOR_BORDER if not hover else COLOR_ACCENT_DIM)
        _panel(screen, rect, bg, border, radius=8, width=2 if active else 1)
        badge_rect = pygame.Rect(rect.x + 10, rect.y + (rect.h - 26) // 2, 26, 26)
        pygame.draw.circle(screen, COLOR_ACCENT if active else (70, 70, 80), badge_rect.center, 13)
        badge_col = (16, 16, 20) if active else COLOR_TEXT_DIM
        _centered(screen, get_font(12, bold=True), chapter.badge, badge_col, badge_rect)
        title_col = COLOR_ACCENT if active else COLOR_TEXT
        _text(screen, get_font(14, bold=True), chapter.title, title_col, (rect.x + 44, rect.y + 8))
        sub_font = get_font(10)
        sub = chapter.subtitle
        while sub_font.size(sub)[0] > rect.w - 60 and len(sub) > 4:
            sub = sub[:-2]
        _text(screen, sub_font, sub, COLOR_TEXT_DIM, (rect.x + 44, rect.y + 26))
        if done:
            tick_rect = pygame.Rect(rect.right - 24, rect.y + (rect.h - 18) // 2, 18, 18)
            pygame.draw.circle(screen, (40, 80, 50), tick_rect.center, 9)
            _centered(screen, get_font(11, bold=True), "✓", COLOR_GREEN, tick_rect)


def _draw_footer(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    draw_panel(screen, layout.footer)
    mouse = _mouse_logical(game)

    back_hover = layout.btn_back.collidepoint(mouse)
    _panel(
        screen,
        layout.btn_back,
        (44, 38, 30) if back_hover else (34, 34, 42),
        COLOR_ACCENT if back_hover else COLOR_BORDER,
        radius=7,
    )
    _centered(screen, get_font(12, bold=True), "← В МЕНЮ", COLOR_TEXT, layout.btn_back)

    first = state.chapter == 0
    last = state.chapter == len(CHAPTERS) - 1
    # «Назад»
    _panel(
        screen,
        layout.btn_prev,
        (34, 34, 42) if not first else (26, 26, 32),
        COLOR_BORDER,
        radius=7,
    )
    _centered(
        screen,
        get_font(12, bold=True),
        "← НАЗАД",
        COLOR_TEXT if not first else COLOR_TEXT_DARK,
        layout.btn_prev,
    )
    # «Далее» — акцентная кнопка
    _panel(
        screen,
        layout.btn_next,
        COLOR_ACCENT if not last else (40, 60, 46),
        COLOR_ACCENT if not last else COLOR_GREEN,
        radius=7,
    )
    _centered(
        screen,
        get_font(12, bold=True),
        "ДАЛЕЕ →" if not last else "К ИГРЕ →",
        (16, 16, 20) if not last else COLOR_TEXT,
        layout.btn_next,
    )

    # прогресс
    progress = (state.chapter + 1) / len(CHAPTERS)
    draw_progress_bar(screen, layout.progress, progress)
    _text(
        screen,
        get_font(10),
        f"Пройдено {len(state.visited)} из {len(CHAPTERS)} глав",
        COLOR_TEXT_DIM,
        (layout.progress.x, layout.progress.y - 16),
    )


# ---------------------------------------------------------------------------
# Глава 1. Интро
# ---------------------------------------------------------------------------


_FEATURE_TARGETS = (1, 2, 3, 5)

_FEATURES = (
    ("КАРТА", "Ходите по локациям, тратя игровое время", "К"),
    ("УЛИКИ", "Находите, читайте — они копятся в журнале", "У"),
    ("БЛОКНОТ", "Улики, подозреваемые и схема города", "Б"),
    ("ОБВИНЕНИЕ", "выбираете, кто виновен — улик чем больше, тем лучше", "О"),
)


def _draw_intro(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    hero = layout.hero
    img = _image("office_desk.jpg", (hero.w, hero.h), dim=0.35)
    if img:
        screen.blit(img, hero.topleft)
    else:
        pygame.draw.rect(screen, (26, 30, 40), hero, border_radius=10)
    pygame.draw.rect(screen, COLOR_BORDER, hero, width=1, border_radius=10)
    # градиент снизу для читаемости
    grad = pygame.Surface((hero.w, hero.h), pygame.SRCALPHA)
    for y in range(hero.h):
        alpha = int(190 * (y / max(1, hero.h)) ** 1.4)
        pygame.draw.line(grad, (8, 10, 16, alpha), (0, y), (hero.w, y))
    screen.blit(grad, hero.topleft)
    _text(
        screen,
        get_font(26, bold=True),
        "Как играть: одно дело — три шага",
        COLOR_TEXT,
        (hero.x + 20, hero.y + hero.h - 78),
        shadow=True,
    )
    _text(
        screen,
        get_font(13),
        "Собирайте улики, читайте показания и обвиняйте того, на кого указывают факты.",
        COLOR_TEXT_DIM,
        (hero.x + 22, hero.y + hero.h - 44),
    )

    mouse = _mouse_logical(game)
    for i, (title, desc, icon) in enumerate(_FEATURES):
        if i >= len(layout.feature_cards):
            break
        rect = layout.feature_cards[i]
        hover = rect.collidepoint(mouse)
        _panel(
            screen,
            rect,
            (38, 36, 30) if hover else (30, 30, 38),
            COLOR_ACCENT if hover else COLOR_BORDER,
            radius=9,
        )
        icon_rect = pygame.Rect(rect.x + 14, rect.y + 14, 44, 44)
        pygame.draw.rect(screen, (44, 40, 28), icon_rect, border_radius=8)
        pygame.draw.rect(screen, COLOR_ACCENT_DIM, icon_rect, width=1, border_radius=8)
        _centered(screen, get_font(20, bold=True), icon, COLOR_ACCENT, icon_rect)
        _text(screen, get_font(14, bold=True), title, COLOR_ACCENT, (rect.x + 70, rect.y + 14))
        draw_text_wrapped(
            screen,
            desc,
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(rect.x + 70, rect.y + 34, rect.w - 86, rect.h - 50),
        )
        _text(
            screen,
            get_font(11, bold=True),
            "Открыть →",
            COLOR_ACCENT if hover else COLOR_TEXT_DARK,
            (rect.x + 14, rect.bottom - 26),
        )


# ---------------------------------------------------------------------------
# Глава 2. Карта
# ---------------------------------------------------------------------------


def _draw_map(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    rect = layout.map_rect
    img = _image("city_map.jpg", (rect.w, rect.h), dim=0.52)
    if img:
        screen.blit(img, rect.topleft)
    else:
        pygame.draw.rect(screen, (20, 22, 30), rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, rect, width=1, border_radius=8)
    # тёмная вуаль, чтобы пины читались на светной карте
    veil = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    veil.fill((10, 14, 26, 90))
    screen.blit(veil, rect.topleft)

    mouse = _mouse_logical(game)
    for index, (loc, pin) in enumerate(zip(TRAINING_LOCATIONS, layout.pins, strict=False)):
        selected = state.pin == index
        hover = pin.collidepoint(mouse)
        radius = 18 if selected else (16 if hover else 14)
        base = (212, 175, 55) if selected else ((90, 140, 200) if hover else (70, 80, 100))
        pygame.draw.circle(screen, (0, 0, 0), (pin.centerx + 3, pin.centery + 3), radius + 3)
        pygame.draw.circle(screen, base, pin.center, radius)
        pygame.draw.circle(
            screen, (255, 255, 255) if selected else (200, 205, 215), pin.center, radius, width=2
        )
        if selected:
            pygame.draw.circle(screen, COLOR_ACCENT, pin.center, radius + 7, width=2)
        label = get_font(10, bold=True)
        txt = render_text(label, loc.name, COLOR_TEXT)
        bg = pygame.Surface((txt.get_width() + 8, txt.get_height() + 4), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 190), bg.get_rect(), border_radius=4)
        screen.blit(bg, (pin.centerx - bg.get_width() // 2, pin.centery + radius + 4))
        screen.blit(txt, (pin.centerx - txt.get_width() // 2, pin.centery + radius + 6))

    # панель описания
    info = layout.map_info
    _panel(screen, info, (24, 26, 34), COLOR_BORDER, radius=9)
    _text(screen, get_font(12, bold=True), "ЛОКАЦИЯ", COLOR_ACCENT, (info.x + 14, info.y + 12))
    if state.pin is None:
        draw_text_wrapped(
            screen,
            "Кликните по любому пину на карте — справа появится описание и подсказка, "
            "что делать в этом месте.",
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(info.x + 14, info.y + 36, info.w - 28, info.h - 50),
        )
    else:
        loc = TRAINING_LOCATIONS[state.pin % len(TRAINING_LOCATIONS)]
        _text(screen, get_font(16, bold=True), loc.name, COLOR_TEXT, (info.x + 14, info.y + 34))
        _text(screen, get_font(11), f"Район: {loc.district}", COLOR_ACCENT_DIM, (info.x + 14, info.y + 58))
        draw_text_wrapped(
            screen,
            loc.note,
            get_font(11),
            COLOR_TEXT,
            pygame.Rect(info.x + 14, info.y + 80, info.w - 28, info.h - 150),
        )
        _text(screen, get_font(11, bold=True), "Совет", COLOR_ACCENT, (info.x + 14, info.bottom - 84))
        draw_text_wrapped(
            screen,
            "Клик по пину = переход. Недоступные локации открываются уликами.",
            get_font(10),
            COLOR_TEXT_DIM,
            pygame.Rect(info.x + 14, info.bottom - 66, info.w - 28, 56),
        )

    hint = layout.map_hint
    _text(
        screen,
        get_font(11),
        "Попробуйте: кликните по пину — это ровно то же, что делает игрок на экране карты.",
        COLOR_TEXT_DIM,
        (hint.x + 4, hint.y + 8),
    )


# ---------------------------------------------------------------------------
# Глава 3. Улики
# ---------------------------------------------------------------------------


def _draw_clues(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    mouse = _mouse_logical(game)
    for index, (clue, rect) in enumerate(zip(TRAINING_CLUES, layout.clue_cards, strict=False)):
        selected = state.clue == index
        hover = rect.collidepoint(mouse)
        _panel(
            screen,
            rect,
            (36, 34, 26) if selected else ((32, 32, 40) if hover else (26, 26, 34)),
            COLOR_ACCENT if selected or hover else COLOR_BORDER,
            radius=9,
            width=2 if selected else 1,
        )
        img_h = int(rect.h * 0.52)
        img_rect = pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 16, img_h)
        img = _image(clue.image, (img_rect.w, img_rect.h), dim=0.12) if clue.image else None
        if img:
            screen.blit(img, img_rect.topleft)
            pygame.draw.rect(screen, COLOR_BORDER, img_rect, width=1, border_radius=6)
        else:
            _document_icon(screen, img_rect)
        star_col = COLOR_ACCENT if clue.importance == "high" else COLOR_TEXT_DARK
        _text(screen, get_font(13), "★" if clue.importance == "high" else "☆", star_col, (rect.x + 12, img_rect.bottom + 8))
        _text(screen, get_font(13, bold=True), clue.title, COLOR_TEXT, (rect.x + 32, img_rect.bottom + 8))
        _text(screen, get_font(10), f"Где: {clue.place}", COLOR_TEXT_DIM, (rect.x + 12, img_rect.bottom + 30))
        if selected:
            _text(screen, get_font(10, bold=True), "открыто ниже ↓", COLOR_ACCENT, (rect.x + 12, rect.bottom - 20))

    detail = layout.clue_detail
    _panel(screen, detail, (24, 26, 34), COLOR_BORDER, radius=9)
    if state.clue is None:
        draw_text_wrapped(
            screen,
            "Кликните на карточку — внизу появится полное описание улики, её важность и куда она ведёт. "
            "В игре такие карточки лежат в блокноте на вкладке «Улики».",
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(detail.x + 16, detail.y + 16, detail.w - 32, detail.h - 32),
        )
        return
    clue = TRAINING_CLUES[state.clue % len(TRAINING_CLUES)]
    img_w = int(detail.w * 0.30)
    img_rect = pygame.Rect(detail.x + 12, detail.y + 12, img_w, detail.h - 24)
    img = _image(clue.image, (img_rect.w, img_rect.h), dim=0.05) if clue.image else None
    if img:
        screen.blit(img, img_rect.topleft)
        pygame.draw.rect(screen, COLOR_ACCENT_DIM, img_rect, width=1, border_radius=6)
    else:
        _document_icon(screen, img_rect)
    text_x = img_rect.right + 16
    _text(screen, get_font(16, bold=True), clue.title, COLOR_ACCENT, (text_x, detail.y + 14))
    _text(screen, get_font(11), f"Найдено: {clue.place}   ·   важность: {'высокая ★' if clue.importance == 'high' else 'обычная ☆'}", COLOR_TEXT_DIM, (text_x, detail.y + 40))
    draw_text_wrapped(
        screen,
        clue.text,
        get_font(11),
        COLOR_TEXT,
        pygame.Rect(text_x, detail.y + 62, detail.right - text_x - 16, detail.h - 110),
    )
    if clue.leads:
        _text(screen, get_font(11, bold=True), f"Ведёт в: {clue.leads}", COLOR_ACCENT, (text_x, detail.bottom - 30))


# ---------------------------------------------------------------------------
# Глава 4. Блокнот
# ---------------------------------------------------------------------------


def _draw_notebook(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    mouse = _mouse_logical(game)
    for index, (title, _desc) in enumerate(NOTEBOOK_TABS):
        rect = layout.tabs[index]
        active = state.tab == index
        hover = rect.collidepoint(mouse)
        _panel(
            screen,
            rect,
            (46, 40, 24) if active else ((36, 36, 46) if hover else (28, 28, 36)),
            COLOR_ACCENT if active else COLOR_BORDER,
            radius=7,
            width=2 if active else 1,
        )
        _centered(screen, get_font(12, bold=True), title, COLOR_ACCENT if active else COLOR_TEXT, rect)

    body = layout.notebook_body
    _panel(screen, body, (22, 24, 30), COLOR_BORDER, radius=9)
    _text(screen, get_font(11), NOTEBOOK_TABS[state.tab][1], COLOR_TEXT_DIM, (body.x + 14, body.y + 10))
    top = body.y + 34

    if state.tab == 0:
        row_h = min(58, max(34, (body.h - 50) // max(1, len(TRAINING_CLUES))))
        for i, clue in enumerate(TRAINING_CLUES):
            row = pygame.Rect(body.x + 14, top + i * row_h, body.w - 28, row_h - 6)
            _panel(screen, row, (30, 30, 40), COLOR_BORDER, radius=6)
            star = "★" if clue.importance == "high" else "☆"
            _text(screen, get_font(14), star, COLOR_ACCENT if clue.importance == "high" else COLOR_TEXT_DARK, (row.x + 10, row.y + 4))
            _text(screen, get_font(12, bold=True), clue.title, COLOR_TEXT, (row.x + 32, row.y + 4))
            _text(screen, get_font(10), f"{clue.place} · {clue.text[:52]}…", COLOR_TEXT_DIM, (row.x + 32, row.y + 20))
    elif state.tab == 1:
        row_h = min(62, max(38, (body.h - 50) // max(1, len(SUSPECTS))))
        for i, (name, note) in enumerate(SUSPECTS):
            row = pygame.Rect(body.x + 14, top + i * row_h, body.w - 28, row_h - 6)
            _panel(screen, row, (30, 30, 40), COLOR_BORDER, radius=6)
            avatar = pygame.Rect(row.x + 8, row.y + 4, row.h - 8, row.h - 8)
            pygame.draw.circle(screen, (60, 60, 76), avatar.center, avatar.w // 2)
            _centered(screen, get_font(13, bold=True), name[0], COLOR_TEXT, avatar)
            _text(screen, get_font(12, bold=True), name, COLOR_TEXT, (avatar.right + 10, row.y + 4))
            _text(screen, get_font(10), note[:70], COLOR_TEXT_DIM, (avatar.right + 10, row.y + 20))
    else:
        mini = pygame.Rect(body.x + 14, top, int(body.w * 0.55), body.bottom - top - 14)
        # Фон — та же карта города, что и в главе «Карта города»: пустой
        # прямоугольник читался как «карта не отобразилась».
        drawn = _blit_rounded(screen, _image("city_map.jpg", (mini.w, mini.h), dim=0.62), mini)
        if not drawn:
            pygame.draw.rect(screen, (18, 22, 30), mini, border_radius=6)
        else:
            # лёгкая вуаль: карта не должна спорить с пинами и подписями
            veil = pygame.Surface((mini.w, mini.h), pygame.SRCALPHA)
            veil.fill((10, 14, 26, 60))
            screen.blit(veil, mini.topleft)
        pygame.draw.rect(screen, COLOR_BORDER, mini, width=1, border_radius=6)
        previous_clip = screen.get_clip()
        screen.set_clip(mini.inflate(-4, -4))
        for i, loc in enumerate(TRAINING_LOCATIONS):
            cx = mini.x + int(loc.x * mini.w)
            cy = mini.y + int(loc.y * mini.h)
            pygame.draw.circle(screen, (0, 0, 0), (cx + 2, cy + 2), 9)
            pygame.draw.circle(screen, (212, 175, 55) if i == 0 else (86, 110, 146), (cx, cy), 7)
            pygame.draw.circle(screen, (225, 225, 235), (cx, cy), 7, width=1)
            label = render_text(get_font(9), loc.name, COLOR_TEXT)
            badge = pygame.Surface((label.get_width() + 6, label.get_height() + 2), pygame.SRCALPHA)
            pygame.draw.rect(badge, (0, 0, 0, 180), badge.get_rect(), border_radius=3)
            screen.blit(badge, (cx + 9, cy - 7))
            screen.blit(label, (cx + 12, cy - 6))
        screen.set_clip(previous_clip)
        _text(
            screen,
            get_font(11),
            "Заметки:",
            COLOR_ACCENT,
            (mini.right + 14, top),
        )
        draw_text_wrapped(
            screen,
            "• Офис — начать дело\n• Дом мэра — первая улика\n• Парк — ошейник\n• Бар — свидетели",
            get_font(11),
            COLOR_TEXT,
            pygame.Rect(mini.right + 14, top + 22, body.right - mini.right - 28, body.h - 60),
        )

    # Подсказка внизу — экран не выглядит пустым и объясняет смысл вкладки
    tip_h = max(34, int(body.h * 0.16))
    tip = pygame.Rect(body.x + 14, body.bottom - tip_h - 12, body.w - 28, tip_h)
    _panel(screen, tip, (34, 32, 24), COLOR_ACCENT_DIM, radius=7)
    _text(screen, get_font(10, bold=True), "СОВЕТ", COLOR_ACCENT, (tip.x + 12, tip.y + (tip.h - 14) // 2))
    draw_text_wrapped(
        screen,
        _NOTEBOOK_TIPS[state.tab],
        get_font(11),
        COLOR_TEXT,
        pygame.Rect(tip.x + 62, tip.y + 6, tip.w - 74, tip.h - 10),
    )


# ---------------------------------------------------------------------------
# Глава 5. Допрос
# ---------------------------------------------------------------------------


def _draw_dialogue(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    mouse = _mouse_logical(game)

    # «Портрет» персонажа — силуэт в нуар-стиле
    portrait = layout.portrait
    _panel(screen, portrait, (26, 26, 34), COLOR_BORDER, radius=9)
    face = pygame.Rect(portrait.centerx - 44, portrait.y + 18, 88, 88)
    pygame.draw.circle(screen, (58, 60, 76), face.center, 44)
    pygame.draw.circle(screen, (86, 88, 106), (face.centerx, face.centery - 10), 22)
    pygame.draw.ellipse(screen, (86, 88, 106), pygame.Rect(face.centerx - 28, face.centery + 12, 56, 34))
    _centered(screen, get_font(11, bold=True), "МЭР ДЖОНС", COLOR_TEXT, pygame.Rect(portrait.x, face.bottom + 8, portrait.w, 18))
    _centered(screen, get_font(10), "Клиент · Дом мэра", COLOR_TEXT_DIM, pygame.Rect(portrait.x, face.bottom + 26, portrait.w, 16))
    _centered(screen, get_font(10), "Настроение: встревожен", COLOR_ACCENT_DIM, pygame.Rect(portrait.x, portrait.bottom - 26, portrait.w, 16))

    question = layout.question
    _panel(screen, question, (24, 26, 34), COLOR_BORDER, radius=9)
    if state.answer is None:
        _text(screen, get_font(16, bold=True), "«Я ничего не знаю о коте!»", COLOR_TEXT, (question.x + 16, question.y + 16))
        draw_text_wrapped(
            screen,
            "Выберите реплику слева-снизу. В игре каждая реплика — кнопка: вопрос, "
            "давление или предъявление улики. Выбор влияет на доверие и на то, что вам расскажут.",
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(question.x + 16, question.y + 48, question.w - 32, question.h - 64),
        )
    else:
        q, a = DIALOGUE_LINES[state.answer % len(DIALOGUE_LINES)]
        _text(screen, get_font(12, bold=True), f"Вы: {q}", COLOR_ACCENT, (question.x + 16, question.y + 14))
        draw_text_wrapped(
            screen,
            f"Мэр Джонс: {a}",
            get_font(13),
            COLOR_TEXT,
            pygame.Rect(question.x + 16, question.y + 42, question.w - 32, question.h - 60),
        )

    for index, (line, _answer) in enumerate(DIALOGUE_LINES):
        rect = layout.answers[index]
        active = state.answer == index
        hover = rect.collidepoint(mouse)
        _panel(
            screen,
            rect,
            (44, 38, 24) if active else ((34, 34, 44) if hover else (28, 28, 36)),
            COLOR_ACCENT if active or hover else COLOR_BORDER,
            radius=7,
        )
        _text(screen, get_font(11, bold=True), f"{index + 1}.", COLOR_ACCENT_DIM, (rect.x + 12, rect.y + 12))
        _text(screen, get_font(12), line, COLOR_TEXT, (rect.x + 36, rect.y + 11))
        if active:
            _text(screen, get_font(10, bold=True), "выбрано", COLOR_GREEN, (rect.right - 74, rect.y + 13))


# ---------------------------------------------------------------------------
# Глава 6. Обвинение
# ---------------------------------------------------------------------------


def _draw_accuse(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    mouse = _mouse_logical(game)

    text_rect = layout.verdict_text
    if state.verdict_shown and state.suspect is not None:
        name = SUSPECTS[state.suspect % len(SUSPECTS)][0]
        ok = state.suspect == 0
        _panel(screen, text_rect, (24, 44, 30) if ok else (48, 24, 26), COLOR_GREEN if ok else COLOR_RED, radius=9)
        _text(
            screen,
            get_font(15, bold=True),
            f"Обвинение предъявлено: {name}",
            COLOR_GREEN if ok else COLOR_RED,
            (text_rect.x + 16, text_rect.y + 12),
        )
        draw_text_wrapped(
            screen,
            VERDICT_TEXT if ok else "Это не тот, кто украл кота. Улик было мало — допросите свидетелей ещё раз.",
            get_font(11),
            COLOR_TEXT,
            pygame.Rect(text_rect.x + 16, text_rect.y + 36, text_rect.w - 32, text_rect.h - 44),
        )
    else:
        _panel(screen, text_rect, (24, 26, 34), COLOR_BORDER, radius=9)
        _text(screen, get_font(14, bold=True), "Пора назвать имя", COLOR_ACCENT, (text_rect.x + 16, text_rect.y + 10))
        draw_text_wrapped(
            screen,
            "Обвинение открывается, когда собрано 3 улики. Выберите подозреваемого — "
            "игра проверит, совпадает ли он с настоящим виновником.",
            get_font(11),
            COLOR_TEXT_DIM,
            pygame.Rect(text_rect.x + 16, text_rect.y + 32, text_rect.w - 32, text_rect.h - 40),
        )

    for index, (name, note) in enumerate(SUSPECTS):
        rect = layout.suspects[index]
        active = state.suspect == index
        hover = rect.collidepoint(mouse)
        _panel(
            screen,
            rect,
            (44, 38, 24) if active else ((34, 34, 44) if hover else (28, 28, 36)),
            COLOR_ACCENT if active or hover else COLOR_BORDER,
            radius=9,
            width=2 if active else 1,
        )
        avatar = pygame.Rect(rect.centerx - 28, rect.y + 12, 56, 56)
        pygame.draw.circle(screen, (58, 60, 76), avatar.center, 28)
        _centered(screen, get_font(20, bold=True), name[0], COLOR_TEXT, avatar)
        _centered(screen, get_font(13, bold=True), name, COLOR_TEXT, pygame.Rect(rect.x, avatar.bottom + 6, rect.w, 20))
        draw_text_wrapped(
            screen,
            note,
            get_font(10),
            COLOR_TEXT_DIM,
            pygame.Rect(rect.x + 12, avatar.bottom + 28, rect.w - 24, rect.bottom - avatar.bottom - 36),
        )
        if active:
            pygame.draw.circle(screen, COLOR_ACCENT, (rect.right - 18, rect.y + 18), 8)
            _centered(screen, get_font(11, bold=True), "✓", (16, 16, 20), pygame.Rect(rect.right - 26, rect.y + 10, 16, 16))

    btn = layout.verdict_btn
    enabled = state.suspect is not None
    hover = btn.collidepoint(mouse) and enabled
    _panel(
        screen,
        btn,
        (COLOR_ACCENT if enabled else (40, 40, 48)),
        COLOR_ACCENT if enabled else COLOR_BORDER,
        radius=8,
    )
    _centered(
        screen,
        get_font(13, bold=True),
        "ПРЕДЪЯВИТЬ ОБВИНЕНИЕ" if not state.verdict_shown else "ПОПРОБОВАТЬ СНОВА",
        (16, 16, 20) if enabled else COLOR_TEXT_DARK,
        btn,
    )
    if hover:
        pygame.draw.rect(screen, COLOR_ACCENT, btn.inflate(4, 4), width=2, border_radius=10)


# ---------------------------------------------------------------------------
# Глава 7. «Видео-обзор»
# ---------------------------------------------------------------------------


def _draw_demo(game, layout: TutorialLayout, state: TutorialState) -> None:
    screen = game.screen
    player = layout.player
    pygame.draw.rect(screen, (14, 16, 22), player, border_radius=10)
    pygame.draw.rect(screen, COLOR_BORDER, player, width=1, border_radius=10)
    # мягкая сетка «плёночного» кадра
    for gx in range(player.x, player.right, 48):
        pygame.draw.line(screen, (22, 24, 32), (gx, player.y), (gx, player.bottom), 1)
    for gy in range(player.y, player.bottom, 48):
        pygame.draw.line(screen, (22, 24, 32), (player.x, gy), (player.right, gy), 1)

    scene_index, scene_progress = state.scene()
    scene = DEMO_SCENES[scene_index]
    cursor: Optional[Tuple[int, int]] = None
    ripple = 0.0

    if scene_index == 0:
        _demo_map(screen, player, pulse=True, highlight=0)
    elif scene_index == 1:
        target = (player.x + int(player.w * 0.30), player.y + int(player.h * 0.42))
        start = (player.centerx, player.centery + 40)
        cursor = _lerp(start, target, _ease(min(1.0, scene_progress / 0.55)))
        _demo_map(screen, player, pulse=False, highlight=1 if scene_progress > 0.55 else None)
        if scene_progress > 0.55:
            ripple = min(1.0, (scene_progress - 0.55) / 0.35)
    elif scene_index == 2:
        _demo_location(screen, player, scene_progress)
    elif scene_index == 3:
        _demo_notebook(screen, player, scene_progress)
    else:
        _demo_accuse(screen, player, scene_progress)

    # рамка «видео»
    for corner in (
        pygame.Rect(player.x + 8, player.y + 8, 22, 3),
        pygame.Rect(player.x + 8, player.y + 8, 3, 22),
        pygame.Rect(player.right - 30, player.y + 8, 22, 3),
        pygame.Rect(player.right - 11, player.y + 8, 3, 22),
        pygame.Rect(player.x + 8, player.bottom - 11, 22, 3),
        pygame.Rect(player.x + 8, player.bottom - 30, 3, 22),
        pygame.Rect(player.right - 30, player.bottom - 11, 22, 3),
        pygame.Rect(player.right - 11, player.bottom - 30, 3, 22),
    ):
        pygame.draw.rect(screen, COLOR_ACCENT_DIM, corner)

    # бейдж REC / PAUSE
    badge = pygame.Rect(player.x + 16, player.y + 14, 76, 22)
    _panel(screen, badge, (40, 18, 20) if state.demo_playing else (30, 30, 36), COLOR_RED if state.demo_playing else COLOR_BORDER, radius=5)
    _text(
        screen,
        get_font(10, bold=True),
        "● ЗАПИСЬ" if state.demo_playing else "❚❚ ПАУЗА",
        (255, 190, 190) if state.demo_playing else COLOR_TEXT_DIM,
        (badge.x + 8, badge.y + 5),
    )

    # субтитры
    sub = layout.subtitle
    shade = pygame.Surface((sub.w, sub.h), pygame.SRCALPHA)
    shade.fill((4, 6, 10, 190))
    screen.blit(shade, sub.topleft)
    _text(screen, get_font(14, bold=True), scene.title, COLOR_ACCENT, (sub.x + 12, sub.y + 8))
    draw_text_wrapped(
        screen,
        scene.subtitle,
        get_font(11),
        COLOR_TEXT,
        pygame.Rect(sub.x + 12, sub.y + 28, sub.w - 24, sub.h - 32),
    )

    # курсор и «клик»
    if cursor:
        pygame.draw.polygon(
            screen,
            (255, 255, 255),
            [(cursor[0], cursor[1]), (cursor[0] + 14, cursor[1] + 20), (cursor[0] + 6, cursor[1] + 19)],
        )
        pygame.draw.polygon(
            screen,
            (20, 20, 24),
            [(cursor[0], cursor[1]), (cursor[0] + 14, cursor[1] + 20), (cursor[0] + 6, cursor[1] + 19)],
            width=1,
        )
    if ripple > 0:
        radius = int(6 + ripple * 26)
        pygame.draw.circle(screen, COLOR_ACCENT, cursor or player.center, radius, width=2)

    # прогресс просмотра внутри сцены
    bar = pygame.Rect(player.x + 16, player.bottom - 14, player.w - 32, 4)
    pygame.draw.rect(screen, (40, 40, 48), bar, border_radius=2)
    pygame.draw.rect(
        screen,
        COLOR_ACCENT,
        (bar.x, bar.y, int(bar.w * min(1.0, scene_progress)), bar.h),
        border_radius=2,
    )

    # управление
    _panel(screen, layout.btn_play, (40, 40, 50), COLOR_ACCENT_DIM, radius=7)
    _centered(
        screen,
        get_font(12, bold=True),
        "❚❚ ПАУЗА" if state.demo_playing else "▶ СМОТРЕТЬ",
        COLOR_TEXT,
        layout.btn_play,
    )
    _panel(screen, layout.btn_restart, (32, 32, 40), COLOR_BORDER, radius=7)
    _centered(screen, get_font(12, bold=True), "⟲ СНАЧАЛА", COLOR_TEXT, layout.btn_restart)

    draw_progress_bar(screen, layout.timeline, state.demo_time / DEMO_TOTAL)
    starts = demo_scene_starts()
    for start, scene_item in zip(starts, DEMO_SCENES, strict=False):
        x = layout.timeline.x + int(layout.timeline.w * (start / DEMO_TOTAL))
        pygame.draw.line(screen, COLOR_TEXT_DARK, (x, layout.timeline.y - 3), (x, layout.timeline.bottom + 3), 1)
    total_txt = f"{int(state.demo_time):02d} / {int(DEMO_TOTAL):02d} c"
    _text(screen, get_font(10), total_txt, COLOR_TEXT_DIM, (layout.timeline.right - 78, layout.timeline.y - 20))

    for index, chip in enumerate(layout.scene_chips):
        active = index == scene_index
        _panel(
            screen,
            chip,
            (44, 38, 24) if active else (30, 30, 38),
            COLOR_ACCENT if active else COLOR_BORDER,
            radius=6,
        )
        scene_item = DEMO_SCENES[index]
        label = f"{index + 1}. {scene_item.short or scene_item.title}"
        font = get_font(10, bold=active)
        while font.size(label)[0] > chip.w - 12 and len(label) > 6:
            label = label[:-2]
        _centered(screen, font, label, COLOR_ACCENT if active else COLOR_TEXT_DIM, chip)


def _demo_map(surface, player, *, pulse: bool, highlight: Optional[int]) -> None:
    """Мини-карта для «видео»: пины, подсветка, пульсация."""
    area = pygame.Rect(player.x + 40, player.y + 44, player.w - 80, player.h - 96)
    img = _image("city_map.jpg", (area.w, area.h), dim=0.55)
    if img:
        surface.blit(img, area.topleft)
    pygame.draw.rect(surface, COLOR_BORDER, area, width=1, border_radius=6)
    for index, loc in enumerate(TRAINING_LOCATIONS):
        cx = area.x + int(loc.x * area.w)
        cy = area.y + int(loc.y * area.h)
        selected = highlight == index
        pygame.draw.circle(surface, (0, 0, 0), (cx + 2, cy + 2), 12)
        pygame.draw.circle(surface, COLOR_ACCENT if selected or index == 0 else (80, 96, 124), (cx, cy), 11)
        pygame.draw.circle(surface, (230, 230, 240), (cx, cy), 11, width=1)
        if pulse and index == 0:
            radius = 18 + int(6 * abs(pygame.time.get_ticks() % 1200 - 600) / 600)
            pygame.draw.circle(surface, COLOR_ACCENT, (cx, cy), radius, width=2)
        label_font = get_font(9)
        surface.blit(render_text(label_font, loc.name, COLOR_TEXT), (cx + 14, cy - 6))


def _demo_location(surface, player, progress: float) -> None:
    """Сцена «нашли улику»: карточка локации с фото улики."""
    area = pygame.Rect(player.x + 40, player.y + 44, player.w - 80, player.h - 96)
    _panel(surface, area, (24, 26, 34), COLOR_BORDER, radius=8)
    clue = TRAINING_CLUES[1]
    img_rect = pygame.Rect(area.x + 12, area.y + 12, int(area.w * 0.44), area.h - 24)
    img = _image(clue.image, (img_rect.w, img_rect.h), dim=0.05)
    if img:
        slide = int((1 - _ease(progress / 0.4)) * 60)
        surface.blit(img, (img_rect.x - slide, img_rect.y))
    _text(surface, get_font(16, bold=True), clue.title, COLOR_ACCENT, (img_rect.right + 16, area.y + 16))
    _text(surface, get_font(10), f"Найдено: {clue.place}", COLOR_TEXT_DIM, (img_rect.right + 16, area.y + 42))
    draw_text_wrapped(
        surface,
        clue.text,
        get_font(11),
        COLOR_TEXT,
        pygame.Rect(img_rect.right + 16, area.y + 62, area.right - img_rect.right - 32, area.h - 120),
    )
    btn = pygame.Rect(img_rect.right + 16, area.bottom - 44, 190, 30)
    pressed = progress > 0.6
    _panel(surface, btn, COLOR_ACCENT if pressed else (40, 40, 50), COLOR_ACCENT if pressed else COLOR_BORDER, radius=6)
    _centered(surface, get_font(11, bold=True), "ЗАБРАТЬ УЛИКУ", (16, 16, 20) if pressed else COLOR_TEXT, btn)
    if pressed:
        journal = pygame.Rect(area.right - 132, area.y + 14, 120, 58)
        _panel(surface, journal, (30, 38, 30), COLOR_GREEN, radius=6)
        _text(surface, get_font(9, bold=True), "В ЖУРНАЛЕ", COLOR_GREEN, (journal.x + 8, journal.y + 6))
        _text(surface, get_font(9), clue.title[:16], COLOR_TEXT, (journal.x + 8, journal.y + 22))


def _demo_notebook(surface, player, progress: float) -> None:
    area = pygame.Rect(player.x + 40, player.y + 44, player.w - 80, player.h - 96)
    _panel(surface, area, (22, 24, 30), COLOR_BORDER, radius=8)
    tabs = ["Улики", "Подозреваемые", "Карта"]
    tab_w = (area.w - 24 - 16) // 3
    for i, title in enumerate(tabs):
        rect = pygame.Rect(area.x + 12 + i * (tab_w + 8), area.y + 12, tab_w, 34)
        active = (i == 1 and progress > 0.45) or (i == 0 and progress <= 0.45)
        _panel(surface, rect, (46, 40, 24) if active else (30, 30, 38), COLOR_ACCENT if active else COLOR_BORDER, radius=6)
        _centered(surface, get_font(11, bold=True), title, COLOR_ACCENT if active else COLOR_TEXT_DIM, rect)
    body = pygame.Rect(area.x + 12, area.y + 56, area.w - 24, area.h - 70)
    _panel(surface, body, (26, 28, 36), COLOR_BORDER, radius=6)
    if progress <= 0.45:
        for i, clue in enumerate(TRAINING_CLUES):
            row = pygame.Rect(body.x + 8, body.y + 8 + i * 32, body.w - 16, 28)
            _panel(surface, row, (32, 32, 42), COLOR_BORDER, radius=5)
            _text(surface, get_font(10), "★" if clue.importance == "high" else "☆", COLOR_ACCENT, (row.x + 8, row.y + 6))
            _text(surface, get_font(11), clue.title, COLOR_TEXT, (row.x + 26, row.y + 6))
    else:
        for i, (name, note) in enumerate(SUSPECTS):
            row = pygame.Rect(body.x + 8, body.y + 8 + i * 34, body.w - 16, 30)
            _panel(surface, row, (32, 32, 42), COLOR_BORDER, radius=5)
            _text(surface, get_font(11, bold=True), name, COLOR_TEXT, (row.x + 10, row.y + 6))
            _text(surface, get_font(9), note[:54], COLOR_TEXT_DIM, (row.x + 120, row.y + 8))


def _demo_accuse(surface, player, progress: float) -> None:
    area = pygame.Rect(player.x + 40, player.y + 44, player.w - 80, player.h - 96)
    _panel(surface, area, (24, 26, 34), COLOR_BORDER, radius=8)
    _text(surface, get_font(13, bold=True), "Собрано 3 улики — можно обвинять", COLOR_ACCENT, (area.x + 14, area.y + 12))
    card_w = (area.w - 28 - 16) // 3
    for i, (name, _note) in enumerate(SUSPECTS):
        rect = pygame.Rect(area.x + 14 + i * (card_w + 8), area.y + 40, card_w, 90)
        chosen = i == 0 and progress > 0.45
        _panel(surface, rect, (44, 38, 24) if chosen else (30, 30, 38), COLOR_ACCENT if chosen else COLOR_BORDER, radius=6)
        _text(surface, get_font(11, bold=True), name, COLOR_TEXT if not chosen else COLOR_ACCENT, (rect.x + 8, rect.y + 8))
        pygame.draw.circle(surface, (58, 60, 76), (rect.centerx, rect.y + 54), 20)
    btn = pygame.Rect(area.centerx - 110, area.bottom - 52, 220, 34)
    _panel(surface, btn, COLOR_ACCENT if progress > 0.6 else (40, 40, 48), COLOR_ACCENT, radius=7)
    _centered(surface, get_font(11, bold=True), "ПРЕДЪЯВИТЬ ОБВИНЕНИЕ", (16, 16, 20), btn)


# ---------------------------------------------------------------------------
# Ввод
# ---------------------------------------------------------------------------


def handle_tutorial_click(game, state: TutorialState, pos) -> bool:
    """Обрабатывает клик. Возвращает True, если клик «съеден» экраном."""
    layout = tutorial_layout(game.LOGICAL_W, game.LOGICAL_H, state.key)
    if layout.btn_back.collidepoint(pos):
        game.screen_name = "menu"
        return True
    if layout.btn_prev.collidepoint(pos):
        state.prev()
        return True
    if layout.btn_next.collidepoint(pos):
        next_index = state.chapter + 1
        if next_index >= len(CHAPTERS):
            # прошли всё — назад в игру
            game.screen_name = "menu"
        else:
            state.goto(next_index)
        return True

    nav_index = layout.nav_at(pos)
    if nav_index is not None:
        state.goto(nav_index)
        return True

    if state.key == "intro":
        feature = layout.feature_at(pos)
        if feature is not None:
            # КАРТА→map, УЛИКИ→clues, БЛОКНОТ→notebook, ОБВИНЕНИЕ→accuse
            state.goto(_FEATURE_TARGETS[feature] if feature < len(_FEATURE_TARGETS) else 1)
            return True

    elif state.key == "map":
        pin = layout.pin_at(pos)
        if pin is not None:
            state.pin = pin
            return True

    elif state.key == "clues":
        card = layout.clue_at(pos)
        if card is not None:
            state.clue = card
            return True

    elif state.key == "notebook":
        tab = layout.tab_at(pos)
        if tab is not None:
            state.tab = tab
            return True

    elif state.key == "dialogue":
        answer = layout.answer_at(pos)
        if answer is not None:
            state.answer = answer
            return True

    elif state.key == "accuse":
        suspect = layout.suspect_at(pos)
        if suspect is not None:
            state.suspect = suspect
            state.verdict_shown = False
            return True
        if layout.verdict_btn.collidepoint(pos):
            if state.verdict_shown:
                state.verdict_shown = False
                state.suspect = None
            elif state.suspect is not None:
                state.verdict_shown = True
            return True

    elif state.key == "demo":
        chip = layout.chip_at(pos)
        if chip is not None:
            state.jump_to_scene(chip)
            return True
        if layout.btn_play.collidepoint(pos):
            state.demo_playing = not state.demo_playing
            return True
        if layout.btn_restart.collidepoint(pos):
            state.seek(0.0)
            state.demo_playing = True
            return True
        seek = layout.timeline_time(pos)
        if seek is not None:
            state.seek(seek)
            state.demo_playing = True
            return True
        if layout.player.collidepoint(pos):
            state.demo_playing = not state.demo_playing
            return True

    return True


def handle_tutorial_key(game, state: TutorialState, event) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
        game.screen_name = "menu"
        return True
    if event.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN):
        state.next()
        return True
    if event.key in (pygame.K_LEFT, pygame.K_PAGEUP):
        state.prev()
        return True
    if event.key == pygame.K_SPACE and state.key == "demo":
        state.demo_playing = not state.demo_playing
        return True
    return False
