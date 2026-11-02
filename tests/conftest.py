"""Общая настройка тестов: без окна и без фоновой сетевой проверки обновлений.

`Game()` при старте поднимает поток апдейтера, который ходит в GitHub. В тестах
этот поток (а) лезет в сеть на каждый созданный объект игры и (б) может
пересекаться с отрисовкой шрифтов pygame — в CI это иногда давало
`Segmentation fault`. Поэтому авто-проверку в тестах не запускаем: сами тесты
обновлений создают `UpdateChecker` напрямую и работают с ним синхронно.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_background_update_check(monkeypatch):
    """`UpdateChecker.start()` в тестах ничего не делает — ни сети, ни потоков."""
    try:
        from detective_game import main as game_main
    except Exception:  # pragma: no cover - pygame может отсутствовать
        return

    checker_cls = getattr(game_main, "UpdateChecker", None)
    if checker_cls is None:  # pragma: no cover
        return

    class _QuietChecker(checker_cls):
        def start(self, *args, **kwargs):
            return None

    monkeypatch.setattr(game_main, "UpdateChecker", _QuietChecker)
