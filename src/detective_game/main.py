"""Главный цикл игры — все экраны."""

import sys
import time

import pygame

from . import get_version_source
from .config import *
from .data import get_clue, get_location, list_cases, load_case
from .game_state import AVATARS, BACKGROUNDS, DetectiveProfile, GameState
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
from .ui.layout import (
    case_select_layout,
    customization_layout,
    map_layout,
    settings_layout,
)
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
        self.screen_name = "menu"  # menu | customization | case_select | map | location | dialogue | notebook | accusation | ending | settings
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
        # notebook tab
        self.notebook_tab = "clues"  # clues | suspects | map
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
        """Показывает, чем закончилась установка обновления из прошлого запуска."""
        if not result:
            return
        if result.get("status") == "installed":
            self.add_notification(f"Обновление установлено — теперь v{result['current']}")
            log_update(f"обновление установлено: v{result['current']}")
            return
        target = result.get("target", "?")
        current = result.get("current", "?")
        log_update(f"обновление до v{target} не установилось (у вас v{current})")
        self.add_notification(
            f"Обновление до v{target} не установилось (у вас v{current}). "
            "Настройки → «Проверить обновления» → «Журнал»"
        )

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

    def _install_update(self):
        """Запускает установщик скачанного обновления и выходит из игры.

        Если текущая папка игры недоступна на запись (Program Files), установка
        идёт через видимый мастер с запросом UAC — иначе Windows молча
        отказывает в записи и «игра не обновляется».
        """
        path = getattr(self.update_checker, "downloaded_path", None)
        if not path or not getattr(path, "exists", lambda: False)():
            self.add_notification("Файл обновления не найден — скачайте его заново")
            return False
        if str(path).lower().endswith(".zip"):
            try:
                from .updater import open_download_folder

                open_download_folder(path)
            except Exception:
                pass
            self.add_notification(
                "Обновление скачано архивом — закройте игру и распакуйте его вручную"
            )
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
            self.add_notification(
                "Не удалось запустить установщик — откройте папку загрузок кнопкой «Папка»"
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
                loc_id = layout.pin_at(event.pos)
                # Пины ловятся в тех же точках, где нарисованы (раньше клик
                # проверялся по сырым координатам дела и уходил мимо).
                if loc_id and loc_id in self.get_available_locations():
                    pygame.time.wait(120)
                    self.location_id = loc_id
                    self.screen_name = "location"
                    self.state.visited_locations.add(loc_id)
                    save_game(self.state)
        elif self.screen_name == "location":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.screen_name = "map"

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
        # обновление времени
        if self.state.case_state == "in_progress":
            self.state.total_playtime += 1 / FPS
        if self.screen_name == "tutorial":
            try:
                dt = self.clock.get_time()
            except Exception:
                dt = 1000 // FPS
            self.tutorial.update(dt)

    def draw(self):
        # Letterbox рендер: рисуем всё на логический холст 1280×720, затем масштабируем
        real_screen = self.screen
        logical = pygame.Surface((self.LOGICAL_W, self.LOGICAL_H))
        self.screen = logical
        try:
            self.screen.fill(COLOR_BG)
            # фон — сетка города
            self.draw_city_background()
            if self.screen_name == "menu":
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
            # уведомления поверх всего
            self.draw_notifications()
            # проверка обновлений баннер
            self.draw_update_banner()
        finally:
            self.screen = real_screen
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
                    self.screen_name = "customization"
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
            # постер-заглушка
            poster = card.poster
            for i in range(poster.h):
                col = (30 + i // 3, 30 + i // 4, 40 + i // 5)
                pygame.draw.line(
                    self.screen, col, (poster.x, poster.y + i), (poster.right, poster.y + i)
                )
            pygame.draw.rect(self.screen, COLOR_BORDER, poster, width=1, border_radius=8)
            # иконка-бейдж дела (эмодзи нет в бандл-шрифте — рисуем букву в кольце)
            draw_icon(
                self.screen,
                "",
                poster.center,
                max(48, min(poster.w, poster.h) // 2),
                color=COLOR_ACCENT,
                fallback=(case["title"][:1] or "?"),
            )
            # заголовок и подзаголовок
            title_surf = get_font(18, bold=True).render(case["title"], True, COLOR_TEXT)
            self.screen.blit(title_surf, card.title_pos)
            sub = get_font(12).render(case["subtitle"], True, COLOR_ACCENT)
            self.screen.blit(sub, card.subtitle_pos)
            diff = get_font(11).render(
                f"{case['difficulty']} • {case['duration']}", True, COLOR_TEXT_DIM
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

    def start_case(self, case_id):
        case = load_case(case_id)
        if not case:
            return
        self.current_case = case
        self.state.current_case_id = case_id
        self.state.visited_locations = set(["office"])
        self.state.collected_clues = set()
        self.state.interrogated = set()
        self.state.case_time_minutes = 0
        self.state.game_day = 1
        self.state.case_state = "in_progress"
        self.state.accusation_result = None
        self.state.accusation_correct = None
        save_game(self.state)
        self.location_id = "office"
        self.screen_name = "map"
        self.add_notification(f"Дело «{case['title']}» начато. Удачи, {self.state.detective.name}!")

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

    def draw_map(self):
        if not self.current_case:
            return
        layout = self._map_layout()
        font_title = get_font(20, bold=True)
        font_small = get_font(13)

        # header
        draw_panel(self.screen, layout.header)
        case_title = font_title.render(
            f"ДЕЛО: {self.current_case['title'].upper()}", True, COLOR_ACCENT
        )
        self.screen.blit(case_title, (layout.header.x + 20, layout.header.y + 8))
        day_text = font_small.render(
            f"День {self.state.game_day} • Время: {9 + self.state.case_time_minutes // 60:02d}:{self.state.case_time_minutes % 60:02d} • Улик: {len(self.state.collected_clues)}/{len(self.current_case['clues'])}",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(day_text, (layout.header.x + 20, layout.header.y + 30))

        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        can_accuse = len(self.state.collected_clues) >= 3
        btn_notebook = Button(layout.btn_notebook, "БЛОКНОТ")
        btn_dossier = Button(layout.btn_dossier, "ДОСЬЕ")
        btn_accuse = Button(layout.btn_accuse, "ОБВИНИТЬ", accent=True)
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
                    self.screen_name = "accusation"

        # карта
        draw_panel(self.screen, layout.map_rect)
        city_surf = pygame.Surface((layout.map_rect.w, layout.map_rect.h))
        city_surf.fill((18, 18, 26))
        districts = [
            {"name": "ЦЕНТР", "x": 0.35, "y": 0.3, "w": 0.3, "h": 0.3},
            {"name": "ПОРТ", "x": 0.7, "y": 0.5, "w": 0.3, "h": 0.5},
            {"name": "ЗАПАД", "x": 0, "y": 0.5, "w": 0.35, "h": 0.5},
            {"name": "СЕВЕР", "x": 0, "y": 0, "w": 0.5, "h": 0.3},
            {"name": "ХОЛМЫ", "x": 0, "y": 0, "w": 0.3, "h": 0.35},
        ]
        for d in districts:
            r = pygame.Rect(
                int(d["x"] * layout.map_rect.w),
                int(d["y"] * layout.map_rect.h),
                int(d["w"] * layout.map_rect.w),
                int(d["h"] * layout.map_rect.h),
            )
            pygame.draw.rect(city_surf, (28, 28, 38), r, border_radius=8)
            pygame.draw.rect(city_surf, (50, 50, 60), r, width=1, border_radius=8)
            font_dist = get_font(10, bold=True)
            txt = font_dist.render(d["name"], True, (80, 80, 90))
            city_surf.blit(txt, (r.x + 8, r.y + 6))
        for x in range(0, layout.map_rect.w, 80):
            pygame.draw.line(city_surf, (40, 40, 50), (x, 0), (x, layout.map_rect.h), 1)
        for y in range(0, layout.map_rect.h, 80):
            pygame.draw.line(city_surf, (40, 40, 50), (0, y), (layout.map_rect.w, y), 1)
        self.screen.blit(city_surf, layout.map_rect.topleft)

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

        hint = font_small.render(
            "Нажмите на локацию, чтобы посетить. Серые — недоступны, пока не найдёте зацепку.",
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
                if y > layout.btn_menu.y - 40:
                    break
        prog_rect = pygame.Rect(right.x + 15, layout.btn_menu.y - 26, right.w - 30, 8)
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
        type_txt = get_font(11).render(
            loc["type"].upper() + " • " + loc["district"], True, COLOR_TEXT_DIM
        )
        self.screen.blit(type_txt, (header.right - 200, header.y + 20))
        btn_back = Button((header.right - 220, header.y + 10, 100, 30), "← КАРТА")
        btn_notes = Button((header.right - 110, header.y + 10, 90, 30), "БЛОКНОТ")
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
        # слева — визуал локации
        visual = pygame.Rect(main_rect.x + 15, main_rect.y + 15, 500, 300)
        # градиент локации по типу
        type_cols = {
            "police": (30, 50, 80),
            "crime": (60, 30, 30),
            "bar": (60, 40, 20),
            "apartment": (40, 50, 40),
            "bank": (60, 60, 30),
            "vault": (40, 40, 50),
            "public": (40, 50, 60),
            "hub": (50, 50, 30),
            "warehouse": (40, 40, 40),
        }
        base_col = type_cols.get(loc["type"], (30, 30, 40))
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
            visual.center,
            96,
            color=(200, 200, 210),
            fallback=(loc["name"][:1] or "?"),
        )
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
        # находим улики в этой локации
        clues_here = [c for c in self.current_case["clues"] if c["location"] == loc["id"]]
        chars_here = [ch for ch in self.current_case["characters"] if ch["location"] == loc["id"]]
        y = right.y
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
                # описание обрезанное
                desc = clue["desc"][:90] + "..." if len(clue["desc"]) > 90 else clue["desc"]
                draw_text_wrapped(
                    self.screen,
                    desc,
                    get_font(11),
                    COLOR_TEXT_DIM,
                    pygame.Rect(rect.x + 35, rect.y + 30, rect.w - 50, 30),
                )
                # кнопка собрать
                if not collected:
                    btn = Button((rect.right - 100, rect.y + 12, 85, 28), "ИЗУЧИТЬ", accent=True)
                    btn.update(mouse, pressed)
                    btn.draw(self.screen, get_font(11, bold=True))
                    if btn.clicked:
                        pygame.time.wait(150)
                        self.state.collected_clues.add(clue["id"])
                        # разблокируем новые локации
                        for nid in clue.get("leads_to", []):
                            self.add_notification("Новая локация открыта!")
                        # время +10 мин
                        self.state.case_time_minutes += 10
                        save_game(self.state)
                        self.add_notification(f"Улика собрана: {clue['title']}")
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
                role = get_font(11).render(ch["role"], True, COLOR_ACCENT)
                self.screen.blit(role, (rect.x + 70, rect.y + 28))
                bio = get_font(10).render(ch["bio"][:50], True, COLOR_TEXT_DIM)
                self.screen.blit(bio, (rect.x + 70, rect.y + 45))
                # кнопка допроса
                btn = Button((rect.right - 110, rect.y + 20, 95, 30), "ДОПРОСИТЬ")
                btn.update(mouse, pressed)
                btn.draw(self.screen, get_font(11, bold=True))
                if btn.clicked:
                    pygame.time.wait(150)
                    self.dialogue_char = ch
                    self.dialogue_idx = 0
                    self.screen_name = "dialogue"
                    self.state.interrogated.add(ch["id"])
                y += 78
        else:
            empty2 = get_font(12).render("Персонажей здесь нет.", True, COLOR_TEXT_DARK)
            self.screen.blit(empty2, (right.x, y))

    def draw_dialogue(self):
        if not self.dialogue_char:
            self.screen_name = "location"
            return
        ch = self.dialogue_char
        font_btn = get_font(13, bold=True)
        # затемнение
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        # панель диалога
        panel = pygame.Rect(60, 80, WINDOW_WIDTH - 120, WINDOW_HEIGHT - 160)
        draw_panel(self.screen, panel)
        # портрет большой
        port_rect = pygame.Rect(panel.x + 20, panel.y + 20, 90, 90)
        pygame.draw.rect(self.screen, ch["portrait_color"], port_rect, border_radius=10)
        pygame.draw.rect(self.screen, COLOR_ACCENT, port_rect, width=2, border_radius=10)
        init = ch["name"][0]
        txt = get_font(36, bold=True).render(init, True, (255, 255, 255))
        self.screen.blit(txt, txt.get_rect(center=port_rect.center))
        # имя и роль
        name = get_font(20, bold=True).render(ch["name"], True, COLOR_TEXT)
        self.screen.blit(name, (port_rect.right + 15, panel.y + 30))
        role = get_font(13).render(ch["role"] + " • " + ch["bio"], True, COLOR_ACCENT)
        self.screen.blit(role, (port_rect.right + 15, panel.y + 55))
        # допрос
        dialogues = ch.get("dialogue", [])
        if self.dialogue_idx < len(dialogues):
            q = dialogues[self.dialogue_idx]
            # вопрос
            q_rect = pygame.Rect(panel.x + 20, panel.y + 130, panel.w - 40, 50)
            draw_panel(self.screen, q_rect, color=COLOR_ACCENT, border=COLOR_ACCENT)
            # детектив говорит
            det_name = get_font(11, bold=True).render(
                self.state.detective.name.upper() + " :", True, (10, 10, 10)
            )
            self.screen.blit(det_name, (q_rect.x + 12, q_rect.y + 8))
            q_text = get_font(13, bold=True).render(q["q"], True, (10, 10, 10))
            self.screen.blit(q_text, (q_rect.x + 12, q_rect.y + 26))
            # ответ
            a_rect = pygame.Rect(panel.x + 20, q_rect.bottom + 15, panel.w - 40, 120)
            draw_panel(self.screen, a_rect, color=(30, 30, 40))
            draw_text_wrapped(
                self.screen,
                q["a"],
                get_font(14),
                COLOR_TEXT,
                pygame.Rect(a_rect.x + 15, a_rect.y + 15, a_rect.w - 30, a_rect.h - 30),
            )
            # бэкграунд бонус
            if self.state.detective.background == "ex_cop" and ch["location"] == "police":
                bonus = get_font(11).render(
                    "Бонус «Бывший коп»: Сержант Грей делится дополнительным протоколом.",
                    True,
                    COLOR_GREEN,
                )
                self.screen.blit(bonus, (panel.x + 20, a_rect.bottom + 10))
            elif self.state.detective.background == "reporter" and ch["id"] == "barmen":
                bonus2 = get_font(11).render(
                    "Бонус «Репортёр»: Бармен рассказывает больше — вы умеете разговорить.",
                    True,
                    COLOR_GREEN,
                )
                self.screen.blit(bonus2, (panel.x + 20, a_rect.bottom + 10))
        else:
            end_rect = pygame.Rect(panel.x + 20, panel.y + 130, panel.w - 40, 100)
            draw_panel(self.screen, end_rect, color=(30, 30, 40))
            end_text = get_font(14).render(
                "Допрос окончен. Вы узнали всё, что он мог рассказать.", True, COLOR_TEXT_DIM
            )
            self.screen.blit(end_text, end_text.get_rect(center=end_rect.center))
            # возможная улика после допроса — проверим
            # если это Рома и у нас есть ticket — можно дать ключ
            if ch["id"] == "roma" and "clue_ticket" in self.state.collected_clues:
                clue_extra = get_font(12).render(
                    "Получена наводка: Ключ в порту, ящик у 3-го причала!", True, COLOR_ACCENT
                )
                self.screen.blit(clue_extra, (panel.x + 20, end_rect.bottom + 10))
        # кнопки
        y_btn = panel.bottom - 50
        if self.dialogue_idx < len(dialogues):
            btn_next = Button((panel.right - 200, y_btn, 180, 40), "ДАЛЕЕ →", accent=True)
            mouse = self._to_logical(pygame.mouse.get_pos())
            pressed = pygame.mouse.get_pressed()[0]
            btn_next.update(mouse, pressed)
            btn_next.draw(self.screen, font_btn)
            if btn_next.clicked:
                pygame.time.wait(150)
                self.dialogue_idx += 1
            btn_back = Button((panel.x + 20, y_btn, 120, 40), "← НАЗАД")
            btn_back.update(mouse, pressed)
            btn_back.draw(self.screen, font_btn)
            if btn_back.clicked:
                pygame.time.wait(150)
                self.screen_name = "location"
        else:
            btn_close = Button((panel.right - 200, y_btn, 180, 40), "ЗАВЕРШИТЬ", accent=True)
            mouse = self._to_logical(pygame.mouse.get_pos())
            pressed = pygame.mouse.get_pressed()[0]
            btn_close.update(mouse, pressed)
            btn_close.draw(self.screen, font_btn)
            if btn_close.clicked:
                pygame.time.wait(150)
                self.screen_name = "location"
        # прогресс диалога
        prog = get_font(11).render(
            f"{min(self.dialogue_idx + 1, len(dialogues))}/{len(dialogues)}", True, COLOR_TEXT_DARK
        )
        self.screen.blit(prog, prog.get_rect(center=(panel.centerx, y_btn + 20)))

    def draw_notebook(self):
        font_title = get_font(20, bold=True)
        header = pygame.Rect(20, 15, WINDOW_WIDTH - 40, 50)
        draw_panel(self.screen, header)
        t = font_title.render("БЛОКНОТ ДЕТЕКТИВА", True, COLOR_ACCENT)
        self.screen.blit(t, (header.x + 20, header.y + 12))
        # вкладки
        tabs = [("clues", "УЛИКИ"), ("suspects", "ДОСЬЕ"), ("notes", "ЗАМЕТКИ")]
        x = header.right - 350
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
        else:
            self.draw_notebook_notes(main)

    def draw_notebook_clues(self, rect):
        if not self.current_case:
            return
        font_small = get_font(12)
        # заголовок
        title = get_font(14, bold=True).render(
            f"СОБРАНО УЛИК: {len(self.state.collected_clues)}/{len(self.current_case['clues'])}",
            True,
            COLOR_TEXT,
        )
        self.screen.blit(title, (rect.x + 20, rect.y + 15))
        y = rect.y + 45
        # сетка улик
        for clue in self.current_case["clues"]:
            collected = clue["id"] in self.state.collected_clues
            r = pygame.Rect(rect.x + 20, y, rect.w - 40, 70)
            if r.bottom > rect.bottom - 20:
                break
            col = (35, 35, 50) if collected else (25, 25, 30)
            pygame.draw.rect(self.screen, col, r, border_radius=6)
            pygame.draw.rect(
                self.screen,
                COLOR_ACCENT if collected else COLOR_BORDER,
                r,
                width=1,
                border_radius=6,
            )
            status = "✓" if collected else "?"
            status_col = COLOR_GREEN if collected else COLOR_TEXT_DARK
            st = get_font(16, bold=True).render(status, True, status_col)
            self.screen.blit(st, (r.x + 12, r.y + 12))
            t = get_font(13, bold=True).render(
                clue["title"] if collected else "???",
                True,
                COLOR_TEXT if collected else COLOR_TEXT_DARK,
            )
            self.screen.blit(t, (r.x + 40, r.y + 12))
            if collected:
                desc = font_small.render(clue["desc"][:90], True, COLOR_TEXT_DIM)
                self.screen.blit(desc, (r.x + 40, r.y + 32))
                loc = get_location(self.current_case, clue["location"])
                loc_txt = get_font(10).render(
                    f"{loc['name'] if loc else clue['location']}", True, COLOR_ACCENT
                )
                self.screen.blit(loc_txt, (r.x + 40, r.y + 50))
            else:
                hint = font_small.render(
                    "(найдите в локациях — ищите значок лупы)", True, COLOR_TEXT_DARK
                )
                self.screen.blit(hint, (r.x + 40, r.y + 32))
            y += 78

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
        # подозреваемые карточки
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        y = main.y + 50
        for sus in self.current_case.get("suspects", []):
            selected = self.accusation_selected == sus["id"]
            r = pygame.Rect(main.x + 20, y, main.w - 40, 100)
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
            self.screen.blit(name, (r.x + 20, r.y + 15))
            motive = get_font(11).render(
                sus["motive"], True, (10, 10, 10) if selected else COLOR_TEXT_DIM
            )
            self.screen.blit(motive, (r.x + 20, r.y + 40))
            # кликабельность
            if r.collidepoint(mouse) and pressed:
                pygame.time.wait(150)
                self.accusation_selected = sus["id"]
            # галочка
            if selected:
                chk = get_font(20, bold=True).render("✓", True, (10, 10, 10))
                self.screen.blit(chk, (r.right - 40, r.y + 20))
            y += 110
        # кнопки
        btn_back = Button((main.x + 20, main.bottom - 50, 160, 40), "← ОТМЕНА")
        can_confirm = self.accusation_selected is not None
        btn_confirm = Button(
            (main.right - 200, main.bottom - 50, 180, 40),
            "ОБВИНИТЬ!",
            accent=True,
            enabled=can_confirm,
        )
        for btn, act in [(btn_back, "back"), (btn_confirm, "confirm")]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(13, bold=True))
            if btn.clicked:
                pygame.time.wait(150)
                if act == "back":
                    self.screen_name = "map"
                else:
                    # финал
                    self.state.accusation_result = self.accusation_selected
                    # проверяем правильность
                    suspect = next(
                        (
                            s
                            for s in self.current_case["suspects"]
                            if s["id"] == self.accusation_selected
                        ),
                        None,
                    )
                    self.state.accusation_correct = bool(suspect and suspect.get("is_culprit"))
                    self.state.case_state = "finished"
                    save_game(self.state)
                    self.screen_name = "ending"

    def draw_ending(self):
        if not self.current_case:
            return
        ending_data = self.current_case.get("endings", {}).get(self.state.accusation_result, {})
        success = ending_data.get("success", False)
        title = ending_data.get("title", "Финал")
        text = ending_data.get("text", "История окончена.")
        rank = ending_data.get("rank", "?")
        # фон
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.fill((10, 10, 14) if success else (20, 10, 10))
        self.screen.blit(overlay, (0, 0))
        # панель
        panel = pygame.Rect(WINDOW_WIDTH // 2 - 380, WINDOW_HEIGHT // 2 - 260, 760, 520)
        draw_panel(self.screen, panel)
        # ранг
        rank_font = get_font(56, bold=True)
        rank_col = COLOR_GREEN if success else COLOR_RED
        rank_surf = rank_font.render(f"РАНГ {rank}", True, rank_col)
        self.screen.blit(rank_surf, rank_surf.get_rect(center=(panel.centerx, panel.y + 50)))
        result_col = COLOR_GREEN if success else COLOR_RED
        result_text = "ДЕЛО РАСКРЫТО" if success else "ПРОВАЛ"
        res_font = get_font(28, bold=True)
        res = res_font.render(result_text, True, result_col)
        self.screen.blit(res, res.get_rect(center=(panel.centerx, panel.y + 95)))
        tit = get_font(18, bold=True).render(title, True, COLOR_TEXT)
        self.screen.blit(tit, tit.get_rect(center=(panel.centerx, panel.y + 125)))
        # текст финала
        text_rect = pygame.Rect(panel.x + 30, panel.y + 150, panel.w - 60, 250)
        draw_panel(self.screen, text_rect, color=(22, 22, 30))
        draw_text_wrapped(
            self.screen,
            text,
            get_font(14),
            COLOR_TEXT,
            pygame.Rect(text_rect.x + 15, text_rect.y + 15, text_rect.w - 30, text_rect.h - 30),
        )
        # статистика
        stats = get_font(12).render(
            f"Улик собрано: {len(self.state.collected_clues)}/{len(self.current_case['clues'])} • Время: {self.state.case_time_minutes} мин • Детектив: {self.state.detective.name} ({self.state.detective.background_label})",
            True,
            COLOR_TEXT_DIM,
        )
        self.screen.blit(stats, stats.get_rect(center=(panel.centerx, panel.y + 420)))
        # кнопки
        mouse = self._to_logical(pygame.mouse.get_pos())
        pressed = pygame.mouse.get_pressed()[0]
        btn_menu = Button((panel.x + 40, panel.bottom - 50, 200, 40), "В МЕНЮ")
        btn_replay = Button(
            (panel.centerx + 20, panel.bottom - 50, 200, 40), "СЫГРАТЬ ЕЩЁ", accent=True
        )
        for btn, act in [(btn_menu, "menu"), (btn_replay, "replay")]:
            btn.update(mouse, pressed)
            btn.draw(self.screen, get_font(13, bold=True))
            if btn.clicked:
                pygame.time.wait(150)
                if act == "menu":
                    self.screen_name = "menu"
                else:
                    # рестарт кейса
                    self.start_case(self.current_case["id"])
                    self.screen_name = "map"

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
        btn_cancel = Button(layout.reset, "СБРОСИТЬ")
        btn_cancel.update(mouse, pressed)
        btn_cancel.draw(self.screen, get_font(11, bold=True))
        if btn_cancel.clicked:
            self._init_settings_widgets()
            self.add_notification("Изменения сброшены")
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
        ry += 50
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
                if btn_install.clicked:
                    self._install_update()
                btn_folder = Button((upd_rect.x + 160, upd_rect.y + 58, 80, 26), "Папка")
                btn_folder.update(mouse, pressed)
                btn_folder.draw(self.screen, get_font(8, bold=True))
                if btn_folder.clicked:
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
                if btn_dl.clicked:
                    checker.start_download()
                    self.add_notification("Загрузка началась...")
                btn_later = Button((upd_rect.x + 142, upd_rect.y + 46, 90, 28), "Позже")
                btn_later.update(mouse, pressed)
                btn_later.draw(self.screen, get_font(9, bold=True))
                if btn_later.clicked:
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
            if btn_retry.clicked:
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
            if btn_retry.clicked:
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
            # Подтверждение через уведомление + таймер? Пока сразу
            delete_save()
            self.state = GameState(detective=self.state.detective)
            save_game(self.state)
            self.add_notification("Прогресс сброшен — начинаем заново")

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
            if btn_retry.clicked:
                self._retry_update_check()
                return
            btn_log = Button((rect.right - 150, rect.y + 15, 90, 30), "Журнал")
            btn_log.update(mouse, pressed)
            btn_log.draw(self.screen, get_font(8, bold=True))
            if btn_log.clicked:
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
                if btn_inst.clicked:
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
            if btn_install.clicked:
                self._install_update()
            btn_open = Button((rect.right - 60, rect.y + 12, 40, 26), "Папка")
            btn_open.update(mouse, pressed)
            btn_open.draw(self.screen, get_font(8, bold=True))
            if btn_open.clicked:
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
            if btn_dl.clicked:
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
