"""Центральное состояние игры."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class DetectiveProfile:
    name: str = "Алекс Рейн"
    avatar_id: str = "detective_01"
    background: str = "private_eye"  # private_eye | ex_cop | reporter
    gender: str = "male"
    created_at: float = field(default_factory=time.time)

    @property
    def background_label(self) -> str:
        return {
            "private_eye": "Частный сыщик",
            "ex_cop": "Бывший коп",
            "reporter": "Репортёр",
        }.get(self.background, self.background)

    @property
    def background_desc(self) -> str:
        return {
            "private_eye": "Умеет находить общий язык с улицей. Люди доверяют ему тайны.",
            "ex_cop": "Связи в полиции и знание процедур. Доступ к закрытым деталям.",
            "reporter": "Острый глаз на детали и умение разговорить любого.",
        }.get(self.background, "")

AVATARS = [
    {"id": "detective_01", "name": "Рейн", "gender": "male", "color": (60, 90, 130), "desc": "Классика нуара — плащ и шляпа"},
    {"id": "detective_02", "name": "Мара", "gender": "female", "color": (130, 60, 80), "desc": "Острая интуиция и ледяное спокойствие"},
    {"id": "detective_03", "name": "Коул", "gender": "male", "color": (80, 110, 80), "desc": "Бывший военный, видит то, что другие пропускают"},
    {"id": "detective_04", "name": "Вивиан", "gender": "female", "color": (120, 90, 50), "desc": "Светская львица с тёмным прошлым"},
    {"id": "detective_05", "name": "Шедоу", "gender": "male", "color": (70, 70, 90), "desc": "Тень города — его никто не замечает"},
    {"id": "detective_06", "name": "Лора", "gender": "female", "color": (90, 120, 110), "desc": "Криминалист, помешанная на деталях"},
]

# Пулы имён для генерации — связаны с аватаром (имя под фото → полное имя)
AVATAR_NAME_POOLS = {
    "detective_01": ["Алекс Рейн", "Киран Рейн", "Джек Рейн", "Мик Рейн", "Рой Рейн", "Шон Рейн"],
    "detective_02": ["Мара Кросс", "Ада Мара", "Ева Мара", "Лина Мара", "Кири Мара", "Рина Мара"],
    "detective_03": ["Марк Коул", "Джон Коул", "Том Коул", "Глен Коул", "Брук Коул", "Рэй Коул"],
    "detective_04": ["Вивиан Блэк", "Вивиан Сноу", "Вивиан Крэй", "Вивиан Шелл", "Эва Вивиан", "Лу Вивиан"],
    "detective_05": ["Тень Грэй", "Ник Шедоу", "Кей Шедоу", "Джо Шедоу", "Лео Шедоу", "Вэнс Шедоу"],
    "detective_06": ["Лора Финч", "Лора Квинн", "Лора Хилл", "Мия Лора", "Сара Лора", "Клэр Лора"],
}

def get_random_name_for_avatar(avatar_id: str, rng=None) -> str:
    """Возвращает случайное полное имя для аватара."""
    import random
    pool = AVATAR_NAME_POOLS.get(avatar_id) or AVATAR_NAME_POOLS["detective_01"]
    r = rng or random
    return r.choice(pool)

BACKGROUNDS = [
    {"id": "private_eye", "label": "Частный сыщик", "icon": "🕵️"},
    {"id": "ex_cop", "label": "Бывший коп", "icon": "🚓"},
    {"id": "reporter", "label": "Репортёр", "icon": "📰"},
]

@dataclass
class GameState:
    # detective
    detective: DetectiveProfile = field(default_factory=DetectiveProfile)
    # case
    current_case_id: Optional[str] = None
    visited_locations: set = field(default_factory=set)
    collected_clues: set = field(default_factory=set)
    interrogated: set = field(default_factory=set)
    case_time_minutes: int = 0  # игровое время
    game_day: int = 1
    case_state: str = "not_started"  # not_started | in_progress | accusation | finished
    accusation_result: Optional[str] = None
    accusation_correct: Optional[bool] = None
    notes: list = field(default_factory=list)
    # допросы: какие реплики выбраны, доверие персонажей, выданные бонусы
    dialogue_choices: dict = field(default_factory=dict)  # "char_id:тема" -> индекс реплики
    trust: dict = field(default_factory=dict)  # char_id -> доверие
    trust_bonus_taken: set = field(default_factory=set)
    # открытые концовки: id дела -> ["дело:подозреваемый:вариант", ...]
    unlocked_endings: dict = field(default_factory=dict)
    # успешно закрытые дела — для галочки «ПРОЙДЕНО» и кнопки «СЛЕДУЮЩЕЕ ДЕЛО»
    completed_cases: set = field(default_factory=set)
    # доска версий: верные и ошибочные связки «улика|подозреваемый»
    board_links: set = field(default_factory=set)
    board_wrong: set = field(default_factory=set)
    # реконструкция: порядок карточек времени и результат
    timeline_order: list = field(default_factory=list)
    timeline_solved: bool = False
    timeline_attempts: int = 0
    # обыск: найденные точки и раскрытые скрытые улики
    search_found: set = field(default_factory=set)
    hidden_found: set = field(default_factory=set)
    # слежка: дела, где удалось довести объект до места
    tail_done: set = field(default_factory=set)
    # разоблачённая ложь: "персонаж:тема" -> ответ персонажа
    exposed_lies: dict = field(default_factory=dict)
    # ресурсы детектива
    reputation: int = 0
    money: int = 500
    # ордер на обыск/задержание: куплен или выбит блефом
    warrant: bool = False
    # редкое QTE «драка в баре» уже случилось в этом деле
    fight_done: bool = False
    # ── «взрослые» правила (дела с advanced: true) ──────────────────
    # какие темы допроса уже открывались: "персонаж:тема"
    asked_topics: set = field(default_factory=set)
    # улики, подтверждённые лабораторией, и подброшенные (фальшивки)
    confirmed_clues: set = field(default_factory=set)
    fake_clues: set = field(default_factory=set)
    # выводы, полученные сопоставлением показаний
    deductions: set = field(default_factory=set)
    # кодовые замки, которые уже открыты
    riddles_solved: set = field(default_factory=set)
    # подсказку про «КОД» показываем один раз за сохранение
    riddle_tip_shown: bool = False
    # выбор игрока на суде: мотив и способ
    trial_motive: Optional[str] = None
    trial_method: Optional[str] = None
    # срок дела истёк
    deadline_missed: bool = False
    # сколько анонимных звонков уже было и когда звонили в последний раз
    calls_seen: int = 0
    last_call_minute: int = 0
    # проваленные слежки и день, до которого объект осторожен
    tail_failed: set = field(default_factory=set)
    tail_blocked_until_day: int = 0
    # персонажи, замолчавшие до определённого дня: char_id -> день
    silenced: dict = field(default_factory=dict)
    # meta
    total_playtime: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["visited_locations"] = list(self.visited_locations)
        d["collected_clues"] = list(self.collected_clues)
        d["interrogated"] = list(self.interrogated)
        d["trust_bonus_taken"] = list(self.trust_bonus_taken)
        d["unlocked_endings"] = {k: list(v) for k, v in self.unlocked_endings.items()}
        d["completed_cases"] = list(self.completed_cases)
        d["board_links"] = list(self.board_links)
        d["board_wrong"] = list(self.board_wrong)
        d["timeline_order"] = list(self.timeline_order)
        d["search_found"] = list(self.search_found)
        d["hidden_found"] = list(self.hidden_found)
        d["tail_done"] = list(self.tail_done)
        d["exposed_lies"] = dict(self.exposed_lies)
        d["asked_topics"] = list(self.asked_topics)
        d["confirmed_clues"] = list(self.confirmed_clues)
        d["fake_clues"] = list(self.fake_clues)
        d["deductions"] = list(self.deductions)
        d["riddles_solved"] = list(self.riddles_solved)
        d["riddle_tip_shown"] = bool(self.riddle_tip_shown)
        d["tail_failed"] = list(self.tail_failed)
        d["silenced"] = dict(self.silenced)
        # dataclass nested
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        det = DetectiveProfile(**data.get("detective", {}))
        obj = cls(
            detective=det,
            current_case_id=data.get("current_case_id"),
            visited_locations=set(data.get("visited_locations", [])),
            collected_clues=set(data.get("collected_clues", [])),
            interrogated=set(data.get("interrogated", [])),
            case_time_minutes=data.get("case_time_minutes", 0),
            game_day=data.get("game_day", 1),
            case_state=data.get("case_state", "not_started"),
            accusation_result=data.get("accusation_result"),
            accusation_correct=data.get("accusation_correct"),
            notes=data.get("notes", []),
            dialogue_choices=dict(data.get("dialogue_choices", {}) or {}),
            trust={k: int(v) for k, v in (data.get("trust", {}) or {}).items()},
            trust_bonus_taken=set(data.get("trust_bonus_taken", []) or []),
            unlocked_endings={
                str(k): list(v) for k, v in (data.get("unlocked_endings", {}) or {}).items()
            },
            completed_cases=set(data.get("completed_cases", []) or []),
            board_links=set(data.get("board_links", []) or []),
            board_wrong=set(data.get("board_wrong", []) or []),
            timeline_order=list(data.get("timeline_order", []) or []),
            timeline_solved=bool(data.get("timeline_solved", False)),
            timeline_attempts=int(data.get("timeline_attempts", 0) or 0),
            search_found=set(data.get("search_found", []) or []),
            hidden_found=set(data.get("hidden_found", []) or []),
            tail_done=set(data.get("tail_done", []) or []),
            exposed_lies=dict(data.get("exposed_lies", {}) or {}),
            reputation=int(data.get("reputation", 0) or 0),
            money=int(data.get("money", 500) or 0),
            warrant=bool(data.get("warrant", False)),
            fight_done=bool(data.get("fight_done", False)),
            asked_topics=set(data.get("asked_topics", []) or []),
            confirmed_clues=set(data.get("confirmed_clues", []) or []),
            fake_clues=set(data.get("fake_clues", []) or []),
            deductions=set(data.get("deductions", []) or []),
            riddles_solved=set(data.get("riddles_solved", []) or []),
            riddle_tip_shown=bool(data.get("riddle_tip_shown", False)),
            trial_motive=data.get("trial_motive"),
            trial_method=data.get("trial_method"),
            deadline_missed=bool(data.get("deadline_missed", False)),
            calls_seen=int(data.get("calls_seen", 0) or 0),
            last_call_minute=int(data.get("last_call_minute", 0) or 0),
            tail_failed=set(data.get("tail_failed", []) or []),
            tail_blocked_until_day=int(data.get("tail_blocked_until_day", 0) or 0),
            silenced={str(k): int(v) for k, v in (data.get("silenced", {}) or {}).items()},
            total_playtime=data.get("total_playtime", 0.0),
        )
        return obj
