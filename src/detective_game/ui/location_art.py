"""Иллюстрации локаций: какой картинкой показывать место действия.

Игра берёт файл по типу локации (``hub``, ``bar``, ``police``…). Если для типа
отдельной иллюстрации нет — используется похожая с цветной вуалью, чтобы
экраны не были однотонными. У дела можно переопределить картинку полем
``"image"`` у локации.
"""

from typing import Dict, Optional, Tuple

FALLBACK_TINT = (18, 22, 34, 90)

# тип локации -> (файл в assets/images, цветная вуаль)
LOCATION_ART: Dict[str, Tuple[str, Optional[Tuple[int, int, int, int]]]] = {
    "hub": ("locations/hub.jpg", None),
    "mansion": ("locations/mansion.jpg", None),
    "public": ("locations/public.jpg", None),
    "crime": ("locations/crime.jpg", None),
    "police": ("locations/police.jpg", None),
    "bar": ("locations/bar.jpg", None),
    "apartment": ("locations/apartment.jpg", None),
    # отдельной иллюстрации пока нет — та же сцена с другой «погодой»
    "office": ("locations/police.jpg", (16, 34, 62, 80)),
    "bank": ("locations/mansion.jpg", (70, 52, 12, 85)),
    "vault": ("locations/mansion.jpg", (28, 36, 58, 120)),
    # фотолаборатория — красный свет, «порт» и «склад» видны как район на карте
    "shop": ("locations/apartment.jpg", (120, 8, 8, 150)),
    "warehouse": ("maps/downtown.jpg", (10, 16, 24, 150)),
    "port": ("maps/northport.jpg", (8, 20, 45, 130)),
    "station": ("locations/public.jpg", (60, 45, 15, 80)),
    "radio": ("locations/radio.jpg", None),
    "transmitter": ("locations/transmitter.jpg", None),
    "archive": ("locations/archive_exterior.jpg", None),
}


def location_art(loc: dict) -> Tuple[Optional[str], Optional[Tuple[int, int, int, int]]]:
    """(картинка, вуаль) для локации дела."""
    if not loc:
        return None, None
    override = loc.get("image")
    if override:
        return str(override), None
    return LOCATION_ART.get(str(loc.get("type", "")), (None, FALLBACK_TINT))


# как тип локации называется по-русски на экране
LOCATION_TYPE_LABELS = {
    "hub": "ОФИС",
    "mansion": "ОСОБНЯК",
    "public": "ОБЩЕСТВЕННОЕ МЕСТО",
    "crime": "МЕСТО ПРЕСТУПЛЕНИЯ",
    "police": "ПОЛИЦИЯ",
    "bar": "БАР",
    "apartment": "КВАРТИРА",
    "bank": "БАНК",
    "vault": "ХРАНИЛИЩЕ",
    "shop": "МАСТЕРСКАЯ",
    "warehouse": "СКЛАД",
    "port": "ПОРТ",
    "station": "ВОКЗАЛ",
    "radio": "РАДИОСТАНЦИЯ",
    "transmitter": "ПЕРЕДАТЧИК",
    "archive": "АРХИВ",
    "office": "КОМНАТА ОХРАНЫ",
}


def type_label(loc: dict) -> str:
    """Русское название типа локации (или сам тип, если он незнакомый)."""
    kind = str((loc or {}).get("type", ""))
    return LOCATION_TYPE_LABELS.get(kind, kind.upper())
