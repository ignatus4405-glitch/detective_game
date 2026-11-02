"""Тесты головоломок: логика, данные дел и интеграция с игрой."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import puzzles  # noqa: E402
from detective_game.data import BUILTIN_CASES, get_clue  # noqa: E402
from detective_game.puzzles import Puzzle, difficulty_label, for_clue  # noqa: E402

CASES = {case["id"]: case for case in BUILTIN_CASES}
PUZZLED_CLUES = [
    (case["id"], clue["id"], clue["puzzle"])
    for case in BUILTIN_CASES
    for clue in case["clues"]
    if clue.get("puzzle")
]


# ---------------------------------------------------------------------------
# Кодовый замок
# ---------------------------------------------------------------------------


def test_safe_accepts_code_from_data_and_hints():
    pz = Puzzle({"type": "safe", "code": "2016"})
    assert pz.code == [2, 0, 1, 6]
    for digit in pz.code:
        pz.press_digit(digit)
    feedback = pz.submit_code()
    assert pz.success
    assert feedback is not None
    assert all(item.correct for item in feedback)


def test_safe_wrong_code_gives_marks_and_spends_attempt():
    pz = Puzzle({"type": "safe", "code": "5555", "attempts": 2})
    for digit in (1, 2, 3, 4):
        pz.press_digit(digit)
    feedback = pz.submit_code()
    assert feedback is not None
    assert not pz.success
    assert pz.attempts_left == 1
    marks = {item.mark for item in feedback}
    assert marks <= {"=", "↑", "↓"}
    # 1 < 5 — подсказка «больше», 4 < 5 — тоже
    assert [item.mark for item in feedback] == ["↑", "↑", "↑", "↑"]


def test_safe_runs_out_of_attempts():
    pz = Puzzle({"type": "safe", "code": "0000", "attempts": 1})
    for digit in (9, 9, 9, 9):
        pz.press_digit(digit)
    pz.submit_code()
    assert pz.failed
    assert not pz.success
    # ввод после провала игнорируется
    pz.press_digit(0)
    assert pz.entry == []


def test_safe_backspace_and_digit_limit():
    pz = Puzzle({"type": "safe", "code": "1234"})
    for digit in (1, 2, 3, 4, 5, 6):
        pz.press_digit(digit)
    assert pz.entry == [1, 2, 3, 4]
    pz.backspace()
    assert pz.entry == [1, 2, 3]


# ---------------------------------------------------------------------------
# Отмычки
# ---------------------------------------------------------------------------


def test_lockpick_three_hits_open_the_lock():
    pz = Puzzle({"type": "lockpick", "difficulty": 1})
    for target in pz.targets:
        pz.cursor = target
        assert pz.strike() is True
    assert pz.success
    assert pz.hits == 3


def test_lockpick_misses_and_failure():
    pz = Puzzle({"type": "lockpick", "difficulty": 1, "attempts": 2})
    pz.cursor = 0.0
    assert pz.strike() is False
    pz.cursor = 0.0
    pz.strike()
    assert pz.failed


def test_lockpick_cursor_moves_and_bounces():
    pz = Puzzle({"type": "lockpick", "difficulty": 1})
    pz.update(0.2)
    assert pz.cursor > 0
    pz.cursor, pz.direction = 0.999, 1
    pz.update(0.2)
    assert 0.0 <= pz.cursor <= 1.0
    assert pz.direction == -1


# ---------------------------------------------------------------------------
# Провода
# ---------------------------------------------------------------------------


def test_wires_have_single_answer():
    for seed in range(60):
        pz = Puzzle({"type": "wires", "difficulty": 2}, seed=f"seed-{seed}")
        matching = [i for i, _ in enumerate(pz.wires) if _wire_matches(pz, i)]
        assert matching == [pz.correct_wire], (seed, pz.constraints)


def _wire_matches(pz, index):
    names = [name for name, _, _ in puzzles.WIRE_COLORS]
    genitive = {gen: i for i, (_, gen, _) in enumerate(puzzles.WIRE_COLORS)}
    for text in pz.constraints:
        if text.startswith("Это не "):
            if names[index] == text[len("Это не "):].replace(" провод.", ""):
                return False
        elif " левее " in text:
            other = genitive[text.split(" левее ")[1].rstrip(".")]
            if not index < other:
                return False
        elif " правее " in text:
            other = genitive[text.split(" правее ")[1].rstrip(".")]
            if not index > other:
                return False
    return True


def test_wires_wrong_cut_spends_attempt():
    pz = Puzzle({"type": "wires", "difficulty": 1, "attempts": 2})
    wrong = (pz.correct_wire + 1) % len(pz.wires)
    assert pz.cut(wrong) is False
    assert pz.attempts_left == 1
    assert not pz.finished
    assert pz.cut(pz.correct_wire) is True
    assert pz.success


def test_wires_two_mistakes_fail():
    pz = Puzzle({"type": "wires", "difficulty": 1, "attempts": 2})
    for _ in range(2):
        pz.cut((pz.correct_wire + 1) % len(pz.wires))
    assert pz.failed


# ---------------------------------------------------------------------------
# Последовательность
# ---------------------------------------------------------------------------


def test_sequence_replay():
    pz = Puzzle({"type": "sequence", "difficulty": 2}, seed="seq")
    pz.update(99)  # досмотреть показ
    pz.showing = False
    for name in pz.order:
        assert pz.tap(name) is True
    assert pz.success


def test_sequence_wrong_shape_spends_attempt():
    pz = Puzzle({"type": "sequence", "difficulty": 1, "attempts": 2}, seed="seq2")
    pz.showing = False
    wrong = next(name for name in puzzles.SHAPES if name != pz.order[0])
    assert pz.tap(wrong) is False
    assert pz.attempts_left == 1
    assert pz.input == []


def test_sequence_cannot_click_while_showing():
    pz = Puzzle({"type": "sequence", "difficulty": 1}, seed="seq3")
    assert pz.showing
    assert pz.tap(pz.order[0]) is None


# ---------------------------------------------------------------------------
# Данные дел
# ---------------------------------------------------------------------------


def test_every_case_has_interactive_clues():
    by_case = {}
    for case_id, _, spec in PUZZLED_CLUES:
        by_case.setdefault(case_id, []).append(spec)
    assert set(by_case) == set(CASES), "в каждом деле должна быть хотя бы одна головоломка"
    for case_id, specs in by_case.items():
        kinds = {spec["type"] for spec in specs}
        assert len(specs) >= 2, case_id
        assert len(kinds) >= 2, f"{case_id}: нужны разные типы головоломок, а не только {kinds}"


def test_puzzle_specs_are_renderable():
    for case_id, clue_id, spec in PUZZLED_CLUES:
        clue = get_clue(CASES[case_id], clue_id)
        assert spec["type"] in puzzles.DEFAULT_TITLES
        assert spec.get("hint"), f"{clue_id}: без подсказки игрок застрянет"
        assert spec.get("reward"), f"{clue_id}: без награды непонятно, зачем взламывать"
        pz = Puzzle(spec, seed=clue["id"])
        assert pz.title and pz.hint
        assert pz.progress_text
        if spec["type"] == "safe":
            assert len(pz.code) == 4


def test_difficulty_label():
    assert difficulty_label(Puzzle({"type": "safe", "difficulty": 1})) == "★☆☆"
    assert difficulty_label(Puzzle({"type": "safe", "difficulty": 3})) == "★★★"


def test_for_clue_returns_puzzle_or_none():
    pz = for_clue({"id": "x", "puzzle": {"type": "wires"}})
    assert pz is not None and pz.kind == "wires"
    assert for_clue({"puzzle": None}) is None
    assert for_clue({}) is None


# ---------------------------------------------------------------------------
# Интеграция с игрой
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def game():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    g = Game()
    g.notifications.clear()
    g.current_case = CASES["missing_chess"]
    yield g
    pygame.quit()


@pytest.mark.parametrize("case_id,clue_id,spec", PUZZLED_CLUES)
def test_open_and_solve_every_clue(game, case_id, clue_id, spec):
    case = CASES[case_id]
    clue = get_clue(case, clue_id)
    game.current_case = case
    game.state.collected_clues.discard(clue_id)
    game.screen_name = "location"
    game.open_puzzle(clue)
    assert game.screen_name == "puzzle"
    game.draw()
    assert game.puzzle_rects.get("body")
    assert "cancel" in game.puzzle_rects

    pz = game.puzzle
    if pz.kind == "safe":
        pz.entry = list(pz.code)
        game.submit_puzzle_code()
    elif pz.kind == "lockpick":
        for target in pz.targets:
            pz.cursor = target
            game.strike_lockpick()
    elif pz.kind == "wires":
        game.cut_wire(pz.correct_wire)
    elif pz.kind == "alibi":
        for person, place in enumerate(pz.solution):
            game.assign_puzzle_alibi(person, place)
        game.submit_puzzle_grid()
    elif pz.kind == "develop":
        for name, target in pz.targets_dev.items():
            game.adjust_puzzle_param(name, target - pz.params[name])
        game.submit_puzzle_develop()
    elif pz.kind == "align":
        for target in pz.angle_targets:
            pz.angle = target
            game.strike_puzzle_align()
    else:
        pz.showing = False
        for name in pz.order:
            game.tap_shape(name)

    assert pz.success
    game.draw()  # экран победы с кнопкой «ПРОДОЛЖИТЬ»
    assert "continue" in game.puzzle_rects
    game.finish_puzzle_flow()
    assert clue_id in game.state.collected_clues
    assert game.screen_name == "location"
    assert game.puzzle is None


def test_failed_puzzle_costs_time_but_can_be_retried(game):
    clue = get_clue(CASES["missing_chess"], "clue_camera")
    game.current_case = CASES["missing_chess"]
    game.state.collected_clues.discard(clue["id"])
    game.open_puzzle(clue)
    game.puzzle.failed = True
    minutes = game.state.case_time_minutes
    game.finish_puzzle_flow()
    assert game.state.case_time_minutes == minutes + 15
    assert clue["id"] not in game.state.collected_clues
    assert game.screen_name == "location"


def test_clue_without_puzzle_is_collected_directly(game):
    clue = get_clue(CASES["missing_chess"], "clue_blood_scarf")
    game.state.collected_clues.discard(clue["id"])
    game.screen_name = "location"
    game.open_puzzle(clue)
    assert clue["id"] in game.state.collected_clues
    assert game.screen_name == "location"


# ---------------------------------------------------------------------------
# Новые типы: сетка алиби, проявка, совмещение
# ---------------------------------------------------------------------------


def test_alibi_grid_assigns_and_enforces_unique_places():
    pz = Puzzle({"type": "alibi", "people": ["А", "Б", "В"], "places": ["1", "2", "3"]})
    assert pz.kind == "alibi"
    assert len(pz.people) == len(pz.places) == 3
    assert pz.assign(0, 0) and pz.assignments[0] == 0
    # место занято другим — прежний освобождается
    pz.assign(1, 0)
    assert pz.assignments[0] is None
    assert pz.assignments[1] == 0
    pz.clear_row(1)
    assert pz.assignments[1] is None


def test_alibi_facts_define_unique_solution():
    pz = Puzzle({"type": "alibi", "difficulty": 1})
    assert pz.facts
    assert all("—" in fact for fact in pz.facts)
    assert len(pz.facts) >= len(pz.people)


def test_alibi_requires_full_grid_and_accepts_solution():
    pz = Puzzle({"type": "alibi", "people": ["А", "Б", "В"], "places": ["1", "2", "3"]})
    pz.assign(0, pz.solution[0])
    assert pz.submit_grid() is False
    assert "Заполните всех" in pz.message
    for person, place in enumerate(pz.solution):
        pz.assign(person, place)
    assert pz.submit_grid() is True
    assert pz.success


def test_alibi_wrong_grid_costs_attempt():
    pz = Puzzle({"type": "alibi", "people": ["А", "Б"], "places": ["1", "2"], "attempts": 2})
    wrong = [1, 0]
    for person, place in enumerate(wrong):
        pz.assign(person, place)
    assert pz.submit_grid() is False
    assert pz.attempts_left == 1
    assert all(item is None for item in pz.assignments)


def test_develop_feedback_and_success():
    pz = Puzzle({"type": "develop", "difficulty": 1, "targets": {"exposure": 50, "contrast": 30, "time": 70}})
    feedback = pz.submit_develop()
    assert set(feedback) == {"exposure", "contrast", "time"}
    assert all(mark in {"=", "↑", "↓"} for mark in feedback.values())
    assert not pz.success
    for name, target in pz.targets_dev.items():
        pz.adjust(name, target - pz.params[name])
    feedback = pz.submit_develop()
    assert set(feedback.values()) == {"="}
    assert pz.success


def test_develop_clamps_and_ignores_unknown_params():
    pz = Puzzle({"type": "develop"})
    pz.adjust("exposure", 999)
    assert pz.params["exposure"] == 100
    pz.adjust("exposure", -999)
    assert pz.params["exposure"] == 0
    pz.adjust("nope", 10)
    assert "nope" not in pz.params


def test_align_hits_and_misses():
    pz = Puzzle({"type": "align", "difficulty": 1})
    assert len(pz.angle_targets) == 3
    for target in pz.angle_targets:
        pz.angle = target
        assert pz.strike_angle() is True
    assert pz.success
    assert pz.hits == 3


def test_align_three_misses_fail():
    pz = Puzzle({"type": "align", "difficulty": 3})
    pz.angle = (pz.angle_targets[0] + 0.5) % 1.0
    for _ in range(3):
        pz.strike_angle()
    assert pz.failed
    assert pz.misses == pz.attempts_total


def test_align_needle_moves_over_time():
    pz = Puzzle({"type": "align", "difficulty": 1})
    start = pz.angle
    for _ in range(10):
        pz.update(0.1)
    assert pz.angle != start


def test_new_puzzle_types_have_titles_and_hints():
    for kind in ("alibi", "develop", "align"):
        pz = Puzzle({"type": kind})
        assert pz.title
        assert pz.hint
        assert difficulty_label(pz)


def test_align_voice_mode_has_label():
    pz = Puzzle({"type": "align", "mode": "voice", "difficulty": 1})
    assert pz.align_mode == "voice"
    assert pz.title


def test_data_voice_clue_uses_align():
    case = CASES["missing_chess"]
    clue = get_clue(case, "clue_tape")
    assert clue and clue["hidden"]
    assert clue["puzzle"]["type"] == "align"
    assert clue["puzzle"]["mode"] == "voice"
