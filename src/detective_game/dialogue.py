"""Интерактивный допрос: выбор реплик, доверие и бонусы.

Раньше допрос был линейным: список готовых вопросов и кнопка «Далее».
Теперь у темы может быть несколько **вариантов реплики детектива** —
мягкий, жёсткий, по делу. От выбора зависит ответ персонажа, его доверие
и то, выдаст ли он улику.

Формат темы в JSON дела (старый формат ``{"q": ..., "a": ...}`` тоже
поддерживается — он просто играется без выбора)::

    {
      "prompt": "Реплика персонажа, которая открывает тему",
      "options": [
        {"text": "фраза детектива", "reply": "ответ персонажа",
         "trust": 1, "clue": "clue_paw", "time": 10}
      ]
    }
"""

from __future__ import annotations

from typing import Dict, List, Optional

MAX_OPTIONS = 3
DEFAULT_TRUST_BONUS_MIN = 2
MAX_TRUST = 5


def options(topic: Optional[Dict]) -> List[Dict]:
    """Варианты реплики в теме (не больше ``MAX_OPTIONS``)."""
    if not topic:
        return []
    raw = topic.get("options") or []
    return [o for o in raw if isinstance(o, dict) and o.get("text")][:MAX_OPTIONS]


def is_interactive(topic: Optional[Dict]) -> bool:
    """Есть ли в теме выбор реплики."""
    return bool(options(topic))


def prompt(topic: Optional[Dict]) -> str:
    """Реплика персонажа, открывающая тему."""
    return str((topic or {}).get("prompt") or "")


def key(char_id: str, index: int) -> str:
    """Ключ выбора в состоянии игры."""
    return f"{char_id}:{index}"


def chosen(state, char_id: str, index: int) -> Optional[int]:
    """Индекс уже выбранной реплики или ``None``."""
    raw = (getattr(state, "dialogue_choices", None) or {}).get(key(char_id, index))
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def chosen_option(state, char_id: str, index: int, topic: Optional[Dict]) -> Optional[Dict]:
    """Выбранная реплика вместе с ответом персонажа."""
    idx = chosen(state, char_id, index)
    opts = options(topic)
    if idx is None or not 0 <= idx < len(opts):
        return None
    return opts[idx]


def trust_of(state, char_id: str) -> int:
    """Текущее доверие персонажа (может быть отрицательным)."""
    try:
        return int((getattr(state, "trust", None) or {}).get(char_id, 0))
    except (TypeError, ValueError):
        return 0


def trust_pips(trust: int) -> int:
    """Сколько делений рисовать в шкале доверия."""
    return max(0, min(MAX_TRUST, trust))


def trust_bonus(char: Dict) -> Optional[Dict]:
    """Бонус за доверие, если он описан у персонажа."""
    bonus = (char or {}).get("trust_bonus") or {}
    return bonus if bonus.get("text") else None


def bonus_min(char: Dict) -> int:
    bonus = trust_bonus(char) or {}
    try:
        return int(bonus.get("min", DEFAULT_TRUST_BONUS_MIN))
    except (TypeError, ValueError):
        return DEFAULT_TRUST_BONUS_MIN


def choose(
    state,
    char: Dict,
    index: int,
    opt_index: int,
    clue_lookup=None,
) -> Optional[Dict]:
    """Выбрать реплику в теме ``index``.

    Возвращает ``{"option", "trust_delta", "clue"}`` или ``None``, если выбор
    невозможен (нет такой темы/реплики или уже выбран ранее — переиграть
    допрос нельзя).
    """
    topics = (char or {}).get("dialogue") or []
    if not 0 <= index < len(topics):
        return None
    opts = options(topics[index])
    if not 0 <= opt_index < len(opts):
        return None
    char_id = char.get("id", "")
    if chosen(state, char_id, index) is not None:
        return None

    option = opts[opt_index]
    if getattr(state, "dialogue_choices", None) is None:
        state.dialogue_choices = {}
    state.dialogue_choices[key(char_id, index)] = opt_index

    delta = int(option.get("trust", 0) or 0)
    if delta:
        if getattr(state, "trust", None) is None:
            state.trust = {}
        state.trust[char_id] = trust_of(state, char_id) + delta

    clue = _award_clue(state, option.get("clue"), option.get("time"), clue_lookup)
    return {"option": option, "trust_delta": delta, "clue": clue}


def finish(state, char: Dict, clue_lookup=None) -> Optional[Dict]:
    """Итог допроса: бонус за доверие (выдаётся один раз)."""
    bonus = trust_bonus(char)
    if not bonus:
        return None
    char_id = char.get("id", "")
    taken = getattr(state, "trust_bonus_taken", None)
    if taken is None:
        state.trust_bonus_taken = taken = set()
    if char_id in taken:
        return None
    if trust_of(state, char_id) < bonus_min(char):
        return None
    taken.add(char_id)
    clue = _award_clue(state, bonus.get("clue"), 10, clue_lookup)
    return {"text": bonus["text"], "clue": clue}


def _award_clue(state, clue_id, minutes, clue_lookup) -> Optional[Dict]:
    """Добавить улику в блокнот. Возвращает улику или ``None``."""
    if not clue_id or not clue_lookup:
        return None
    clue = clue_lookup(clue_id)
    if not clue:
        return None
    if clue_id in (getattr(state, "collected_clues", None) or set()):
        return None
    state.collected_clues.add(clue_id)
    try:
        state.case_time_minutes += int(minutes if minutes is not None else 10)
    except (TypeError, ValueError):
        state.case_time_minutes += 10
    return clue
