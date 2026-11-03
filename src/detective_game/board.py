"""Доска версий: связываем улики с подозреваемыми.

Главная мысль: блокнот — это не список, а рабочий стол. Игрок берёт улику и
«прикрепляет» её к человеку. Верные связки (те, что лежат в
``suspects[].evidence``) складываются в **вывод** по подозреваемому: когда все
его улики связаны, доска говорит, на кого давить.

Ошибаться можно: неверная связка стоит времени, помечается красным и больше не
предлагается. Ничего не блокируется — дело всегда можно закрыть.

Чистая логика без pygame: доска проверяется тестами без окна.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

LINK_SEP = "|"


def link_key(clue_id: str, suspect_id: str) -> str:
    """Ключ связки для хранения в состоянии."""
    return f"{clue_id}{LINK_SEP}{suspect_id}"


def parse_key(key: str) -> Tuple[str, str]:
    clue_id, _, suspect_id = str(key).partition(LINK_SEP)
    return clue_id, suspect_id


def suspects(case: Optional[Dict]) -> List[Dict]:
    """Подозреваемые, по которым есть что связывать."""
    return [s for s in (case or {}).get("suspects", []) if s.get("evidence")]


def suspect(case: Optional[Dict], suspect_id: str) -> Optional[Dict]:
    for item in (case or {}).get("suspects", []):
        if item.get("id") == suspect_id:
            return item
    return None


def clue_exists(case: Optional[Dict], clue_id: str) -> bool:
    return any(clue.get("id") == clue_id for clue in (case or {}).get("clues", []))


def evidence(clue: Dict, suspect_item: Dict) -> bool:
    """Правильная ли это связка: улика есть в списке доказательств."""
    return str(clue.get("id")) in {str(cid) for cid in suspect_item.get("evidence", [])}


def total_links(case: Optional[Dict]) -> int:
    """Сколько всего различных верных связок в деле."""
    pairs: Set[Tuple[str, str]] = set()
    for item in suspects(case):
        for clue_id in item.get("evidence", []):
            if clue_exists(case, str(clue_id)):
                pairs.add((str(clue_id), str(item.get("id"))))
    return len(pairs)


def is_correct(case: Optional[Dict], clue_id: str, suspect_id: str) -> bool:
    item = suspect(case, suspect_id)
    if not item or not clue_exists(case, clue_id):
        return False
    return str(clue_id) in {str(cid) for cid in item.get("evidence", [])}


def link(state, case: Optional[Dict], clue_id: str, suspect_id: str) -> Dict:
    """Связать улику с подозреваемым.

    Возвращает словарь со ``status``: ``ok`` (верная связка),
    ``wrong`` (неверная), ``known`` (уже связана), ``blocked`` (уже ошибались),
    ``missing`` (нет улики/подозреваемого) и ``conclusion`` — вывод, если
    после этой связки у подозреваемого сошлось всё.
    """
    from . import deduction

    clue_id, suspect_id = str(clue_id), str(suspect_id)
    item = suspect(case, suspect_id)
    if not item or not clue_exists(case, clue_id):
        return {"status": "missing", "message": "Такой улики или подозреваемого нет."}
    if clue_id not in getattr(state, "collected_clues", set()):
        return {"status": "missing", "message": "Сначала найдите эту улику."}
    key = link_key(clue_id, suspect_id)
    if deduction.enabled(case, state):
        draft = set(getattr(state, "board_draft", set()))
        existed = key in draft
        if existed:
            draft.discard(key)
        else:
            draft.add(key)
        state.board_draft = draft
        state.board_suspect = suspect_id
        state.board_review = {}
        return {
            "status": "draft_removed" if existed else "draft",
            "message": "Связь убрана из черновика." if existed else "Гипотеза записана. Истинность пока не проверяется.",
            "time": 0,
        }
    correct_links = getattr(state, "board_links", set())
    wrong_links = getattr(state, "board_wrong", set())
    if key in correct_links:
        return {"status": "known", "message": "Эта связка уже на доске."}
    if key in wrong_links:
        return {"status": "blocked", "message": "Вы уже пробовали эту связку — она не сошлась."}

    if is_correct(case, clue_id, suspect_id):
        correct_links.add(key)
        state.board_links = correct_links
        state.reputation = int(getattr(state, "reputation", 0)) + 1
        conclusion = None
        if all_evidence_linked(case, state, item):
            state.reputation += 2
            conclusion = build_conclusion(item)
        return {
            "status": "ok",
            "message": f"Связка принята: «{clue_title(case, clue_id)}» → {item.get('name')}.",
            "conclusion": conclusion,
            "time": 5,
        }

    wrong_links.add(key)
    state.board_wrong = wrong_links
    return {
        "status": "wrong",
        "message": "Не сходится: эта улика ни о чём не говорит в его пользу.",
        "time": 10,
    }


def clue_title(case: Optional[Dict], clue_id: str) -> str:
    for clue in (case or {}).get("clues", []):
        if clue.get("id") == clue_id:
            return str(clue.get("title", clue_id))
    return str(clue_id)


def all_evidence_linked(case: Optional[Dict], state, item: Dict) -> bool:
    from . import deduction
    if deduction.enabled(case, state):
        return False
    links = getattr(state, "board_links", set())
    evidence_ids = {str(cid) for cid in item.get("evidence", []) if clue_exists(case, str(cid))}
    if not evidence_ids:
        return False
    return all(link_key(cid, str(item.get("id"))) in links for cid in evidence_ids)


def build_conclusion(item: Dict) -> Dict:
    """Текст вывода, когда все доказательства по подозреваемому связаны."""
    name = str(item.get("name", "Неизвестный"))
    motive = str(item.get("motive", "")).strip()
    text = (
        f"{name}: все связи сходятся. {motive}."
        if motive
        else f"{name}: все связи сходятся — пора давить."
    )
    return {
        "suspect_id": str(item.get("id", "")),
        "title": name,
        "text": text,
        "motive": motive,
    }


def conclusion_for(case: Optional[Dict], state, item: Dict) -> Optional[Dict]:
    """Вывод по подозреваемому, если он уже собран."""
    return build_conclusion(item) if all_evidence_linked(case, state, item) else None


def conclusions(case: Optional[Dict], state) -> List[Dict]:
    result = []
    for item in suspects(case):
        if all_evidence_linked(case, state, item):
            result.append(build_conclusion(item))
    return result


def review(case: Optional[Dict], state, suspect_id: str) -> Dict:
    """Проверить всю версию: ни одна отдельная связь не получает оценку."""
    from . import deduction

    if not deduction.enabled(case, state):
        return {"status": "disabled"}
    expected = (case.get("proof") or {}).get("board", {}).get(suspect_id, [])
    links = {cid for cid, sid in map(parse_key, state.board_draft) if sid == suspect_id}
    signature = "|".join(sorted(links))
    cached = state.board_review or {}
    if cached.get("signature") == signature and cached.get("suspect") == suspect_id:
        return {**cached, "status": "cached"}
    missing = []
    for slot, _n, label, _q in deduction.SLOTS:
        accepted = (case.get("proof") or {}).get("slots", {}).get(slot, [])
        if not links.intersection(accepted):
            missing.append(label.lower())
    extra = len(links - set(expected))
    complete = not missing and not extra and bool(expected)
    result = {
        "status": "ok", "signature": signature, "suspect": suspect_id,
        "complete": complete, "missing": missing, "extra": extra,
    }
    state.board_review = dict(result)
    state.case_time_minutes += deduction.REVIEW_COST
    if complete and not state.board_rewarded:
        state.board_rewarded = True
        state.reputation += 2
    return result


def review_text(result: Dict) -> str:
    if result.get("complete"):
        return "Версия выдержала проверку. Перенесите доказательства в обвинение."
    parts = []
    if result.get("missing"):
        parts.append("Не обоснованы: " + ", ".join(result["missing"]))
    if result.get("extra"):
        parts.append(f"Лишних связок: {result['extra']}")
    return ". ".join(parts) + ". Игра не отмечает отдельные связи."


def progress(case: Optional[Dict], state) -> Dict:
    """Счёт для шапки доски и подсказок."""
    from . import deduction
    if deduction.enabled(case, state):
        return {"correct": 0, "wrong": 0, "total": 0, "suspects_done": 0,
                "suspects_total": len(suspects(case)), "percent": 0,
                "draft": len(state.board_draft)}
    total = total_links(case)
    links = getattr(state, "board_links", set())
    correct = sum(1 for key in links if _key_valid(case, key))
    wrong = len(getattr(state, "board_wrong", set()))
    done = len(conclusions(case, state))
    return {
        "correct": correct,
        "wrong": wrong,
        "total": total,
        "suspects_done": done,
        "suspects_total": len(suspects(case)),
        "percent": int(100 * correct / total) if total else 0,
    }


def _key_valid(case: Optional[Dict], key: str) -> bool:
    clue_id, suspect_id = parse_key(key)
    return is_correct(case, clue_id, suspect_id)


def hint_pair(case: Optional[Dict], state) -> Optional[Tuple[str, str]]:
    """Подсказка для кнопки «наводка»: верная связка, которой ещё нет."""
    for item in suspects(case):
        for clue_id in item.get("evidence", []):
            clue_id = str(clue_id)
            if clue_id not in getattr(state, "collected_clues", set()):
                continue
            key = link_key(clue_id, str(item.get("id")))
            if key not in getattr(state, "board_links", set()):
                return clue_id, str(item.get("id"))
    return None


__all__ = [
    "build_conclusion",
    "conclusions",
    "hint_pair",
    "is_correct",
    "link",
    "link_key",
    "parse_key",
    "progress",
    "suspects",
    "total_links",
]
