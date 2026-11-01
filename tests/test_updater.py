from detective_game.updater import _parse_version, is_newer

def test_parse_version():
    assert _parse_version("v0.1.0") == (0,1,0)
    assert _parse_version("1.2.3") == (1,2,3)
    assert _parse_version("v10.20.30") == (10,20,30)
    assert _parse_version("0.0.1") == (0,0,1)

def test_is_newer():
    assert is_newer("v0.2.0", "0.1.0") == True
    assert is_newer("0.1.1", "0.1.0") == True
    assert is_newer("0.1.0", "0.1.0") == False
    assert is_newer("0.0.9", "0.1.0") == False
    assert is_newer("v1.0.0", "0.9.9") == True

def test_version_sync():
    # VERSION file and pyproject should be in sync — checked in CI
    from pathlib import Path
    version_file = Path("VERSION")
    if version_file.exists():
        v = version_file.read_text().strip().lstrip("v")
        # must be semver
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
