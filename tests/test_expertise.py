"""Экспертиза улик: слухи, подброшенные бумажки и счёт суда."""

import pytest

from detective_game import expertise, pressure
from detective_game.data import get_clue, list_cases, load_case
from detective_game.game_state import GameState


def _case():
    return load_case("bank_heist")


def _state():
    state = GameState()
    state.money = 500
    state.reputation = 2
    state.collected_clues = {"clue_coffee", "clue_cleaner_key", "clue_log"}
    return state


def test_reliability_and_needs_check():
    case = _case()
    coffee = get_clue(case, "clue_coffee")
    log = get_clue(case, "clue_log")
    assert expertise.reliability(coffee) == expertise.HEARSAY
    assert expertise.reliability(log) == expertise.SOLID
    assert expertise.needs_check(case, coffee) is True
    assert expertise.needs_check(case, log) is False
    # в простом деле экспертиза не нужна
    assert expertise.needs_check(load_case("tutorial"), {"reliability": "hearsay"}) is False


def test_submit_confirms_hearsay():
    case = _case()
    state = _state()
    result = expertise.submit(state, case, get_clue(case, "clue_coffee"))
    assert result["status"] == "ok"
    assert result["fake"] is False
    assert state.money == 500 - pressure.LAB_COST
    assert state.case_time_minutes == pressure.LAB_MINUTES
    assert "clue_coffee" in state.confirmed_clues
    assert state.reputation == 3
    again = expertise.submit(state, case, get_clue(case, "clue_coffee"))
    assert again["status"] == "already"


def test_submit_removes_planted_clue():
    case = _case()
    state = _state()
    result = expertise.submit(state, case, get_clue(case, "clue_cleaner_key"))
    assert result["status"] == "ok"
    assert result["fake"] is True
    assert "clue_cleaner_key" in state.fake_clues
    assert "clue_cleaner_key" not in state.collected_clues
    assert state.reputation == 1  # +1 за подтверждение не даётся, −1 за фальшивку


def test_submit_rejects_solid_clue():
    case = _case()
    state = _state()
    assert expertise.submit(state, case, get_clue(case, "clue_log"))["status"] == "solid"
    assert state.money == 500


def test_submit_requires_money_and_reputation():
    case = _case()
    state = _state()
    state.money = pressure.LAB_COST - 1
    assert expertise.submit(state, case, get_clue(case, "clue_coffee"))["status"] == "no_money"
    state.money = 500
    state.reputation = 0
    assert expertise.submit(state, case, get_clue(case, "clue_coffee"))["status"] == "no_rep"


def test_court_clues_filters_unchecked_and_fake():
    case = _case()
    state = _state()
    assert expertise.court_clues(case, state) == {"clue_log"}
    expertise.submit(state, case, get_clue(case, "clue_coffee"))
    assert expertise.court_clues(case, state) == {"clue_log", "clue_coffee"}
    expertise.submit(state, case, get_clue(case, "clue_cleaner_key"))
    assert "clue_cleaner_key" not in expertise.court_clues(case, state)


def test_pending_lists_unchecked_clues():
    case = _case()
    state = _state()
    pending = {clue["id"] for clue in expertise.pending(case, state)}
    assert pending == {"clue_coffee", "clue_cleaner_key"}


def test_status_labels():
    case = _case()
    state = _state()
    coffee = get_clue(case, "clue_coffee")
    assert expertise.status(case, state, coffee) == "hearsay"
    assert "без экспертизы" in expertise.status_label(case, state, coffee)
    expertise.submit(state, case, coffee)
    assert expertise.status(case, state, coffee) == "confirmed"
    assert "подтверждено" in expertise.status_label(case, state, coffee)
    state.collected_clues.add("clue_cleaner_key")
    key = get_clue(case, "clue_cleaner_key")
    expertise.submit(state, case, key)
    assert expertise.status(case, state, key) == "fake"
    assert "подброшено" in expertise.status_label(case, state, key)


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_reliability_is_known(case):
    for clue in case["clues"]:
        assert expertise.reliability(clue) in expertise.RELIABILITY_LABELS


def test_advanced_cases_have_expertise_targets():
    for case_id in ("missing_chess", "bank_heist"):
        case = load_case(case_id)
        targets = [c for c in case["clues"] if expertise.needs_check(case, c)]
        assert targets, case_id
        assert any(expertise.reliability(c) == expertise.PLANTED for c in targets)
