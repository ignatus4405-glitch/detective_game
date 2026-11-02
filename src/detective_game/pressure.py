"""Правила «взрослого» расследования: сроки, цена ошибки и допуски.

Механики включаются не во всех делах: в данных дела стоит ``"advanced": true``.
Учебное дело остаётся простым — там ничего не штрафуется, а игрок учится
ходить по карте. Начиная со второго дела включаются:

* **срок дела** — прокурор ждёт ограниченное время (по умолчанию 3 дня);
* **платные промахи** — пустая точка при обыске и повторный вопрос стоят;
* **экспертиза** — часть улик нужно подтвердить в лаборатории;
* **таймер реплики** — молчание в допросе стоит доверия;
* **сопоставление показаний**, **суд с мотивом и способом**;
* **патруль при обыске**, **риск слежки**, **анонимные звонки**.

Модуль держит только числа и правила, а не состояние экранов: так баланс
правится в одном месте и покрывается тестами.
"""

from __future__ import annotations

from typing import Dict, Optional

DAY_MINUTES = 24 * 60
DEFAULT_DEADLINE_DAYS = 3

# цена промахов
EMPTY_CLICK_MINUTES = 2
REPEAT_TOPIC_TRUST = 1
DIALOGUE_SECONDS = 10.0
SILENCE_TRUST = 1

# лаборатория
LAB_MINUTES = 45
LAB_COST = 50
LAB_REPUTATION = 2

# обыск с патрулём
PATROL_CAUGHT_MINUTES = 15

# слежка
TAIL_ALERT_SUSPICION = 0.7
TAIL_COOLDOWN_MINUTES = DAY_MINUTES
TAIL_ALERT_MINUTES = 20

# анонимные звонки
CALL_FIRST_MINUTE = 90
CALL_EVERY_MINUTES = 150
CALL_MINUTES = 5
CALL_TRAP_CHANCE = 0.4
CALL_TRAP_MINUTES = 45

# суд
TRIAL_RANK_BONUS = 1


def advanced(case: Optional[Dict]) -> bool:
    """Включены ли «взрослые» правила в этом деле."""
    return bool((case or {}).get("advanced"))


def deadline_minutes(case: Optional[Dict]) -> int:
    """Срок дела в игровых минутах (0 — срока нет)."""
    case = case or {}
    if not advanced(case):
        return 0
    raw = case.get("deadline_minutes")
    if raw is None:
        days = case.get("deadline_days", DEFAULT_DEADLINE_DAYS)
        try:
            return max(1, int(days)) * DAY_MINUTES
        except (TypeError, ValueError):
            return DEFAULT_DEADLINE_DAYS * DAY_MINUTES
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_DEADLINE_DAYS * DAY_MINUTES


def remaining(state, case: Optional[Dict]) -> int:
    """Сколько игровых минут осталось до срока (может быть отрицательным)."""
    limit = deadline_minutes(case)
    if not limit:
        return 0
    spent = int(getattr(state, "case_time_minutes", 0) or 0)
    return limit - spent


def has_deadline(case: Optional[Dict]) -> bool:
    return deadline_minutes(case) > 0


def is_late(state, case: Optional[Dict]) -> bool:
    return has_deadline(case) and remaining(state, case) <= 0


def has_slipped_case(state, case: Optional[Dict]) -> bool:
    """Срок превышен настолько, что дело пора закрывать принудительно."""
    limit = deadline_minutes(case)
    if not limit:
        return False
    return remaining(state, case) <= -max(1, limit // 2)


def duration_text(minutes: int) -> str:
    """«2 д 4 ч», «45 мин», «просрочено на 3 ч»."""
    minutes = int(minutes)
    late = minutes < 0
    minutes = abs(minutes)
    days, rest = divmod(minutes, DAY_MINUTES)
    hours, mins = divmod(rest, 60)
    if days:
        text = f"{days} д {hours} ч"
    elif hours:
        text = f"{hours} ч {mins:02d} м"
    else:
        text = f"{mins} мин"
    return f"просрочено на {text}" if late else text


def deadline_text(state, case: Optional[Dict]) -> str:
    """Строка для шапки карты: сколько осталось до срока."""
    if not has_deadline(case):
        return "срок не ограничен"
    left = remaining(state, case)
    if left <= 0:
        return f"СРОК ВЫШЕЛ · {duration_text(left)}"
    return f"до срока {duration_text(left)}"


def deadline_chip(state, case: Optional[Dict]) -> str:
    """Короткая версия для чипа ресурсов."""
    if not has_deadline(case):
        return ""
    left = remaining(state, case)
    if left <= 0:
        return "СРОК ВЫШЕЛ"
    days, rest = divmod(left, DAY_MINUTES)
    hours = rest // 60
    if days:
        return f"срок: {days} д {hours} ч"
    return f"срок: {duration_text(left)}"


def can_afford_lab(state) -> Dict[str, bool]:
    """Хватает ли денег и репутации на экспертизу."""
    money = int(getattr(state, "money", 0) or 0)
    reputation = int(getattr(state, "reputation", 0) or 0)
    return {
        "money": money >= LAB_COST,
        "reputation": reputation >= LAB_REPUTATION,
    }


def lab_ready(state) -> bool:
    return all(can_afford_lab(state).values())


def call_due(state, case: Optional[Dict]) -> int:
    """Пора ли звонить анониму: возвращает номер звонка (0 — рано)."""
    if not advanced(case):
        return 0
    seen = int(getattr(state, "calls_seen", 0) or 0)
    if seen >= 3:
        return 0
    at = CALL_FIRST_MINUTE + seen * CALL_EVERY_MINUTES
    spent = int(getattr(state, "case_time_minutes", 0) or 0)
    return seen + 1 if spent >= at else 0
