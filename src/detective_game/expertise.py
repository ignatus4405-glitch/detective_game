"""Экспертиза улик: что суд примет, а что окажется подброшенным.

В больших делах часть находок — не доказательство, а слух или подкинутая
бумажка. Улику можно отнести в лабораторию: 45 минут игрового времени,
$50 и репутация не ниже 2. Результат:

* **подтверждена** — идёт в счёт суда (+1 репутация);
* **подброшена** — улика исчезает из блокнота, репутация −1, зато вы знаете,
  что кто-то заметает следы (это тоже информация);
* **без экспертизы** — слух остаётся в блокноте, но суд его не считает.

Твёрдые улики (отпечатки, плёнка, сейф) проверки не требуют. Учебное дело
и дела без ``advanced`` работают по-старому: всё считается доказательством.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from . import pressure

SOLID = "solid"
HEARSAY = "hearsay"
PLANTED = "planted"

RELIABILITY_LABELS = {
    SOLID: "твёрдая улика",
    HEARSAY: "слух",
    PLANTED: "подброшено",
}

FAKE_REPUTATION = -1
CONFIRM_REPUTATION = 1


def reliability(clue: Optional[Dict]) -> str:
    """Достоверность улики по данным дела."""
    raw = str((clue or {}).get("reliability") or SOLID).lower()
    return raw if raw in RELIABILITY_LABELS else SOLID


def needs_check(case: Optional[Dict], clue: Optional[Dict]) -> bool:
    """Нужна ли экспертиза (только в больших делах и только для слухов)."""
    if not pressure.advanced(case):
        return False
    return reliability(clue) in (HEARSAY, PLANTED)


def confirmed(state, clue_id: str) -> bool:
    return clue_id in (getattr(state, "confirmed_clues", None) or set())


def is_fake(state, clue_id: str) -> bool:
    return clue_id in (getattr(state, "fake_clues", None) or set())


def status(case: Optional[Dict], state, clue: Optional[Dict]) -> str:
    """``solid`` / ``confirmed`` / ``fake`` / ``hearsay``."""
    if not clue:
        return SOLID
    clue_id = str(clue.get("id", ""))
    if not needs_check(case, clue):
        return SOLID
    if is_fake(state, clue_id):
        return "fake"
    if confirmed(state, clue_id):
        return "confirmed"
    return "hearsay"


def status_label(case: Optional[Dict], state, clue: Optional[Dict]) -> str:
    return {
        "solid": "",
        "confirmed": "✓ подтверждено",
        "fake": "✗ подброшено",
        "hearsay": "? без экспертизы",
    }.get(status(case, state, clue), "")


def counts_in_court(case: Optional[Dict], state, clue: Optional[Dict]) -> bool:
    """Примет ли суд эту улику."""
    return status(case, state, clue) in (SOLID, "confirmed")


def court_clues(case: Optional[Dict], state) -> Set[str]:
    """Улики, которые суд примет."""
    result: Set[str] = set()
    collected = getattr(state, "collected_clues", None) or set()
    for clue in (case or {}).get("clues") or []:
        clue_id = str(clue.get("id", ""))
        if clue_id in collected and counts_in_court(case, state, clue):
            result.add(clue_id)
    return result


def pending(case: Optional[Dict], state) -> List[Dict]:
    """Улики, которые ждут экспертизы."""
    collected = getattr(state, "collected_clues", None) or set()
    return [
        clue
        for clue in (case or {}).get("clues") or []
        if str(clue.get("id", "")) in collected
        and needs_check(case, clue)
        and not confirmed(state, str(clue.get("id", "")))
    ]


def cost_text() -> str:
    return f"{pressure.LAB_COST} $ и {pressure.LAB_MINUTES} мин"


def can_submit(state, case: Optional[Dict], clue: Optional[Dict]) -> Dict[str, bool]:
    """Что мешает отправить улику на экспертизу."""
    clue_id = str((clue or {}).get("id", ""))
    collected = clue_id in (getattr(state, "collected_clues", None) or set())
    afford = pressure.can_afford_lab(state)
    return {
        "advanced": pressure.advanced(case),
        "collected": collected,
        "needs_check": needs_check(case, clue),
        "confirmed": confirmed(state, clue_id),
        "fake": is_fake(state, clue_id),
        "money": afford["money"],
        "reputation": afford["reputation"],
    }


def submit(state, case: Optional[Dict], clue: Optional[Dict]) -> Dict:
    """Отправить улику в лабораторию.

    Статусы: ``ok`` (есть результат), ``already``, ``no_clue``, ``solid``
    (проверка не нужна), ``no_money``, ``no_rep``.
    """
    clue = clue or {}
    clue_id = str(clue.get("id", ""))
    checks = can_submit(state, case, clue)
    if not checks["advanced"] or not checks["needs_check"]:
        return {"status": "solid"}
    if not checks["collected"]:
        return {"status": "no_clue"}
    if checks["confirmed"] or checks["fake"]:
        return {"status": "already"}
    if not checks["money"]:
        return {"status": "no_money", "need": pressure.LAB_COST}
    if not checks["reputation"]:
        return {"status": "no_rep", "need": pressure.LAB_REPUTATION}

    if getattr(state, "confirmed_clues", None) is None:
        state.confirmed_clues = set()
    if getattr(state, "fake_clues", None) is None:
        state.fake_clues = set()

    state.money = int(getattr(state, "money", 0) or 0) - pressure.LAB_COST
    state.case_time_minutes = (
        int(getattr(state, "case_time_minutes", 0) or 0) + pressure.LAB_MINUTES
    )

    fake = reliability(clue) == PLANTED or bool(clue.get("fake"))
    if fake:
        state.fake_clues.add(clue_id)
        state.collected_clues.discard(clue_id)
        state.reputation = int(getattr(state, "reputation", 0) or 0) + FAKE_REPUTATION
        return {
            "status": "ok",
            "fake": True,
            "clue": clue,
            "minutes": pressure.LAB_MINUTES,
            "money": pressure.LAB_COST,
            "text": (
                f"Экспертиза: «{clue.get('title', 'улика')}» — подделка. "
                "Кто-то подбросил её вам. Улика изъята из блокнота."
            ),
        }

    state.confirmed_clues.add(clue_id)
    state.reputation = int(getattr(state, "reputation", 0) or 0) + CONFIRM_REPUTATION
    return {
        "status": "ok",
        "fake": False,
        "clue": clue,
        "minutes": pressure.LAB_MINUTES,
        "money": pressure.LAB_COST,
        "text": (
            f"Экспертиза: «{clue.get('title', 'улика')}» подтверждена. "
            "Суд примет её как доказательство."
        ),
    }
