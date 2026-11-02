"""Тесты «Школы детектива» и раскладки карты.

Проверяем то, что обычно ломается: геометрия на разных разрешениях, попадание
клика в каждый нарисованный элемент и отсутствие «мёртвых» кнопок.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game.ui.layout import (  # noqa: E402
    ensure_unique_hits,
    layout_contains,
    map_layout,
)
from detective_game.ui.tutorial import (  # noqa: E402
    CHAPTERS,
    DEMO_SCENES,
    DEMO_TOTAL,
    NOTEBOOK_TABS,
    SUSPECTS,
    TRAINING_CLUES,
    TRAINING_LOCATIONS,
    TutorialState,
    demo_scene_at,
    demo_scene_starts,
    tutorial_layout,
    tutorial_layout_problems,
)

RESOLUTIONS = [(1280, 720), (1366, 768), (1440, 900), (1600, 900), (1920, 1080), (2560, 1440)]


@pytest.fixture(scope="module", autouse=True)
def _video():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Раскладка
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width,height", RESOLUTIONS)
@pytest.mark.parametrize("chapter", [c.key for c in CHAPTERS])
def test_tutorial_layout_is_clean(width, height, chapter):
    layout = tutorial_layout(width, height, chapter)
    assert tutorial_layout_problems(layout) == []
    # всё внутри логического экрана
    for rect in layout.interactive_rects():
        assert layout_contains(pygame.Rect(0, 0, width, height), rect), (chapter, rect)


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_every_element_has_its_own_click_zone(width, height):
    layout = tutorial_layout(width, height, "clues")
    assert ensure_unique_hits(layout.clue_cards)
    # каждая карточка ловит клик по своему центру и не ловит по чужому
    for i, rect in enumerate(layout.clue_cards):
        assert layout.clue_at(rect.center) == i
    for i, rect in enumerate(layout.pins):
        assert layout.pin_at(rect.center) == i
    for i, rect in enumerate(layout.nav_items):
        assert layout.nav_at(rect.center) == i
    for i, rect in enumerate(layout.feature_cards):
        assert layout.feature_at(rect.center) == i
    for i, rect in enumerate(layout.tabs):
        assert layout.tab_at(rect.center) == i
    for i, rect in enumerate(layout.answers):
        assert layout.answer_at(rect.center) == i
    for i, rect in enumerate(layout.suspects):
        assert layout.suspect_at(rect.center) == i


def test_clue_cards_do_not_overlap_detail():
    layout = tutorial_layout(1280, 720, "clues")
    for card in layout.clue_cards:
        assert not card.colliderect(layout.clue_detail)


def test_nav_has_entry_for_every_chapter():
    layout = tutorial_layout(1280, 720, "intro")
    assert len(layout.nav_items) == len(CHAPTERS)


def test_timeline_maps_click_to_time():
    layout = tutorial_layout(1280, 720, "demo")
    left = layout.timeline_time((layout.timeline.x, layout.timeline.centery))
    right = layout.timeline_time((layout.timeline.right - 1, layout.timeline.centery))
    assert left == pytest.approx(0.0, abs=0.2)
    assert right == pytest.approx(DEMO_TOTAL, abs=0.2)
    assert layout.timeline_time((0, 0)) is None


# ---------------------------------------------------------------------------
# Карта: клики совпадают с пинами (регрессия)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width,height", RESOLUTIONS)
def test_map_pins_are_clickable_where_drawn(width, height):
    """Раньше отрисовка масштабировала пин в панель карты, а клик проверялся
    по сырым координатам дела — на 1280×720 промах достигал 100+ px."""
    case_locations = [
        {"id": "office", "x": 640, "y": 360},
        {"id": "mayor_house", "x": 400, "y": 200},
        {"id": "park", "x": 800, "y": 400},
    ]
    layout = map_layout(width, height, case_locations)
    for loc, rect in zip(case_locations, layout.pins, strict=False):
        assert layout.pin_at(rect.center) == loc["id"]
        assert layout.map_rect.collidepoint(rect.center)
        assert not layout.right.colliderect(rect)
    # старый (сломанный) способ не должен находить пин там же
    old_center = (case_locations[0]["x"], case_locations[0]["y"])
    assert layout.pin_at(old_center) != "mayor_house"


def test_map_buttons_inside_header():
    layout = map_layout(1280, 720, [{"id": "a", "x": 10, "y": 10}])
    for btn in (layout.btn_notebook, layout.btn_dossier, layout.btn_accuse):
        assert layout.header.contains(btn)
    assert ensure_unique_hits([layout.btn_notebook, layout.btn_dossier, layout.btn_accuse])
    assert layout.right.contains(layout.btn_menu)
    assert layout.right.contains(layout.btn_save)


def test_map_pins_clamped_inside_panel():
    layout = map_layout(1280, 720, [{"id": "edge", "x": 5000, "y": -300}])
    assert layout.map_rect.contains(layout.pins[0])


# ---------------------------------------------------------------------------
# Состояние и навигация
# ---------------------------------------------------------------------------


def test_state_navigation_and_visited():
    state = TutorialState()
    assert state.key == "intro"
    state.next()
    assert state.key == "map"
    assert 1 in state.visited
    state.prev()
    assert state.key == "intro"
    state.goto(999)
    assert state.chapter == len(CHAPTERS) - 1
    state.goto(-5)
    assert state.chapter == 0


def test_demo_timeline_advances_and_loops():
    state = TutorialState()
    state.goto(6)
    state.demo_time = 0.0
    state.update(1000)
    assert state.demo_time == pytest.approx(1.0, abs=0.01)
    state.update((DEMO_TOTAL + 5) * 1000)
    assert 0 <= state.demo_time < DEMO_TOTAL


def test_demo_scene_lookup():
    starts = demo_scene_starts()
    assert starts[0] == 0
    for index, start in enumerate(starts):
        scene_index, progress = demo_scene_at(start + 0.01)
        assert scene_index == index
        assert 0.0 <= progress <= 1.0
    assert len(DEMO_SCENES) == len(starts)


def test_jump_to_scene_moves_playhead():
    state = TutorialState()
    state.goto(6)
    state.jump_to_scene(3)
    assert state.scene()[0] == 3


# ---------------------------------------------------------------------------
# Все элементы кликабельны (через настоящий обработчик)
# ---------------------------------------------------------------------------


class _StubGame:
    LOGICAL_W = 1280
    LOGICAL_H = 720

    def __init__(self):
        self.screen_name = "tutorial"


def _click(state, pos):
    from detective_game.ui.tutorial_view import handle_tutorial_click

    game = _StubGame()
    handle_tutorial_click(game, state, pos)
    return game


def test_clicking_every_chapter_in_nav_opens_it():
    state = TutorialState()
    layout = tutorial_layout(1280, 720, state.key)
    for index, rect in enumerate(layout.nav_items):
        _click(state, rect.center)
        assert state.chapter == index
        layout = tutorial_layout(1280, 720, state.key)


def test_footer_buttons_navigate():
    state = TutorialState()
    layout = tutorial_layout(1280, 720, state.key)
    _click(state, layout.btn_next.center)
    assert state.chapter == 1
    layout = tutorial_layout(1280, 720, state.key)
    _click(state, layout.btn_prev.center)
    assert state.chapter == 0
    game = _click(state, layout.btn_back.center)
    assert game.screen_name == "menu"


def test_last_chapter_next_goes_back_to_game():
    state = TutorialState()
    state.goto(len(CHAPTERS) - 1)
    layout = tutorial_layout(1280, 720, state.key)
    game = _click(state, layout.btn_next.center)
    assert game.screen_name == "menu"


def test_intro_cards_open_matching_chapters():
    state = TutorialState()
    layout = tutorial_layout(1280, 720, state.key)
    expected = [1, 2, 3, 5]
    for index, rect in enumerate(layout.feature_cards):
        state.goto(0)
        _click(state, rect.center)
        assert state.key == CHAPTERS[expected[index]].key


def test_every_pin_and_clue_is_clickable():
    state = TutorialState()
    state.goto(1)
    layout = tutorial_layout(1280, 720, state.key)
    for index, rect in enumerate(layout.pins):
        _click(state, rect.center)
        assert state.pin == index
    state.goto(2)
    layout = tutorial_layout(1280, 720, state.key)
    for index, rect in enumerate(layout.clue_cards):
        _click(state, rect.center)
        assert state.clue == index


def test_notebook_tabs_and_dialogue_answers():
    state = TutorialState()
    state.goto(3)
    layout = tutorial_layout(1280, 720, state.key)
    for index, rect in enumerate(layout.tabs):
        _click(state, rect.center)
        assert state.tab == index
    state.goto(4)
    layout = tutorial_layout(1280, 720, state.key)
    for index, rect in enumerate(layout.answers):
        _click(state, rect.center)
        assert state.answer == index


def test_accusation_flow():
    state = TutorialState()
    state.goto(5)
    layout = tutorial_layout(1280, 720, state.key)
    # без выбора подозреваемого обвинение не срабатывает
    _click(state, layout.verdict_btn.center)
    assert state.verdict_shown is False
    _click(state, layout.suspects[0].center)
    assert state.suspect == 0
    _click(state, layout.verdict_btn.center)
    assert state.verdict_shown is True
    # «Попробовать снова» сбрасывает выбор
    _click(state, layout.verdict_btn.center)
    assert state.verdict_shown is False
    assert state.suspect is None


def test_demo_controls_are_clickable():
    state = TutorialState()
    state.goto(6)
    layout = tutorial_layout(1280, 720, state.key)
    _click(state, layout.btn_play.center)
    assert state.demo_playing is False
    _click(state, layout.btn_play.center)
    assert state.demo_playing is True
    _click(state, layout.scene_chips[2].center)
    assert state.scene()[0] == 2
    _click(state, layout.btn_restart.center)
    assert state.demo_time == 0.0
    _click(state, (layout.timeline.right - 1, layout.timeline.centery))
    assert state.demo_time > DEMO_TOTAL * 0.8
    playing = state.demo_playing
    _click(state, layout.player.center)
    assert state.demo_playing is not playing


def test_keyboard_shortcuts():
    from detective_game.ui.tutorial_view import handle_tutorial_key

    state = TutorialState()
    game = _StubGame()
    right = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    assert handle_tutorial_key(game, state, right) is True
    assert state.chapter == 1
    left = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
    handle_tutorial_key(game, state, left)
    assert state.chapter == 0
    esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    handle_tutorial_key(game, state, esc)
    assert game.screen_name == "menu"
    # пробел управляет только «видео»
    state.goto(6)
    state.demo_playing = True
    space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    handle_tutorial_key(game, state, space)
    assert state.demo_playing is False


# ---------------------------------------------------------------------------
# Содержание
# ---------------------------------------------------------------------------


def test_content_is_consistent():
    assert len(TRAINING_CLUES) == 3
    assert len(TRAINING_LOCATIONS) >= len(TRAINING_CLUES)
    assert len(NOTEBOOK_TABS) == 3
    assert len(SUSPECTS) == 3
    assert len(DEMO_SCENES) >= 3
    for clue in TRAINING_CLUES:
        assert clue.title and clue.place and clue.text


def test_tutorial_images_exist():
    from pathlib import Path

    from detective_game.config import IMAGES_DIR

    base = Path(IMAGES_DIR) / "tutorial"
    for name in ("city_map.jpg", "clue_paw.jpg", "clue_collar.jpg", "office_desk.jpg"):
        path = base / name
        assert path.exists(), f"нет картинки туториала: {path}"
        assert path.stat().st_size > 20_000, f"подозрительно маленькая картинка: {path}"


def test_screen_renders_without_errors():
    """Каждая глава реально рисуется — ловим исключения в отрисовке."""
    from detective_game.main import Game

    game = Game()
    game.screen_name = "tutorial"
    game.notifications.clear()
    for index, chapter in enumerate(CHAPTERS):
        game.tutorial = TutorialState()
        game.tutorial.goto(index)
        game.tutorial.demo_time = 4.0
        game.draw()
        assert game.screen.get_width() == game.LOGICAL_W


def test_all_chapters_have_unique_progress_badge():
    badges = [c.badge for c in CHAPTERS]
    titles = [c.title for c in CHAPTERS]
    assert len(set(badges)) == len(badges)
    assert len(set(titles)) == len(titles)


def test_real_game_map_click_opens_location():
    """Интеграция: клик по нарисованному пину в настоящей игре открывает локацию."""
    from detective_game.main import Game

    game = Game()
    game.notifications.clear()
    game.start_case("tutorial")
    game.screen_name = "map"
    layout = game._map_layout()
    assert layout.pins, "у дела должны быть локации"
    # берём доступную локацию
    avail = set(game.get_available_locations())
    target_index = next(
        i for i, loc in enumerate(game.current_case["locations"]) if loc["id"] in avail
    )
    target_id = game.current_case["locations"][target_index]["id"]
    pos = layout.pins[target_index].center
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    assert game.screen_name == "location"
    assert game.location_id == target_id
    assert target_id in game.state.visited_locations


def test_real_game_map_click_miss_does_nothing():
    from detective_game.main import Game

    game = Game()
    game.notifications.clear()
    game.start_case("tutorial")
    game.screen_name = "map"
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5)))
    assert game.screen_name == "map"


def test_f1_opens_tutorial_from_menu():
    from detective_game.main import Game

    game = Game()
    game.notifications.clear()
    game.screen_name = "menu"
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
    assert game.screen_name == "tutorial"
