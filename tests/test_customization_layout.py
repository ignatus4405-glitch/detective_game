"""Тесты макета экрана кастомизации.

Регрессия: клики считались от физического размера окна, а отрисовка — от
логического холста 1280×720. На fullscreen/больших разрешениях портреты
«не нажимались», а кнопки уезжали за панель.
"""

import pytest

from detective_game.game_state import AVATARS, BACKGROUNDS
from detective_game.ui.layout import (
    customization_layout,
    ensure_unique_hits,
    layout_contains,
    rects_overlap,
)

RESOLUTIONS = [
    (1280, 720),  # базовое окно
    (1024, 600),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),  # ультраширокий
    (800, 600),  # минимальное
]


def make_layout(width, height):
    return customization_layout(
        width, height, avatars=len(AVATARS), backgrounds=len(BACKGROUNDS)
    )


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_all_blocks_inside_panel(width, height):
    layout = make_layout(width, height)
    panel = layout.panel
    assert layout_contains(panel, layout.header) is False
    for rect in (
        layout.name_input,
        layout.name_button,
        *layout.avatar_rects,
        layout.desc,
        *layout.bg_rects,
        layout.bg_hint,
        layout.btn_back,
        layout.btn_save,
    ):
        assert layout_contains(panel, rect), f"{rect} вне панели {panel} при {width}x{height}"

    # поле имени и кнопка кубика не пересекаются
    assert not rects_overlap(layout.name_input, layout.name_button)
    # ввод имени не вылезает на подсказку/разделитель
    assert layout.name_input.bottom < layout.divider_y
    # сетка портретов не наезжает на описание и на подсказку сверху
    for rect in layout.avatar_rects:
        assert rect.bottom <= layout.desc.y
        assert rect.y >= layout.avatars_hint[1]


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_no_vertical_overlaps(width, height):
    """Блоки идут сверху вниз без пересечений — ничего не «уезжает»."""
    layout = make_layout(width, height)
    ordered = [
        ("name", layout.name_input),
        ("desc", layout.desc),
        ("backgrounds", layout.bg_rects[0]),
        ("bg_hint", layout.bg_hint),
        ("buttons", layout.btn_back),
    ]
    for (name_a, a), (name_b, b) in zip(ordered, ordered[1:], strict=False):
        assert a.bottom <= b.y, f"{name_a} перекрывает {name_b} при {width}x{height}"

    # кнопки «Назад» и «Сохранить» не пересекаются и не вылезают из панели
    assert not rects_overlap(layout.btn_back, layout.btn_save)
    assert layout.btn_back.bottom <= layout.panel.bottom
    assert layout.btn_save.right <= layout.panel.right


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_avatar_grid_fits_and_is_clickable(width, height):
    layout = make_layout(width, height)
    assert len(layout.avatar_rects) == len(AVATARS)
    assert ensure_unique_hits(layout.avatar_rects)
    for i, rect in enumerate(layout.avatar_rects):
        assert layout.avatar_at(rect.center) == i
        # клик по краю портрета тоже попадает в него
        assert layout.avatar_at((rect.x + 2, rect.y + 2)) == i

    # за пределами сетки — промах, а не чужой портрет
    assert layout.avatar_at((layout.panel.x - 50, layout.panel.y - 50)) is None
    assert layout.avatar_at(layout.name_input.center) is None


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_background_buttons_clickable(width, height):
    layout = make_layout(width, height)
    assert len(layout.bg_rects) == len(BACKGROUNDS)
    assert ensure_unique_hits(layout.bg_rects)
    for i, rect in enumerate(layout.bg_rects):
        assert layout.background_at(rect.center) == i
    assert layout.background_at(layout.btn_save.center) is None


def test_avatars_scale_with_window():
    small = make_layout(1024, 600)
    large = make_layout(1920, 1080)
    assert small.avatar_size < large.avatar_size
    # портреты остаются квадратными
    for rect in small.avatar_rects + large.avatar_rects:
        assert rect.w == rect.h


def test_header_and_panel_centered_on_wide_screen():
    layout = make_layout(3440, 1440)
    assert layout.panel.centerx == pytest.approx(3440 // 2, abs=1)
    assert layout.header.centerx == pytest.approx(3440 // 2, abs=1)


# --- Выбор дела: все карточки видны и кликабельны ---

from detective_game.ui.layout import case_select_layout  # noqa: E402


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_case_cards_fit_screen(width, height):
    layout = case_select_layout(width, height, 3)
    assert len(layout.cards) == 3
    for card in layout.cards:
        assert layout_contains(pygame_rect_bounds(width, height), card.rect)
        # содержимое карточки внутри самой карточки
        assert layout_contains(card.rect, card.poster)
        assert layout_contains(card.rect, card.desc)
        assert layout_contains(card.rect, card.button)
        # интро рисуется, только если для него есть место — и тогда не лезет на кнопку
        if card.intro.h > 0:
            assert layout_contains(card.rect, card.intro)
            assert card.intro.bottom <= card.button.y
        # подпись не залезает на кнопку
        assert card.desc.bottom <= card.button.y


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_case_buttons_do_not_overlap(width, height):
    layout = case_select_layout(width, height, 3)
    assert ensure_unique_hits([card.button for card in layout.cards])
    assert ensure_unique_hits([card.rect for card in layout.cards])
    assert not rects_overlap(layout.btn_back, layout.cards[0].rect)


def test_case_cards_stack_on_narrow_screen():
    layout = case_select_layout(760, 720, 3)
    rows = {(card.rect.x, card.rect.y) for card in layout.cards}
    assert len(rows) == 3  # на узком экране карточки идут друг под другом


def pygame_rect_bounds(width, height):
    import pygame

    return pygame.Rect(0, 0, width, height)


# --- Настройки: кнопки внутри панелей на любом разрешении ---

from detective_game.ui.layout import settings_layout  # noqa: E402


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_settings_buttons_inside_panels(width, height):
    layout = settings_layout(width, height)
    assert layout_contains(layout.left, layout.apply)
    assert layout_contains(layout.left, layout.reset)
    assert layout_contains(layout.right, layout.wipe)
    assert layout_contains(layout.right, layout.check_updates)
    # кнопки не перекрывают друг друга и не вылезают за низ панели
    assert not rects_overlap(layout.apply, layout.reset)
    assert not rects_overlap(layout.check_updates, layout.wipe)
    assert layout.apply.bottom <= layout.left.bottom
    assert layout.wipe.bottom <= layout.right.bottom
    assert layout.check_updates.bottom <= layout.wipe.y
    # шапка с кнопкой «Назад» не пересекается с панелями
    assert layout.header.bottom <= layout.left.y
    assert not rects_overlap(layout.back, layout.left)
