"""Тесты финалов: сколько улик нужно, варианты концовок, коллекция."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import endings  # noqa: E402
from detective_game.data import list_cases, load_case  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402


def _case(case_id):
    return load_case(case_id)


def _culprit(case):
    return next(s for s in case["suspects"] if s.get("is_culprit"))


def test_required_clues_never_exceed_available():
    for case in list_cases():
        need = endings.required_clues(case)
        total = len(case["clues"])
        assert 1 <= need <= total, f"{case['id']}: нужно {need} из {total}"


def test_tutorial_can_be_finished_with_its_two_clues():
    """Регрессия: в туториале всего 2 улики, а обвинение требовало 3."""
    case = _case("tutorial")
    assert endings.required_clues(case) == 2
    state = GameState()
    state.collected_clues = {"clue_paw", "clue_collar"}
    assert endings.can_accuse(state, case) is True


def test_accusation_opens_with_one_clue():
    case = _case("missing_chess")
    state = GameState()
    assert endings.can_accuse(state, case) is False
    assert "улику" in endings.clue_hint(state, case)
    state.collected_clues = {"clue_camera"}
    assert endings.can_accuse(state, case) is True
    assert "может развалиться" in endings.clue_hint(state, case)
    state.collected_clues |= set(clue["id"] for clue in case["clues"])
    assert "достаточно" in endings.clue_hint(state, case)


@pytest.mark.parametrize("case_id", ["tutorial", "missing_chess", "bank_heist"])
def test_every_case_can_be_finished(case_id):
    case = _case(case_id)
    culprit = _culprit(case)
    state = GameState()
    state.collected_clues = {clue["id"] for clue in case["clues"]}
    state.accusation_result = culprit["id"]
    resolution = endings.resolve(case, state)
    assert resolution["success"] is True
    assert resolution["title"] and resolution["text"]
    assert resolution["rank"]
    assert endings.record(state, case_id, resolution) is True
    assert endings.record(state, case_id, resolution) is False


@pytest.mark.parametrize("case_id", ["tutorial", "missing_chess", "bank_heist"])
def test_every_suspect_has_a_working_ending(case_id):
    case = _case(case_id)
    for suspect in case["suspects"]:
        state = GameState()
        state.accusation_result = suspect["id"]
        state.collected_clues = {clue["id"] for clue in case["clues"]}
        resolution = endings.resolve(case, state)
        assert resolution["title"]
        assert resolution["text"]
        assert resolution["rank"] != "?"
        assert resolution["success"] is bool(suspect.get("is_culprit"))


def test_unknown_suspect_falls_back_to_generic_ending():
    case = _case("tutorial")
    state = GameState()
    state.accusation_result = "nobody"
    resolution = endings.resolve(case, state)
    assert resolution["success"] is False
    assert resolution["text"]


def test_tutorial_perfect_ending_needs_all_clues_and_trust():
    case = _case("tutorial")
    state = GameState()
    state.accusation_result = "neighbor"
    state.collected_clues = {"clue_paw", "clue_collar"}

    # без доверия — базовая концовка
    assert endings.resolve(case, state)["variant"] == "base"

    # мягкий допрос + все улики — идеальный финал
    state.trust = {"mayor": 2, "smith": 1}
    perfect = endings.resolve(case, state)
    assert perfect["variant"] == "perfect"
    assert perfect["rank"] == "S+"
    assert perfect["label"] == "Идеальный финал"


def test_harsh_ending_for_negative_trust():
    case = _case("tutorial")
    state = GameState()
    state.accusation_result = "neighbor"
    state.collected_clues = {"clue_paw", "clue_collar"}
    state.trust = {"smith": -2}
    harsh = endings.resolve(case, state)
    assert harsh["variant"] == "harsh"
    assert harsh["rank"] == "B"


def test_thin_ending_with_few_clues():
    case = _case("missing_chess")
    state = GameState()
    state.accusation_result = "finch"
    state.collected_clues = {"clue_camera", "clue_chess_note", "clue_blood_scarf"}
    thin = endings.resolve(case, state)
    assert thin["variant"] == "thin"
    assert thin["success"] is True  # Артёма спасли, но Финч ушёл
    assert thin["rank"] == "C"


def test_max_time_condition():
    assert endings.matches({"max_time": 30}, GameState(), {}) is True
    slow = GameState()
    slow.case_time_minutes = 90
    assert endings.matches({"max_time": 30}, slow, {}) is False


def test_conditions_match_helper():
    case = load_case("tutorial")
    state = GameState()
    state.collected_clues = {"clue_paw"}
    state.trust = {"mayor": 1}
    assert endings.matches({"min_clues": 1}, state, case) is True
    assert endings.matches({"min_clues": 2}, state, case) is False
    assert endings.matches({"min_trust": 1}, state, case) is True
    assert endings.matches({"max_trust": 0}, state, case) is False
    assert endings.matches({"all_clues": True}, state, case) is False
    assert endings.matches({}, state, case) is True


def test_ending_collection_counts_and_persists():
    case = _case("tutorial")
    state = GameState()
    opened, total = endings.progress(state, case)
    assert opened == 0
    assert total == endings.total_endings(case) >= 5

    resolution = {
        "suspect_id": "neighbor",
        "variant": "perfect",
        "success": True,
        "title": "t",
        "text": "x",
        "rank": "S+",
        "label": "Идеальный финал",
    }
    endings.record(state, "tutorial", resolution)
    assert endings.progress(state, case) == (1, total)

    restored = GameState.from_dict(state.to_dict())
    assert endings.unlocked_for(restored, "tutorial") == endings.unlocked_for(state, "tutorial")


# ---------------------------------------------------------------------------
# Экран
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def game():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game.main import Game

    obj = Game()
    obj.notifications.clear()
    yield obj
    pygame.quit()


def test_map_button_allows_accusation_with_two_clues(game):
    game.current_case = _case("tutorial")
    game.state = GameState()
    game.state.collected_clues = {"clue_paw", "clue_collar"}
    game.screen_name = "map"
    game.draw()  # не падает и рисует доступную кнопку обвинения
    assert endings.can_accuse(game.state, game.current_case) is True


def test_finish_case_opens_ending_and_records(game):
    game.current_case = _case("tutorial")
    game.state = GameState()
    game.state.collected_clues = {"clue_paw", "clue_collar"}
    game.state.trust = {"mayor": 2}
    game.accusation_selected = "neighbor"

    game._finish_case()

    assert game.state.case_state == "finished"
    assert game.state.accusation_correct is True
    assert game.screen_name == "ending"
    assert endings.unlocked_for(game.state, "tutorial")
    assert game._ending_is_new is True

    game.draw()  # экран финала рисуется
    assert endings.resolve(game.current_case, game.state)["variant"] == "perfect"


def test_finish_case_wrong_suspect_is_not_success(game):
    game.current_case = _case("tutorial")
    game.state = GameState()
    game.state.collected_clues = {"clue_paw", "clue_collar"}
    game.accusation_selected = "mayor_sus"
    game._finish_case()
    assert game.state.accusation_correct is False
    assert endings.resolve(game.current_case, game.state)["success"] is False
    game.draw()


def test_start_case_resets_dialogue_but_keeps_endings(game):
    game.state.unlocked_endings = {"tutorial": ["tutorial:neighbor:base"]}
    game.state.trust = {"mayor": 3}
    game.state.dialogue_choices = {"mayor:0": 1}
    game.state.trust_bonus_taken = {"mayor"}

    game.start_case("tutorial")

    assert game.state.trust == {}
    assert game.state.dialogue_choices == {}
    assert game.state.trust_bonus_taken == set()
    assert game.state.unlocked_endings == {"tutorial": ["tutorial:neighbor:base"]}


def test_map_accuse_button_opens_accusation(game, monkeypatch):
    game.current_case = _case("tutorial")
    game.state = GameState()
    game.state.collected_clues = {"clue_paw"}
    game.screen_name = "map"
    game.location_id = "office"
    target = game._map_layout().btn_accuse.center
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: target)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)

    game.draw()

    # сначала предлагается восстановить хронологию — её можно пропустить
    assert game.screen_name == "timeline"
    game.draw()  # экран хронологии рисуется следующим кадром
    skip = game.timeline_rects["skip"].center
    game.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=skip)
    )
    assert game.screen_name == "accusation"
    assert game.accusation_selected is None


def test_confirm_button_opens_ending(game, monkeypatch):
    game.current_case = _case("tutorial")
    game.state = GameState()
    game.state.collected_clues = {"clue_paw", "clue_collar"}
    game.accusation_selected = "neighbor"
    game.screen_name = "accusation"
    main = pygame.Rect(20, 75, 1280 - 40, 720 - 95)
    target = (main.right - 200 + 90, main.bottom - 50 + 20)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: target)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)

    game.draw()

    assert game.screen_name == "ending"
    assert game.state.case_state == "finished"
    assert endings.unlocked_for(game.state, "tutorial")
