"""Проверка и загрузка обновлений через GitHub Releases — с установкой из приложения."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple
from urllib.request import urlretrieve

try:
    import requests
except ImportError:
    requests = None

from . import __version__
from .config import GITHUB_API_LATEST, GITHUB_RELEASES_URL, GITHUB_REPO

UPDATE_LOG_NAME = "blackville_update.log"
UPDATE_STATE_FILE = "update_state.json"
_HTTP_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Blackville-Detective-Game",
}


class UpdateCheckError(RuntimeError):
    """Проверка обновлений не удалась: нет сети, лимит GitHub, битый ответ."""


def _parse_version(v: str) -> Tuple[int, ...]:
    v = str(v).lstrip("vV").strip()
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p.split("-")[0]))  # игнорируем -beta суффиксы
        except ValueError:
            parts.append(0)
    return tuple(parts)

def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)

def _find_download_url(release_data: dict) -> Optional[str]:
    """Находит URL для скачивания Windows сборки. Приоритет: Setup.exe > Full.zip > Windows.zip."""
    assets = release_data.get("assets", []) or []
    # 1. Инсталлятор — лучший вариант для автообновления (ставится в Program Files, ярлыки, uninstall)
    for asset in assets:
        name = asset.get("name") or ""
        if name.startswith("DetectiveBlackville-Setup-") and name.endswith(".exe"):
            return asset.get("browser_download_url")
    # На случай если имя без версии — любой Setup exe
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if "setup" in name and name.endswith(".exe"):
            return asset.get("browser_download_url")
    # 2. Full.zip / Windows.zip — fallback (портативка)
    for name in ["DetectiveBlackville-Full.zip", "DetectiveBlackville-Windows.zip"]:
        for asset in assets:
            if asset.get("name") == name:
                return asset.get("browser_download_url")
    for asset in assets:
        if (asset.get("name") or "").endswith(".zip"):
            return asset.get("browser_download_url")
    # Fallback к самому релизу
    return release_data.get("html_url")

def _http_get_json(url: str, timeout: float) -> dict:
    """GET JSON с GitHub. requests — если есть, иначе stdlib (чтобы обновления работали всегда)."""
    if requests is not None:
        try:
            resp = requests.get(url, headers=_HTTP_HEADERS, timeout=timeout)
        except Exception as e:
            raise UpdateCheckError(f"нет связи с GitHub ({e})") from e
        if resp.status_code != 200:
            raise UpdateCheckError(f"GitHub вернул HTTP {resp.status_code}")
        try:
            return resp.json()
        except Exception as e:
            raise UpdateCheckError(f"некорректный ответ GitHub ({e})") from e
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    try:
        with urlopen(Request(url, headers=_HTTP_HEADERS), timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise UpdateCheckError(f"GitHub вернул HTTP {e.code}") from e
    except Exception as e:
        raise UpdateCheckError(f"нет связи с GitHub ({e})") from e
    try:
        return json.loads(payload)
    except Exception as e:
        raise UpdateCheckError(f"некорректный ответ GitHub ({e})") from e

def check_for_updates(timeout: float = 6.0) -> Optional[dict]:
    """Синхронная проверка.

    Возвращает dict с информацией о релизе или None, если у пользователя
    последняя версия. При сетевой/серверной ошибке поднимает UpdateCheckError —
    вызывающий код обязан показать её игроку, а не «у вас последняя версия».
    """
    data = _http_get_json(GITHUB_API_LATEST, timeout)
    if not isinstance(data, dict):
        raise UpdateCheckError("некорректный ответ GitHub")
    tag = data.get("tag_name", "")
    if not tag:
        raise UpdateCheckError("в релизе нет тега версии")
    if is_newer(tag, __version__):
        download_url = _find_download_url(data)
        return {
            "current": __version__,
            "latest": tag.lstrip("v"),
            "tag": tag,
            "name": data.get("name", tag),
            "url": data.get("html_url", GITHUB_RELEASES_URL),
            "download_url": download_url,
            "body": (data.get("body", "") or "")[:2000],
            "published": data.get("published_at", ""),
            "assets": data.get("assets", []),
        }
    return None

def download_update(url: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[Path]:
    """Скачивает обновление, возвращает путь к файлу или None. Поддерживает прогресс."""
    if not url or not url.startswith("http"):
        return None
    # Если это страница релиза, а не прямая ссылка — открываем браузер
    is_direct = url.endswith(".zip") or url.endswith(".exe")
    if "github.com" in url and "/releases/tag/" in url and not is_direct:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
        return None

    try:
        # Определяем имя файла
        filename = url.split("/")[-1].split("?")[0]
        # Поддерживаем .exe и .zip
        if not (filename.endswith(".zip") or filename.endswith(".exe")):
            # если имя не распознали — fallback
            ext = ".exe" if ".exe" in url.lower() else ".zip"
            filename = f"DetectiveBlackville-Update-{__version__}{ext}"

        # Папка загрузки — Downloads (если есть) или TEMP
        download_dir = Path.home() / "Downloads"
        if not download_dir.exists() or not os.access(download_dir, os.W_OK):
            download_dir = Path(tempfile.gettempdir())

        dest = download_dir / filename
        # Если уже есть — перезаписываем
        if dest.exists():
            try:
                dest.unlink()
            except Exception:
                dest = download_dir / f"update-{filename}"

        print(f"[Updater] Downloading {url} -> {dest}")

        if progress_callback:
            # С requests и прогрессией
            if requests:
                resp = requests.get(url, stream=True, timeout=60, headers=_HTTP_HEADERS)
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            try:
                                progress_callback(downloaded, total)
                            except Exception:
                                pass
            else:
                urlretrieve(url, str(dest))
        else:
            if requests:
                resp = requests.get(url, stream=True, timeout=60, headers=_HTTP_HEADERS)
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            else:
                urlretrieve(url, str(dest))

        if dest.exists() and dest.stat().st_size > 1000:
            return dest
        return None
    except Exception as e:
        print(f"[Updater] download failed: {e}")
        return None

def open_download_folder(path: Path):
    """Открывает папку с загруженным файлом."""
    try:
        if sys.platform == "win32":
            # Выделяем файл в проводнике
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except Exception as e:
        print(f"[Updater] open folder failed: {e}")
        try:
            import webbrowser
            webbrowser.open(str(path.parent))
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Установка: куда ставим, можно ли тихо, журнал и результат
# ---------------------------------------------------------------------------

def get_install_dir() -> Optional[Path]:
    """Папка, из которой запущена игра (для frozen-сборки) — цель обновления.

    Раньше апдейтер не передавал инсталлятору /DIR, и тот молча ставил новую
    копию в %LOCALAPPDATA%\\Programs (или в Program Files). Пользователь же
    продолжал запускать старый exe (например, распакованный из zip) и видел,
    что «игра не обновилась».
    """
    if not getattr(sys, "frozen", False):
        return None
    try:
        return Path(sys.executable).resolve().parent
    except Exception:
        return None

def is_dir_writable(path: Path) -> bool:
    """Можно ли записать файл в папку без прав администратора."""
    try:
        path = Path(path)
        if not path.is_dir():
            return False
        probe = path / f".blackville_write_test_{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False

def should_install_silently(install_dir: Optional[Path] = None) -> bool:
    """Тихая установка возможна, только если текущая папка доступна на запись.

    Иначе (Program Files, установка «для всех пользователей») нужен видимый
    мастер и подтверждение UAC — молчаливый запуск там просто тихо падал.
    """
    if sys.platform != "win32":
        return True
    target = install_dir if install_dir is not None else get_install_dir()
    if target is None:
        return False
    return is_dir_writable(target)

def install_requires_elevation(install_dir: Optional[Path] = None) -> bool:
    """True, если для установки в текущую папку нужны права администратора."""
    if sys.platform != "win32":
        return False
    target = install_dir if install_dir is not None else get_install_dir()
    if target is None:
        return False
    return not is_dir_writable(target)

def get_update_log_path() -> Path:
    return Path(tempfile.gettempdir()) / UPDATE_LOG_NAME

def build_installer_args(
    installer: Path,
    silent: bool = True,
    autolaunch: bool = True,
    install_dir: Optional[Path] = None,
    log_path: Optional[Path] = None,
) -> List[str]:
    """Аргументы Inno Setup для обновления текущей копии игры."""
    args: List[str] = []
    if silent:
        args += ["/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART"]
    if autolaunch:
        args.append("/AUTOLAUNCH=1")
    if install_dir:
        args.append(f'/DIR="{install_dir}"')
    if log_path:
        args.append(f'/LOG="{log_path}"')
    return args

def _update_state_path() -> Path:
    from .save_system import get_save_dir

    return get_save_dir() / UPDATE_STATE_FILE

def write_pending_update(target_version: str, installer: Path, log_path: Optional[Path] = None) -> None:
    """Запоминает, что установка запущена — при следующем старте покажем итог."""
    if not target_version:
        return
    try:
        path = _update_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "target_version": target_version,
                    "from_version": __version__,
                    "installer": str(installer),
                    "log": str(log_path) if log_path else "",
                    "started_at": time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Updater] cannot write update state: {e}")

def consume_update_result() -> Optional[dict]:
    """Возвращает итог прошлой установки (и удаляет маркер обновления).

    {"status": "installed"|"failed", "target": "0.1.24", "current": "0.1.24", "log": "..."}
    """
    path = _update_state_path()
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    target = str(data.get("target_version") or "").strip().lstrip("vV")
    if not target:
        return None
    status = "failed" if is_newer(target, __version__) else "installed"
    return {
        "status": status,
        "target": target,
        "current": __version__,
        "log": data.get("log", ""),
        "installer": data.get("installer", ""),
    }

def _create_windows_update_helper(
    installer_path: Path,
    args: Sequence[str],
    install_dir: Optional[Path] = None,
    autolaunch: bool = True,
) -> Optional[Path]:
    """Временный bat-помощник: ждёт выхода игры и запускает инсталлятор.

    Пути передаются через переменные окружения, а не вписываются в текст bat:
    иначе кириллица в C:\\Users\\Иван\\... превращалась в кракозябры и установка
    молча не срабатывала. Сам bat — чистый ASCII.
    """
    try:
        tmp_dir = Path(tempfile.gettempdir())
        bat_path = tmp_dir / f"blackville_update_{os.getpid()}.bat"
        log_path = get_update_log_path()

        bat_content = r"""@echo off
