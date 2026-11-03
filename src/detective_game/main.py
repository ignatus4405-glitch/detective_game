"""Главный цикл игры — все экраны."""

import sys
import time

import pygame

from . import board as board_logic
from . import (
    dialogue,
    expertise,
    get_version_source,
    pressure,
    puzzles,
    surveillance,
    timeline,
    trial,
    worldtime,
)
from . import endings as ending_logic
from . import riddle as riddle_logic
from . import search as search_logic
from . import testimony as testimony_logic
from .audio import audio
from .case_cutscenes import cutscene_for
from .config import *
from .cutscene import CutscenePlayer, cutscene_button_rect
from .cutscene import draw_cutscene as draw_cutscene_screen
from .data import case_map, get_clue, get_location, list_cases, load_case
from .game_state import (
    AVATARS,
    BACKGROUNDS,
    START_MONEY,
    START_REPUTATION,
    DetectiveProfile,
    GameState,
)
from .save_system import (
    delete_save,
    get_save_dir,
    has_save,
    load_detective,
    load_game,
    load_settings,
    save_detective,
    save_game,
    save_settings,
)
from .ui import (
    board_view,
    qte_view,
    search_view,
    surveillance_view,
    testimony_view,
    timeline_view,
)
from .ui.artwork import blit_rounded as blit_rounded_image
from .ui.artwork import clear_cache as clear_artwork_cache
from .ui.artwork import cover_image
from .ui.layout import (
    case_select_layout,
    customization_layout,
    map_layout,
    settings_layout,
)
from .ui.location_art import location_art, type_label
from .ui.puzzle_view import draw_puzzle_screen, handle_puzzle_click, handle_puzzle_key
from .ui.riddle_view import draw_riddle, handle_riddle_click, handle_riddle_key
from .ui.tutorial import TutorialState
from .ui.tutorial_view import (
    draw_tutorial_screen,
    handle_tutorial_click,
    handle_tutorial_key,
)
from .ui.widgets import (
    Button,
    TextInput,
    draw_avatar,
    draw_die_icon,
    draw_icon,
    draw_map_pin,
    draw_panel,
    draw_text_wrapped,
    get_font,
    render_text,
    reset_font_caches,
    safe_text,
)
from .updater import (
    UpdateChecker,
    consume_update_result,
    get_app_log_path,
    install_requires_elevation,
    log_update,
    open_app_log,
)

try:
    from .settings_manager import (
        SUPPORTED_RESOLUTIONS,
        WINDOW_MODES,
        apply_display_settings,
        get_available_monitors,
        get_available_resolutions,
        get_current_settings,
    )
except Exception:
    SUPPORTED_RESOLUTIONS = [(1280, 720), (1920, 1080)]
    WINDOW_MODES = [("windowed", "Оконный", "🗔")]

    def get_available_monitors():
        return [{"id": 0, "name": "Монитор 1 — 1920×1080", "size": (1920, 1080)}]

    def get_available_resolutions():
        return SUPPORTED_RESOLUTIONS

    def apply_display_settings(s, screen=None):
        return screen

    def get_current_settings():
        return {}


pygame.init()


# Создаём базовые ассеты если нет
def ensure_placeholder_images():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # можно позже генерировать


