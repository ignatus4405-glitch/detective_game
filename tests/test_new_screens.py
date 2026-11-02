"""Тесты новых экранов: доска, хронология, обыск, слежка, ложь, время.

Логика проверяется отдельными модулями, а здесь — что клики попадают в те же
прямоугольники, что нарисованы, и что состояние игры меняется как задумано.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import board, search, surveillance, timeline, worldtime  # noqa: E402
from detective_game.data import load_case  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402
from detective_game.ui import search_view  # noqa: E402


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
    game.state.collected_clues = set(clues if clues is not None else [c["id"] for c in case["clues"]])
    game.notifications.clear()
    return case


def _click(game, pos):
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


# ── доска версий ────────────────────────────────────────────────────


def test_board_tab_links_clicked_pair(game):
    case = _setup(game, clues=["clue_chess_note"])
    game.state.collected_clues.add("clue_ticket")
    game.screen_name = "notebook"
    game.notebook_tab = "board"
    game.draw()
    clue_rect = game.board_rects["clues"]["clue_chess_note"]
    _click(game, clue_rect.center)
    assert game.board_clue == "clue_chess_note"
    suspect_rect = game.board_rects["suspects"]["finch"]
    _click(game, suspect_rect.center)
    assert board.link_key("clue_chess_note", "finch") in game.state.board_links
    assert game.state.case_time_minutes == 5
    assert "принята" in game.board_message
    assert game.board_clue is None


def test_board_wrong_pair_costs_time_and_is_blocked(game):
    _setup(game)
    game.screen_name = "notebook"
    game.notebook_tab = "board"
    game.draw()
    _click(game, game.board_rects["clues"]["clue_chess_note"].center)
    before = game.state.case_time_minutes
    _click(game, game.board_rects["suspects"]["lansky"].center)
    assert game.state.case_time_minutes == before + 10
    assert "Не сходится" in game.board_message
    assert board.link_key("clue_chess_note", "lansky") in game.state.board_wrong


def test_board_hint_button_marks_pair(game):
    _setup(game)
    game.screen_name = "notebook"
    game.notebook_tab = "board"
    game.draw()
    before = game.state.case_time_minutes
    _click(game, game.board_rects["hint"].center)
    assert game.board_clue is not None
    assert "Наводка" in game.board_message
    assert game.state.case_time_minutes == before + 5


def test_notebook_has_versions_tab(game, monkeypatch):
    _setup(game)
    game.screen_name = "notebook"
    game.notebook_tab = "clues"
    # третья вкладка «ВЕРСИИ» — x = header.right - 460 + 2*110
    tab_center = (1280 - 20 - 460 + 2 * 110 + 50, 15 + 25)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: tab_center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    game.draw()
    assert game.notebook_tab == "board"
    assert game.board_rects.get("suspects")


# ── хронология ─────────────────────────────────────────────────────


def test_timeline_check_button_solves_and_rewards(game):
    case = _setup(game)
    game.screen_name = "timeline"
    game.timeline_return = "accusation"
    game.state.timeline_order = timeline.correct_order(case)
    game.draw()
    _click(game, game.timeline_rects["check"].center)
    assert game.state.timeline_solved is True
    assert game.state.reputation == 2
    assert game.state.case_time_minutes == 10
    game.draw()
    _click(game, game.timeline_rects["next"].center)
    assert game.screen_name == "accusation"


def test_timeline_skip_button_returns_to_accusation(game):
    _setup(game)
    game.screen_name = "timeline"
    game.timeline_return = "accusation"
    timeline.reset(game.state, game.current_case)
    game.draw()
    _click(game, game.timeline_rects["skip"].center)
    assert game.screen_name == "accusation"


def test_timeline_cards_swap_on_two_clicks(game):
    _setup(game)
    game.screen_name = "timeline"
    timeline.start(game.state, game.current_case)
    game.draw()
    order = list(game.state.timeline_order)
    _click(game, game.timeline_rects["cards"][0].center)
    assert game.timeline_selected == 0
    _click(game, game.timeline_rects["cards"][1].center)
    assert game.state.timeline_order[0] == order[1]
    assert game.state.timeline_order[1] == order[0]


def test_timeline_arrows_move_card(game):
    _setup(game)
    game.screen_name = "timeline"
    timeline.start(game.state, game.current_case)
    game.draw()
    first = game.state.timeline_order[0]
    _click(game, game.timeline_rects["down"][0].center)
    assert game.state.timeline_order[1] == first


# ── обыск ──────────────────────────────────────────────────────────


def test_search_reveals_hidden_clue_and_hides_it_until_found(game):
    case = _setup(game)
    game.state.collected_clues = set()
    game.screen_name = "location"
    game.location_id = "warehouse"
    visible = search.visible_clues(case, "warehouse", game.state)
    assert all(not c.get("hidden") for c in visible)
    game.draw()
    _click(game, game.search_start_rect.center)
    assert game.search is not None
    assert game.search.clue_spots_left == 1
    game.draw()
    clue_spot = next(s for s in game.search.spots if s["kind"] == "clue")
    visual = game.search_rects["visual"]
    pos = (
        int(visual.x + clue_spot["x"] * visual.w),
        int(visual.y + clue_spot["y"] * visual.h),
    )
    _click(game, pos)
    assert "clue_fabric" in game.state.hidden_found
    # последняя улика найдена — обыск закрывается сам
    assert game.search is None
    assert any(c["id"] == "clue_fabric" for c in search.visible_clues(case, "warehouse", game.state))


def test_search_timer_expires_and_costs_time(game):
    case = _setup(game)
    game.state.collected_clues = set()
    search_view.start(game)
    game.search.remaining = 0.0
    before = game.state.case_time_minutes
    game.update(game._to_logical(pygame.mouse.get_pos()), False)
    assert game.search is None
    assert game.state.case_time_minutes == before + 10


def test_search_finish_button_stops(game):
    _setup(game)
    game.state.collected_clues = set()
    search_view.start(game)
    game.draw()
    before = game.state.case_time_minutes
    _click(game, game.search_rects["finish"].center)
    assert game.search is None
    assert game.state.case_time_minutes == before + 10


# ── слежка ─────────────────────────────────────────────────────────


def test_surveillance_starts_from_map(game):
    case = _setup(game, clues=["clue_bar_testimony"])
    assert surveillance.available(case, game.state)
    game.screen_name = "map"
    game.map_action_rects = {}
    game.draw()
    assert "tail" in game.map_action_rects
    game.tail = surveillance.Tail(surveillance.spec_for(case))
    game.screen_name = "tail"
    game.tail_rects = {}
    game.draw()
    assert game.tail_rects.get("back")


def test_surveillance_success_pays_and_finishes(game):
    case = _setup(game, clues=["clue_bar_testimony"])
    game.tail = surveillance.Tail(surveillance.spec_for(case))
    game.tail_rewarded = False
    game.tail.success = True
    game.tail.last_event = "дошёл"
    game.screen_name = "tail"
    game.update((640, 360), False)
    assert "missing_chess" in game.state.tail_done
    assert game.state.money == 620
    game.draw()
    _click(game, game.tail_rects["next"].center)
    assert game.screen_name == "map"
    assert game.tail is None


def test_surveillance_abort_returns_to_map(game):
    _setup(game)
    game.tail = surveillance.Tail(surveillance.spec_for(game.current_case))
    game.screen_name = "tail"
    game.draw()
    _click(game, game.tail_rects["back"].center)
    assert game.screen_name == "map"


# ── ложь и доверие ─────────────────────────────────────────────────


def test_expose_lie_button_uses_clue(game, monkeypatch):
    case = _setup(game, clues=["clue_camera"])
    game.screen_name = "dialogue"
    char = next(c for c in case["characters"] if c["id"] == "elena")
    game.dialogue_char = char
    game.dialogue_idx = 2
    game.draw()
    lie_rect = game.dialogue_lie_rects["lie"]
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: lie_rect.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    game.draw()
    assert "elena:2" in game.state.exposed_lies
    assert game.state.trust["elena"] >= 1
    assert game.state.case_time_minutes == 5
    game.draw()  # чип «уличён во лжи» рисуется без ошибок


def test_expose_lie_without_clue_is_disabled(game, monkeypatch):
    case = _setup(game, clues=[])
    game.screen_name = "dialogue"
    char = next(c for c in case["characters"] if c["id"] == "elena")
    game.dialogue_char = char
    game.dialogue_idx = 2
    game.draw()
    rect = game.dialogue_lie_rects["lie"]
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    game.draw()
    assert game.state.exposed_lies == {}


# ── время суток ────────────────────────────────────────────────────


def test_wait_button_on_map_advances_time(game, monkeypatch):
    _setup(game)
    game.state.case_time_minutes = 0
    game.screen_name = "map"
    game.draw()
    rect = game.map_action_rects["wait"]
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    game.draw()
    assert game.state.case_time_minutes > 0
    # «ЖДАТЬ» промотало время до ближайшего открытия — хоть одна локация открылась
    opened = [
        loc
        for loc in game.current_case["locations"]
        if worldtime.is_open_now(loc, game.state.case_time_minutes)
    ]
    assert opened
    assert any(
        not worldtime.is_open_now(loc, 0) for loc in opened
    ) or game.state.case_time_minutes == 60


def test_closed_location_click_does_not_enter(game):
    _setup(game)
    game.state.case_time_minutes = 300  # 14:00 — бар закрыт
    game.screen_name = "map"
    game.draw()
    layout = game._map_layout()
    pin = next(
        rect
        for loc, rect in zip(game.current_case["locations"], layout.pins, strict=False)
        if loc["id"] == "bar"
    )
    _click(game, pin.center)
    assert game.screen_name == "map"
    assert any("Закрыто" in text for text, _ in game.notifications)


def test_closed_location_screen_waits_on_click(game, monkeypatch):
    _setup(game)
    game.state.case_time_minutes = 300
    game.screen_name = "location"
    game.location_id = "bar"
    game.draw()  # закрытый экран не падает
    button = (1280 // 2, 75 + 290 + 23)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: button)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    before = game.state.case_time_minutes
    game.draw()
    assert game.state.case_time_minutes > before
    bar = next(loc for loc in game.current_case["locations"] if loc["id"] == "bar")
    assert worldtime.is_open_now(bar, game.state.case_time_minutes)


def test_location_shows_clock_and_hours(game):
    _setup(game)
    game.state.case_time_minutes = 0
    game.screen_name = "location"
    game.location_id = "office"
    game.draw()
    assert worldtime.clock_text(game.state.case_time_minutes) == "День 1 • 09:00"


# ── головоломки новых типов через игру ─────────────────────────────


def test_new_puzzle_clicks_work(game):
    from detective_game import puzzles
    from detective_game.data import get_clue

    for case_id, clue_id, kind in (
        ("missing_chess", "clue_bar_testimony", "alibi"),
        ("missing_chess", "clue_photos", "develop"),
        ("bank_heist", "clue_fingerprint", "align"),
    ):
        case = _setup(game, case_id=case_id)
        clue = get_clue(case, clue_id)
        game.state.collected_clues.discard(clue_id)
        game.open_puzzle(clue)
        assert game.puzzle.kind == kind
        game.draw()
        if kind == "alibi":
            for person, place in enumerate(game.puzzle.solution):
                game.assign_puzzle_alibi(person, place)
            game.submit_puzzle_grid()
        elif kind == "develop":
            for name, target in game.puzzle.targets_dev.items():
                game.adjust_puzzle_param(name, target - game.puzzle.params[name])
            game.submit_puzzle_develop()
        else:
            for target in game.puzzle.angle_targets:
                game.puzzle.angle = target
                game.strike_puzzle_align()
        assert game.puzzle.success, kind
        game.finish_puzzle_flow()
        assert clue_id in game.state.collected_clues
        assert puzzles.PUZZLE_TYPES


# ── маршрут и QTE ──────────────────────────────────────────────────


def test_map_tail_button_opens_route_screen(game, monkeypatch):
    _setup(game, clues=["clue_bar_testimony"])
    game.screen_name = "map"
    game.draw()
    rect = game.map_action_rects["tail"]
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)
    game.draw()
    assert game.screen_name == "route"
    game.draw()  # экран маршрута рисуется на следующем кадре
    assert game.route_rects.get("cards")


def test_route_choice_starts_tail_and_costs_time(game):
    case = _setup(game, clues=["clue_bar_testimony"])
    game.screen_name = "route"
    game.tail_spec = surveillance.spec_for(case)
    game.draw()
    route, card = game.route_rects["cards"][0]
    before = game.state.case_time_minutes
    _click(game, card.center)
    assert game.screen_name == "tail"
    assert game.state.case_time_minutes == before + route["minutes"]
    assert game.tail is not None


def test_route_cancel_returns_to_map(game):
    case = _setup(game, clues=["clue_bar_testimony"])
    game.screen_name = "route"
    game.tail_spec = surveillance.spec_for(case)
    game.draw()
    _click(game, game.route_rects["back"].center)
    assert game.screen_name == "map"


def test_qte_success_rewards_state(game):
    from detective_game.ui import qte_view

    _setup(game)
    game.screen_name = "location"
    game.location_id = "bar"
    game.state.case_time_minutes = 600  # 19:00 — бар открыт
    assert qte_view.start(game)
    assert game.screen_name == "qte"
    fight = game.qte
    for _ in range(3):
        if fight.finished:
            break
        direction = fight.prompt
        key = {
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "up": pygame.K_UP,
            "down": pygame.K_DOWN,
        }[direction]
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
    game.update((640, 360), False)
    assert game.state.fight_done is True
    assert game.state.reputation == 1
    assert game.state.money == 540
    game.draw()
    _click(game, game.qte_rects["next"].center)
    assert game.screen_name == "location"
    assert game.qte is None


def test_qte_failure_costs_time(game):
    from detective_game.ui import qte_view

    _setup(game)
    game.screen_name = "location"
    game.location_id = "bar"
    game.state.case_time_minutes = 600
    assert qte_view.start(game)
    fight = game.qte
    before = game.state.case_time_minutes
    while not fight.finished:
        wrong = next(d for d in ("left", "right", "up", "down") if d != fight.prompt)
        key = {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "up": pygame.K_w,
            "down": pygame.K_s,
        }[wrong]
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
    game.update((640, 360), False)
    assert game.state.case_time_minutes == before + 20
    assert game.state.reputation == 0


# ── «взрослые» правила: экспертиза, показания, суд, патруль, срок ────


def _press(game, monkeypatch, pos):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
    monkeypatch.setattr(game, "_click_once", lambda: True)


def test_expertise_button_confirms_hearsay(game, monkeypatch):
    from detective_game import expertise
    from detective_game.data import get_clue

    case = _setup(game, case_id="bank_heist", clues=["clue_coffee"])
    game.state.reputation = 2
    game.state.money = 200
    game.screen_name = "notebook"
    game.notebook_tab = "clues"
    game.draw()
    rect = game.expertise_rects["clue_coffee"]
    _press(game, monkeypatch, rect.center)
    game.draw()
    assert "clue_coffee" in game.state.confirmed_clues
    assert game.state.money == 200 - 50
    assert expertise.counts_in_court(case, game.state, get_clue(case, "clue_coffee"))


def test_testimony_screen_finds_contradiction(game):
    from detective_game import testimony
    from detective_game.ui import testimony_view

    case = _setup(game)
    item = testimony.contradictions(case)[0]
    game.state.asked_topics = {item["a"], item["b"]}
    game.screen_name = "notebook"
    game.notebook_tab = "board"
    game.draw()
    _click(game, game.board_rects["testimony"].center)
    assert game.screen_name == "testimony"
    game.draw()
    assert item["a"] in game.testimony_rects["rows"]
    testimony_view.handle_testimony_click(game, game.testimony_rects["rows"][item["a"]].center)
    testimony_view.handle_testimony_click(game, game.testimony_rects["rows"][item["b"]].center)
    assert len(game.testimony_selected) == 2
    _click(game, game.testimony_rects["compare"].center)
    assert item["id"] in game.state.deductions
    assert game.state.reputation >= 1


def test_trial_chips_required_before_accusation(game, monkeypatch):
    from detective_game import trial

    case = _setup(game)
    game.screen_name = "accusation"
    game.accusation_selected = "finch"
    game.draw()
    assert game.trial_rects["motive"]
    assert game.trial_rects["method"]
    assert trial.ready(case, game.state) is False
    motive_id = trial.answers(case, "finch")["motive"]
    method_id = trial.answers(case, "finch")["method"]
    _press(game, monkeypatch, game.trial_rects["motive"][motive_id].center)
    game.draw()
    _press(game, monkeypatch, game.trial_rects["method"][method_id].center)
    game.draw()
    assert game.state.trial_motive == motive_id
    assert game.state.trial_method == method_id
    assert trial.ready(case, game.state) is True


def test_search_patrol_catches_player(game):
    case = _setup(game)
    game.location_id = "warehouse"
    game.screen_name = "location"
    game.search = search.Search(case, "warehouse", game.state)
    game.draw()
    session = game.search
    assert session.patrol_on is True
    visual = game.search_rects["visual"]
    px, py, pw, ph = session.patrol_rect()
    pos = (
        int(visual.x + (px + pw / 2) * visual.w),
        int(visual.y + (py + ph / 2) * visual.h),
    )
    search_view.handle_click(game, pos)
    assert session.caught is True


def test_empty_search_click_costs_time_in_advanced_case(game):
    case = _setup(game)
    game.location_id = "warehouse"
    game.screen_name = "location"
    game.search = search.Search(case, "warehouse", game.state)
    game.draw()
    session = game.search
    before = game.state.case_time_minutes
    # правый нижний угол пуст; патруль уводим в левый верхний сектор
    session.route_index = session.patrol_route.index((0, 0))
    visual = game.search_rects["visual"]
    search_view.handle_click(game, (visual.right - 3, visual.bottom - 3))
    assert game.state.case_time_minutes == before + 2
    assert session.misses == 1


def test_dialogue_timeout_costs_trust(game):
    from detective_game import dialogue

    case = _setup(game)
    elena = next(c for c in case["characters"] if c["id"] == "elena")
    interactive = next(
        i for i, topic in enumerate(elena["dialogue"]) if dialogue.is_interactive(topic)
    )
    game.dialogue_char = elena
    game.dialogue_idx = interactive
    game.screen_name = "dialogue"
    game.state.asked_topics.add(f"elena:{interactive}")
    game.dialogue_timer = 0.1
    game._update_dialogue_timer(0.5)
    assert dialogue.declined(game.state, "elena", interactive)
    assert dialogue.trust_of(game.state, "elena") == -1
    assert game.dialogue_timer == 0


def test_harsh_reply_silences_character(game):
    from detective_game import dialogue

    case = _setup(game)
    elena = next(c for c in case["characters"] if c["id"] == "elena")
    index, option, harsh = None, None, None
    for i, topic in enumerate(elena["dialogue"]):
        for j, opt in enumerate(dialogue.options(topic)):
            if int(opt.get("trust", 0) or 0) < 0:
                index, option, harsh = i, j, opt
                break
        if harsh:
            break
    if harsh is None:
        pytest.skip("у Елены нет жёстких реплик")
    game.state.trust["elena"] = 0
    result = dialogue.choose(game.state, elena, index, option)
    assert result["trust_delta"] < 0
    assert dialogue.is_silent(game.state, "elena")


def test_deadline_missed_marks_state(game):
    from detective_game import pressure

    case = _setup(game)
    game.state.case_time_minutes = pressure.deadline_minutes(case) + 1
    game.screen_name = "map"
    game.update((0, 0), False)
    assert game.state.deadline_missed is True
    assert any("Срок" in text for text, _ in game.notifications)


def test_repeat_topic_penalty_once_per_visit(game):
    from detective_game import dialogue

    case = _setup(game)
    elena = next(c for c in case["characters"] if c["id"] == "elena")
    game.state.asked_topics.add("elena:0")
    game.dialogue_char = elena
    game.dialogue_idx = 0
    game.dialogue_penalized = False
    game._dialogue_enter(elena)
    assert dialogue.trust_of(game.state, "elena") == -1
    game.dialogue_idx = 1
    game.state.asked_topics.add("elena:1")
    game._dialogue_enter(elena)
    assert dialogue.trust_of(game.state, "elena") == -1
