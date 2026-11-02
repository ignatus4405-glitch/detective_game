"""Головоломки: замки, отмычки, сигнализация и последовательности.

Логика отделена от отрисовки: класс :class:`Puzzle` знает правила и состояние,
а экран (``main.draw_puzzle``) только рисует и передаёт клики/клавиши. Поэтому
головоломки можно прогонять в тестах без окна.

Типы:

``safe``      — кодовый замок: 4 цифры, после каждой попытки подсказка по каждой
                цифре (↑ больше, ↓ меньше, = верно);
``lockpick``  — отмычки: бегунок ходит по шкале, надо трижды попасть в зелёную зону;
``wires``     — какой провод резать: набор логических условий, единственный ответ;
``sequence``  — запомнить и повторить последовательность символов.

Спецификация в данных дела (у улики)::

    "puzzle": {"type": "lockpick", "difficulty": 2, "hint": "Замок старый…"}
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .config import WINDOW_HEIGHT, WINDOW_WIDTH  # noqa: F401  (единая конфигурация)

DEFAULT_TITLES = {
    "safe": "КОДОВЫЙ ЗАМОК",
    "lockpick": "ОТМЫЧКИ",
    "wires": "СИГНАЛИЗАЦИЯ",
    "sequence": "ПОСЛЕДОВАТЕЛЬНОСТЬ",
}

DEFAULT_HINTS = {
    "safe": "Четыре цифры. После каждой попытки — подсказка по каждой цифре.",
    "lockpick": "Пробел или клик — когда бегунок в зелёной зоне. Три попадания.",
    "wires": "Прочитайте условия и выберите провод. Ошибка стоит одной попытки.",
    "sequence": "Запомните порядок и повторите его.",
}

DEFAULT_ATTEMPTS = {"safe": 6, "lockpick": 3, "wires": 2, "sequence": 2}

MAX_SAFE_DIGITS = 4
# (именительный, родительный, цвет) — «не красный» и «правее красного»
WIRE_COLORS: List[Tuple[str, str, Tuple[int, int, int]]] = [
    ("красный", "красного", (196, 76, 70)),
    ("синий", "синего", (74, 116, 196)),
    ("зелёный", "зелёного", (86, 168, 110)),
    ("жёлтый", "жёлтого", (206, 184, 84)),
    ("белый", "белого", (214, 212, 200)),
]
SHAPES = ["круг", "квадрат", "треугольник", "ромб"]
SHAPE_COLORS = {
    "круг": (196, 92, 84),
    "квадрат": (92, 132, 196),
    "треугольник": (206, 176, 82),
    "ромб": (104, 168, 118),
}


@dataclass
class Feedback:
    digit: str
    mark: str  # "=", "↑", "↓"

    @property
    def correct(self) -> bool:
        return self.mark == "="


class Puzzle:
    """Состояние одной головоломки."""

    def __init__(self, spec: Optional[Dict], seed: str = ""):
        spec = dict(spec or {})
        self.kind = str(spec.get("type", "safe"))
        if self.kind not in DEFAULT_TITLES:
            self.kind = "safe"
        self.title = str(spec.get("title") or DEFAULT_TITLES[self.kind])
        self.hint = str(spec.get("hint") or DEFAULT_HINTS[self.kind])
        self.difficulty = max(1, min(3, int(spec.get("difficulty", 2) or 2)))
        self.attempts_total = max(1, int(spec.get("attempts", DEFAULT_ATTEMPTS[self.kind])))
        self.attempts_left = self.attempts_total
        self.message = ""
        self.success = False
        self.failed = False
        self.reward = str(spec.get("reward", "") or "")
        self.seed = f"{seed}:{self.kind}:{self.difficulty}"
        self.rng = random.Random(self.seed)
        self.elapsed = 0.0
        # поля по типу
        self.code: List[int] = []
        self.entry: List[int] = []
        self.history: List[Tuple[List[int], List[Feedback]]] = []
        self.targets: List[float] = []
        self.cursor = 0.0
        self.direction = 1.0
        self.speed = 0.5
        self.hits = 0
        self.misses = 0
        self.wires: List[str] = []
        self.constraints: List[str] = []
        self.correct_wire = 0
        self.cut_wire: Optional[int] = None
        self.order: List[str] = []
        self.input: List[str] = []
        self.showing = True
        self.show_index = 0
        self._setup(spec)

    # ── настройка по типу ─────────────────────────────────────────────
    def _setup(self, spec: Dict) -> None:
        if self.kind == "safe":
            digits = spec.get("digits", MAX_SAFE_DIGITS)
            digits = max(3, min(4, int(digits)))
            code = spec.get("code")
            parsed = None
            if isinstance(code, str):
                parsed = [int(ch) for ch in code if ch.isdigit()]
            elif isinstance(code, Sequence):
                parsed = [int(d) % 10 for d in code]
            if parsed and len(parsed) == digits:
                self.code = parsed
            else:
                self.code = [self.rng.randrange(0, 10) for _ in range(digits)]
            self.entry = []
        elif self.kind == "lockpick":
            self.speed = 0.45 + 0.22 * self.difficulty
            width = 0.16 - 0.025 * self.difficulty
            self.targets = []
            for i in range(3):
                center = 0.18 + 0.28 * i + self.rng.uniform(-0.03, 0.03)
                self.targets.append(round(min(0.92, max(0.08, center)), 3))
            self.target_width = width
            self.cursor = 0.0
            self.direction = 1.0
        elif self.kind == "wires":
            self._setup_wires()
        elif self.kind == "sequence":
            length = 3 + self.difficulty  # 4–6
            pool = list(SHAPES)
            order: List[str] = []
            while len(order) < length:
                choice = self.rng.choice(pool)
                if order and choice == order[-1]:
                    continue
                order.append(choice)
            self.order = order
            self.showing = True
            self.show_index = 0
        self._refresh_message()

    def _setup_wires(self) -> None:
        colors = [name for name, _, _ in WIRE_COLORS]
        genitive = {name: gen for name, gen, _ in WIRE_COLORS}
        self.wires = list(colors)
        correct = self.rng.randrange(len(self.wires))
        candidates = set(range(len(self.wires)))
        statements: List[str] = []

        def filter_with(kind: str, arg: str) -> set:
            if kind == "not":
                return {i for i in candidates if colors[i] != arg}
            if kind == "left_of":
                return {i for i in candidates if i < colors.index(arg)}
            if kind == "right_of":
                return {i for i in candidates if i > colors.index(arg)}
            return set(candidates)

        pool: List[Tuple[str, str, str]] = []
        for name in colors:
            pool.append(("not", name, f"Это не {name} провод."))
        for name in colors:
            pool.append(("left_of", name, f"Этот провод левее {genitive[name]}."))
        for name in colors:
            pool.append(("right_of", name, f"Этот провод правее {genitive[name]}."))
        self.rng.shuffle(pool)

        # добавляем условия, пока ответ не станет единственным.
        # Условие принимаем, только если оно отсекает часть вариантов и не
        # обнуляет список: иначе получилось бы противоречие без решения.
        guard = 0
        while len(candidates) > 1 and pool and guard < 60:
            guard += 1
            kind, arg, text = pool.pop()
            narrowed = filter_with(kind, arg)
            if 0 < len(narrowed) < len(candidates):
                candidates = narrowed
                statements.append(text)
        self.correct_wire = sorted(candidates)[0] if candidates else correct
        if len(candidates) > 1:
            # редкий случай: условия не сошлись — даём прямой ответ
            self.correct_wire = min(candidates)
            statements.append(
                f"Журнал техника: обесточивали {colors[self.correct_wire]} провод."
            )
        if not statements:
            statements.append(f"Это {colors[self.correct_wire]} провод — других вариантов нет.")
        self.constraints = statements

    # ── общее состояние ───────────────────────────────────────────────
    @property
    def finished(self) -> bool:
        return self.success or self.failed

    @property
    def progress_text(self) -> str:
        if self.kind == "lockpick":
            return f"Замков взведено: {self.hits}/3  •  промахи: {self.misses}/{self.attempts_total}"
        if self.kind == "safe":
            return f"Попыток: {self.attempts_left}/{self.attempts_total}"
        if self.kind == "wires":
            return f"Попыток: {self.attempts_left}/{self.attempts_total}"
        return f"Попыток: {self.attempts_left}/{self.attempts_total}"

    def _refresh_message(self) -> None:
        if self.success:
            self.message = "Готово. Замок поддался."
        elif self.failed:
            self.message = "Не вышло. Придётся попробовать позже."

    def _win(self) -> None:
        self.success = True
        self._refresh_message()

    def _lose(self, reason: str = "") -> None:
        self.failed = True
        self.message = reason or "Попытки кончились."
        self._refresh_message()

    # ── обновление времени ────────────────────────────────────────────
    def update(self, dt: float) -> None:
        if self.finished:
            return
        dt = max(0.0, min(0.2, float(dt or 0.0)))
        self.elapsed += dt
        if self.kind == "lockpick":
            self.cursor += self.direction * self.speed * dt
            if self.cursor >= 1.0:
                self.cursor = 1.0
                self.direction = -1.0
            elif self.cursor <= 0.0:
                self.cursor = 0.0
                self.direction = 1.0
        elif self.kind == "sequence" and self.showing:
            step = 0.62
            index = int(self.elapsed / step)
            if index >= len(self.order):
                self.showing = False
                self.elapsed = 0.0
            else:
                self.show_index = index

    @property
    def sequence_visible(self) -> Optional[str]:
        if self.kind != "sequence" or not self.showing:
            return None
        if self.show_index < len(self.order):
            return self.order[self.show_index]
        return None

    # ── действия ──────────────────────────────────────────────────────
    def press_digit(self, digit: int) -> None:
        if self.kind != "safe" or self.finished:
            return
        if len(self.entry) >= len(self.code):
            return
        self.entry.append(int(digit) % 10)

    def backspace(self) -> None:
        if self.kind == "safe" and self.entry and not self.finished:
            self.entry.pop()

    def submit_code(self) -> Optional[List[Feedback]]:
        """Проверить введённый код. Возвращает подсказки или None."""
        if self.kind != "safe" or self.finished:
            return None
        if len(self.entry) != len(self.code):
            self.message = "Нужно ввести все цифры."
            return None
        feedback = []
        for guess, real in zip(self.entry, self.code, strict=False):
            if guess == real:
                feedback.append(Feedback(str(guess), "="))
            elif guess < real:
                feedback.append(Feedback(str(guess), "↑"))
            else:
                feedback.append(Feedback(str(guess), "↓"))
        self.history.append((list(self.entry), feedback))
        self.entry = []
        if all(item.correct for item in feedback):
            self._win()
            return feedback
        self.attempts_left -= 1
        if self.attempts_left <= 0:
            self._lose(f"Код не подошёл. Правильный был {''.join(map(str, self.code))}.")
        else:
            self.message = "Не то. Смотрите подсказки по цифрам."
        return feedback

    def strike(self) -> bool:
        """Удар отмычкой: True — попал в зону."""
        if self.kind != "lockpick" or self.finished:
            return False
        hit = any(abs(self.cursor - target) <= self.target_width / 2 for target in self.targets)
        if hit:
            self.hits += 1
            if self.hits >= 3:
                self._win()
            else:
                self.message = "Щёлк! Ещё один."
                self.elapsed = 0.0
        else:
            self.misses += 1
            if self.misses >= self.attempts_total:
                self._lose("Отмычка соскользнула. Замок заклинило.")
            else:
                self.message = "Мимо — слышно, как скрипнул металл."
        return hit

    def cut(self, index: int) -> bool:
        """Перерезать провод. True — если угадал."""
        if self.kind != "wires" or self.finished:
            return False
        self.cut_wire = index
        if index == self.correct_wire:
            self._win()
            return True
        self.attempts_left -= 1
        if self.attempts_left <= 0:
            self._lose("Не тот провод. Сигнализация взвыла.")
        else:
            self.message = "Не он. Провод искрит, но панель ещё жива."
        return False

    def tap(self, shape: str) -> Optional[bool]:
        """Нажать фигуру в игре «последовательность»."""
        if self.kind != "sequence" or self.finished or self.showing:
            return None
        expected = self.order[len(self.input)]
        self.input.append(shape)
        if shape != expected:
            self.attempts_left -= 1
            self.input = []
            if self.attempts_left <= 0:
                self._lose("Последовательность сбилась.")
            else:
                self.message = "Не та фигура. Начните заново."
                self.showing = True
                self.elapsed = 0.0
                self.show_index = 0
            return False
        if len(self.input) == len(self.order):
            self._win()
            return True
        self.message = f"Верно: {len(self.input)} из {len(self.order)}."
        return True

    def restart_sequence(self) -> None:
        if self.kind == "sequence" and not self.finished:
            self.showing = True
            self.elapsed = 0.0
            self.show_index = 0
            self.input = []


# ── спецификации по умолчанию ─────────────────────────────────────────

PUZZLE_TYPES = tuple(DEFAULT_TITLES)


def for_clue(clue: Dict, seed: str = "") -> Optional[Puzzle]:
    """Собрать головоломку для улики или None, если у неё нет замка."""
    spec = (clue or {}).get("puzzle")
    if not spec:
        return None
    return Puzzle(spec, seed=str(seed or (clue or {}).get("id", "")))


def difficulty_label(puzzle: Puzzle) -> str:
    return "★" * puzzle.difficulty + "☆" * (3 - puzzle.difficulty)
