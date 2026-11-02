"""Время суток и расписание локаций.

Дело начинается в 9:00, каждый сбор улики, допрос и провал стоят игровых
минут. Теперь у локаций есть часы работы: в банк ночью не пустят, бар днём
закрыт, школа работает до трёх.

Игрок всегда может подождать — кнопка «ЖДАТЬ» в штабе/на карте переносит время
до ближайшего открытия. Тупика нет: офис и улица доступны круглосуточно.

Часы работы берутся из ``location["hours"] = [открытие, закрытие]`` в формате
часов (0–24), иначе — по типу локации.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

START_MINUTE = 9 * 60
DAY_MINUTES = 24 * 60

# тип локации -> [открытие, закрытие]; закрытие меньше открытия = через полночь
TYPE_HOURS: Dict[str, Tuple[int, int]] = {
    "bar": (18, 2),
    "police": (8, 20),
    "school": (8, 15),
    "bank": (9, 17),
    "vault": (9, 17),
    "mansion": (10, 18),
    "shop": (10, 20),
    "apartment": (8, 22),
    "public": (8, 21),
    "crime": (0, 24),
    "warehouse": (0, 24),
    "port": (0, 24),
    "hub": (0, 24),
    "office": (0, 24),
}


def clock(case_time_minutes: int) -> Tuple[int, int, int]:
    """(день, часы, минуты) по общему игровому времени дела."""
    total = START_MINUTE + max(0, int(case_time_minutes or 0))
    day = total // DAY_MINUTES + 1
    minute_of_day = total % DAY_MINUTES
    return day, minute_of_day // 60, minute_of_day % 60


def clock_text(case_time_minutes: int) -> str:
    day, hours, minutes = clock(case_time_minutes)
    return f"День {day} • {hours:02d}:{minutes:02d}"


def time_of_day(case_time_minutes: int) -> int:
    """Минуты от полуночи."""
    return (START_MINUTE + max(0, int(case_time_minutes or 0))) % DAY_MINUTES


def hours_for(location: Optional[Dict]) -> Tuple[int, int]:
    location = location or {}
    raw = location.get("hours")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return int(raw[0]) % 24, int(raw[1]) % 24
        except (TypeError, ValueError):
            pass
    return TYPE_HOURS.get(str(location.get("type", "")), (0, 24))


def is_open_now(location: Optional[Dict], case_time_minutes: int) -> bool:
    open_h, close_h = hours_for(location)
    if open_h == close_h or (open_h, close_h) == (0, 24):
        return True
    now = time_of_day(case_time_minutes)
    start = open_h * 60
    end = close_h * 60
    if start < end:
        return start <= now < end
    # через полночь, например бар 18:00–02:00
    return now >= start or now < end


def _next_opening_minutes(location: Optional[Dict], case_time_minutes: int) -> int:
    """Сколько минут ждать до открытия (0 — уже открыто)."""
    if is_open_now(location, case_time_minutes):
        return 0
    open_h, _close_h = hours_for(location)
    now = time_of_day(case_time_minutes)
    target = open_h * 60
    delta = (target - now) % DAY_MINUTES
    return delta or DAY_MINUTES


def wait_for(location: Optional[Dict], case_time_minutes: int) -> int:
    """Минуты, которые нужно промотать, чтобы локация открылась."""
    return _next_opening_minutes(location, case_time_minutes)


def hours_label(location: Optional[Dict]) -> str:
    open_h, close_h = hours_for(location)
    if open_h == close_h or (open_h, close_h) == (0, 24):
        return "круглосуточно"
    return f"{open_h:02d}:00–{close_h:02d}:00"


def closed_reason(location: Optional[Dict], case_time_minutes: int) -> str:
    """Текст для карточки закрытой локации."""
    if is_open_now(location, case_time_minutes):
        return ""
    wait = _next_opening_minutes(location, case_time_minutes)
    open_h, _ = hours_for(location)
    return f"Закрыто до {open_h:02d}:00 — подождать {wait} мин"


def character_present(character: Optional[Dict], case_time_minutes: int) -> bool:
    """На месте ли персонаж в это время."""
    character = character or {}
    raw = character.get("schedule")
    if not raw:
        return True
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and all(
        isinstance(value, (int, float)) for value in raw
    ):
        raw = [raw]
    now = time_of_day(case_time_minutes)
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            start, end = int(item[0]) % 24, int(item[1]) % 24
        except (TypeError, ValueError):
            continue
        start, end = start * 60, end * 60
        if start == end:
            return True
        if start < end:
            if start <= now < end:
                return True
        elif now >= start or now < end:
            return True
    return False


def character_return(character: Optional[Dict], case_time_minutes: int) -> str:
    """Когда персонаж вернётся: строка для карточки локации."""
    character = character or {}
    raw = character.get("schedule")
    if not raw or character_present(character, case_time_minutes):
        return ""
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and all(
        isinstance(value, (int, float)) for value in raw
    ):
        raw = [raw]
    now = time_of_day(case_time_minutes)
    best = None
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            start = int(item[0]) % 24
        except (TypeError, ValueError):
            continue
        delta = (start * 60 - now) % DAY_MINUTES
        if delta and (best is None or delta < best):
            best = delta
    if best is None:
        return "Сейчас его здесь нет"
    return f"Вернётся примерно через {best} мин"


def nearest_opening(case: Optional[Dict], state) -> Tuple[Optional[Dict], int]:
    """Ближайшая закрытая доступная локация и сколько до её открытия."""
    best_loc: Optional[Dict] = None
    best_wait = 0
    minutes = int(getattr(state, "case_time_minutes", 0) or 0)
    for location in (case or {}).get("locations", []):
        if is_open_now(location, minutes):
            continue
        wait = _next_opening_minutes(location, minutes)
        if wait and (best_loc is None or wait < best_wait):
            best_loc, best_wait = location, wait
    return best_loc, best_wait


def advance(state, minutes: int) -> int:
    """Промотать время дела. Возвращает новое значение."""
    minutes = max(0, int(minutes or 0))
    state.case_time_minutes = int(getattr(state, "case_time_minutes", 0) or 0) + minutes
    return state.case_time_minutes


def wait_until_open(state, case: Optional[Dict], location: Optional[Dict]) -> int:
    """Промотать до открытия локации (или час, если она открыта)."""
    wait = wait_for(location, int(getattr(state, "case_time_minutes", 0) or 0))
    if wait <= 0:
        wait = 60
    return advance(state, wait)


def open_locations(case: Optional[Dict], state) -> List[Dict]:
    minutes = int(getattr(state, "case_time_minutes", 0) or 0)
    return [loc for loc in (case or {}).get("locations", []) if is_open_now(loc, minutes)]


__all__ = [
    "DAY_MINUTES",
    "START_MINUTE",
    "TYPE_HOURS",
    "advance",
    "character_present",
    "character_return",
    "clock",
    "clock_text",
    "closed_reason",
    "hours_for",
    "hours_label",
    "is_open_now",
    "nearest_opening",
    "open_locations",
    "time_of_day",
    "wait_for",
    "wait_until_open",
]
