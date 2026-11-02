"""Реконструкция таймлайна: собрать картину преступления по времени.

Перед обвинением детектив раскладывает карточки событий в хронологическом
порядке. Это отдельный экран, а не текст: карточки перемешиваются, игрок
переставляет их кликами (или стрелками), проверяет и получает оценку.

Таймлайны лежат здесь, а не в ``data.py``: текста много, а встроенные дела
должны оставаться читаемыми. Если в JSON дела есть поле ``timeline``, оно
важнее встроенного.

Событие — словарь ``{"id", "time", "text"}``; порядок в списке = правильный
хронологический порядок.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

DEFAULT_TIMELINES: Dict[str, List[Dict]] = {
    "tutorial": [
        {"id": "t1", "time": "21:12", "text": "Барсик сидит на подоконнике в кабинете мэра"},
        {"id": "t2", "time": "21:20", "text": "Кто-то отворачивает защёлку окна снаружи"},
        {"id": "t3", "time": "21:40", "text": "Человек в плаще уносит кота через сад"},
        {"id": "t4", "time": "22:05", "text": "Сосед Смит возвращается домой с большой сумкой"},
        {"id": "t5", "time": "07:55", "text": "Мэр находит открытое окно и пустую миску"},
    ],
    "missing_chess": [
        {"id": "m1", "time": "14:00", "text": "Артём уходит на турнир в ДК «Юность»"},
        {
            "id": "m2",
            "time": "15:40",
            "text": "Артём выходит через служебную дверь с мужчиной в сером плаще",
        },
        {"id": "m3", "time": "16:05", "text": "В кассе вокзала покупают детский билет до Нортпорта"},
        {"id": "m4", "time": "16:40", "text": "Елена звонит в ДК: сын не вернулся"},
        {"id": "m5", "time": "23:10", "text": "В парке Роузвуд находят тело фотографа Ланского"},
        {"id": "m6", "time": "01:20", "text": "В кладовке склада за бойлером заперт ребёнок"},
    ],
    "bank_heist": [
        {"id": "b1", "time": "02:14", "text": "Сигнализация замолкает: введён код M-314"},
        {"id": "b2", "time": "02:18", "text": "Дверь хранилища открывается изнутри"},
        {"id": "b3", "time": "02:24", "text": "Сигнализация включается: ячейки 310–320 вскрыты"},
        {"id": "b4", "time": "05:40", "text": "Ящик с деньгами перегружают на третьем причале"},
        {"id": "b5", "time": "09:00", "text": "Управляющий заявляет об ограблении"},
        {"id": "b6", "time": "09:20", "text": "В комнате охраны находят тёплую чашку кофе"},
        {"id": "b7", "time": "11:30", "text": "Уборщица не выходит на смену"},
    ],
}

MIN_EVENTS = 3


def events(case: Optional[Dict]) -> List[Dict]:
    """События дела в правильном порядке (пустой список, если их нет)."""
    case = case or {}
    raw = case.get("timeline") or DEFAULT_TIMELINES.get(str(case.get("id", "")), [])
    result = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("text"):
            continue
        result.append(
            {
                "id": str(item.get("id") or f"e{index}"),
                "time": str(item.get("time") or ""),
                "text": str(item.get("text")),
            }
        )
    return result


def available(case: Optional[Dict]) -> bool:
    return len(events(case)) >= MIN_EVENTS


def correct_order(case: Optional[Dict]) -> List[str]:
    return [item["id"] for item in events(case)]


def by_id(case: Optional[Dict]) -> Dict[str, Dict]:
    return {item["id"]: item for item in events(case)}


def shuffled(case: Optional[Dict]) -> List[str]:
    """Перемешанный порядок, который не совпадает с правильным."""
    ids = correct_order(case)
    if len(ids) < 2:
        return ids
    rng = random.Random(f"timeline:{status_key(case)}")
    order = list(ids)
    for _ in range(12):
        rng.shuffle(order)
        if order != ids:
            break
    return order


def status_key(case: Optional[Dict]) -> str:
    return str((case or {}).get("id", ""))


def start(state, case: Optional[Dict]) -> List[str]:
    """Подготовить порядок карточек в состоянии (если его ещё нет)."""
    ids = correct_order(case)
    current = [str(item) for item in (getattr(state, "timeline_order", None) or [])]
    if sorted(current) != sorted(ids):
        current = shuffled(case)
        state.timeline_order = list(current)
    return list(current)


def swap(state, i: int, j: int) -> None:
    order = list(getattr(state, "timeline_order", []) or [])
    if not (0 <= i < len(order) and 0 <= j < len(order)) or i == j:
        return
    order[i], order[j] = order[j], order[i]
    state.timeline_order = order


def move(state, i: int, delta: int) -> int:
    """Сдвинуть карточку стрелкой. Возвращает новый индекс."""
    order = list(getattr(state, "timeline_order", []) or [])
    if not order:
        return i
    j = max(0, min(len(order) - 1, i + delta))
    if j != i:
        swap(state, i, j)
    return j


def order(state, case: Optional[Dict]) -> List[str]:
    """Текущий порядок карточек (с автозапуском, если пусто)."""
    if not getattr(state, "timeline_order", None):
        start(state, case)
    return list(state.timeline_order)


def matched(state, case: Optional[Dict]) -> int:
    """Сколько карточек уже стоят на своём месте."""
    right = correct_order(case)
    current = order(state, case)
    return sum(1 for i, cid in enumerate(current) if i < len(right) and right[i] == cid)


def is_solved(state, case: Optional[Dict]) -> bool:
    return bool(getattr(state, "timeline_solved", False))


def check(state, case: Optional[Dict]) -> Dict:
    """Проверить реконструкцию. Одна попытка стоит 10 минут игрового времени."""
    right = correct_order(case)
    current = order(state, case)
    solved = current == right
    state.timeline_attempts = int(getattr(state, "timeline_attempts", 0)) + 1
    if solved and not getattr(state, "timeline_solved", False):
        state.timeline_solved = True
        state.reputation = int(getattr(state, "reputation", 0)) + 2
    return {
        "solved": solved,
        "matched": sum(1 for i, cid in enumerate(current) if i < len(right) and right[i] == cid),
        "total": len(right),
        "attempts": state.timeline_attempts,
    }


def reset(state, case: Optional[Dict]) -> None:
    state.timeline_order = shuffled(case)


__all__ = [
    "DEFAULT_TIMELINES",
    "available",
    "check",
    "correct_order",
    "events",
    "is_solved",
    "matched",
    "move",
    "order",
    "reset",
    "shuffled",
    "start",
    "swap",
]
