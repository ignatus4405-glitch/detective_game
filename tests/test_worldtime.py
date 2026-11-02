"""Тесты времени суток и расписания локаций."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from detective_game import worldtime  # noqa: E402
from detective_game.data import list_cases  # noqa: E402
from detective_game.game_state import GameState  # noqa: E402

BAR = {"id": "bar", "type": "bar"}
BANK = {"id": "bank", "type": "bank"}
OFFICE = {"id": "office", "type": "office"}


def _at(hours, minutes=0):
    """Минуты дела для заданного времени суток (до 9:00 — уже второй день)."""
    absolute = (hours * 60 + minutes) % worldtime.DAY_MINUTES
    if absolute < worldtime.START_MINUTE:
        absolute += worldtime.DAY_MINUTES
    return absolute - worldtime.START_MINUTE


def test_start_is_nine_am():
    assert worldtime.START_MINUTE == 540
    assert worldtime.clock(0) == (1, 9, 0)
    assert worldtime.clock_text(0) == "День 1 • 09:00"


def test_clock_wraps_into_next_days():
    assert worldtime.clock(60 * 15) == (2, 0, 0)
    assert worldtime.clock_text(60 * 15) == "День 2 • 00:00"
    assert worldtime.clock(60 * 39) == (3, 0, 0)
    assert worldtime.clock(-100) == (1, 9, 0)


def test_hours_for_types_and_overrides():
    assert worldtime.hours_for(BAR) == (18, 2)
    assert worldtime.hours_for(BANK) == (9, 17)
    assert worldtime.hours_for(OFFICE) == (0, 24)
    assert worldtime.hours_for({"type": "unknown"}) == (0, 24)
    assert worldtime.hours_for(None) == (0, 24)
    assert worldtime.hours_for({"type": "bar", "hours": [12, 16]}) == (12, 16)
    assert worldtime.hours_for({"type": "bar", "hours": ["a", "b"]}) == (18, 2)
    assert worldtime.hours_for({"type": "bar", "hours": [25, 3]}) == (1, 3)


def test_open_during_day():
    assert worldtime.is_open_now(BANK, _at(10))
    assert not worldtime.is_open_now(BANK, _at(8))
    assert not worldtime.is_open_now(BANK, _at(17))
    assert worldtime.is_open_now(OFFICE, _at(3))


def test_bar_open_across_midnight():
    assert worldtime.is_open_now(BAR, _at(19))
    assert worldtime.is_open_now(BAR, _at(23, 59))
    assert worldtime.is_open_now(BAR, _at(1, 30))
    assert not worldtime.is_open_now(BAR, _at(2))
    assert not worldtime.is_open_now(BAR, _at(12))


def test_wait_for_counts_minutes_until_open():
    # в 9:00 бар откроется в 18:00 — 540 минут
    assert worldtime.wait_for(BAR, 0) == 540
    assert worldtime.wait_for(BANK, _at(8)) == 60
    assert worldtime.wait_for(OFFICE, _at(3)) == 0


def test_hours_label_and_closed_reason():
    assert worldtime.hours_label(OFFICE) == "круглосуточно"
    assert worldtime.hours_label(BAR) == "18:00–02:00"
    assert worldtime.closed_reason(BANK, _at(10)) == ""
    reason = worldtime.closed_reason(BANK, _at(8))
    assert "09:00" in reason and "подождать 60" in reason


def test_advance_and_wait_until_open():
    state = GameState()
    assert worldtime.advance(state, 90) == 90
    assert worldtime.advance(state, -50) == 90
    assert worldtime.advance(state, 0) == 90
    # в 10:30 банк уже открыт — «подождать» промотает час
    worldtime.wait_until_open(state, {}, BANK)
    assert state.case_time_minutes == 150
    # закрытый банк: ждём ровно до открытия
    state.case_time_minutes = _at(8)
    worldtime.wait_until_open(state, {}, BANK)
    # 8:00 второго дня → 9:00 второго дня
    assert state.case_time_minutes == worldtime.DAY_MINUTES
    assert worldtime.clock_text(state.case_time_minutes) == "День 2 • 09:00"
    assert worldtime.is_open_now(BANK, state.case_time_minutes)


def test_nearest_opening_and_open_locations():
    case = {
        "locations": [OFFICE, BANK, BAR],
    }
    state = GameState()
    state.case_time_minutes = _at(8)
    location, wait = worldtime.nearest_opening(case, state)
    assert location["id"] == "bank"
    assert wait == 60
    ids = {loc["id"] for loc in worldtime.open_locations(case, state)}
    assert ids == {"office"}


def test_nearest_opening_with_nothing_closed():
    state = GameState()
    location, wait = worldtime.nearest_opening({"locations": [OFFICE]}, state)
    assert location is None and wait == 0


def test_time_of_day():
    assert worldtime.time_of_day(0) == 540
    assert worldtime.time_of_day(60 * 15) == 0


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_every_case_has_round_the_clock_hub(case):
    """Даже если все закрыты, офис доступен — тупика нет."""
    by_id = {loc["id"]: loc for loc in case["locations"]}
    assert worldtime.is_open_now(by_id["office"], _at(4))
    # в любой момент суток хотя бы одна локация открыта
    for hour in range(24):
        minutes = _at(hour, 30)
        opened = [loc for loc in case["locations"] if worldtime.is_open_now(loc, minutes)]
        assert opened, (case["id"], hour)


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_hub_is_always_open(case):
    """Офис — точка возврата: он открыт и в 9:00, и ночью."""
    office = next(loc for loc in case["locations"] if loc["id"] == "office")
    assert worldtime.is_open_now(office, 0)
    assert worldtime.is_open_now(office, _at(4))


# ── расписание персонажей ─────────────────────────────────────────


def test_character_without_schedule_is_always_present():
    assert worldtime.character_present({}, 0)
    assert worldtime.character_present({"schedule": []}, 0)


def test_character_schedule_day_window():
    teacher = {"schedule": [8, 15]}
    assert worldtime.character_present(teacher, _at(9))
    assert not worldtime.character_present(teacher, _at(16))


def test_character_schedule_across_midnight():
    barmen = {"schedule": [18, 2]}
    assert worldtime.character_present(barmen, _at(21))
    assert worldtime.character_present(barmen, _at(1))
    assert not worldtime.character_present(barmen, _at(12))


def test_character_return_text():
    teacher = {"schedule": [8, 15]}
    assert worldtime.character_return(teacher, _at(9)) == ""
    text = worldtime.character_return(teacher, _at(16))
    assert "Вернётся" in text
    assert not worldtime.character_present(teacher, _at(16))


@pytest.mark.parametrize("case", list_cases(), ids=lambda c: c["id"])
def test_schedules_are_valid(case):
    for character in case["characters"]:
        raw = character.get("schedule")
        if not raw:
            continue
        assert len(raw) == 2
        assert all(isinstance(value, int) and 0 <= value <= 24 for value in raw)
