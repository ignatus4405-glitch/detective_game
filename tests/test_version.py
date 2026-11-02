"""Тесты определения версии — особенно для frozen (PyInstaller) сборки.

Регрессия: раньше собранная игра не находила VERSION (файл не попадал в
бандл), сообщала версию 0.1.0 и бесконечно предлагала «обновиться» до той,
что уже установлена.
"""
import sys
import types
from pathlib import Path

import detective_game
from detective_game import _read_version_file, _version_candidates, get_version


def test_get_version_matches_version_file():
    root = Path(__file__).resolve().parent.parent
    expected = (root / "VERSION").read_text(encoding="utf-8").strip().lstrip("vV")
    assert get_version() == expected


def test_read_version_file_strips_prefix_and_newlines(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("v0.1.24\n", encoding="utf-8")
    assert _read_version_file(version_file) == "0.1.24"


def test_read_version_file_rejects_garbage(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("не версия", encoding="utf-8")
    assert _read_version_file(version_file) is None
    assert _read_version_file(tmp_path / "missing") is None


def test_candidates_cover_pyinstaller_onedir_layout(tmp_path):
    app = tmp_path / "app"
    internal = app / "_internal"
    internal.mkdir(parents=True)
    candidates = _version_candidates(
        frozen=True,
        executable=str(app / "DetectiveBlackville.exe"),
        meipass=str(internal),
        package_dir=internal / "detective_game",
    )
    assert app / "VERSION" in candidates
    assert internal / "VERSION" in candidates
    assert internal / "detective_game" / "VERSION" in candidates


def test_frozen_build_reads_version_from_internal(tmp_path, monkeypatch):
    app = tmp_path / "app"
    internal = app / "_internal"
    internal.mkdir(parents=True)
    (internal / "VERSION").write_text("9.8.7\n", encoding="utf-8")
    monkeypatch.setattr(
        detective_game,
        "_version_candidates",
        lambda: _version_candidates(
            frozen=True,
            executable=str(app / "DetectiveBlackville.exe"),
            meipass=str(internal),
            package_dir=internal / "detective_game",
        ),
    )
    assert detective_game.get_version() == "9.8.7"


def test_build_version_module_is_used_as_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(detective_game, "_version_candidates", lambda: [tmp_path / "missing"])
    fake = types.ModuleType("detective_game._build_version")
    fake.BUILD_VERSION = "0.2.5"
    monkeypatch.setitem(sys.modules, "detective_game._build_version", fake)
    monkeypatch.setattr(detective_game, "_read_metadata_version", lambda: None)
    assert detective_game.get_version() == "0.2.5"


def test_last_resort_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(detective_game, "_version_candidates", lambda: [tmp_path / "missing"])
    monkeypatch.setattr(detective_game, "_read_packaged_version", lambda: None)
    monkeypatch.setattr(detective_game, "_read_metadata_version", lambda: None)
    assert detective_game.get_version() == detective_game._FALLBACK_VERSION
