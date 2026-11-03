"""Регрессии 0.1.42: застывший патруль и неполный сброс прогресса.

Три бага, которые нашлись в игре:

* в локациях без скрытых улик сессия обыска считалась завершённой сразу —
  патруль стоял на месте, таймер не шёл, точки не нажимались;
* «НОВАЯ ИГРА» ничего не стирала, а тайком продолжала старое прохождение;
* «СБРОСИТЬ ПРОГРЕСС» стирала данные без вопроса, а серая «СБРОСИТЬ» рядом
  с «ПРИМЕНИТЬ» выглядела как сброс прогресса, хотя отменяла только настройки.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import search  # noqa: E402
from detective_game.data import BUILTIN_CASES, load_case  # noqa: E402
from detective_game.game_state import START_MONEY, GameState  # noqa: E402
from detective_game.save_system import has_save, load_game, save_game  # noqa: E402
from detective_game.ui import search_view  # noqa: E402
from detective_game.ui.layout import settings_layout  # noqa: E402


@pytest.fixture
def game():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    obj = Game()
    obj.notifications.clear()
    yield obj
    pygame.quit()


def _open_location(game, case_id="bank_heist", location_id="bank", minute=60):
    case = load_case(case_id)
    game.current_case = case
    game.state = GameState()
    game.state.current_case_id = case_id
    game.state.case_state = "in_progress"
    game.state.case_time_minutes = minute
    game.screen_name = "location"
    game.location_id = location_id
    game.notifications.clear()
    return case


def _press_release(game, pos):
    """Нажать и отпустить кнопку мыши в точке — как настоящий игрок."""
    if hasattr(pos, "center"):  # передали прямоугольник кнопки
        pos = pos.center
    pygame.mouse.get_pos = lambda: pos
    pygame.mouse.get_pressed = lambda *a: (True, False, False)
    game.draw()
    pygame.mouse.get_pressed = lambda *a: (False, False, False)
    game.draw()


# ── патруль и обыск ─────────────────────────────────────────────────


def _clueless_locations(case):
    """Локации, где нет ни одной скрытой улики (раньше там всё замирало)."""
    state = GameState()
    result = []
    for loc in case["locations"]:
        session = search.Search(case, loc["id"], state)
        if not session.had_clues:
            result.append(loc["id"])
    return result


def test_bank_heist_has_clueless_locations_to_cover():
    """Если таких локаций не останется, тест ниже перестанет что-то проверять."""
    case = load_case("bank_heist")
    assert len(_clueless_locations(case)) >= 5


def test_patrol_moves_in_location_without_hidden_clues():
    case = load_case("bank_heist")
    state = GameState()
    for location_id in _clueless_locations(case):
        session = search.Search(case, location_id, state)
        assert session.patrol_on, location_id
        assert not session.finished, location_id
        start_cell = session.patrol_cell()
        for _ in range(320):  # ~5 секунд при 16 мс на кадр
            session.update(0.016)
        assert session.remaining < session.seconds, location_id
        assert session.patrol_moves >= 1, location_id
        assert session.patrol_cell() != start_cell, location_id


def test_flavour_spot_is_clickable_and_search_stays_open(game):
    _open_location(game)
    search_view.start(game)
    session = game.search
    assert not session.finished
    game.draw_location()
    visual = game.search_visual
    spot = session.spots[0]
    pos = (
        int(visual.x + spot["x"] * visual.w),
        int(visual.y + spot["y"] * visual.h),
    )
    assert search_view.handle_click(game, pos) is True
    assert session.found_count == 1
    assert game.search is not None
    assert game.search_message


def test_inspection_without_clues_costs_no_time(game):
    _open_location(game)
    before = game.state.case_time_minutes
    search_view.start(game)
    assert game.search.had_clues is False
    search_view.stop(game)
    assert game.state.case_time_minutes == before
    assert game.search is None
    assert "искать было нечего" in game.notifications[-1][0]


def test_search_with_clues_still_costs_time(game):
    _open_location(game, location_id="harbor")
    before = game.state.case_time_minutes
    search_view.start(game)
    assert game.search.had_clues is True
    search_view.stop(game)
    assert game.state.case_time_minutes == before + 10


def test_search_closes_itself_when_all_clues_found(game):
    _open_location(game, location_id="harbor")
    search_view.start(game)
    session = game.search
    game.draw_location()
    visual = game.search_visual
    clue_spot = next(s for s in session.spots if s["kind"] == "clue")
    pos = (
        int(visual.x + clue_spot["x"] * visual.w),
        int(visual.y + clue_spot["y"] * visual.h),
    )
    search_view.handle_click(game, pos)
    assert game.search is None


def test_start_button_reads_look_around_when_nothing_to_search(game):
    _open_location(game)
    assert search_view.has_hidden_clues(game) is False
    _open_location(game, location_id="harbor")
    assert search_view.has_hidden_clues(game) is True


def test_clue_count_survives_taking_spots():
    case = load_case("bank_heist")
    session = search.Search(case, "harbor", GameState())
    assert session.clue_count == 1
    for spot in list(session.spots):
        session.take(spot)
    assert session.had_clues is True
    assert session.finished


# ── «СЫГРАТЬ ЕЩЁ» ───────────────────────────────────────────────────


def _case_with_resources(game):
    game.start_case("bank_heist")
    game.cutscene = None
    game.state.collected_clues = {"clue_log", "clue_tv"}
    game.state.case_time_minutes = 900
    game.state.money = 450
    game.state.reputation = 30
    return game.current_case


def test_replay_resets_reputation_and_money(game):
    _case_with_resources(game)
    game._ending_action("replay")
    assert game.state.money == START_MONEY
    assert game.state.reputation == 0
    assert game.state.collected_clues == set()
    assert game.state.case_time_minutes == 0
    assert game.screen_name == "map"


def test_next_case_keeps_career_resources(game):
    """Переход к следующему делу — это карьера: ресурсы переносятся."""
    _case_with_resources(game)
    game.start_case("missing_chess")
    game.cutscene = None
    assert game.state.money == 450
    assert game.state.reputation == 30


# ── «НОВАЯ ИГРА» и «СБРОСИТЬ ПРОГРЕСС» ──────────────────────────────


def _dirty_state(game):
    _case_with_resources(game)
    game.state.completed_cases = {"tutorial_case"}
    game.state.unlocked_endings = {"tutorial_case": ["tutorial_case:finch:perfect"]}
    game.state.board_links = {"clue_log|kane_sus"}
    game.state.asked_topics = {"kane:0"}
    save_game(game.state)


def test_new_game_asks_before_wiping(game):
    _dirty_state(game)
    game.screen_name = "menu"
    game.draw()
    game._start_new_game()
    assert game.screen_name == "confirm"
    assert game.confirm_dialog["title"] == "НАЧАТЬ НОВУЮ ИГРУ?"
    # пока не подтвердили — прогресс на месте
    assert game.state.current_case_id == "bank_heist"
    assert game.state.money == 450


def test_new_game_cancel_keeps_progress(game):
    _dirty_state(game)
    game.screen_name = "menu"
    game.draw()
    game._start_new_game()
    game.draw()
    _press_release(game, game.confirm_rects["no"])
    assert game.screen_name == "menu"
    assert game.state.current_case_id == "bank_heist"
    assert game.state.money == 450
    assert game.state.collected_clues == {"clue_log", "clue_tv"}


def test_new_game_confirm_wipes_and_opens_customization(game):
    _dirty_state(game)
    game.screen_name = "menu"
    game.draw()
    game._start_new_game()
    game.draw()
    _press_release(game, game.confirm_rects["yes"])
    assert game.screen_name == "customization"
    assert game.state.current_case_id is None
    assert game.state.money == START_MONEY
    assert game.state.reputation == 0
    assert game.state.collected_clues == set()
    assert game.state.completed_cases == set()
    assert game.state.unlocked_endings == {}
    assert game.current_case is None
    assert load_game().current_case_id is None


def test_new_game_without_progress_goes_straight_ahead(game):
    game.state = GameState()
    game.current_case = None
    game.screen_name = "menu"
    game._start_new_game()
    assert game.screen_name == "customization"


def test_wipe_progress_requires_confirmation(game):
    _dirty_state(game)
    game.screen_name = "settings"
    game.draw()
    _press_release(game, settings_layout(1280, 720).wipe)
    assert game.screen_name == "confirm"
    assert "СБРОСИТЬ ПРОГРЕСС" in game.confirm_dialog["title"]
    assert has_save()
    assert game.state.current_case_id == "bank_heist"


def test_wipe_progress_confirm_clears_everything(game):
    _dirty_state(game)
    game.screen_name = "settings"
    game.draw()
    _press_release(game, settings_layout(1280, 720).wipe)
    game.draw()
    _press_release(game, game.confirm_rects["yes"])
    assert game.screen_name == "menu"
    assert game.state.current_case_id is None
    assert game.state.money == START_MONEY
    assert game.state.reputation == 0
    assert game.state.board_links == set()
    assert game.state.asked_topics == set()
    assert game.current_case is None
    assert game.search is None
    assert load_game().current_case_id is None


def test_confirm_screen_swallows_events(game):
    """Под диалогом ничего не нажимается, Esc — отмена."""
    _dirty_state(game)
    game.screen_name = "settings"
    game.draw()
    _press_release(game, settings_layout(1280, 720).wipe)
    assert game.screen_name == "confirm"
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
    assert game.screen_name == "confirm"
    game.draw()
    _press_release(game, game.confirm_rects["yes"])
    game.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    )
    assert game.screen_name in {"menu", "settings"}
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.screen_name == "menu"


def test_confirm_answer_waits_for_mouse_release(game):
    """«Да» срабатывает на отпускании — иначе отпускание дожимало бы экран под ним."""
    _dirty_state(game)
    game.screen_name = "menu"
    game.draw()
    game._start_new_game()
    game.draw()
    yes = game.confirm_rects["yes"]
    pygame.mouse.get_pos = lambda: yes.center
    pygame.mouse.get_pressed = lambda *a: (True, False, False)
    game.draw()
    assert game.screen_name == "confirm"
    assert game.state.current_case_id == "bank_heist"
    pygame.mouse.get_pressed = lambda *a: (False, False, False)
    game.draw()
    assert game.screen_name == "customization"
    assert game.state.current_case_id is None


def test_settings_cancel_button_is_renamed_and_safe(game):
    """Серая кнопка рядом с «ПРИМЕНИТЬ» больше не называется «СБРОСИТЬ»."""
    _dirty_state(game)
    game.screen_name = "settings"
    game.draw()
    _press_release(game, settings_layout(1280, 720).reset)
    assert game.state.current_case_id == "bank_heist"
    assert game.state.money == 450
    assert game.screen_name == "settings"


# ── данные ──────────────────────────────────────────────────────────


def test_every_advanced_case_has_locations_to_explore():
    for case in BUILTIN_CASES:
        if not case.get("advanced"):
            continue
        state = GameState()
        for loc in case["locations"]:
            session = search.Search(case, loc["id"], state)
            assert session.spots, f"{case['id']}:{loc['id']}"
            assert not session.finished, f"{case['id']}:{loc['id']}"


def test_search_charge_is_ten_minutes():
    assert search_view.SEARCH_MINUTES == 10
