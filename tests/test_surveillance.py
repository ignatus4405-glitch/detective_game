"""Тесты слежки: дистанция, шкалы подозрения/потери и награда."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from detective_game import surveillance  # noqa: E402
from detective_game.data import list_cases  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402

SPEC = {
    "title": "Слежка за тестом",
    "target": "Беглец",
    "place": "Порт",
    "seconds": 20.0,
    "band": [0.3, 0.7],
    "reveal": "clue_hidden",
    "money": 50,
    "reputation": 1,
}


def _run(tail, advance, steps=200, dt=0.1):
    for _ in range(steps):
        if tail.finished:
            break
        tail.update(dt, advance)
    return tail


def test_spec_for_builtin_cases():
    for case in list_cases():
        spec = surveillance.spec_for(case)
        if not spec:
            continue
        assert spec["title"]
        low, high = spec["band"]
        assert 0.05 <= low < high <= 0.95


def test_spec_for_returns_none_and_clamps():
    assert surveillance.spec_for({"id": "nope"}) is None
    assert surveillance.spec_for(None) is None
    spec = surveillance.spec_for({"surveillance": {"band": [-3, 9]}})
    assert spec["band"] == [0.05, 0.95]
    broken = surveillance.spec_for({"surveillance": {"band": "мусор"}})
    assert broken["band"] == list(surveillance.DEFAULT_BAND)
    defaults = surveillance.spec_for({"surveillance": {"title": "Т"}})
    assert defaults["seconds"] == surveillance.DEFAULT_SECONDS
    # пустой словарь — как отсутствие слежки
    assert surveillance.spec_for({"surveillance": {}}) is None


def test_available_respects_clue_and_completion():
    case = {"id": "missing_chess"}
    state = GameState()
    assert not surveillance.available(case, state)
    state.collected_clues = {"clue_bar_testimony"}
    assert surveillance.available(case, state)
    state.tail_done = {"missing_chess"}
    assert not surveillance.available(case, state)
    assert not surveillance.available({"id": "tutorial"}, GameState())


def test_tail_initial_state():
    tail = surveillance.Tail(SPEC)
    assert tail.title == "Слежка за тестом"
    assert tail.duration == 20.0
    assert tail.progress == 0
    assert not tail.finished
    assert tail.in_band
    assert tail.message == "Дистанция в норме."
    assert tail.progress_text.startswith("Маршрут 0%")


def test_steady_pace_finishes_unnoticed():
    tail = _run(surveillance.Tail(SPEC), 0)
    assert tail.success and not tail.failed
    assert tail.progress == 1
    assert tail.suspicion == 0 and tail.lost == 0
    assert "незамеченным" in tail.message
    assert tail.events


def test_getting_too_close_raises_suspicion():
    tail = _run(surveillance.Tail(SPEC), 1)
    assert tail.failed
    assert tail.suspicion == 1.0
    assert "обернулся" in tail.message


def test_falling_behind_loses_target():
    tail = _run(surveillance.Tail(SPEC), -1)
    assert tail.failed
    assert tail.lost == 1.0
    assert "потеряли" in tail.message


def test_band_exit_changes_message():
    tail = surveillance.Tail(SPEC)
    tail.set_gap(0.1)
    assert "близко" in tail.message
    tail.set_gap(0.95)
    assert "далеко" in tail.message
    tail.set_gap(0.5)
    assert tail.in_band


def test_cool_down_after_suspicion():
    tail = surveillance.Tail(SPEC)
    tail.set_gap(0.1)
    tail.update(0.5, 0)
    hot = tail.suspicion
    assert hot > 0
    tail.set_gap(0.5)
    tail.update(1.0, 0)
    assert tail.suspicion < hot


def test_update_ignores_bad_dt_and_finished_tail():
    tail = surveillance.Tail(SPEC)
    tail.update(0, 0)
    tail.update(-1, 0)
    assert tail.elapsed == 0
    tail.update(10.0, 0)  # dt обрезается до 0.25
    assert tail.elapsed == 0.25
    tail.success = True
    tail.update(1.0, 0)
    assert tail.elapsed == 0.25


def test_restart_resets_progress():
    tail = surveillance.Tail(SPEC)
    tail.update(1.0, 0)
    tail.failed = True
    tail.restart()
    assert tail.progress == 0
    assert not tail.finished
    assert tail.elapsed == 0


def test_apply_reward_writes_state():
    state = GameState()
    result = surveillance.apply_reward({"id": "missing_chess"}, state, SPEC)
    assert result == {"reveal": "clue_hidden", "money": 50, "reputation": 1}
    assert state.hidden_found == {"clue_hidden"}
    assert state.money == 550
    assert state.reputation == 1
    assert state.tail_done == {"missing_chess"}


def test_apply_reward_without_rewards():
    state = GameState()
    result = surveillance.apply_reward({"id": "x"}, state, {"title": "Т"})
    assert result == {"reveal": None, "money": 0, "reputation": 0}
    assert state.money == 500
    assert state.tail_done == {"x"}


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_case_spec_matches_case_location_data(case):
    spec = surveillance.spec_for(case)
    if not spec:
        return
    if spec.get("reveal"):
        assert any(clue["id"] == spec["reveal"] for clue in case["clues"])
    if spec.get("requires_clue"):
        assert any(clue["id"] == spec["requires_clue"] for clue in case["clues"])


# ── маршрут перед слежкой ──────────────────────────────────────────


def test_routes_for_builtin_cases():
    for case in list_cases():
        routes = surveillance.routes_for(case)
        if not routes:
            continue
        assert len(routes) >= 2
        assert sum(1 for route in routes if route["correct"]) == 1
        for route in routes:
            assert route["title"] and route["note"]
            assert route["minutes"] > 0


def test_plan_marks_route_and_changes_band():
    spec = surveillance.spec_for({"id": "missing_chess"})
    routes = surveillance.routes_for({"id": "missing_chess"})
    good = next(route for route in routes if route["correct"])
    bad = next(route for route in routes if not route["correct"])
    plan_good = surveillance.plan({"id": "missing_chess"}, spec, good)
    plan_bad = surveillance.plan({"id": "missing_chess"}, spec, bad)
    assert plan_good["correct"] and not plan_bad["correct"]
    low_good, high_good = plan_good["spec"]["band"]
    low_bad, high_bad = plan_bad["spec"]["band"]
    assert high_good - low_good > high_bad - low_bad
    assert plan_good["minutes"] == good["minutes"]
    assert "проще" in plan_good["message"]


def test_plan_without_route_keeps_spec():
    spec = surveillance.spec_for({"id": "bank_heist"})
    plan = surveillance.plan({"id": "bank_heist"}, spec, None)
    assert plan["minutes"] == 0
    assert not plan["correct"]
