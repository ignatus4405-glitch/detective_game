from detective_game.game_state import AVATARS, BACKGROUNDS, DetectiveProfile, GameState


def test_detective_profile_defaults():
    det = DetectiveProfile()
    assert det.name == "Алекс Рейн"
    assert det.avatar_id
    assert det.background in {"private_eye", "ex_cop", "reporter"}
    assert det.background_label
    assert det.background_desc

def test_avatars_structure():
    assert len(AVATARS) == 6
    for av in AVATARS:
        assert "id" in av and "name" in av and "color" in av
        assert av["gender"] in {"male", "female"}

def test_backgrounds():
    assert len(BACKGROUNDS) == 3
    ids = {b["id"] for b in BACKGROUNDS}
    assert ids == {"private_eye", "ex_cop", "reporter"}

def test_game_state_serialization():
    state = GameState(
        detective=DetectiveProfile(name="Тест", avatar_id="detective_02", background="reporter"),
        current_case_id="missing_chess",
        visited_locations={"office", "park"},
        collected_clues={"clue_camera"},
    )
    d = state.to_dict()
    restored = GameState.from_dict(d)
    assert restored.detective.name == "Тест"
    assert restored.current_case_id == "missing_chess"
    assert "park" in restored.visited_locations
    assert "clue_camera" in restored.collected_clues
    assert restored.case_state == "not_started"

def test_game_state_defaults():
    s = GameState()
    assert s.case_state == "not_started"
    assert s.visited_locations == set()
