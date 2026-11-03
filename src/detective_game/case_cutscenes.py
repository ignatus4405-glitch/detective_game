"""Тексты и раскадровка катсцен «что произошло до дела».

Каждая катсцена — 3 кадра: завязка, преступление, утро после. Иллюстрации
лежат в ``assets/images/cutscenes/<id дела>/``.

Поля сцены:

``image``     — файл относительно ``assets/images``;
``label``     — метка кадра («НОЧЬ, 21:40»);
``caption``   — подпись-субтитр (печатается посимвольно);
``duration``  — минимальная длительность, секунд (чтение может растянуть);
``pan``       — движение камеры: ``in``/``out``/``left``/``right``.
"""

from typing import Dict, List, Optional

from .cutscene import Cutscene, Scene

CUTSCENES: Dict[str, Dict] = {
    "tutorial": {
        "title": "Учебное дело: Пропавший кот",
        "subtitle": "Блэквил, октябрь 1987. Три кадра до вашего звонка.",
        "scenes": [
            Scene(
                image="cutscenes/tutorial/01_window.jpg",
                label="Вечер, 21:12",
                caption=(
                    "Кабинет мэра. Дождь стучит по стеклу, а Барсик сидит на подоконнике — "
                    "как всегда, когда хозяин уходит. Защёлку кто-то уже отвернул."
                ),
                duration=5.0,
                pan="in",
            ),
            Scene(
                image="cutscenes/tutorial/02_garden.jpg",
                label="Ночь, 21:40",
                caption=(
                    "Створка окна хлопает. Через сад к калитке идёт человек в плаще. "
                    "Что-то большое и тёплое он прижимает к груди — кот спит."
                ),
                duration=5.5,
                pan="left",
            ),
            Scene(
                image="cutscenes/tutorial/03_morning.jpg",
                label="Утро, 07:55",
                caption=(
                    "Утро. Окно открыто, миска пуста, на паркете — чужие следы. "
                    "Через десять минут в вашем офисе звонит телефон."
                ),
                duration=5.0,
                pan="out",
            ),
        ],
    },
    "missing_chess": {
        "title": "Загадочное похищение",
        "subtitle": "Блэквил, ночь с пятницы на субботу.",
        "scenes": [
            Scene(
                image="cutscenes/missing_chess/01_park.jpg",
                label="Парк Роузвуд, 23:10",
                caption=(
                    "Фотограф Виктор Ланский успел снять что-то важное — и остался лежать "
                    "на мокрой дорожке. Камера в луже, но плёнка цела."
                ),
                duration=5.0,
                pan="in",
            ),
            Scene(
                image="cutscenes/missing_chess/02_hall.jpg",
                label="ДК «Юность», 16:40",
                caption=(
                    "За два часа до этого Артём Морозов, девяти лет, вышел из ДК через "
                    "служебную дверь с мужчиной в сером плаще."
                ),
                duration=5.5,
                pan="in",
            ),
            Scene(
                image="cutscenes/missing_chess/03_storeroom.jpg",
                label="Склад у порта, 01:20",
                caption=(
                    "Кладовка без окон у порта. Фонарь, чужая куртка и шахматы: мальчик "
                    "играет сам с собой. Заказчик уже берёт билет."
                ),
                duration=5.5,
                pan="right",
            ),
        ],
    },
    "bank_heist": {
        "title": "Тень ячейки №314",
        "subtitle": "Блэквил, ночь на понедельник, 02:00.",
        "scenes": [
            Scene(
                image="cutscenes/bank_heist/01_vault.jpg",
                label="Хранилище, 02:05",
                caption=(
                    "Сигнализация молчит уже десять минут. Дверь хранилища приоткрыта, "
                    "ячейки 310–320 вскрыты, по полу — бумаги и запах сигар."
                ),
                duration=5.0,
                pan="in",
            ),
            Scene(
                image="cutscenes/bank_heist/02_box314.jpg",
                label="Ячейка №314, 02:12",
                caption=(
                    "Деньги Моргана Хейса исчезли, а карта сокровищ — нет: её забрала уборщица "
                    "Мария, которая думала, что спасает брата от долга."
                ),
                duration=5.5,
                pan="left",
            ),
            Scene(
                image="cutscenes/bank_heist/03_harbor.jpg",
                label="Порт, 05:40",
                caption=(
                    "К рассвету часть денег уже в ящике на третьем причале. Кто-то очень хочет, "
                    "чтобы вы искали не там."
                ),
                duration=5.0,
                pan="out",
            ),
        ],
    },
}


def cutscene_for(case_id: str) -> Optional[Cutscene]:
    """Катсцена дела или ``None``, если для него её нет."""
    data = CUTSCENES.get(str(case_id or ""))
    if not data:
        return None
    scenes: List[Scene] = list(data.get("scenes") or [])
    if not scenes:
        return None
    return Cutscene(
        case_id=str(case_id),
        title=str(data.get("title", "")),
        subtitle=str(data.get("subtitle", "")),
        scenes=scenes,
    )


def has_cutscene(case_id: str) -> bool:
    return cutscene_for(case_id) is not None

CUTSCENES["last_signal"] = {
    "title": "Последний сигнал",
    "subtitle": "Радиостанция «Волна», ночная смена.",
    "scenes": [
        Scene(image="cases/last_signal.jpg", label="Улица у станции, 22:05",
              caption="Дождь глушит антенны. В студии горит лампа «ЭФИР», но ведущая уже не отвечает на звонки.", duration=5.0, pan="in"),
        Scene(image="locations/radio.jpg", label="Студия, 22:17",
              caption="В эфир уходит признание, которого никто не произносил. На плёнке — щелчок реле и свежая склейка.", duration=5.5, pan="left"),
        Scene(image="locations/transmitter.jpg", label="Передатчик, 22:25",
              caption="Инженер закрывает журнал ремонта. До студии двенадцать минут пешком — и ни одного лишнего следа.", duration=5.5, pan="out"),
    ],
}
CUTSCENES["silent_archive"] = {
    "title": "Архив молчания",
    "subtitle": "Городской архив, ночь до суда.",
    "scenes": [
        Scene(image="locations/archive_exterior.jpg", label="Архив, 23:40",
              caption="Пожар начинается в корзине с бумагой. Стеллажи не задеты — кто-то знал, что именно должно сгореть.", duration=5.0, pan="in"),
        Scene(image="cases/silent_archive.jpg", label="Читальный зал, 20:26",
              caption="Реестр раскрыт на пустом месте. Страница 47 вырезана по корешку, а контрольный номер остался на соседнем листе.", duration=5.5, pan="right"),
        Scene(image="locations/archive_vault.jpg", label="Хранилище, 20:41",
              caption="Ключ возвращён на место. Часы отстают на девять минут — и эта поправка скоро станет важнее признания.", duration=5.5, pan="out"),
    ],
}
