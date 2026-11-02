"""Регрессии аудита 0.1.39: критичные баги, найденные при проверке игры.

Каждый тест здесь — про конкретную поломку, которая уже случалась:

* экран показаний не листался и не давал выбрать реплику;
* «назад» из показаний уводил на несуществующий экран;
* при смене подозреваемого оставались ответы суда от прошлого;
* просрочка закрывала дело generic-концовкой и плодила концовки в коллекции;
* «Безупречное дело» выдавалось с неверным мотивом и способом.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import data, endings, pressure, search, testimony, trial  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402
from detective_game.ui import search_view, testimony_view  # noqa: E402


@pytest.fixture(scope="module")
def game():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    obj = Game()
    obj.notifications.clear()
    yield obj
    pygame.quit()


def _setup(game, case_id="missing_chess", heard=True):
    case = data.load_case(case_id)
    game.current_case = case
    game.state = GameState()
    game.state.current_case_id = case_id
    game.state.case_state = "in_progress"
    game.state.collected_clues = {c["id"] for c in case["clues"]}
    game.state.reputation = 5
    game.state.money = 600
    if heard:
        game.state.asked_topics = {
            f"{ch['id']}:{i}"
            for ch in case["characters"]
            for i in range(len(ch.get("dialogue", [])))
        }
    game.accusation_selected = None
    game.testimony_selected = []
    game.testimony_scroll = 0
    game.testimony_message = ""
    game.notifications.clear()
    return case


# ── экран сопоставления показаний ────────────────────────────────────


def test_testimony_row_click_survives_next_draw(game, monkeypatch):
    """Клик по реплике не должен отменяться при следующей отрисовке."""
    _setup(game)
    game.screen_name = "testimony"
    game.draw()
    rect = next(iter(game.testimony_rects["rows"].values()))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert len(game.testimony_selected) == 1
    game.draw()
    assert len(game.testimony_selected) == 1
    assert game.testimony_selected[0] in game.testimony_rects["rows"]


def test_testimony_back_returns_to_notebook(game):
    _setup(game)
    game.screen_name = "testimony"
    game.draw()
    testimony_view.handle_testimony_click(game, game.testimony_rects["back"].center)
    assert game.screen_name == "notebook"
    assert game.notebook_tab == "board"


def test_testimony_list_scrolls_to_every_statement(game):
    """Раньше было видно только 6 из 36 реплик — противоречия были недостижимы."""
    case = _setup(game)
    game.screen_name = "testimony"
    game.draw()
    assert len(game.testimony_rects["rows"]) == testimony_view.MAX_ROWS
    seen = set(game.testimony_rects["rows"])
    while game.testimony_rects.get("down"):
        testimony_view.handle_testimony_click(game, game.testimony_rects["down"].center)
        game.draw()
        seen |= set(game.testimony_rects["rows"])
    assert len(seen) == len(testimony.statements(case, game.state))
    for item in case["contradictions"]:
        assert item["a"] in seen and item["b"] in seen


def test_testimony_wheel_and_keys_scroll(game):
    _setup(game)
    game.screen_name = "testimony"
    game.draw()
    assert testimony_view.handle_testimony_scroll(game, 3) is True
    assert game.testimony_scroll > 0
    testimony_view.scroll(game, -10**6)
    assert game.testimony_scroll == 0
    testimony_view.handle_testimony_key(
        game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PAGEDOWN, unicode="")
    )
    assert game.testimony_scroll == testimony_view.MAX_ROWS


# ── ответы суда привязаны к подозреваемому ───────────────────────────


def test_switching_suspect_resets_trial_answers(game, monkeypatch):
    case = _setup(game)
    game.screen_name = "accusation"
    game.accusation_selected = "finch"
    game.state.trial_motive = "collection"
    game.state.trial_method = "frame"
    main = pygame.Rect(20, 75, 1280 - 40, 720 - 95)
    second_card = pygame.Rect(main.x + 20, main.y + 62 + 102, main.w - 40, 96)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: second_card.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    game.draw()
    game.accusation_selected = "father"
    assert trial.available(case)
    # ответов от прошлого подозреваемого больше нет — суд снова ждёт
    assert game.state.trial_motive is None
    assert game.state.trial_method is None
    assert trial.ready(case, game.state) is False


# ── просрочка ────────────────────────────────────────────────────────


def test_late_case_gets_late_ending_and_is_not_recorded(game):
    case = _setup(game)
    game.state.case_time_minutes = pressure.deadline_minutes(case)
    game.state.accusation_result = None
    game.accusation_selected = None
    game._finish_case()
    resolution = endings.resolve(case, game.state)
    assert resolution["title"] == "Опоздал"
    assert resolution["success"] is False
    assert resolution["rank"] == "F"
    assert game.screen_name == "ending"
    assert endings.unlocked_for(game.state, case["id"]) == []
    opened, total = endings.progress(game.state, case)
    assert opened <= total


# ── «Безупречное дело» требует верного суда ──────────────────────────


def _perfect_state(case, correct_trial=True):
    state = GameState()
    state.collected_clues = {c["id"] for c in case["clues"]}
    for clue in case["clues"]:
        if clue.get("reliability") and clue["reliability"] != "planted":
            state.confirmed_clues.add(clue["id"])
    culprit = next(s["id"] for s in case["suspects"] if s.get("is_culprit"))
    state.accusation_result = culprit
    state.deductions = {item["id"] for item in case["contradictions"]}
    answers = trial.answers(case, culprit)
    if correct_trial:
        state.trial_motive = answers["motive"]
        state.trial_method = answers["method"]
    else:
        state.trial_motive = next(
            m["id"] for m in trial.motives(case) if m["id"] != answers["motive"]
        )
        state.trial_method = next(
            m["id"] for m in trial.methods(case) if m["id"] != answers["method"]
        )
    return state


def test_perfect_ending_needs_correct_court_answers():
    for case_id in ("missing_chess", "bank_heist"):
        case = data.load_case(case_id)
        good = endings.resolve(case, _perfect_state(case))
        assert good["variant"] == "deduction_perfect"
        assert good["rank"] == "S+"
        bad = endings.resolve(case, _perfect_state(case, correct_trial=False))
        assert bad["variant"] != "deduction_perfect"
        assert bad["rank"] != "S+"


# ── обыск и патруль ──────────────────────────────────────────────────


def test_patrol_catch_costs_pressure_minutes(game):
    case = _setup(game)
    game.location_id = "warehouse"
    game.screen_name = "location"
    game.search = search.Search(case, "warehouse", game.state)
    game.search.caught = True
    before = game.state.case_time_minutes
    game.update((640, 360), False)
    assert game.search is None
    assert game.state.case_time_minutes == before + pressure.PATROL_CAUGHT_MINUTES


def test_patrol_spot_shows_warning_not_search_hint(game, monkeypatch):
    """Подсказка на точке в секторе патруля не должна звать кликать."""
    case = _setup(game)
    game.location_id = "warehouse"
    game.screen_name = "location"
    session = search.Search(case, "warehouse", game.state)
    spot = session.spots[0]
    col = 0 if spot["x"] < 0.5 else 1
    row = 0 if spot["y"] < 0.5 else 1
    session.elapsed = (row * 2 + col) * search.PATROL_CYCLE  # сектор над точкой
    game.search = session
    game.draw()
    visual = game.search_rects["visual"]
    pos = (int(visual.x + spot["x"] * visual.w), int(visual.y + spot["y"] * visual.h))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    game.draw()
    assert session.in_patrol(spot["x"], spot["y"])
    # клик по такой точке прерывает обыск — это и есть предупреждение
    search_view.handle_click(game, pos)
    assert session.caught is True


def test_fake_clue_draws_without_crash(game):
    case = _setup(game)
    fake_id = next(c["id"] for c in case["clues"] if c.get("reliability") == "planted")
    game.state.fake_clues = {fake_id}
    game.state.collected_clues.discard(fake_id)
    game.screen_name = "notebook"
    game.notebook_tab = "clues"
    game.draw()
    assert fake_id not in game.state.collected_clues


# ── анонимные звонки ─────────────────────────────────────────────────


def test_anonymous_calls_do_not_chain_after_time_jump():
    """Прыжок во времени не должен выдавать второй звонок сразу после первого."""
    case = data.load_case("missing_chess")
    state = GameState()
    state.calls_seen = 2
    state.last_call_minute = 500
    state.case_time_minutes = 505  # порог 2-го звонка давно позади
    assert pressure.call_due(state, case) == 0
    state.case_time_minutes = 500 + pressure.CALL_EVERY_MINUTES
    assert pressure.call_due(state, case) == 3


def test_anonymous_calls_stop_after_max():
    case = data.load_case("missing_chess")
    state = GameState()
    state.calls_seen = pressure.MAX_CALLS
    state.case_time_minutes = 10**6
    assert pressure.call_due(state, case) == 0
