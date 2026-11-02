import pytest

from detective_game.data import (
    BUILTIN_CASES,
    get_character,
    get_clue,
    get_location,
    list_cases,
    load_case,
)


def test_builtin_cases_exist():
    assert len(BUILTIN_CASES) >= 2
    ids = {c["id"] for c in BUILTIN_CASES}
    assert "missing_chess" in ids
    assert "bank_heist" in ids

def test_case_structure():
    for case in BUILTIN_CASES:
        assert "id" in case and "title" in case
        assert "locations" in case and len(case["locations"]) >= 5
        assert "clues" in case and len(case["clues"]) >= 3
        assert "characters" in case
        assert "suspects" in case
        # у каждого дела есть culprit
        assert any(s.get("is_culprit") for s in case["suspects"])
        # у каждого есть endings
        assert "endings" in case

def test_load_case():
    case = load_case("missing_chess")
    assert case is not None
    assert case["id"] == "missing_chess"
    assert load_case("nonexistent") is None

def test_list_cases():
    cases = list_cases()
    assert len(cases) >= 2

def test_getters():
    case = load_case("missing_chess")
    assert get_location(case, "park") is not None
    assert get_location(case, "nope") is None
    assert get_clue(case, "clue_camera") is not None
    assert get_character(case, "elena") is not None

def test_clue_leads_to_valid_locations():
    for case in BUILTIN_CASES:
        loc_ids = {l["id"] for l in case["locations"]}
        for clue in case["clues"]:
            for target in clue.get("leads_to", []):
                assert target in loc_ids, f"clue {clue['id']} leads_to unknown {target} in case {case['id']}"


def test_every_listed_case_can_be_loaded():
    """Регрессия: дело из example.json (id=tutorial) не открывалось —
    load_case искал файл tutorial.json, а не поле id."""
    from detective_game.data import list_cases, load_case

    cases = list_cases()
    assert cases
    for case in cases:
        loaded = load_case(case["id"])
        assert loaded is not None, f"дело {case['id']} не загружается"
        assert loaded["id"] == case["id"]
        assert loaded["locations"], f"у дела {case['id']} нет локаций"


def test_load_case_unknown_returns_none():
    from detective_game.data import load_case

    assert load_case("no_such_case_123") is None


def test_every_case_has_existing_map_image():
    """В каждом деле — карта-картинка, и файл на месте (вкладка «Карта»)."""
    from detective_game.config import IMAGES_DIR
    from detective_game.data import case_map

    for case in list_cases():
        rel = case_map(case)
        assert rel.endswith((".jpg", ".jpeg", ".png")), f"{case['id']}: карта не картинка"
        assert (IMAGES_DIR / rel).is_file(), f"{case['id']}: нет файла карты {rel}"


def test_case_map_falls_back_to_default():
    from detective_game.data import DEFAULT_CASE_MAP, case_map

    assert case_map(None) == DEFAULT_CASE_MAP
    assert case_map({"id": "x"}) == DEFAULT_CASE_MAP
    assert case_map({"map": "maps/custom.jpg"}) == "maps/custom.jpg"


def test_location_art_files_exist():
    """Иллюстрации локаций из location_art ссылаются на существующие файлы."""
    from detective_game.config import IMAGES_DIR
    from detective_game.ui.location_art import LOCATION_ART, type_label

    for kind, (rel, tint) in LOCATION_ART.items():
        assert (IMAGES_DIR / rel).is_file(), f"{kind}: нет файла {rel}"
        if tint is not None:
            assert len(tint) == 4
    # неизвестный тип не падает и не превращается в пустую строку
    assert type_label({"type": "space_station"}) == "SPACE_STATION"
    assert type_label({}) == ""


def test_dialogues_are_long_enough():
    """Больше диалогов: у каждого персонажа минимум 3 темы.

    Тема — либо старая пара «вопрос/ответ», либо интерактивная тема с
    репликой персонажа и вариантами ответа детектива.
    """
    for case in list_cases():
        assert len(case["characters"]) >= 2, f"{case['id']}: мало персонажей"
        for ch in case["characters"]:
            topics = ch.get("dialogue", [])
            assert len(topics) >= 3, f"{case['id']}/{ch['id']}: всего {len(topics)} тем"
            for topic in topics:
                if topic.get("options"):
                    assert topic.get("prompt"), f"{case['id']}/{ch['id']}: тема без prompt"
                    for option in topic["options"]:
                        assert option.get("text") and option.get("reply")
                else:
                    assert topic.get("q") and topic.get("a")


# ── данные новых механик ─────────────────────────────────────────


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_all_cases_have_timeline(case):
    from detective_game import timeline

    assert timeline.available(case)
    events = list(timeline.by_id(case).values())
    assert len(events) >= 4
    assert all(event["text"] for event in events)
    assert len({event["time"] for event in events}) >= 3


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_all_cases_have_surveillance(case):
    from detective_game import surveillance

    spec = surveillance.spec_for(case)
    assert spec is not None
    assert any(clue["id"] == spec["reveal"] for clue in case["clues"])
    assert any(clue["id"] == spec["requires_clue"] for clue in case["clues"])
    assert len(surveillance.routes_for(case)) >= 2


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_every_case_has_hidden_clue(case):
    if case["id"] == "tutorial":
        return  # учебное дело короткое: скрытых улик нет намеренно
    assert any(clue.get("hidden") for clue in case["clues"])


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_board_fits_every_case(case):
    from detective_game import board

    for suspect in case["suspects"]:
        data = board.suspect(case, suspect["id"])
        assert data is not None
        for clue_id in data["evidence"]:
            assert any(clue["id"] == clue_id for clue in case["clues"])
