"""Тесты прогресса: «Следующее дело» после успеха и музыка по локациям."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import endings as ending_logic  # noqa: E402
from detective_game.data import list_cases  # noqa: E402
from detective_game.synth import TRACKS  # noqa: E402

CASES = {case["id"]: case for case in list_cases()}
CASE_ORDER = [case["id"] for case in list_cases()]


@pytest.fixture(scope="module")
def game():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    g = Game()
    g.notifications.clear()
    yield g
    pygame.quit()


def _culprit(case):
    return next(s["id"] for s in case["suspects"] if s.get("is_culprit"))


def _solve(game, case_id):
    """Довести дело до успешного финала, как это делает игра."""
    case = CASES[case_id]
    game.current_case = case
    game.state.current_case_id = case_id
    game.state.collected_clues = {clue["id"] for clue in case["clues"]}
    game.state.case_state = "in_progress"
    game.accusation_selected = _culprit(case)
    game._finish_case()
    return case


# ---------------------------------------------------------------------------
# Порядок дел
# ---------------------------------------------------------------------------


def test_next_case_follows_card_order(game):
    for index, case_id in enumerate(CASE_ORDER[:-1]):
        game.current_case = CASES[case_id]
        assert game.next_case()["id"] == CASE_ORDER[index + 1]


def test_last_case_has_no_next(game):
    game.current_case = CASES[CASE_ORDER[-1]]
    assert game.next_case() is None


def test_unknown_case_has_no_next(game):
    game.current_case = {"id": "нет-такого-дела"}
    assert game.next_case() is None


# ---------------------------------------------------------------------------
# Экран финала
# ---------------------------------------------------------------------------


def test_success_adds_next_case_button(game):
    _solve(game, "tutorial")
    game.draw()
    assert "next" in game.ending_rects
    assert game.ending_rects["next"].width > 0
    # кнопки не наезжают друг на друга
    rects = [game.ending_rects[key] for key in ("menu", "next", "replay")]
    for left, right in zip(rects, rects[1:], strict=False):
        assert left.right < right.left


def test_next_case_button_starts_next_case(game):
    _solve(game, "tutorial")
    game.draw()
    game._ending_action("next")
    assert game.state.current_case_id == CASE_ORDER[1]
    assert game.screen_name == "cutscene"
    assert game.state.collected_clues == set()
    assert game.state.case_time_minutes == 0


def test_failure_has_no_next_case_button(game):
    case = CASES["missing_chess"]
    game.current_case = case
    game.state.current_case_id = case["id"]
    game.state.collected_clues = {clue["id"] for clue in case["clues"]}
    wrong = next(s["id"] for s in case["suspects"] if not s.get("is_culprit"))
    game.accusation_selected = wrong
    game._finish_case()
    assert not ending_logic.resolve(case, game.state)["success"]
    game.draw()
    assert "next" not in game.ending_rects
    assert "replay" in game.ending_rects


def test_last_successful_case_shows_no_next_button(game):
    last = CASE_ORDER[-1]
    _solve(game, last)
    game.draw()
    assert "next" not in game.ending_rects
    assert set(game.ending_rects) == {"menu", "replay"}


def test_completed_cases_remembered_and_saved(game):
    _solve(game, "tutorial")
    assert "tutorial" in game.state.completed_cases
    data = game.state.to_dict()
    assert "tutorial" in data["completed_cases"]
    restored = type(game.state).from_dict(data)
    assert "tutorial" in restored.completed_cases


def test_failed_case_not_marked_completed(game):
    case = CASES["bank_heist"]
    game.current_case = case
    game.state.current_case_id = case["id"]
    game.state.collected_clues = {clue["id"] for clue in case["clues"]}
    game.accusation_selected = next(s["id"] for s in case["suspects"] if not s.get("is_culprit"))
    game.state.completed_cases.discard(case["id"])
    game._finish_case()
    assert case["id"] not in game.state.completed_cases


def test_enter_on_success_starts_next_case(game):
    pygame = pytest.importorskip("pygame")
    _solve(game, "tutorial")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert game.state.current_case_id == CASE_ORDER[1]


def test_escape_on_ending_returns_to_menu(game):
    pygame = pytest.importorskip("pygame")
    _solve(game, "tutorial")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.screen_name == "menu"


def test_replay_restarts_same_case(game):
    _solve(game, "tutorial")
    game._ending_action("replay")
    assert game.state.current_case_id == "tutorial"
    assert game.screen_name == "map"
    assert game.state.collected_clues == set()


# ---------------------------------------------------------------------------
# Музыка
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "location_id,expected",
    [
        ("office", "noir"),
        ("park", "mystery"),
        ("bar", "lounge"),
        ("warehouse", "harbor"),
        ("police", "precinct"),
    ],
)
def test_location_has_own_theme(game, location_id, expected):
    game.current_case = CASES["missing_chess"]
    game.location_id = location_id
    game.screen_name = "location"
    assert game._music_key() == expected


def test_vault_and_mansion_are_mystery(game):
    game.current_case = CASES["bank_heist"]
    game.location_id = "vault"
    game.screen_name = "location"
    assert game._music_key() == "mystery"


def test_unknown_location_falls_back_to_investigation(game):
    game.current_case = CASES["missing_chess"]
    game.location_id = "station"  # тип public — своей темы нет
    game.screen_name = "location"
    assert game._music_key() == "investigation"


def test_screen_themes(game):
    game.current_case = CASES["missing_chess"]
    for screen, expected in (
        ("menu", "noir"),
        ("map", "investigation"),
        ("notebook", "mystery"),
        ("accusation", "chase"),
        ("puzzle", "tension"),
    ):
        game.screen_name = screen
        assert game._music_key() == expected, screen


def test_ending_theme_depends_on_result(game):
    _solve(game, "tutorial")
    game.screen_name = "ending"
    assert game._music_key() == "success"
    case = CASES["missing_chess"]
    game.current_case = case
    game.state.accusation_result = next(s["id"] for s in case["suspects"] if not s.get("is_culprit"))
    assert game._music_key() == "failure"


def test_new_tracks_registered():
    for name in ("lounge", "harbor", "precinct", "mystery", "chase"):
        assert name in TRACKS
    from detective_game.audio import MUSIC_TRACKS

    assert set(TRACKS) == set(MUSIC_TRACKS)
