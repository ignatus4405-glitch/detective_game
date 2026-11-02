"""Тесты интерактивного допроса: выбор реплик, доверие, бонусы."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import dialogue  # noqa: E402
from detective_game.data import get_clue, list_cases, load_case  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402


def _char(case, char_id):
    return next(ch for ch in case["characters"] if ch["id"] == char_id)


def _lookup(case):
    return lambda clue_id: get_clue(case, clue_id)


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------


def test_case_topics_are_valid():
    """Каждая тема с выбором корректна, а все улики из реплик существуют."""
    for case in list_cases():
        clue_ids = {clue["id"] for clue in case["clues"]}
        for char in case["characters"]:
            for topic in char.get("dialogue", []):
                opts = topic.get("options")
                if not opts:
                    continue
                assert topic.get("prompt"), f"{case['id']}/{char['id']}: тема без prompt"
                assert 2 <= len(opts) <= dialogue.MAX_OPTIONS, (
                    f"{case['id']}/{char['id']}: {len(opts)} вариантов"
                )
                for option in opts:
                    assert option.get("text"), "вариант без текста реплики"
                    assert option.get("reply"), "вариант без ответа персонажа"
                    if option.get("clue"):
                        assert option["clue"] in clue_ids, (
                            f"{case['id']}/{char['id']}: нет улики {option['clue']}"
                        )
            bonus = char.get("trust_bonus")
            if bonus:
                assert bonus.get("text")
                if bonus.get("clue"):
                    assert bonus["clue"] in clue_ids


def test_every_case_has_interactive_topics():
    """В каждом деле есть хотя бы один персонаж с выбором реплик."""
    for case in list_cases():
        has_choice = any(
            topic.get("options")
            for char in case["characters"]
            for topic in char.get("dialogue", [])
        )
        assert has_choice, f"{case['id']}: нет интерактивных тем"


def test_options_are_limited():
    topic = {"options": [{"text": f"r{i}", "reply": "a"} for i in range(5)]}
    assert len(dialogue.options(topic)) == dialogue.MAX_OPTIONS
    assert dialogue.options(None) == []
    assert dialogue.options({"options": [{"reply": "без текста"}]}) == []
    assert dialogue.is_interactive(topic) is True
    assert dialogue.is_interactive({"q": "вопрос", "a": "ответ"}) is False


# ---------------------------------------------------------------------------
# Выбор реплики
# ---------------------------------------------------------------------------


def test_choose_records_trust_and_awards_clue():
    case = load_case("tutorial")
    mayor = _char(case, "mayor")
    state = GameState()

    result = dialogue.choose(state, mayor, 0, 1, _lookup(case))

    assert result is not None
    assert result["clue"]["id"] == "clue_paw"
    assert "clue_paw" in state.collected_clues
    assert state.case_time_minutes == 10
    assert dialogue.chosen(state, "mayor", 0) == 1
    assert dialogue.chosen_option(state, "mayor", 0, mayor["dialogue"][0])["text"]


def test_second_choice_in_same_topic_is_rejected():
    """Переиграть тему нельзя: выбор фиксируется в сохранении."""
    case = load_case("tutorial")
    mayor = _char(case, "mayor")
    state = GameState()
    assert dialogue.choose(state, mayor, 0, 0, _lookup(case)) is not None
    assert dialogue.choose(state, mayor, 0, 2, _lookup(case)) is None
    assert dialogue.chosen(state, "mayor", 0) == 0


def test_bad_indexes_are_ignored():
    case = load_case("tutorial")
    mayor = _char(case, "mayor")
    state = GameState()
    assert dialogue.choose(state, mayor, 99, 0, _lookup(case)) is None
    assert dialogue.choose(state, mayor, 0, 5, _lookup(case)) is None
    assert dialogue.trust_of(state, "mayor") == 0


def test_soft_answers_raise_trust_and_unlock_bonus():
    case = load_case("tutorial")
    mayor = _char(case, "mayor")
    state = GameState()

    dialogue.choose(state, mayor, 0, 0, _lookup(case))  # мягко: +1
    dialogue.choose(state, mayor, 1, 0, _lookup(case))  # мягко: +1
    assert dialogue.trust_of(state, "mayor") == 2

    bonus = dialogue.finish(state, mayor, _lookup(case))
    assert bonus is not None
    assert "сейф" in bonus["text"]
    assert "mayor" in state.trust_bonus_taken
    # второй раз бонус не выдаётся
    assert dialogue.finish(state, mayor, _lookup(case)) is None


def test_harsh_answers_lower_trust_and_block_bonus():
    case = load_case("tutorial")
    mayor = _char(case, "mayor")
    state = GameState()
    dialogue.choose(state, mayor, 0, 2, _lookup(case))  # жёстко: -1
    assert dialogue.trust_of(state, "mayor") == -1
    assert dialogue.finish(state, mayor, _lookup(case)) is None


def test_bonus_can_award_clue():
    case = load_case("tutorial")
    smith = _char(case, "smith")
    state = GameState()
    dialogue.choose(state, smith, 0, 0, _lookup(case))  # +1
    bonus = dialogue.finish(state, smith, _lookup(case))
    assert bonus is not None
    assert bonus["clue"]["id"] == "clue_collar"
    assert "clue_collar" in state.collected_clues


def test_trust_pips_are_clamped():
    assert dialogue.trust_pips(-3) == 0
    assert dialogue.trust_pips(2) == 2
    assert dialogue.trust_pips(99) == dialogue.MAX_TRUST


def test_dialogue_progress_survives_save_and_load():
    state = GameState()
    state.dialogue_choices = {"mayor:0": 2}
    state.trust = {"mayor": -1}
    state.trust_bonus_taken = {"smith"}

    restored = GameState.from_dict(state.to_dict())

    assert restored.dialogue_choices == {"mayor:0": 2}
    assert restored.trust == {"mayor": -1}
    assert restored.trust_bonus_taken == {"smith"}


def test_old_save_without_dialogue_fields_loads():
    restored = GameState.from_dict({"case_state": "in_progress"})
    assert restored.dialogue_choices == {}
    assert restored.trust == {}
    assert restored.trust_bonus_taken == set()


# ---------------------------------------------------------------------------
# Экран допроса
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


def _open_dialogue(game, case_id, char_id, idx=0):
    case = load_case(case_id)
    game.current_case = case
    game.state = GameState()
    game.dialogue_char = _char(case, char_id)
    game.dialogue_idx = idx
    game.screen_name = "dialogue"
    game.notifications.clear()


def test_dialogue_screen_draws_choices(game):
    _open_dialogue(game, "tutorial", "mayor")
    game.draw()
    assert len(dialogue.options(game.dialogue_char["dialogue"][0])) == 3
    assert dialogue.chosen(game.state, "mayor", 0) is None


def test_click_on_option_selects_it(game, monkeypatch):
    _open_dialogue(game, "tutorial", "mayor")
    rects = game._dialogue_option_rects(pygame.Rect(60, 80, 1160, 560), 3)
    target = rects[1].center
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: target)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)

    game.draw()

    assert dialogue.chosen(game.state, "mayor", 0) == 1
    assert "clue_paw" in game.state.collected_clues
    # после выбора экран рисуется без падений и показывает ответ
    game.draw()


def test_keyboard_choice_and_next(game):
    _open_dialogue(game, "tutorial", "alfred")
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)
    assert game._dialogue_event(ev) is True
    assert dialogue.chosen(game.state, "alfred", 0) == 0
    assert dialogue.trust_of(game.state, "alfred") == 1

    ev_next = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    assert game._dialogue_event(ev_next) is True
    assert game.dialogue_idx == 1


def test_next_is_blocked_until_choice(game):
    _open_dialogue(game, "tutorial", "smith")
    ev_next = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    assert game._dialogue_event(ev_next) is True
    assert game.dialogue_idx == 0
    assert dialogue.chosen(game.state, "smith", 0) is None
    assert any("реплику" in text for text, _ in game.notifications)


def test_finish_awards_bonus_at_last_topic(game):
    _open_dialogue(game, "tutorial", "smith", idx=3)
    dialogue.choose(game.state, game.dialogue_char, 3, 1, game._dialogue_clue_lookup())
    game._dialogue_next(game.dialogue_char)
    assert game.dialogue_idx == 4
    assert "smith" in game.state.trust_bonus_taken


def test_escape_leaves_dialogue(game):
    _open_dialogue(game, "tutorial", "mayor")
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    assert game._dialogue_event(ev) is True
    assert game.screen_name == "location"
