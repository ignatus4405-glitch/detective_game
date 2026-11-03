"""Экспертные слои старых дел: алиби, доказательная цепочка и новые улики.

Обычный режим не меняется. Дополнительные документы доступны и в классике,
но только «Эксперт» требует собрать из них полную версию и опровергнуть алиби.
"""
from __future__ import annotations

EXPERT_LAYERS = {
    "missing_chess": {
        "cover": "cutscenes/missing_chess/01_park.jpg",
        "extra_clues": [
            {
                "id": "clue_finch_network", "title": "Записная книжка «Шахматиста»",
                "desc": "В сейфе участка лежит копия книжки Финча: список одарённых детей, псевдоним «Шахматист» и помета «исполнителю — после доставки». Почерк совпадает с запиской Ланского.",
                "location": "police", "importance": "high", "leads_to": [],
            },
            {
                "id": "clue_finch_locker", "title": "Квитанция Финча на камеру хранения",
                "desc": "Ячейку вокзала открывал не Роман, а Финч. В описи — расписание поездов, дубликат ключа склада и серые перчатки. Квитанция выдана за час до похищения.",
                "location": "station", "importance": "high", "hidden": True, "leads_to": [],
            },
        ],
        "suspect_evidence": {"finch": ["clue_finch_network", "clue_finch_locker"]},
        "alibi": {
            "title": "Три места в 16:05",
            "question": "Где были Роман, Финч и Ланский в 16:05 — когда поезд ушёл в Нортпорт?",
            "people": [{"id": "roma", "name": "Роман"}, {"id": "finch", "name": "Финч"}, {"id": "lansky", "name": "Ланский"}],
            "places": [{"id": "station", "name": "Вокзал"}, {"id": "bar", "name": "Бар"}, {"id": "lab", "name": "Фотолаборатория"}],
            "facts": [
                {"id": "ticket", "text": "Кассир помнит: мужчина с детским билетом на 16:05 был на вокзале. Билет куплен на имя Р. Ковалёв.", "source": {"type": "clue", "id": "clue_ticket"}, "constraints": [{"type": "is", "person": "roma", "place": "station"}]},
                {"id": "bar", "text": "Бармен записал заказ Финча в 16:00, а следующий — в 16:20. Финч не отходил от стойки; до вокзала идти 12 минут.", "source": {"type": "clue", "id": "clue_bar_testimony"}, "constraints": [{"type": "is", "person": "finch", "place": "bar"}]},
                {"id": "lab", "text": "На контрольном листе проявки — подпись Ланского и время 16:05. Реактив требовал его присутствия ещё десять минут.", "source": {"type": "clue", "id": "clue_photos"}, "constraints": [{"type": "is", "person": "lansky", "place": "lab"}]},
                {"id": "clock", "text": "Часы бара спешат на семь минут. Заказ, отмеченный 16:07, сделан в 16:00. Поправка не меняет алиби Финча.", "source": {"type": "clue", "id": "clue_camera"}, "constraints": [{"type": "not", "person": "finch", "place": "station"}]},
            ],
            "solution": {"roma": "station", "finch": "bar", "lansky": "lab"},
            "explanation": "Роман был на вокзале, Финч — у стойки, Ланский — в лаборатории. Финч подготовил маршрут заранее, но сам в 16:05 оставался на виду. Это не снимает с него организацию похищения.",
        },
        "proof": {
            "slots": {
                "motive": ["clue_finch_network"], "access": ["clue_finch_locker"],
                "presence": ["clue_tape"], "action": ["clue_warehouse_footprints"],
                "cover": ["clue_ticket"],
            },
            "board": {"finch": ["clue_finch_network", "clue_finch_locker", "clue_tape", "clue_warehouse_footprints", "clue_ticket"]},
            "alternatives": [
                {"id": "roma", "text": "Роман действовал один ради денег"},
                {"id": "ordered", "text": "Роман выполнял заказ Финча; билет и ткань должны были указать на исполнителя", "correct": True},
                {"id": "father", "text": "Отец забрал сына после развода"},
            ],
        },
    },
    "bank_heist": {
        "cover": "cutscenes/bank_heist/01_vault.jpg",
        "extra_clues": [
            {
                "id": "clue_kane_payments", "title": "Теневая ведомость Кейна",
                "desc": "В копии банковского журнала — платежи Дереку за «ночную проверку» и заявление о потере ключа Марии, напечатанное до самой потери. Подпись управляющего стоит на обеих бумагах.",
                "location": "police", "importance": "high", "leads_to": [],
            },
        ],
        "suspect_evidence": {"kane_sus": ["clue_kane_payments"]},
        "alibi": {
            "title": "Десять минут тишины",
            "question": "Где были Кейн, Дерек и Мария в 02:18 — в середине отключения сигнализации?",
            "people": [{"id": "kane", "name": "Кейн"}, {"id": "derek", "name": "Дерек"}, {"id": "maria", "name": "Мария"}],
            "places": [{"id": "bar", "name": "Бар"}, {"id": "vault", "name": "Хранилище"}, {"id": "mansion", "name": "Особняк Хейса"}],
            "facts": [
                {"id": "call", "text": "Бармен слышал голос Кейна в трубке с 02:10 до 02:25. Часы бара спешат на 7 минут: начало разговора отмечено 02:17.", "source": {"type": "clue", "id": "clue_bar_call"}, "constraints": [{"type": "is", "person": "kane", "place": "bar"}]},
                {"id": "guard", "text": "Дерек отметился у пульта хранилища в 02:18. Код M-314 введён изнутри; до бара от пульта идти 15 минут.", "source": {"type": "clue", "id": "clue_log"}, "constraints": [{"type": "is", "person": "derek", "place": "vault"}]},
                {"id": "diary", "text": "Хейс записал: в 02:15 Мария вернула ему карту в особняке и просила защиты для брата. До банка от особняка 20 минут.", "source": {"type": "clue", "id": "clue_morgan_diary_copy"}, "constraints": [{"type": "is", "person": "maria", "place": "mansion"}]},
                {"id": "coffee", "text": "Тёплая чашка в 09:00 не доказывает, что Кейн был в банке ночью. Это отдельный утренний след, не алиби на 02:18.", "source": {"type": "clue", "id": "clue_coffee"}, "constraints": [{"type": "not", "person": "kane", "place": "vault"}]},
            ],
            "solution": {"kane": "bar", "derek": "vault", "maria": "mansion"},
            "explanation": "Кейн руководил из бара, Дерек открыл хранилище, а Мария к 02:18 уже была у Хейса. Алиби Кейна настоящее — но оно не мешает ему быть организатором.",
        },
        "proof": {
            "slots": {
                "motive": ["clue_manager_debt"], "access": ["clue_log"],
                "presence": ["clue_coffee"], "action": ["clue_bar_call"],
                "cover": ["clue_kane_payments"],
            },
            "board": {"kane_sus": ["clue_manager_debt", "clue_log", "clue_coffee", "clue_bar_call", "clue_kane_payments"]},
            "alternatives": [
                {"id": "maria", "text": "Мария вынесла деньги ради брата"},
                {"id": "inside", "text": "Кейн организовал «ограбление» изнутри, Дерек открыл ячейки, а ключ Марии подбросили", "correct": True},
                {"id": "outside", "text": "Это взломщик с улицы, воспользовавшийся потертым ключом"},
            ],
        },
    },
}


def apply(case: dict) -> dict:
    layer = EXPERT_LAYERS.get(str(case.get("id", "")))
    if not layer:
        return case
    existing = {c["id"] for c in case.get("clues", [])}
    for clue in layer.get("extra_clues", []):
        if clue["id"] not in existing:
            case.setdefault("clues", []).append(dict(clue))
    for suspect in case.get("suspects", []):
        extra = layer.get("suspect_evidence", {}).get(suspect["id"], [])
        suspect.setdefault("evidence", []).extend(c for c in extra if c not in suspect["evidence"])
    case["alibi"] = layer["alibi"]
    case["proof"] = layer["proof"]
    case["cover"] = layer["cover"]
    return case
