"""Сопоставление показаний: перекрёстный допрос без улики в руках.

До сих пор поймать на лжи можно было только предъявив улику. Теперь в больших
делах показания сами по себе — объекты: у двух персонажей есть реплики, которые
не могут быть правдой одновременно. Игрок открывает обе темы в допросах, потом
на экране «СОПОСТАВЛЕНИЕ» выбирает две реплики.

Формат в данных дела::

    "contradictions": [
      {
        "id": "warehouse_time",
        "a": "elena:1",
        "b": "roma:0",
        "title": "Кто был у склада",
        "text": "Елена говорит, что Роман был у неё, а Роман — что был в порту.",
        "reputation": 1
      }
    ]

Ключ реплики — ``"персонаж:тема"``, как в ``state.asked_topics``. Сопоставлять
можно только те реплики, которые игрок уже слышал, поэтому перебор исключён:
в списке просто нет неоткрытых строк.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import dialogue, pressure

WRONG_MINUTES = 2
WRONG_TRUST = 1
DEFAULT_REPUTATION = 1


def statements(case: Optional[Dict], state) -> List[Dict]:
    """Все уже услышанные реплики, которые можно сопоставлять."""
    case = case or {}
    asked = getattr(state, "asked_topics", None) or set()
    result: List[Dict] = []
    for char in case.get("characters", []):
        char_id = str(char.get("id", ""))
        for index, topic in enumerate(char.get("dialogue") or []):
            item = dialogue.key(char_id, index)
            if item not in asked:
                continue
            result.append(
                {
                    "key": item,
                    "char_id": char_id,
                    "char": str(char.get("name", char_id)),
                    "index": index,
                    "text": statement_text(topic),
                }
            )
    return result


def statement_text(topic: Optional[Dict]) -> str:
    """Что именно сказал персонаж в этой теме."""
    topic = topic or {}
    text = str(topic.get("prompt") or "").strip()
    if text:
        return text
    # старый формат: {"q": вопрос, "a": ответ}
    return str(topic.get("a") or topic.get("q") or "").strip()


def statement(case: Optional[Dict], key: str) -> Optional[Dict]:
    """Реплика по ключу ``"персонаж:тема"`` (без проверки, слышал ли игрок)."""
    try:
        char_id, raw_index = str(key).split(":", 1)
        index = int(raw_index)
    except (ValueError, AttributeError):
        return None
    for char in (case or {}).get("characters", []):
        if str(char.get("id", "")) != char_id:
            continue
        topics = char.get("dialogue") or []
        if not 0 <= index < len(topics):
            return None
        return {
            "key": dialogue.key(char_id, index),
            "char_id": char_id,
            "char": str(char.get("name", char_id)),
            "index": index,
            "text": statement_text(topics[index]),
        }
    return None


def contradictions(case: Optional[Dict]) -> List[Dict]:
    """Все пары противоречий из данных дела."""
    raw = (case or {}).get("contradictions") or []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not item.get("a") or not item.get("b"):
            continue
        result.append(
            {
                "id": str(item.get("id") or f"{item['a']}|{item['b']}"),
                "a": str(item["a"]),
                "b": str(item["b"]),
                "title": str(item.get("title") or "Противоречие"),
                "text": str(item.get("text") or ""),
                "reputation": int(item.get("reputation", DEFAULT_REPUTATION) or 0),
            }
        )
    return result


def available(case: Optional[Dict], state) -> bool:
    """Есть ли что сопоставлять: хотя бы две услышанные реплики."""
    if not pressure.advanced(case):
        return False
    return len(statements(case, state)) >= 2


def heard(case: Optional[Dict], state, key: str) -> bool:
    return key in (getattr(state, "asked_topics", None) or set())


def pair_of(item: Dict) -> frozenset:
    return frozenset((item["a"], item["b"]))


def solved(state, case: Optional[Dict]) -> List[str]:
    """id уже раскрытых противоречий."""
    found = getattr(state, "deductions", None) or set()
    return [item["id"] for item in contradictions(case) if item["id"] in found]


def pending(case: Optional[Dict], state) -> List[Dict]:
    found = getattr(state, "deductions", None) or set()
    return [item for item in contradictions(case) if item["id"] not in found]


def deduction(case: Optional[Dict], ded_id: str) -> Optional[Dict]:
    for item in contradictions(case):
        if item["id"] == str(ded_id):
            return item
    return None


def has_deduction(state, ded_id: str) -> bool:
    return str(ded_id) in (getattr(state, "deductions", None) or set())


def check(state, case: Optional[Dict], key_a: str, key_b: str) -> Dict:
    """Сопоставить две реплики.

    Статусы: ``ok`` (противоречие найдено), ``already``, ``same`` (одна и та же
    реплика), ``locked`` (реплику ещё не слышали), ``wrong`` (не противоречат).
    """
    if str(key_a) == str(key_b):
        return {"status": "same"}
    for key in (key_a, key_b):
        if not heard(case, state, str(key)):
            return {"status": "locked", "key": key}
        if statement(case, str(key)) is None:
            return {"status": "locked", "key": key}
    pair = frozenset((str(key_a), str(key_b)))
    for item in contradictions(case):
        if pair_of(item) != pair:
            continue
        if has_deduction(state, item["id"]):
            return {"status": "already", "deduction": item}
        if getattr(state, "deductions", None) is None:
            state.deductions = set()
        state.deductions.add(item["id"])
        rep = int(item.get("reputation", DEFAULT_REPUTATION) or 0)
        if rep:
            state.reputation = int(getattr(state, "reputation", 0) or 0) + rep
        return {"status": "ok", "deduction": item, "reputation": rep}

    # ошибка стоит времени и доверия обоим собеседникам
    state.case_time_minutes = (
        int(getattr(state, "case_time_minutes", 0) or 0) + WRONG_MINUTES
    )
    for char_id in {key.split(":", 1)[0] for key in (str(key_a), str(key_b))}:
        if getattr(state, "trust", None) is None:
            state.trust = {}
        state.trust[char_id] = dialogue.trust_of(state, char_id) - WRONG_TRUST
    return {"status": "wrong", "minutes": WRONG_MINUTES, "trust": -WRONG_TRUST}


def summary(case: Optional[Dict], state) -> str:
    total = len(contradictions(case))
    found = len(solved(state, case))
    if not total:
        return "В этом деле нечего сопоставлять"
    return f"Найдено противоречий: {found} из {total}"


def hints(case: Optional[Dict], state) -> List[str]:
    """Подсказки, какие пары ещё не проверены (без раскрытия ответа)."""
    result = []
    for item in pending(case, state):
        a = statement(case, item["a"]) or {}
        b = statement(case, item["b"]) or {}
        if heard(case, state, item["a"]) and heard(case, state, item["b"]):
            result.append(f"{a.get('char', '?')} ↔ {b.get('char', '?')}")
    return result
