"""Звук в игре: музыка, эффекты и озвучка.

Всё построено на pygame.mixer, но **никогда не ломает игру**: если микшера
нет (нет звуковой карты, dummy-драйвер, ошибка инициализации), движок
переходит в тихий режим и все вызовы становятся пустыми.

Музыка генерируется кодом (см. :mod:`detective_game.synth`) и кэшируется в
папке пользователя ``<save_dir>/music``. Первый запуск считает ~5 дорожек за
2–3 секунды в фоновом потоке; пока они не готовы, игра просто тихая, потом
музыка плавно появляется.

Озвучка — обычные файлы в ``assets/voice`` (если их нет, субтитры остаются
субтитрами; игра не падает и не ругается).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, Optional

import pygame

from . import synth
from .config import IMAGES_DIR  # noqa: F401  (держит единый импорт конфигурации)
from .save_system import ensure_save_dir

MUSIC_TRACKS = (
    "noir",
    "investigation",
    "tension",
    "success",
    "failure",
    "lounge",
    "harbor",
    "precinct",
    "mystery",
    "chase",
)
SFX_NAMES = tuple(synth.SFX.keys())

# где искать озвучку (файлы кладутся рядом с игрой, не в кэш)
VOICE_DIR = Path(__file__).resolve().parent / "assets" / "voice"
VOICE_EXTS = (".ogg", ".wav", ".mp3")
MIXER_RATE = 44100


class AudioEngine:
    """Тонкая обёртка над mixer: музыка по настроению, эффекты, голос."""

    def __init__(self) -> None:
        self.available = False
        self.music_volume = 0.5
        self.sfx_volume = 0.7
        self.voice_enabled = True
        self.current_track: Optional[str] = None
        self._sfx: Dict[str, pygame.mixer.Sound] = {}
        self._voice_cache: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self._want_track: Optional[str] = None
        self._ready = False
        self._preparing = False
        self._prepared_paths: Dict[str, Path] = {}
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._voice_channel: Optional[pygame.mixer.Channel] = None
        self.last_error: Optional[str] = None

    # ── инициализация ─────────────────────────────────────────────────
    def init(self, *, start_prepare: bool = True) -> bool:
        """Поднять микшер. Возвращает True, если звук доступен."""
        if self.available:
            return True
        try:
            # 44100 — под озвучку (mp3/ogg обычно 44.1 кГц); музыку синтезатор
            # пишет в 16 кГц, микшер сам её пересэмплирует при загрузке.
            pygame.mixer.pre_init(MIXER_RATE, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self.available = True
            self.last_error = None
        except Exception as exc:  # pragma: no cover - зависит от железа
            self.available = False
            self.last_error = str(exc)
            return False
        self._load_sfx()
        if start_prepare:
            self.start_prepare()
        return True

    def shutdown(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.available = False
        self._ready = False
        self._sfx.clear()

    # ── громкость ─────────────────────────────────────────────────────
    def set_volumes(self, *, music: Optional[float] = None, sfx: Optional[float] = None,
                    voice: Optional[bool] = None) -> None:
        if music is not None:
            self.music_volume = max(0.0, min(1.0, float(music)))
            if self.available:
                try:
                    pygame.mixer.music.set_volume(self.music_volume)
                except Exception:
                    pass
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, float(sfx)))
        if voice is not None:
            self.voice_enabled = bool(voice)

    # ── подготовка файлов ─────────────────────────────────────────────
    def cache_dir(self) -> Path:
        try:
            return ensure_save_dir() / "music"
        except Exception:  # pragma: no cover
            return Path.cwd() / "music_cache"

    def track_path(self, name: str) -> Path:
        return self.cache_dir() / f"{name}.wav"

    def tracks_present(self) -> bool:
        return all(self.track_path(name).is_file() for name in MUSIC_TRACKS)

    def start_prepare(self) -> None:
        """Сгенерировать недостающие дорожки в фоновом потоке."""
        if self._preparing or self._ready:
            return
        if self.tracks_present():
            self._ready = True
            return
        self._preparing = True

        def _work() -> None:
            paths: Dict[str, Path] = {}
            try:
                for name in MUSIC_TRACKS:
                    path = self.track_path(name)
                    if not path.is_file():
                        buf, _ = synth.render_track(name)
                        synth.write_wav(path, buf)
                    paths[name] = path
            except Exception as exc:  # pragma: no cover - диск/права
                with self._lock:
                    self.last_error = f"музыка: {exc}"
                    self._preparing = False
                return
            with self._lock:
                self._prepared_paths = paths
                self._ready = True
                self._preparing = False

        self._thread = threading.Thread(target=_work, name="music-synth", daemon=True)
        self._thread.start()

    # ── музыка ────────────────────────────────────────────────────────
    def play_music(self, track: str, *, fade_ms: int = 900) -> None:
        """Включить тему (если она уже готова)."""
        if not track:
            return
        self._want_track = track
        if not self.available:
            return
        if track == self.current_track:
            return
        path = self._prepared_paths.get(track) or self.track_path(track)
        if not path.is_file():
            # дорожки ещё считаются — включим, когда будут готовы
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1, fade_ms=fade_ms)
            self.current_track = track
        except Exception as exc:  # pragma: no cover
            self.last_error = f"музыка: {exc}"

    def stop_music(self, fade_ms: int = 600) -> None:
        self._want_track = None
        self.current_track = None
        if not self.available:
            return
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except Exception:
            pass

    def _load_sfx(self) -> None:
        if not self.available:
            return
        for name in SFX_NAMES:
            try:
                buf = synth.render_sfx(name)
                pcm = synth._to_pcm(buf)
                self._sfx[name] = pygame.mixer.Sound(buffer=pcm.tobytes())
            except Exception:  # pragma: no cover
                continue
        for sound in self._sfx.values():
            sound.set_volume(self.sfx_volume)

    def play_sfx(self, name: str) -> None:
        if not self.available or self.sfx_volume <= 0.001:
            return
        if name == "tick":
            return  # слишком частый: тишина вместо треска
        sound = self._sfx.get(name)
        if not sound:
            return
        try:
            sound.set_volume(self.sfx_volume)
            sound.play()
        except Exception:
            pass

    # ── озвучка ───────────────────────────────────────────────────────
    def voice_path(self, key: str) -> Optional[Path]:
        for ext in VOICE_EXTS:
            path = VOICE_DIR / f"{key}{ext}"
            if path.is_file():
                return path
        return None

    def has_voice(self, key: str) -> bool:
        return self.voice_path(key) is not None

    def voice_length(self, key: str) -> float:
        """Длительность озвучки в секундах (0 — файла нет или микшер недоступен)."""
        if not self.available:
            return 0.0
        path = self.voice_path(key)
        if not path:
            return 0.0
        if key not in self._voice_cache:
            try:
                self._voice_cache[key] = pygame.mixer.Sound(str(path))
            except Exception:  # pragma: no cover
                self._voice_cache[key] = None
        sound = self._voice_cache[key]
        try:
            return float(sound.get_length()) if sound else 0.0
        except Exception:  # pragma: no cover
            return 0.0

    def play_voice(self, key: str) -> bool:
        """Проиграть озвучку по ключу. True — если файл найден и запущен."""
        if not self.available or not self.voice_enabled:
            return False
        path = self.voice_path(key)
        if not path:
            return False
        if key not in self._voice_cache:
            try:
                self._voice_cache[key] = pygame.mixer.Sound(str(path))
            except Exception:  # pragma: no cover
                self._voice_cache[key] = None
        sound = self._voice_cache[key]
        if not sound:
            return False
        try:
            if self._voice_channel is None:
                self._voice_channel = pygame.mixer.Channel(0)
            self._voice_channel.set_volume(min(1.0, self.sfx_volume * 1.1))
            self._voice_channel.play(sound)
            return True
        except Exception:  # pragma: no cover
            return False

    def stop_voice(self) -> None:
        if self._voice_channel:
            try:
                self._voice_channel.stop()
            except Exception:
                pass

    # ── игровой цикл ──────────────────────────────────────────────────
    def update(self) -> None:
        """Вызывать каждый кадр: дозапустить музыку, когда дорожки готовы."""
        if not self.available:
            return
        if not self._ready:
            if self._preparing:
                return
            if self.tracks_present():
                self._ready = True
            else:
                return
        want = self._want_track
        if want and want != self.current_track:
            self.play_music(want)


# единственный движок на игру
audio = AudioEngine()
