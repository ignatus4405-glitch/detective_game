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
