"""Клики на игровых экранах переводятся в логические координаты ровно один раз."""
import pytest

pygame = pytest.importorskip("pygame")

from detective_game import main as game_main


@pytest.fixture
def game(monkeypatch):
    pygame.init()
    obj = game_main.Game()
    monkeypatch.setattr(obj.audio, "play_sfx", lambda *args: None)
    yield obj
    pygame.quit()


@pytest.mark.parametrize("size", [(1920, 1080), (1024, 768)])
@pytest.mark.parametrize("screen", ["case_select", "alibi", "proof", "riddle"])
def test_scaled_mouse_click_reaches_logical_position(game, monkeypatch, size, screen):
    pygame.display.set_mode(size)
    game.screen_name = screen
    expected = (400, 300)
    scale, ox, oy, *_ = game._get_letterbox()
    physical = (int(expected[0] * scale + ox), int(expected[1] * scale + oy))
    # run() преобразует позицию до передачи события в handle_event.
    logical = game._to_logical(physical)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=logical)
    if screen == "case_select":
        game.case_index = 0
        game.case_select_rects = {"cases": {1: pygame.Rect(390, 290, 20, 20)}}
        game.handle_event(event)
        assert game.case_index == 1
    else:
        calls = []
        if screen == "riddle":
            monkeypatch.setattr(game_main, "handle_riddle_click", lambda _game, pos: calls.append(pos))
        else:
            view = getattr(game_main, f"{screen}_view")
            monkeypatch.setattr(view, "handle_click", lambda _game, pos: calls.append(pos))
        game.handle_event(event)
        assert calls == [logical]
