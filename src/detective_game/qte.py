"""Драка в баре — редкое QTE: три удара по подсказке.

В «Синей Луне» можно нарваться на пьяного, которому не понравился ваш
вопрос. Это короткая проверка реакции: на экране появляется стрелка, её нужно
нажать за отведённое время. Три точных нажатия — вы стоите, толпа уважает;
два промаха — вы теряете время (и достоинство), но дело не ломается.

Чистая логика без pygame: экран только показывает подсказку и шкалу.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

PROMPTS = ("left", "right", "up", "down")
PROMPT_KEYS = {"left": "A / ←", "right": "D / →", "up": "W / ↑", "down": "S / ↓"}
WINDOW = 1.15  # секунд на реакцию
ROUNDS = 3
MAX_MISSES = 2


def prompts_for(seed: str, rounds: int = ROUNDS) -> List[str]:
    """Последовательность подсказок, одинаково воспроизводимая для сида."""
    rng = random.Random(f"qte:{seed}")
    result: List[str] = []
    for _ in range(max(1, rounds)):
        choice = rng.choice(PROMPTS)
        if result and choice == result[-1]:
            choice = PROMPTS[(PROMPTS.index(choice) + 1) % len(PROMPTS)]
        result.append(choice)
    return result


class BarFight:
    """Состояние одной драки: раунды, таймер, попадания."""

    def __init__(self, seed: str = "", rounds: int = ROUNDS, window: float = WINDOW):
        self.sequence = prompts_for(seed, rounds)
        self.window = max(0.4, float(window))
        self.index = 0
        self.remaining = self.window
        self.hits = 0
        self.misses = 0
        self.success = False
        self.failed = False
        self.message = "Он замахивается. Жмите по подсказке!"

    @property
    def prompt(self) -> Optional[str]:
        if self.finished or self.index >= len(self.sequence):
            return None
        return self.sequence[self.index]

    @property
    def prompt_label(self) -> str:
        return PROMPT_KEYS.get(self.prompt or "", "")

    @property
    def progress(self) -> float:
        """Доля времени, оставшаяся на реакцию (1 — только появилась)."""
        return max(0.0, min(1.0, self.remaining / self.window))

    @property
    def finished(self) -> bool:
        return self.success or self.failed

    @property
    def result_text(self) -> str:
        if self.success:
            return "Вы устояли. Бармен молча ставит стакан — за счёт заведения."
        if self.failed:
            return "Вас вытолкали на улицу. Время потеряно, но дело не закрыто."
        return self.message

    def update(self, dt: float) -> None:
        if self.finished:
            return
        self.remaining -= max(0.0, float(dt or 0.0))
        if self.remaining <= 0.0:
            self._miss("Поздно — удар прошёл мимо блока.")

    def press(self, direction: str) -> bool:
        """Нажата стрелка. True — попадание."""
        if self.finished:
            return False
        if direction == self.prompt:
            self.hits += 1
            self.index += 1
            self.remaining = self.window
            if self.index >= len(self.sequence):
                self.success = True
                self.message = "Чисто. Трое на полу, вы — на ногах."
            else:
                self.message = f"Блок! {self.hits} из {len(self.sequence)}."
            return True
        self._miss("Не в ту сторону — пропустили удар.")
        return False

    def _miss(self, text: str) -> None:
        self.misses += 1
        self.index += 1
        self.remaining = self.window
        self.message = text
        if self.misses >= MAX_MISSES or self.index >= len(self.sequence):
            self.success = self.hits >= len(self.sequence) - MAX_MISSES and self.misses < MAX_MISSES
            self.failed = not self.success
            self.index = len(self.sequence)


def reward(success: bool) -> Dict:
    """Что драка даёт делу."""
    if success:
        return {"reputation": 1, "money": 40, "time": 0}
    return {"reputation": 0, "money": 0, "time": 20}


__all__ = [
    "MAX_MISSES",
    "PROMPTS",
    "PROMPT_KEYS",
    "ROUNDS",
    "WINDOW",
    "BarFight",
    "prompts_for",
    "reward",
]
