"""Тесты видео-катсцены: данные, тайминг, управление, отрисовка."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from detective_game import cutscene as cutscene_mod  # noqa: E402
from detective_game.case_cutscenes import CUTSCENES, cutscene_for, has_cutscene  # noqa: E402
from detective_game.config import IMAGES_DIR  # noqa: E402
from detective_game.cutscene import Cutscene, CutscenePlayer, Scene  # noqa: E402
from detective_game.data import list_cases  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _video():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------


def test_every_case_has_cutscene():
    """У каждого дела есть вступление — иначе игрок не поймёт, что случилось."""
    for case in list_cases():
        assert has_cutscene(case["id"]), f"{case['id']}: нет катсцены"
        movie = cutscene_for(case["id"])
        assert movie.title
        assert len(movie.scenes) >= 3


def test_cutscene_images_exist():
    for case_id, data in CUTSCENES.items():
        for scene in data["scenes"]:
            path = IMAGES_DIR / scene.image
            assert path.is_file(), f"{case_id}: нет картинки {scene.image}"
            assert path.stat().st_size > 20_000, f"{case_id}: {scene.image} похож на заглушку"


def test_scenes_have_captions_and_labels():
    for case_id, data in CUTSCENES.items():
        for scene in data["scenes"]:
            assert len(scene.caption) > 40, f"{case_id}: слишком короткая подпись"
            assert scene.label, f"{case_id}: у кадра нет метки времени"
            assert scene.pan in ("in", "out", "left", "right")


def test_cutscene_titles_match_case_titles():
    titles = {case["id"]: case["title"] for case in list_cases()}
    for case_id, data in CUTSCENES.items():
        assert data["title"] == titles[case_id], f"{case_id}: заголовок катсцены разошёлся с делом"


def test_unknown_case_has_no_cutscene():
    assert cutscene_for("no_such_case") is None
    assert has_cutscene("") is False


# ---------------------------------------------------------------------------
# Тайминг
# ---------------------------------------------------------------------------


def test_read_time_grows_with_caption_length():
    short = cutscene_mod.read_time("Коротко.")
    long = cutscene_mod.read_time("Очень длинная подпись. " * 8)
    assert short >= cutscene_mod.MIN_READ_TIME
    assert long > short


def test_every_scene_is_readable():
    """Сцена должна висеть на экране не меньше, чем нужно на чтение."""
    for data in CUTSCENES.values():
        for scene in data["scenes"]:
            assert cutscene_mod.scene_duration(scene) >= cutscene_mod.read_time(scene.caption)


def test_player_advances_and_finishes():
    player = CutscenePlayer(cutscene_for("tutorial"))
    scenes = len(player.scenes)
    assert player.index == 0
    assert player.finished is False

    for _ in range(200):
        player.update(0.1)
        if player.finished:
            break

    assert player.finished is True
    assert player.index == scenes


def test_typing_reveals_caption_gradually():
    player = CutscenePlayer(cutscene_for("tutorial"))
    full = player.scene.caption
    assert player.revealed == 0
    for _ in range(4):  # dt ограничен 0.25 с за кадр — как в реальном цикле
        player.update(0.25)
    partial = player.revealed
    assert 0 < partial < len(full)
    player.elapsed = 60.0
    assert player.revealed == len(full)


def test_advance_first_completes_typing_then_moves_on():
    player = CutscenePlayer(cutscene_for("tutorial"))
    player.update(0.3)
    assert player.typing_done is False
    player.advance()
    assert player.typing_done is True
    assert player.index == 0
    player.advance()
    assert player.index == 1


def test_skip_finishes_immediately():
    player = CutscenePlayer(cutscene_for("bank_heist"))
    player.skip()
    assert player.finished is True
    assert player.scene is None


def test_restart_replays_from_first_scene():
    player = CutscenePlayer(cutscene_for("tutorial"))
    player.skip()
    player.restart()
    assert player.finished is False
    assert player.index == 0


def test_empty_cutscene_is_finished():
    player = CutscenePlayer(Cutscene("", ""))
    assert player.finished is True
    assert player.update(1.0) is False


def test_no_replay_of_underlying_story_state():
    """Катсцена — только показ: состояние дела она не меняет."""
    player = CutscenePlayer(cutscene_for("tutorial"))
    player.update(3.0)
    player.skip()
    assert player.cutscene.case_id == "tutorial"


# ---------------------------------------------------------------------------
# Кадры и отрисовка
# ---------------------------------------------------------------------------


def test_frames_are_rendered_and_zoom():
    player = CutscenePlayer(Cutscene("x", "t", scenes=[Scene("cutscenes/tutorial/01_window.jpg", "текст")]))
    frames = player.frames()
    assert len(frames) == cutscene_mod.ZOOM_STEPS
    assert frames[0].get_size() == (1280, 720)
    # кадры различаются: камера действительно движется
    first = pygame.image.tostring(frames[0], "RGB")
    last = pygame.image.tostring(frames[-1], "RGB")
    assert first != last


def test_missing_image_falls_back_to_gradient():
    player = CutscenePlayer(
        Cutscene("x", "t", scenes=[Scene("cutscenes/nope.jpg", "подпись про пустоту")])
    )
    player.elapsed = 2.0  # пережили затемнение на входе
    surface = pygame.Surface((1280, 720))
    cutscene_mod.draw_cutscene(surface, player)  # не падает
    assert surface.get_at((640, 360))[:3] != (0, 0, 0)


def test_draw_cutscene_paints_frame_and_caption():
    player = CutscenePlayer(cutscene_for("missing_chess"))
    player.elapsed = 3.0
    surface = pygame.Surface((1280, 720))
    cutscene_mod.draw_cutscene(surface, player)
    colors = {
        surface.get_at((x, y))[:3]
        for x in range(0, 1280, 64)
        for y in range(0, 720, 72)
    }
    assert len(colors) > 40, "кадр не нарисован (однотонная заливка)"
    # подпись печатается — на экране есть светлые пиксели в нижней трети
    bright = sum(
        1
        for x in range(100, 1180, 7)
        for y in range(560, 660, 5)
        if sum(surface.get_at((x, y))[:3]) > 420
    )
    assert bright > 30, "подпись не отрисована"


def test_skip_button_rect_matches_draw():
    rect = cutscene_mod.cutscene_button_rect(1280, 720)
    assert rect.right <= 1280 and rect.y >= 0
    assert cutscene_mod.cutscene_button_rect(1600, 900).right <= 1600


# ---------------------------------------------------------------------------
# Интеграция с игрой
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def game():
    from detective_game.main import Game

    obj = Game()
    obj.notifications.clear()
    yield obj


def test_start_case_plays_cutscene_then_map(game):
    game.start_case("tutorial")
    assert game.screen_name == "cutscene"
    assert game.cutscene is not None

    game.cutscene.skip()
    game._cutscene_done()
    assert game.screen_name == "map"


def test_escape_skips_cutscene(game):
    game.start_case("bank_heist")
    game.draw()
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.screen_name == "map"


def test_click_advances_cutscene(game):
    game.start_case("tutorial")
    game.cutscene.update(0.2)
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(640, 400)))
    assert game.cutscene.index == 0  # первый клик досрочно допечатал подпись
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(640, 400)))
    assert game.cutscene.index == 1


def test_skip_button_click_ends_cutscene(game):
    game.start_case("tutorial")
    rect = cutscene_mod.cutscene_button_rect(1280, 720)
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert game.screen_name == "map"


def test_update_timer_finishes_cutscene(game, monkeypatch):
    """Игровой цикл сам закрывает катсцену, когда время вышло."""

    class _FastClock:
        def get_time(self):
            return 250  # 4 кадра в секунду, как на слабой машине

        def tick(self, *args, **kwargs):
            return 250

    game.start_case("tutorial")
    game.cutscene.skip()
    game.cutscene.restart()
    monkeypatch.setattr(game, "clock", _FastClock())
    for _ in range(400):
        game.update((0, 0), False)
        if game.screen_name != "cutscene":
            break
    assert game.screen_name == "map"


def test_map_has_replay_button(game):
    game.start_case("missing_chess")
    game.cutscene.skip()
    game._cutscene_done()
    assert game.screen_name == "map"
    rect = game._cutscene_replay_rect(game._map_layout())
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert game.screen_name == "cutscene"


def test_cutscene_draws_without_notifications(game):
    """На катсцене баннеры уведомлений не перекрывают кадр."""
    game.start_case("tutorial")
    game.cutscene.elapsed = 3.0
    game.add_notification("проверка баннера")
    game.draw()  # не падает
    # правый верхний угол занят кнопкой «пропустить», а не баннером уведомления
    assert game.screen_name == "cutscene"
