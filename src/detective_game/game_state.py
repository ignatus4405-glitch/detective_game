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
    # meta
    total_playtime: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["visited_locations"] = list(self.visited_locations)
        d["collected_clues"] = list(self.collected_clues)
        d["interrogated"] = list(self.interrogated)
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
            total_playtime=data.get("total_playtime", 0.0),
        )
        return obj
