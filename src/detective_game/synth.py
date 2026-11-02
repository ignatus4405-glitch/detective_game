"""Синтез звука без внешних зависимостей и без файлов в репозитории.

Музыка и звуки в игре генерируются кодом (чистый Python + ``wave`` из
стандартной библиотеки). Это даёт нуар-атмосферу без мегабайтов ассетов и без
проблем с кодеками: один и тот же WAV читается везде, где есть pygame.

Синтез сознательно простой: табличные осцилляторы, ADSR-огибающая, шум для
тарелок. Этого достаточно для лоу-фай нуара, и всё считается за секунды.
"""

from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

SAMPLE_RATE = 16000
_TABLE_SIZE = 1024

# ── осцилляторы ────────────────────────────────────────────────────────


def _build_table(kind: str) -> List[float]:
    table = []
    for i in range(_TABLE_SIZE):
        phase = i / _TABLE_SIZE
        if kind == "sine":
            value = math.sin(2 * math.pi * phase)
        elif kind == "triangle":
            value = 4 * abs(phase - 0.5) - 1
        elif kind == "square":
            value = 1.0 if phase < 0.5 else -1.0
            # немного сглаживаем — чистый квадрат в нуаре звучит как 8-бит
            value *= 0.6
        elif kind == "saw":
            value = 2 * phase - 1
        else:  # мягкий «орган» — смесь синуса и треугольника
            value = 0.6 * math.sin(2 * math.pi * phase) + 0.4 * (4 * abs(phase - 0.5) - 1)
        table.append(value)
    # убираем щелчок на стыке периода
    table.append(table[0])
    return table


TABLES: Dict[str, List[float]] = {
    kind: _build_table(kind) for kind in ("sine", "triangle", "square", "saw", "organ")
}


def _envelope(pos: float, length: int, attack: float, release: float) -> float:
    """Простая ADSR: атака, ровная часть, спад."""
    if length <= 0:
        return 0.0
    t = pos / SAMPLE_RATE
    total = length / SAMPLE_RATE
    a = max(0.0005, attack)
    r = max(0.0005, min(release, total - 0.0005))
    if t < a:
        return t / a
    if t > total - r:
        return max(0.0, (total - t) / r)
    return 1.0


def add_note(
    buf: List[float],
    start: float,
    freq: float,
    dur: float,
    amp: float = 0.2,
    kind: str = "triangle",
    attack: float = 0.008,
    release: float = 0.22,
    vibrato: float = 0.0,
    vibrato_hz: float = 5.0,
) -> None:
    """Добавить ноту в буфер (в секундах начало и длительность)."""
    if freq <= 0 or dur <= 0 or amp <= 0:
        return
    table = TABLES.get(kind, TABLES["triangle"])
    size = len(table) - 1
    length = min(int(dur * SAMPLE_RATE), len(buf) - int(start * SAMPLE_RATE))
    if length <= 0:
        return
    offset = int(start * SAMPLE_RATE)
    phase = 0.0
    step = freq / SAMPLE_RATE * size
    for i in range(length):
        env = _envelope(i, length, attack, release)
        if env <= 0:
            continue
        index = int(phase) % size
        # линейная интерполяция между соседними значениями таблицы
        frac = phase - int(phase)
        value = table[index] * (1 - frac) + table[index + 1] * frac
        if vibrato:
            value *= 1.0 + vibrato * math.sin(2 * math.pi * vibrato_hz * i / SAMPLE_RATE)
        buf[offset + i] += value * amp * env
        phase += step


def add_noise(
    buf: List[float],
    start: float,
    dur: float,
    amp: float = 0.05,
    decay: float = 40.0,
    rng: random.Random | None = None,
    hat: bool = False,
) -> None:
    """Шумовой удар — «щётка» по тарелке или хэт."""
    rng = rng or random.Random(7)
    offset = int(start * SAMPLE_RATE)
    length = min(int(dur * SAMPLE_RATE), len(buf) - offset)
    if length <= 0 or offset < 0:
        return
    prev = 0.0
    for i in range(length):
        t = i / SAMPLE_RATE
        env = math.exp(-decay * t)
        if env < 0.0005:
            break
        value = rng.uniform(-1.0, 1.0)
        if hat:
            # грубый хайпас: разница соседних отсчётов
            out = value - prev
            prev = value
        else:
            out = value
        buf[offset + i] += out * amp * env


