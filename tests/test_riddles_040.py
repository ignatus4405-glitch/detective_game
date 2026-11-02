"""Загадки-кодовые замки и подвижный патруль (0.1.40).

Кодовый замок — не реакция и не память: код выводится из фактов в тексте
загадки. Здесь проверяем и правила (штрафы, подсказка, сохранение), и что
кнопка «КОД» доводит до улики.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import riddle, search  # noqa: E402
from detective_game.data import load_case  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402


@pytest.fixture(scope="module")
def game():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    obj = Game()
    obj.notifications.clear()
    yield obj
    pygame.quit()


def _setup(game, case_id="missing_chess", clues=None):
    case = load_case(case_id)
    game.current_case = case
    game.state = GameState()
    game.state.current_case_id = case_id
    game.state.case_state = "in_progress"
    game.state.collected_clues = set(clues or [])
    game.location_id = "apartment_morozov"
    game.screen_name = "location"
    game.notifications.clear()
    return case


def _press(game, monkeypatch, pos):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)


def _type(game, text):
    for ch in str(text):
        game.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        )


# ── правила кодового замка ──────────────────────────────────────────


def test_tutorial_has_no_riddles():
    """Туториал остаётся простым: замков в нём нет."""
    case = load_case("tutorial")
    assert all(riddle.spec(case, clue) is None for clue in case["clues"])


def test_riddle_spec_ignored_without_advanced_flag():
    case = load_case("missing_chess")
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    assert riddle.spec(case, clue) is not None
    plain = dict(case, advanced=False)
    assert riddle.spec(plain, clue) is None


def test_every_riddle_is_solvable_and_documented():
    for case_id in ("missing_chess", "bank_heist"):
        case = load_case(case_id)
        found = 0
        for clue in case["clues"]:
            item = riddle.spec(case, clue)
            if not item:
                continue
            found += 1
            assert 1 <= len(item["answer"]) <= riddle.MAX_DIGITS
            assert item["answer"].isdigit()
            assert len(item["prompt"]) > 40
            assert item["hint"], clue["id"]
            assert item["minutes"] > 0
        assert found >= 3, case_id


def test_normalize_keeps_digits_only():
    assert riddle.normalize("15:00") == "1500"
    assert riddle.normalize(" 1 7-3 5 ") == "1735"
    assert riddle.normalize("") == ""


def test_wrong_code_costs_minutes_and_keeps_lock():
    case = load_case("missing_chess")
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    item = riddle.spec(case, clue)
    state = GameState()
    before = state.case_time_minutes
    result = riddle.check(state, item, "1234")
    assert result["status"] == "wrong"
    assert state.case_time_minutes == before + item["minutes"]
    assert riddle.solved(state, item) is False


def test_hint_costs_two_minutes_and_returns_text():
    case = load_case("missing_chess")
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    item = riddle.spec(case, clue)
    state = GameState()
    before = state.case_time_minutes
    result = riddle.hint(state, item)
    assert result["status"] == "ok"
    assert result["text"] == item["hint"]
    assert state.case_time_minutes == before + riddle.HINT_MINUTES


def test_hint_without_text_is_free():
    state = GameState()
    before = state.case_time_minutes
    assert riddle.hint(state, {"id": "x", "answer": "1", "hint": ""})["status"] == "none"
    assert state.case_time_minutes == before


def test_right_code_solves_and_survives_save_roundtrip():
    case = load_case("missing_chess")
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    item = riddle.spec(case, clue)
    state = GameState()
    assert riddle.check(state, item, "1500")["status"] == "ok"
    assert riddle.solved(state, item) is True
    # «15:00» в поле ввода — тот же код
    assert riddle.normalize("15:00") == item["answer"]
    restored = GameState.from_dict(state.to_dict())
    assert riddle.solved(restored, item) is True
    # повторная проверка не штрафует
    before = restored.case_time_minutes
    assert riddle.check(restored, item, "0000")["status"] == "solved"
    assert restored.case_time_minutes == before


def test_empty_input_is_short_and_free():
    case = load_case("missing_chess")
    clue = next(c for c in case["clues"] if c["id"] == "clue_ticket")
    item = riddle.spec(case, clue)
    state = GameState()
    before = state.case_time_minutes
    assert riddle.check(state, item, "")["status"] == "short"
    assert state.case_time_minutes == before


# ── экран и кнопка «КОД» ────────────────────────────────────────────


def test_code_button_opens_lock_then_collects_clue(game, monkeypatch):
    _setup(game)
    game.draw()
    button = game.location_clue_buttons["clue_diary"]
    assert button
    _press(game, monkeypatch, button.center)
    game.draw()
    assert game.screen_name == "riddle"
    assert game.riddle["answer"] == "1500"

    game.draw()
    assert len(game.riddle_rects["digits"]) == len("1500")

    # неверный код — остаёмся у замка и платим минутами
    before = game.state.case_time_minutes
    _type(game, "1234")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert game.screen_name == "riddle"
    assert game.state.case_time_minutes == before + 3
    assert game.state.collected_clues == set()

    # подсказка
    game.draw()
    _press(game, monkeypatch, game.riddle_rects["hint"].center)
    game.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=game.riddle_rects["hint"].center)
    )
    assert game.riddle_hint

    # верный код открывает улику
    _type(game, "1500")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert "clue_diary" in game.state.collected_clues
    game.draw()
    assert game.screen_name == "location"
    game.draw()
    assert "clue_diary" not in game.location_clue_buttons  # улика уже изучена


def test_numpad_and_unicode_digits_are_accepted(game):
    case = _setup(game)
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    game.open_riddle(clue)
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_KP1, unicode="1"))
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_KP5, unicode="5"))
    assert game.riddle_input == "15"
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="\x08"))
    assert game.riddle_input == "1"


def test_leaving_riddle_returns_to_location(game, monkeypatch):
    case = _setup(game)
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    game.open_riddle(clue)
    assert game.screen_name == "riddle"
    game.draw()
    back = game.riddle_rects["back"]
    _press(game, monkeypatch, back.center)
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=back.center))
    assert game.screen_name == "location"
    assert "clue_diary" not in game.state.collected_clues


def test_every_case_riddle_opens_its_clue(game):
    """Каждая загадка в данных действительно открывает свою улику."""
    for case_id in ("missing_chess", "bank_heist"):
        case = load_case(case_id)
        for clue in case["clues"]:
            item = riddle.spec(case, clue)
            if not item:
                continue
            _setup(game, case_id=case_id)
            game.open_riddle(clue)
            assert game.screen_name == "riddle", clue["id"]
            _type(game, item["answer"])
            game.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
            )
            assert clue["id"] in game.state.collected_clues, clue["id"]
            assert game.screen_name == "location", clue["id"]


def test_riddle_then_puzzle_chain(game):
    """Замок и головоломка на одной улике идут по цепочке."""
    case = load_case("missing_chess")
    base = next(c for c in case["clues"] if c["id"] == "clue_diary")
    clue = dict(base, puzzle={"type": "sequence", "difficulty": 1, "title": "ТЕСТ"})
    game.current_case = dict(case, clues=[clue] + [c for c in case["clues"] if c["id"] != "clue_diary"])
    game.state = GameState()
    game.state.case_state = "in_progress"
    game.location_id = "apartment_morozov"
    game.open_riddle(clue)
    _type(game, "1500")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert game.screen_name == "puzzle"
    assert game.puzzle_clue is clue
    game.close_puzzle()


def test_keypad_buttons_type_digits(game, monkeypatch):
    case = _setup(game)
    clue = next(c for c in case["clues"] if c["id"] == "clue_diary")
    game.open_riddle(clue)
    game.draw()
    for digit in "150":
        _press(game, monkeypatch, game.riddle_rects["keys"][digit].center)
        game.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=game.riddle_rects["keys"][digit].center
            )
        )
    assert game.riddle_input == "150"
    clear = game.riddle_rects["keys"]["C"]
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=clear.center))
    assert game.riddle_input == "15"


def test_riddle_tip_is_shown_once(game):
    _setup(game)
    game._maybe_riddle_tip("apartment_morozov")
    texts = [text for text, _ in game.notifications]
    assert any("КОД" in text for text in texts)
    assert game.state.riddle_tip_shown is True
    game.notifications.clear()
    game._maybe_riddle_tip("apartment_morozov")
    assert game.notifications == []


def test_no_tip_for_plain_location(game):
    _setup(game)
    game._maybe_riddle_tip("office")
    assert game.state.riddle_tip_shown is False
    assert game.notifications == []


# ── подвижный патруль ───────────────────────────────────────────────


def _search(game, case):
    session = search.Search(case, "warehouse", game.state)
    game.location_id = "warehouse"
    game.screen_name = "location"
    game.search = session
    return session


def test_patrol_route_covers_every_cell_once():
    case = load_case("missing_chess")
    session = search.Search(case, "warehouse", GameState())
    cells = search.PATROL_COLS * search.PATROL_ROWS
    assert len(session.patrol_route) == cells
    assert len(set(session.patrol_route)) == cells
    # «змейка»: соседние сектора всегда рядом
    for index in range(cells):
        current = session.patrol_route[index]
        nxt = session.patrol_route[(index + 1) % cells]
        assert abs(current[0] - nxt[0]) + abs(current[1] - nxt[1]) == 1


def test_patrol_moves_with_search_time():
    case = load_case("missing_chess")
    session = search.Search(case, "warehouse", GameState())
    start = session.patrol_cell()
    session.update(search.PATROL_STEP)
    assert session.patrol_cell() != start
    session.update(search.PATROL_STEP)
    assert session.patrol_moves == 2


def test_patrol_countdown_and_alert():
    case = load_case("missing_chess")
    session = search.Search(case, "warehouse", GameState())
    assert session.patrol_seconds_left() == pytest.approx(search.PATROL_STEP, abs=0.01)
    assert session.patrol_alert is False
    session.update(search.PATROL_STEP - 1.0)
    assert session.patrol_seconds_left() == pytest.approx(1.0, abs=0.01)
    assert session.patrol_alert is True


def test_patrol_speeds_up_at_the_end():
    case = load_case("missing_chess")
    session = search.Search(case, "warehouse", GameState())
    assert session.patrol_step_seconds() == pytest.approx(search.PATROL_STEP)
    session.remaining = session.seconds * 0.2
    assert session.patrol_step_seconds() < search.PATROL_STEP
    assert session.patrol_step_seconds() >= search.PATROL_MIN_STEP


def test_patrol_next_cell_is_drawn_and_click_into_zone_is_caught(game):
    case = _setup(game)
    session = _search(game, case)
    game.draw()
    visual = game.search_rects["visual"]
    nxt = session.patrol_next_cell()
    x = (nxt[0] + 0.5) / search.PATROL_COLS
    y = (nxt[1] + 0.5) / search.PATROL_ROWS
    # в следующий сектор кликать пока безопасно, в активный — нельзя
    from detective_game.ui import search_view

    assert session.in_patrol(x, y) is False
    active = session.patrol_rect()
    pos = (
        int(visual.x + (active[0] + active[2] / 2) * visual.w),
        int(visual.y + (active[1] + active[3] / 2) * visual.h),
    )
    search_view.handle_click(game, pos)
    assert session.caught is True


def test_patrol_edge_click_is_forgiven():
    """Клик на самой кромке красного сектора обыск не прерывает."""
    case = load_case("missing_chess")
    session = search.Search(case, "warehouse", GameState())
    cell = session.patrol_cell()
    x = cell[0] / search.PATROL_COLS + 0.002
    y = cell[1] / search.PATROL_ROWS + 0.002
    assert session.in_patrol(x, y) is True
    assert session.caught_by_click(x, y) is False
    centre_x = (cell[0] + 0.5) / search.PATROL_COLS
    centre_y = (cell[1] + 0.5) / search.PATROL_ROWS
    assert session.caught_by_click(centre_x, centre_y) is True


def test_patrol_off_in_simple_cases():
    case = load_case("tutorial")
    session = search.Search(case, "park", GameState())
    assert session.patrol_on is False
    assert session.in_patrol(0.1, 0.1) is False
    session.update(30.0)
    assert session.patrol_moves == 0
