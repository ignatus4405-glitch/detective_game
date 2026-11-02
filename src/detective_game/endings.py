"""Финалы дел: сколько улик нужно, какой конец выбрать.

У дела может быть несколько концовок:

* базовая — по подозреваемому (``case["endings"][suspect_id]``);
* варианты (``variants``) — уточняют базовую по условиям: сколько улик
  собрано, какое доверие у персонажей, сколько занял допрос.

Порядок в ``variants`` важен: берётся первый подходящий вариант, иначе
базовая концовка. Условия (``requires``):

``all_clues`` / ``min_clues`` / ``max_clues``
    сколько улик собрано;
``min_trust`` / ``max_trust``
    суммарное доверие по всем персонажам дела (может быть отрицательным);
``all_bonuses`` / ``any_bonus``
    выданы ли бонусы за доверие;
``max_time``
    сколько игровых минут потрачено.

Обвинение не блокируется «наглухо»: играть можно с одной уликой, просто
суд развалится — это и есть отдельная концовка. Рекомендуемое число улик
показывается на карте и на экране обвинения.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

DEFAULT_MIN_CLUES = 3
MIN_CLUES_TO_ACCUSE = 1


def required_clues(case: Optional[Dict]) -> int:
    """Сколько улик рекомендуется для обвинения в этом деле."""
    case = case or {}
    clues = case.get("clues") or []
    total = len(clues)
    if total <= 0:
        return 0
    explicit = case.get("min_clues")
    if explicit is not None:
        try:
            return max(1, min(int(explicit), total))
        except (TypeError, ValueError):
            pass
    return max(1, min(DEFAULT_MIN_CLUES, total))


def can_accuse(state, case: Optional[Dict]) -> bool:
    """Обвинять можно, как только есть хоть одна улика (или ордер)."""
    case = case or {}
    if not (case.get("suspects") or []):
        return False
    if getattr(state, "warrant", False):
        return True
    return len(getattr(state, "collected_clues", None) or set()) >= MIN_CLUES_TO_ACCUSE


def clue_hint(state, case: Optional[Dict]) -> str:
    """Подсказка для кнопки «Обвинить» (в больших делах — счёт суда)."""
    have = clue_count(state, case)
    need = required_clues(case)
    if have <= 0:
        return "Найдите хотя бы одну улику"
    if not can_accuse(state, case):
        return "Обвинение недоступно"
    if have < need:
        return f"Улик {have}/{need} — в суде может развалиться"
    return "Улик достаточно"


def clue_count(state, case: Optional[Dict]) -> int:
    """Сколько улик пойдёт в счёт суда.

    В больших делах слухи без экспертизы и подброшенные бумажки не считаются.
    """
    from . import expertise, pressure

    if not pressure.advanced(case):
        return len(getattr(state, "collected_clues", None) or set())
    return len(expertise.court_clues(case, state))


def _trust_sum(state, case: Dict) -> int:
    trust = getattr(state, "trust", None) or {}
    return sum(int(trust.get(ch.get("id", ""), 0)) for ch in case.get("characters", []))


def _bonus_count(state, case: Dict) -> int:
    taken = getattr(state, "trust_bonus_taken", None) or set()
    return sum(1 for ch in case.get("characters", []) if ch.get("id") in taken)


def _has_bonus(case: Dict) -> bool:
    return any(ch.get("trust_bonus") for ch in case.get("characters", []))


def matches(requires: Optional[Dict], state, case: Dict) -> bool:
    """Выполнены ли условия варианта концовки."""
    if not requires:
        return True
    clues = clue_count(state, case)
    total = len(case.get("clues") or [])
    trust = _trust_sum(state, case)
    if requires.get("all_clues") and clues < total:
        return False
    if "min_clues" in requires and clues < int(requires["min_clues"]):
        return False
    if "max_clues" in requires and clues > int(requires["max_clues"]):
        return False
    if "min_trust" in requires and trust < int(requires["min_trust"]):
        return False
    if "max_trust" in requires and trust > int(requires["max_trust"]):
        return False
    if requires.get("all_bonuses") and _bonus_count(state, case) < sum(
        1 for ch in case.get("characters", []) if ch.get("trust_bonus")
    ):
        return False
    if requires.get("any_bonus") and _bonus_count(state, case) <= 0:
        return False
    if "max_time" in requires and int(getattr(state, "case_time_minutes", 0)) > int(
        requires["max_time"]
    ):
        return False
    if requires.get("all_deductions"):
        from . import testimony

        if len(testimony.solved(state, case)) < len(testimony.contradictions(case)):
            return False
    if "min_confirmed" in requires:
        from . import expertise

        if len(expertise.court_clues(case, state)) < int(requires["min_confirmed"]):
            return False
    if requires.get("trial_correct"):
        from . import trial

        if trial.evaluate(case, state).get("score") != 2:
            return False
    return True


def suspect_of(case: Dict, suspect_id: Optional[str]) -> Optional[Dict]:
    for suspect in case.get("suspects", []):
        if suspect.get("id") == suspect_id:
            return suspect
    return None


def variants_of(case: Dict, suspect_id: Optional[str]) -> List[Dict]:
    ending = (case.get("endings") or {}).get(suspect_id or "") or {}
    return list(ending.get("variants") or [])


def _fallback(case: Dict, suspect: Optional[Dict]) -> Dict:
    """Концовка для подозреваемого, у которого её нет в данных."""
    if not suspect:
        return {
            "success": False,
            "title": "Дело закрыто",
            "text": "Вы не назвали виновного. Дело уходит в архив — и остаётся там.",
            "rank": "F",
        }
    name = suspect.get("name", "подозреваемый")
    if suspect.get("is_culprit"):
        return {
            "success": True,
            "title": f"Дело закрыто: {name}",
            "text": (
                f"{name} задержан. Вы собрали достаточно, чтобы суд согласился: "
                "приговор вынесен, Блэквил может спать спокойно."
            ),
            "rank": "B",
        }
    return {
        "success": False,
        "title": "Не тот",
        "text": (
            f"Вы обвинили {name}. Настоящий виновный уже собирает чемоданы — "
            "а ваша репутация трещит по швам."
        ),
        "rank": "F",
    }


def _late_ending() -> Dict:
    """Срок истёк так, что прокурор закрыл дело сам."""
    return {
        "success": False,
        "title": "Опоздал",
        "text": (
            "Вы тянули слишком долго: прокурор подписал отказ и закрыл дело. "
            "Виновный успел замести следы, а в газете вышла заметка «Детектив, "
            "который не успел». Улик было много — времени не хватило."
        ),
        "rank": "F",
    }


# ранг выше — если игрок восстановил хронологию перед обвинением
RANK_UP = {"F": "D", "D": "C", "C": "B", "B": "A", "A": "S", "S": "S+", "S+": "S+"}
RANK_DOWN = {"S+": "S", "S": "A", "A": "B", "B": "C", "C": "D", "D": "F", "F": "F"}


def promote_rank(rank: str) -> str:
    return RANK_UP.get(str(rank), str(rank))


def demote_rank(rank: str) -> str:
    return RANK_DOWN.get(str(rank), str(rank))


def adjust_rank(rank: str, state, case: Optional[Dict]) -> Tuple[str, List[str]]:
    """Итоговый ранг: срок, суд (мотив/способ) и хронология."""
    from . import pressure, trial

    notes: List[str] = []
    rank = str(rank)
    bonus = trial.rank_bonus(case, state)
    if bonus > 0:
        rank = promote_rank(rank)
        notes.append("суд: мотив и способ доказаны (+1 ступень)")
    elif bonus < 0:
        rank = demote_rank(rank)
        notes.append("суд: мотив и способ не доказаны (−1 ступень)")
    if pressure.advanced(case) and pressure.is_late(state, case):
        rank = demote_rank(rank)
        notes.append("срок вышел (−1 ступень)")
    return rank, notes


def resolve(case: Optional[Dict], state) -> Dict:
    """Итоговая концовка: подозреваемый + первый подходящий вариант."""
    case = case or {}
    suspect = suspect_of(case, getattr(state, "accusation_result", None))
    base = (case.get("endings") or {}).get(suspect.get("id") if suspect else None)
    if not base:
        from . import pressure

        if suspect is None and pressure.advanced(case) and pressure.is_late(state, case):
            base = _late_ending()
        else:
            base = _fallback(case, suspect)
    result = {
        "success": bool(base.get("success", False)),
        "title": base.get("title", "Финал"),
        "text": base.get("text", "История окончена."),
        "rank": base.get("rank", "?"),
        "variant": "base",
        "label": "Основная концовка",
        "suspect_id": (suspect or {}).get("id"),
    }
    from . import pressure, trial

    result["court_clues"] = clue_count(state, case)
    result["late"] = bool(
        pressure.advanced(case) and pressure.is_late(state, case)
    )
    result["trial"] = trial.evaluate(case, state)
    for variant in base.get("variants") or []:
        if matches(variant.get("requires"), state, case):
            result.update(
                {
                    "title": variant.get("title", result["title"]),
                    "text": variant.get("text", result["text"]),
                    "rank": variant.get("rank", result["rank"]),
                    "variant": str(variant.get("id", "variant")),
                    "label": str(variant.get("label", "Вариант концовки")),
                }
            )
            break
    if result["success"] and getattr(state, "timeline_solved", False):
        result["rank"] = promote_rank(result.get("rank", "F"))
        result["timeline_bonus"] = True
    rank, notes = adjust_rank(result.get("rank", "F"), state, case)
    result["rank"] = rank
    if notes:
        result["rank_notes"] = notes
    return result


def ending_key(case_id: str, resolution: Dict) -> str:
    return f"{case_id}:{resolution.get('suspect_id')}:{resolution.get('variant')}"


def total_endings(case: Optional[Dict]) -> int:
    """Сколько всего концовок можно открыть в деле."""
    case = case or {}
    total = 0
    for suspect in case.get("suspects", []):
        ending = (case.get("endings") or {}).get(suspect.get("id")) or {}
        total += 1 + len(ending.get("variants") or [])
    return total


def unlocked_for(state, case_id: str) -> List[str]:
    data = getattr(state, "unlocked_endings", None) or {}
    return list(data.get(case_id) or [])


def record(state, case_id: str, resolution: Dict) -> bool:
    """Запомнить открытую концовку. True — если она новая."""
    data = getattr(state, "unlocked_endings", None)
    if data is None:
        state.unlocked_endings = data = {}
    keys = data.setdefault(case_id, [])
    key = ending_key(case_id, resolution)
    if key in keys:
        return False
    keys.append(key)
    return True


def progress(state, case: Optional[Dict]) -> Tuple[int, int]:
    """(открыто, всего) для экрана выбора дела."""
    case = case or {}
    case_id = str(case.get("id", ""))
    return len(unlocked_for(state, case_id)), total_endings(case)
