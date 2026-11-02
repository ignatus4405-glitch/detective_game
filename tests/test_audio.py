"""Тесты синтеза музыки и звукового движка (без реальной звуковой карты)."""

import os
import wave
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import audio as audio_mod  # noqa: E402
from detective_game import synth  # noqa: E402
from detective_game.audio import MUSIC_TRACKS, SFX_NAMES, AudioEngine  # noqa: E402


# ---------------------------------------------------------------------------
# Синтез
# ---------------------------------------------------------------------------


def test_every_sfx_renders_audible_signal():
    assert set(SFX_NAMES) == set(synth.SFX)
    for name in SFX_NAMES:
        buf = synth.render_sfx(name)
        assert len(buf) > 400, name
        peak = max(abs(sample) for sample in buf)
        assert 0.01 < peak <= 1.0, (name, peak)


def test_sfx_are_short():
    for name in SFX_NAMES:
        duration = len(synth.render_sfx(name)) / synth.SAMPLE_RATE
        assert duration < 2.0, name


def test_write_wav_produces_valid_file(tmp_path):
    path = tmp_path / "click.wav"
    buf = synth.render_sfx("click")
    synth.write_wav(path, buf)
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == synth.SAMPLE_RATE
        assert handle.getnframes() == len(buf)


def test_note_frequencies():
    assert round(synth.note_hz("A4")) == 440
    assert round(synth.note_hz("C4")) == 262


def test_success_track_is_short_and_musical():
    buf, seconds = synth.render_track("success")
    assert 3.0 <= seconds <= 10.0
    assert len(buf) == int(seconds * synth.SAMPLE_RATE) or abs(len(buf) - seconds * synth.SAMPLE_RATE) < 4000
    assert max(buf) > 0.05


@pytest.mark.parametrize("track", ["failure"])
def test_tracks_are_listed(track):
    assert track in MUSIC_TRACKS
    assert callable(getattr(synth, f"track_{track}"))


# ---------------------------------------------------------------------------
# Движок
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_mod, "ensure_save_dir", lambda: tmp_path)
    eng = AudioEngine()
    eng.init(start_prepare=False)
    yield eng
    eng.shutdown()


def test_engine_volumes_are_clamped(engine):
    engine.set_volumes(music=2.0, sfx=-1.0, voice=False)
    assert engine.music_volume == 1.0
    assert engine.sfx_volume == 0.0
    assert engine.voice_enabled is False


def test_track_paths_live_in_save_dir(engine, tmp_path):
    assert engine.cache_dir() == tmp_path / "music"
    assert engine.track_path("noir") == tmp_path / "music" / "noir.wav"
    assert engine.tracks_present() is False


def test_prepare_writes_tracks(engine, tmp_path):
    engine.start_prepare()
    assert engine._thread is not None
    engine._thread.join(timeout=60)
    assert engine.tracks_present()
    for name in MUSIC_TRACKS:
        assert (tmp_path / "music" / f"{name}.wav").stat().st_size > 10_000


def test_play_voice_without_file_is_silent(engine):
    assert engine.voice_path("нет-такого") is None
    assert engine.has_voice("нет-такого") is False
    assert engine.play_voice("нет-такого") is False
    engine.stop_voice()  # не падает


def test_play_voice_finds_file(engine, tmp_path, monkeypatch):
    voice_dir = tmp_path / "voice"
    voice_dir.mkdir()
    path = voice_dir / "cutscene_tutorial_1.wav"
    synth.write_wav(path, synth.render_sfx("tick"))
    monkeypatch.setattr(audio_mod, "VOICE_DIR", voice_dir)
    assert engine.voice_path("cutscene_tutorial_1") == path
    assert engine.has_voice("cutscene_tutorial_1") is True
    if not engine.available:  # pragma: no cover - зависит от драйвера
        pytest.skip("микшер недоступен")
    assert engine.play_voice("cutscene_tutorial_1") is True
    engine.voice_enabled = False
    engine.stop_voice()
    assert engine.play_voice("cutscene_tutorial_1") is False


def test_unknown_track_does_not_raise(engine):
    engine.play_music("странная-тема")
    engine.update()  # дорожек нет — просто ничего не делает
    engine.stop_music()


def test_voice_dir_is_inside_package():
    assert Path(audio_mod.__file__).parent / "assets" in audio_mod.VOICE_DIR.parents