setlocal
if not defined BLK_INSTALLER exit /b 1
:waitgame
if defined BLK_PID (
  tasklist /FI "PID eq %BLK_PID%" 2>nul | find "%BLK_PID%" >nul
  if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitgame
  )
)
timeout /t 1 /nobreak >nul
start "" /wait "%BLK_INSTALLER%" %BLK_ARGS%
timeout /t 1 /nobreak >nul
if defined BLK_EXE (
  if exist "%BLK_EXE%" (
    tasklist /FI "IMAGENAME eq %BLK_EXENAME%" 2>nul | find /I "%BLK_EXENAME%" >nul
    if errorlevel 1 start "" "%BLK_EXE%"
  )
)
(goto) 2>nul & del "%~f0"
"""
        bat_path.write_text(bat_content, encoding="ascii", errors="ignore")

        env = dict(os.environ)
        env["BLK_INSTALLER"] = str(installer_path)
        env["BLK_ARGS"] = " ".join(args)
        env["BLK_PID"] = str(os.getpid())
        if install_dir:
            env["BLK_EXE"] = str(Path(install_dir) / "DetectiveBlackville.exe")
            env["BLK_EXENAME"] = "DetectiveBlackville.exe"
        if log_path:
            env["BLK_LOG"] = str(log_path)
        print(f"[Updater] helper: {bat_path} (installer={installer_path}, args={env['BLK_ARGS']})")
        return bat_path
    except Exception as e:
        print(f"[Updater] helper create failed: {e}")
        return None

def _launch_elevated(exe: Path, args: Sequence[str]) -> bool:
    """Запуск инсталлятора с запросом UAC (нельзя молча писать в Program Files)."""
    try:
        import ctypes

        params = " ".join(str(a) for a in args)
        print(f"[Updater] elevated launch: {exe} {params}")
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(exe), params, None, 1)
        # >32 — успех; 5 — пользователь отменил UAC
        return int(rc) > 32
    except Exception as e:
        print(f"[Updater] elevated launch failed: {e}")
        return False

def run_installer(
    path: Path,
    silent: Optional[bool] = None,
    autolaunch: bool = True,
    install_dir: Optional[Path] = None,
    target_version: Optional[str] = None,
) -> bool:
    """Запускает установщик обновления и ставит его в текущую папку игры.

    silent=None — выбрать автоматически: тихо, если папка игры доступна на
    запись, иначе интерактивный мастер с UAC.

    Возвращает True если запуск успешен. Вызывающий код должен сразу выйти:
        if run_installer(p): pygame.quit(); sys.exit(0)
    """
    try:
        if not path:
            print("[Updater] installer not found: None")
            return False
        p = Path(path)
        if not p.exists():
            print(f"[Updater] installer not found: {p}")
            return False

        if p.suffix.lower() != ".exe":
            # .zip и прочее — инсталлятор не запускаем, только показываем файл
            open_download_folder(p)
            return False

        target = install_dir if install_dir is not None else get_install_dir()
        if silent is None:
            silent = should_install_silently(target)

        log_path = get_update_log_path()
        args = build_installer_args(p, silent=silent, autolaunch=autolaunch, install_dir=target, log_path=log_path)
        print(f"[Updater] Launching installer: {p} {args} (silent={silent}, dir={target})")

        started = False
        if sys.platform == "win32":
            if silent:
                helper = _create_windows_update_helper(p, args, install_dir=target, autolaunch=autolaunch)
                if helper:
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", str(helper)],
                        creationflags=0x00000008,  # DETACHED_PROCESS
                        close_fds=True,
                    )
                    started = True
                else:
                    subprocess.Popen([str(p), *args], creationflags=0x00000008, close_fds=True)
                    started = True
            elif target is not None and not is_dir_writable(target):
                # Program Files: нужен видимый UAC, иначе установка молча провалится
                started = _launch_elevated(p, args)
            else:
                try:
                    subprocess.Popen([str(p), *args], creationflags=0x00000008, close_fds=True)
                except TypeError:
                    subprocess.Popen([str(p), *args])
                started = True
        else:
            subprocess.Popen([str(p), *args])
            started = True

        if started:
            write_pending_update(target_version or "", p, log_path)
        return started
    except Exception as e:
        print(f"[Updater] run_installer failed: {e}")
        return False

def install_downloaded_update(
    path: Path,
    silent: Optional[bool] = None,
    target_version: Optional[str] = None,
) -> bool:
    """Запускает установщик и завершает текущее приложение для обновления.

    Рекомендуемый вызов из UI:
        if updater.install_downloaded_update(updater.downloaded_path):
            pygame.quit(); sys.exit(0)
    """
    ok = run_installer(path, silent=silent, autolaunch=True, target_version=target_version)
    if ok:
        try:
            time.sleep(0.5)
        except Exception:
            pass
    return ok

class UpdateChecker:
    """Асинхронная обёртка, чтобы не блокировать UI. Теперь с поддержкой скачивания и установки."""
    def __init__(self):
        self.result: Optional[dict] = None
        self.checking: bool = False
        self.done: bool = False
        self.error: Optional[str] = None
        # Для загрузки
        self.downloading: bool = False
        self.download_progress: int = 0  # 0-100
        self.download_total: int = 0
        self.downloaded_path: Optional[Path] = None
        self.download_target_version: str = ""
        self.download_error: Optional[str] = None

    @property
    def up_to_date(self) -> bool:
        return self.done and not self.result and not self.error

    def start(self):
        if self.checking or self.done:
            return
        self.checking = True
        self.error = None
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            self.result = check_for_updates()
        except UpdateCheckError as e:
            self.error = str(e)
            print(f"[Updater] check failed: {e}")
        except Exception as e:
            self.error = f"неизвестная ошибка: {e}"
            print(f"[Updater] check failed: {e}")
        finally:
            self.checking = False
            self.done = True

    def start_download(self, progress_callback: Optional[Callable] = None):
        """Начинает загрузку в фоновом потоке."""
        if not self.result or not self.result.get("download_url"):
            self.download_error = "Нет ссылки для загрузки"
            return
        if self.downloading:
            return
        self.downloading = True
        self.download_error = None
        self.download_progress = 0
        self.download_target_version = self.result.get("latest", "")

        def _download():
            try:
                def progress(downloaded, total):
                    self.download_total = total
                    if total > 0:
                        self.download_progress = int(downloaded / total * 100)
                    if progress_callback:
                        try:
                            progress_callback(downloaded, total)
                        except Exception:
                            pass

                url = self.result["download_url"]
                path = download_update(url, progress_callback=progress)
                if path:
                    self.downloaded_path = path
                    self.download_progress = 100
                else:
                    self.download_error = "Не удалось скачать — открыта страница релиза"
            except Exception as e:
                self.download_error = str(e)
            finally:
                self.downloading = False

        t = threading.Thread(target=_download, daemon=True)
        t.start()

    def install(self, silent: Optional[bool] = None) -> bool:
        """Запускает установку загруженного обновления с автозапуском.

        silent=None — тихо, если папка игры доступна на запись, иначе мастер + UAC.
        """
        if not self.downloaded_path or not self.downloaded_path.exists():
            self.download_error = "Файл обновления не найден"
            return False
        version = self.download_target_version or (self.result or {}).get("latest", "")
        return run_installer(
            self.downloaded_path, silent=silent, autolaunch=True, target_version=version
        )
