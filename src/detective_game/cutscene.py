"""Видео-катсцены: «что произошло до того, как вы взялись за дело».

Формат — не видео-файл, а **слайд-шоу с движением**: каждая сцена это
иллюстрация с медленным наездом (эффект Кена Бёрнса), затемнением по краям,
печатающейся подписью-субтитром и таймлайном. Так катсцена весит десятки
килобайт вместо десятков мегабайт, работает без кодеков и одинаково
выглядит на любой машине.

Логика (``CutscenePlayer``) отделена от отрисовки (``draw_cutscene``), чтобы
тесты могли проматывать сцены без экрана.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pygame

from .config import WINDOW_HEIGHT, WINDOW_WIDTH
from .ui.artwork import cover_image
from .ui.widgets import Button, draw_panel, get_font, wrap_text

FADE = 0.45  # секунд на появление/угасание кадра
CHARS_PER_SECOND = 46.0
MIN_READ_TIME = 2.6  # минимум на сцену, даже если подпись короткая
ZOOM_STEPS = 10  # сколько кадров «наезда» готовим заранее
ZOOM_RANGE = 0.10  # насколько камера приближается к концу сцены
ACCENT = (214, 178, 74)
TEXT = (240, 236, 226)
TEXT_DIM = (170, 168, 158)


@dataclass
class Scene:
    """Один кадр катсцены."""

    image: str
    caption: str
    duration: float = 5.0
    label: str = ""
    pan: str = "in"  # in | out | left | right


@dataclass
class Cutscene:
    """Катсцена дела: заголовок и сцены."""

    case_id: str
    title: str
    subtitle: str = ""
    scenes: List[Scene] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.scenes)


def read_time(caption: str) -> float:
    """Сколько секунд комфортно читать подпись."""
    return max(MIN_READ_TIME, 1.4 + len(caption) / CHARS_PER_SECOND)


def scene_duration(scene: Scene) -> float:
    """Полная длительность сцены: подпись + пауза."""
    return max(float(scene.duration or 0.0), read_time(scene.caption) + 0.9)


class CutscenePlayer:
    """Проигрыватель катсцены: сцены, время, печатающийся текст."""

    def __init__(self, cutscene: Optional[Cutscene], width: int = WINDOW_WIDTH,
                 height: int = WINDOW_HEIGHT):
        self.cutscene = cutscene or Cutscene("", "")
        self.width = width
        self.height = height
        self.index = 0
        self.elapsed = 0.0
        self.total_elapsed = 0.0
        self.finished = not self.cutscene.scenes
        self._frames: Dict[int, List[pygame.Surface]] = {}
        self._current_image: Optional[str] = None

    # ── состояние ────────────────────────────────────────────────────
    @property
    def scenes(self) -> Sequence[Scene]:
        return self.cutscene.scenes

    @property
    def scene(self) -> Optional[Scene]:
        if self.finished or not self.scenes:
            return None
        return self.scenes[min(self.index, len(self.scenes) - 1)]

    @property
    def duration(self) -> float:
        scene = self.scene
        return scene_duration(scene) if scene else 0.0

    @property
    def progress(self) -> float:
        """Прогресс текущей сцены 0..1."""
        duration = self.duration
        if duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed / duration))

    @property
    def revealed(self) -> int:
        """Сколько символов подписи уже напечатано."""
        scene = self.scene
        if not scene:
            return 0
        text = scene.caption or ""
        # первые 0.35 с — только появление кадра
        shown = max(0.0, self.elapsed - 0.35) * CHARS_PER_SECOND
        return int(min(len(text), shown))

    @property
    def typing_done(self) -> bool:
        scene = self.scene
        if not scene:
            return True
        return self.revealed >= len(scene.caption or "")

    def visible_caption(self) -> str:
        scene = self.scene
        if not scene:
            return ""
        return (scene.caption or "")[: self.revealed]

    # ── управление ───────────────────────────────────────────────────
    def update(self, dt: float) -> bool:
        """Продвинуть время. True — если катсцена закончилась на этом кадре."""
        if self.finished:
            return False
        dt = max(0.0, min(float(dt or 0.0), 0.25))
        self.elapsed += dt
        self.total_elapsed += dt
        if self.elapsed >= self.duration:
            self.next_scene()
        return self.finished

    def next_scene(self) -> None:
        """Следующая сцена или конец катсцены."""
        if self.finished:
            return
        self.index += 1
        self.elapsed = 0.0
        if self.index >= len(self.scenes):
            self.finished = True
            self.index = len(self.scenes)

    def advance(self) -> None:
        """Клик/пробел: сначала досрочно показать подпись, потом сменить кадр."""
        if self.finished:
            return
        if not self.typing_done:
            self.elapsed = max(self.elapsed, self.typing_time + 0.35)
            return
        self.next_scene()

    @property
    def typing_time(self) -> float:
        scene = self.scene
        if not scene:
            return 0.0
        return len(scene.caption or "") / CHARS_PER_SECOND

    def skip(self) -> None:
        """Пропустить катсцену целиком."""
        self.index = len(self.scenes)
        self.elapsed = 0.0
        self.finished = True

    def restart(self) -> None:
        self.index = 0
        self.elapsed = 0.0
        self.total_elapsed = 0.0
        self.finished = not self.scenes

    # ── кадры «наезда» ───────────────────────────────────────────────
    def frames(self) -> List[pygame.Surface]:
        """Готовые кадры наезда камеры для текущей сцены (ленивый кэш)."""
        scene = self.scene
        if not scene or not scene.image:
            return []
        if scene.image in self._frames:
            return self._frames[scene.image]
        w, h = int(self.width * (1 + ZOOM_RANGE)), int(self.height * (1 + ZOOM_RANGE))
        base = cover_image(scene.image, (w, h))
        if not base:
            return []
        result: List[pygame.Surface] = []
        for step in range(ZOOM_STEPS):
            zoom = 1.0 + ZOOM_RANGE * (step / max(1, ZOOM_STEPS - 1))
            crop_w = max(1, int(w / zoom))
            crop_h = max(1, int(h / zoom))
            drift = int((w - crop_w) * (step / max(1, ZOOM_STEPS - 1)))
            rect = pygame.Rect(0, 0, crop_w, crop_h)
            if scene.pan == "out":
                rect.topleft = (drift, (h - crop_h) // 2)
            elif scene.pan == "left":
                rect.topleft = (w - crop_w - drift, (h - crop_h) // 2)
            elif scene.pan == "right":
                rect.topleft = (drift, (h - crop_h) // 2)
            else:
                rect.center = (w // 2, h // 2)
            try:
                frame = pygame.transform.smoothscale(base.subsurface(rect), (self.width, self.height))
            except Exception:
                frame = pygame.transform.scale(base.subsurface(rect), (self.width, self.height))
            result.append(frame)
        self._frames[scene.image] = result
        return result

    def current_frame(self) -> Optional[pygame.Surface]:
        frames = self.frames()
        if not frames:
            return None
        step = int(self.progress * (len(frames) - 1))
        return frames[max(0, min(len(frames) - 1, step))]

    def clear_cache(self) -> None:
        self._frames.clear()


# ── отрисовка ────────────────────────────────────────────────────────


def _vignette(size, strength: int = 150) -> pygame.Surface:
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = 28
    for i in range(steps):
        alpha = int(strength * ((i / steps) ** 2))
        inset = int(min(w, h) * 0.5 * (1 - i / steps))
        rect = pygame.Rect(inset, inset, w - inset * 2, h - inset * 2)
        pygame.draw.rect(surf, (0, 0, 0, alpha), rect, width=max(2, inset // 6), border_radius=inset // 2)
    return surf


def draw_cutscene(surface: pygame.Surface, player: CutscenePlayer) -> None:
    """Нарисовать текущий кадр катсцены с субтитром и управлением."""
    w, h = surface.get_size()
    surface.fill((6, 7, 10))
    scene = player.scene
    if not scene:
        return
    frame = player.current_frame()
    if frame:
        surface.blit(frame, (0, 0))
    else:
        # запасной фон, если картинки нет
        for i in range(h):
            shade = 14 + int(26 * i / max(1, h))
            pygame.draw.line(surface, (shade, shade + 2, shade + 6), (0, i), (w, i))

    # затемнение сверху и снизу под подписи
    top = pygame.Surface((w, int(h * 0.22)), pygame.SRCALPHA)
    for row in range(top.get_height()):
        pygame.draw.line(top, (4, 5, 8, int(190 * (1 - row / top.get_height()))), (0, row), (w, row))
    surface.blit(top, (0, 0))
    bottom_h = int(h * 0.34)
    bottom = pygame.Surface((w, bottom_h), pygame.SRCALPHA)
    for row in range(bottom_h):
        alpha = int(225 * (row / max(1, bottom_h)) ** 1.25)
        pygame.draw.line(bottom, (4, 5, 8, alpha), (0, row), (w, row))
    surface.blit(bottom, (0, h - bottom_h))
    surface.blit(_vignette((w, h), 140), (0, 0))

    # появление/угасание кадра
    fade = 0.0
    if player.elapsed < FADE:
        fade = 1.0 - player.elapsed / FADE
    remaining = player.duration - player.elapsed
    if 0.0 <= remaining < FADE:
        fade = max(fade, 1.0 - remaining / FADE)
    if fade > 0.001:
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(255 * min(1.0, fade))))
        surface.blit(veil, (0, 0))

    # верхняя строка: название дела и метка сцены
    font_label = get_font(11, bold=True)
    title = font_label.render(player.cutscene.title.upper(), True, ACCENT)
    surface.blit(title, (32, 24))
    if scene.label:
        tag = font_label.render(scene.label.upper(), True, TEXT_DIM)
        surface.blit(tag, (32, 44))
    if player.cutscene.subtitle:
        sub = get_font(10).render(player.cutscene.subtitle, True, TEXT_DIM)
        surface.blit(sub, (32, 62))

    # таймлайн сцен
    dots = len(player.scenes)
    if dots:
        # индикатор сцен — под кнопкой «пропустить», чтобы не спорить с подписью
        dot_y = 62
        total_w = dots * 26
        start_x = w - 32 - total_w
        for i in range(dots):
            cx = start_x + i * 26 + 9
            filled = i < player.index or (i == player.index and player.progress > 0.55)
            color = ACCENT if i == player.index else ((150, 140, 110) if filled else (70, 70, 80))
            pygame.draw.circle(surface, color, (cx, dot_y), 4)
            if i == player.index:
                pygame.draw.circle(surface, ACCENT, (cx, dot_y), 7, width=1)

    # подпись
    caption = player.visible_caption()
    if caption:
        font_cap = get_font(19)
        max_w = w - 220
        lines = wrap_text(caption, font_cap, max_w)
        line_h = font_cap.get_linesize()
        total_h = len(lines) * line_h
        base_y = h - 112 - total_h // 2
        for i, line in enumerate(lines):
            text = font_cap.render(line, True, TEXT)
            shadow = font_cap.render(line, True, (0, 0, 0))
            x = (w - text.get_width()) // 2
            y = base_y + i * line_h
            surface.blit(shadow, (x + 2, y + 2))
            surface.blit(text, (x, y))

    # прогресс сцены
    bar = pygame.Rect(32, h - 52, w - 64, 3)
    pygame.draw.rect(surface, (44, 44, 54), bar, border_radius=2)
    filled_w = int(bar.w * (player.index + player.progress) / max(1, len(player.scenes)))
    pygame.draw.rect(surface, ACCENT, (bar.x, bar.y, max(0, filled_w), bar.h), border_radius=2)

    hint = get_font(10).render(
        "КЛИК / ПРОБЕЛ — ДАЛЬШЕ   •   ESC — ПРОПУСТИТЬ", True, TEXT_DIM
    )
    surface.blit(hint, (32, h - 40))
    counter = get_font(10, bold=True).render(
        f"{min(player.index + 1, len(player.scenes))}/{len(player.scenes)}", True, TEXT_DIM
    )
    surface.blit(counter, (w - 32 - counter.get_width(), h - 40))

    # кнопка «пропустить»
    btn = Button(cutscene_button_rect(w, h), "ПРОПУСТИТЬ →", tooltip="Сразу перейти к делу")
    btn.update(pygame.mouse.get_pos(), pygame.mouse.get_pressed()[0])
    btn.draw(surface, get_font(10, bold=True))


def cutscene_button_rect(width: int, height: int) -> pygame.Rect:
    """Прямоугольник кнопки «пропустить» — общий для отрисовки и кликов."""
    return pygame.Rect(width - 190, 16, 158, 30)
