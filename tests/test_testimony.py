"""Сопоставление показаний: пары противоречий и выводы."""

import pytest

from detective_game import dialogue, testimony
from detective_game.data import list_cases, load_case
from detective_game.game_state import GameState


def _case():
    return load_case("missing_chess")


def _state(*keys):
    state = GameState()
    state.asked_topics = set(keys)
    return state


def test_contradictions_are_linked_to_real_topics():
    for case in list_cases():
        for item in testimony.contradictions(case):
            a = testimony.statement(case, item["a"])
            b = testimony.statement(case, item["b"])
            assert a and a["text"], f"{case['id']}/{item['id']}: нет реплики A"
            assert b and b["text"], f"{case['id']}/{item['id']}: нет реплики B"
            assert item["a"] != item["b"]


def test_advanced_cases_have_contradictions():
    for case_id in ("missing_chess", "bank_heist"):
        case = load_case(case_id)
        assert len(testimony.contradictions(case)) >= 2
        assert testimony.contradictions(load_case("tutorial")) == []


def test_statements_only_heard_topics():
    case = _case()
    state = _state("elena:0")
    keys = [item["key"] for item in testimony.statements(case, state)]
    assert keys == ["elena:0"]


def test_available_needs_two_heard_statements():
    case = _case()
    assert testimony.available(case, _state("elena:0")) is False
    assert testimony.available(case, _state("elena:0", "elena:1")) is True
    assert testimony.available(load_case("tutorial"), _state("mayor:0", "mayor:1")) is False


def test_check_finds_contradiction_and_pays_reputation():
    case = _case()
    item = testimony.contradictions(case)[0]
    state = _state(item["a"], item["b"])
    result = testimony.check(state, case, item["a"], item["b"])
    assert result["status"] == "ok"
    assert item["id"] in state.deductions
    assert state.reputation == item["reputation"]
    again = testimony.check(state, case, item["a"], item["b"])
    assert again["status"] == "already"


def test_check_is_order_insensitive():
    case = _case()
    item = testimony.contradictions(case)[0]
    state = _state(item["a"], item["b"])
    assert testimony.check(state, case, item["b"], item["a"])["status"] == "ok"


def test_check_wrong_pair_costs_time_and_trust():
    case = _case()
    item = testimony.contradictions(case)[0]
    state = _state(item["a"], "elena:0")
    result = testimony.check(state, case, item["a"], "elena:0")
    assert result["status"] == "wrong"
    assert state.case_time_minutes == testimony.WRONG_MINUTES
    assert state.trust["elena"] == -testimony.WRONG_TRUST


def test_check_same_locked_and_unknown():
    case = _case()
    item = testimony.contradictions(case)[0]
    state = _state(item["a"])
    assert testimony.check(state, case, item["a"], item["a"])["status"] == "same"
    assert testimony.check(state, case, item["a"], item["b"])["status"] == "locked"
    assert testimony.check(state, case, "ghost:0", item["a"])["status"] == "locked"
    assert testimony.statement(case, "bad-key") is None
    assert testimony.statement(case, "ghost:1") is None


def test_solved_pending_summary_and_hints():
    case = _case()
    items = testimony.contradictions(case)
    state = _state(*[key for item in items for key in (item["a"], item["b"])])
    assert testimony.solved(state, case) == []
    assert len(testimony.pending(case, state)) == len(items)
    assert "0" in testimony.summary(case, state)
    hints = testimony.hints(case, state)
    assert len(hints) == len(items)
    testimony.check(state, case, items[0]["a"], items[0]["b"])
    assert testimony.solved(state, case) == [items[0]["id"]]
    assert len(testimony.pending(case, state)) == len(items) - 1
    assert testimony.deduction(case, items[0]["id"])["title"]


def test_declined_and_repeat_helpers():
    case = _case()
    char = next(c for c in case["characters"] if c["id"] == "elena")
    state = GameState()
    assert dialogue.mark_asked(state, "elena", 0) is True
    assert dialogue.mark_asked(state, "elena", 0) is False
    assert dialogue.is_asked(state, "elena", 0) is True
    result = dialogue.decline(state, char, 1)
    assert result["status"] == "ok"
    assert dialogue.declined(state, "elena", 1) is True
    assert dialogue.declined(state, "elena", 2) is False
    assert dialogue.chosen(state, "elena", 1) == dialogue.DECLINED


@pytest.mark.parametrize("case_id", ["missing_chess", "bank_heist"])
def test_contradiction_statements_available_after_dialogue(case_id):
    case = load_case(case_id)
    for item in testimony.contradictions(case):
        for key in (item["a"], item["b"]):
            assert testimony.statement(case, key) is not None
