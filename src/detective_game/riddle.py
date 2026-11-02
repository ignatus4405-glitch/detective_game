"""Загадки с кодовым замком: не рефлексы, а размышление.

Часть улик в больших делах лежит под кодовым замком. Код не угадывается:
он выводится из текста загадки и фактов дела (время на табло, часы работы,
номер ячейки, долг в расписке). Неверный код стоит игровых минут, подсказка —
тоже, но меньше: перебирать вслепую невыгодно.

Спецификация живёт в данных дела::

    "riddle": {
      "id": "lock_ticket",
      "title": "КАМЕРА ХРАНЕНИЯ",
      "prompt": "Пропажу заметили через пять минут после отправления поезда...",
      "answer": "1610",
      "hint": "Поезд ушёл в 16:05 — прибавьте пять минут.",
      "minutes": 3
    }

Модуль чистый: ни pygame, ни экранов — только правила и состояние.
"""

from __future__ import annotations

from typing import Dict, Optional

from . import pressure

DEFAULT_MINUTES = 3
HINT_MINUTES = 2
MAX_DIGITS = 6


def spec(case: Optional[Dict], clue: Optional[Dict]) -> Optional[Dict]:
    """Загадка улики из данных дела (если есть и дело «взрослое»)."""
    raw = (clue or {}).get("riddle")
    if not isinstance(raw, dict) or not raw.get("answer"):
        return None
    if not pressure.advanced(case):
        return None
    answer = normalize(raw.get("answer"))
    if not answer:
        return None
    return {
        "id": str(raw.get("id") or f"{clue.get('id', '')}:riddle"),
        "title": str(raw.get("title") or "КОДОВЫЙ ЗАМОК"),
        "prompt": str(raw.get("prompt") or ""),
        "hint": str(raw.get("hint") or ""),
        "answer": answer,
        "minutes": int(raw.get("minutes", DEFAULT_MINUTES) or 0),
    }


def for_clue(case: Optional[Dict], clue: Optional[Dict]) -> Optional[Dict]:
    return spec(case, clue)


def normalize(value) -> str:
    """Оставить только цифры: «16:10» и «1610» — одно и то же."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())[:MAX_DIGITS]


def solved(state, item: Optional[Dict]) -> bool:
    if not item:
        return True
    return str(item.get("id")) in (getattr(state, "riddles_solved", None) or set())


def mark_solved(state, item: Optional[Dict]) -> None:
    if not item:
        return
    if getattr(state, "riddles_solved", None) is None:
        state.riddles_solved = set()
    state.riddles_solved.add(str(item["id"]))


def hint_text(item: Optional[Dict]) -> str:
    return str((item or {}).get("hint") or "")


def check(state, item: Optional[Dict], guess: str) -> Dict:
    """Проверить код.

    Статусы: ``ok`` (замок открыт), ``wrong`` (штраф по времени),
    ``solved`` (уже открывали), ``short`` (не все цифры введены).
    """
    if not item:
        return {"status": "solved"}
    if solved(state, item):
        return {"status": "solved"}
    digits = normalize(guess)
    if not digits:
        return {"status": "short"}
    if digits == item["answer"]:
        mark_solved(state, item)
        return {"status": "ok", "clue_id": item.get("clue_id")}
    minutes = int(item.get("minutes", DEFAULT_MINUTES) or 0)
    if minutes:
        state.case_time_minutes = (
            int(getattr(state, "case_time_minutes", 0) or 0) + minutes
        )
    return {"status": "wrong", "minutes": minutes}


def hint(state, item: Optional[Dict]) -> Dict:
    """Открыть подсказку: короткий штраф по времени."""
    if not item or not hint_text(item):
        return {"status": "none"}
    state.case_time_minutes = (
        int(getattr(state, "case_time_minutes", 0) or 0) + HINT_MINUTES
    )
    return {"status": "ok", "text": hint_text(item), "minutes": HINT_MINUTES}


def answer_length(item: Optional[Dict]) -> int:
    return len(str((item or {}).get("answer") or ""))


__all__ = [
    "DEFAULT_MINUTES",
    "HINT_MINUTES",
    "answer_length",
    "check",
    "for_clue",
    "hint",
    "hint_text",
    "mark_solved",
    "normalize",
    "solved",
    "spec",
]