def _to_pcm(buf: Sequence[float]) -> array:
    pcm = array("h")
    for value in buf:
        clipped = max(-1.0, min(1.0, value))
        pcm.append(int(clipped * 32000))
    return pcm


def write_wav(path: Path, buf: Sequence[float], loops: bool = False) -> Path:
    """Записать буфер в 16-битный моно-WAV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(_to_pcm(buf).tobytes())
    tmp.replace(path)
    if loops:
        _ = path.stat().st_size
    return path


# ── музыка ─────────────────────────────────────────────────────────────

# частоты нот (ля первой октавы = 440)
def note_hz(name: str) -> float:
    """Частота ноты по имени: C4, F#3, Bb2 …"""
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    name = name.strip()
    step = names[name[0].upper()]
    rest = name[1:]
    if rest.startswith("#"):
        step += 1
        rest = rest[1:]
    elif rest.startswith("b"):
        step -= 1
        rest = rest[1:]
    octave = int(rest)
    midi = 12 * (octave + 1) + step
    return 440.0 * (2 ** ((midi - 69) / 12))


def _bars_to_buf(seconds: float) -> List[float]:
    return [0.0] * int(seconds * SAMPLE_RATE)


def _chord(
    buf: List[float],
    start: float,
    dur: float,
    notes: Sequence[str],
    amp: float = 0.05,
    kind: str = "organ",
    attack: float = 0.35,
    release: float = 1.2,
) -> None:
    for name in notes:
        add_note(buf, start, note_hz(name), dur, amp=amp, kind=kind, attack=attack, release=release)


def _bass_line(
    buf: List[float],
    start: float,
    beat: float,
    notes: Sequence[str],
    amp: float = 0.22,
    beats_per_note: float = 1.0,
) -> None:
    for i, name in enumerate(notes):
        add_note(
            buf,
            start + i * beat * beats_per_note,
            note_hz(name),
            beat * beats_per_note * 0.9,
            amp=amp,
            kind="sine",
            attack=0.01,
            release=beat * 0.5,
        )


def _ride_pattern(buf: List[float], start: float, beat: float, bars: int, amp: float = 0.035) -> None:
    rng = random.Random(11)
    for bar in range(bars):
        for beat_i in range(4):
            t = start + (bar * 4 + beat_i) * beat
            add_noise(buf, t, beat * 0.55, amp=amp, decay=26.0, rng=rng, hat=True)
            if beat_i in (1, 3):
                add_noise(buf, t + beat * 0.5, beat * 0.35, amp=amp * 0.6, decay=32.0, rng=rng)


def _pluck(
    buf: List[float],
    start: float,
    notes: Sequence[str],
    amp: float = 0.08,
    spacing: float = 0.0,
    kind: str = "triangle",
) -> None:
    for i, name in enumerate(notes):
        add_note(
            buf,
            start + i * spacing,
            note_hz(name),
            1.6,
            amp=amp,
            kind=kind,
            attack=0.004,
            release=1.4,
        )


def track_noir() -> Tuple[List[float], float]:
    """Главная тема: медленный нуар-джаз, 8 тактов."""
    bpm = 76
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    # Dm7 | Gm7 | A7 | Dm7 | Bb maj7 | Gm7 | A7b9 | Dm7
    chords = [
        ("D3", "F3", "A3", "C4"),
        ("G2", "Bb2", "D3", "F3"),
        ("A2", "C#3", "E3", "G3"),
        ("D3", "F3", "A3", "C4"),
        ("Bb2", "D3", "F3", "A3"),
        ("G2", "Bb2", "D3", "F3"),
        ("A2", "C#3", "E3", "Bb3"),
        ("D3", "F3", "A3", "C4"),
    ]
    for bar, chord in enumerate(chords):
        start = bar * 4 * beat
        _chord(buf, start, 4 * beat, chord, amp=0.035, attack=0.5, release=1.0)
        root = chord[0]
        fifth = chord[2]
        bass = [root, fifth, root, chord[3]]
        _bass_line(buf, start, beat, bass, amp=0.16, beats_per_note=1.0)
    _ride_pattern(buf, 0.0, beat, bars, amp=0.026)
    # редкие «рояльные» капли
    for bar, t in ((0, 1.5), (2, 2.5), (3, 0.5), (5, 1.0), (6, 2.0), (7, 1.5)):
        _pluck(buf, bar * 4 * beat + t * beat, ("A4", "D5"), amp=0.05, spacing=0.18)
    _fade_edges(buf)
    return buf, total


