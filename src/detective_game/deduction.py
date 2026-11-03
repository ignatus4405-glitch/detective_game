"""Экспертное расследование: черновик доски, алиби и доказательная цепочка.

Правила отделены от pygame. В классическом режиме старые дела работают как
раньше; экспертные ответы никогда не используются для проверки отдельной связи.
"""
from __future__ import annotations

from typing import Dict, Optional

MODES = ("classic", "expert")
MODE_LABELS = {"classic": "КЛАССИКА", "expert": "ЭКСПЕРТ"}
THINKING_SCREENS = frozenset({
    "notebook", "riddle", "alibi", "proof", "timeline", "testimony", "accusation",
})
SLOTS = (
    ("motive", "01", "МОТИВ", "Зачем ему было это делать?"),
    ("access", "02", "ДОСТУП", "Как он получил доступ?"),
    ("presence", "03", "ПРИСУТСТВИЕ", "Что ставит его на место события?"),
    ("action", "04", "ДЕЙСТВИЕ", "Что доказывает сам способ?"),
    ("cover", "05", "СОКРЫТИЕ", "Как он заметал следы?"),
)
SLOT_IDS = tuple(item[0] for item in SLOTS)
REVIEW_COST = 15


def supported(case: Optional[Dict]) -> bool:
    return bool((case or {}).get("advanced")) and bool((case or {}).get("proof"))


def enabled(case: Optional[Dict], state) -> bool:
    return supported(case) and getattr(state, "difficulty", "classic") == "expert"


def normalize_mode(case: Optional[Dict], mode: str) -> str:
    return "expert" if mode == "expert" and supported(case) else "classic"


def thinking(screen: str, case: Optional[Dict], state) -> bool:
    return enabled(case, state) and screen in THINKING_SCREENS


def alibi_spec(case: Optional[Dict]) -> Optional[Dict]:
    raw = (case or {}).get("alibi")
    return raw if isinstance(raw, dict) and raw.get("people") else None


def alibi_facts(case: Optional[Dict], state):
    """Факт открыт только после находки или реально услышанной реплики."""
    from .data import get_clue
    from .testimony import heard

    result = []
    for fact in (alibi_spec(case) or {}).get("facts", []):
        source = fact.get("source", {})
        if source.get("type") == "clue":
            clue = get_clue(case or {}, str(source.get("id", "")))
            unlocked = bool(clue) and clue["id"] in (getattr(state, "collected_clues", None) or set())
            source_name = (clue or {}).get("title", "Не найденная улика")
        else:
            key = str(source.get("key", ""))
            unlocked = heard(case, state, key)
            source_name = str(source.get("label") or "Показания свидетеля")
        result.append({**fact, "unlocked": unlocked, "source_name": source_name})
    return result


def alibi_ready(case: Optional[Dict], state) -> bool:
    spec = alibi_spec(case)
    if not spec:
        return False
    facts = alibi_facts(case, state)
    answers = getattr(state, "alibi_assignments", None) or {}
    people = [p["id"] for p in spec["people"]]
    places = [p["id"] for p in spec["places"]]
    return (
        bool(facts) and all(f["unlocked"] for f in facts)
        and all(answers.get(p) in places for p in people)
        and len(set(answers.get(p) for p in people)) == len(people)
    )


def alibi_assign(state, person: str, place: str) -> None:
    answers = dict(getattr(state, "alibi_assignments", None) or {})
    if answers.get(person) == place:
        answers.pop(person, None)
    else:
        for other, value in list(answers.items()):
            if value == place:
                answers.pop(other)
        answers[person] = place
    state.alibi_assignments = answers


def alibi_check(case: Optional[Dict], state) -> Dict:
    if getattr(state, "alibi_solved", False):
        return {"status": "already", "message": (alibi_spec(case) or {}).get("explanation", "")}
    if not alibi_ready(case, state):
        return {"status": "locked", "message": "Нужны все источники и одна версия места для каждого человека."}
    state.alibi_attempts = int(getattr(state, "alibi_attempts", 0)) + 1
    if state.alibi_assignments == (alibi_spec(case) or {}).get("solution", {}):
        state.alibi_solved = True
        state.reputation = int(getattr(state, "reputation", 0)) + 2
        return {"status": "ok", "message": alibi_spec(case)["explanation"]}
    state.case_time_minutes = int(getattr(state, "case_time_minutes", 0)) + 10
    return {"status": "wrong", "message": "Версия не согласуется со всеми источниками. Проверьте поправки часов и время в пути. −10 минут."}


def proof_spec(case: Optional[Dict]) -> Dict:
    return (case or {}).get("proof") or {}


def proof_select(case: Optional[Dict], state, slot: str, clue_id: str) -> bool:
    from .data import get_clue
    from .expertise import counts_in_court

    clue = get_clue(case or {}, clue_id)
    if slot not in SLOT_IDS or not clue or not counts_in_court(case, state, clue):
        return False
    if clue_id not in (getattr(state, "collected_clues", None) or set()):
        return False
    slots = dict(getattr(state, "proof_slots", None) or {})
    slots[slot] = clue_id
    state.proof_slots = slots
    return True


def proof_ready(case: Optional[Dict], state) -> bool:
    slots = getattr(state, "proof_slots", None) or {}
    return bool(proof_spec(case)) and all(slots.get(s) for s in SLOT_IDS) and bool(getattr(state, "proof_counter", None))


def proof_evaluate(case: Optional[Dict], state, suspect_id: Optional[str] = None) -> Dict:
    from .data import get_clue
    from .expertise import counts_in_court
    from .trial import evaluate as trial_evaluate

    spec = proof_spec(case)
    suspect_id = suspect_id or getattr(state, "accusation_result", None)
    culprit = next((s["id"] for s in (case or {}).get("suspects", []) if s.get("is_culprit")), None)
    selected = getattr(state, "proof_slots", None) or {}
    failures = []
    score = 0
    for slot, _num, label, _question in SLOTS:
        clue_id = selected.get(slot)
        clue = get_clue(case or {}, str(clue_id or ""))
        ok = (
            suspect_id == culprit and clue_id in (spec.get("slots", {}).get(slot, []))
            and bool(clue) and counts_in_court(case, state, clue)
            and clue_id in (getattr(state, "collected_clues", None) or set())
        )
        score += int(ok)
        if not ok:
            failures.append(label.lower())
    alternatives = spec.get("alternatives", [])
    counter = getattr(state, "proof_counter", None)
    counter_ok = any(a["id"] == counter and a.get("correct") for a in alternatives) and suspect_id == culprit
    if not counter_ok:
        failures.append("опровержение альтернативной версии")
    alibi_ok = bool(getattr(state, "alibi_solved", False)) or not alibi_spec(case)
    if not alibi_ok:
        failures.append("перекрёстное алиби")
    trial_ok = trial_evaluate(case, state).get("score") == 2
    if not trial_ok:
        failures.append("мотив и способ на суде")
    return {
        "asked": bool(spec), "complete": proof_ready(case, state),
        "correct": proof_ready(case, state) and not failures,
        "score": score, "failures": failures, "counter_ok": counter_ok,
        "alibi_ok": alibi_ok, "trial_ok": trial_ok,
    }
