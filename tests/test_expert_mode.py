"""Экспертный режим: черновик доски, алиби, цепочка и новые дела."""
import itertools
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from detective_game import board, deduction, endings, search, trial
from detective_game.data import get_clue, list_cases, load_case
from detective_game.game_state import GameState

EXPERT_CASES = ["missing_chess", "bank_heist", "last_signal", "silent_archive"]


def _state(case_id="last_signal", all_clues=True):
    case = load_case(case_id)
    state = GameState()
    state.current_case_id = case_id
    state.difficulty = "expert"
    if all_clues:
        state.collected_clues = {c["id"] for c in case["clues"]}
        state.confirmed_clues = {c["id"] for c in case["clues"] if c.get("reliability") == "hearsay"}
    return case, state


def _culprit(case):
    return next(s["id"] for s in case["suspects"] if s.get("is_culprit"))


def _solve_proof(case, state):
    culprit = _culprit(case)
    state.accusation_result = culprit
    answers = trial.answers(case, culprit)
    state.trial_motive = answers["motive"]
    state.trial_method = answers["method"]
    for slot, accepted in case["proof"]["slots"].items():
        assert deduction.proof_select(case, state, slot, accepted[0])
    state.proof_counter = next(a["id"] for a in case["proof"]["alternatives"] if a.get("correct"))
    state.alibi_assignments = dict(case["alibi"]["solution"])
    state.alibi_solved = True


@pytest.mark.parametrize("case_id", EXPERT_CASES)
def test_expert_supported_and_classic_default(case_id):
    case = load_case(case_id)
    assert deduction.supported(case)
    assert not deduction.enabled(case, GameState())
    state = GameState(difficulty="expert")
    assert deduction.enabled(case, state)
    assert deduction.normalize_mode(load_case("tutorial"), "expert") == "classic"


@pytest.mark.parametrize("case_id", EXPERT_CASES)
def test_board_draft_does_not_reveal_correctness(case_id):
    case, state = _state(case_id)
    culprit = _culprit(case)
    clue = case["proof"]["board"][culprit][0]
    before = state.reputation
    result = board.link(state, case, clue, culprit)
    assert result["status"] == "draft"
    assert state.reputation == before
    assert state.case_time_minutes == 0
    assert board.link_key(clue, culprit) in state.board_draft
    assert not state.board_links
    assert board.conclusion_for(case, state, board.suspect(case, culprit)) is None
    removed = board.link(state, case, clue, culprit)
    assert removed["status"] == "draft_removed"


def test_board_review_checks_whole_version_and_caches():
    case, state = _state()
    culprit = _culprit(case)
    for clue in case["proof"]["board"][culprit]:
        board.link(state, case, clue, culprit)
    result = board.review(case, state, culprit)
    assert result["complete"] is True
    assert state.case_time_minutes == deduction.REVIEW_COST
    again = board.review(case, state, culprit)
    assert again["status"] == "cached"
    assert state.case_time_minutes == deduction.REVIEW_COST
    board.link(state, case, "clue_rumor", culprit)
    result = board.review(case, state, culprit)
    assert result["complete"] is False
    assert result["extra"] == 1


@pytest.mark.parametrize("case_id", EXPERT_CASES)
def test_alibi_sources_gate_and_unique_solution(case_id):
    case, state = _state(case_id, all_clues=False)
    spec = case["alibi"]
    assert not deduction.alibi_ready(case, state)
    state.collected_clues = {c["id"] for c in case["clues"]}
    state.asked_topics = {f["source"]["key"] for f in spec["facts"] if f["source"]["type"] == "dialogue"}
    facts = deduction.alibi_facts(case, state)
    assert all(f["unlocked"] for f in facts)
    people = [p["id"] for p in spec["people"]]
    places = [p["id"] for p in spec["places"]]
    solutions = []
    for perm in itertools.permutations(places):
        assignment = dict(zip(people, perm, strict=True))
        ok = True
        for fact in spec["facts"]:
            for c in fact.get("constraints", []):
                if c["type"] == "is" and assignment[c["person"]] != c["place"]:
                    ok = False
                if c["type"] == "not" and assignment[c["person"]] == c["place"]:
                    ok = False
        if ok:
            solutions.append(assignment)
    assert solutions == [spec["solution"]]
    state.alibi_assignments = dict(spec["solution"])
    assert deduction.alibi_ready(case, state)
    result = deduction.alibi_check(case, state)
    assert result["status"] == "ok"
    assert state.alibi_solved
    assert state.reputation == 2


