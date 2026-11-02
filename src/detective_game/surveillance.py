"""Слежка: держать дистанцию, не потерять объект и не попасться.

Мини-игра на карте: объект идёт по маршруту, детектив — за ним. Слишком
близко — заметят (растёт «подозрение»), слишком далеко — потеряешь (растёт
«потеря»). Держишь дистанцию в зелёной зоне — обе шкалы остывают.

Управление простое: **→/D** — догонять, **←/A** — отставать, отпустить — идти
ровно. Успех — объект дошёл до конца маршрута, а детектива не раскрыли.

Чистая логика без pygame — тесты гоняют слежку по шагам.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

DEFAULT_SECONDS = 24.0
DEFAULT_BAND = (0.26, 0.68)
CATCH_UP = 1.85  # во сколько раз быстрее объекта идёт детектив с зажатой стрелкой
SLOW_DOWN = 0.0  # стоим на месте
SUSPICION_RATE = 1.35
LOST_RATE = 1.25
COOL_RATE = 0.55

DEFAULT_SPECS: Dict[str, Dict] = {
    "missing_chess": {
        "title": "Слежка за Финчем",
        "target": "Эдвард Финч",
        "place": "Порт Блэквила",
        "requires_clue": "clue_bar_testimony",
        "seconds": 24.0,
        "band": [0.26, 0.68],
        "reveal": "clue_fabric",
        "reputation": 1,
        "money": 120,
        "description": (
            "Бармен сказал, что Финч каждый вечер уходит из «Синей Луны» в порт. "
            "Держитесь на расстоянии: ближе — заметит, дальше — потеряете."
        ),
    },
    "bank_heist": {
        "title": "Слежка за Дереком",
        "target": "Дерек Стоун",
        "place": "Улицы Центра",
        "requires_clue": "clue_coffee",
        "seconds": 22.0,
        "band": [0.26, 0.68],
        "reveal": "clue_harbor_crate",
        "reputation": 1,
        "money": 100,
        "description": (
            "Охранник вышел из банка с спортивной сумкой. Если он идёт в порт — "
            "у вас будет адрес. Если заметит слежку — сорвётся."
        ),
    },
}


# маршруты для «прокладки» до начала слежки: один верный, остальные — крюк
DEFAULT_ROUTES: Dict[str, List[Dict]] = {
    "missing_chess": [
        {
            "id": "river",
            "title": "Вдоль реки",
            "minutes": 15,
            "note": "Финч всегда ходит пешком по набережной: не любит такси.",
            "correct": True,
        },
        {
            "id": "tram",
            "title": "На трамвае",
            "minutes": 25,
            "note": "Быстро, но вагоновожатый знает вас в лицо.",
        },
        {
            "id": "roofs",
            "title": "По крышам",
            "minutes": 35,
            "note": "Коротко по карте — и очень заметно сверху.",
        },
    ],
    "bank_heist": [
        {
            "id": "market",
            "title": "Через рынок",
            "minutes": 18,
            "note": "Дерек обходит банк с запада — через рыбный рынок.",
            "correct": True,
        },
        {
            "id": "alley",
            "title": "Переулками",
            "minutes": 28,
            "note": "Тихо, но там патруль Грея каждые десять минут.",
        },
        {
            "id": "taxi",
            "title": "На такси",
            "minutes": 40,
            "note": "Комфортно. И совершенно бесполезно: пробки.",
        },
    ],
}


def routes_for(case: Optional[Dict]) -> List[Dict]:
    """Варианты маршрута для дела (из данных или встроенные)."""
    case = case or {}
    spec = spec_for(case) or {}
    raw = spec.get("routes") or DEFAULT_ROUTES.get(str(case.get("id", "")), [])
    routes = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        routes.append(
            {
                "id": str(item.get("id") or item["title"]),
                "title": str(item["title"]),
                "minutes": int(item.get("minutes", 20) or 0),
                "note": str(item.get("note", "")),
                "correct": bool(item.get("correct")),
            }
        )
    return routes


def plan(case: Optional[Dict], spec: Optional[Dict], route: Optional[Dict]) -> Dict:
    """Итог прокладки маршрута: как это меняет сложность слежки."""
    route = route or {}
    minutes = int(route.get("minutes", 0) or 0)
    correct = bool(route.get("correct"))
    tuned = dict(spec or {})
    band = list(tuned.get("band") or DEFAULT_BAND)
    if correct:
        band = [max(0.05, band[0] - 0.04), min(0.95, band[1] + 0.04)]
    else:
        band = [min(0.85, band[0] + 0.03), max(0.2, band[1] - 0.03)]
    tuned["band"] = band
    return {
        "correct": correct,
        "minutes": minutes,
        "spec": tuned,
        "message": (
            "Верный маршрут: держать дистанцию будет проще."
            if correct
            else "Крюк: объект может вас заметить — дистанция стала уже."
        ),
    }


def spec_for(case: Optional[Dict]) -> Optional[Dict]:
    """Спецификация слежки для дела (из данных или встроенная)."""
    case = case or {}
    raw = case.get("surveillance") or DEFAULT_SPECS.get(str(case.get("id", "")))
    if not raw:
        return None
    spec = dict(raw)
    spec.setdefault("title", "Слежка")
    spec.setdefault("target", "Объект")
    spec.setdefault("seconds", DEFAULT_SECONDS)
    band = spec.get("band") or DEFAULT_BAND
    try:
        low, high = float(band[0]), float(band[1])
    except (TypeError, ValueError, IndexError):
        low, high = DEFAULT_BAND
    spec["band"] = [max(0.05, min(low, 0.85)), max(0.2, min(high, 0.95))]
    return spec


def blocked(case: Optional[Dict], state) -> bool:
    """Объект насторожился после провала: до какого-то дня слежка закрыта."""
    from . import worldtime

    until = int(getattr(state, "tail_blocked_until_day", 0) or 0)
    if until <= 0:
        return False
    day = worldtime.clock(int(getattr(state, "case_time_minutes", 0) or 0))[0]
    return until > day


def block_text(case: Optional[Dict], state) -> str:
    """Почему слежка недоступна."""
    if not blocked(case, state):
        return ""
    until = int(getattr(state, "tail_blocked_until_day", 0) or 0)
    if until > 10**5:
        return "Объект сменил маршрут — слежка по этому делу закрыта"
    return "Объект насторожился — попробуйте на следующий день"


def register_failure(case: Optional[Dict], state) -> str:
    """Провал слежки: первый — до завтра, второй — навсегда."""
    from . import worldtime

    case_id = str((case or {}).get("id", ""))
    failed = getattr(state, "tail_failed", None)
    if failed is None:
        state.tail_failed = failed = set()
    day = worldtime.clock(int(getattr(state, "case_time_minutes", 0) or 0))[0]
    first = case_id not in failed
    failed.add(case_id)
    if first:
        state.tail_blocked_until_day = day + 1
        return "Объект насторожился: слежка по этому делу — не раньше следующего дня"
    state.tail_blocked_until_day = 10**6
    return "Объект сменил маршрут: слежка по этому делу больше не сработает"


def available(case: Optional[Dict], state) -> bool:
    """Можно ли уже идти на слежку."""
    spec = spec_for(case)
    if not spec:
        return False
    if str(case.get("id", "")) in getattr(state, "tail_done", set()):
        return False
    if blocked(case, state):
        return False
    need = spec.get("requires_clue")
    if need and str(need) not in getattr(state, "collected_clues", set()):
        return False
    return True


class Tail:
    """Состояние одной слежки."""

    def __init__(self, spec: Optional[Dict]):
        spec = dict(spec or {})
        self.spec = spec
        self.title = str(spec.get("title", "Слежка"))
        self.target = str(spec.get("target", "Объект"))
        self.place = str(spec.get("place", ""))
        self.duration = max(8.0, float(spec.get("seconds", DEFAULT_SECONDS)))
        band = spec.get("band") or DEFAULT_BAND
        self.band: Tuple[float, float] = (float(band[0]), float(band[1]))
        self.speed = 1.0 / self.duration
        self.target_t = 0.0
        self.elapsed = 0.0
        self.gap = (self.band[0] + self.band[1]) / 2
        self.suspicion = 0.0
        self.lost = 0.0
        self.success = False
        self.failed = False
        self.last_event = ""
        self.events: List[str] = []

    # ── состояние ─────────────────────────────────────────────────────
    @property
    def finished(self) -> bool:
        return self.success or self.failed

    @property
    def progress(self) -> float:
        return self.target_t

    @property
    def in_band(self) -> bool:
        return self.band[0] <= self.gap <= self.band[1]

    @property
    def message(self) -> str:
        if self.success:
            return self.last_event or "Объект у цели. Вы записали адрес."
        if self.failed:
            return self.last_event or "Слежка сорвалась."
        if self.gap < self.band[0]:
            return "Слишком близко — он может обернуться!"
        if self.gap > self.band[1]:
            return "Слишком далеко — вот-вот потеряете."
        return "Дистанция в норме."

    @property
    def progress_text(self) -> str:
        return f"Маршрут {int(self.target_t * 100)}%  •  дистанция {int(self.gap * 100)}%"

    # ── игровой шаг ───────────────────────────────────────────────────
    def update(self, dt: float, advance: float = 0.0) -> None:
        """Шаг слежки.

        ``advance``: +1 — догонять, 0 — идти ровно, −1 — отставать.
        """
        if self.finished:
            return
        dt = max(0.0, min(0.25, float(dt or 0.0)))
        if dt <= 0.0:
            return
        self.elapsed += dt
        step = self.speed * dt
        multiplier = {1: CATCH_UP, 0: 1.0, -1: SLOW_DOWN}.get(int(advance), 1.0)
        self.target_t = min(1.0, self.target_t + step)
        self.gap += (1.0 - multiplier) * step
        self.gap = max(0.0, min(1.0, self.gap))

        low, high = self.band
        if self.gap < low:
            depth = (low - self.gap) / max(low, 0.05)
            self.suspicion += dt * SUSPICION_RATE * (0.35 + depth)
            self.lost = max(0.0, self.lost - dt * COOL_RATE * 0.5)
        elif self.gap > high:
            depth = (self.gap - high) / max(1.0 - high, 0.05)
            self.lost += dt * LOST_RATE * (0.35 + depth)
            self.suspicion = max(0.0, self.suspicion - dt * COOL_RATE * 0.5)
        else:
            self.suspicion = max(0.0, self.suspicion - dt * COOL_RATE)
            self.lost = max(0.0, self.lost - dt * COOL_RATE)

        self.suspicion = min(1.0, self.suspicion)
        self.lost = min(1.0, self.lost)

        if self.suspicion >= 1.0:
            self.failed = True
            self._event("Финч обернулся и посмотрел прямо на вас.")
        elif self.lost >= 1.0:
            self.failed = True
            self._event("Вы потеряли его из виду на повороте.")
        elif self.target_t >= 1.0:
            self.success = True
            self._event(f"{self.target} дошёл до цели незамеченным.")

    def _event(self, text: str) -> None:
        self.last_event = text
        self.events.append(text)

    def set_gap(self, gap: float) -> None:
        self.gap = max(0.0, min(1.0, float(gap)))

    def restart(self) -> None:
        self.__init__(self.spec)


def apply_reward(case: Optional[Dict], state, spec: Optional[Dict]) -> Dict:
    """Награда за удачную слежку: улика/деньги/репутация."""
    spec = spec or {}
    case_id = str((case or {}).get("id", ""))
    result = {"reveal": None, "money": 0, "reputation": 0}
    done = set(getattr(state, "tail_done", set()))
    done.add(case_id)
    state.tail_done = done
    reveal = spec.get("reveal")
    if reveal:
        hidden = set(getattr(state, "hidden_found", set()))
        hidden.add(str(reveal))
        state.hidden_found = hidden
        result["reveal"] = str(reveal)
    money = int(spec.get("money", 0) or 0)
    if money:
        state.money = int(getattr(state, "money", 0)) + money
        result["money"] = money
    rep = int(spec.get("reputation", 0) or 0)
    if rep:
        state.reputation = int(getattr(state, "reputation", 0)) + rep
        result["reputation"] = rep
    return result


__all__ = [
    "DEFAULT_ROUTES",
    "DEFAULT_SPECS",
    "Tail",
    "apply_reward",
    "available",
    "plan",
    "routes_for",
    "spec_for",
]
