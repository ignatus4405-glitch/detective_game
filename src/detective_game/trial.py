"""Суд: мало назвать виновного — нужны мотив и способ.

В больших делах обвинение состоит из трёх ответов: **кто**, **зачем** и
**как**. Мотив и способ выбираются на экране обвинения из списков дела;
верные ответы поднимают ранг финала, неверные — снижают и меняют вердикт.

Формат в данных дела::

    "trial": {
      "motives": [{"id": "debts", "text": "Долги — его вот-вот выселяют"}],
      "methods": [{"id": "staged", "text": "Инсценировал ограбление"}],
      "answers": {
        "finch": {"motive": "debts", "method": "staged"}
      }
    }

Если блока нет или дело простое — суд работает по-старому: только виновный.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import pressure

MOTIVE = "motive"
METHOD = "method"


def spec(case: Optional[Dict]) -> Optional[Dict]:
    raw = (case or {}).get("trial")
    if not isinstance(raw, dict):
        return None
    if not raw.get("motives") or not raw.get("methods"):
        return None
    return raw


def available(case: Optional[Dict]) -> bool:
    """Нужно ли отвечать про мотив и способ."""
    return pressure.advanced(case) and spec(case) is not None


def _items(case: Optional[Dict], kind: str) -> List[Dict]:
    data = spec(case) or {}
    result = []
    for item in data.get(kind + "s") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        result.append(
            {"id": str(item["id"]), "text": str(item.get("text") or item["id"])}
        )
    return result


def motives(case: Optional[Dict]) -> List[Dict]:
    return _items(case, MOTIVE)


def methods(case: Optional[Dict]) -> List[Dict]:
    return _items(case, METHOD)


def answers(case: Optional[Dict], suspect_id: Optional[str]) -> Dict[str, str]:
    data = spec(case) or {}
    raw = (data.get("answers") or {}).get(str(suspect_id or "")) or {}
    return {str(k): str(v) for k, v in raw.items()}


def selected(state, kind: str) -> Optional[str]:
    return getattr(state, "trial_" + kind, None)


def select_from(case: Optional[Dict], state, kind: str, value: Optional[str]) -> bool:
    """Выбрать ответ, сверяясь со списками конкретного дела."""
    if kind not in (MOTIVE, METHOD):
        return False
    if value is not None:
        allowed = {item["id"] for item in _items(case, kind)}
        if value not in allowed:
            return False
    setattr(state, "trial_" + kind, value)
    return True


def ready(case: Optional[Dict], state) -> bool:
    """Все ли ответы даны (для дел со судом)."""
    if not available(case):
        return True
    return bool(selected(state, MOTIVE)) and bool(selected(state, METHOD))


def evaluate(case: Optional[Dict], state) -> Dict:
    """Проверить ответы игрока по выбранному подозреваемому."""
    if not available(case):
        return {"asked": False, "motive_ok": None, "method_ok": None, "score": 0}
    suspect = str(getattr(state, "accusation_result", "") or "")
    key = answers(case, suspect)
    motive = selected(state, MOTIVE)
    method = selected(state, METHOD)
    motive_ok = bool(motive) and motive == key.get(MOTIVE)
    method_ok = bool(method) and method == key.get(METHOD)
    return {
        "asked": True,
        "answered": answered(state),
        "motive": motive,
        "method": method,
        "motive_ok": motive_ok,
        "method_ok": method_ok,
        "score": int(motive_ok) + int(method_ok),
        "correct": key,
    }


def verdict_text(case: Optional[Dict], state) -> str:
    result = evaluate(case, state)
    if not result["asked"] or not result.get("answered"):
        return ""
    parts = []
    parts.append("мотив верен" if result["motive_ok"] else "мотив не доказан")
    parts.append("способ верен" if result["method_ok"] else "способ не доказан")
    return "Суд: " + ", ".join(parts)


def answered(state) -> bool:
    """Давал ли игрок хоть какие-то ответы на суде."""
    return bool(selected(state, MOTIVE) or selected(state, METHOD))


def rank_bonus(case: Optional[Dict], state) -> int:
    """+1 за оба верных ответа, −1 за оба неверных."""
    result = evaluate(case, state)
    if not result["asked"] or not answered(state):
        return 0
    if result["score"] == 2:
        return 1
    if result["score"] == 0:
        return -1
    return 0
