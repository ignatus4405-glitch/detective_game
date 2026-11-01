from pathlib import Path

from detective_game.game_state import DetectiveProfile, GameState
from detective_game.save_system import get_save_dir


def test_save_dir_exists():
    # get_save_dir should return a Path
    p = get_save_dir()
    assert isinstance(p, Path)
    assert "BlackvilleDetective" in str(p)

def test_game_state_save_load_roundtrip(tmp_path, monkeypatch):
    # monkeypatch get_save_dir to tmp
    import detective_game.save_system as ss
    monkeypatch.setattr(ss, "get_save_dir", lambda: tmp_path)

    state = GameState(
        detective=DetectiveProfile(name="Тест Детектив", avatar_id="detective_03", background="ex_cop"),
        current_case_id="bank_heist",
        visited_locations={"office"},
        collected_clues={"clue_log"},
        case_state="in_progress",
    )
    ss.save_game(state)
    loaded = ss.load_game()
    assert loaded is not None
    assert loaded.detective.name == "Тест Детектив"
    assert loaded.current_case_id == "bank_heist"
    assert "clue_log" in loaded.collected_clues

def test_settings_roundtrip(tmp_path, monkeypatch):
    import detective_game.save_system as ss
    monkeypatch.setattr(ss, "get_save_dir", lambda: tmp_path)
    settings = {"sfx_volume": 0.5, "fullscreen": True, "lang": "ru"}
    ss.save_settings(settings)
    loaded = ss.load_settings()
    assert loaded["sfx_volume"] == 0.5
    assert loaded["fullscreen"] == True

def test_detective_roundtrip(tmp_path, monkeypatch):
    import detective_game.save_system as ss
    monkeypatch.setattr(ss, "get_save_dir", lambda: tmp_path)
    det = DetectiveProfile(name="Мара", avatar_id="detective_02", background="reporter", gender="female")
    ss.save_detective(det)
    loaded = ss.load_detective()
    assert loaded is not None
    assert loaded.name == "Мара"
    assert loaded.background == "reporter"
