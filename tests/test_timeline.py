"""Тесты реконструкции таймлайна: карточки событий по порядку."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import timeline  # noqa: E402
from detective_game.data import list_cases  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402

CASE = {
    "id": "test_case",
    "timeline": [
        {"id": "a", "time": "09:00", "text": "Первый"},
        {"id": "b", "time": "10:00", "text": "Второй"},
        {"id": "c", "time": "11:00", "text": "Третий"},
        {"id": "d", "time": "12:00", "text": "Четвёртый"},
    ],
}


def _solve(state, case=CASE):
    state.timeline_order = timeline.correct_order(case)
    return timeline.check(state, case)


def test_events_from_case_data():
    events = timeline.events(CASE)
    assert [e["id"] for e in events] == ["a", "b", "c", "d"]
    assert events[0]["time"] == "09:00"
    assert timeline.available(CASE)
    assert timeline.correct_order(CASE) == ["a", "b", "c", "d"]
    assert timeline.by_id(CASE)["c"]["text"] == "Третий"


def test_events_fall_back_to_builtin_timelines():
    for case in list_cases():
        events = timeline.events(case)
        assert len(events) >= timeline.MIN_EVENTS
        assert len({e["id"] for e in events}) == len(events)
        assert all(e["text"] for e in events)


def test_unknown_case_has_no_timeline():
    assert timeline.events({"id": "nope"}) == []
    assert not timeline.available({"id": "nope"})
    assert timeline.events(None) == []


def test_case_timeline_overrides_builtin():
    case = {"id": "tutorial", "timeline": [{"id": "z", "text": "Своё"}] * 3}
    events = timeline.events(case)
    assert len(events) == 3
    assert all(e["id"] == "z" for e in events)


def test_events_skip_broken_items_and_default_ids():
    case = {
        "id": "x",
        "timeline": [
            {"text": "Раз"},
            "мусор",
            {"text": "Два", "time": 5},
        ],
    }
    events = timeline.events(case)
    assert [e["id"] for e in events] == ["e0", "e2"]
    assert events[0]["time"] == ""
    assert events[1]["time"] == "5"


def test_shuffled_is_deterministic_and_not_sorted():
    first = timeline.shuffled(CASE)
    second = timeline.shuffled(CASE)
    assert first == second
    assert sorted(first) == sorted(timeline.correct_order(CASE))
    assert first != timeline.correct_order(CASE)


def test_start_prepares_state_and_is_stable():
    state = GameState()
    order = timeline.start(state, CASE)
    assert sorted(order) == ["a", "b", "c", "d"]
    assert state.timeline_order == order
    assert timeline.start(state, CASE) == order


def test_start_reshuffles_when_card_set_changes():
    state = GameState()
    state.timeline_order = ["a", "b"]
    order = timeline.start(state, CASE)
    assert sorted(order) == ["a", "b", "c", "d"]


def test_swap_and_move():
    state = GameState()
    state.timeline_order = ["a", "b", "c", "d"]
    timeline.swap(state, 0, 2)
    assert state.timeline_order == ["c", "b", "a", "d"]
    timeline.swap(state, 0, 9)
    assert state.timeline_order == ["c", "b", "a", "d"]
    timeline.swap(state, 1, 1)
    assert state.timeline_order == ["c", "b", "a", "d"]
    assert timeline.move(state, 0, 1) == 1
    assert state.timeline_order == ["b", "c", "a", "d"]
    assert timeline.move(state, 0, -1) == 0
    assert timeline.move(state, 3, 5) == 3
    assert state.timeline_order == ["b", "c", "a", "d"]


def test_move_on_empty_order_is_safe():
    state = GameState()
    assert timeline.move(state, 0, 1) == 0


def test_matched_counts_right_positions():
    state = GameState()
    state.timeline_order = ["a", "c", "b", "d"]
    assert timeline.matched(state, CASE) == 2


def test_check_wrong_order_counts_attempts_and_time():
    state = GameState()
    state.timeline_order = ["b", "a", "c", "d"]
    result = timeline.check(state, CASE)
    assert result == {"solved": False, "matched": 2, "total": 4, "attempts": 1}
    assert state.timeline_attempts == 1
    assert not state.timeline_solved
    assert state.reputation == 0


def test_check_solves_once_and_awards_reputation_once():
    state = GameState()
    result = _solve(state)
    assert result["solved"] is True
    assert result["matched"] == 4
    assert state.timeline_solved
    assert state.reputation == 2
    assert timeline.is_solved(state, CASE)
    again = _solve(state)
    assert again["solved"] is True
    assert again["attempts"] == 2
    assert state.reputation == 2


def test_reset_reshuffles_cards():
    state = GameState()
    state.timeline_order = timeline.correct_order(CASE)
    timeline.reset(state, CASE)
    assert state.timeline_order != timeline.correct_order(CASE)
    assert sorted(state.timeline_order) == ["a", "b", "c", "d"]


def test_order_autostarts_on_empty_state():
    state = GameState()
    order = timeline.order(state, CASE)
    assert sorted(order) == ["a", "b", "c", "d"]
    assert state.timeline_order == order


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_every_case_can_be_reconstructed(case):
    state = GameState()
    state.timeline_order = timeline.shuffled(case)
    assert timeline.matched(state, case) < len(timeline.events(case))
    result = _solve(state, case)
    assert result["solved"]
    assert result["total"] == len(timeline.events(case))
    assert state.reputation == 2
