"""Обыск локации: точки на картинке, таймер и скрытые улики.

Улика может быть «спрятана» (``"hidden": true``): в списке справа её нет, пока
игрок не найдёт её на иллюстрации локации. Позиции точек детерминированы —
одна и та же улика всегда в одном месте, так что её можно запомнить и показать
другому.

Обыск ограничен по времени («хозяин вот-вот вернётся»). Успел — забираешь
улику; не успел — попытка стоит времени, но точки остаются на месте и
попробовать можно снова.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set

DEFAULT_SECONDS = 60
CLICK_RADIUS = 0.055
DECOYS_PER_LOCATION = 2
# патруль в больших делах: подсвеченный сектор нельзя трогать
PATROL_CYCLE = 6.0

# что можно найти «не по делу» — атмосфера и потерянное время
FLAVOUR = {
    "bar": [
        "Пепельница, полная окурков. Кто-то сидел здесь всю ночь.",
        "Под стойкой — чужая зажигалка с монограммой. Не пригодится.",
        "Старая афиша боксёрского матча. Мик действительно дрался.",
    ],
    "warehouse": [
        "Ржавый гвоздь и клочок брезента. Ничего.",
        "Пустые ящики с логотипом банка. Уже обысканы.",
        "След от ботинка в пыли — размер не сходится.",
    ],
    "police": [
        "Стопка старых протоколов. Все — по чужим делам.",
        "Кофейная чашка сержанта Грея. Ещё тёплая.",
        "Ключ от архива без бирки. Не тот, что нужен.",
    ],
    "crime": [
        "Лента ограждения, бумажный стаканчик, чей-то окурок.",
        "Мокрая листва. Под ней — ничего.",
        "Следы шин. Проехала патрульная машина.",
    ],
    "bank": [
        "Мрамор, охрана, нервный управляющий. Всё как в отчёте.",
        "Брошюра «Как открыть вклад». Не сейчас.",
        "Ковёр с пятном. Кофе, не кровь.",
    ],
    "vault": [
        "Открытая ячейка 313: пусто, если не считать пыли.",
        "Осколок стекла. Откуда он здесь?",
        "Инструкция по сейфам. Пригодилась бы раньше.",
    ],
    "apartment": [
        "Недопитая чашка на столе. Уже остыла.",
        "Фотография на полке: двое смеются, третий обрезан.",
        "Ящик с инструментами. Молоток на месте.",
    ],
    "public": [
        "Расписание занятий. Кто-то обвёл среду.",
        "Потерянная перчатка. Не по сезону.",
        "Стул с отломанной ножкой. Ничего интересного.",
    ],
    "shop": [
        "Реактивы стоят по алфавиту — хозяин был аккуратен.",
        "Плёнка с чужой свадьбы. Не то.",
        "Список заказов: половина имён вычеркнута.",
    ],
    "mansion": [
        "Пыль на рояле. Играли недавно, но не здесь.",
        "Пустая рама на стене. Картину сняли в спешке.",
        "Пепел в камине. Бумаги жгли ночью.",
    ],
    "port": [
        "Чайка на кране. Провожает вас взглядом.",
        "Канат, соль, ржавчина. Ни одной зацепки.",
        "Контейнер без пломбы. Внутри — пусто.",
    ],
}
DEFAULT_FLAVOUR = [
    "Пыль, тени и ничего полезного.",
    "Вы перевернули всё, но здесь пусто.",
    "Ещё один угол, где правды нет.",
]


def is_hidden(clue: Optional[Dict]) -> bool:
    return bool((clue or {}).get("hidden"))


def is_revealed(state, clue: Optional[Dict]) -> bool:
    """Видна ли улика в обычном списке."""
    if not clue:
        return False
    if not is_hidden(clue):
        return True
    clue_id = str(clue.get("id"))
    return clue_id in getattr(state, "hidden_found", set()) or clue_id in getattr(
        state, "collected_clues", set()
    )


def visible_clues(case: Optional[Dict], location_id: str, state) -> List[Dict]:
    return [
        clue
        for clue in (case or {}).get("clues", [])
        if clue.get("location") == location_id and is_revealed(state, clue)
    ]


def hidden_here(case: Optional[Dict], location_id: str, state) -> List[Dict]:
    return [
        clue
        for clue in (case or {}).get("clues", [])
        if clue.get("location") == location_id
        and is_hidden(clue)
        and not is_revealed(state, clue)
    ]


def _positions(case_id: str, location_id: str, count: int) -> List[tuple]:
    """Раскидать точки по шести «клеткам» картинки без наложений."""
    rng = random.Random(f"search:{case_id}:{location_id}")
    cells = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
    rng.shuffle(cells)
    spots = []
    for index in range(max(1, count)):
        cx, cy = cells[index % len(cells)]
        x = 0.14 + cx * 0.28 + rng.uniform(-0.05, 0.05)
        y = 0.34 + cy * 0.24 + rng.uniform(-0.04, 0.04)
        # держим точки ниже шкалы таймера и выше нижней подписи
        spots.append((round(min(0.9, max(0.1, x)), 3), round(min(0.68, max(0.30, y)), 3)))
    return spots


def _spot_coords(raw, fallback) -> tuple:
    """Координаты точки из данных дела (``"spot": [x, y]`` в долях картинки)."""
    try:
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            x, y = float(raw[0]), float(raw[1])
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return round(x, 3), round(y, 3)
    except (TypeError, ValueError):
        pass
    return fallback


def build(case: Optional[Dict], location_id: str, state) -> List[Dict]:
    """Все точки обыска в локации (кроме уже найденных)."""
    case = case or {}
    case_id = str(case.get("id", ""))
    location = next(
        (loc for loc in case.get("locations", []) if loc.get("id") == location_id), {}
    )
    loc_type = str(location.get("type", ""))
    clues = hidden_here(case, location_id, state)
    decoys = list(FLAVOUR.get(loc_type, DEFAULT_FLAVOUR))[:DECOYS_PER_LOCATION]
    positions = _positions(case_id, location_id, len(clues) + len(decoys))
    found: Set[str] = set(getattr(state, "search_found", set()))

    spots: List[Dict] = []
    for index, clue in enumerate(clues):
        spot_id = f"{location_id}:clue:{clue.get('id')}"
        if spot_id in found:
            continue
        x, y = _spot_coords(clue.get("spot"), positions[index])
        spots.append(
            {
                "id": spot_id,
                "x": x,
                "y": y,
                "kind": "clue",
                "clue": str(clue.get("id")),
                "label": "Что-то блестит в пыли",
            }
        )
    offset = len(clues)
    for index, text in enumerate(decoys):
        spot_id = f"{location_id}:flavour:{index}"
        if spot_id in found:
            continue
        x, y = positions[offset + index]
        spots.append(
            {
                "id": spot_id,
                "x": x,
                "y": y,
                "kind": "flavour",
                "clue": None,
                "label": text,
            }
        )
    return spots


class Search:
    """Сессия обыска: точки, таймер, найденное."""

    def __init__(self, case: Optional[Dict], location_id: str, state, seconds: int = DEFAULT_SECONDS):
        self.case = case or {}
        self.location_id = str(location_id)
        self.seconds = max(10, int(seconds or DEFAULT_SECONDS))
        self.remaining = float(self.seconds)
        self.spots = build(self.case, self.location_id, state)
        self.found: List[Dict] = []
        self.expired = False
        self._state = state
        from . import pressure

        self.patrol_on = pressure.advanced(self.case)
        self.elapsed = 0.0
        self.caught = False
        self.misses = 0

    @property
    def total(self) -> int:
        return len(self.spots)

    @property
    def found_count(self) -> int:
        return len(self.found)

    @property
    def clue_spots_left(self) -> int:
        return sum(1 for spot in self.spots if spot["kind"] == "clue")

    @property
    def finished(self) -> bool:
        return self.expired or self.clue_spots_left == 0 or not self.spots

    def update(self, dt: float) -> None:
        if self.finished:
            return
        step = max(0.0, float(dt or 0.0))
        self.elapsed += step
        self.remaining = max(0.0, self.remaining - step)
        if self.remaining <= 0.0:
            self.expired = True

    # ── патруль ───────────────────────────────────────────────────
    def patrol_cell(self) -> tuple:
        """Литой сектор 2×2, в котором сейчас ходит охранник."""
        step = int(self.elapsed // PATROL_CYCLE) % 4
        return step % 2, step // 2

    def patrol_rect(self) -> tuple:
        """Сектор в долях картинки: ``(x, y, w, h)``."""
        col, row = self.patrol_cell()
        return (col * 0.5, row * 0.5, 0.5, 0.5)

    def in_patrol(self, x: float, y: float) -> bool:
        if not self.patrol_on:
            return False
        px, py, pw, ph = self.patrol_rect()
        return px <= x < px + pw and py <= y < py + ph

    def miss(self) -> int:
        """Пустой клик: в больших делах стоит времени."""
        from . import pressure

        self.misses += 1
        minutes = pressure.EMPTY_CLICK_MINUTES if self.patrol_on else 0
        if minutes:
            self._state.case_time_minutes = (
                int(getattr(self._state, "case_time_minutes", 0) or 0) + minutes
            )
        return minutes

    def at(self, x: float, y: float, radius: float = CLICK_RADIUS) -> Optional[Dict]:
        """Точка под курсором (x, y — доли от размера картинки)."""
        best = None
        best_dist = radius
        for spot in self.spots:
            dist = ((spot["x"] - x) ** 2 + (spot["y"] - y) ** 2) ** 0.5
            if dist <= best_dist:
                best, best_dist = spot, dist
        return best

    def take(self, spot: Optional[Dict]) -> Optional[Dict]:
        """Найти точку. Возвращает описание находки."""
        if not spot or self.finished or spot not in self.spots:
            return None
        self.spots.remove(spot)
        self.found.append(spot)
        found = set(getattr(self._state, "search_found", set()))
        found.add(str(spot["id"]))
        self._state.search_found = found
        if spot["kind"] == "clue":
            hidden = set(getattr(self._state, "hidden_found", set()))
            hidden.add(str(spot["clue"]))
            self._state.hidden_found = hidden
        return spot

    def skip(self) -> None:
        """Закончить обыск (ушли или время вышло)."""
        self.expired = True


__all__ = [
    "CLICK_RADIUS",
    "DEFAULT_SECONDS",
    "Search",
    "build",
    "hidden_here",
    "is_hidden",
    "is_revealed",
    "visible_clues",
]