def test_alibi_wrong_costs_time_not_cell_feedback():
    case, state = _state()
    state.asked_topics = {"vera:0"}
    state.alibi_assignments = {"vera": "bar", "owen": "transmitter", "jules": "studio"}
    result = deduction.alibi_check(case, state)
    assert result["status"] == "wrong"
    assert state.case_time_minutes == 10
    assert "vera" not in result["message"]


@pytest.mark.parametrize("case_id", EXPERT_CASES)
def test_proof_requires_all_links_and_refutation(case_id):
    case, state = _state(case_id)
    _solve_proof(case, state)
    assert deduction.proof_ready(case, state)
    assert deduction.proof_evaluate(case, state)["correct"]
    state.proof_counter = next(a["id"] for a in case["proof"]["alternatives"] if not a.get("correct"))
    assert not deduction.proof_evaluate(case, state)["correct"]
    state.proof_counter = next(a["id"] for a in case["proof"]["alternatives"] if a.get("correct"))
    state.alibi_solved = False
    assert not deduction.proof_evaluate(case, state)["correct"]


@pytest.mark.parametrize("case_id", EXPERT_CASES)
def test_expert_ending_fails_without_chain_but_classic_unchanged(case_id):
    case, state = _state(case_id)
    state.accusation_result = _culprit(case)
    answers = trial.answers(case, state.accusation_result)
    state.trial_motive = answers["motive"]
    state.trial_method = answers["method"]
    assert not endings.resolve(case, state)["success"]
    _solve_proof(case, state)
    assert endings.resolve(case, state)["success"]
    state.difficulty = "classic"
    assert endings.resolve(case, state)["success"]


def test_proof_rejects_unconfirmed_hearsay():
    case, state = _state("bank_heist")
    state.confirmed_clues = set()
    assert not deduction.proof_select(case, state, "presence", "clue_coffee")


def test_expert_search_has_no_countdown_or_patrol():
    case, state = _state("last_signal")
    session = search.Search(case, "radio", state)
    assert session.relaxed
    assert not session.patrol_on
    before = session.remaining
    session.update(30)
    assert session.remaining == before
    assert not session.expired


def test_new_cases_are_complete_and_reachable():
    for case_id in ("last_signal", "silent_archive"):
        case = load_case(case_id)
        assert case["is_new"]
        assert len(case["locations"]) >= 7
        assert len(case["clues"]) >= 10
        assert len(case["suspects"]) == 3
        locs = {l["id"] for l in case["locations"]}
        reachable = {l["id"] for l in case["locations"] if l.get("initial")}
        changed = True
        while changed:
            changed = False
            for clue in case["clues"]:
                if clue["location"] in reachable:
                    for target in clue.get("leads_to", []):
                        assert target in locs
                        if target not in reachable:
                            reachable.add(target)
                            changed = True
        assert reachable == locs
        for slot, accepted in case["proof"]["slots"].items():
            assert accepted
            assert all(get_clue(case, cid) for cid in accepted)
        for cid in case["proof"]["board"][_culprit(case)]:
            assert get_clue(case, cid)


@pytest.fixture(scope="module")
def game():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game
    obj = Game()
    obj.notifications.clear()
    yield obj
    pygame.quit()


def test_expert_screens_draw_and_start_resets(game):
    game.start_case("last_signal", difficulty="expert")
    assert game.state.difficulty == "expert"
    assert game.state.board_draft == set()
    game.state.collected_clues = {c["id"] for c in game.current_case["clues"]}
    game.screen_name = "notebook"
    game.notebook_tab = "board"
    game.draw()
    assert "review" in game.board_rects
    game.screen_name = "alibi"
    game.draw()
    assert game.alibi_rects["cells"]
    game.accusation_selected = _culprit(game.current_case)
    game.screen_name = "proof"
    game.draw()
    assert game.proof_rects["slots"]
    game.screen_name = "case_select"
    game.case_index = 3
    game.draw()
    assert game.case_select_rects["start"]
