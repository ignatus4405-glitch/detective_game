"""«Школа детектива» — интерактивный туториал: раскладка и содержание.

Экран обучает играть на живых мини-примерах: карта с кликабельными пинами,
карточки улик с картинками, блокнот с вкладками, допрос с вариантами ответа,
обвинение и «видео-обзор» — анимированная демонстрация полного цикла.

Геометрия считается здесь, а не в `main.py`: одна правда для отрисовки и для
обработки кликов (иначе кнопки «уезжают» и не нажимаются — эта ошибка уже
была в кастомизации).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import pygame

from .layout import ensure_unique_hits, layout_contains, rects_overlap

Point = Tuple[int, int]


# ---------------------------------------------------------------------------
# Содержание туториала
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chapter:
    key: str
    title: str
    subtitle: str
    badge: str


CHAPTERS: Tuple[Chapter, ...] = (
    Chapter("intro", "Как играть", "Цель и экраны игры", "1"),
    Chapter("map", "Карта города", "Куда идти и что открывает локации", "2"),
    Chapter("clues", "Улики", "Нашёл — прочитал — связал", "3"),
    Chapter("notebook", "Блокнот", "Улики · Подозреваемые · Карта", "4"),
    Chapter("dialogue", "Допрос", "Вопросы и выбор ответа", "5"),
    Chapter("accuse", "Обвинение", "Когда и кого обвинять", "6"),
    Chapter("demo", "Видео-обзор", "Полный цикл расследования", "▶"),
)

CHAPTER_INDEX = {chapter.key: i for i, chapter in enumerate(CHAPTERS)}


def _empty_rect() -> pygame.Rect:
    """Пустой прямоугольник (pygame.Rect требует аргументы)."""
    return pygame.Rect(0, 0, 0, 0)


@dataclass(frozen=True)
class DemoLocation:
    name: str
    x: float  # 0..1 внутри карты
    y: float
    district: str
    note: str


# Тренировочные точки на карте: те же типы, что и в настоящем деле.
TRAINING_LOCATIONS: Tuple[DemoLocation, ...] = (
    DemoLocation("Ваш офис", 0.50, 0.55, "Центр", "Дело начинается здесь. Тут же лежат записи."),
    DemoLocation("Дом мэра", 0.23, 0.22, "Холмы", "Клиент и первая улика: отпечаток лапы."),
    DemoLocation("Парк", 0.73, 0.63, "Центр", "Ошейник в кустах — и записка с угрозой."),
    DemoLocation("Порт", 0.87, 0.28, "Порт", "Свидетели, склады и тёмные сделки."),
    DemoLocation("Полиция", 0.18, 0.70, "Запад", "Архив, экспертиза и старые дела."),
    DemoLocation("Бар «Фонарь»", 0.60, 0.85, "Север", "За стаканом языки развязываются."),
)


@dataclass(frozen=True)
class DemoClue:
    title: str
    place: str
    text: str
    importance: str  # "high" | "normal"
    leads: str
    image: str  # имя файла в assets/images/tutorial/ или ""


TRAINING_CLUES: Tuple[DemoClue, ...] = (
    DemoClue(
        "Отпечаток лапы",
        "Дом мэра",
        "Грязный след у миски. Лапа слишком большая для Барсика — значит, кто-то "
        "подставил чужой след, чтобы увести вас в парк.",
        "high",
        "Парк",
        "clue_paw.jpg",
    ),
    DemoClue(
        "Ошейник с запиской",
        "Парк",
        "В кустах — ошейник кота и записка: «Верну за выкуп». Бумага из бара "
        "«Фонарь» — такие блокноты дают только за стойкой.",
        "high",
        "Бар «Фонарь»",
        "clue_collar.jpg",
    ),
    DemoClue(
        "Показания соседа",
        "Бар «Фонарь»",
        "Сосед Смит видел, как мэр ночью нёс коробку к парку. Важная деталь: "
        "он путается в датах.",
        "normal",
        "",
        "",
    ),
)

NOTEBOOK_TABS: Tuple[Tuple[str, str], ...] = (
    ("Улики", "Все найденные улики: значок ★ — важная, серая — второстепенная."),
    ("Подозреваемые", "Досье на каждого: мотив, алиби и связи с уликами."),
    ("Карта", "Схема города и заметки: куда вы уже ходили."),
)

DIALOGUE_LINES: Tuple[Tuple[str, str], ...] = (
    ("Когда пропал кот?", "«Вчера вечером! Кто-то оставил окно открытым.»"),
    ("Кто ещё был в доме?", "«Только сосед… он странно себя ведёт.»"),
    ("Показать ошейник", "«Это же Барсик!.. Откуда у вас его ошейник?»"),
)

SUSPECTS: Tuple[Tuple[str, str], ...] = (
    ("Сосед Смит", "Мотив: ссора из-за забора. Алиби шаткое."),
    ("Сам мэр", "Мотив: страховка. Слишком спокойно говорит о пропаже."),
    ("Неизвестный", "Высокий, в грязных ботинках. Видели у парка."),
)

VERDICT_TEXT = (
    "Вы обвинили верного подозреваемого — дело закрыто. "
    "Если ошибиться, будет экран провала: игру можно начать заново из меню."
)


@dataclass(frozen=True)
class DemoScene:
    title: str
    subtitle: str
    duration: float
    chapter: str = ""
    short: str = ""


# «Видео» — анимированный проход по игре: без внешних кодеков, работает
# в любом разрешении и в PyInstaller-сборке.
DEMO_SCENES: Tuple[DemoScene, ...] = (
    DemoScene("Карта города", "Пины — это локации. Жёлтое кольцо — где вы сейчас.", 6.0, "map", "Карта"),
    DemoScene("Переход", "Клик по пину открывает локацию — тратится время.", 5.0, "map", "Переход"),
    DemoScene("Улика", "Нашли улику — она сразу попадает в журнал справа.", 6.0, "clues", "Улика"),
    DemoScene("Блокнот", "Вкладки: Улики · Подозреваемые · Карта.", 6.0, "notebook", "Блокнот"),
    DemoScene("Обвинение", "Собрали 3+ улики — выбирайте подозреваемого.", 6.0, "accuse", "Обвинение"),
)

DEMO_TOTAL = sum(scene.duration for scene in DEMO_SCENES)


def demo_scene_at(time_sec: float) -> Tuple[int, float]:
    """Индекс сцены и время внутри неё для позиции на таймлайне."""
    t = max(0.0, float(time_sec)) % DEMO_TOTAL
    for index, scene in enumerate(DEMO_SCENES):
        if t < scene.duration:
            return index, t / scene.duration
        t -= scene.duration
    return len(DEMO_SCENES) - 1, 1.0


def demo_scene_starts() -> List[float]:
    """Абсолютное время начала каждой сцены (для клика по таймлайну)."""
    starts: List[float] = []
    acc = 0.0
    for scene in DEMO_SCENES:
        starts.append(acc)
        acc += scene.duration
    return starts


# ---------------------------------------------------------------------------
# Раскладка
# ---------------------------------------------------------------------------


@dataclass
class TutorialLayout:
    """Прямоугольники «Школы детектива» в логических координатах."""

    width: int
    height: int
    chapter: str
    header: pygame.Rect
    nav: pygame.Rect
    content: pygame.Rect
    footer: pygame.Rect
    btn_back: pygame.Rect
    btn_prev: pygame.Rect
    btn_next: pygame.Rect
    progress: pygame.Rect
    nav_items: List[pygame.Rect] = field(default_factory=list)
    # интро
    hero: pygame.Rect = field(default_factory=_empty_rect)
    feature_cards: List[pygame.Rect] = field(default_factory=list)
    # карта
    map_rect: pygame.Rect = field(default_factory=_empty_rect)
    pins: List[pygame.Rect] = field(default_factory=list)
    map_info: pygame.Rect = field(default_factory=_empty_rect)
    map_hint: pygame.Rect = field(default_factory=_empty_rect)
    # улики
    clue_cards: List[pygame.Rect] = field(default_factory=list)
    clue_detail: pygame.Rect = field(default_factory=_empty_rect)
    # блокнот
    tabs: List[pygame.Rect] = field(default_factory=list)
    notebook_body: pygame.Rect = field(default_factory=_empty_rect)
    # допрос
    portrait: pygame.Rect = field(default_factory=_empty_rect)
    question: pygame.Rect = field(default_factory=_empty_rect)
    answers: List[pygame.Rect] = field(default_factory=list)
    # обвинение
    suspects: List[pygame.Rect] = field(default_factory=list)
    verdict_btn: pygame.Rect = field(default_factory=_empty_rect)
    verdict_text: pygame.Rect = field(default_factory=_empty_rect)
    # видео
    player: pygame.Rect = field(default_factory=_empty_rect)
    btn_play: pygame.Rect = field(default_factory=_empty_rect)
    btn_restart: pygame.Rect = field(default_factory=_empty_rect)
    timeline: pygame.Rect = field(default_factory=_empty_rect)
    scene_chips: List[pygame.Rect] = field(default_factory=list)
    subtitle: pygame.Rect = field(default_factory=_empty_rect)

    # -- выбор элементов по точке (логические координаты) --

    def nav_at(self, pos) -> Optional[int]:
        return _hit(self.nav_items, pos)

    def feature_at(self, pos) -> Optional[int]:
        return _hit(self.feature_cards, pos)

    def pin_at(self, pos) -> Optional[int]:
        return _hit(self.pins, pos)

    def clue_at(self, pos) -> Optional[int]:
        return _hit(self.clue_cards, pos)

    def tab_at(self, pos) -> Optional[int]:
        return _hit(self.tabs, pos)

    def answer_at(self, pos) -> Optional[int]:
        return _hit(self.answers, pos)

    def suspect_at(self, pos) -> Optional[int]:
        return _hit(self.suspects, pos)

    def chip_at(self, pos) -> Optional[int]:
        return _hit(self.scene_chips, pos)

    def timeline_time(self, pos) -> Optional[float]:
        """Время на таймлайне по клику (None, если клик мимо)."""
        if not self.timeline.collidepoint(pos):
            return None
        rel = (pos[0] - self.timeline.x) / max(1, self.timeline.w)
        return max(0.0, min(1.0, rel)) * DEMO_TOTAL

    def interactive_rects(self) -> List[pygame.Rect]:
        """Все кликабельные зоны текущей главы — для проверок и подсветки."""
        rects: List[pygame.Rect] = [self.btn_back, self.btn_prev, self.btn_next]
        rects += list(self.nav_items)
        rects += list(self.feature_cards)
        rects += list(self.pins)
        rects += list(self.clue_cards)
        rects += list(self.tabs)
        rects += list(self.answers)
        rects += list(self.suspects)
        if self.chapter == "accuse":
            rects.append(self.verdict_btn)
        if self.chapter == "demo":
            rects += [self.btn_play, self.btn_restart, self.timeline]
            rects += list(self.scene_chips)
        return [r for r in rects if r.w > 0 and r.h > 0]


def _hit(rects: Sequence[pygame.Rect], pos) -> Optional[int]:
    if not pos:
        return None
    for index, rect in enumerate(rects):
        if rect.collidepoint(pos):
            return index
    return None


def _inset(rect: pygame.Rect, dx: int, dy: Optional[int] = None) -> pygame.Rect:
    dy = dx if dy is None else dy
    return pygame.Rect(rect.x + dx, rect.y + dy, max(1, rect.w - 2 * dx), max(1, rect.h - 2 * dy))


def tutorial_layout(
    width: int = 1280,
    height: int = 720,
    chapter: str = "intro",
    *,
    pins: int = len(TRAINING_LOCATIONS),
    clues: int = len(TRAINING_CLUES),
    tabs: int = len(NOTEBOOK_TABS),
    answers: int = len(DIALOGUE_LINES),
    suspects: int = len(SUSPECTS),
    scenes: int = len(DEMO_SCENES),
) -> TutorialLayout:
    """Считает раскладку главы. Ничего не пересекается и влезает в панели."""
    width = max(800, int(width))
    height = max(600, int(height))
    margin = max(14, int(width * 0.019))
    gap = max(8, int(width * 0.010))
    header_h = max(46, int(height * 0.078))
    footer_h = max(48, int(height * 0.083))
    nav_w = int(width * 0.235)

    header = pygame.Rect(margin, max(10, int(height * 0.022)), width - 2 * margin, header_h)
    footer = pygame.Rect(
        margin, height - margin - footer_h, width - 2 * margin, footer_h
    )
    nav = pygame.Rect(margin, header.bottom + gap, nav_w, footer.top - gap - header.bottom - gap)
    content = pygame.Rect(
        nav.right + gap, nav.y, width - margin - (nav.right + gap), nav.h
    )

    # Кнопки в футере: слева «В меню», справа «Далее», в центре прогресс.
    back_w = int(width * 0.13)
    btn_back = pygame.Rect(footer.x + 8, footer.y + 8, back_w, footer.h - 16)
    next_w = int(width * 0.12)
    btn_next = pygame.Rect(footer.right - next_w - 8, footer.y + 8, next_w, footer.h - 16)
    prev_w = int(width * 0.11)
    btn_prev = pygame.Rect(btn_next.x - prev_w - 10, footer.y + 8, prev_w, footer.h - 16)
    progress = pygame.Rect(btn_back.right + 24, footer.y + 14, max(1, btn_prev.x - btn_back.right - 48), footer.h - 28)

    # Навигация по главам
    pad = max(8, int(width * 0.009))
    nav_items: List[pygame.Rect] = []
    if chapter:
        inner = nav.inflate(-2 * pad, -2 * pad)
        step = (inner.h + 6) // max(1, len(CHAPTERS))
        item_h = max(24, step - 6)
        for i in range(len(CHAPTERS)):
            nav_items.append(pygame.Rect(inner.x, inner.y + i * step, inner.w, item_h))

    zone = _inset(content, max(10, int(content.w * 0.02)), max(10, int(content.h * 0.02)))
    layout = TutorialLayout(
        width=width,
        height=height,
        chapter=chapter,
        header=header,
        nav=nav,
        content=content,
        footer=footer,
        btn_back=btn_back,
        btn_prev=btn_prev,
        btn_next=btn_next,
        progress=progress,
        nav_items=nav_items,
    )

    if chapter == "intro":
        hero_h = int(zone.h * 0.36)
        layout.hero = pygame.Rect(zone.x, zone.y, zone.w, hero_h)
        grid_top = layout.hero.bottom + gap
        grid_h = zone.bottom - grid_top
        card_w = (zone.w - gap) // 2
        card_h = (grid_h - gap) // 2
        for row in range(2):
            for col in range(2):
                layout.feature_cards.append(
                    pygame.Rect(
                        zone.x + col * (card_w + gap),
                        grid_top + row * (card_h + gap),
                        card_w,
                        card_h,
                    )
                )

    elif chapter == "map":
        info_w = min(int(zone.w * 0.30), 320)
        hint_h = 34
        layout.map_rect = pygame.Rect(zone.x, zone.y, zone.w - info_w - gap, zone.h - hint_h - gap)
        layout.map_info = pygame.Rect(layout.map_rect.right + gap, zone.y, info_w, layout.map_rect.h)
        layout.map_hint = pygame.Rect(zone.x, layout.map_rect.bottom + gap, zone.w, hint_h)
        for i in range(pins):
            loc = TRAINING_LOCATIONS[i % len(TRAINING_LOCATIONS)]
            cx = layout.map_rect.x + int(loc.x * layout.map_rect.w)
            cy = layout.map_rect.y + int(loc.y * layout.map_rect.h)
            radius = 26
            cx = max(layout.map_rect.x + radius, min(layout.map_rect.right - radius, cx))
            cy = max(layout.map_rect.y + radius, min(layout.map_rect.bottom - radius, cy))
            layout.pins.append(pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2))

    elif chapter == "clues":
        card_h = int(zone.h * 0.46)
        card_w = (zone.w - gap * (clues - 1)) // max(1, clues)
        for i in range(clues):
            layout.clue_cards.append(
                pygame.Rect(zone.x + i * (card_w + gap), zone.y, card_w, card_h)
            )
        layout.clue_detail = pygame.Rect(
            zone.x, zone.y + card_h + gap, zone.w, zone.bottom - (zone.y + card_h + gap)
        )

    elif chapter == "notebook":
        tab_h = max(34, int(zone.h * 0.10))
        tab_w = (zone.w - gap * (tabs - 1)) // max(1, tabs)
        for i in range(tabs):
            layout.tabs.append(pygame.Rect(zone.x + i * (tab_w + gap), zone.y, tab_w, tab_h))
        layout.notebook_body = pygame.Rect(
            zone.x, zone.y + tab_h + gap, zone.w, zone.bottom - (zone.y + tab_h + gap)
        )

    elif chapter == "dialogue":
        portrait_w = min(int(zone.w * 0.26), 260)
        portrait_h = int(zone.h * 0.46)
        layout.portrait = pygame.Rect(zone.x, zone.y, portrait_w, portrait_h)
        layout.question = pygame.Rect(
            layout.portrait.right + gap, zone.y, zone.w - portrait_w - gap, portrait_h
        )
        answer_h = max(40, int((zone.h - portrait_h - gap - gap * (answers - 1)) / max(1, answers)))
        top = layout.portrait.bottom + gap
        for i in range(answers):
            layout.answers.append(pygame.Rect(zone.x, top + i * (answer_h + gap), zone.w, answer_h))

    elif chapter == "accuse":
        text_h = int(zone.h * 0.15)
        layout.verdict_text = pygame.Rect(zone.x, zone.y, zone.w, text_h)
        card_top = layout.verdict_text.bottom + gap
        card_h = int(zone.h * 0.52)
        card_w = (zone.w - gap * (suspects - 1)) // max(1, suspects)
        for i in range(suspects):
            layout.suspects.append(
                pygame.Rect(zone.x + i * (card_w + gap), card_top, card_w, card_h)
            )
        verdict_w = min(int(zone.w * 0.36), 340)
        verdict_h = max(38, min(56, zone.bottom - (card_top + card_h) - 2 * gap))
        layout.verdict_btn = pygame.Rect(
            zone.x + (zone.w - verdict_w) // 2,
            card_top + card_h + gap,
            verdict_w,
            verdict_h,
        )

    elif chapter == "demo":
        controls_h = max(44, int(zone.h * 0.11))
        chips_h = max(26, int(zone.h * 0.07))
        layout.player = pygame.Rect(
            zone.x, zone.y, zone.w, zone.h - controls_h - chips_h - 2 * gap
        )
        controls_y = layout.player.bottom + gap
        layout.btn_play = pygame.Rect(zone.x, controls_y, int(zone.w * 0.16), controls_h)
        layout.btn_restart = pygame.Rect(
            layout.btn_play.right + gap, controls_y, int(zone.w * 0.14), controls_h
        )
        layout.timeline = pygame.Rect(
            layout.btn_restart.right + gap * 2,
            controls_y + controls_h // 2 - 6,
            zone.right - (layout.btn_restart.right + gap * 2),
            12,
        )
        chips_y = controls_y + controls_h + gap
        chip_w = (zone.w - gap * (scenes - 1)) // max(1, scenes)
        for i in range(scenes):
            layout.scene_chips.append(
                pygame.Rect(zone.x + i * (chip_w + gap), chips_y, chip_w, chips_h)
            )
        layout.subtitle = pygame.Rect(
            layout.player.x + 16,
            layout.player.bottom - int(layout.player.h * 0.22),
            layout.player.w - 32,
            int(layout.player.h * 0.19),
        )

    return layout


# ---------------------------------------------------------------------------
# Самопроверки — используются тестами и в CI
# ---------------------------------------------------------------------------


def tutorial_layout_problems(layout: TutorialLayout) -> List[str]:
    """Список нарушений раскладки (пустой = всё в порядке)."""
    problems: List[str] = []
    panels = [layout.header, layout.nav, layout.content, layout.footer]

    for group_name, rects in (
        ("nav", layout.nav_items),
        ("feature", layout.feature_cards),
        ("pins", layout.pins),
        ("clues", layout.clue_cards),
        ("tabs", layout.tabs),
        ("answers", layout.answers),
        ("suspects", layout.suspects),
        ("chips", layout.scene_chips),
    ):
        if not rects:
            continue
        if not ensure_unique_hits(rects):
            problems.append(f"{group_name}: пересекающиеся кликабельные зоны")
        for rect in rects:
            if not any(layout_contains(panel, rect) for panel in panels):
                problems.append(f"{group_name}: {tuple(rect)} вне панелей")

    content = layout.content
    for name in ("hero", "map_rect", "map_info", "map_hint", "clue_detail",
                 "notebook_body", "portrait", "question", "verdict_text",
                 "verdict_btn", "player", "timeline"):
        rect = getattr(layout, name)
        if rect.w > 0 and not layout_contains(content, rect):
            problems.append(f"{name} вне контента")

    if layout.map_rect.w and layout.map_info.w and rects_overlap(layout.map_rect, layout.map_info):
        problems.append("карта перекрывает панель описания")
    if layout.portrait.w and layout.question.w and rects_overlap(layout.portrait, layout.question):
        problems.append("портрет перекрывает вопрос")
    if layout.clue_cards and layout.feature_cards:
        problems.append("карточки разных глав посчитаны одновременно")
    return problems


# ---------------------------------------------------------------------------
# Состояние прохождения
# ---------------------------------------------------------------------------


@dataclass
class TutorialState:
    """Что открыто и выбрано в «Школе детектива»."""

    chapter: int = 0
    visited: set = field(default_factory=lambda: {0})
    pin: Optional[int] = 0
    clue: Optional[int] = 0
    tab: int = 0
    answer: Optional[int] = None
    suspect: Optional[int] = None
    verdict_shown: bool = False
    demo_time: float = 0.0
    demo_playing: bool = True

    @property
    def key(self) -> str:
        index = max(0, min(len(CHAPTERS) - 1, int(self.chapter)))
        return CHAPTERS[index].key

    def goto(self, index: int) -> None:
        self.chapter = max(0, min(len(CHAPTERS) - 1, int(index)))
        self.visited.add(self.chapter)

    def next(self) -> None:
        self.goto(self.chapter + 1)

    def prev(self) -> None:
        self.goto(self.chapter - 1)

    def update(self, dt_ms: float) -> None:
        if self.key == "demo" and self.demo_playing:
            self.demo_time = (self.demo_time + dt_ms / 1000.0) % DEMO_TOTAL

    def scene(self) -> Tuple[int, float]:
        return demo_scene_at(self.demo_time)

    def seek(self, seconds: float) -> None:
        self.demo_time = max(0.0, min(DEMO_TOTAL - 0.01, float(seconds)))

    def jump_to_scene(self, index: int) -> None:
        starts = demo_scene_starts()
        if 0 <= index < len(starts):
            self.seek(starts[index])
            self.demo_playing = True
