"""Тесты доски версий: связки «улика → подозреваемый» и выводы."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import board  # noqa: E402
from detective_game.data import list_cases  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402

CASES = {case["id"]: case for case in list_cases()}

CASE = {
    "id": "test_case",
    "clues": [
        {"id": "c1", "title": "Плащ"},
        {"id": "c2", "title": "Ключ"},
        {"id": "c3", "title": "Снимок"},
        {"id": "c4", "title": "Билет"},
    ],
    "suspects": [
        {
            "id": "s1",
            "name": "Иван",
            "motive": "Долг",
            "evidence": ["c1", "c2"],
            "is_culprit": True,
        },
        {"id": "s2", "name": "Пётр", "motive": "Ревность", "evidence": ["c3"]},
        {"id": "s3", "name": "Без улик", "evidence": []},
    ],
}


def _state(*clues):
    state = GameState()
    state.collected_clues = set(clues) if clues else {"c1", "c2", "c3", "c4"}
    return state


def test_suspects_skip_people_without_evidence():
    assert [s["id"] for s in board.suspects(CASE)] == ["s1", "s2"]
    assert board.suspects(None) == []
    assert board.suspects({}) == []


def test_total_links_counts_only_known_clues():
    assert board.total_links(CASE) == 3
    broken = {
        "clues": [{"id": "c1"}],
        "suspects": [{"id": "s1", "evidence": ["c1", "gone"]}],
    }
    assert board.total_links(broken) == 1
    assert board.total_links(None) == 0


def test_link_key_roundtrip():
    assert board.link_key("c1", "s1") == "c1|s1"
    assert board.parse_key("c1|s1") == ("c1", "s1")
    assert board.parse_key("мусор") == ("мусор", "")


def test_correct_link_marks_state_and_adds_reputation():
    state = _state()
    result = board.link(state, CASE, "c1", "s1")
    assert result["status"] == "ok"
    assert result["conclusion"] is None
    assert state.board_links == {"c1|s1"}
    assert state.reputation == 1
    assert result["time"] == 5


def test_second_link_completes_conclusion_and_bonus():
    state = _state()
    board.link(state, CASE, "c1", "s1")
    result = board.link(state, CASE, "c2", "s1")
    assert result["status"] == "ok"
    assert result["conclusion"]["suspect_id"] == "s1"
    assert "Долг" in result["conclusion"]["text"]
    # +1 за каждую связку и +2 за собранный вывод
    assert state.reputation == 4
    assert board.progress(CASE, state)["suspects_done"] == 1


def test_conclusion_not_issued_until_all_evidence_linked():
    state = _state()
    first = board.link(state, CASE, "c2", "s1")
    assert first["conclusion"] is None
    assert board.conclusion_for(CASE, state, board.suspect(CASE, "s1")) is None
    board.link(state, CASE, "c1", "s1")
    assert board.conclusion_for(CASE, state, board.suspect(CASE, "s1")) is not None


def test_wrong_link_is_remembered_and_blocked():
    state = _state()
    result = board.link(state, CASE, "c3", "s1")
    assert result["status"] == "wrong"
    assert result["time"] == 10
    assert state.board_wrong == {"c3|s1"}
    assert state.reputation == 0
    again = board.link(state, CASE, "c3", "s1")
    assert again["status"] == "blocked"


def test_known_link_is_idempotent():
    state = _state()
    board.link(state, CASE, "c1", "s1")
    again = board.link(state, CASE, "c1", "s1")
    assert again["status"] == "known"
    assert state.reputation == 1


def test_link_requires_collected_clue():
    state = _state("c1")
    result = board.link(state, CASE, "c2", "s1")
    assert result["status"] == "missing"
    assert "найдите" in result["message"].lower()


def test_link_unknown_clue_or_suspect():
    state = _state()
    assert board.link(state, CASE, "nope", "s1")["status"] == "missing"
    assert board.link(state, CASE, "c1", "nope")["status"] == "missing"


def test_progress_and_hint_pair():
    state = _state()
    assert board.progress(CASE, state) == {
        "correct": 0,
        "wrong": 0,
        "total": 3,
        "suspects_done": 0,
        "suspects_total": 2,
        "percent": 0,
    }
    clue_id, suspect_id = board.hint_pair(CASE, state)
    assert (clue_id, suspect_id) == ("c1", "s1")
    board.link(state, CASE, clue_id, suspect_id)
    assert board.hint_pair(CASE, state) == ("c2", "s1")
    progress = board.progress(CASE, state)
    assert progress["correct"] == 1
    assert progress["percent"] == 33


def test_hint_pair_ignores_clues_not_found_yet():
    state = _state("c3")
    assert board.hint_pair(CASE, state) == ("c3", "s2")


def test_hint_pair_empty_when_all_linked():
    state = _state()
    for clue_id in ("c1", "c2", "c3"):
        board.link(state, CASE, clue_id, "s1" if clue_id != "c3" else "s2")
    assert board.hint_pair(CASE, state) is None
    assert len(board.conclusions(CASE, state)) == 2


def test_build_conclusion_without_motive():
    text = board.build_conclusion({"id": "s9", "name": "Никто"})
    assert text["title"] == "Никто"
    assert "пора давить" in text["text"]


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_real_cases_expose_links(case):
    """В каждом деле есть верные связки, и они сходятся в вывод."""
    state = GameState()
    state.collected_clues = {clue["id"] for clue in case["clues"]}
    # в туториале одна связка — это учебный пример, в делах больше
    assert board.total_links(case) >= (1 if case["id"] == "tutorial" else 2)
    linked = 0
    for item in board.suspects(case):
        for clue_id in item.get("evidence", []):
            result = board.link(state, case, clue_id, item["id"])
            assert result["status"] in {"ok", "known"}
            linked += result["status"] == "ok"
    assert linked == board.total_links(case)
    assert state.reputation > 0
    assert board.progress(case, state)["percent"] == 100
    assert board.progress(case, state)["suspects_done"] == len(board.suspects(case))
    assert board.hint_pair(case, state) is None
