"""Проверка и загрузка обновлений через GitHub Releases — с установкой из приложения."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlretrieve

try:
    import requests
except ImportError:
    requests = None

from . import __version__
from .config import GITHUB_API_LATEST, GITHUB_RELEASES_URL, GITHUB_REPO


def _parse_version(v: str) -> Tuple[int, ...]:
    v = v.lstrip("vV").strip()
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
    """Находит URL для скачивания Windows сборки."""
    assets = release_data.get("assets", [])
    # Приоритет: Full.zip > Windows.zip > первый zip
    for name in ["DetectiveBlackville-Full.zip", "DetectiveBlackville-Windows.zip"]:
        for asset in assets:
            if asset.get("name") == name:
                return asset.get("browser_download_url")
    for asset in assets:
        if asset.get("name", "").endswith(".zip"):
            return asset.get("browser_download_url")
    # Fallback к самому релизу
    return release_data.get("html_url")

def check_for_updates(timeout: float = 5.0) -> Optional[dict]:
    """Синхронная проверка. Возвращает dict с информацией о релизе или None."""
    if requests is None:
        return None
    try:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Blackville-Detective-Game"}
        resp = requests.get(GITHUB_API_LATEST, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        tag = data.get("tag_name", "")
        if not tag:
            return None
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
    except Exception as e:
        print(f"[Updater] check failed: {e}")
        return None

def download_update(url: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[Path]:
    """Скачивает обновление, возвращает путь к файлу или None. Поддерживает прогресс."""
    if not url or not url.startswith("http"):
        return None
    # Если это страница релиза, а не прямая ссылка — открываем браузер
    if "github.com" in url and "/releases/tag/" in url and not url.endswith(".zip"):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
        return None
    
    try:
        # Определяем имя файла
        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith(".zip"):
            filename = f"DetectiveBlackville-Update-{__version__}.zip"
        
        # Папка загрузки — Downloads или TEMP
        download_dir = Path.home() / "Downloads"
        if not download_dir.exists():
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
                resp = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Blackville-Detective-Game"})
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
                resp = requests.get(url, stream=True, timeout=30)
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

class UpdateChecker:
    """Асинхронная обёртка, чтобы не блокировать UI. Теперь с поддержкой скачивания."""
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
        self.download_error: Optional[str] = None

    def start(self):
        if self.checking or self.done:
            return
        self.checking = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            self.result = check_for_updates()
        except Exception as e:
            self.error = str(e)
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
