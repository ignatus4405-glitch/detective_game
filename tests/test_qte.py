"""Тесты редкого QTE «драка в баре»."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from detective_game import qte  # noqa: E402


def test_prompts_are_deterministic():
    first = qte.prompts_for("missing_chess:0")
    assert first == qte.prompts_for("missing_chess:0")
    assert first != qte.prompts_for("bank_heist:0") or len(set(first)) > 1
    assert len(first) == qte.ROUNDS
    assert all(prompt in qte.PROMPTS for prompt in first)
    for a, b in zip(first, first[1:], strict=False):
        assert a != b


def test_prompt_keys_cover_all_directions():
    for direction in qte.PROMPTS:
        assert direction in qte.PROMPT_KEYS


def test_perfect_run_wins():
    fight = qte.BarFight(seed="perfect")
    assert fight.prompt
    for _ in range(qte.ROUNDS):
        direction = fight.prompt
        assert fight.press(direction) is True
    assert fight.success
    assert not fight.failed
    assert fight.hits == qte.ROUNDS
    assert "устояли" in fight.result_text


def test_two_misses_fail():
    fight = qte.BarFight(seed="miss")
    for _ in range(2):
        wrong = next(d for d in qte.PROMPTS if d != fight.prompt)
        assert fight.press(wrong) is False
    assert fight.failed
    assert not fight.success
    assert "вытолкали" in fight.result_text


def test_timer_expires_as_miss():
    fight = qte.BarFight(seed="timer", window=0.5)
    fight.update(0.2)
    assert not fight.finished
    fight.update(5.0)
    assert fight.misses == 1
    assert fight.index == 1
    assert not fight.finished


def test_update_ignores_bad_dt_and_finished():
    fight = qte.BarFight(seed="edge")
    fight.update(0)
    fight.update(-1)
    assert fight.remaining == qte.WINDOW
    fight.success = True
    fight.update(1.0)
    assert fight.finished


def test_press_after_finish_does_nothing():
    fight = qte.BarFight(seed="done")
    fight.success = True
    assert fight.press(qte.PROMPTS[0]) is False
    assert fight.finished


def test_reward_values():
    assert qte.reward(True)["reputation"] == 1
    assert qte.reward(True)["money"] == 40
    assert qte.reward(False)["time"] == 20
    assert qte.reward(False)["money"] == 0


def test_chance_is_stable_and_per_case():
    from detective_game.ui import qte_view

    assert qte_view.chance_for("missing_chess") == qte_view.chance_for("missing_chess")
    values = {qte_view.chance_for(case_id) for case_id in ("missing_chess", "bank_heist", "tutorial")}
    assert values <= {True, False}