def track_investigation() -> Tuple[List[float], float]:
    """Фоновая тема расследования: разреженные аккорды и шаги баса."""
    bpm = 64
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    chords = [
        ("D3", "A3", "E4"),
        ("D3", "A3", "F4"),
        ("C3", "G3", "E4"),
        ("D3", "A3", "E4"),
        ("Bb2", "F3", "D4"),
        ("A2", "E3", "C#4"),
        ("D3", "A3", "E4"),
        ("D3", "F3", "A3"),
    ]
    for bar, chord in enumerate(chords):
        start = bar * 4 * beat
        _chord(buf, start, 4 * beat, chord, amp=0.03, attack=0.8, release=1.6)
        add_note(
            buf,
            start,
            note_hz(chord[0]) / 2,
            4 * beat,
            amp=0.15,
            kind="sine",
            attack=0.05,
            release=1.4,
        )
        if bar % 2 == 1:
            _pluck(buf, start + 2 * beat, ("A4", "C5", "E5"), amp=0.04, spacing=0.22)
    _ride_pattern(buf, 0.0, beat * 2, bars // 2, amp=0.02)
    _fade_edges(buf)
    return buf, total


def track_tension() -> Tuple[List[float], float]:
    """Напряжение: пульс, низкий дрон и редкие удары."""
    bpm = 96
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    for bar in range(bars):
        start = bar * 4 * beat
        for beat_i in range(4):
            add_note(
                buf,
                start + beat_i * beat,
                note_hz("D2"),
                beat * 0.5,
                amp=0.2 if beat_i in (0, 2) else 0.12,
                kind="square",
                attack=0.004,
                release=beat * 0.3,
            )
        add_note(buf, start, note_hz("D3"), 4 * beat, amp=0.05, kind="saw", attack=1.2, release=1.2)
        if bar % 2 == 0:
            _pluck(buf, start + 2.5 * beat, ("Eb5",), amp=0.06, kind="triangle")
    rng = random.Random(23)
    for bar in range(bars):
        add_noise(buf, bar * 4 * beat + 3.5 * beat, 0.4, amp=0.05, decay=14.0, rng=rng)
    _fade_edges(buf)
    return buf, total


def track_success() -> Tuple[List[float], float]:
    """Короткая победная фраза."""
    beat = 0.42
    buf = _bars_to_buf(beat * 8 + 1.6)
    _pluck(buf, 0.0, ("D4", "F4", "A4", "D5"), amp=0.11, spacing=beat)
    _chord(buf, 0.0, 1.9, ("D3", "A3", "F4"), amp=0.05, attack=0.1, release=1.2)
    _pluck(buf, beat * 4, ("A4", "D5", "F5"), amp=0.09, spacing=0.16)
    _fade_edges(buf)
    return buf, len(buf) / SAMPLE_RATE


def track_failure() -> Tuple[List[float], float]:
    """Короткая мрачная фраза на провал."""
    beat = 0.5
    buf = _bars_to_buf(beat * 6 + 1.2)
    for i, name in enumerate(("D3", "C#3", "C3", "B2")):
        add_note(buf, i * beat, note_hz(name), beat * 1.1, amp=0.16, kind="organ", attack=0.02, release=0.5)
    _chord(buf, beat * 2, 2.2, ("D3", "F3", "Ab3"), amp=0.05, attack=0.3, release=1.6)
    _fade_edges(buf)
    return buf, len(buf) / SAMPLE_RATE


def track_lounge() -> Tuple[List[float], float]:
    """Бар «Синяя Луна»: ленивый свинг, контрабас и стаканы."""
    bpm = 100
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    # Cm7 | F7 | Bbmaj7 | Ebmaj7 | Am7 | D7 | Gm7 | C7
    chords = [
        ("C3", "Eb3", "G3", "Bb3"),
        ("F2", "A2", "C3", "Eb3"),
        ("Bb2", "D3", "F3", "A3"),
        ("Eb3", "G3", "Bb3", "D4"),
        ("A2", "C3", "E3", "G3"),
        ("D3", "F#3", "A3", "C4"),
        ("G2", "Bb2", "D3", "F3"),
        ("C3", "E3", "G3", "Bb3"),
    ]
    rng = random.Random(31)
    for bar, chord in enumerate(chords):
        start = bar * 4 * beat
        # «духовые» короткие стабы на второй и четвёртой доле
        for offset in (1, 3):
            _chord(
                buf, start + offset * beat, beat * 0.55, chord,
                amp=0.026, attack=0.03, release=0.4,
            )
        # контрабас: простая «прогулка» по аккорду
        walk = [chord[0], chord[2], chord[1], chord[3]]
        for i, name in enumerate(walk):
            add_note(
                buf,
                start + i * beat,
                note_hz(name) / 2,
                beat * 0.8,
                amp=0.20,
                kind="sine",
                attack=0.012,
                release=beat * 0.45,
            )
    # свингующие «тарелки»
    for bar in range(bars):
        start = bar * 4 * beat
        for i in range(4):
            add_noise(buf, start + i * beat, 0.12, amp=0.02, decay=45.0, rng=rng, hat=True)
            add_noise(
                buf,
                start + i * beat + beat * 2 / 3,
                0.08,
                amp=0.012,
                decay=50.0,
                rng=rng,
                hat=True,
            )
    # редкие фортепианные «капли» на слабой доле
    for bar, t0 in ((1, 3.5), (3, 2.5), (5, 3.0), (7, 1.5)):
        _pluck(buf, bar * 4 * beat + t0 * beat, ("Bb4", "D5"), amp=0.045, spacing=0.16)
    _fade_edges(buf)
    return buf, total


def track_harbor() -> Tuple[List[float], float]:
    """Порт: туман, низкий гудок и далёкий буй."""
    bpm = 56
    beat = 60.0 / bpm
    bars = 6
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    # дрон: две низкие ноты на весь трек
    for bar in range(bars):
        start = bar * 4 * beat
        add_note(
            buf, start, note_hz("D2"), 4 * beat, amp=0.10, kind="organ", attack=0.9, release=1.6
        )
        add_note(buf, start, note_hz("A2"), 4 * beat, amp=0.05, kind="sine", attack=1.1, release=1.6)
    # гудок парохода — дважды, как в тумане
    for t0 in (beat * 3, beat * 17):
        add_note(buf, t0, note_hz("F2"), 2.2, amp=0.17, kind="organ", attack=0.25, release=0.9)
        add_note(buf, t0, note_hz("C3"), 2.2, amp=0.08, kind="sine", attack=0.2, release=1.2)
    # далёкий буй
    for bar in (1, 3, 5):
        _pluck(buf, bar * 4 * beat + 2 * beat, ("A5",), amp=0.035, kind="sine")
    # «ветер»: медленные шумовые волны
    rng = random.Random(41)
    for bar in range(bars):
        add_noise(buf, bar * 4 * beat, 4 * beat * 0.95, amp=0.012, decay=0.4, rng=rng)
    _fade_edges(buf)
    return buf, total


def track_precinct() -> Tuple[List[float], float]:
    """Участок: стук машинки, гул лампы и усталые аккорды."""
    bpm = 88
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    chords = [
        ("D3", "F3", "A3"),
        ("D3", "F3", "Bb3"),
        ("C3", "E3", "G3"),
        ("D3", "F3", "A3"),
        ("Bb2", "D3", "F3"),
        ("A2", "C#3", "E3"),
        ("D3", "F3", "A3"),
        ("D3", "F3", "A3"),
    ]
    for bar, chord in enumerate(chords):
        start = bar * 4 * beat
        _chord(buf, start, 4 * beat, chord, amp=0.026, attack=0.7, release=1.3)
        add_note(
            buf,
            start,
            note_hz(chord[0]) / 2,
            4 * beat,
            amp=0.12,
            kind="sine",
            attack=0.1,
            release=1.2,
        )
    # машинка: дробный стук, будто кто-то печатает отчёт
    rng = random.Random(53)
    for bar in range(bars):
        for i in range(6):
            t0 = bar * 4 * beat + (i * 0.62 + rng.uniform(0.0, 0.1)) * beat
            add_noise(buf, t0, 0.045, amp=0.05, decay=70.0, rng=rng, hat=True)
    # редкая мелодия «кларнета» — по одной ноте на два такта
    for bar, name in ((0, "A4"), (2, "Bb4"), (4, "F4"), (6, "E4")):
        add_note(
            buf,
            bar * 4 * beat + beat,
            note_hz(name),
            beat * 1.6,
            amp=0.06,
            kind="triangle",
            attack=0.05,
            release=0.5,
        )
    _fade_edges(buf)
    return buf, total


def track_mystery() -> Tuple[List[float], float]:
    """Тайна: разреженные высокие ноты и целотонный ряд."""
    bpm = 66
    beat = 60.0 / bpm
    bars = 6
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    # дрон с биениями: две близкие низкие ноты
    add_note(buf, 0.0, note_hz("D2"), total, amp=0.09, kind="sine", attack=2.0, release=2.5)
    add_note(buf, 0.0, note_hz("D2") * 1.006, total, amp=0.06, kind="sine", attack=2.5, release=2.5)
    # целотонный ряд: D, E, F#, G#, A#, C
    notes = ["D4", "E4", "F#4", "G#4", "A#4", "C5", "A#4", "G#4", "F#4", "E4"]
    for i, name in enumerate(notes):
        add_note(
            buf,
            i * 2 * beat,
            note_hz(name),
            1.4,
            amp=0.045,
            kind="triangle",
            attack=0.02,
            release=1.1,
        )
    # глухие удары где-то за стеной
    rng = random.Random(67)
    for bar in (1, 3, 5):
        add_note(
            buf,
            bar * 4 * beat,
            note_hz("D2") / 2,
            0.7,
            amp=0.18,
            kind="sine",
            attack=0.005,
            release=0.5,
        )
        add_noise(buf, bar * 4 * beat + 2 * beat, 0.5, amp=0.02, decay=18.0, rng=rng)
    _fade_edges(buf)
    return buf, total


def track_chase() -> Tuple[List[float], float]:
    """Погоня: частый пульс, стабы и «дыхание» баса — для обвинения."""
    bpm = 138
    beat = 60.0 / bpm
    bars = 8
    total = bars * 4 * beat
    buf = _bars_to_buf(total)
    progression = [
        ("D3", "F3", "A3"),
        ("D3", "F3", "A3"),
        ("Bb2", "D3", "F3"),
        ("C3", "E3", "G3"),
    ]
    rng = random.Random(79)
    for bar in range(bars):
        start = bar * 4 * beat
        chord = progression[bar % len(progression)]
        _chord(buf, start, 2 * beat, chord, amp=0.03, kind="saw", attack=0.05, release=0.4)
        _chord(
            buf,
            start + 2 * beat,
            2 * beat,
            chord,
            amp=0.024,
            kind="saw",
            attack=0.05,
            release=0.4,
        )
        # восьмые баса
        for i in range(8):
            add_note(
                buf,
                start + i * beat / 2,
                note_hz(chord[0]) / 2,
                beat * 0.42,
                amp=0.19 if i % 2 == 0 else 0.11,
                kind="sine",
                attack=0.004,
                release=beat * 0.25,
            )
        # «малый барабан» на 2 и 4, хэт по восьмым
        for i in range(8):
            add_noise(buf, start + i * beat / 2, 0.06, amp=0.018, decay=60.0, rng=rng, hat=True)
        for i in (1, 3):
            add_noise(buf, start + i * beat, 0.18, amp=0.06, decay=26.0, rng=rng)
        # короткие стабы духовых
        for offset in (1.5, 3.5):
            _chord(
                buf,
                start + offset * beat,
                beat * 0.3,
                chord,
                amp=0.022,
                kind="square",
                attack=0.004,
                release=0.2,
            )
    _fade_edges(buf)
    return buf, total


TRACKS = {
    "noir": track_noir,
    "investigation": track_investigation,
    "tension": track_tension,
    "success": track_success,
    "failure": track_failure,
    "lounge": track_lounge,
    "harbor": track_harbor,
    "precinct": track_precinct,
    "mystery": track_mystery,
    "chase": track_chase,
}

# ── звуковые эффекты ──────────────────────────────────────────────────


def sfx_click() -> List[float]:
    buf = _bars_to_buf(0.12)
    add_note(buf, 0.0, 1350, 0.05, amp=0.20, kind="square", attack=0.001, release=0.03)
    add_note(buf, 0.01, 900, 0.06, amp=0.10, kind="triangle", attack=0.001, release=0.05)
    return buf


def sfx_clue() -> List[float]:
    buf = _bars_to_buf(0.9)
    for i, name in enumerate(("A4", "C5", "E5", "A5")):
        add_note(buf, i * 0.075, note_hz(name), 0.55, amp=0.13, kind="triangle", attack=0.004, release=0.4)
    return buf


def sfx_page() -> List[float]:
    buf = _bars_to_buf(0.3)
    rng = random.Random(5)
    add_noise(buf, 0.0, 0.28, amp=0.08, decay=9.0, rng=rng, hat=True)
    return buf


def sfx_success() -> List[float]:
    buf = _bars_to_buf(1.1)
    for i, name in enumerate(("D4", "A4", "D5")):
        add_note(buf, i * 0.12, note_hz(name), 0.8, amp=0.16, kind="triangle", attack=0.005, release=0.6)
    return buf


def sfx_fail() -> List[float]:
    buf = _bars_to_buf(0.8)
    add_note(buf, 0.0, 220, 0.35, amp=0.18, kind="saw", attack=0.005, release=0.25)
    add_note(buf, 0.18, 160, 0.5, amp=0.18, kind="saw", attack=0.005, release=0.35)
    return buf


def sfx_tick() -> List[float]:
    buf = _bars_to_buf(0.06)
    add_note(buf, 0.0, 2200, 0.03, amp=0.12, kind="square", attack=0.001, release=0.02)
    return buf


def sfx_dial() -> List[float]:
    buf = _bars_to_buf(0.14)
    add_note(buf, 0.0, 480, 0.05, amp=0.22, kind="square", attack=0.001, release=0.04)
    add_noise(buf, 0.0, 0.09, amp=0.05, decay=40.0, rng=random.Random(3))
    return buf


def sfx_type() -> List[float]:
    buf = _bars_to_buf(0.04)
    add_note(buf, 0.0, 620, 0.02, amp=0.05, kind="square", attack=0.001, release=0.015)
    return buf


def sfx_slide() -> List[float]:
    buf = _bars_to_buf(0.45)
    rng = random.Random(9)
    add_noise(buf, 0.0, 0.42, amp=0.06, decay=5.0, rng=rng, hat=True)
    add_note(buf, 0.0, 160, 0.4, amp=0.10, kind="saw", attack=0.05, release=0.3)
    return buf


SFX = {
    "click": sfx_click,
    "clue": sfx_clue,
    "page": sfx_page,
    "success": sfx_success,
    "fail": sfx_fail,
    "tick": sfx_tick,
    "dial": sfx_dial,
    "type": sfx_type,
    "slide": sfx_slide,
}


def _fade_edges(buf: List[float], ms: int = 30) -> None:
    """Плавно убрать щелчки на границах лупа."""
    n = min(len(buf) // 2, int(SAMPLE_RATE * ms / 1000))
    for i in range(n):
        k = i / n
        buf[i] *= k
        buf[-1 - i] *= k


def render_track(name: str) -> Tuple[List[float], float]:
    fn = TRACKS.get(name)
    if not fn:
        raise KeyError(f"нет такой темы: {name}")
    return fn()


def render_sfx(name: str) -> List[float]:
    fn = SFX.get(name)
    if not fn:
        raise KeyError(f"нет такого звука: {name}")
    return fn()
