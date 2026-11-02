"""Сроки дела, цена промахов и тайминги «взрослых» правил."""

import pytest

from detective_game import pressure
from detective_game.data import load_case
from detective_game.game_state import GameState


def test_advanced_only_for_big_cases():
    assert pressure.advanced(load_case("missing_chess")) is True
    assert pressure.advanced(load_case("bank_heist")) is True
    assert pressure.advanced(load_case("tutorial")) is False
    assert pressure.advanced({}) is False


def test_deadline_defaults_and_override():
    assert pressure.deadline_minutes(load_case("tutorial")) == 0
    assert pressure.deadline_minutes({"advanced": True}) == 3 * 24 * 60
    assert pressure.deadline_minutes({"advanced": True, "deadline_days": 1}) == 24 * 60
    assert pressure.deadline_minutes({"advanced": True, "deadline_minutes": 90}) == 90


def test_remaining_and_late():
    case = load_case("bank_heist")
    state = GameState()
    limit = pressure.deadline_minutes(case)
    assert limit == 2 * 24 * 60
    assert pressure.remaining(state, case) == limit
    state.case_time_minutes = limit - 60
    assert pressure.remaining(state, case) == 60
    assert pressure.is_late(state, case) is False
    state.case_time_minutes = limit + 1
    assert pressure.is_late(state, case) is True
    assert pressure.has_deadline(case) is True


def test_slipped_case_only_after_half_deadline():
    case = load_case("bank_heist")
    state = GameState()
    limit = pressure.deadline_minutes(case)
    state.case_time_minutes = limit + limit // 4
    assert pressure.has_slipped_case(state, case) is False
    state.case_time_minutes = limit + limit // 2 + 1
    assert pressure.has_slipped_case(state, case) is True


@pytest.mark.parametrize(
    "minutes,text",
    [
        (0, "0 мин"),
        (45, "45 мин"),
        (60, "1 ч 00 м"),
        (150, "2 ч 30 м"),
        (24 * 60, "1 д 0 ч"),
        (24 * 60 + 5 * 60, "1 д 5 ч"),
    ],
)
def test_duration_text(minutes, text):
    assert pressure.duration_text(minutes) == text


def test_duration_text_late():
    assert pressure.duration_text(-150) == "просрочено на 2 ч 30 м"


def test_deadline_text_and_chip():
    case = load_case("missing_chess")
    state = GameState()
    assert "до срока" in pressure.deadline_text(state, case)
    assert pressure.deadline_chip(state, case).startswith("срок:")
    state.case_time_minutes = pressure.deadline_minutes(case) + 10
    assert "СРОК ВЫШЕЛ" in pressure.deadline_text(state, case)
    assert pressure.deadline_chip(state, case) == "СРОК ВЫШЕЛ"
    assert pressure.deadline_chip(state, load_case("tutorial")) == ""


def test_lab_affordability():
    state = GameState()
    state.money = pressure.LAB_COST
    state.reputation = pressure.LAB_REPUTATION
    assert pressure.lab_ready(state) is True
    state.reputation = 0
    assert pressure.can_afford_lab(state) == {"money": True, "reputation": False}
    assert pressure.lab_ready(state) is False


def test_call_schedule_and_cap():
    case = load_case("missing_chess")
    state = GameState()
    assert pressure.call_due(state, load_case("tutorial")) == 0
    assert pressure.call_due(state, case) == 0
    state.case_time_minutes = pressure.CALL_FIRST_MINUTE
    assert pressure.call_due(state, case) == 1
    state.calls_seen = 2
    state.case_time_minutes = pressure.CALL_FIRST_MINUTE + 2 * pressure.CALL_EVERY_MINUTES
    assert pressure.call_due(state, case) == 3
    state.calls_seen = 3
    assert pressure.call_due(state, case) == 0
