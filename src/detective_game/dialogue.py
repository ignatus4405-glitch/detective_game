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

from .pressure import SILENCE_TRUST

MAX_OPTIONS = 3
DEFAULT_TRUST_BONUS_MIN = 2
MAX_TRUST = 5
# ответ «промолчал» в списке выбранных реплик
DECLINED = -1


def day_of(state) -> int:
    """Текущий игровой день по времени дела."""
    from . import worldtime

    try:
        return worldtime.clock(int(getattr(state, "case_time_minutes", 0) or 0))[0]
    except Exception:
        return int(getattr(state, "game_day", 1) or 1)


def is_asked(state, char_id: str, index: int) -> bool:
    """Открывал ли игрок эту тему раньше."""
    return key(char_id, index) in (getattr(state, "asked_topics", None) or set())


def mark_asked(state, char_id: str, index: int) -> bool:
    """Отметить тему как открытую. ``True`` — если открыта впервые."""
    if getattr(state, "asked_topics", None) is None:
        state.asked_topics = set()
    item = key(char_id, index)
    first = item not in state.asked_topics
    state.asked_topics.add(item)
    return first


def silenced_until(state, char_id: str) -> int:
    """День, до которого персонаж отказывается говорить (0 — не молчит)."""
    try:
        return int((getattr(state, "silenced", None) or {}).get(char_id, 0) or 0)
    except (TypeError, ValueError):
        return 0


def is_silent(state, char_id: str) -> bool:
    """Молчит ли персонаж прямо сейчас."""
    return silenced_until(state, char_id) > day_of(state)


def silence(state, char_id: str) -> int:
    """Заставить персонажа замолчать до следующего дня."""
    if getattr(state, "silenced", None) is None:
        state.silenced = {}
    until = day_of(state) + 1
    state.silenced[char_id] = until
    return until


def decline(state, char: Dict, index: int) -> Dict:
    """Игрок промолчал: тема закрыта, доверие −1."""
    char_id = str((char or {}).get("id", ""))
    if chosen(state, char_id, index) is not None:
        return {"status": "already"}
    topics = (char or {}).get("dialogue") or []
    if not 0 <= index < len(topics):
        return {"status": "no_topic"}
    if getattr(state, "dialogue_choices", None) is None:
        state.dialogue_choices = {}
    state.dialogue_choices[key(char_id, index)] = DECLINED
    if getattr(state, "trust", None) is None:
        state.trust = {}
    delta = -SILENCE_TRUST
    state.trust[char_id] = trust_of(state, char_id) + delta
    return {"status": "ok", "trust_delta": delta}


def declined(state, char_id: str, index: int) -> bool:
    return chosen(state, char_id, index) == DECLINED


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
    result = {"option": option, "trust_delta": delta, "clue": clue}
    # жёсткая реплика при нулевом доверии — персонаж закрывается до утра
    if delta < 0 and trust_of(state, char_id) <= 0:
        result["silenced_until"] = silence(state, char_id)
    return result


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


# ── «уличить во лжи» ───────────────────────────────────────────────────

DEFAULT_LIE_TRUST = 2
DEFAULT_LIE_TIME = 5


def lie(topic: Optional[Dict]) -> Optional[Dict]:
    """Спецификация лжи в теме: ``{"clue", "reply", "claim", "trust"}``."""
    raw = (topic or {}).get("lie") or {}
    if not raw.get("clue") or not raw.get("reply"):
        return None
    return raw


def lie_key(char_id: str, index: int) -> str:
    return f"{char_id}:{index}"


def lie_exposed(state, char_id: str, index: int) -> bool:
    return lie_key(char_id, index) in (getattr(state, "exposed_lies", None) or {})


def lie_reply(state, char_id: str, index: int) -> str:
    return str((getattr(state, "exposed_lies", None) or {}).get(lie_key(char_id, index), ""))


def lie_evidence(state, topic: Optional[Dict]) -> Optional[str]:
    """Улика, которой можно уличить (её id), если она уже собрана."""
    spec = lie(topic)
    if not spec:
        return None
    clue_id = str(spec["clue"])
    if clue_id in (getattr(state, "collected_clues", None) or set()):
        return clue_id
    return None


def requires(topic: Optional[Dict]) -> Dict:
    """Условия, при которых тема открывается."""
    raw = (topic or {}).get("requires")
    return raw if isinstance(raw, dict) else {}


def topic_locked(topic: Optional[Dict], state, case: Optional[Dict] = None) -> bool:
    """Закрыта ли тема (например, пока не собрана версия на доске).

    ``"requires": {"board": true}`` — нужен любой собранный вывод,
    ``{"board": "suspect_id"}`` — вывод именно по этому подозреваемому.
    """
    from . import board, testimony

    req = requires(topic)
    if req.get("deduction"):
        return not testimony.has_deduction(state, str(req["deduction"]))
    if not req or "board" not in req:
        return False
    target = req.get("board")
    if target is True:
        return not board.conclusions(case, state)
    item = board.suspect(case, str(target))
    if item is None:
        return True
    return board.conclusion_for(case, state, item) is None


def lock_hint(topic: Optional[Dict], case: Optional[Dict] = None) -> str:
    """Что сделать, чтобы тема открылась (для подсказки в допросе)."""
    from . import board

    ded = requires(topic).get("deduction")
    if ded:
        return "Сначала найдите противоречие в показаниях (блокнот → ВЕРСИИ → ПОКАЗАНИЯ)"
    target = requires(topic).get("board")
    if target is True:
        return "Нужна собранная версия на доске в блокноте"
    item = board.suspect(case, str(target)) if case else None
    if item is None:
        return "Нужна собранная версия на доске в блокноте"
    return f"Свяжите все улики с «{item.get('name')}» на доске версий"


def expose(state, char: Dict, index: int, clue_lookup=None) -> Dict:
    """Уличить персонажа во лжи, предъявив улику.

    Возвращает ``{"status": ...}``: ``ok`` (пойман), ``already`` (уже),
    ``need_clue`` (нужна улика), ``no_lie`` (в теме нет лжи).
    """
    topics = (char or {}).get("dialogue") or []
    if not 0 <= index < len(topics):
        return {"status": "no_lie"}
    topic = topics[index]
    spec = lie(topic)
    if not spec:
        return {"status": "no_lie"}
    char_id = str(char.get("id", ""))
    key = lie_key(char_id, index)
    if key in (getattr(state, "exposed_lies", None) or {}):
        return {"status": "already", "reply": lie_reply(state, char_id, index)}
    clue_id = str(spec["clue"])
    if clue_id not in (getattr(state, "collected_clues", None) or set()):
        return {"status": "need_clue", "clue": clue_id}

    if getattr(state, "exposed_lies", None) is None:
        state.exposed_lies = {}
    state.exposed_lies[key] = str(spec.get("reply", ""))
    delta = int(spec.get("trust", DEFAULT_LIE_TRUST) or 0)
    if delta:
        if getattr(state, "trust", None) is None:
            state.trust = {}
        state.trust[char_id] = trust_of(state, char_id) + delta
    minutes = int(spec.get("time", DEFAULT_LIE_TIME) or 0)
    if minutes:
        state.case_time_minutes = int(getattr(state, "case_time_minutes", 0) or 0) + minutes
    _award_clue(state, spec.get("bonus_clue"), 0, clue_lookup)
    return {
        "status": "ok",
        "reply": str(spec.get("reply", "")),
        "trust_delta": delta,
        "clue": spec.get("bonus_clue"),
    }
