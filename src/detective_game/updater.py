"""Проверка обновлений через GitHub Releases."""
import threading
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

from . import __version__
from .config import GITHUB_API_LATEST, GITHUB_RELEASES_URL


def _parse_version(v: str) -> Tuple[int, ...]:
    v = v.lstrip("vV").strip()
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)

def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)

def check_for_updates(timeout: float = 4.0) -> Optional[dict]:
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
            return {
                "current": __version__,
                "latest": tag.lstrip("v"),
                "tag": tag,
                "name": data.get("name", tag),
                "url": data.get("html_url", GITHUB_RELEASES_URL),
                "body": data.get("body", "")[:600],
                "published": data.get("published_at", ""),
            }
        return None
    except Exception:
        return None

class UpdateChecker:
    """Асинхронная обёртка, чтобы не блокировать UI."""
    def __init__(self):
        self.result: Optional[dict] = None
        self.checking: bool = False
        self.done: bool = False
        self.error: Optional[str] = None

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
