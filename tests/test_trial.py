"""Суд: кто, зачем и как — мотив и способ на экране обвинения."""

import pytest

from detective_game import endings, trial
from detective_game.data import list_cases, load_case
from detective_game.game_state import GameState


def _case():
    return load_case("missing_chess")


def _state(motive=None, method=None, suspect="finch"):
    state = GameState()
    state.accusation_result = suspect
    state.trial_motive = motive
    state.trial_method = method
    state.collected_clues = {c["id"] for c in _case()["clues"]}
    return state


def test_available_only_for_advanced_cases_with_trial():
    assert trial.available(_case()) is True
    assert trial.available(load_case("bank_heist")) is True
    assert trial.available(load_case("tutorial")) is False
    assert trial.available({"advanced": True}) is False


def test_motives_and_methods_lists():
    case = _case()
    motives = trial.motives(case)
    methods = trial.methods(case)
    assert len(motives) == 3 and len(methods) == 3
    assert all(item["id"] and item["text"] for item in motives + methods)


def test_answers_point_to_existing_options():
    for case in list_cases():
        if not trial.available(case):
            continue
        motive_ids = {item["id"] for item in trial.motives(case)}
        method_ids = {item["id"] for item in trial.methods(case)}
        culprit = next(s["id"] for s in case["suspects"] if s.get("is_culprit"))
        answer = trial.answers(case, culprit)
        assert answer.get(trial.MOTIVE) in motive_ids
        assert answer.get(trial.METHOD) in method_ids


def test_select_from_validates_ids():
    case = _case()
    state = _state()
    assert trial.select_from(case, state, trial.MOTIVE, "collection") is True
    assert state.trial_motive == "collection"
    assert trial.select_from(case, state, trial.MOTIVE, "no_such") is False
    assert state.trial_motive == "collection"
    assert trial.select_from(case, state, "bogus", "x") is False
    assert trial.select_from(case, state, trial.METHOD, None) is True
    assert state.trial_method is None


def test_ready_requires_both_answers():
    case = _case()
    state = _state(motive="collection")
    assert trial.ready(case, state) is False
    state.trial_method = "frame"
    assert trial.ready(case, state) is True
    assert trial.ready(load_case("tutorial"), GameState()) is True


def test_evaluate_correct_and_wrong():
    case = _case()
    ok = trial.evaluate(case, _state(motive="collection", method="frame"))
    assert ok["asked"] is True
    assert ok["score"] == 2
    assert ok["motive_ok"] and ok["method_ok"]
    assert trial.rank_bonus(case, _state(motive="collection", method="frame")) == 1

    half = trial.evaluate(case, _state(motive="collection", method="flight"))
    assert half["score"] == 1
    assert trial.rank_bonus(case, _state(motive="collection", method="flight")) == 0

    bad = trial.evaluate(case, _state(motive="ransom", method="flight"))
    assert bad["score"] == 0
    assert trial.rank_bonus(case, _state(motive="ransom", method="flight")) == -1


def test_unanswered_trial_gives_no_penalty():
    case = _case()
    state = _state()
    assert trial.answered(state) is False
    assert trial.rank_bonus(case, state) == 0
    assert trial.verdict_text(case, state) == ""


def test_verdict_text():
    case = _case()
    text = trial.verdict_text(case, _state(motive="collection", method="frame"))
    assert "мотив верен" in text and "способ верен" in text
    text = trial.verdict_text(case, _state(motive="ransom", method="frame"))
    assert "мотив не доказан" in text


def test_rank_bonus_applied_to_ending():
    case = _case()
    base = endings.resolve(case, _state("collection", "frame"))
    assert base["trial"]["score"] == 2
    assert any("мотив и способ" in note for note in base.get("rank_notes", []))
    wrong = endings.resolve(case, _state("ransom", "flight"))
    assert wrong["rank"] == endings.demote_rank(base["rank"]) or wrong["rank"] != base["rank"]
    assert wrong.get("rank_notes")


def test_late_deadline_demotes_rank():
    case = _case()
    state = _state("collection", "frame")
    state.case_time_minutes = 10**6
    result = endings.resolve(case, state)
    assert result["late"] is True
    assert any("срок" in note for note in result.get("rank_notes", []))


@pytest.mark.parametrize("case_id", ["missing_chess", "bank_heist"])
def test_advanced_cases_have_full_trial(case_id):
    case = load_case(case_id)
    assert trial.available(case)
    culprit = next(s["id"] for s in case["suspects"] if s.get("is_culprit"))
    answer = trial.answers(case, culprit)
    state = _state(answer["motive"], answer["method"], suspect=culprit)
    state.current_case_id = case_id
    assert trial.evaluate(case, state)["score"] == 2
