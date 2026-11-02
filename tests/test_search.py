"""Тесты обыска локации: хотспоты, ложные точки и таймер."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from detective_game import search  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402

CASE = {
    "id": "test_case",
    "locations": [
        {"id": "warehouse", "name": "Склад", "type": "warehouse"},
        {"id": "bar", "name": "Бар", "type": "bar"},
        {"id": "office", "name": "Офис", "type": "hub"},
    ],
    "clues": [
        {"id": "c_open", "title": "Открытая", "location": "warehouse"},
        {"id": "c_hidden", "title": "Скрытая", "location": "warehouse", "hidden": True},
        {"id": "c_second", "title": "Вторая скрытая", "location": "warehouse", "hidden": True},
        {"id": "c_elsewhere", "title": "В баре", "location": "bar", "hidden": True},
    ],
}


def _state():
    return GameState()


def test_hidden_flag_and_reveal():
    hidden = {"id": "x", "hidden": True}
    assert search.is_hidden(hidden)
    assert not search.is_hidden({"id": "x"})
    assert not search.is_hidden(None)
    state = _state()
    assert not search.is_revealed(state, hidden)
    state.hidden_found = {"x"}
    assert search.is_revealed(state, hidden)
    state2 = _state()
    state2.collected_clues = {"x"}
    assert search.is_revealed(state2, hidden)
    assert search.is_revealed(state2, {"id": "plain"})


def test_visible_and_hidden_lists():
    state = _state()
    assert [c["id"] for c in search.visible_clues(CASE, "warehouse", state)] == ["c_open"]
    assert [c["id"] for c in search.hidden_here(CASE, "warehouse", state)] == [
        "c_hidden",
        "c_second",
    ]
    state.hidden_found = {"c_hidden"}
    assert [c["id"] for c in search.visible_clues(CASE, "warehouse", state)] == [
        "c_open",
        "c_hidden",
    ]
    assert [c["id"] for c in search.hidden_here(CASE, "warehouse", state)] == ["c_second"]


def test_build_spots_has_clues_and_decoys():
    state = _state()
    spots = search.build(CASE, "warehouse", state)
    kinds = [spot["kind"] for spot in spots]
    assert kinds.count("clue") == 2
    assert kinds.count("flavour") == search.DECOYS_PER_LOCATION
    assert len(spots) == 4
    for spot in spots:
        assert 0.0 <= spot["x"] <= 1.0 and 0.0 <= spot["y"] <= 1.0
        assert spot["label"]
    clue_spots = [spot for spot in spots if spot["kind"] == "clue"]
    assert {spot["clue"] for spot in clue_spots} == {"c_hidden", "c_second"}


def test_build_positions_are_deterministic_and_apart():
    first = search.build(CASE, "warehouse", _state())
    second = search.build(CASE, "warehouse", _state())
    assert [(s["id"], s["x"], s["y"]) for s in first] == [
        (s["id"], s["x"], s["y"]) for s in second
    ]
    coords = [(s["x"], s["y"]) for s in first]
    for i, a in enumerate(coords):
        for b in coords[i + 1 :]:
            assert ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 > 0.05


def test_build_without_hidden_clues_has_only_flavour():
    spots = search.build(CASE, "office", _state())
    assert spots
    assert all(spot["kind"] == "flavour" for spot in spots)


def test_found_spots_disappear():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    spot = session.spots[0]
    assert session.take(spot) is spot
    assert spot["id"] in state.search_found
    assert spot not in search.build(CASE, "warehouse", state)


def test_search_take_clue_reveals_it():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    clue_spot = next(spot for spot in session.spots if spot["kind"] == "clue")
    session.take(clue_spot)
    assert clue_spot["clue"] in state.hidden_found
    assert clue_spot["clue"] in {c["id"] for c in search.visible_clues(CASE, "warehouse", state)}
    assert session.found_count == 1


def test_search_take_decoys_reveals_nothing():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    flavour = next(spot for spot in session.spots if spot["kind"] == "flavour")
    session.take(flavour)
    assert state.hidden_found == set()
    assert flavour["id"] in state.search_found


def test_search_take_invalid_inputs():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    assert session.take(None) is None
    assert session.take({"id": "чужой"}) is None
    session.skip()
    assert session.take(session.spots[0]) is None


def test_at_finds_nearest_spot():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    spot = session.spots[2]
    assert session.at(spot["x"], spot["y"]) is spot
    # чуть рядом — всё ещё попадание, но далеко — нет
    assert session.at(spot["x"] + 0.01, spot["y"] + 0.01) is spot
    assert session.at(0.99, 0.99) is None


def test_counters_and_finish_condition():
    state = _state()
    session = search.Search(CASE, "warehouse", state)
    assert session.total == 4
    assert session.clue_spots_left == 2
    assert not session.finished
    for spot in list(session.spots):
        if spot["kind"] == "clue":
            session.take(spot)
    assert session.clue_spots_left == 0
    assert session.finished


def test_timer_expires():
    state = _state()
    session = search.Search(CASE, "warehouse", state, seconds=10)
    assert session.remaining == 10
    session.update(4.0)
    assert session.remaining == 6
    session.update(100.0)
    assert session.remaining == 0
    assert session.expired
    assert session.finished
    session.update(1.0)
    assert session.remaining == 0


def test_skip_finishes():
    session = search.Search(CASE, "warehouse", _state())
    session.skip()
    assert session.expired


def test_flavour_texts_per_type():
    for loc_type, texts in search.FLAVOUR.items():
        assert len(texts) >= search.DECOYS_PER_LOCATION, loc_type
    bar_case = {"id": "bar_case", "locations": [{"id": "bar", "type": "bar"}], "clues": []}
    labels = {spot["label"] for spot in search.build(bar_case, "bar", _state())}
    assert labels and labels <= set(search.FLAVOUR["bar"])
    unknown = {"id": "u", "locations": [{"id": "x", "type": "нет такого"}], "clues": []}
    spots = search.build(unknown, "x", _state())
    assert {spot["label"] for spot in spots} <= set(search.DEFAULT_FLAVOUR)


def test_search_does_not_break_when_clue_list_is_empty():
    session = search.Search({"id": "empty", "clues": []}, "nowhere", _state())
    assert session.spots
    assert session.clue_spots_left == 0
    assert session.finished


@pytest.mark.parametrize(
    "loc_type", sorted(set(search.FLAVOUR)), ids=lambda value: value
)
def test_flavour_spots_are_clickable(loc_type):
    case = {"id": f"case_{loc_type}", "locations": [{"id": "loc", "type": loc_type}], "clues": []}
    session = search.Search(case, "loc", _state())
    for spot in list(session.spots):
        found = session.at(spot["x"], spot["y"])
        assert found is not None


def test_spot_coordinates_can_come_from_case_data():
    case = {
        "id": "coords",
        "locations": [{"id": "loc", "type": "public"}],
        "clues": [{"id": "c1", "location": "loc", "hidden": True, "spot": [0.31, 0.44]}],
    }
    spot = next(s for s in search.build(case, "loc", _state()) if s["kind"] == "clue")
    assert (spot["x"], spot["y"]) == (0.31, 0.44)
    broken = {
        "id": "coords2",
        "locations": [{"id": "loc", "type": "public"}],
        "clues": [{"id": "c1", "location": "loc", "hidden": True, "spot": ["a", 2]}],
    }
    spot = next(s for s in search.build(broken, "loc", _state()) if s["kind"] == "clue")
    assert 0.0 < spot["x"] < 1.0 and 0.0 < spot["y"] < 1.0