class Game:
    # Базовое логическое разрешение — дизайн 1280×720, масштабируется letterbox на любое окно
    LOGICAL_W = 1280
    LOGICAL_H = 720

    def _get_letterbox(self):
        """Возвращает (scale, ox, oy, w, h) для letterbox-масштабирования."""
        try:
            # Важно: брать физический размер окна дисплея, а не логического холста
            surf = pygame.display.get_surface()
            if surf is not None:
                Wp, Hp = surf.get_size()
            else:
                Wp, Hp = self.screen.get_size()
        except Exception:
            Wp, Hp = WINDOW_WIDTH, WINDOW_HEIGHT
        Lw, Lh = self.LOGICAL_W, self.LOGICAL_H
        if Wp <= 0 or Hp <= 0:
            return 1.0, 0, 0, Lw, Lh
        scale = min(Wp / Lw, Hp / Lh)
        w = int(Lw * scale)
        h = int(Lh * scale)
        ox = (Wp - w) // 2
        oy = (Hp - h) // 2
        return scale, ox, oy, w, h

    def _to_logical(self, pos):
        """Переводит физические координаты мыши в логические."""
        if pos is None:
            return pos
        try:
            scale, ox, oy, w, h = self._get_letterbox()
            x, y = pos
            if scale == 0:
                return pos
            lx = (x - ox) / scale
            ly = (y - oy) / scale
            return (int(lx), int(ly))
        except Exception:
            return pos

    def _init_display(self):
        # Применяем настройки экрана при старте
        try:
            from .settings_manager import apply_display_settings

            self.screen = apply_display_settings(self.settings, getattr(self, "screen", None))
            # Обновляем размер окна в настройках если не совпадает с десктопом
        except Exception as e:
            print(f"[Display] init failed: {e}")
            self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(TITLE)

    def __init__(self):
        # После pygame.quit()/init() в том же процессе старые Font-объекты
        # недействительны — иначе отрисовка может упасть в segfault.
        reset_font_caches()
        clear_artwork_cache()
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.settings = load_settings()
        # Дефолты для новых настроек экрана
        if "resolution" not in self.settings:
            self.settings["resolution"] = [WINDOW_WIDTH, WINDOW_HEIGHT]
        if "window_mode" not in self.settings:
            # мигрируем со старого fullscreen bool
            if self.settings.get("fullscreen"):
                self.settings["window_mode"] = "fullscreen"
            else:
                self.settings["window_mode"] = "windowed"
        if "monitor" not in self.settings:
            self.settings["monitor"] = 0
        if "auto_check_updates" not in self.settings:
            self.settings["auto_check_updates"] = True
        # Инициализируем экран по настройкам
        self._init_display()
        self.state = load_game() or GameState()
        # Если есть сохранённый детектив, загрузим
        saved_det = load_detective()
        if saved_det:
            self.state.detective = saved_det
        self.cases = list_cases()
        self.current_case = None
        if self.state.current_case_id:
            self.current_case = load_case(self.state.current_case_id)
        # UI state
        self.screen_name = "menu"  # menu | ... | cutscene | puzzle
        self.cutscene: CutscenePlayer | None = None
        # головоломки
        self.puzzle = None
        self.puzzle_clue = None
        self.puzzle_rects = {}
        self._puzzle_started_at = 0.0
        # кодовые замки (загадки)
        self.riddle = None
        self.riddle_clue = None
        self.riddle_input = ""
        self.riddle_hint = ""
        self.riddle_message = ""
        self.riddle_attempts = 0
        self.riddle_rects = {}
        self.location_clue_buttons = {}
        self.ending_rects = {}
        # звук и музыка
        self.audio = audio
        self.audio.init()
        self.audio.set_volumes(
            music=self.settings.get("music_volume", 0.5),
            sfx=self.settings.get("sfx_volume", 0.7),
            voice=self.settings.get("voice_enabled", True),
        )
        self._music_screen = None
        self.prev_screen = "menu"
        self.selected_avatar = 0
        self.selected_bg = self.state.detective.background
        self.name_input = TextInput(
            (55, 115, 1170, 42),
            placeholder="Введите имя детектива... Например: Алекс Рейн",
            text=self.state.detective.name,
        )
        # прямоугольник поля берём из общего макета — он же используется кликами
        self.name_input.rect = self._customization_layout().name_input
        # на аватар индекс
        for i, av in enumerate(AVATARS):
            if av["id"] == self.state.detective.avatar_id:
                self.selected_avatar = i
                break
        # case selection
        self.case_index = 0
        # map
        self.map_selected_loc = None
        self.map_hover = None
        # location
        self.location_id = "office"
        self.dialogue_char = None
        self.dialogue_idx = 0
        # таймер реплики и отметка «уже штрафовали за повтор в этом разговоре»
        self.dialogue_timer = 0.0
        self.dialogue_penalized = False
        # выбор мотива и способа на экране обвинения
        self.trial_rects = {}
        # кнопки «экспертиза» в блокноте
        self.expertise_rects = {}
        # сопоставление показаний
        self.testimony_selected = []
        self.testimony_message = ""
        self.testimony_return = "notebook"
        self.testimony_scroll = 0
        self.testimony_rects = {}
        # notebook tab
        self.notebook_tab = "clues"  # clues | suspects | board | notes
        # доска версий
        self.board_clue = None
        self.board_message = ""
        self.board_rects = {}
        self.dialogue_lie_rects = {}
        # реконструкция хронологии
        self.timeline_selected = None
        self.timeline_message = ""
        self.timeline_return = "map"
        self.timeline_rects = {}
        # обыск локации и слежка
        self.search = None
        self.search_visual = None
        self.search_rects = {}
        self.search_start_rect = None
        self.search_message = ""
        self.tail = None
        self.tail_spec = None
        self.tail_rects = {}
        self.tail_reward = None
        self.route_rects = {}
        self.route_message = ""
        self.qte = None
        self.qte_rects = {}
        self._dev_param = None
        # accusation
        self.accusation_selected = None
        # интерактивная «Школа детектива»
        self.tutorial = TutorialState()
        self.tutorial_seen = bool(self.settings.get("tutorial_seen", False))
        # updater — проверяем только если включена авто-проверка в настройках
        self.update_checker = UpdateChecker()
        if self.settings.get("auto_check_updates", True):
            self.update_checker.start()
        self.update_notified = False
        self.update_dismissed = False
        # результат неудачной установки из прошлого запуска (показываем баннером)
        self.failed_update = None
        # защёлка клика: кнопки баннеров создаются заново каждый кадр и без неё
        # срабатывали на каждое удержание мыши (8 окон проводника за один клик)
        self._click_latch = False
        # модальное подтверждение опасных действий (сброс прогресса, новая игра)
        self.confirm_dialog = None
        self.confirm_back = "menu"
        self.confirm_pending = None
        self.confirm_rects = {}
        # последний нарисованный кадр — фон для диалога подтверждения
        self._frame_snapshot = None
        # --- Новые виджеты настроек ---
        self._init_settings_widgets()
        # notifications queue
        self.notifications = []  # list of (text, time)
        # итог прошлой установки обновления (обновилось / не обновилось)
        self._report_update_result(consume_update_result())
        if not self.tutorial_seen:
            self.add_notification(
                "Впервые здесь? Меню → «ТУТОРИАЛ»: карта, улики и видео-обзор"
            )
        # time
        self.start_time = time.time()

    def _report_update_result(self, result):
        """Показывает, чем закончилась установка обновления из прошлого запуска.

        Неудачу держим на экране баннером, а не 4-секундным уведомлением:
        раньше игрок видел «старую версию и предложение обновиться снова»
        и не понимал, что именно сломалось.
        """
        if not result:
            return
        if result.get("status") == "installed":
            self.add_notification(f"Обновление установлено — теперь v{result['current']}")
            log_update(f"обновление установлено: v{result['current']}")
            return
        target = result.get("target", "?")
        current = result.get("current", "?")
        log_update(f"обновление до v{target} не установилось (у вас v{current})")
        self.failed_update = result
        self.update_dismissed = False

    def _init_settings_widgets(self):
        # Дропдауны и слайдеры для настроек
        try:
            from .settings_manager import get_available_monitors, get_available_resolutions

            res_list = get_available_resolutions()
            mons = get_available_monitors()
        except Exception:
            res_list = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]
            mons = [{"id": 0, "name": "Монитор 1", "size": (1920, 1080)}]
        # Текущие значения
        cur_res = tuple(self.settings.get("resolution", [WINDOW_WIDTH, WINDOW_HEIGHT]))
        if isinstance(cur_res[0], list):
            cur_res = tuple(cur_res)
        cur_mon = int(self.settings.get("monitor", 0))
        res_opts = [
            (f"{w}x{h}", f"{w} × {h} {'★' if w == 1920 and h == 1080 else ''} ".strip())
            for w, h in res_list
        ]
        # Улучшенные подписи разрешений
        res_labels = []
        for w, h in res_list:
            label = f"{w} × {h}"
            if (w, h) == (1280, 720):
                label += "  — HD (базовое)"
            elif (w, h) == (1920, 1080):
                label += "  — Full HD ★"
            elif (w, h) == (2560, 1440):
                label += "  — QHD"
            res_labels.append(label)
        res_opts = [(f"{w}x{h}", lbl) for (w, h), lbl in zip(res_list, res_labels, strict=False)]
        mon_opts = [(str(m["id"]), m["name"]) for m in mons]
        # Инициализируем дропдауны (позиции обновятся в draw_settings)
        from .ui.widgets import Dropdown, Slider, Toggle

        self.resolution_dropdown = Dropdown(
            pygame.Rect(0, 0, 280, 36),
            res_opts,
            selected=f"{cur_res[0]}x{cur_res[1]}",
            label="",
        )
        self.monitor_dropdown = Dropdown(
            pygame.Rect(0, 0, 280, 36), mon_opts, selected=str(cur_mon), label=""
        )
        # Для одного монитора — дизейблим выбор? оставляем но показываем 1
        self.window_mode = self.settings.get("window_mode", "windowed")
        self.sfx_slider = Slider(
            pygame.Rect(0, 0, 280, 12), 0, 1, self.settings.get("sfx_volume", 0.7), label="Эффекты"
        )
        self.music_slider = Slider(
            pygame.Rect(0, 0, 280, 12), 0, 1, self.settings.get("music_volume", 0.5), label="Музыка"
        )
        self.auto_update_toggle = Toggle(
            pygame.Rect(0, 0, 44, 24),
            checked=self.settings.get("auto_check_updates", True),
            label="Авто-проверка обновлений",
        )
        self.voice_toggle = Toggle(
            pygame.Rect(0, 0, 44, 24),
            checked=self.settings.get("voice_enabled", True),
            label="Озвучка",
        )
        # Превью применения
        self._pending_resolution = f"{cur_res[0]}x{cur_res[1]}"
        self._pending_monitor = str(cur_mon)
        self._pending_window_mode = self.window_mode
        self._settings_changed = False
        self._confirm_reset_timer = 0  # для превью с revert
        self._update_download_progress = 0

    def _apply_pending_settings(self):
        # Применяем выбранные настройки
        try:
            w, h = map(int, self._pending_resolution.split("x"))
            self.settings["resolution"] = [w, h]
            self.settings["monitor"] = int(self._pending_monitor)
            self.settings["window_mode"] = self._pending_window_mode
            self.settings["sfx_volume"] = self.sfx_slider.value
            self.settings["music_volume"] = self.music_slider.value
            self.settings["voice_enabled"] = self.voice_toggle.checked
            self.audio.set_volumes(
                music=self.settings["music_volume"],
                sfx=self.settings["sfx_volume"],
                voice=self.settings["voice_enabled"],
            )
            self.settings["auto_check_updates"] = self.auto_update_toggle.checked
            from .settings_manager import apply_display_settings

            new_screen = apply_display_settings(self.settings, self.screen)
            if new_screen:
                self.screen = new_screen
            from .save_system import save_settings

            save_settings(self.settings)
            self.add_notification(
                f"Настройки применены: {w}×{h} · {self._pending_window_mode} · Монитор {int(self._pending_monitor) + 1}"
            )
            self._settings_changed = False
            # Переинициализируем виджеты для новых позиций
            self._init_settings_widgets()
        except Exception as e:
            self.add_notification(f"Ошибка применения: {e}")

    def add_notification(self, text):
        self.notifications.append((text, time.time() + 4))
        print(f"[NOTIFY] {text}")

    def _retry_update_check(self):
        """Повторная проверка обновлений (в т.ч. после сетевой ошибки)."""
        self.update_checker = UpdateChecker()
        self.update_checker.start()
        self.update_dismissed = False
        self.add_notification("Проверяем обновления…")

    def _update_diagnostics(self):
        """Строки диагностики апдейтера для настроек."""
        from . import __version__ as game_version

        checker = self.update_checker
        source = get_version_source()
        source_name = source.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        lines = [f"Версия: v{game_version}  ·  источник: {source_name}"]
        if checker.checking:
            lines.append("Проверка: идёт…")
        elif checker.done and checker.error:
            lines.append("Проверка: ОШИБКА — подробности в журнале")
        elif checker.done and checker.result:
            lines.append(f"Проверка: доступна v{checker.result['latest']} (канал {checker.source})")
        elif checker.done:
            lines.append("Проверка: обновлений нет")
        else:
            lines.append("Проверка: не выполнялась")
        if getattr(checker, "download_error", None):
            lines.append(f"Загрузка: {checker.download_error}")
        lines.append(f"Журнал: {get_app_log_path()}")
        return lines

    def _click_once(self) -> bool:
        """True только в первый кадр нажатия — одно нажатие = одно действие.

        Кнопки на баннерах обновления создаются внутри ``draw()`` заново каждый
        кадр, поэтому у них ``self.pressed`` всегда ``False``: ``clicked``
        остаётся ``True``, пока кнопка мыши удерживается. Без защёлки действие
        повторялось каждый кадр — именно так одно нажатие «Установить»
        открывало 8 окон проводника.
        """
        if not pygame.mouse.get_pressed()[0]:
            self._click_latch = False
            return False
        if self._click_latch:
            return False
        self._click_latch = True
        return True

    # ── подтверждение опасных действий и сброс прогресса ─────────────────

    def ask_confirm(self, title: str, text: str, action, yes: str = "ДА", danger: bool = True):
        """Спросить подтверждение перед необратимым действием.

        Открывает отдельный экран ``confirm`` поверх снимка текущего кадра:
        под ним ничего не нажимается, а «да» срабатывает только после того,
        как игрок отпустит кнопку мыши (иначе отпускание «дожимало» бы
        кнопку под диалогом).
        """
        self.confirm_dialog = {
            "title": str(title),
            "text": str(text),
            "yes": str(yes),
            "no": "ОТМЕНА",
            "action": action,
            "danger": bool(danger),
        }
        self.confirm_pending = None
        self.confirm_back = self.screen_name if self.screen_name != "confirm" else "menu"
        self.screen_name = "confirm"
        self._click_latch = True

    def _confirm_resolve(self, accepted: bool) -> None:
        """Закрыть диалог: при согласии — выполнить действие."""
        dialog = self.confirm_dialog or {}
        self.confirm_dialog = None
        self.confirm_pending = None
        self.screen_name = str(self.confirm_back or "menu")
        self._click_latch = True
        self.audio.play_sfx("page" if accepted else "click")
        action = dialog.get("action")
        if accepted and callable(action):
            action()

    def _reset_progress(self) -> None:
        """Стереть прогресс целиком: сохранение, дело, ресурсы и экраны.

        Детектив (имя, портрет, прошлое) остаётся — его выбирают заново на
        экране кастомизации, а вот улики, репутация, деньги, открытые
        концовки и незакрытое дело исчезают.
        """
        detective = self.state.detective
        delete_save()
        self.state = GameState(detective=detective)
        save_game(self.state)
        # то, что живёт вне GameState и могло остаться на экране
        self.current_case = None
        self.location_id = "office"
        self.search = None
        self.search_message = ""
        self.tail = None
        self.tail_spec = None
        self.cutscene = None
        self.puzzle = None
        self.riddle = None
        self.riddle_clue = None
        self.qte = None
        self.dialogue_char = None
        self.dialogue_idx = 0
        self.dialogue_timer = 0.0
        self.accusation_selected = None
        self.testimony_selected = []
        self.testimony_message = ""
        self.timeline_selected = None
        self.timeline_message = ""
        self.board_clue = None
        self.board_message = ""
        self.screen_name = "menu"

    def _start_new_game(self) -> None:
        """«НОВАЯ ИГРА»: спросить и стереть прогресс (если он вообще есть)."""
        has_progress = bool(
            self.state.current_case_id
            or self.state.completed_cases
            or self.state.collected_clues
        )
        if not has_progress:
            self.screen_name = "customization"
            return
        self.ask_confirm(
            "НАЧАТЬ НОВУЮ ИГРУ?",
            "Текущее дело, собранные улики, репутация, деньги и открытые "
            "концовки будут стёрты. Детектива можно будет выбрать заново.",
            self._new_game_confirmed,
            yes="НАЧАТЬ ЗАНОВО",
        )

    def _new_game_confirmed(self) -> None:
        self._reset_progress()
        self.screen_name = "customization"

    def _wipe_confirmed(self) -> None:
        self._reset_progress()
        self.add_notification("Прогресс сброшен — начинаем заново")

    def draw_confirm(self) -> None:
        """Экран подтверждения: диммированный прошлый кадр и два ответа."""
        W, H = self.LOGICAL_W, self.LOGICAL_H
        if self._frame_snapshot is not None:
            self.screen.blit(self._frame_snapshot, (0, 0))
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((4, 6, 10, 205))
        self.screen.blit(veil, (0, 0))
        dialog = self.confirm_dialog or {}
        danger = bool(dialog.get("danger", True))
        accent = COLOR_RED if danger else COLOR_ACCENT
        panel = pygame.Rect(0, 0, 660, 260)
        panel.center = (W // 2, H // 2)
        shadow = pygame.Surface((panel.w + 12, panel.h + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120), (0, 0, panel.w + 12, panel.h + 12), border_radius=12)
        self.screen.blit(shadow, (panel.x - 6, panel.y - 6))
        draw_panel(self.screen, panel)
        pygame.draw.rect(self.screen, accent, panel, width=2, border_radius=8)
        title = get_font(18, bold=True).render(str(dialog.get("title", "ПОДТВЕРДИТЕ")), True, accent)
        self.screen.blit(title, (panel.x + 26, panel.y + 20))
        draw_text_wrapped(
            self.screen,
            str(dialog.get("text", "")),
            get_font(13),
            COLOR_TEXT,
            pygame.Rect(panel.x + 26, panel.y + 56, panel.w - 52, 110),
        )
        yes = Button(
            pygame.Rect(panel.x + 26, panel.bottom - 62, 290, 42),
            str(dialog.get("yes", "ДА")),
            style="danger" if danger else "primary",
        )
        no = Button(
            pygame.Rect(panel.right - 26 - 290, panel.bottom - 62, 290, 42),
            str(dialog.get("no", "ОТМЕНА")),
        )
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        # ответ применяем на отпускании кнопки мыши — так «да» не «дожимает»
        # кнопку того экрана, который откроется под диалогом
        if self.confirm_pending is not None and not pressed:
            answer = self.confirm_pending
            self._confirm_resolve(answer)
            return
        for btn, answer in ((yes, True), (no, False)):
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(12, bold=True))
            if btn.clicked and self.confirm_pending is None:
                self.confirm_pending = answer
        hint = get_font(9).render("Esc — отмена", True, COLOR_TEXT_DARK)
        self.screen.blit(hint, (panel.x + 26, panel.bottom - 18))
        self.confirm_rects = {"yes": yes.rect, "no": no.rect}

    def _install_update(self):
        """Ставит скачанное обновление и выходит из игры.

        Архив (обычный путь с 0.1.28) распаковывается и копируется скрытым
        помощником после выхода игры; exe-установщик остаётся для защищённых
        папок вроде Program Files, где нужен UAC. Раньше архив просто открывался
        в проводнике с надписью «распакуйте вручную» — из-за этого обновление
        «не копировалось само».
        """
        path = getattr(self.update_checker, "downloaded_path", None)
        if not path or not getattr(path, "exists", lambda: False)():
            self.add_notification("Файл обновления не найден — скачайте его заново")
            return False
        try:
            if install_requires_elevation():
                self.add_notification(
                    "Установка: подтвердите запрос администратора Windows (UAC)"
                )
            else:
                self.add_notification("Установка… игра перезапустится автоматически")
            if self.update_checker.install():
                pygame.quit()
                sys.exit(0)
            # Причину показываем текстом: иначе игрок видит только «не сработало»
            reason = getattr(self.update_checker, "download_error", None)
            self.add_notification(
                reason
                or "Не удалось запустить обновление — подробности в журнале обновлений"
            )
        except Exception as e:
            self.add_notification(f"Ошибка установки: {e}")
        return False

    def draw_notifications(self):
        now = time.time()
        self.notifications = [n for n in self.notifications if n[1] > now]
        W = self.screen.get_width()
        # на экране обучения шапка занимает верх — уведомления уводим ниже
        y = 96 if self.screen_name == "tutorial" else 20
        font = get_font(14)
        for text, _ in self.notifications:
            surf = font.render(text, True, COLOR_TEXT)
            bg_w = surf.get_width() + 20
            bg_h = surf.get_height() + 10
            bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
            pygame.draw.rect(bg, (30, 30, 40, 230), (0, 0, bg_w, bg_h), border_radius=6)
            pygame.draw.rect(bg, COLOR_ACCENT, (0, 0, bg_w, bg_h), width=1, border_radius=6)
            self.screen.blit(bg, (W - bg_w - 20, y))
            self.screen.blit(surf, (W - bg_w - 20 + 10, y + 5))
            y += bg_h + 8

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            # переводим мышь в логические координаты
            phys_mouse = pygame.mouse.get_pos()
            mouse_pos = self._to_logical(phys_mouse)
            mouse_pressed = pygame.mouse.get_pressed()[0]
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                # транслируем координаты клика в логическую систему
                if hasattr(event, 'pos'):
                    try:
                        event.pos = self._to_logical(event.pos)
                    except Exception:
                        pass
                self.handle_event(event)
            self.update(mouse_pos, mouse_pressed)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit(0)

    def draw_tutorial(self):
        """Интерактивная «Школа детектива» (карта, улики, блокнот, видео-обзор)."""
        draw_tutorial_screen(self, self.tutorial)
        # запоминаем, что игрок открыл обучение — подсказку больше не показываем
        if not self.tutorial_seen:
            self.tutorial_seen = True
            self.settings["tutorial_seen"] = True
            try:
                save_settings(self.settings)
            except Exception:
                pass

    def handle_event(self, event):
        # диалог подтверждения перехватывает всё: под ним ничего не нажимается
        if self.screen_name == "confirm":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._confirm_resolve(False)
            return
        # F1 — «Школа детектива» из любого экрана (кроме самого обучения)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.screen_name != "tutorial":
            if self.screen_name in ("menu", "settings", "customization", "case_select"):
                self.screen_name = "tutorial"
                self.tutorial.goto(0)
                return
        if self.screen_name == "tutorial":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_tutorial_click(self, self.tutorial, event.pos)
                return
            if handle_tutorial_key(self, self.tutorial, event):
                return
            return
        if self.screen_name == "ending" and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self._ending_success() and self.next_case():
                    self._ending_action("next")
                else:
                    self._ending_action("menu")
                return
            if event.key == pygame.K_ESCAPE:
                self._ending_action("menu")
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.audio.play_sfx("click")
        if self.screen_name == "puzzle":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_puzzle_click(self, event.pos)
            elif event.type == pygame.KEYDOWN:
                handle_puzzle_key(self, event)
            return
        if self.screen_name == "riddle":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_riddle_click(self, self._to_logical(event.pos))
            elif handle_riddle_key(self, event):
                pass
            return
        if self.screen_name == "cutscene":
            self.handle_cutscene_event(event)
            return
        if self.screen_name == "timeline":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                timeline_view.handle_timeline_click(self, event.pos)
            elif timeline_view.handle_timeline_key(self, event):
                pass
            return
        if self.screen_name == "testimony":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                testimony_view.handle_testimony_click(self, event.pos)
            elif testimony_view.handle_testimony_key(self, event):
                pass
            return
        if self.screen_name == "tail":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                surveillance_view.handle_click(self, event.pos)
            elif surveillance_view.handle_key(self, event):
                pass
            return
        if self.screen_name == "route":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                surveillance_view.handle_route_click(self, event.pos)
            elif surveillance_view.handle_route_key(self, event):
                pass
            return
        if self.screen_name == "qte":
            self._qte_event(event)
            return
        if self.screen_name == "dialogue" and self._dialogue_event(event):
            return
        if self.screen_name == "notebook" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.notebook_tab == "board" and board_view.handle_board_click(self, event.pos):
                return
        # Глобально: дропдауны настроек — взаимоисключение и закрытие по клику в пустоту
        if self.screen_name == "settings" and hasattr(self, "resolution_dropdown"):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Проверяем попадание в любой дропдаун или его список
                def _hit_dd(dd):
                    if dd.rect.collidepoint(event.pos):
                        return True
                    if dd.open:
                        list_rect = pygame.Rect(dd.rect.x, dd.rect.bottom + 2, dd.rect.w, len(dd.options) * 32)
                        if list_rect.collidepoint(event.pos):
                            return True
                    return False
                hit_res = _hit_dd(self.resolution_dropdown)
                hit_mon = _hit_dd(self.monitor_dropdown)
                if not hit_res and not hit_mon:
                    # Клик в пустоту — закрыть оба
                    if self.resolution_dropdown.open or self.monitor_dropdown.open:
                        self.resolution_dropdown.open = False
                        self.monitor_dropdown.open = False
                # Даем дропдаунам обработать клик первым
            if hasattr(self, "resolution_dropdown"):
                if self.resolution_dropdown.handle_event(event):
                    self._pending_resolution = self.resolution_dropdown.selected
                    self._settings_changed = True
                    self.monitor_dropdown.open = False
                    return
                if self.monitor_dropdown.handle_event(event):
                    self._pending_monitor = self.monitor_dropdown.selected
                    self._settings_changed = True
                    self.resolution_dropdown.open = False
                    return
                if self.sfx_slider.handle_event(event):
                    self._settings_changed = True
                    return
                if self.music_slider.handle_event(event):
                    self._settings_changed = True
                    return
                if self.auto_update_toggle.handle_event(event):
                    self._settings_changed = True
                    return
                if self.voice_toggle.handle_event(event):
                    self._settings_changed = True
                    self.audio.play_sfx("click")
                    return
        if self.screen_name == "customization":
            # Единый макет: те же прямоугольники, что и при отрисовке (логические
            # координаты 1280×720). Раньше здесь брался размер физического окна,
            # поэтому на fullscreen/крупных разрешениях клики по портретам уходили мимо.
            layout = self._customization_layout()
            self.name_input.rect = layout.name_input
            self.name_input.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                avatar_idx = layout.avatar_at(event.pos)
                if avatar_idx is not None:
                    self.select_avatar(avatar_idx)
                bg_idx = layout.background_at(event.pos)
                if bg_idx is not None:
                    self.selected_bg = BACKGROUNDS[bg_idx]["id"]
        elif self.screen_name == "case_select":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                layout = self._case_select_layout()
                if layout.btn_back.collidepoint(event.pos):
                    pygame.time.wait(150)
                    self.screen_name = "menu"
                    return
                for idx, case in enumerate(self.cases):
                    if idx >= len(layout.cards):
                        break
                    if layout.cards[idx].button.collidepoint(event.pos):
                        pygame.time.wait(150)
                        self.start_case(case["id"])
                        return
        elif self.screen_name == "map":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.current_case:
                layout = self._map_layout()
                # повтор катсцены — та же кнопка, что рисуется в журнале
                if self._cutscene_replay_rect(layout).collidepoint(event.pos):
                    if cutscene_for(str(self.current_case.get("id", ""))):
                        pygame.time.wait(120)
                        self.play_cutscene()
                    return
                loc_id = layout.pin_at(event.pos)
                # Пины ловятся в тех же точках, где нарисованы (раньше клик
                # проверялся по сырым координатам дела и уходил мимо).
                if loc_id and loc_id in self.get_available_locations():
                    location = get_location(self.current_case, loc_id)
                    if not worldtime.is_open_now(location, self.state.case_time_minutes):
                        pygame.time.wait(120)
                        self.add_notification(worldtime.closed_reason(location, self.state.case_time_minutes))
                        self.audio.play_sfx("fail")
                        return
                    pygame.time.wait(120)
                    self.location_id = loc_id
                    self.screen_name = "location"
                    self.state.visited_locations.add(loc_id)
                    save_game(self.state)
                    self._maybe_riddle_tip(loc_id)
        elif self.screen_name == "location":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.search:
                    search_view.stop(self)
                    return
                self.screen_name = "map"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.search:
                    search_view.handle_click(self, event.pos)
                elif search_view.handle_start_click(self, event.pos):
                    pass

    def _maybe_riddle_tip(self, location_id):
        """Один раз за сохранение объяснить, что «КОД» — это загадка."""
        if getattr(self.state, "riddle_tip_shown", False):
            return
        clues = search_logic.visible_clues(self.current_case, location_id, self.state)
        for clue in clues:
            if clue["id"] in self.state.collected_clues:
                continue
            item = self.riddle_for(clue)
            if item and not riddle_logic.solved(self.state, item):
                self.state.riddle_tip_shown = True
                self.add_notification(
                    "Улика под загадкой: жмите «КОД», ответ выводится из текста"
                )
                save_game(self.state)
                return

    def get_available_locations(self):
        if not self.current_case:
            return set()
        # изначально доступны initial=True, остальные открываются по уликам
        avail = set()
        for loc in self.current_case["locations"]:
            if loc.get("initial"):
                avail.add(loc["id"])
            else:
                # проверяем есть ли улика которая ведёт к ней
                for clue in self.current_case["clues"]:
                    if (
                        loc["id"] in clue.get("leads_to", [])
                        and clue["id"] in self.state.collected_clues
                    ):
                        avail.add(loc["id"])
                        break
                # также если там персонаж с квестом? упрощаем
                if loc["id"] in self.state.visited_locations:
                    avail.add(loc["id"])
        # офис всегда доступен
        avail.add("office")
        return avail

    def update(self, mouse_pos, mouse_pressed):
        if not mouse_pressed:
            self._click_latch = False
        self.audio.update()
        self._update_music()
        # обновление времени
        if self.state.case_state == "in_progress":
            self.state.total_playtime += 1 / FPS
        if self.screen_name == "location" and self.search:
            try:
                self.search.update(self.clock.get_time() / 1000.0)
            except Exception:
                pass
            if self.search and getattr(self.search, "caught", False):
                search_view.stop(
                    self,
                    minutes=pressure.PATROL_CAUGHT_MINUTES,
                )
            elif self.search and self.search.expired:
                search_view.stop(self)
        if self.screen_name == "dialogue" and self.dialogue_char and self.dialogue_timer > 0:
            try:
                dt = self.clock.get_time() / 1000.0
            except Exception:
                dt = 1.0 / FPS
            self._update_dialogue_timer(dt)
        if self.state.case_state == "in_progress":
            self._check_deadline()
            # звонок ловит игрока только на карте — не в мини-игре и не в допросе
            if self.screen_name == "map":
                self._check_anonymous_call()
        if self.screen_name == "tail":
            try:
                dt = self.clock.get_time() / 1000.0
            except Exception:
                dt = 1.0 / FPS
            surveillance_view.update(self, dt)
        if self.screen_name == "qte":
            try:
                dt = self.clock.get_time() / 1000.0
            except Exception:
                dt = 1.0 / FPS
            qte_view.update(self, dt)
        if self.screen_name in ("tutorial", "cutscene", "puzzle"):
            try:
                dt = self.clock.get_time()
            except Exception:
                dt = 1000 // FPS
            if self.screen_name == "tutorial":
                self.tutorial.update(dt)
            elif self.screen_name == "puzzle":
                if self.puzzle:
                    self.puzzle.update(dt / 1000.0)
            elif self.cutscene:
                if self.cutscene.update(dt / 1000.0):
                    self._cutscene_done()
                else:
                    self._speak_cutscene()

    def _update_dialogue_timer(self, dt):
        """Тикает таймер реплики; на нуле тема закрывается молчанием."""
        ch = self.dialogue_char
        topics = (ch or {}).get("dialogue", [])
        if self.dialogue_idx >= len(topics):
            self.dialogue_timer = 0.0
            return
        topic = topics[self.dialogue_idx]
        answered = dialogue.chosen(self.state, ch["id"], self.dialogue_idx) is not None
        if answered or not dialogue.is_interactive(topic):
            self.dialogue_timer = 0.0
            return
        if not pressure.advanced(self.current_case):
            self.dialogue_timer = 0.0
            return
        self.dialogue_timer = max(0.0, self.dialogue_timer - max(0.0, dt))
        if self.dialogue_timer <= 0:
            self._dialogue_timeout()

    def _check_deadline(self):
        """Срок дела: предупреждение, затем принудительное закрытие."""
        case = self.current_case
        if not pressure.advanced(case):
            return
        if not self.state.deadline_missed and pressure.is_late(self.state, case):
            self.state.deadline_missed = True
            self.state.reputation = max(0, int(self.state.reputation) - 1)
            self.add_notification(
                "Срок дела вышел: прокурор недоволен, −1 репутация. "
                "Обвинение всё ещё возможно, но ранг упадёт."
            )
            self.audio.play_sfx("fail")
            save_game(self.state)
            return
        if self.state.deadline_missed and pressure.has_slipped_case(self.state, case):
            self.add_notification("Прокурор закрыл дело: срок истёк окончательно.")
            self.accusation_selected = None
            self._finish_case()

    def _check_anonymous_call(self):
        """Анонимный звонок: иногда наводка, иногда ловушка."""
        case = self.current_case
        number = pressure.call_due(self.state, case)
        if not number:
            return
        self.state.calls_seen = number
        spent = int(self.state.case_time_minutes or 0) + pressure.CALL_MINUTES
        self.state.case_time_minutes = spent
        rng = __import__("random").Random(f"{case.get('id', '')}:call:{number}")
        trap = rng.random() < pressure.CALL_TRAP_CHANCE
        if trap:
            self.state.case_time_minutes += pressure.CALL_TRAP_MINUTES
            self.add_notification(
                "Звонок: «Он на складе, идите туда сейчас же» — ловушка. "
                f"Вы потеряли {pressure.CALL_TRAP_MINUTES} минут."
            )
            self.audio.play_sfx("fail")
        else:
            self.state.reputation = int(self.state.reputation) + 1
            self.add_notification(
                "Звонок: аноним подсказал, где искать. +1 репутация за наводку."
            )
            self.audio.play_sfx("success")
        self.state.last_call_minute = int(self.state.case_time_minutes or 0)
        save_game(self.state)

    MOODS = {
        "menu": "noir",
        "case_select": "noir",
        "customization": "noir",
        "settings": "noir",
        "tutorial": "noir",
        "cutscene": "noir",
        "map": "investigation",
        "location": "investigation",
        "dialogue": "investigation",
        "notebook": "mystery",
        "accusation": "chase",
        "puzzle": "tension",
        "riddle": "mystery",
        "timeline": "mystery",
        "tail": "chase",
        "route": "chase",
        "qte": "chase",
    }

    # у каждого типа локации — своя тема: бар, порт, участок, место преступления
    LOCATION_MOODS = {
        "bar": "lounge",
        "port": "harbor",
        "warehouse": "harbor",
        "harbor": "harbor",
        "police": "precinct",
        "crime": "mystery",
        "vault": "mystery",
        "mansion": "mystery",
        "hub": "noir",
        "office": "noir",
    }

    def _music_key(self) -> str:
        """Какая тема должна играть прямо сейчас."""
        if self.screen_name == "ending":
            resolution = ending_logic.resolve(self.current_case, self.state) if self.current_case else {}
            return "success" if resolution.get("success") else "failure"
        if self.screen_name == "location":
            loc = get_location(self.current_case, self.location_id) if self.current_case else None
            return self.LOCATION_MOODS.get(str((loc or {}).get("type", "")), "investigation")
        return self.MOODS.get(self.screen_name, "noir")

    def _update_music(self):
        """Подобрать музыку под экран — и под место, если мы в локации."""
        key = self._music_key()
        if key == self._music_screen:
            return
        self._music_screen = key
        self.audio.play_music(key)

    def draw(self):
        # Letterbox рендер: рисуем всё на логический холст 1280×720, затем масштабируем
        real_screen = self.screen
        logical = pygame.Surface((self.LOGICAL_W, self.LOGICAL_H))
        self.screen = logical
        try:
            self.screen.fill(COLOR_BG)
            # фон — сетка города
            self.draw_city_background()
            if self.screen_name == "confirm":
                self.draw_confirm()
            elif self.screen_name == "menu":
                self.draw_menu()
            elif self.screen_name == "customization":
                self.draw_customization()
            elif self.screen_name == "case_select":
                self.draw_case_select()
            elif self.screen_name == "map":
                self.draw_map()
            elif self.screen_name == "location":
                self.draw_location()
            elif self.screen_name == "dialogue":
                self.draw_dialogue()
            elif self.screen_name == "notebook":
                self.draw_notebook()
            elif self.screen_name == "accusation":
                self.draw_accusation()
            elif self.screen_name == "ending":
                self.draw_ending()
            elif self.screen_name == "settings":
                self.draw_settings()
            elif self.screen_name == "tutorial":
                self.draw_tutorial()
            elif self.screen_name == "cutscene":
                self.draw_cutscene()
            elif self.screen_name == "puzzle":
                self.draw_puzzle()
            elif self.screen_name == "riddle":
                draw_riddle(self)
            elif self.screen_name == "timeline":
                timeline_view.draw_timeline(self)
            elif self.screen_name == "testimony":
                testimony_view.draw_testimony(self)
            elif self.screen_name == "tail":
                surveillance_view.draw(self)
            elif self.screen_name == "route":
                surveillance_view.draw_route(self)
            elif self.screen_name == "qte":
                qte_view.draw(self)
            # на катсцене ничего не перекрывает кадр
            if self.screen_name != "cutscene":
                # уведомления поверх всего
                self.draw_notifications()
                # проверка обновлений баннер
                self.draw_update_banner()
        finally:
            self.screen = real_screen
        if self.screen_name != "confirm":
            # держим последний «настоящий» кадр: поверх него рисуем подтверждение
            self._frame_snapshot = logical
        # масштабирование letterbox на физический экран
        try:
            Wp, Hp = real_screen.get_size()
        except Exception:
            Wp, Hp = self.LOGICAL_W, self.LOGICAL_H
        scale, ox, oy, w, h = self._get_letterbox()
        # чёрные поля
        real_screen.fill((0, 0, 0))
        if w == self.LOGICAL_W and h == self.LOGICAL_H and ox == 0 and oy == 0:
            real_screen.blit(logical, (0, 0))
        else:
            try:
                # сглаженное масштабирование для retina/улучшенных разрешений
                scaled = pygame.transform.smoothscale(logical, (w, h))
            except Exception:
                scaled = pygame.transform.scale(logical, (w, h))
            real_screen.blit(scaled, (ox, oy))

    def draw_city_background(self):
        W, H = self.screen.get_size()
        # фон — кабинет детектива; если картинки нет, остаётся сетка города
        bg = cover_image("locations/hub.jpg", (W, H), dim=0.66)
        if bg:
            self.screen.blit(bg, (0, 0))
        for x in range(0, W, 80):
            pygame.draw.line(self.screen, (22, 22, 30), (x, 0), (x, H), 1)
        for y in range(0, H, 80):
            pygame.draw.line(self.screen, (22, 22, 30), (0, y), (W, y), 1)
        fog = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(H):
            a = int(30 * (i / H))
            pygame.draw.line(fog, (0, 0, 0, a), (0, i), (W, i))
        self.screen.blit(fog, (0, 0))

    def draw_menu(self):
        W, H = self.screen.get_size()
        font_title = get_font(52, bold=True)
        font_sub = get_font(18)
        font_small = get_font(14)
        # центр панель — всегда по центру экрана, независимо от разрешения
        panel_rect = pygame.Rect(W // 2 - 360, H // 2 - 260, 720, 520)
        draw_panel(self.screen, panel_rect)
        # логотип — эмблема
        title = font_title.render("ДЕТЕКТИВ", True, COLOR_ACCENT)
        self.screen.blit(title, title.get_rect(center=(W // 2, panel_rect.y + 70)))
        subtitle = get_font(28, bold=True).render("БЛЭКВИЛ", True, COLOR_TEXT)
        self.screen.blit(subtitle, subtitle.get_rect(center=(W // 2, panel_rect.y + 115)))
        sub2 = font_sub.render(
            "КОД ГОРОДА  •  Нуар-расследование  •  Блэквил, 1987", True, COLOR_TEXT_DIM
        )
        self.screen.blit(sub2, sub2.get_rect(center=(W // 2, panel_rect.y + 150)))
        # разделитель
        pygame.draw.line(
            self.screen,
            COLOR_BORDER,
            (panel_rect.x + 40, panel_rect.y + 180),
            (panel_rect.right - 40, panel_rect.y + 180),
            1,
        )
        # детектив инфо
        det = self.state.detective
        # аватар превью
        av_data = next((a for a in AVATARS if a["id"] == det.avatar_id), AVATARS[0])
        r = pygame.Rect(W // 2 - 50, panel_rect.y + 195, 100, 100)
        draw_avatar(self.screen, r, av_data, selected=True)
        name_font = get_font(20, bold=True)
        name_surf = name_font.render(det.name, True, COLOR_TEXT)
        self.screen.blit(name_surf, name_surf.get_rect(center=(W // 2, panel_rect.y + 315)))
        bg_label = get_font(14).render(
            av_data["desc"] + " • " + det.background_label, True, COLOR_ACCENT
        )
        self.screen.blit(bg_label, bg_label.get_rect(center=(W // 2, panel_rect.y + 335)))
        # кнопки — с подсказками (ярлычками)
        btn_y = panel_rect.y + 370
        font_btn = get_font(16, bold=True)
        buttons = []
        has_save_flag = has_save() and self.state.current_case_id is not None
        if has_save_flag:
            b1 = Button((panel_rect.x + 80, btn_y, 260, 48), "ПРОДОЛЖИТЬ", accent=True, tooltip="Продолжить сохранённую игру")
            buttons.append(("continue", b1))
            b2 = Button((panel_rect.right - 340, btn_y, 260, 48), "НОВАЯ ИГРА", tooltip="Начать новую историю")
            buttons.append(("new", b2))
        else:
            b1 = Button((W // 2 - 140, btn_y, 280, 52), "НАЧАТЬ РАССЛЕДОВАНИЕ", accent=True, tooltip="Начать первую игру — создать детектива")
            buttons.append(("new", b1))
        # Второй ряд: четыре кнопки на всю ширину панели и со своим (мельче)
        # шрифтом — «КАСТОМИЗАЦИЯ» в узкую кнопку не влезала и выезжала за край.
        row2_gap = 10
        row2_x = panel_rect.x + 60
        row2_w = panel_rect.w - 120
        row2_bw = (row2_w - row2_gap * 3) // 4
        row2_y = btn_y + 60

        def _row2(index):
            return pygame.Rect(row2_x + index * (row2_bw + row2_gap), row2_y, row2_bw, 40)

        b3 = Button(_row2(0), "НАСТРОЙКИ", tooltip="Экран, звук и обновления")
        buttons.append(("settings", b3))
        b4 = Button(_row2(1), "КАСТОМИЗАЦИЯ", tooltip="Внешность и прошлое детектива")
        buttons.append(("custom", b4))
        b5 = Button(
            _row2(2),
            "ТУТОРИАЛ",
            accent=not self.tutorial_seen,
            tooltip="Как играть: карта, улики, блокнот и видео-обзор",
        )
        buttons.append(("tutorial", b5))
        b6 = Button(_row2(3), "ВЫХОД", tooltip="Выйти на рабочий стол (F1 — туториал)")
        buttons.append(("exit", b6))

        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        font_btn_small = get_font(12, bold=True)
        primary_keys = {"continue", "new"}
        for key, btn in buttons:
            btn.update(mouse, pressed)
            btn.draw(self.screen, font_btn if key in primary_keys else font_btn_small)
            if btn.clicked:
                # debounce
                pygame.time.wait(150)
                if key == "continue":
                    self.current_case = load_case(self.state.current_case_id)
                    self.screen_name = "map"
                elif key == "new":
                    self._start_new_game()
                elif key == "custom":
                    self.screen_name = "customization"
                elif key == "settings":
                    self.screen_name = "settings"
                elif key == "tutorial":
                    self.tutorial.goto(0)
                    self.screen_name = "tutorial"
                elif key == "exit":
                    self.running = False

        # версия внизу
        from . import __version__

        ver = font_small.render(
            f"v{__version__}  •  © Sams_studio128  •  {GITHUB_RELEASES_URL}",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(ver, ver.get_rect(center=(W // 2, panel_rect.bottom - 18)))
        quote = font_small.render("«Город не спит. Он ждёт, когда ты ошибёшься.»", True, COLOR_TEXT_DIM)
        self.screen.blit(quote, quote.get_rect(center=(W // 2, H - 20)))

    def _customization_layout(self):
        """Макет экрана кастомизации в логических координатах (общий для draw и кликов)."""
        return customization_layout(
            self.LOGICAL_W,
            self.LOGICAL_H,
            avatars=len(AVATARS),
            backgrounds=len(BACKGROUNDS),
        )

    def select_avatar(self, index: int) -> None:
        """Выбирает портрет и подставляет подходящее имя."""
        if not 0 <= index < len(AVATARS):
            return
        self.selected_avatar = index
        try:
            from .game_state import get_random_name_for_avatar

            self.name_input.text = get_random_name_for_avatar(AVATARS[index]["id"])
        except Exception:
            pass

    def draw_customization(self):
        W, H = self.LOGICAL_W, self.LOGICAL_H
        layout = self._customization_layout()
        panel = layout.panel
        font_title = get_font(26, bold=True)
        font_sub = get_font(14, bold=True)
        font_hint = get_font(11)
        font_btn = get_font(14, bold=True)
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]

        draw_panel(self.screen, layout.header)
        title = font_title.render("КАСТОМИЗАЦИЯ ДЕТЕКТИВА", True, COLOR_ACCENT)
        self.screen.blit(title, title.get_rect(center=(W // 2, layout.header.centery)))
        draw_panel(self.screen, panel)

        # --- Секция 1: Имя ---
        label = font_sub.render("ИМЯ ДЕТЕКТИВА", True, COLOR_ACCENT)
        self.screen.blit(label, layout.name_label)
        # Поле ввода + кнопка генерации имени (связана с фото ниже)
        self.name_input.rect = layout.name_input
        self.name_input.draw(self.screen, get_font(16))
        avatar_name = AVATARS[self.selected_avatar]["name"]
        btn_gen = Button(layout.name_button, "", tooltip=f"Случайное имя для «{avatar_name}»", style="secondary")
        btn_gen.update(mouse, pressed)
        btn_gen.draw(self.screen, get_font(16))
        draw_die_icon(
            self.screen,
            layout.name_button,
            color=COLOR_ACCENT if (btn_gen.hovered or btn_gen.pressed) else COLOR_TEXT_DIM,
        )
        if btn_gen.clicked:
            self.select_avatar(self.selected_avatar)
            self.add_notification(f"Имя сгенерировано: {self.name_input.text}")

        hint = font_hint.render(
            "Нажмите на кубик для случайного имени или выберите портрет — имя подберётся автоматически.",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(hint, (layout.name_hint[0], layout.name_hint[1]))

        # Разделитель
        pygame.draw.line(
            self.screen,
            COLOR_BORDER,
            (panel.x + 25, layout.divider_y),
            (panel.right - 25, layout.divider_y),
            1,
        )

        # --- Секция 2: Выбор образа ---
        label2 = font_sub.render("ВЫБЕРИТЕ ОБРАЗ", True, COLOR_ACCENT)
        self.screen.blit(label2, layout.avatars_label)
        sub_hint = font_hint.render("Нажмите на портрет чтобы выбрать", True, COLOR_TEXT_DARK)
        self.screen.blit(sub_hint, layout.avatars_hint)

        hovered_avatar = layout.avatar_at(mouse)
        for i, av in enumerate(AVATARS):
            rect = layout.avatar_rects[i]
            draw_avatar(self.screen, rect, av, selected=(i == self.selected_avatar))
            if hovered_avatar == i and i != self.selected_avatar:
                pygame.draw.rect(self.screen, COLOR_ACCENT_DIM, rect, width=2, border_radius=10)

        # Описание выбранного — под сеткой, в рамке
        selected_av = AVATARS[self.selected_avatar]
        draw_panel(
            self.screen,
            layout.desc,
            color=(32, 28, 40),
            border=COLOR_ACCENT_DIM,
            radius=6,
            with_shadow=False,
        )
        desc_text = f"{selected_av['name']} — {selected_av['desc']}"
        desc_surf = render_text(get_font(11), desc_text, COLOR_ACCENT)
        self.screen.blit(desc_surf, desc_surf.get_rect(center=layout.desc.center))

        # --- Секция 3: Прошлое ---
        label3 = font_sub.render("ПРОШЛОЕ", True, COLOR_ACCENT)
        self.screen.blit(label3, layout.past_label)

        hovered_bg_tooltip = None
        for i, bg in enumerate(BACKGROUNDS):
            rect = layout.bg_rects[i]
            is_sel = bg["id"] == self.selected_bg
            col = COLOR_ACCENT if is_sel else COLOR_PANEL_LIGHT
            tcol = (10, 10, 10) if is_sel else COLOR_TEXT
            pygame.draw.rect(self.screen, col, rect, border_radius=8)
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if is_sel else COLOR_BORDER,
                rect,
                width=2 if is_sel else 1,
                border_radius=8,
            )
            txt = render_text(get_font(12, bold=True), bg["label"], tcol)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            if rect.collidepoint(mouse):
                hovered_bg_tooltip = bg

        # описание прошлого — отдельной строкой над кнопками (раньше наезжало на них)
        bg_desc_map = {
            "private_eye": "Умеет находить общий язык с улицей. +1 к доверию свидетелей.",
            "ex_cop": "Связи в полиции. Видит скрытые детали в протоколах.",
            "reporter": "Острый глаз и умение разговорить любого собеседника.",
        }
        desc_text = bg_desc_map.get(self.selected_bg, "")
        bg_hint = font_hint.render(desc_text, True, COLOR_TEXT_DIM)
        self.screen.blit(bg_hint, bg_hint.get_rect(center=layout.bg_hint.center))

        # ярлычок при наведении на кнопку прошлого
        if hovered_bg_tooltip:
            tip_text = bg_desc_map.get(hovered_bg_tooltip["id"], "")
            tip_font = get_font(10)
            pad = 8
            tw, th = tip_font.size(tip_text)
            tx = max(8, min(mouse[0] - tw // 2, W - tw - 16))
            ty = max(8, mouse[1] - 32)
            bg_rect = pygame.Rect(tx - pad, ty - pad // 2, tw + pad * 2, th + pad)
            pygame.draw.rect(self.screen, (28, 28, 36), bg_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_ACCENT, bg_rect, width=1, border_radius=6)
            self.screen.blit(tip_font.render(tip_text, True, COLOR_TEXT), (tx, ty))

        # --- Кнопки «Назад» / «Сохранить» — отдельная строка футера ---
        btn_back = Button(layout.btn_back, "← НАЗАД", tooltip="Вернуться в главное меню без сохранения")
        btn_save = Button(layout.btn_save, "СОХРАНИТЬ", accent=True, tooltip="Сохранить детектива и перейти к выбору дела")
        for btn, action in [(btn_back, "back"), (btn_save, "save")]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, font_btn)
            if btn.clicked:
                pygame.time.wait(150)
                if action == "back":
                    self.screen_name = "menu"
                else:
                    name = self.name_input.text.strip()
                    if len(name) < 2:
                        self.add_notification("Имя слишком короткое!")
                        continue
                    av = AVATARS[self.selected_avatar]
                    self.state.detective = DetectiveProfile(
                        name=name,
                        avatar_id=av["id"],
                        background=self.selected_bg,
                        gender=av["gender"],
                    )
                    save_detective(self.state.detective)
                    self.add_notification(f"Детектив {name} сохранён")
                    self.screen_name = "case_select"

    def _case_select_layout(self):
        """Раскладка выбора дела в логических координатах — общая для draw и кликов."""
        return case_select_layout(self.LOGICAL_W, self.LOGICAL_H, len(self.cases))

    def draw_case_select(self):
        W, H = self.LOGICAL_W, self.LOGICAL_H
        layout = self._case_select_layout()
        font_title = get_font(28, bold=True)
        font_btn = get_font(16, bold=True)
        draw_panel(self.screen, layout.header)
        t = font_title.render("ВЫБЕРИ ДЕЛО, ДЕТЕКТИВ", True, COLOR_ACCENT)
        self.screen.blit(t, t.get_rect(center=(W // 2, layout.header.centery)))
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        btn_font = get_font(14, bold=True)

        for idx, case in enumerate(self.cases):
            if idx >= len(layout.cards):
                break
            card = layout.cards[idx]
            rect = card.rect
            draw_panel(self.screen, rect)
            # постер дела: карта города, если она есть у дела
            poster = card.poster
            poster_art = cover_image(
                case_map(case), (poster.w, poster.h), dim=0.45, tint=None
            ) if case_map(case) else None
            if blit_rounded_image(self.screen, poster_art, poster, radius=8):
                # затемнение под заголовок дела и значок «расследование»
                band = pygame.Surface((poster.w, 44), pygame.SRCALPHA)
                for row in range(44):
                    alpha = int(200 * (row / 43) ** 1.5)
                    pygame.draw.line(band, (6, 8, 14, alpha), (0, row), (poster.w, row))
                self.screen.blit(band, (poster.x, poster.bottom - 44))
                badge = get_font(10, bold=True).render("ДЕЛО", True, (230, 214, 160))
                self.screen.blit(badge, (poster.x + 10, poster.bottom - 26))
            else:
                for i in range(poster.h):
                    col = (30 + i // 3, 30 + i // 4, 40 + i // 5)
                    pygame.draw.line(
                        self.screen, col, (poster.x, poster.y + i), (poster.right, poster.y + i)
                    )
                # иконка-бейдж дела (эмодзи нет в бандл-шрифте — рисуем букву в кольце)
                draw_icon(
                    self.screen,
                    "",
                    poster.center,
                    max(48, min(poster.w, poster.h) // 2),
                    color=COLOR_ACCENT,
                    fallback=(case["title"][:1] or "?"),
                )
            pygame.draw.rect(self.screen, COLOR_BORDER, poster, width=1, border_radius=8)
            if case.get("id") in getattr(self.state, "completed_cases", set()):
                done_txt = get_font(9, bold=True).render("✓ ПРОЙДЕНО", True, (12, 12, 12))
                done_chip = pygame.Rect(0, 0, done_txt.get_width() + 14, 18)
                done_chip.topright = (poster.right - 8, poster.y + 8)
                pygame.draw.rect(self.screen, COLOR_GREEN, done_chip, border_radius=9)
                self.screen.blit(done_txt, (done_chip.x + 7, done_chip.y + 4))
            # заголовок и подзаголовок
            title_surf = get_font(18, bold=True).render(case["title"], True, COLOR_TEXT)
            self.screen.blit(title_surf, card.title_pos)
            sub = get_font(12).render(case["subtitle"], True, COLOR_ACCENT)
            self.screen.blit(sub, card.subtitle_pos)
            opened, total_end = ending_logic.progress(self.state, case)
            diff = get_font(11).render(
                f"{case['difficulty']} • {case['duration']} • концовки {opened}/{total_end}",
                True,
                COLOR_TEXT_DIM,
            )
            self.screen.blit(diff, card.meta_pos)
            # описание
            draw_text_wrapped(
                self.screen, case["description"], get_font(12), COLOR_TEXT_DIM, card.desc
            )
            # интро (на низких экранах может не хватить места — тогда пропускаем)
            if card.intro.h > 0:
                draw_panel(self.screen, card.intro, color=(20, 20, 28), border=(40, 40, 50))
                draw_text_wrapped(
                    self.screen,
                    case["intro"][:220] + "...",
                    get_font(10),
                    COLOR_TEXT_DIM,
                    pygame.Rect(
                        card.intro.x + 10, card.intro.y + 8, card.intro.w - 20, card.intro.h - 16
                    ),
                )
            # кнопка «ВЗЯТЬ ДЕЛО»
            btn_rect = card.button
            hovered = btn_rect.collidepoint(mouse)
            col = COLOR_ACCENT_HOVER if hovered else COLOR_ACCENT
            pygame.draw.rect(self.screen, col, btn_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_BORDER, btn_rect, width=1, border_radius=6)
            btn_text = btn_font.render("ВЗЯТЬ ДЕЛО", True, (10, 10, 10))
            self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
            # ярлычок-тултип цены при наведении (если есть)
            if hovered and case.get("price"):
                tip_font = get_font(10)
                tip = case["price"]
                tw, th = tip_font.size(tip)
                tx = btn_rect.centerx - tw // 2
                ty = btn_rect.y - th - 8
                tp_rect = pygame.Rect(tx - 8, ty - 4, tw + 16, th + 8)
                pygame.draw.rect(self.screen, (28, 28, 36), tp_rect, border_radius=4)
                pygame.draw.rect(self.screen, COLOR_BORDER, tp_rect, width=1, border_radius=4)
                self.screen.blit(tip_font.render(tip, True, COLOR_TEXT_DIM), (tx, ty))
        # назад (клик обрабатывается в handle_event — по событиям мыши)
        btn_back = Button(layout.btn_back, "← НАЗАД", tooltip="Вернуться в меню")
        btn_back.update(mouse, pressed)
        btn_back.draw(self.screen, font_btn)

    def start_case(self, case_id, new_run: bool = False):
        """Начать дело. ``new_run`` — прохождение «с нуля» (кнопка «СЫГРАТЬ ЕЩЁ»).

        При обычном старте ресурсы детектива переносятся из прошлого дела
        (карьера), а при переигровке того же дела — сбрасываются: иначе финал
        сразу получал S+ за репутацию, набранную в предыдущем заходе.
        """
        case = load_case(case_id)
        if not case:
            return
        self.current_case = case
        self.state.current_case_id = case_id
        if new_run:
            self.state.reputation = START_REPUTATION
            self.state.money = START_MONEY
        self.state.visited_locations = set(["office"])
        self.state.collected_clues = set()
        self.state.interrogated = set()
        self.state.case_time_minutes = 0
        self.state.game_day = 1
        self.state.case_state = "in_progress"
        self.state.accusation_result = None
        self.state.accusation_correct = None
        self.state.dialogue_choices = {}
        self.state.trust = {}
        self.state.trust_bonus_taken = set()
        # механики расследования начинаются с чистого листа
        self.state.board_links = set()
        self.state.board_wrong = set()
        self.state.timeline_order = []
        self.state.timeline_solved = False
        self.state.timeline_attempts = 0
        self.state.search_found = set()
        self.state.hidden_found = set()
        self.state.tail_done = set()
        self.state.tail_failed = set()
        self.state.tail_blocked_until_day = 0
        self.state.exposed_lies = {}
        self.state.asked_topics = set()
        self.state.confirmed_clues = set()
        self.state.fake_clues = set()
        self.state.deductions = set()
        self.state.trial_motive = None
        self.state.trial_method = None
        self.state.riddles_solved = set()
        self.state.riddle_tip_shown = False
        self.state.deadline_missed = False
        self.state.calls_seen = 0
        self.state.last_call_minute = 0
        self.state.silenced = {}
        self.testimony_selected = []
        self.testimony_message = ""
        self.testimony_scroll = 0
        self.dialogue_timer = 0.0
        self.trial_rects = {}
        self.expertise_rects = {}
        self.state.fight_done = False
        self.state.warrant = False
        self.accusation_selected = None
        self.board_clue = None
        self.board_message = ""
        self.timeline_selected = None
        self.timeline_message = ""
        self.search = None
        self.tail = None
        self.tail_spec = None
        self.tail_reward = None
        self.qte = None
        self.ending_rects = {}
        save_game(self.state)
        self.location_id = "office"
        self.add_notification(f"Дело «{case['title']}» начато. Удачи, {self.state.detective.name}!")
        self.play_cutscene(case_id)

    # ── прогресс: следующее дело ─────────────────────────────────────

    def next_case(self):
        """Следующее дело по порядку карточек или None, если это последнее."""
        case_id = str((self.current_case or {}).get("id", ""))
        ids = [str(c.get("id", "")) for c in self.cases]
        if case_id not in ids:
            return None
        index = ids.index(case_id) + 1
        return self.cases[index] if index < len(ids) else None

    def _ending_success(self) -> bool:
        """Дело закрыто успешно (для кнопки «Следующее дело»)."""
        if not self.current_case:
            return False
        return bool(ending_logic.resolve(self.current_case, self.state).get("success"))

    def start_next_case(self) -> bool:
        """Начать следующее дело (с катсценой). False — если следующего нет."""
        nxt = self.next_case()
        if not nxt or not nxt.get("id"):
            return False
        self.start_case(nxt["id"])
        return True

    # ── катсцена ─────────────────────────────────────────────────────

    def play_cutscene(self, case_id=None) -> bool:
        """Запустить катсцену дела. False — если для дела её нет."""
        case_id = case_id or (self.current_case or {}).get("id")
        scene = cutscene_for(str(case_id or ""))
        if not scene:
            if self.screen_name == "cutscene":
                self.screen_name = "map"
            return False
        self.cutscene = CutscenePlayer(scene, self.LOGICAL_W, self.LOGICAL_H)
        self.screen_name = "cutscene"
        self._cutscene_case = str(case_id or "tutorial")
        # кадр не уходит раньше, чем закончится его озвучка
        for i, frame in enumerate(scene.scenes):
            seconds = self.audio.voice_length(f"cutscene_{self._cutscene_case}_{i + 1}")
            if seconds:
                frame.duration = max(frame.duration, seconds + 0.9)
        self._cutscene_voice_index = -1
        self._speak_cutscene()
        return True

    def _speak_cutscene(self):
        """Озвучка кадра катсцены (если для него есть файл в assets/voice)."""
        player = self.cutscene
        if not player:
            return
        index = player.index
        if index == self._cutscene_voice_index:
            return
        self._cutscene_voice_index = index
        self.audio.stop_voice()
        scene = player.scene
        if scene is None:
            return
        self.audio.play_voice(f"cutscene_{self._cutscene_case}_{index + 1}")

    def _cutscene_done(self):
        """Катсцена закончилась (досмотрена или пропущена)."""
        self.audio.stop_voice()
        self._cutscene_voice_index = -1
        if self.cutscene:
            self.cutscene.clear_cache()
        self.screen_name = "map" if self.current_case else "case_select"

    def handle_cutscene_event(self, event) -> bool:
        """Управление катсценой: дальше, пропустить, пауза."""
        player = self.cutscene
        if not player:
            self._cutscene_done()
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                player.skip()
                self._cutscene_done()
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_RIGHT):
                player.advance()
                if player.finished:
                    self._cutscene_done()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if cutscene_button_rect(self.LOGICAL_W, self.LOGICAL_H).collidepoint(event.pos):
                player.skip()
                self._cutscene_done()
                return True
            player.advance()
            if player.finished:
                self._cutscene_done()
            return True
        return False

    def draw_cutscene(self):
        if not self.cutscene:
            self._cutscene_done()
            return
        draw_cutscene_screen(self.screen, self.cutscene)

    # ── улики и головоломки ──────────────────────────────────────────

    def collect_clue(self, clue):
        """Забрать улику в блокнот (с уведомлениями, временем и звуком)."""
        if clue["id"] in self.state.collected_clues:
            return
        self.state.collected_clues.add(clue["id"])
        for _nid in clue.get("leads_to", []):
            self.add_notification("Новая локация открыта!")
        self.state.case_time_minutes += 10
        self.audio.play_sfx("clue")
        save_game(self.state)
        self.add_notification(f"Улика собрана: {clue['title']}")

    def riddle_for(self, clue):
        """Загадка-код на улике (или None, если замка нет)."""
        return riddle_logic.spec(self.current_case, clue)

    def open_riddle(self, clue):
        """Открыть кодовый замок: код выводится из фактов дела."""
        item = self.riddle_for(clue)
        if not item or riddle_logic.solved(self.state, item):
            self.open_puzzle(clue)
            return
        item = dict(item, clue_id=clue.get("id"))
        self.riddle = item
        self.riddle_clue = clue
        self.riddle_input = ""
        self.riddle_hint = ""
        self.riddle_message = ""
        self.riddle_attempts = 0
        self.riddle_rects = {}
        self.screen_name = "riddle"
        self.audio.play_music("mystery")

    def open_puzzle(self, clue):
        """Открыть головоломку, которая охраняет улику."""
        spec = clue.get("puzzle")
        if not spec:
            self.collect_clue(clue)
            if self.screen_name == "riddle":
                # замок открыт, а головоломки нет — сразу обратно в локацию
                self.screen_name = "location"
            return
        self.puzzle = puzzles.Puzzle(spec, seed=str(clue.get("id", "")))
        self.puzzle_clue = clue
        self.puzzle_rects = {}
        self._puzzle_started_at = time.time()
        self.screen_name = "puzzle"
        self.audio.play_music("tension")

    def close_puzzle(self):
        self.puzzle = None
        self.puzzle_clue = None
        self.puzzle_rects = {}
        self.screen_name = "location"
        self._music_screen = None

    def finish_puzzle_flow(self):
        """Нажали «Продолжить» после победы или провала."""
        puzzle = self.puzzle
        clue = self.puzzle_clue
        if puzzle and puzzle.success and clue:
            self.collect_clue(clue)
        elif puzzle and puzzle.failed:
            # попытка стоит времени, но не блокирует дело навсегда
            self.state.case_time_minutes += 15
            save_game(self.state)
            self.add_notification("Замок не поддался. Можно вернуться позже.")
        self.close_puzzle()

    def submit_puzzle_code(self):
        if not self.puzzle:
            return
        before = self.puzzle.success
        self.puzzle.submit_code()
        if self.puzzle.success and not before:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")
        else:
            self.audio.play_sfx("tick")

    def strike_lockpick(self):
        if not self.puzzle:
            return
        hit = self.puzzle.strike()
        if self.puzzle.success:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")
        else:
            self.audio.play_sfx("dial" if hit else "tick")

    def cut_wire(self, index: int):
        if not self.puzzle:
            return
        self.audio.play_sfx("slide")
        correct = self.puzzle.cut(index)
        if correct:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")

    def tap_shape(self, name: str):
        if not self.puzzle:
            return
        result = self.puzzle.tap(name)
        if result is None:
            return
        if self.puzzle.success:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")
        else:
            self.audio.play_sfx("page" if result else "tick")

    def _qte_event(self, event) -> None:
        """Ввод в драке: стрелки/WASD, Esc, Enter."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            qte_view.handle_click(self, event.pos)
        else:
            qte_view.handle_key(self, event)

    def submit_puzzle_grid(self):
        """Проверить сетку алиби."""
        if not self.puzzle:
            return
        before = self.puzzle.success
        self.puzzle.submit_grid()
        self._puzzle_sound(before)

    def submit_puzzle_develop(self):
        """Проверить параметры проявки."""
        if not self.puzzle:
            return
        before = self.puzzle.success
        self.puzzle.submit_develop()
        self._puzzle_sound(before)

    def strike_puzzle_align(self):
        """Приложить отпечаток (игла против метки)."""
        if not self.puzzle:
            return
        before = self.puzzle.success
        hit = self.puzzle.strike_angle()
        if self.puzzle.success and not before:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")
        else:
            self.audio.play_sfx("dial" if hit else "tick")

    def assign_puzzle_alibi(self, person: int, place: int):
        """Поставить человека в место на сетке алиби."""
        if not self.puzzle or not self.puzzle.assign(person, place):
            return
        self.audio.play_sfx("tick")

    def adjust_puzzle_param(self, name: str, delta: int):
        """Покрутить ползунок проявки."""
        if not self.puzzle:
            return
        self.puzzle.adjust(name, delta)
        self.audio.play_sfx("slide")

    def _puzzle_sound(self, before: bool) -> None:
        if not self.puzzle:
            return
        if self.puzzle.success and not before:
            self.audio.play_sfx("success")
        elif self.puzzle.failed:
            self.audio.play_sfx("fail")
        else:
            self.audio.play_sfx("tick")

    def draw_puzzle(self):
        if not self.puzzle:
            self.close_puzzle()
            return
        draw_puzzle_screen(self)

    def _cutscene_replay_rect(self, layout) -> pygame.Rect:
        """Кнопка «КАК ВСЁ БЫЛО» в журнале карты (одна для отрисовки и кликов)."""
        right = layout.right
        return pygame.Rect(right.x + 15, layout.btn_menu.y - 82, right.w - 30, 26)

    def _map_layout(self):
        """Макет карты (общий для отрисовки и кликов) — логические координаты."""
        locations = (self.current_case or {}).get("locations", [])
        return map_layout(
            self.LOGICAL_W,
            self.LOGICAL_H,
            locations,
            pin_radius=18,
            world=(WINDOW_WIDTH, WINDOW_HEIGHT),
        )

    def _draw_case_map(self, rect: pygame.Rect) -> None:
        """Фон карты дела: картинка города + подписи районов + вуаль под пины."""
        draw_panel(self.screen, rect)
        art = cover_image(case_map(self.current_case), (rect.w, rect.h), dim=0.5)
        if blit_rounded_image(self.screen, art, rect, radius=8):
            veil = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            veil.fill((8, 10, 18, 80))
            self.screen.blit(veil, rect.topleft)
            # нижняя «шторка»: подсказка внизу карты должна читаться
            band_h = max(48, int(rect.h * 0.1))
            band = pygame.Surface((rect.w, band_h), pygame.SRCALPHA)
            for row in range(band_h):
                alpha = int(225 * (row / max(1, band_h - 1)) ** 1.5)
                pygame.draw.line(band, (8, 10, 18, alpha), (0, row), (rect.w, row))
            self.screen.blit(band, (rect.x, rect.bottom - band_h))
        else:
            # запасной вариант, если картинки нет: прежняя тёмная сетка
            pygame.draw.rect(self.screen, (18, 18, 26), rect, border_radius=8)
            for x in range(rect.x, rect.right, 80):
                pygame.draw.line(self.screen, (40, 40, 50), (x, rect.y), (x, rect.bottom), 1)
            for y in range(rect.y, rect.bottom, 80):
                pygame.draw.line(self.screen, (40, 40, 50), (rect.x, y), (rect.right, y), 1)

        # районы города: подпись на плашке, чтобы читалась на любой карте
        font_dist = get_font(10, bold=True)
        for name, nx, ny in (
            ("ХОЛМЫ", 0.03, 0.04),
            ("СЕВЕР", 0.55, 0.04),
            ("ЗАПАД", 0.03, 0.52),
            ("ЦЕНТР", 0.46, 0.30),
            ("ПОРТ", 0.72, 0.62),
        ):
            label = font_dist.render(name, True, (214, 206, 186))
            badge = pygame.Surface((label.get_width() + 12, label.get_height() + 4), pygame.SRCALPHA)
            pygame.draw.rect(badge, (10, 12, 20, 165), badge.get_rect(), border_radius=3)
            pos = (rect.x + int(nx * rect.w), rect.y + int(ny * rect.h))
            self.screen.blit(badge, pos)
            self.screen.blit(label, (pos[0] + 6, pos[1] + 2))
        pygame.draw.rect(self.screen, COLOR_BORDER, rect, width=1, border_radius=8)

    def draw_map(self):
        if not self.current_case:
            return
        layout = self._map_layout()
        font_title = get_font(20, bold=True)
        font_small = get_font(13)

        # header
        draw_panel(self.screen, layout.header)
        # у туториала в названии уже есть слово «дело» — не дублируем
        raw_title = self.current_case["title"].upper()
        title_text = raw_title if "ДЕЛО" in raw_title else f"ДЕЛО: {raw_title}"
        case_title = font_title.render(title_text, True, COLOR_ACCENT)
        self.screen.blit(case_title, (layout.header.x + 20, layout.header.y + 8))
        deadline_chip = pressure.deadline_chip(self.state, self.current_case)
        day_text = font_small.render(
            worldtime.clock_text(self.state.case_time_minutes)
            + f" • Улик: {len(self.state.collected_clues)}/{len(self.current_case['clues'])}"
            f" (нужно {ending_logic.required_clues(self.current_case)})"
            f" • ★ {self.state.reputation} • ${self.state.money}"
            + (f" • {deadline_chip}" if deadline_chip else ""),
            True,
            COLOR_RED if self.state.deadline_missed else COLOR_TEXT_DIM,
        )
        self.screen.blit(day_text, (layout.header.x + 20, layout.header.y + 30))

        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        can_accuse = ending_logic.can_accuse(self.state, self.current_case)
        btn_notebook = Button(layout.btn_notebook, "БЛОКНОТ")
        btn_dossier = Button(layout.btn_dossier, "ДОСЬЕ")
        btn_accuse = Button(
            layout.btn_accuse,
            "ОБВИНИТЬ",
            accent=True,
            tooltip=ending_logic.clue_hint(self.state, self.current_case),
        )
        btn_accuse.enabled = can_accuse
        for btn, action in [
            (btn_notebook, "notebook"),
            (btn_dossier, "dossier"),
            (btn_accuse, "accuse"),
        ]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(12, bold=True))
            if btn.clicked:
                pygame.time.wait(150)
                if action == "notebook":
                    self.notebook_tab = "clues"
                    self.screen_name = "notebook"
                elif action == "dossier":
                    self.notebook_tab = "suspects"
                    self.screen_name = "notebook"
                elif action == "accuse" and can_accuse:
                    self.accusation_selected = None
                    self.timeline_return = "accusation"
                    self.timeline_selected = None
                    self.timeline_message = ""
                    if timeline.available(self.current_case) and not timeline.is_solved(
                        self.state, self.current_case
                    ):
                        # перед обвинением — реконструкция; её можно пропустить
                        self.screen_name = "timeline"
                    else:
                        self.screen_name = "accusation"

        # карта дела — художественная карта-картинка (assets/images/maps/…)
        self._draw_case_map(layout.map_rect)

        # локации: позиции берём из макета — те же, по которым ловим клики
        avail = self.get_available_locations()
        for loc, pin_rect in zip(self.current_case["locations"], layout.pins, strict=False):
            if loc["id"] not in avail:
                continue
            visited = loc["id"] in self.state.visited_locations
            draw_map_pin(
                self.screen,
                pin_rect.center,
                loc,
                visited=visited,
                current=(loc["id"] == self.location_id),
            )
            if not worldtime.is_open_now(loc, self.state.case_time_minutes):
                badge = (pin_rect.right - 4, pin_rect.y + 2)
                pygame.draw.circle(self.screen, (14, 16, 24), badge, 9)
                pygame.draw.circle(self.screen, (170, 150, 90), badge, 9, 1)
                pygame.draw.line(self.screen, (200, 180, 110), (badge[0], badge[1]), (badge[0], badge[1] - 5), 2)
                pygame.draw.line(self.screen, (200, 180, 110), (badge[0], badge[1]), (badge[0] + 4, badge[1] + 2), 2)

        # кнопки на карте: «ЖДАТЬ» и «СЛЕЖКА»
        action_y = layout.map_rect.y + 10
        tail_ready = surveillance.available(self.current_case, self.state)
        tail_rect = pygame.Rect(layout.map_rect.right - 208, action_y, 96, 26)
        wait_rect = pygame.Rect(layout.map_rect.right - 104, action_y, 96, 26)
        for rect, label, enabled, action in (
            (tail_rect, "СЛЕЖКА", tail_ready, "tail"),
            (wait_rect, "ЖДАТЬ", True, "wait"),
        ):
            hovered = rect.collidepoint(mouse) and enabled
            pygame.draw.rect(
                self.screen,
                (52, 46, 32) if hovered else (16, 18, 26),
                rect,
                border_radius=6,
            )
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if enabled else (60, 60, 70),
                rect,
                width=1,
                border_radius=6,
            )
            chip = get_font(10, bold=True).render(
                label, True, COLOR_ACCENT if enabled else COLOR_TEXT_DARK
            )
            self.screen.blit(chip, chip.get_rect(center=rect.center))
        self.map_action_rects = {"tail": tail_rect, "wait": wait_rect}
        if tail_rect.collidepoint(mouse) and pressed and self._click_once():
            if tail_ready and surveillance_view.start(self):
                pygame.time.wait(120)
                return
            if surveillance.blocked(self.current_case, self.state):
                self.add_notification(surveillance.block_text(self.current_case, self.state))
            else:
                self.add_notification("Сначала найдите зацепку (улику) для слежки")
        if wait_rect.collidepoint(mouse) and pressed and self._click_once():
            location, wait = worldtime.nearest_opening(self.current_case, self.state)
            if not wait:
                wait = 60
                self.add_notification("Все локации открыты. Вы ждёте час.")
            else:
                self.add_notification(
                    f"Вы ждёте до открытия «{location['name']}» — {wait} мин."
                )
            worldtime.advance(self.state, wait)
            save_game(self.state)
            pygame.time.wait(120)

        hint = font_small.render(
            "Нажмите на локацию, чтобы посетить. Серые — недоступны, пока не найдёте зацепку. "
            "Часы работы — на пинах.",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(hint, (layout.hint.x, layout.hint.y))

        # правая панель — журнал детектива
        right = layout.right
        draw_panel(self.screen, right)
        r_title = get_font(14, bold=True).render("ЖУРНАЛ ДЕТЕКТИВА", True, COLOR_ACCENT)
        self.screen.blit(r_title, (right.x + 15, right.y + 15))
        av = next((a for a in AVATARS if a["id"] == self.state.detective.avatar_id), AVATARS[0])
        avatar_rect = pygame.Rect(right.x + 15, right.y + 40, 50, 50)
        draw_avatar(self.screen, avatar_rect, av, selected=True)
        name_surf = get_font(13, bold=True).render(self.state.detective.name, True, COLOR_TEXT)
        self.screen.blit(name_surf, (right.x + 75, right.y + 45))
        bg_surf = get_font(11).render(self.state.detective.background_label, True, COLOR_TEXT_DIM)
        self.screen.blit(bg_surf, (right.x + 75, right.y + 62))
        pygame.draw.line(
            self.screen,
            COLOR_BORDER,
            (right.x + 15, right.y + 100),
            (right.right - 15, right.y + 100),
            1,
        )
        clue_title = get_font(12, bold=True).render("СОБРАННЫЕ УЛИКИ", True, COLOR_TEXT)
        self.screen.blit(clue_title, (right.x + 15, right.y + 110))
        y = right.y + 135
        font_clue = get_font(12)
        if not self.state.collected_clues:
            empty = font_clue.render("Пока пусто. Ищите в локациях!", True, COLOR_TEXT_DARK)
            self.screen.blit(empty, (right.x + 15, y))
        else:
            for clue_id in list(self.state.collected_clues)[-6:]:
                clue = get_clue(self.current_case, clue_id)
                if not clue:
                    continue
                pygame.draw.rect(
                    self.screen, (40, 40, 50), (right.x + 15, y, 240, 30), border_radius=4
                )
                pygame.draw.rect(
                    self.screen, COLOR_BORDER, (right.x + 15, y, 240, 30), width=1, border_radius=4
                )
                imp_col = COLOR_ACCENT if clue.get("importance") == "high" else COLOR_TEXT_DIM
                pygame.draw.circle(self.screen, imp_col, (right.x + 28, y + 15), 5)
                t = font_clue.render(clue["title"][:24], True, COLOR_TEXT)
                self.screen.blit(t, (right.x + 40, y + 7))
                y += 36
                if y > layout.btn_menu.y - 124:
                    break
        prog_rect = pygame.Rect(right.x + 15, layout.btn_menu.y - 106, right.w - 30, 8)
        pygame.draw.rect(self.screen, (40, 40, 50), prog_rect, border_radius=4)
        progress = len(self.state.collected_clues) / max(1, len(self.current_case["clues"]))
        pygame.draw.rect(
            self.screen,
            COLOR_ACCENT,
            (prog_rect.x, prog_rect.y, int(prog_rect.w * progress), prog_rect.h),
            border_radius=4,
        )
        prog_text = get_font(10).render(
            f"Прогресс расследования: {int(progress * 100)}%", True, COLOR_TEXT_DIM
        )
        self.screen.blit(prog_text, (right.x + 15, prog_rect.y - 15))

        # повтор катсцены «как всё было»
        has_cut = cutscene_for(str((self.current_case or {}).get("id", ""))) is not None
        cut_rect = self._cutscene_replay_rect(layout)
        btn_cut = Button(
            cut_rect,
            "▶ КАК ВСЁ БЫЛО",
            enabled=has_cut,
            tooltip="Посмотреть вступление дела ещё раз",
        )
        btn_cut.update(mouse, pressed)
        btn_cut.draw(self.screen, get_font(10, bold=True))
        if btn_cut.clicked and has_cut and self._click_once():
            pygame.time.wait(120)
            self.play_cutscene()

        btn_back2 = Button(layout.btn_menu, "← МЕНЮ")
        btn_save2 = Button(layout.btn_save, "СОХРАНИТЬ")
        for btn, act in [(btn_back2, "menu"), (btn_save2, "save")]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(10, bold=True))
            if btn.clicked:
                pygame.time.wait(150)
                if act == "menu":
                    self.screen_name = "menu"
                else:
                    save_game(self.state)
                    self.add_notification("Игра сохранена")

    def draw_location(self):
        if not self.current_case:
            return
        loc = get_location(self.current_case, self.location_id)
        if not loc:
            self.screen_name = "map"
            return
        font_title = get_font(24, bold=True)
        font_btn = get_font(13, bold=True)
        # header
        header = pygame.Rect(20, 15, WINDOW_WIDTH - 40, 50)
        draw_panel(self.screen, header)
        title = font_title.render(loc["name"].upper(), True, COLOR_ACCENT)
        self.screen.blit(title, (header.x + 20, header.y + 12))
        btn_back = Button((header.right - 220, header.y + 10, 100, 30), "← КАРТА")
        btn_notes = Button((header.right - 110, header.y + 10, 90, 30), "БЛОКНОТ")
        # подпись типа и района — слева от кнопок и с обрезкой по доступной ширине
        type_text = (
            type_label(loc)
            + " • "
            + loc["district"]
            + " • "
            + worldtime.hours_label(loc)
            + " • "
            + worldtime.clock_text(self.state.case_time_minutes)
        )
        type_font = get_font(11)
        avail = header.right - 230 - (header.x + 30)
        while type_text and type_font.size(type_text)[0] > avail:
            type_text = type_text[:-1]
        if type_text:
            type_txt = type_font.render(type_text.rstrip(" •"), True, COLOR_TEXT_DIM)
            self.screen.blit(type_txt, (header.right - 240 - type_txt.get_width(), header.y + 20))
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        for btn, act in [(btn_back, "map"), (btn_notes, "notebook")]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(12, bold=True))
            if btn.clicked:
                pygame.time.wait(150)
                self.screen_name = act
        # main
        main_rect = pygame.Rect(20, 75, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 95)
        draw_panel(self.screen, main_rect)
        if not worldtime.is_open_now(loc, self.state.case_time_minutes):
            veil = pygame.Surface((main_rect.w, main_rect.h), pygame.SRCALPHA)
            veil.fill((6, 8, 14, 225))
            self.screen.blit(veil, main_rect.topleft)
            reason = worldtime.closed_reason(loc, self.state.case_time_minutes)
            head = get_font(30, bold=True).render("ЗАКРЫТО", True, COLOR_ACCENT)
            self.screen.blit(head, head.get_rect(center=(main_rect.centerx, main_rect.y + 150)))
            sub = get_font(15).render(
                f"{loc['name']} — часы работы {worldtime.hours_label(loc)}", True, COLOR_TEXT
            )
            self.screen.blit(sub, sub.get_rect(center=(main_rect.centerx, main_rect.y + 196)))
            why = get_font(13).render(reason, True, COLOR_TEXT_DIM)
            self.screen.blit(why, why.get_rect(center=(main_rect.centerx, main_rect.y + 224)))
            clock = get_font(13, bold=True).render(
                worldtime.clock_text(self.state.case_time_minutes), True, COLOR_TEXT_DIM
            )
            self.screen.blit(clock, clock.get_rect(center=(main_rect.centerx, main_rect.y + 250)))
            wait_btn = Button(
                (main_rect.centerx - 130, main_rect.y + 290, 260, 46),
                "ПОДОЖДАТЬ ДО ОТКРЫТИЯ",
                accent=True,
            )
            wait_btn.update(mouse, pressed)
            wait_btn.draw(self.screen, get_font(13, bold=True))
            if wait_btn.clicked and self._click_once():
                pygame.time.wait(140)
                worldtime.wait_until_open(self.state, self.current_case, loc)
                self.add_notification(
                    f"Вы прождали до открытия: {worldtime.clock_text(self.state.case_time_minutes)}"
                )
                save_game(self.state)
            return
        # слева — визуал локации
        visual = pygame.Rect(main_rect.x + 15, main_rect.y + 15, 500, 300)
        # иллюстрация локации (по типу), с «погодой»-вуалью для разных мест
        art_name, art_tint = location_art(loc)
        art = cover_image(art_name or "", (visual.w, visual.h), dim=0.18, tint=art_tint) if art_name else None
        if blit_rounded_image(self.screen, art, visual, radius=8):
            # нижняя шторка, чтобы подписи поверх картинки читались
            band_h = 46
            band = pygame.Surface((visual.w, band_h), pygame.SRCALPHA)
            for row in range(band_h):
                alpha = int(210 * (row / max(1, band_h - 1)) ** 1.4)
                pygame.draw.line(band, (6, 8, 14, alpha), (0, row), (visual.w, row))
            self.screen.blit(band, (visual.x, visual.bottom - band_h))
        else:
            base_col = (30, 30, 40)
            for i in range(visual.h):
                col = tuple(min(255, c + i // 8) for c in base_col)
                pygame.draw.line(
                    self.screen, col, (visual.x, visual.y + i), (visual.right, visual.y + i)
                )
        pygame.draw.rect(self.screen, COLOR_BORDER, visual, width=1, border_radius=8)
        # иконка
        icon_map = {
            "police": "🚔",
            "crime": "🚧",
            "bar": "🍸",
            "apartment": "🏠",
            "bank": "🏦",
            "vault": "🔒",
            "public": "🏫",
            "hub": "🕵️",
            "warehouse": "📦",
            "shop": "🔬",
            "port": "⚓",
            "mansion": "🏰",
        }
        icon = icon_map.get(loc["type"], "📍")
        draw_icon(
            self.screen,
            icon,
            (visual.x + 46, visual.bottom - 42),
            34 if art else 96,
            color=(230, 226, 210),
            fallback=(loc["name"][:1] or "?"),
        )
        if art:
            label, district = type_label(loc), loc["district"].upper()
            caption_text = label if label == district else f"{label} • {district}"
            caption = get_font(10).render(caption_text, True, (200, 196, 180))
            self.screen.blit(caption, (visual.x + 70, visual.bottom - 48))
        self.search_visual = pygame.Rect(visual)
        if self.search:
            search_view.draw_overlay(self, visual)
        else:
            search_view.draw_start_button(self, visual)
        # редкое QTE: в баре можно нарваться на драку (раз в дело)
        if (
            loc["id"] == "bar"
            and not self.search
            and not self.state.fight_done
            and qte_view.chance_for(str(self.current_case.get("id", "")))
        ):
            brawl = pygame.Rect(visual.x + 12, visual.y + 12, 150, 26)
            hovered = brawl.collidepoint(mouse)
            pygame.draw.rect(
                self.screen, (56, 34, 34) if hovered else (24, 18, 22), brawl, border_radius=6
            )
            pygame.draw.rect(self.screen, (190, 90, 80), brawl, width=1, border_radius=6)
            label = get_font(10, bold=True).render("ЗАГЛЯНУТЬ В ЗАЛ", True, (220, 120, 110))
            self.screen.blit(label, label.get_rect(center=brawl.center))
            if brawl.collidepoint(mouse) and pressed and self._click_once():
                pygame.time.wait(120)
                qte_view.start(self)
        # описание
        desc_rect = pygame.Rect(main_rect.x + 15, visual.bottom + 15, 500, 100)
        draw_panel(self.screen, desc_rect, color=(22, 22, 30))
        draw_text_wrapped(
            self.screen,
            loc["desc"],
            get_font(13),
            COLOR_TEXT_DIM,
            pygame.Rect(desc_rect.x + 12, desc_rect.y + 8, desc_rect.w - 24, desc_rect.h - 16),
        )
        # справа — улики и персонажи
        right = pygame.Rect(
            main_rect.x + 530, main_rect.y + 15, main_rect.w - 545, main_rect.h - 30
        )
        # находим улики в этой локации (спрятанные появляются после обыска)
        clues_here = search_logic.visible_clues(self.current_case, loc["id"], self.state)
        chars_here = [ch for ch in self.current_case["characters"] if ch["location"] == loc["id"]]
        y = right.y
        self.location_clue_buttons = {}
        # заголовок улик
        clue_header = get_font(14, bold=True).render("УЛИКИ В ЛОКАЦИИ", True, COLOR_TEXT)
        self.screen.blit(clue_header, (right.x, y))
        y += 25
        if clues_here:
            for clue in clues_here:
                collected = clue["id"] in self.state.collected_clues
                rect = pygame.Rect(right.x, y, right.w, 70)
                col = (35, 35, 45) if collected else (28, 28, 36)
                border = COLOR_ACCENT if not collected else COLOR_BORDER
                pygame.draw.rect(self.screen, col, rect, border_radius=6)
                pygame.draw.rect(
                    self.screen, border, rect, width=2 if not collected else 1, border_radius=6
                )
                # иконка важности
                imp_col = COLOR_ACCENT if clue["importance"] == "high" else COLOR_BLUE
                pygame.draw.circle(self.screen, imp_col, (rect.x + 18, rect.y + 20), 6)
                title = get_font(13, bold=True).render(
                    clue["title"], True, COLOR_TEXT if not collected else COLOR_TEXT_DIM
                )
                self.screen.blit(title, (rect.x + 35, rect.y + 10))
                # описание обрезанное; справа оставляем место под кнопку «ИЗУЧИТЬ»
                desc = clue["desc"][:110] + "..." if len(clue["desc"]) > 110 else clue["desc"]
                draw_text_wrapped(
                    self.screen,
                    desc,
                    get_font(11),
                    COLOR_TEXT_DIM,
                    pygame.Rect(rect.x + 35, rect.y + 30, rect.w - 155, 34),
                )
                # кнопка: код → «КОД», замок → «ВЗЛОМАТЬ», иначе «ИЗУЧИТЬ»
                if not collected:
                    riddle_item = self.riddle_for(clue)
                    need_code = bool(riddle_item) and not riddle_logic.solved(
                        self.state, riddle_item
                    )
                    locked = bool(clue.get("puzzle"))
                    label = "КОД" if need_code else ("ВЗЛОМАТЬ" if locked else "ИЗУЧИТЬ")
                    btn = Button((rect.right - 100, rect.y + 12, 85, 28), label, accent=True)
                    btn.update(mouse, pressed)
                    btn.draw(self.screen, get_font(11, bold=True))
                    self.location_clue_buttons[clue["id"]] = pygame.Rect(btn.rect)
                    if need_code:
                        mark = get_font(9, bold=True).render("ЗАГАДКА", True, (210, 170, 90))
                        self.screen.blit(mark, (rect.right - 100, rect.y + 44))
                    if btn.clicked and self._click_once() and not self.search:
                        pygame.time.wait(120)
                        if need_code:
                            self.open_riddle(clue)
                        elif locked:
                            self.open_puzzle(clue)
                        else:
                            self.collect_clue(clue)
                else:
                    done = get_font(11).render("✓ ИЗУЧЕНО", True, COLOR_GREEN)
                    self.screen.blit(done, (rect.right - 90, rect.y + 18))
                y += 78
                if y > right.bottom - 80:
                    break
        else:
            empty = get_font(12).render(
                "В этой локации улик нет. Поговорите с персонажами.", True, COLOR_TEXT_DARK
            )
            self.screen.blit(empty, (right.x, y))
            y += 30
        # персонажи
        y += 15
        char_header = get_font(14, bold=True).render("ПЕРСОНАЖИ", True, COLOR_TEXT)
        self.screen.blit(char_header, (right.x, y))
        y += 25
        if chars_here:
            for ch in chars_here:
                rect = pygame.Rect(right.x, y, right.w, 70)
                draw_panel(self.screen, rect, color=(30, 30, 40))
                # портрет
                port = pygame.Rect(rect.x + 10, rect.y + 10, 50, 50)
                pygame.draw.rect(self.screen, ch["portrait_color"], port, border_radius=6)
                pygame.draw.rect(self.screen, COLOR_BORDER, port, width=1, border_radius=6)
                init = ch["name"][0]
                txt = get_font(20, bold=True).render(init, True, (255, 255, 255))
                self.screen.blit(txt, txt.get_rect(center=port.center))
                name = get_font(13, bold=True).render(ch["name"], True, COLOR_TEXT)
                self.screen.blit(name, (rect.x + 70, rect.y + 10))
                trust = dialogue.trust_of(self.state, ch["id"])
                role_x = rect.x + 70
                if trust:
                    role = get_font(11).render(ch["role"], True, COLOR_ACCENT)
                    self.screen.blit(role, (role_x, rect.y + 28))
                    chip_col = COLOR_GREEN if trust > 0 else (200, 100, 100)
                    chip_text = get_font(10, bold=True).render(
                        f"доверие {trust:+d}", True, chip_col
                    )
                    chip = pygame.Rect(0, 0, chip_text.get_width() + 14, 18)
                    chip.topleft = (role_x + role.get_width() + 10, rect.y + 27)
                    pygame.draw.rect(self.screen, (24, 26, 32), chip, border_radius=9)
                    pygame.draw.rect(self.screen, chip_col, chip, width=1, border_radius=9)
                    self.screen.blit(chip_text, (chip.x + 7, chip.y + 4))
                else:
                    role = get_font(11).render(ch["role"], True, COLOR_ACCENT)
                    self.screen.blit(role, (role_x, rect.y + 28))
                bio = get_font(10).render(ch["bio"][:50], True, COLOR_TEXT_DIM)
                self.screen.blit(bio, (rect.x + 70, rect.y + 45))
                # кнопка допроса: если человек не на месте — когда вернётся
                present = worldtime.character_present(ch, self.state.case_time_minutes)
                if not present:
                    away = get_font(10, bold=True).render("НЕ НА МЕСТЕ", True, COLOR_TEXT_DARK)
                    self.screen.blit(away, (rect.right - 110, rect.y + 18))
                    back = get_font(9).render(
                        worldtime.character_return(ch, self.state.case_time_minutes)[:30],
                        True,
                        COLOR_TEXT_DARK,
                    )
                    self.screen.blit(back, (rect.right - 110, rect.y + 34))
                btn = Button(
                    (rect.right - 110, rect.y + 20, 95, 30),
                    "ДОПРОСИТЬ",
                    enabled=present,
                )
                btn.update(mouse, pressed)
                btn.draw(self.screen, get_font(11, bold=True))
                if btn.clicked and not self.search and present:
                    pygame.time.wait(150)
                    if dialogue.is_silent(self.state, ch["id"]):
                        self.add_notification(
                            f"{ch['name']} не станет говорить до следующего дня"
                        )
                        self.audio.play_sfx("fail")
                        continue
                    self.dialogue_char = ch
                    self.dialogue_idx = 0
                    self.dialogue_penalized = False
                    self.screen_name = "dialogue"
                    self.state.interrogated.add(ch["id"])
                    self._dialogue_enter(ch)
                y += 78
        else:
            empty2 = get_font(12).render("Персонажей здесь нет.", True, COLOR_TEXT_DARK)
            self.screen.blit(empty2, (right.x, y))

    # ── интерактивный допрос ──────────────────────────────────────────────

    def _dialogue_enter(self, ch):
        """Открыть тему: отметить «уже спрашивали», оштрафовать за повтор, включить таймер."""
        topics = ch.get("dialogue", [])
        if self.dialogue_idx >= len(topics):
            self.dialogue_timer = 0.0
            return
        first = dialogue.mark_asked(self.state, ch["id"], self.dialogue_idx)
        if (
            not first
            and not self.dialogue_penalized
            and pressure.advanced(self.current_case)
        ):
            self.dialogue_penalized = True
            char_id = ch["id"]
            self.state.trust[char_id] = (
                dialogue.trust_of(self.state, char_id) - pressure.REPEAT_TOPIC_TRUST
            )
            self.add_notification(f"{ch['name']}: вы уже спрашивали об этом — доверие −1")
            save_game(self.state)
        topic = topics[self.dialogue_idx]
        if pressure.advanced(self.current_case) and dialogue.is_interactive(topic):
            self.dialogue_timer = pressure.DIALOGUE_SECONDS
        else:
            self.dialogue_timer = 0.0

    def _dialogue_timeout(self):
        """Игрок промолчал: тема закрыта, доверие −1."""
        ch = self.dialogue_char
        if not ch:
            return
        result = dialogue.decline(self.state, ch, self.dialogue_idx)
        self.dialogue_timer = 0.0
        if result.get("status") == "ok":
            self.add_notification(f"{ch['name']}: вы промолчали — доверие −1")
            self.audio.play_sfx("fail")
            save_game(self.state)

    def _dialogue_clue_lookup(self):
        case = self.current_case or {}
        return lambda clue_id: get_clue(case, clue_id)

    def _dialogue_choose(self, ch, opt_index):
        """Игрок выбрал реплику — эффекты, уведомления, сохранение."""
        topics = ch.get("dialogue", [])
        if self.dialogue_idx < len(topics) and dialogue.topic_locked(
            topics[self.dialogue_idx], self.state, self.current_case
        ):
            self.add_notification(dialogue.lock_hint(topics[self.dialogue_idx], self.current_case))
            return
        result = dialogue.choose(
            self.state, ch, self.dialogue_idx, opt_index, self._dialogue_clue_lookup()
        )
        if not result:
            return
        pygame.time.wait(120)
        if result["clue"]:
            self.add_notification(f"Улика: {result['clue']['title']}")
        delta = result["trust_delta"]
        if delta:
            word = "выросло" if delta > 0 else "упало"
            self.add_notification(f"{ch['name']}: доверие {word} ({delta:+d})")
        if result.get("silenced_until"):
            self.add_notification(f"{ch['name']} закрылся: до следующего дня говорить не станет")
        self.dialogue_timer = 0.0
        save_game(self.state)

    def _dialogue_expose(self, ch):
        """Уличить персонажа во лжи, предъявив противоречащую улику."""
        topics = ch.get("dialogue", [])
        if self.dialogue_idx >= len(topics):
            return
        result = dialogue.expose(
            self.state, ch, self.dialogue_idx, self._dialogue_clue_lookup()
        )
        status = result.get("status")
        if status == "ok":
            delta = int(result.get("trust_delta", 0) or 0)
            self.add_notification(f"{ch['name']} уличен во лжи")
            if delta:
                self.add_notification(f"{ch['name']}: доверие {delta:+d}")
            self.audio.play_sfx("success")
            save_game(self.state)
        elif status == "need_clue":
            self.add_notification("Нужна улика, которая противоречит его словам")
            self.audio.play_sfx("fail")
        elif status == "already":
            self.add_notification("Он уже признался — давить некуда")
        else:
            self.add_notification("В этих словах не за что зацепиться")
        pygame.time.wait(120)

    def _dialogue_next(self, ch):
        """Следующая тема — или итог допроса с бонусом за доверие."""
        topics = ch.get("dialogue", [])
        pygame.time.wait(100)
        if self.dialogue_idx + 1 < len(topics):
            self.dialogue_idx += 1
            self._dialogue_enter(ch)
            return
        self.dialogue_idx = len(topics)
        bonus = dialogue.finish(self.state, ch, self._dialogue_clue_lookup())
        if bonus:
            self.add_notification(f"{ch['name']}: {bonus['text']}")
            if bonus["clue"]:
                self.add_notification(f"Улика: {bonus['clue']['title']}")
        save_game(self.state)

    def _dialogue_event(self, event):
        """Клавиши допроса: 1–3 — реплика, пробел/Enter — далее, Esc — назад."""
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_ESCAPE:
            self.screen_name = "location"
            return True
        ch = self.dialogue_char
        if not ch:
            return False
        topics = ch.get("dialogue", [])
        if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.dialogue_idx >= len(topics):
                self.screen_name = "location"
                return True
            topic = topics[self.dialogue_idx]
            answered = dialogue.chosen_option(
                self.state, ch["id"], self.dialogue_idx, topic
            )
            if answered or not dialogue.is_interactive(topic):
                self._dialogue_next(ch)
            else:
                self.add_notification("Сначала выберите реплику — клавиши 1–3")
            return True
        if event.key == pygame.K_l and self.dialogue_idx < len(topics):
            self._dialogue_expose(ch)
            return True
        if pygame.K_1 <= event.key <= pygame.K_3 and self.dialogue_idx < len(topics):
            topic = topics[self.dialogue_idx]
            opts = dialogue.options(topic)
            index = event.key - pygame.K_1
            if index < len(opts) and dialogue.chosen(
                self.state, ch["id"], self.dialogue_idx
            ) is None:
                self._dialogue_choose(ch, index)
                return True
        return False

    def _dialogue_backdrop(self, ch):
        """Затемнённая иллюстрация места, где идёт разговор."""
        loc = get_location(self.current_case, ch.get("location", "")) if self.current_case else None
        if loc:
            art_name, art_tint = location_art(loc)
            backdrop = (
                cover_image(art_name, (WINDOW_WIDTH, WINDOW_HEIGHT), dim=0.62, tint=art_tint)
                if art_name
                else None
            )
            if backdrop:
                self.screen.blit(backdrop, (0, 0))
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

    def _dialogue_portrait(self, ch, rect):
        pygame.draw.rect(self.screen, ch["portrait_color"], rect, border_radius=10)
        art = cover_image(str(ch.get("portrait", "")), (rect.w, rect.h))
        init = ch["name"][0]
        if blit_rounded_image(self.screen, art, rect, radius=10):
            badge = pygame.Rect(rect.x + 6, rect.bottom - 28, 22, 22)
            pygame.draw.rect(self.screen, (12, 14, 20), badge, border_radius=5)
            pygame.draw.rect(self.screen, COLOR_ACCENT, badge, width=1, border_radius=5)
            txt = get_font(14, bold=True).render(init, True, (240, 232, 208))
            self.screen.blit(txt, txt.get_rect(center=badge.center))
        else:
            txt = get_font(36, bold=True).render(init, True, (255, 255, 255))
            self.screen.blit(txt, txt.get_rect(center=rect.center))
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, width=2, border_radius=10)

    def _dialogue_header(self, ch, panel):
        port = pygame.Rect(panel.x + 20, panel.y + 18, 96, 96)
        self._dialogue_portrait(ch, port)
        name = get_font(20, bold=True).render(ch["name"], True, COLOR_TEXT)
        self.screen.blit(name, (port.right + 16, panel.y + 24))
        role = get_font(12).render(ch["role"], True, COLOR_ACCENT)
        self.screen.blit(role, (port.right + 16, panel.y + 52))
        bio_text = ch["bio"]
        bio_font = get_font(11)
        limit = panel.right - 290 - (port.right + 16)
        while bio_text and bio_font.size(bio_text)[0] > limit:
            bio_text = bio_text[:-1]
        self.screen.blit(bio_font.render(bio_text, True, COLOR_TEXT_DIM), (port.right + 16, panel.y + 72))
        # шкала доверия
        trust = dialogue.trust_of(self.state, ch["id"])
        badge = pygame.Rect(panel.right - 240, panel.y + 22, 220, 56)
        draw_panel(self.screen, badge, color=(24, 26, 34), radius=8)
        label = get_font(10, bold=True).render("ДОВЕРИЕ", True, COLOR_TEXT_DIM)
        self.screen.blit(label, (badge.x + 14, badge.y + 8))
        filled = dialogue.trust_pips(trust)
        for i in range(5):
            cx = badge.x + 22 + i * 22
            cy = badge.y + 36
            color = COLOR_ACCENT if i < filled else (58, 58, 70)
            if trust < 0 and i < min(5, -trust):
                color = (190, 90, 90)
            pygame.draw.circle(self.screen, color, (cx, cy), 6)
            pygame.draw.circle(self.screen, (14, 14, 18), (cx, cy), 6, width=1)
        value_col = COLOR_GREEN if trust > 0 else ((200, 100, 100) if trust < 0 else COLOR_TEXT_DARK)
        value = get_font(15, bold=True).render(f"{trust:+d}" if trust else "0", True, value_col)
        self.screen.blit(value, value.get_rect(midright=(badge.right - 14, badge.centery + 4)))
        pygame.draw.line(
            self.screen, (40, 40, 50),
            (panel.x + 20, panel.y + 126), (panel.right - 20, panel.y + 126), 1,
        )

    def _dialogue_speech(self, rect, who, text, accent=False, text_color=None):
        """Плашка с репликой: имя говорящего и текст (с переносами)."""
        if accent:
            draw_panel(self.screen, rect, color=COLOR_ACCENT, border=COLOR_ACCENT, radius=8)
            color = (12, 12, 12)
        else:
            draw_panel(self.screen, rect, color=(28, 28, 36), border=(52, 52, 64), radius=8)
            color = text_color or COLOR_TEXT
        font = get_font(11, bold=True)
        self.screen.blit(font.render(who.upper(), True, color), (rect.x + 14, rect.y + 8))
        draw_text_wrapped(
            self.screen,
            text,
            get_font(13),
            color,
            pygame.Rect(rect.x + 14, rect.y + 26, rect.w - 28, rect.h - 32),
        )

    def _dialogue_option_rects(self, panel, count):
        return [
            pygame.Rect(panel.x + 22, panel.y + 264 + i * 62, panel.w - 44, 54)
            for i in range(count)
        ]

    def _dialogue_option_button(self, rect, number, option, hovered):
        bg = (46, 42, 26) if hovered else (30, 30, 38)
        border = COLOR_ACCENT if hovered else (58, 58, 72)
        draw_panel(self.screen, rect, color=bg, border=border, radius=8)
        badge = pygame.Rect(rect.x + 10, rect.y + 12, 30, 30)
        pygame.draw.rect(self.screen, COLOR_ACCENT if hovered else (44, 44, 56), badge, border_radius=6)
        num = get_font(15, bold=True).render(str(number), True, (14, 14, 18) if hovered else COLOR_TEXT)
        self.screen.blit(num, num.get_rect(center=badge.center))
        text_font = get_font(13)
        text = option["text"]
        while text and text_font.size(text)[0] > rect.w - 190:
            text = text[:-1]
        self.screen.blit(text_font.render(text, True, COLOR_TEXT), (badge.right + 12, rect.y + 10))
        if option.get("clue"):
            tag = get_font(9, bold=True).render("УЛИКА", True, (14, 14, 18))
            tag_rect = pygame.Rect(rect.x + 12 + 30 + 12, rect.y + 33, tag.get_width() + 12, 15)
            pygame.draw.rect(self.screen, (170, 190, 120), tag_rect, border_radius=4)
            self.screen.blit(tag, (tag_rect.x + 6, tag_rect.y + 2))
            tip = get_font(9).render("может дать улику", True, COLOR_TEXT_DARK)
            self.screen.blit(tip, (tag_rect.right + 8, tag_rect.y + 1))
        tone = option.get("tone")
        if tone:
            tone_col = {"мягко": COLOR_GREEN, "жёстко": (200, 110, 100)}.get(tone, COLOR_TEXT_DIM)
            tone_txt = get_font(10, bold=True).render(str(tone).upper(), True, tone_col)
            self.screen.blit(tone_txt, tone_txt.get_rect(midright=(rect.right - 16, rect.centery)))

    def _draw_dialogue_topic(self, ch, panel, topic):
        total = len(ch.get("dialogue", []))
        index = self.dialogue_idx
        label = get_font(10, bold=True).render(
            f"ТЕМА {index + 1} ИЗ {total}", True, COLOR_TEXT_DARK
        )
        self.screen.blit(label, (panel.x + 22, panel.y + 138))
        if self.dialogue_timer > 0:
            frac = max(0.0, min(1.0, self.dialogue_timer / max(0.1, pressure.DIALOGUE_SECONDS)))
            bar = pygame.Rect(panel.x + 150, panel.y + 140, 180, 10)
            pygame.draw.rect(self.screen, (40, 40, 50), bar, border_radius=5)
            col = COLOR_GREEN if frac > 0.4 else (COLOR_RED if frac < 0.2 else COLOR_ACCENT)
            fill = pygame.Rect(bar.x, bar.y, int(bar.w * frac), bar.h)
            pygame.draw.rect(self.screen, col, fill, border_radius=5)
            secs = get_font(10, bold=True).render(
                f"{max(0, int(self.dialogue_timer + 0.99))} c", True, col
            )
            self.screen.blit(secs, (bar.right + 8, panel.y + 137))
        opts = dialogue.options(topic)
        top = panel.y + 158
        if dialogue.topic_locked(topic, self.state, self.current_case):
            prompt = dialogue.prompt(topic) or topic.get("q", "")
            if prompt:
                self._dialogue_speech(
                    pygame.Rect(panel.x + 22, top, panel.w - 44, 78), ch["name"], prompt
                )
            block = pygame.Rect(panel.x + 22, top + 92, panel.w - 44, 96)
            draw_panel(self.screen, block, color=(32, 30, 24), border=COLOR_ACCENT, radius=8)
            self.screen.blit(
                get_font(13, bold=True).render("ТЕМА ПОКА ЗАКРЫТА", True, COLOR_ACCENT),
                (block.x + 16, block.y + 14),
            )
            draw_text_wrapped(
                self.screen,
                dialogue.lock_hint(topic, self.current_case),
                get_font(12),
                COLOR_TEXT_DIM,
                pygame.Rect(block.x + 16, block.y + 40, block.w - 32, 46),
            )
            return
        if opts:
            prompt = dialogue.prompt(topic)
            if prompt:
                self._dialogue_speech(
                    pygame.Rect(panel.x + 22, top, panel.w - 44, 78),
                    ch["name"],
                    prompt,
                )
            chosen = dialogue.chosen_option(self.state, ch["id"], index, topic)
            if dialogue.declined(self.state, ch["id"], index):
                note = get_font(11, bold=True).render(
                    "ВЫ ПРОМОЛЧАЛИ — доверие −1", True, COLOR_RED
                )
                self.screen.blit(note, (panel.x + 22, top + 82))
            if dialogue.lie_exposed(self.state, ch["id"], index):
                chip = pygame.Rect(panel.x + 22, top + 82, panel.w - 44, 20)
                pygame.draw.rect(self.screen, (58, 50, 30), chip, border_radius=6)
                pygame.draw.rect(self.screen, COLOR_ACCENT, chip, width=1, border_radius=6)
                text = dialogue.lie_reply(self.state, ch["id"], index)
                self.screen.blit(
                    get_font(10, bold=True).render(
                        f"УЛИЧЁН ВО ЛЖИ: {text[:120]}", True, COLOR_ACCENT
                    ),
                    (chip.x + 8, chip.y + 4),
                )
            if chosen is None:
                if dialogue.declined(self.state, ch["id"], index):
                    # время вышло: варианты больше не принимаются — только «ДАЛЕЕ»
                    closed = pygame.Rect(panel.x + 22, top + 118, panel.w - 44, 46)
                    draw_panel(self.screen, closed, color=(34, 24, 26), border=COLOR_RED, radius=8)
                    self.screen.blit(
                        get_font(12, bold=True).render(
                            "ТЕМА ЗАКРЫТА: вы промолчали. Нажмите «ДАЛЕЕ →».",
                            True,
                            COLOR_RED,
                        ),
                        (closed.x + 16, closed.y + 14),
                    )
                    return
                hint = get_font(11, bold=True).render(
                    "ВЫБЕРИТЕ, ЧТО СКАЗАТЬ (клик или 1–3):", True, COLOR_ACCENT
                )
                self.screen.blit(hint, (panel.x + 22, panel.y + 244))
                mouse = self._to_logical(pygame.mouse.get_pos())
                for i, option in enumerate(opts):
                    rect = self._dialogue_option_rects(panel, len(opts))[i]
                    hovered = rect.collidepoint(mouse)
                    self._dialogue_option_button(rect, i + 1, option, hovered)
                    if hovered and self._click_once():
                        self._dialogue_choose(ch, i)
                return
            self._dialogue_speech(
                pygame.Rect(panel.x + 22, top + 88, panel.w - 44, 54),
                self.state.detective.name,
                chosen["text"],
                accent=True,
            )
            self._dialogue_speech(
                pygame.Rect(panel.x + 22, top + 152, panel.w - 44, 124),
                ch["name"],
                chosen.get("reply", ""),
            )
            self._draw_dialogue_effects(ch, chosen, panel.y + 440)
            return
        # старая тема без выбора — просто вопрос и ответ
        self._dialogue_speech(
            pygame.Rect(panel.x + 22, top, panel.w - 44, 56),
            self.state.detective.name,
            topic.get("q", ""),
            accent=True,
        )
        self._dialogue_speech(
            pygame.Rect(panel.x + 22, top + 70, panel.w - 44, 130),
            ch["name"],
            topic.get("a", ""),
        )

    def _draw_dialogue_effects(self, ch, option, y):
        """Чипы эффектов выбранной реплики: доверие, улика, время."""
        x = 82
        delta = int(option.get("trust", 0) or 0)
        chips = []
        if delta:
            word = f"доверие {delta:+d}"
            chips.append((word, COLOR_GREEN if delta > 0 else (200, 100, 100)))
        if option.get("clue"):
            chips.append(("получена улика", COLOR_ACCENT))
        chips.append((f"время +{int(option.get('time', 10) or 10)} мин", COLOR_TEXT_DIM))
        font = get_font(10, bold=True)
        for text, color in chips:
            width = font.size(text)[0] + 20
            rect = pygame.Rect(x, y, width, 22)
            pygame.draw.rect(self.screen, (26, 26, 34), rect, border_radius=11)
            pygame.draw.rect(self.screen, color, rect, width=1, border_radius=11)
            self.screen.blit(font.render(text, True, color), (rect.x + 10, rect.y + 5))
            x += width + 10
        trust = dialogue.trust_of(self.state, ch["id"])
        bonus = dialogue.trust_bonus(ch)
        if bonus:
            need = dialogue.bonus_min(ch)
            tip = (
                f"Доверие {trust}/{need} — {ch['name']} уже готов говорить откровеннее."
                if trust >= need
                else f"Бонус откровенности — при доверии {need}. Сейчас {trust}."
            )
            self.screen.blit(
                get_font(10).render(tip, True, COLOR_TEXT_DARK), (x + 6, y + 6)
            )

    def _draw_dialogue_summary(self, ch, panel):
        topics = ch.get("dialogue", [])
        answered = sum(
            1
            for i, topic in enumerate(topics)
            if not dialogue.is_interactive(topic)
            or dialogue.chosen(self.state, ch["id"], i) is not None
        )
        trust = dialogue.trust_of(self.state, ch["id"])
        rect = pygame.Rect(panel.x + 22, panel.y + 158, panel.w - 44, 232)
        draw_panel(self.screen, rect, color=(26, 26, 34), radius=10)
        title = get_font(18, bold=True).render("ДОПРОС ОКОНЧЕН", True, COLOR_ACCENT)
        self.screen.blit(title, (rect.x + 20, rect.y + 18))
        info = get_font(12).render(
            f"Тем закрыто: {answered} из {len(topics)}  •  доверие: {trust:+d}"
            if trust
            else f"Тем закрыто: {answered} из {len(topics)}  •  доверие: 0",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(info, (rect.x + 20, rect.y + 46))
        bonus = dialogue.trust_bonus(ch)
        if bonus and ch["id"] in (self.state.trust_bonus_taken or set()):
            head = get_font(12, bold=True).render("ЗА ДОВЕРИЕ:", True, COLOR_GREEN)
            self.screen.blit(head, (rect.x + 20, rect.y + 84))
            draw_text_wrapped(
                self.screen,
                bonus["text"],
                get_font(13),
                (210, 220, 200),
                pygame.Rect(rect.x + 20, rect.y + 106, rect.w - 40, rect.h - 130),
            )
        elif bonus:
            need = dialogue.bonus_min(ch)
            tip_rect = pygame.Rect(rect.x + 20, rect.y + 84, rect.w - 40, 60)
            draw_panel(self.screen, tip_rect, color=(30, 30, 40), radius=8)
            draw_text_wrapped(
                self.screen,
                "Если бы вы были мягче, разговор дал бы больше: "
                f"для бонуса нужно доверие {need} (сейчас {trust}).",
                get_font(12),
                COLOR_TEXT_DIM,
                pygame.Rect(tip_rect.x + 12, tip_rect.y + 10, tip_rect.w - 24, tip_rect.h - 20),
            )
        else:
            hint = get_font(12).render(
                "Вы узнали всё, что он мог рассказать.", True, COLOR_TEXT_DIM
            )
            self.screen.blit(hint, (rect.x + 20, rect.y + 90))

    def _draw_dialogue_buttons(self, ch, panel, topics, font_btn):
        y = panel.bottom - 52
        mouse = self._to_logical(pygame.mouse.get_pos())
        back = Button((panel.x + 20, y, 120, 40), "← НАЗАД")
        back.update(mouse, pygame.mouse.get_pressed()[0])
        back.draw(self.screen, font_btn)
        if back.clicked and self._click_once():
            pygame.time.wait(120)
            self.screen_name = "location"
        finished = self.dialogue_idx >= len(topics)
        if finished:
            close = Button((panel.right - 210, y, 190, 40), "ЗАВЕРШИТЬ", accent=True)
            close.update(mouse, pygame.mouse.get_pressed()[0])
            close.draw(self.screen, font_btn)
            if close.clicked and self._click_once():
                pygame.time.wait(120)
                self.screen_name = "location"
        else:
            topic = topics[self.dialogue_idx]
            ready = (
                not dialogue.is_interactive(topic)
                or dialogue.chosen(self.state, ch["id"], self.dialogue_idx) is not None
            )
            if dialogue.lie(topic) and not dialogue.lie_exposed(
                self.state, ch["id"], self.dialogue_idx
            ):
                has_proof = dialogue.lie_evidence(self.state, topic) is not None
                lie_rect = pygame.Rect(panel.x + 150, y, 210, 40)
                lie_btn = Button(
                    lie_rect,
                    "УЛИЧИТЬ ВО ЛЖИ",
                    accent=has_proof,
                    enabled=has_proof,
                    tooltip=(
                        "Предъявить улику, которая противоречит его словам"
                        if has_proof
                        else "Нужна улика, которая противоречит его словам"
                    ),
                )
                lie_btn.update(mouse, pygame.mouse.get_pressed()[0])
                lie_btn.draw(self.screen, font_btn)
                self.dialogue_lie_rects["lie"] = lie_rect
                if lie_btn.clicked and self._click_once():
                    self._dialogue_expose(ch)
            rect = pygame.Rect(panel.right - 210, y, 190, 40)
            hovered = rect.collidepoint(mouse)
            if ready:
                nxt = Button(rect, "ДАЛЕЕ →", accent=True)
                nxt.update(mouse, pygame.mouse.get_pressed()[0])
                nxt.draw(self.screen, font_btn)
                if nxt.clicked and self._click_once():
                    self._dialogue_next(ch)
            else:
                pygame.draw.rect(self.screen, (44, 44, 54), rect, border_radius=6)
                pygame.draw.rect(self.screen, (60, 60, 74), rect, width=1, border_radius=6)
                label = font_btn.render("ДАЛЕЕ →", True, (110, 110, 124))
                self.screen.blit(label, label.get_rect(center=rect.center))
                if hovered and pygame.mouse.get_pressed()[0]:
                    self._click_once()
                    self.add_notification("Сначала выберите реплику")
        progress = get_font(11).render(
            f"{min(self.dialogue_idx + 1, len(topics))}/{len(topics)}",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(progress, progress.get_rect(center=(panel.centerx, y + 20)))

    def draw_dialogue(self):
        if not self.dialogue_char:
            self.screen_name = "location"
            return
        ch = self.dialogue_char
        font_btn = get_font(13, bold=True)
        self._dialogue_backdrop(ch)
        panel = pygame.Rect(60, 80, WINDOW_WIDTH - 120, WINDOW_HEIGHT - 160)
        draw_panel(self.screen, panel)
        self._dialogue_header(ch, panel)
        topics = ch.get("dialogue", [])
        if self.dialogue_idx < len(topics):
            self._draw_dialogue_topic(ch, panel, topics[self.dialogue_idx])
        else:
            self._draw_dialogue_summary(ch, panel)
        self._draw_dialogue_buttons(ch, panel, topics, font_btn)

    def draw_notebook(self):
        font_title = get_font(20, bold=True)
        header = pygame.Rect(20, 15, WINDOW_WIDTH - 40, 50)
        draw_panel(self.screen, header)
        t = font_title.render("БЛОКНОТ ДЕТЕКТИВА", True, COLOR_ACCENT)
        self.screen.blit(t, (header.x + 20, header.y + 12))
        res = get_font(11).render(
            f"★ репутация {self.state.reputation}   •   ${self.state.money}",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(res, (header.x + 20, header.y + 34))
        # вкладки
        tabs = [
            ("clues", "УЛИКИ"),
            ("suspects", "ДОСЬЕ"),
            ("board", "ВЕРСИИ"),
            ("notes", "ЗАМЕТКИ"),
        ]
        x = header.right - 460
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        for tab_id, label in tabs:
            rect = pygame.Rect(x, header.y + 10, 100, 30)
            is_active = self.notebook_tab == tab_id
            col = COLOR_ACCENT if is_active else COLOR_PANEL_LIGHT
            tcol = (10, 10, 10) if is_active else COLOR_TEXT
            pygame.draw.rect(self.screen, col, rect, border_radius=6)
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if is_active else COLOR_BORDER,
                rect,
                width=1,
                border_radius=6,
            )
            txt = get_font(12, bold=True).render(label, True, tcol)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            if rect.collidepoint(mouse) and pressed:
                pygame.time.wait(150)
                self.notebook_tab = tab_id
            x += 110
        btn_back = Button((header.x + 300, header.y + 10, 80, 30), "← НАЗАД")
        btn_back.update(mouse, pressed)
        btn_back.draw(self.screen, get_font(11, bold=True))
        if btn_back.clicked:
            pygame.time.wait(150)
            self.screen_name = "map"
        # контент
        main = pygame.Rect(20, 75, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 95)
        draw_panel(self.screen, main)
        if self.notebook_tab == "clues":
            self.draw_notebook_clues(main)
        elif self.notebook_tab == "suspects":
            self.draw_notebook_suspects(main)
        elif self.notebook_tab == "board":
            board_view.draw_board(self, main)
        else:
            self.draw_notebook_notes(main)

    def draw_notebook_clues(self, rect):
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        if not self.current_case:
            return
        font_small = get_font(12)
        court = len(expertise.court_clues(self.current_case, self.state))
        title = get_font(14, bold=True).render(
            f"СОБРАНО УЛИК: {len(self.state.collected_clues)}/{len(self.current_case['clues'])}",
            True,
            COLOR_TEXT,
        )
        self.screen.blit(title, (rect.x + 20, rect.y + 15))
        if pressure.advanced(self.current_case):
            court_txt = get_font(11, bold=True).render(
                f"суд примет: {court}", True, COLOR_GREEN if court else COLOR_TEXT_DIM
            )
            self.screen.blit(court_txt, (rect.x + 320, rect.y + 18))
            lab = get_font(10).render(
                f"лаборатория: {pressure.LAB_COST} $ и {pressure.LAB_MINUTES} мин, "
                f"репутация {pressure.LAB_REPUTATION}+",
                True,
                COLOR_TEXT_DIM,
            )
            self.screen.blit(lab, (rect.right - lab.get_width() - 20, rect.y + 18))

        clues = self.current_case["clues"]
        # при большом деле строки сжимаются, иначе последние улики не помещаются
        step = max(40, min(78, (rect.h - 70) // max(1, len(clues))))
        row_h = step - 6
        compact = row_h < 62
        y = rect.y + 45
        for clue in clues:
            collected = clue["id"] in self.state.collected_clues
            r = pygame.Rect(rect.x + 20, y, rect.w - 40, row_h)
            if r.bottom > rect.bottom - 14:
                break
            exposed_fake = clue["id"] in (self.state.fake_clues or set())
            col = (35, 35, 50) if collected else ((38, 24, 26) if exposed_fake else (25, 25, 30))
            pygame.draw.rect(self.screen, col, r, border_radius=6)
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if collected else (COLOR_RED if exposed_fake else COLOR_BORDER),
                r,
                width=1,
                border_radius=6,
            )
            status_col = COLOR_GREEN if collected else (COLOR_RED if exposed_fake else COLOR_TEXT_DARK)
            st = get_font(14 if compact else 16, bold=True).render(
                "✓" if collected else ("✗" if exposed_fake else "?"), True, status_col
            )
            self.screen.blit(st, (r.x + 12, r.y + (row_h - st.get_height()) // 2))
            name = get_font(12 if compact else 13, bold=True).render(
                clue["title"] if collected else "???",
                True,
                COLOR_TEXT if collected else COLOR_TEXT_DARK,
            )
            self.screen.blit(name, (r.x + 40, r.y + 6))
            if not collected:
                if exposed_fake:
                    fake_title = get_font(12 if compact else 13, bold=True).render(
                        f"{clue['title']} — ПОДБРОШЕНО", True, COLOR_RED
                    )
                    self.screen.blit(fake_title, (r.x + 40, r.y + 6))
                    hint = get_font(10).render(
                        "(экспертиза доказала подделку — улика изъята из блокнота)",
                        True,
                        COLOR_TEXT_DIM,
                    )
                    self.screen.blit(hint, (r.x + 40, r.y + (26 if compact else 32)))
                else:
                    hint = get_font(10).render(
                        "(найдите в локациях — ищите значок лупы)", True, COLOR_TEXT_DARK
                    )
                    self.screen.blit(hint, (r.x + 40, r.y + (26 if compact else 32)))
                y += step
                continue

            loc = get_location(self.current_case, clue["location"])
            loc_name = loc["name"] if loc else clue["location"]
            desc_w = r.w - 420
            desc = font_small if not compact else get_font(10)
            desc_line = clue["desc"][: (110 if compact else 90)]
            self.screen.blit(
                desc.render(desc_line, True, COLOR_TEXT_DIM), (r.x + 40, r.y + (24 if compact else 32))
            )
            if not compact:
                self.screen.blit(
                    get_font(10).render(loc_name, True, COLOR_ACCENT), (r.x + 40, r.y + 50)
                )
            status = expertise.status(self.current_case, self.state, clue)
            label = expertise.status_label(self.current_case, self.state, clue)
            if label:
                col = {
                    "confirmed": COLOR_GREEN,
                    "fake": COLOR_RED,
                    "hearsay": COLOR_ACCENT,
                }.get(status, COLOR_TEXT_DIM)
                chip_txt = get_font(10, bold=True).render(label, True, col)
                chip = pygame.Rect(
                    r.right - chip_txt.get_width() - 202,
                    r.y + (6 if compact else 10),
                    chip_txt.get_width() + 12,
                    18,
                )
                pygame.draw.rect(self.screen, (26, 26, 34), chip, border_radius=8)
                pygame.draw.rect(self.screen, col, chip, width=1, border_radius=8)
                self.screen.blit(chip_txt, (chip.x + 6, chip.y + 3))
            if (
                pressure.advanced(self.current_case)
                and expertise.needs_check(self.current_case, clue)
                and status == "hearsay"
            ):
                afford = pressure.lab_ready(self.state)
                btn_rect = pygame.Rect(r.right - 190, r.bottom - (40 if compact else 40), 170, 26)
                if compact:
                    btn_rect.y = r.y + (row_h - 22) // 2
                    btn_rect.h = 22
                hovered = btn_rect.collidepoint(mouse)
                pygame.draw.rect(
                    self.screen,
                    (56, 48, 30) if hovered and afford else (28, 28, 36),
                    btn_rect,
                    border_radius=6,
                )
                pygame.draw.rect(
                    self.screen,
                    COLOR_ACCENT if afford else (70, 70, 80),
                    btn_rect,
                    width=1,
                    border_radius=6,
                )
                lab_label = get_font(10, bold=True).render(
                    f"ЭКСПЕРТИЗА ${pressure.LAB_COST}",
                    True,
                    COLOR_ACCENT if afford else COLOR_TEXT_DARK,
                )
                self.screen.blit(lab_label, lab_label.get_rect(center=btn_rect.center))
                self.expertise_rects[clue["id"]] = btn_rect
                if btn_rect.collidepoint(mouse) and pressed and self._click_once():
                    result = expertise.submit(self.state, self.current_case, clue)
                    self._handle_expertise(result)
                    pygame.time.wait(120)
            y += step

    def _handle_expertise(self, result):
        """Уведомления по итогам экспертизы улики."""
        status = result.get("status")
        if status == "ok":
            text = result.get("text", "Экспертиза готова")
            self.add_notification(text)
            self.audio.play_sfx("fail" if result.get("fake") else "success")
            save_game(self.state)
            return
        if status == "no_money":
            self.add_notification(f"Лаборатория берёт ${result.get('need', pressure.LAB_COST)}")
        elif status == "no_rep":
            self.add_notification(
                f"В лаборатории не хотят связываться: нужна репутация {result.get('need')}"
            )
        elif status == "already":
            self.add_notification("Экспертиза по этой улике уже была")
        else:
            self.add_notification("Эту улику экспертиза не требуется")
        self.audio.play_sfx("tick")

    def draw_notebook_suspects(self, rect):
        if not self.current_case:
            return
        title = get_font(14, bold=True).render("ПОДОЗРЕВАЕМЫЕ", True, COLOR_TEXT)
        self.screen.blit(title, (rect.x + 20, rect.y + 15))
        hint = get_font(11).render(
            "Изучите мотивы и улики против каждого. Выберите одного на экране обвинения.",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(hint, (rect.x + 20, rect.y + 35))
        y = rect.y + 65
        for sus in self.current_case.get("suspects", []):
            r = pygame.Rect(rect.x + 20, y, rect.w - 40, 90)
            if r.bottom > rect.bottom - 20:
                break
            is_culprit = sus.get("is_culprit")
            col = (32, 32, 42)
            pygame.draw.rect(self.screen, col, r, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_BORDER, r, width=1, border_radius=8)
            name = get_font(14, bold=True).render(sus["name"], True, COLOR_TEXT)
            self.screen.blit(name, (r.x + 15, r.y + 12))
            motive = get_font(11).render("Мотив: " + sus["motive"], True, COLOR_ACCENT)
            self.screen.blit(motive, (r.x + 15, r.y + 32))
            ev = ", ".join(sus.get("evidence", [])[:3])
            ev_txt = get_font(10).render(
                f"Улики: {ev if ev else 'нет прямых улик'}", True, COLOR_TEXT_DIM
            )
            self.screen.blit(ev_txt, (r.x + 15, r.y + 50))
            # сколько улик собрано против него
            collected_against = len(
                [e for e in sus.get("evidence", []) if e in self.state.collected_clues]
            )
            total = len(sus.get("evidence", []))
            prog = f"{collected_against}/{total} улик собрано"
            prog_col = COLOR_GREEN if collected_against == total and total > 0 else COLOR_TEXT_DIM
            prog_txt = get_font(11, bold=True).render(prog, True, prog_col)
            self.screen.blit(prog_txt, (r.right - 150, r.y + 15))
            y += 100

    def draw_notebook_notes(self, rect):
        title = get_font(14, bold=True).render("ЗАМЕТКИ ДЕТЕКТИВА", True, COLOR_TEXT)
        self.screen.blit(title, (rect.x + 20, rect.y + 15))
        # timeline
        y = rect.y + 45
        events = [
            f"Дело начато: {self.current_case['title'] if self.current_case else ''}",
        ]
        for clue_id in self.state.collected_clues:
            clue = get_clue(self.current_case, clue_id) if self.current_case else None
            if clue:
                events.append(f"[{clue['location']}] {clue['title']}: {clue['desc'][:60]}")
        for loc_id in self.state.visited_locations:
            loc = get_location(self.current_case, loc_id) if self.current_case else None
            if loc and loc_id != "office":
                events.append(f"Посещено: {loc['name']}")
        if not events:
            empty = get_font(12).render(
                "Пока пусто. Хронология появится по мере расследования.", True, COLOR_TEXT_DARK
            )
            self.screen.blit(empty, (rect.x + 20, y))
            return
        for ev in events[-12:]:
            if y > rect.bottom - 30:
                break
            pygame.draw.circle(self.screen, COLOR_ACCENT, (rect.x + 25, y + 6), 4)
            txt = get_font(11).render(ev[:110], True, COLOR_TEXT_DIM)
            self.screen.blit(txt, (rect.x + 40, y))
            y += 20

    def draw_accusation(self):
        if not self.current_case:
            return
        font_title = get_font(26, bold=True)
        header = pygame.Rect(20, 15, WINDOW_WIDTH - 40, 50)
        draw_panel(self.screen, header)
        t = font_title.render("КТО ВИНОВАТ?", True, COLOR_RED)
        self.screen.blit(t, t.get_rect(center=(header.centerx, header.centery)))
        # панель
        main = pygame.Rect(20, 75, WINDOW_WIDTH - 40, WINDOW_HEIGHT - 95)
        draw_panel(self.screen, main)
        instr = get_font(13).render(
            "Выберите подозреваемого. Будьте внимательны — ошибка стоит жизни.",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(instr, (main.x + 20, main.y + 15))
        # сколько улик есть и сколько рекомендуется
        have = ending_logic.clue_count(self.state, self.current_case)
        collected = len(self.state.collected_clues)
        need = ending_logic.required_clues(self.current_case)
        total_clues = len(self.current_case.get("clues", []))
        if have >= need:
            clue_line = f"Улик: {have} из {total_clues} — доказательств достаточно"
            if collected > have:
                clue_line += f" · собрано {collected}, но суд примет {have}"
            clue_col = COLOR_GREEN
        else:
            clue_line = (
                f"Улик: {have} из {total_clues} — рекомендуется {need}: "
                "с малым числом улик дело может развалиться в суде"
            )
            clue_col = COLOR_ACCENT
        self.screen.blit(
            get_font(12, bold=have >= need).render(clue_line, True, clue_col),
            (main.x + 20, main.y + 34),
        )
        if self.state.warrant:
            chip = get_font(11, bold=True).render("ОРДЕР НА РУКАХ", True, COLOR_GREEN)
            rect = pygame.Rect(main.right - chip.get_width() - 34, main.y + 32, chip.get_width() + 20, 20)
            pygame.draw.rect(self.screen, (26, 42, 30), rect, border_radius=9)
            pygame.draw.rect(self.screen, COLOR_GREEN, rect, width=1, border_radius=9)
            self.screen.blit(chip, (rect.x + 10, rect.y + 4))
        # подозреваемые карточки
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        y = main.y + 62
        for sus in self.current_case.get("suspects", []):
            selected = self.accusation_selected == sus["id"]
            r = pygame.Rect(main.x + 20, y, main.w - 40, 96)
            col = COLOR_ACCENT if selected else (30, 30, 40)
            tcol = (10, 10, 10) if selected else COLOR_TEXT
            pygame.draw.rect(self.screen, col, r, border_radius=8)
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if selected else COLOR_BORDER,
                r,
                width=2 if selected else 1,
                border_radius=8,
            )
            name = get_font(16, bold=True).render(sus["name"], True, tcol)
            self.screen.blit(name, (r.x + 20, r.y + 12))
            motive = get_font(11).render(
                sus["motive"], True, (10, 10, 10) if selected else COLOR_TEXT_DIM
            )
            self.screen.blit(motive, (r.x + 20, r.y + 36))
            # доказательства: сколько улик по этому подозреваемому уже на руках
            evidence = list(sus.get("evidence") or [])
            found = sum(1 for clue_id in evidence if clue_id in self.state.collected_clues)
            if evidence:
                ev_text = f"доказательства: {found}/{len(evidence)}"
                ev_col = (60, 90, 60) if found >= len(evidence) else (90, 70, 40)
            else:
                ev_text = "доказательств нет"
                ev_col = (110, 70, 70)
            if selected:
                ev_col = (40, 40, 30)
            self.screen.blit(
                get_font(10, bold=True).render(ev_text.upper(), True, ev_col),
                (r.x + 20, r.y + 58),
            )
            if board_logic.conclusion_for(self.current_case, self.state, sus):
                tag = get_font(9, bold=True).render("ВЕРСИЯ СОБРАНА", True, COLOR_GREEN)
                self.screen.blit(tag, (r.right - tag.get_width() - 60, r.bottom - 18))
            # кликабельность — один выбор на нажатие
            if r.collidepoint(mouse) and pressed and self._click_once():
                if self.accusation_selected != sus["id"]:
                    # ответы суда относятся к конкретному подозреваемому
                    self.state.trial_motive = None
                    self.state.trial_method = None
                self.accusation_selected = sus["id"]
            # галочка
            if selected:
                chk = get_font(20, bold=True).render("✓", True, (10, 10, 10))
                self.screen.blit(chk, (r.right - 40, r.y + 20))
            y += 102
        # ── суд: мотив и способ ──────────────────────────────────
        self.trial_rects = {"motive": {}, "method": {}}
        if trial.available(self.current_case) and self.accusation_selected:
            rows = [
                (trial.MOTIVE, "МОТИВ", trial.motives(self.current_case)),
                (trial.METHOD, "СПОСОБ", trial.methods(self.current_case)),
            ]
            row_y = main.bottom - 156
            for kind, label, items in rows:
                head = get_font(11, bold=True).render(label, True, COLOR_ACCENT)
                self.screen.blit(head, (main.x + 20, row_y + 5))
                x = main.x + 110
                for item in items:
                    text = item["text"]
                    if len(text) > 46:
                        text = text[:45].rsplit(" ", 1)[0] + "…"
                    chip_label = get_font(10, bold=True).render(text, True, COLOR_TEXT)
                    chip = pygame.Rect(x, row_y, chip_label.get_width() + 18, 24)
                    if chip.right > main.right - 24:
                        break
                    active = trial.selected(self.state, kind) == item["id"]
                    hovered = chip.collidepoint(mouse)
                    pygame.draw.rect(
                        self.screen,
                        (56, 48, 30) if active else ((34, 34, 44) if hovered else (26, 26, 34)),
                        chip,
                        border_radius=6,
                    )
                    pygame.draw.rect(
                        self.screen,
                        COLOR_ACCENT if active else COLOR_BORDER,
                        chip,
                        width=2 if active else 1,
                        border_radius=6,
                    )
                    self.screen.blit(chip_label, (chip.x + 9, chip.y + 6))
                    self.trial_rects[kind][item["id"]] = chip
                    if chip.collidepoint(mouse) and pressed and self._click_once():
                        trial.select_from(self.current_case, self.state, kind, item["id"])
                        self.audio.play_sfx("tick")
                        save_game(self.state)
                    x = chip.right + 8
                row_y += 30
            if not trial.ready(self.current_case, self.state):
                wait_txt = get_font(10).render(
                    "Прокурор ждёт мотив и способ — без них обвинение не примут",
                    True,
                    COLOR_TEXT_DIM,
                )
                self.screen.blit(wait_txt, (main.x + 20, row_y + 4))
        # кнопки
        btn_back = Button((main.x + 20, main.bottom - 50, 160, 40), "← ОТМЕНА")
        can_confirm = self.accusation_selected is not None and trial.ready(
            self.current_case, self.state
        )
        btn_confirm = Button(
            (main.right - 200, main.bottom - 50, 180, 40),
            "ОБВИНИТЬ!",
            accent=True,
            enabled=can_confirm,
        )
        btn_timeline = Button(
            (main.x + 200, main.bottom - 50, 170, 40),
            "ХРОНОЛОГИЯ",
            enabled=timeline.available(self.current_case),
            tooltip="Восстановить порядок событий — ранг финала будет выше",
        )
        btn_warrant = Button(
            (main.x + 390, main.bottom - 50, 200, 40),
            "ОРДЕР ЗА $200",
            enabled=self.state.money >= 200 and not self.state.warrant,
            tooltip="Купить ордер: обвинение откроется даже без улик",
        )
        btn_bluff = Button(
            (main.x + 610, main.bottom - 50, 210, 40),
            "БЛЕФ (−2 РЕПУТ.)",
            enabled=self.state.reputation >= 2 and not self.state.warrant,
            tooltip="Надавить репутацией вместо денег",
        )
        for btn, act in [
            (btn_back, "back"),
            (btn_confirm, "confirm"),
            (btn_timeline, "timeline"),
            (btn_warrant, "warrant"),
            (btn_bluff, "bluff"),
        ]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(13, bold=True))
            if btn.clicked and self._click_once():
                pygame.time.wait(150)
                if act == "back":
                    self.screen_name = "map"
                elif act == "confirm":
                    if not trial.ready(self.current_case, self.state):
                        self.add_notification("Суд ждёт мотив и способ — выберите их под карточками")
                        self.audio.play_sfx("tick")
                    else:
                        self._finish_case()
                elif act == "timeline":
                    self.timeline_return = "accusation"
                    self.timeline_selected = None
                    self.timeline_message = ""
                    self.screen_name = "timeline"
                elif act == "warrant":
                    self.state.money -= 200
                    self.state.warrant = True
                    self.add_notification("Ордер куплен: $200")
                    save_game(self.state)
                elif act == "bluff":
                    self.state.reputation -= 2
                    self.state.warrant = True
                    self.add_notification("Ордер выбит блефом: −2 репутации")
                    save_game(self.state)
        # подсказка, если доказательств по выбранному мало
        if self.accusation_selected:
            sus = ending_logic.suspect_of(self.current_case, self.accusation_selected) or {}
            evidence = list(sus.get("evidence") or [])
            missing = [cid for cid in evidence if cid not in self.state.collected_clues]
            if missing and have >= need:
                warn = get_font(11).render(
                    "По этому подозреваемому не хватает части доказательств — суд может не согласиться.",
                    True,
                    COLOR_ACCENT,
                )
                self.screen.blit(warn, (main.x + 20, main.bottom - 76))

    def _finish_case(self):
        """Обвинение предъявлено: финал, запись концовки в коллекцию."""
        suspect = ending_logic.suspect_of(self.current_case, self.accusation_selected)
        self.state.accusation_result = self.accusation_selected
        self.state.accusation_correct = bool(suspect and suspect.get("is_culprit"))
        self.state.case_state = "finished"
        resolution = ending_logic.resolve(self.current_case, self.state)
        case_id = str(self.current_case.get("id", ""))
        # без обвинения (срок вышел) концовку в коллекцию не пишем:
        # такого финала нет в списке дела, иначе счётчик «N из M» ломается
        if self.state.accusation_result:
            known = ending_logic.ending_key(case_id, resolution) in ending_logic.unlocked_for(
                self.state, case_id
            )
            ending_logic.record(self.state, case_id, resolution)
        else:
            known = True
        if resolution.get("success"):
            self.state.completed_cases.add(case_id)
        self._ending_is_new = not known
        save_game(self.state)
        self.screen_name = "ending"

    def draw_ending(self):
        if not self.current_case:
            return
        resolution = ending_logic.resolve(self.current_case, self.state)
        success = bool(resolution["success"])
        title = resolution["title"]
        text = resolution["text"]
        rank = resolution["rank"]
        label = resolution["label"]
        # фон
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.fill((10, 10, 14) if success else (20, 10, 10))
        self.screen.blit(overlay, (0, 0))
        # панель
        panel = pygame.Rect(WINDOW_WIDTH // 2 - 380, WINDOW_HEIGHT // 2 - 270, 760, 540)
        draw_panel(self.screen, panel)
        # ранг
        rank_font = get_font(52, bold=True)
        rank_col = COLOR_GREEN if success else COLOR_RED
        rank_surf = rank_font.render(f"РАНГ {rank}", True, rank_col)
        self.screen.blit(rank_surf, rank_surf.get_rect(center=(panel.centerx, panel.y + 46)))
        result_text = "ДЕЛО РАСКРЫТО" if success else "ДЕЛО ПРОВАЛЕНО"
        res = get_font(26, bold=True).render(result_text, True, rank_col)
        self.screen.blit(res, res.get_rect(center=(panel.centerx, panel.y + 92)))
        # метка концовки и пометки суда: рисуем группой по центру,
        # иначе при нескольких чипах ряд уезжает за панель
        chip_font = get_font(10, bold=True)
        chips = [(label.upper(), (240, 232, 208), (34, 34, 44), rank_col, 11)]
        if resolution.get("timeline_bonus"):
            chips.append(
                ("ХРОНОЛОГИЯ ВОССТАНОВЛЕНА", COLOR_ACCENT, (34, 30, 22), COLOR_ACCENT, 7)
            )
        trial_info = resolution.get("trial") or {}
        if trial_info.get("asked") and trial_info.get("answered"):
            if trial_info.get("score") == 2:
                note = ("МОТИВ И СПОСОБ ДОКАЗАНЫ", COLOR_GREEN, (26, 34, 28), COLOR_GREEN, 7)
            elif trial_info.get("score") == 0:
                note = ("МОТИВ И СПОСОБ НЕ ДОКАЗАНЫ", COLOR_RED, (34, 22, 24), COLOR_RED, 7)
            else:
                note = ("СУД ПРИНЯЛ ЧАСТЬ ВЕРСИИ", COLOR_ACCENT, (34, 30, 22), COLOR_ACCENT, 7)
            chips.append(note)
        if resolution.get("late"):
            chips.append(("СРОК ВЫШЕЛ", COLOR_RED, (36, 22, 22), COLOR_RED, 7))
        if getattr(self, "_ending_is_new", False):
            chips.append(("НОВАЯ", (12, 12, 12), COLOR_ACCENT, COLOR_ACCENT, 9))
        widths = [
            get_font(9 if pad <= 9 else 10, bold=True).size(chip_label)[0] + pad * 2
            for chip_label, _col, _bg, _border, pad in chips
        ]
        total_w = sum(widths) + 6 * (len(chips) - 1)
        cx = panel.centerx - total_w // 2
        chip_y = panel.y + 108
        for (chip_label, chip_col, chip_bg, chip_border, pad), width in zip(
            chips, widths, strict=True
        ):
            rect = pygame.Rect(cx, chip_y, width, 20)
            pygame.draw.rect(self.screen, chip_bg, rect, border_radius=10)
            pygame.draw.rect(self.screen, chip_border, rect, width=1, border_radius=10)
            surf = get_font(9 if pad <= 9 else 10, bold=True).render(
                chip_label, True, chip_col
            )
            self.screen.blit(surf, surf.get_rect(center=rect.center))
            cx = rect.right + 6
        tit = get_font(18, bold=True).render(title, True, COLOR_TEXT)
        self.screen.blit(tit, tit.get_rect(center=(panel.centerx, panel.y + 146)))
        # текст финала
        text_rect = pygame.Rect(panel.x + 30, panel.y + 166, panel.w - 60, 220)
        draw_panel(self.screen, text_rect, color=(22, 22, 30))
        draw_text_wrapped(
            self.screen,
            text,
            get_font(14),
            COLOR_TEXT,
            pygame.Rect(text_rect.x + 15, text_rect.y + 15, text_rect.w - 30, text_rect.h - 30),
        )
        # статистика
        case = self.current_case
        total_clues = len(case.get("clues", []))
        need = ending_logic.required_clues(case)
        trust = sum(
            int(self.state.trust.get(ch.get("id", ""), 0)) for ch in case.get("characters", [])
        )
        bonuses = sum(
            1 for ch in case.get("characters", []) if ch.get("id") in self.state.trust_bonus_taken
        )
        stats = get_font(12).render(
            f"Улик: {len(self.state.collected_clues)}/{total_clues} (рекомендовано {need}) • "
            f"Время: {self.state.case_time_minutes} мин • Доверие: {trust:+d} • Бонусов: {bonuses}",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(stats, stats.get_rect(center=(panel.centerx, panel.y + 402)))
        opened, total_endings = ending_logic.progress(self.state, case)
        prog_col = COLOR_ACCENT if opened < total_endings else COLOR_GREEN
        prog = get_font(12, bold=True).render(
            f"Открыто концовок: {opened} из {total_endings}", True, prog_col
        )
        self.screen.blit(prog, prog.get_rect(center=(panel.centerx, panel.y + 424)))
        hint = get_font(10).render(
            "Другие реплики, доверие и число улик открывают другие финалы.",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.y + 444)))
        # кнопки: после успеха добавляем переход к следующему делу
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        btn_y = panel.bottom - 50
        nxt = self.next_case() if success else None
        if nxt:
            width, gap = 208, 22
            x0 = panel.centerx - (width * 3 + gap * 2) // 2
            rects = {
                "menu": pygame.Rect(x0, btn_y, width, 40),
                "next": pygame.Rect(x0 + width + gap, btn_y, width, 40),
                "replay": pygame.Rect(x0 + 2 * (width + gap), btn_y, width, 40),
            }
            line = get_font(11, bold=True).render(
                f"Дальше по порядку: «{nxt.get('title', '')}»", True, COLOR_ACCENT
            )
            self.screen.blit(line, line.get_rect(center=(panel.centerx, panel.bottom - 74)))
        else:
            rects = {
                "menu": pygame.Rect(panel.x + 40, btn_y, 200, 40),
                "replay": pygame.Rect(panel.centerx + 20, btn_y, 200, 40),
            }
            if success:
                line = get_font(11, bold=True).render(
                    "Все дела сезона закрыты — спасибо, детектив", True, COLOR_GREEN
                )
                self.screen.blit(line, line.get_rect(center=(panel.centerx, panel.bottom - 74)))
        self.ending_rects = dict(rects)
        buttons = [
            ("menu", "В МЕНЮ", False),
            ("next", "СЛЕДУЮЩЕЕ ДЕЛО →", True),
            ("replay", "СЫГРАТЬ ЕЩЁ", not nxt),
        ]
        for key, label, accent in buttons:
            rect = rects.get(key)
            if rect is None:
                continue
            btn = Button(rect, label, accent=accent)
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(13, bold=True))
            if btn.clicked and self._click_once():
                self._ending_action(key)

    def _ending_action(self, action: str):
        """Действия кнопок финального экрана (общие для клика и тестов)."""
        pygame.time.wait(150)
        if action == "menu":
            self.screen_name = "menu"
        elif action == "replay":
            if self.current_case:
                # переигровка того же дела — с чистым кошельком и репутацией,
                # иначе финал получал S+ за заслуги прошлого захода
                self.start_case(self.current_case["id"], new_run=True)
                self.screen_name = "map"
        elif action == "next" and not self.start_next_case():
            self.screen_name = "case_select"

    def draw_settings(self):
        # Новые настройки экрана — разрешения, монитор, режим окна + звуки + обновления
        import pygame

        from .ui.widgets import (
            Button,
            Dropdown,
            Slider,
            Toggle,
            draw_panel,
            draw_progress_bar,
            get_font,
        )

        font_title = get_font(24, bold=True)
        font_sec = get_font(12, bold=True)
        font_small = get_font(11)
        # Логический размер (1280×720) — как и весь остальной рендер
        W, H = self.LOGICAL_W, self.LOGICAL_H
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        layout = settings_layout(W, H)
        header = layout.header
        draw_panel(self.screen, header)
        # Кнопка НАЗАД в шапке - всегда видна
        btn_back_top = Button(layout.back, "← НАЗАД", style="secondary")
        btn_back_top.update(mouse, pressed)
        btn_back_top.draw(self.screen, get_font(11, bold=True))
        if btn_back_top.clicked:
            self.screen_name = "menu"
        t = font_title.render("НАСТРОЙКИ  —  Экран и звук", True, COLOR_ACCENT)
        self.screen.blit(t, t.get_rect(center=(W // 2, header.centery)))
        # Подзаголовок версии
        ver = get_font(10).render(
            f"v{__import__('detective_game').__version__}  •  {GITHUB_RELEASES_URL}",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(ver, ver.get_rect(center=(W // 2, header.centery + 16)))

        # Левая панель — экран
        left = layout.left
        draw_panel(self.screen, left)
        pygame.draw.rect(self.screen, (212, 175, 55, 40), left, width=1, border_radius=8)
        sec_title = font_sec.render("◆  ЭКРАН", True, COLOR_ACCENT)
        self.screen.blit(sec_title, (left.x + 20, left.y + 14))
        pygame.draw.line(
            self.screen, COLOR_BORDER, (left.x + 15, left.y + 36), (left.right - 15, left.y + 36), 1
        )

        # Правая панель — звук и обновления
        right = layout.right
        draw_panel(self.screen, right)
        sec_title2 = font_sec.render("◆  ЗВУК И ОБНОВЛЕНИЯ", True, COLOR_ACCENT)
        self.screen.blit(sec_title2, (right.x + 20, right.y + 14))
        pygame.draw.line(
            self.screen,
            COLOR_BORDER,
            (right.x + 15, right.y + 36),
            (right.right - 15, right.y + 36),
            1,
        )

        # --- ЛЕВАЯ: Разрешение ---
        y = left.y + 50
        # Подписи
        lbl_res = get_font(11, bold=True).render("РАЗРЕШЕНИЕ ЭКРАНА", True, COLOR_TEXT)
        self.screen.blit(lbl_res, (left.x + 20, y))
        y += 18
        # Обновляем rect дропдаунов под текущую панель
        self.resolution_dropdown.rect = pygame.Rect(left.x + 20, y, left.w - 40, 36)
        self.resolution_dropdown.draw(self.screen, get_font(11), draw_list=False)
        # Показываем текущий применённый рядом
        cur_res = tuple(self.settings.get("resolution", [W, H]))
        cur_label = f"{cur_res[0]}×{cur_res[1]}"
        hint = get_font(10).render(f"Применено: {cur_label}", True, COLOR_TEXT_DIM)
        self.screen.blit(hint, (left.x + 20, y + 40))
        y += 64

        # Монитор
        lbl_mon = get_font(11, bold=True).render("ЭКРАН (МОНИТОР)", True, COLOR_TEXT)
        self.screen.blit(lbl_mon, (left.x + 20, y))
        y += 18
        try:
            mons = get_available_monitors()
        except Exception:
            mons = [{"id": 0, "name": "Монитор 1 — 1920×1080"}]
        self.monitor_dropdown.rect = pygame.Rect(left.x + 20, y, left.w - 40, 36)
        # Если монитор один — показываем disabled стиль
        self.monitor_dropdown.draw(self.screen, get_font(11), draw_list=False)
        if len(mons) == 1:
            tip = font_small.render(
                "Обнаружен 1 монитор. Подключите второй для выбора.", True, COLOR_TEXT_DARK
            )
            self.screen.blit(tip, (left.x + 20, y + 40))
        y += 64

        # Режим окна — 3 кнопки-сегмента
        lbl_mode = get_font(11, bold=True).render("РЕЖИМ ОКНА", True, COLOR_TEXT)
        self.screen.blit(lbl_mode, (left.x + 20, y))
        y += 18
        mode_labels = {
            "windowed": "Оконный",
            "fullscreen": "Полный экран",
            "borderless": "Без рамки",
        }
        mode_width = (left.w - 40 - 12) // 3
        mode_x = left.x + 20
        for i, (mid, label) in enumerate(
            [("windowed", "Оконный"), ("fullscreen", "Полный экран"), ("borderless", "Без рамки")]
        ):
            is_sel = self._pending_window_mode == mid
            style = "primary" if is_sel else "secondary"
            btn = Button((mode_x + i * (mode_width + 6), y, mode_width, 38), label, style=style)
            # Hover
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(10, bold=True))
            if btn.clicked:
                self._pending_window_mode = mid
                self._settings_changed = True
        y += 50
        # Подсказка режимов
        mode_hint = {
            "windowed": "Окно с рамкой — можно перетаскивать",
            "fullscreen": "Эксклюзивный фуллскрин — макс. производительность",
            "borderless": "Окно на весь экран без рамки — удобен для стримов",
        }.get(self._pending_window_mode, "")
        hint2 = font_small.render(mode_hint, True, COLOR_TEXT_DARK)
        self.screen.blit(hint2, (left.x + 20, y))
        y += 28

        # Синхронизируем pending с дропдаунами на случай если handle_event пропустил изменение
        if self.resolution_dropdown.selected != self._pending_resolution:
            self._pending_resolution = self.resolution_dropdown.selected
            self._settings_changed = True
        if self.monitor_dropdown.selected != self._pending_monitor:
            self._pending_monitor = self.monitor_dropdown.selected
            self._settings_changed = True

        # Проверяем изменения надёжно — сравниваем pending с сохранёнными, а не только флаг
        cur_w, cur_h = self.settings.get("resolution", [W, H])
        if isinstance(cur_w, list):
            cur_w, cur_h = cur_w[0], cur_w[1]
        pending_res_str = self._pending_resolution
        saved_res_str = f"{cur_w}x{cur_h}"
        pending_mon_str = str(self._pending_monitor)
        saved_mon_str = str(self.settings.get("monitor", 0))
        pending_mode = self._pending_window_mode
        saved_mode = self.settings.get("window_mode", "windowed")
        has_changes = (
            self._settings_changed
            or pending_res_str != saved_res_str
            or pending_mon_str != saved_mon_str
            or pending_mode != saved_mode
            or self.sfx_slider.value != self.settings.get("sfx_volume", 0.7)
            or self.music_slider.value != self.settings.get("music_volume", 0.5)
            or self.auto_update_toggle.checked != self.settings.get("auto_check_updates", True)
            or self.voice_toggle.checked != self.settings.get("voice_enabled", True)
        )
        # Индикатор изменений
        if has_changes:
            dot = get_font(10, bold=True).render(
                "●  Есть несохранённые изменения", True, COLOR_ACCENT
            )
            self.screen.blit(dot, (left.x + 20, y))
        y += 22
        btn_apply = Button(
            layout.apply,
            "ПРИМЕНИТЬ",
            style="primary" if has_changes else "secondary",
            enabled=has_changes,
        )
        btn_apply.update(mouse, pressed)
        btn_apply.draw(self.screen, get_font(11, bold=True))
        if btn_apply.clicked and has_changes:
            self._apply_pending_settings()
        btn_cancel = Button(
            layout.reset, "ОТМЕНИТЬ", tooltip="Вернуть настройки экрана без сохранения"
        )
        btn_cancel.update(mouse, pressed)
        btn_cancel.draw(self.screen, get_font(11, bold=True))
        if btn_cancel.clicked:
            self._init_settings_widgets()
            self.add_notification("Изменения настроек отменены")
        # Оверлей открытых списков — поверх всего левого блока (чтобы не перекрывались контролами)
        self._draw_dropdown_overlay([self.resolution_dropdown, self.monitor_dropdown])

        # --- ПРАВАЯ: Звук ---
        ry = right.y + 50
        self.sfx_slider.rect = pygame.Rect(right.x + 20, ry + 18, right.w - 40, 12)
        self.sfx_slider.draw(self.screen, get_font(10))
        # Меняем настройки слайдера в реальном времени? Только при apply, но показываем live
        if self.sfx_slider.handle_event(pygame.event.Event(pygame.NOEVENT)) or True:
            pass
        ry += 50
        self.music_slider.rect = pygame.Rect(right.x + 20, ry + 18, right.w - 40, 12)
        self.music_slider.draw(self.screen, get_font(10))
        self.audio.set_volumes(music=self.music_slider.value, sfx=self.sfx_slider.value)
        ry += 50
        # Озвучка
        self.voice_toggle.rect = pygame.Rect(right.x + 20, ry + 6, 44, 24)
        self.voice_toggle.draw(self.screen, get_font(11))
        voice_hint = font_small.render(
            "Голос рассказчика в катсценах" if self.voice_toggle.checked else "Только субтитры, без голоса",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(voice_hint, (right.x + 20, ry + 34))
        ry += 58
        # Авто-обновления
        self.auto_update_toggle.rect = pygame.Rect(right.x + 20, ry + 6, 44, 24)
        self.auto_update_toggle.draw(self.screen, get_font(11))
        ry += 44
        # Папка сохранений
        save_hint = font_small.render(f"Сохранения: {get_save_dir()}", True, COLOR_TEXT_DARK)
        self.screen.blit(save_hint, (right.x + 20, ry))
        ry += 18
        from . import __version__ as _game_version

        ver2 = font_small.render(
            f"Игра: v{_game_version}  •  Python {__import__('sys').version.split()[0]}",
            True,
            COLOR_TEXT_DARK,
        )
        self.screen.blit(ver2, (right.x + 20, ry))
        ry += 30

        # Кнопки обновлений
        btn_check = Button(
            layout.check_updates, "ПРОВЕРИТЬ ОБНОВЛЕНИЯ", style="secondary"
        )
        btn_check.update(mouse, pressed)
        btn_check.draw(self.screen, get_font(11, bold=True))
        if btn_check.clicked:
            self.update_checker = UpdateChecker()
            self.update_checker.start()
            self.update_dismissed = False
            self.add_notification("Проверка обновлений...")
        ry += 48
        # Статус обновления
        checker = self.update_checker
        if checker.checking:
            font_small2 = get_font(11).render("Поиск новой версии...", True, COLOR_TEXT_DIM)
            self.screen.blit(font_small2, (right.x + 20, ry))
            # спиннер
            pygame.draw.circle(self.screen, COLOR_ACCENT, (right.x + 20 + 8, ry + 18), 8, width=2)
        elif checker.done and checker.result:
            info = checker.result
            # Зелёная плашка
            upd_rect = pygame.Rect(right.x + 15, ry, right.w - 30, 86)
            pygame.draw.rect(self.screen, (18, 50, 38), upd_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_GREEN, upd_rect, width=2, border_radius=8)
            new_ver = get_font(11, bold=True).render(
                f"Доступна v{info['latest']}  (у вас v{info['current']})  ★", True, (180, 255, 180)
            )
            self.screen.blit(new_ver, (upd_rect.x + 12, upd_rect.y + 10))
            name_txt = get_font(10).render(info.get("name", "")[:46], True, (220, 255, 220))
            self.screen.blit(name_txt, (upd_rect.x + 12, upd_rect.y + 26))
            # Кнопки: прогресс / скачать / установить
            if checker.downloading:
                prog = checker.download_progress / 100 if checker.download_total else 0
                # прогресс-бар — процент уже рисуется по центру внутри бара
                bar_rect = pygame.Rect(upd_rect.x + 12, upd_rect.y + 44, upd_rect.w - 24, 14)
                draw_progress_bar(self.screen, bar_rect, prog)
            elif getattr(checker, "downloaded_path", None) and checker.downloaded_path.exists():
                # Уже скачано — показываем кнопку УСТАНОВИТЬ
                ok_txt = get_font(9).render(f"✓ Скачано: {checker.downloaded_path.name}", True, (180, 255, 180))
                self.screen.blit(ok_txt, (upd_rect.x + 12, upd_rect.y + 44))
                btn_install = Button(
                    (upd_rect.x + 12, upd_rect.y + 58, 140, 26), "▶ УСТАНОВИТЬ", style="success"
                )
                btn_install.update(mouse, pressed)
                btn_install.draw(self.screen, get_font(8, bold=True))
                if btn_install.clicked and self._click_once():
                    self._install_update()
                btn_folder = Button((upd_rect.x + 160, upd_rect.y + 58, 80, 26), "Папка")
                btn_folder.update(mouse, pressed)
                btn_folder.draw(self.screen, get_font(8, bold=True))
                if btn_folder.clicked and self._click_once():
                    try:
                        from .updater import open_download_folder
                        open_download_folder(checker.downloaded_path)
                    except Exception:
                        pass
            else:
                btn_dl = Button(
                    (upd_rect.x + 12, upd_rect.y + 46, 120, 28), "⬇  СКАЧАТЬ", style="success"
                )
                btn_dl.update(mouse, pressed)
                btn_dl.draw(self.screen, get_font(9, bold=True))
                if btn_dl.clicked and self._click_once():
                    checker.start_download()
                    self.add_notification("Загрузка началась...")
                btn_later = Button((upd_rect.x + 142, upd_rect.y + 46, 90, 28), "Позже")
                btn_later.update(mouse, pressed)
                btn_later.draw(self.screen, get_font(9, bold=True))
                if btn_later.clicked and self._click_once():
                    self.update_dismissed = True
            # Ошибка загрузки
            if getattr(checker, "download_error", None):
                err_txt = get_font(8).render(checker.download_error[:50], True, COLOR_RED)
                self.screen.blit(err_txt, (upd_rect.x + 12, upd_rect.y + 74 - 2))
        elif checker.done and checker.error:
            # Проверка не удалась (нет сети / лимит GitHub) — не врём про «последнюю версию»
            err_rect = pygame.Rect(right.x + 15, ry, right.w - 30, 92)
            pygame.draw.rect(self.screen, (52, 20, 24), err_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_RED, err_rect, width=2, border_radius=8)
            head = get_font(10, bold=True).render("НЕ УДАЛОСЬ ПРОВЕРИТЬ ОБНОВЛЕНИЕ", True, COLOR_RED)
            self.screen.blit(head, (err_rect.x + 10, err_rect.y + 8))
            # Причина целиком, максимум 2 строки — переносим по словам
            draw_text_wrapped(
                self.screen,
                str(checker.error),
                get_font(8),
                (255, 205, 205),
                pygame.Rect(err_rect.x + 10, err_rect.y + 24, err_rect.w - 20, 30),
            )
            btn_retry = Button(
                (err_rect.x + 10, err_rect.y + 58, 150, 26), "ПОВТОРИТЬ ПРОВЕРКУ", style="success"
            )
            btn_retry.update(mouse, pressed)
            btn_retry.draw(self.screen, get_font(8, bold=True))
            if btn_retry.clicked and self._click_once():
                self._retry_update_check()
            btn_log_txt = get_font(8).render("открыть журнал", True, COLOR_ACCENT)
            log_rect = btn_log_txt.get_rect(topleft=(err_rect.x + 172, err_rect.y + 66))
            self.screen.blit(btn_log_txt, log_rect)
            if log_rect.collidepoint(mouse) and pressed:
                open_app_log()
        elif checker.done and checker.result and getattr(checker, "download_error", None):
            # Обновление есть, но скачать не вышло — видно, что именно случилось
            err_rect = pygame.Rect(right.x + 15, ry, right.w - 30, 86)
            pygame.draw.rect(self.screen, (52, 20, 24), err_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_RED, err_rect, width=2, border_radius=8)
            head = get_font(10, bold=True).render("ОШИБКА ЗАГРУЗКИ ОБНОВЛЕНИЯ", True, COLOR_RED)
            self.screen.blit(head, (err_rect.x + 10, err_rect.y + 8))
            draw_text_wrapped(
                self.screen,
                str(checker.download_error),
                get_font(8),
                (255, 205, 205),
                pygame.Rect(err_rect.x + 10, err_rect.y + 24, err_rect.w - 20, 30),
            )
            btn_retry = Button((err_rect.x + 10, err_rect.y + 56, 120, 26), "ЕЩЁ РАЗ")
            btn_retry.update(mouse, pressed)
            btn_retry.draw(self.screen, get_font(8, bold=True))
            if btn_retry.clicked and self._click_once():
                checker.download_error = None
                checker.start_download()
            btn_log_txt = get_font(8).render("открыть журнал", True, COLOR_ACCENT)
            log_rect = btn_log_txt.get_rect(topleft=(err_rect.x + 140, err_rect.y + 64))
            self.screen.blit(btn_log_txt, log_rect)
            if log_rect.collidepoint(mouse) and pressed:
                open_app_log()
        elif checker.done and not checker.result:
            # Нет обновлений
            txt = font_small.render("У вас последняя версия ✓", True, COLOR_GREEN)
            self.screen.blit(txt, (right.x + 20, ry))
        ry += 100

        # Диагностика: версия, канал проверки, путь к журналу (для баг-репортов)
        diag_font = get_font(9)
        diag_x = right.x + 18
        for i, line in enumerate(self._update_diagnostics()[:3]):
            color = COLOR_TEXT_DARK if i < 2 else (150, 150, 165)
            self.screen.blit(diag_font.render(line[:74], True, color), (diag_x, ry - 2 + i * 16))
        log_link = get_font(9).render("открыть журнал обновлений →", True, COLOR_ACCENT)
        log_link_rect = log_link.get_rect(topleft=(diag_x, ry + 50))
        self.screen.blit(log_link, log_link_rect)
        if log_link_rect.collidepoint(mouse) and pressed:
            open_app_log()
        ry += 78

        # Кнопка сброса прогресса — опасная
        btn_wipe = Button(layout.wipe, "СБРОСИТЬ ПРОГРЕСС", style="danger")
        btn_wipe.update(mouse, pressed)
        btn_wipe.draw(self.screen, get_font(10, bold=True))
        if btn_wipe.clicked:
            # необратимо — спрашиваем ещё раз на отдельном экране
            self.ask_confirm(
                "СБРОСИТЬ ПРОГРЕСС?",
                "Будут стёрты все прохождения, собранные улики, репутация, "
                "деньги и открытые концовки. Отменить это действие нельзя.",
                self._wipe_confirmed,
                yes="СТЕРЕТЬ ВСЁ",
            )

    def _draw_dropdown_overlay(self, dropdowns):
        # Рисует открытые списки поверх всего (вторая фаза)
        for dd in dropdowns:
            if dd.open:
                # Фон списка
                list_h = len(dd.options) * 32
                list_rect = pygame.Rect(dd.rect.x, dd.rect.bottom + 2, dd.rect.w, list_h)
                # Тень
                shadow = pygame.Surface((list_rect.w, list_rect.h), 0)
                shadow.set_alpha(0)
                # Рисуем тень как полупрозрачный прямоугольник
                s = pygame.Surface((list_rect.w, list_rect.h), pygame.SRCALPHA)
                pygame.draw.rect(s, (0, 0, 0, 160), (0, 0, list_rect.w, list_rect.h), border_radius=6)
                self.screen.blit(s, (list_rect.x + 2, list_rect.y + 2))
                # Непрозрачный фон списка
                pygame.draw.rect(self.screen, (32, 32, 42), list_rect, border_radius=6)
                pygame.draw.rect(self.screen, COLOR_ACCENT if dd.open else COLOR_BORDER, list_rect, width=2, border_radius=6)
                mouse = self._to_logical(pygame.mouse.get_pos())
                for i, (val, name) in enumerate(dd.options):
                    opt_rect = pygame.Rect(list_rect.x, list_rect.y + i * 32, list_rect.w, 32)
                    hovered = opt_rect.collidepoint(mouse)
                    is_selected = val == dd.selected
                    if hovered:
                        pygame.draw.rect(self.screen, COLOR_ACCENT if is_selected else (48, 48, 62), opt_rect, border_radius=4)
                    elif is_selected:
                        pygame.draw.rect(self.screen, (48, 42, 28), opt_rect, border_radius=4)
                    opt_font = get_font(11, bold=is_selected)
                    # Обрезаем длинные названия
                    disp = name
                    if opt_font.size(disp)[0] > opt_rect.w - 36:
                        while len(disp) > 4 and opt_font.size(disp + "...")[0] > opt_rect.w - 36:
                            disp = disp[:-1]
                        disp += "..."
                    col = COLOR_ACCENT if is_selected else COLOR_TEXT
                    opt_txt = opt_font.render(disp, True, col)
                    self.screen.blit(opt_txt, (opt_rect.x + 10, opt_rect.y + (opt_rect.h - opt_txt.get_height()) // 2))
                    if is_selected:
                        chk = get_font(10).render("✓", True, COLOR_ACCENT)
                        self.screen.blit(chk, (opt_rect.right - 20, opt_rect.y + (opt_rect.h - chk.get_height()) // 2))

    def draw_update_banner(self):
        from .ui.widgets import Button, draw_progress_bar, get_font

        if self.update_dismissed or self.screen_name == "settings":
            # В настройках уже есть детальная панель — баннер не мешаем
            return
        checker = self.update_checker

        # Обновление скачали и запустили, но версия не сменилась — самый
        # непонятный случай: показываем баннер, пока игрок не закроет.
        if self.failed_update:
            rect = pygame.Rect(WINDOW_WIDTH // 2 - 380, 10, 760, 74)
            pygame.draw.rect(self.screen, (58, 22, 26), rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_RED, rect, width=2, border_radius=8)
            target = self.failed_update.get("target", "?")
            current = self.failed_update.get("current", "?")
            self.screen.blit(
                get_font(11, bold=True).render(
                    f"Обновление до v{target} не установилось — открыта v{current}",
                    True,
                    (255, 200, 200),
                ),
                (rect.x + 15, rect.y + 8),
            )
            draw_text_wrapped(
                self.screen,
                "Файлы не заменились. Откройте журнал, чтобы увидеть код ошибки, "
                "или скачайте установщик вручную со страницы релиза.",
                get_font(9),
                (235, 190, 190),
                pygame.Rect(rect.x + 15, rect.y + 26, rect.w - 330, 40),
            )
            mouse = self._to_logical(pygame.mouse.get_pos())
            pressed = pygame.mouse.get_pressed()[0]
            btn_log = Button((rect.right - 300, rect.y + 22, 110, 30), "ЖУРНАЛ")
            btn_log.update(mouse, pressed)
            btn_log.draw(self.screen, get_font(8, bold=True))
            if btn_log.clicked and self._click_once():
                open_app_log()
            btn_manual = Button((rect.right - 182, rect.y + 22, 130, 30), "СКАЧАТЬ ВРУЧНУЮ")
            btn_manual.update(mouse, pressed)
            btn_manual.draw(self.screen, get_font(8, bold=True))
            if btn_manual.clicked and self._click_once():
                try:
                    import webbrowser

                    webbrowser.open(GITHUB_RELEASES_URL)
                except Exception:
                    pass
            close_rect = pygame.Rect(rect.right - 42, rect.y + 22, 30, 30)
            pygame.draw.rect(self.screen, (90, 45, 50), close_rect, border_radius=4)
            x_txt = get_font(12, bold=True).render("×", True, (255, 255, 255))
            self.screen.blit(x_txt, x_txt.get_rect(center=close_rect.center))
            if close_rect.collidepoint(mouse) and pressed:
                self.failed_update = None
            return

        # Сбой проверки — показываем причину на главном экране, а не молчим
        if checker.done and not checker.result and checker.error:
            rect = pygame.Rect(WINDOW_WIDTH // 2 - 360, 10, 720, 62)
            pygame.draw.rect(self.screen, (58, 22, 26), rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_RED, rect, width=2, border_radius=8)
            head = get_font(11, bold=True).render(
                "Не удалось проверить обновления", True, (255, 200, 200)
            )
            self.screen.blit(head, (rect.x + 15, rect.y + 8))
            draw_text_wrapped(
                self.screen,
                str(checker.error),
                get_font(9),
                (235, 190, 190),
                pygame.Rect(rect.x + 15, rect.y + 24, rect.w - 320, 34),
            )
            mouse = self._to_logical(pygame.mouse.get_pos())
            pressed = pygame.mouse.get_pressed()[0]
            btn_retry = Button((rect.right - 290, rect.y + 15, 130, 30), "ПОВТОРИТЬ", style="success")
            btn_retry.update(mouse, pressed)
            btn_retry.draw(self.screen, get_font(8, bold=True))
            if btn_retry.clicked and self._click_once():
                self._retry_update_check()
                return
            btn_log = Button((rect.right - 150, rect.y + 15, 90, 30), "Журнал")
            btn_log.update(mouse, pressed)
            btn_log.draw(self.screen, get_font(8, bold=True))
            if btn_log.clicked and self._click_once():
                open_app_log()
            close_rect = pygame.Rect(rect.right - 50, rect.y + 15, 30, 30)
            pygame.draw.rect(self.screen, (90, 45, 50), close_rect, border_radius=4)
            x_txt = get_font(12, bold=True).render("×", True, (255, 255, 255))
            self.screen.blit(x_txt, x_txt.get_rect(center=close_rect.center))
            if close_rect.collidepoint(mouse) and pressed:
                self.update_dismissed = True
            return
        banner = None
        if checker.done and checker.result:
            banner = checker.result
        if not banner:
            # Покажем успех скачивания даже если result уже сброшен (напр. после перезапуска проверки)
            if getattr(checker, "downloaded_path", None) and not checker.downloading:
                rect = pygame.Rect(WINDOW_WIDTH // 2 - 360, 10, 720, 56)
                pygame.draw.rect(self.screen, (16, 45, 70), rect, border_radius=8)
                pygame.draw.rect(self.screen, (80, 140, 220), rect, width=2, border_radius=8)
                ver_txt = getattr(checker, "download_target_version", "") or (
                    checker.result['latest'] if checker.result and checker.result.get('latest') else ''
                )
                txt = get_font(12, bold=True).render(
                    f"✓ Обновление v{ver_txt} скачано: {checker.downloaded_path.name}", True, (255, 255, 255)
                )
                self.screen.blit(txt, (rect.x + 15, rect.y + 8))
                sub = get_font(11).render("Готово к установке — нажмите «Установить и перезапустить»", True, (200, 230, 255))
                self.screen.blit(sub, (rect.x + 15, rect.y + 28))
                mouse = self._to_logical(pygame.mouse.get_pos())
                pressed = pygame.mouse.get_pressed()[0]
                btn_inst = Button((rect.right - 220, rect.y + 12, 150, 32), "▶ УСТАНОВИТЬ", style="success")
                btn_inst.update(mouse, pressed)
                btn_inst.draw(self.screen, get_font(9, bold=True))
                if btn_inst.clicked and self._click_once():
                    self._install_update()
                close_rect = pygame.Rect(rect.right - 30, rect.y + 10, 20, 20)
                pygame.draw.rect(self.screen, (40, 70, 110), close_rect, border_radius=4)
                x_txt = get_font(12, bold=True).render("×", True, (255, 255, 255))
                self.screen.blit(x_txt, x_txt.get_rect(center=close_rect.center))
                if close_rect.collidepoint(mouse) and pressed:
                    self.update_dismissed = True
            return
        # Активный баннер обновления
        rect = pygame.Rect(WINDOW_WIDTH // 2 - 360, 10, 720, 64)
        from .ui.widgets import Button

        pygame.draw.rect(self.screen, (20, 60, 40), rect, border_radius=10)
        pygame.draw.rect(self.screen, COLOR_GREEN, rect, width=2, border_radius=10)
        # Левая иконка
        pygame.draw.circle(self.screen, COLOR_GREEN, (rect.x + 22, rect.y + 22), 14)
        ic = get_font(14, bold=True).render("↑", True, (255, 255, 255))
        self.screen.blit(ic, ic.get_rect(center=(rect.x + 22, rect.y + 22)))
        txt = get_font(12, bold=True).render(
            f"Доступна новая версия v{banner['latest']}  (у вас v{banner['current']})  —  {banner['name']}",
            True,
            (255, 255, 255),
        )
        self.screen.blit(txt, (rect.x + 44, rect.y + 10))
        sub = get_font(10).render(
            "Обновитесь, чтобы получить исправления и новые Дела", True, (200, 255, 200)
        )
        self.screen.blit(sub, (rect.x + 44, rect.y + 28))
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        if checker.downloading:
            bar_rect = pygame.Rect(rect.x + 44, rect.y + 42, 320, 10)
            prog = (
                checker.download_progress / 100
                if checker.download_total
                else checker.download_progress / 100
            )
            draw_progress_bar(self.screen, bar_rect, prog, radius=5)
        elif getattr(checker, "downloaded_path", None) and checker.downloaded_path.exists():
            # СКАЧАНО — показываем УСТАНОВИТЬ прямо на главном экране (с автозапуском)
            btn_install = Button((rect.right - 220, rect.y + 12, 150, 26), "▶ УСТАНОВИТЬ", style="success")
            btn_install.update(mouse, pressed)
            btn_install.draw(self.screen, get_font(9, bold=True))
            if btn_install.clicked and self._click_once():
                self._install_update()
            btn_open = Button((rect.right - 60, rect.y + 12, 40, 26), "Папка")
            btn_open.update(mouse, pressed)
            btn_open.draw(self.screen, get_font(8, bold=True))
            if btn_open.clicked and self._click_once():
                try:
                    from .updater import open_download_folder
                    open_download_folder(checker.downloaded_path)
                except Exception:
                    pass
        else:
            # Кнопки: скачать / скачать + открыть / закрыть
            btn_dl = Button((rect.right - 220, rect.y + 12, 110, 26), "⬇ Скачать", style="success")
            btn_dl.update(mouse, pressed)
            btn_dl.draw(self.screen, get_font(9, bold=True))
            if btn_dl.clicked and self._click_once():
                checker.start_download()
                self.add_notification("Загрузка обновления...")
            btn_open = Button((rect.right - 100, rect.y + 12, 80, 26), "Открыть")
            btn_open.update(mouse, pressed)
            btn_open.draw(self.screen, get_font(9, bold=True))
            if btn_open.clicked:
                import webbrowser

                try:
                    webbrowser.open(banner["url"])
                except Exception:
                    pass
        close_rect = pygame.Rect(rect.right - 22, rect.y + 6, 16, 16)
        pygame.draw.rect(self.screen, (40, 80, 60), close_rect, border_radius=4)
        x_txt = get_font(10, bold=True).render("×", True, (255, 255, 255))
        self.screen.blit(x_txt, x_txt.get_rect(center=close_rect.center))
        if close_rect.collidepoint(mouse) and pressed:
            self.update_dismissed = True


def main():
    # поддержка exe frozen
    if getattr(sys, "frozen", False):
        # PyInstaller
        os_chdir = getattr(sys, "_MEIPASS", None)
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
