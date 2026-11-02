"""Проверка и загрузка обновлений через GitHub Releases — с установкой из приложения.

Сеть бывает разной: корпоративный прокси, антивирус с подменой сертификата,
лимит GitHub API, заблокированный api.github.com. Поэтому проверка идёт
несколькими независимыми путями, а каждый сбой пишется в журнал
``%APPDATA%/BlackvilleDetective/update.log`` — игрок всегда видит причину.
"""

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, urlopen

try:
    import requests
except ImportError:  # сборка без requests — работаем на stdlib
    requests = None

try:
    import certifi
except ImportError:
    certifi = None

from . import __version__
from .config import GITHUB_API_LATEST, GITHUB_RELEASES_URL, GITHUB_REPO

UPDATE_LOG_NAME = "blackville_update.log"  # журнал инсталлятора (во временной папке)
APP_LOG_NAME = "update.log"  # журнал апдейтера (рядом с сохранениями)
UPDATE_STATE_FILE = "update_state.json"
SETUP_ASSET_TEMPLATE = "DetectiveBlackville-Setup-{version}.exe"
LATEST_JSON_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/latest.json"
LATEST_REDIRECT_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
_HTTP_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Blackville-Detective-Game",
}


class UpdateCheckError(RuntimeError):
    """Проверка обновлений не удалась: нет сети, лимит GitHub, битый ответ."""


# ---------------------------------------------------------------------------
# Журнал: без него в windowed-сборке ошибки некуда посмотреть
# ---------------------------------------------------------------------------


def get_app_log_path() -> Path:
    """Журнал апдейтера рядом с сохранениями (переживает перезапуск игры)."""
    try:
        from .save_system import get_save_dir

        return get_save_dir() / APP_LOG_NAME
    except Exception:
        return Path(tempfile.gettempdir()) / APP_LOG_NAME


def log_update(message: str) -> None:
    """Пишет строку в журнал апдейтера и в stdout (если он есть)."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        print(f"[Updater] {message}")
    except Exception:
        pass
    try:
        path = get_app_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 256 * 1024:
            tail = path.read_text(encoding="utf-8", errors="replace")[-64 * 1024 :]
            path.write_text(tail, encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_app_log(limit: int = 8000) -> str:
    try:
        return get_app_log_path().read_text(encoding="utf-8", errors="replace")[-limit:]
    except Exception:
        return ""


def open_app_log() -> bool:
    """Открывает журнал апдейтера системным редактором."""
    path = get_app_log_path()
    try:
        if not path.exists():
            log_update("журнал создан по запросу из настроек")
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception as e:
        log_update(f"не удалось открыть журнал: {e}")
        return False


# ---------------------------------------------------------------------------
# HTTP: requests -> urllib (системные сертификаты) -> без проверки (крайний случай)
# ---------------------------------------------------------------------------


def _certifi_bundle() -> Optional[str]:
    if certifi is None:
        return None
    try:
        path = certifi.where()
        return path if os.path.exists(path) else None
    except Exception:
        return None


def _requests_get(url: str, timeout: float, **kwargs):
    """GET через requests; на SSL-ошибке честно сообщаем, что дело в сертификате."""
    if requests is None:
        raise UpdateCheckError("requests недоступен")
    verify = _certifi_bundle()
    try:
        if verify:
            return requests.get(url, timeout=timeout, verify=verify, **kwargs)
        return requests.get(url, timeout=timeout, **kwargs)
    except Exception as e:
        name = type(e).__name__
        if "SSL" in name or "SSL" in str(e):
            raise UpdateCheckError(f"SSL-сертификат не проверяется ({name})") from e
        raise UpdateCheckError(f"нет связи с GitHub ({name}: {e})") from e


def _urllib_get(url: str, timeout: float, *, insecure: bool = False, headers=None):
    """GET через stdlib. На Windows использует системные сертификаты."""
    ctx = ssl._create_unverified_context() if insecure else None
    req = Request(url, headers={**_HTTP_HEADERS, **(headers or {})})
    try:
        return urlopen(req, timeout=timeout, context=ctx)
    except HTTPError:
        raise
    except URLError as e:
        reason = getattr(e, "reason", e)
        if "CERTIFICATE" in str(reason).upper() or "SSL" in str(reason).upper():
            raise UpdateCheckError(f"SSL-сертификат не проверяется ({reason})") from e
        raise UpdateCheckError(f"нет связи с GitHub ({reason})") from e
    except Exception as e:
        if "CERTIFICATE" in str(e).upper() or "SSL" in str(e).upper():
            raise UpdateCheckError(f"SSL-сертификат не проверяется ({e})") from e
        raise UpdateCheckError(f"нет связи с GitHub ({e})") from e


def http_get_bytes(
    url: str,
    timeout: float = 6.0,
    *,
    allow_insecure: bool = True,
    headers: Optional[Dict[str, str]] = None,
    allow_redirects: bool = True,
) -> Tuple[bytes, str, bool]:
    """Скачивает URL, перебирая способы доступа.

    Возвращает ``(данные, способ, insecure)``. Порядок: requests → urllib
    (системные сертификаты) → urllib без проверки сертификата. Последний вариант
    включается только для чтения метаданных о релизе, и это пишется в журнал.
    """
    errors: List[str] = []

    # 1. requests (быстро, но зависит от бандла certifi)
    if requests is not None:
        try:
            resp = _requests_get(url, timeout, allow_redirects=allow_redirects, headers=headers)
            if resp.status_code >= 400:
                raise UpdateCheckError(f"HTTP {resp.status_code}")
            return resp.content, "requests", False
        except UpdateCheckError as e:
            errors.append(f"requests: {e}")
            log_update(f"{url} — {errors[-1]}")

    # 2. urllib с проверкой сертификата (системное хранилище Windows)
    try:
        with _urllib_get(url, timeout, headers=headers) as resp:
            return resp.read(), "urllib", False
    except HTTPError as e:
        raise UpdateCheckError(f"HTTP {e.code}") from e
    except UpdateCheckError as e:
        errors.append(f"urllib: {e}")
        log_update(f"{url} — {errors[-1]}")

    # 3. крайний случай — без проверки сертификата (антивирус/прокси MITM)
    if allow_insecure:
        try:
            with _urllib_get(url, timeout, insecure=True, headers=headers) as resp:
                log_update(f"{url} — скачано БЕЗ проверки сертификата")
                return resp.read(), "urllib-insecure", True
        except Exception as e:
            errors.append(f"urllib-insecure: {e}")
            log_update(f"{url} — {errors[-1]}")

    raise UpdateCheckError("; ".join(errors) if errors else "не удалось подключиться")


def http_get_json(url: str, timeout: float = 6.0, **kwargs) -> Tuple[dict, bool]:
    payload, via, insecure = http_get_bytes(url, timeout, **kwargs)
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception as e:
        raise UpdateCheckError(f"некорректный ответ GitHub ({e})") from e
    if not isinstance(data, dict):
        raise UpdateCheckError("некорректный ответ GitHub (ожидался объект)")
    log_update(f"{url} — ok ({via}{', без проверки сертификата' if insecure else ''})")
    return data, insecure


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


def _find_sums_url(release_data: dict) -> Optional[str]:
    for asset in release_data.get("assets", []) or []:
        if (asset.get("name") or "") == "SHA256SUMS.txt":
            return asset.get("browser_download_url")
    return None


def build_release_download_url(tag: str, version: str) -> str:
    """Прямая ссылка на Setup.exe по тегу — работает и без GitHub API."""
    return (
        f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/"
        f"{SETUP_ASSET_TEMPLATE.format(version=version)}"
    )


def _release_info(tag: str, version: str, *, name: str = "", url: str = "", source: str = "") -> dict:
    return {
        "current": __version__,
        "latest": version,
        "tag": tag if tag.startswith("v") else f"v{version}",
        "name": name or f"Детектив: Блэквил v{version}",
        "url": url or f"{GITHUB_RELEASES_URL}/tag/v{version}",
        "download_url": build_release_download_url(tag if tag.startswith("v") else f"v{version}", version),
        "sums_url": (
            f"https://github.com/{GITHUB_REPO}/releases/download/"
            f"{tag if tag.startswith('v') else 'v' + version}/SHA256SUMS.txt"
        ),
        "body": "",
        "published": "",
        "assets": [],
        "source": source,
        "insecure": False,
    }


def _check_via_api(timeout: float) -> Optional[dict]:
    data, insecure = http_get_json(GITHUB_API_LATEST, timeout)
    tag = data.get("tag_name", "")
    if not tag:
        raise UpdateCheckError("в ответе API нет тега версии")
    if not is_newer(tag, __version__):
        return None
    info = _release_info(
        tag,
        tag.lstrip("vV"),
        name=data.get("name", tag),
        url=data.get("html_url", GITHUB_RELEASES_URL),
        source="api",
    )
    info["download_url"] = _find_download_url(data)
    info["sums_url"] = _find_sums_url(data) or info["sums_url"]
    info["body"] = (data.get("body", "") or "")[:2000]
    info["published"] = data.get("published_at", "")
    info["assets"] = data.get("assets", [])
    info["insecure"] = insecure
    return info


def _check_via_latest_json(timeout: float) -> Optional[dict]:
    """latest.json из ассетов последнего релиза — не расходует лимит API."""
    data, insecure = http_get_json(LATEST_JSON_URL, timeout)
    version = str(data.get("version") or data.get("tag") or "").lstrip("vV")
    if not version:
        raise UpdateCheckError("в latest.json нет версии")
    if not is_newer(version, __version__):
        return None
    info = _release_info(
        f"v{version}",
        version,
        name=str(data.get("name") or ""),
        url=str(data.get("url") or ""),
        source="latest.json",
    )
    info["body"] = str(data.get("notes") or "")[:2000]
    info["published"] = str(data.get("published_at") or "")
    info["insecure"] = insecure
    return info


try:
    from urllib.request import HTTPRedirectHandler

    class _NoRedirect(HTTPRedirectHandler):
        """Запрещает следовать редиректам — нужен только заголовок 302/301."""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

except Exception:  # pragma: no cover - защита от экзотических сборок
    _NoRedirect = None


def _latest_tag_from_redirect(timeout: float) -> Optional[str]:
    """Тег последнего релиза из редиректа github.com/<repo>/releases/latest."""
    if requests is not None:
        try:
            resp = _requests_get(LATEST_REDIRECT_URL, timeout, allow_redirects=False)
            location = resp.headers.get("Location", "")
            if location:
                tag = location.rstrip("/").split("/")[-1]
                if tag.startswith("v"):
                    return tag
        except UpdateCheckError as e:
            log_update(f"redirect (requests): {e}")
    try:
        req = Request(LATEST_REDIRECT_URL, headers=_HTTP_HEADERS, method="HEAD")
        opener = build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=timeout) as resp:
                location = resp.headers.get("Location", "")
        except HTTPError as e:  # 302 приходит как HTTPError у NoRedirect
            location = e.headers.get("Location", "") if e.headers else ""
        if location:
            tag = location.rstrip("/").split("/")[-1]
            if tag.startswith("v"):
                return tag
    except Exception as e:
        log_update(f"redirect (urllib): {e}")
    return None


def _check_via_redirect(timeout: float) -> Optional[dict]:
    tag = _latest_tag_from_redirect(timeout)
    if not tag:
        raise UpdateCheckError("не удалось определить последний тег")
    if not is_newer(tag, __version__):
        return None
    return _release_info(tag, tag.lstrip("vV"), source="redirect")


def check_sources():
    """Каналы проверки в порядке приоритета (читаем атрибуты модуля — удобно тестировать)."""
    return (
        ("api", _check_via_api),
        ("latest.json", _check_via_latest_json),
        ("redirect", _check_via_redirect),
    )


def check_for_updates(timeout: float = 6.0) -> Optional[dict]:
    """Синхронная проверка обновлений по нескольким независимым каналам.

    Возвращает dict с информацией о релизе или None, если у пользователя
    последняя версия. Если не сработал ни один канал — поднимает
    UpdateCheckError с перечнем причин (их видно в настройках и в журнале).
    """
    errors: List[str] = []
    log_update(f"проверка обновлений: установлена v{__version__}")
    deadline = time.monotonic() + max(timeout * 2.5, timeout + 1)
    for name, source in check_sources():
        if time.monotonic() > deadline:
            log_update(f"канал {name} — пропущен: истёк лимит времени")
            errors.append(f"{name}: не проверялся (лимит времени)")
            continue
        try:
            result = source(timeout)
        except UpdateCheckError as e:
            errors.append(f"{name}: {e}")
            log_update(f"канал {name} — ошибка: {e}")
            continue
        except Exception as e:  # неожиданная ошибка одного канала не должна ломать остальные
            errors.append(f"{name}: {e}")
            log_update(f"канал {name} — неожиданная ошибка: {e}")
            continue
        if result:
            log_update(f"канал {name} — доступна v{result['latest']}")
            return result
        log_update(f"канал {name} — обновлений нет")
        return None
    message = "; ".join(errors) if errors else "не удалось подключиться к GitHub"
    log_update(f"проверка не удалась: {message}")
    raise UpdateCheckError(message)


def _download_stream(url: str, dest: Path, progress_callback=None) -> Tuple[int, str, bool]:
    """Качает файл в dest любым доступным способом. Возвращает (размер, способ, insecure)."""
    errors: List[str] = []

    def _report(downloaded: int, total: int):
        if progress_callback:
            try:
                progress_callback(downloaded, total)
            except Exception:
                pass

    # 1. requests
    if requests is not None:
        try:
            resp = _requests_get(url, 60, stream=True, headers=_HTTP_HEADERS)
            if resp.status_code >= 400:
                raise UpdateCheckError(f"HTTP {resp.status_code}")
            total = int(resp.headers.get("content-length", 0) or 0)
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        _report(downloaded, total)
            return downloaded, "requests", False
        except UpdateCheckError as e:
            errors.append(f"requests: {e}")
            log_update(f"загрузка — {errors[-1]}")
        except Exception as e:
            errors.append(f"requests: {type(e).__name__}: {e}")
            log_update(f"загрузка — {errors[-1]}")

    # 2. urllib с проверкой сертификата
    for insecure in (False, True):
        if insecure and not errors:
            continue
        try:
            with _urllib_get(url, 60, insecure=insecure) as resp:
                total = int(resp.headers.get("content-length", 0) or 0)
                downloaded = 0
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        _report(downloaded, total)
                if insecure:
                    log_update("загрузка — БЕЗ проверки сертификата")
                return downloaded, ("urllib-insecure" if insecure else "urllib"), insecure
        except Exception as e:
            errors.append(f"urllib{'-insecure' if insecure else ''}: {e}")
            log_update(f"загрузка — {errors[-1]}")

    raise UpdateCheckError("; ".join(errors) if errors else "не удалось скачать файл")


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _decode_text(payload: bytes) -> str:
    """Декодирует файл с учётом BOM (PowerShell utf8/utf16, обычный UTF-8)."""
    if payload[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return payload.decode("utf-16")
        except Exception:
            pass
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return payload.decode(enc)
        except Exception:
            continue
    return payload.decode("utf-8", errors="replace")


_HEX64 = re.compile(r"[0-9a-fA-F]{64}")


def parse_sums(payload: bytes) -> Dict[str, str]:
    """Разбирает SHA256SUMS.txt в {имя файла: хеш}.

    Понимает форматы ``<hash>  <file>``, ``SHA256: <hash>  <file>`` (так пишет
    PowerShell-шаг релиза) и ``SHA256 (file) = <hash>``.
    """
    text = _decode_text(payload)
    sums: Dict[str, str] = {}
    for line in text.splitlines():
        match = _HEX64.search(line)
        if not match:
            continue
        digest = match.group(0).lower()
        name = None
        bsd = re.search(r"\(\s*([^)]+)\s*\)", line)
        if bsd:
            name = bsd.group(1).strip()
        else:
            for token in reversed(line.replace("*", " ").split()):
                if token.lower() == digest:
                    continue
                if token.rstrip(":").upper() == "SHA256":
                    continue
                name = token
                break
        if name:
            sums[Path(name.strip('"')).name] = digest
    return sums


def verify_download(
    path: Path, sums_url: Optional[str], timeout: float = 10.0
) -> Optional[bool]:
    """Сверяет SHA256 файла с SHA256SUMS.txt релиза.

    True — совпало, False — не совпало (файл битый/подменён), None — сверить
    не удалось (список контрольных сумм недоступен или файла в нём нет).
    """
    if not sums_url:
        return None
    try:
        payload, _via, _insecure = http_get_bytes(sums_url, timeout, allow_insecure=True)
        sums = parse_sums(payload)
        expected = sums.get(path.name)
        if not expected:
            log_update(f"контрольная сумма для {path.name} не найдена в SHA256SUMS.txt")
            return None
        actual = _sha256_of(path)
        ok = actual == expected
        log_update(
            f"контрольная сумма {path.name}: "
            f"{'совпала' if ok else f'НЕ совпала ({actual[:12]}… != {expected[:12]}…)'}"
        )
        return ok
    except Exception as e:
        log_update(f"не удалось сверить контрольную сумму: {e}")
        return None


def download_update(url: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[Path]:
    """Скачивает обновление, возвращает путь к файлу или None. Поддерживает прогресс."""
    if not url or not url.startswith("http"):
        log_update(f"скачивание невозможно: некорректная ссылка {url!r}")
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

        log_update(f"скачивание {url} -> {dest}")
        size, via, insecure = _download_stream(url, dest, progress_callback)
        log_update(f"скачано {size} байт ({via}{', без проверки сертификата' if insecure else ''})")

        if dest.exists() and dest.stat().st_size > 1000:
            return dest
        log_update("файл слишком мал — похоже на страницу ошибки, а не установщик")
        try:
            dest.unlink()
        except Exception:
            pass
        return None
    except Exception as e:
        log_update(f"скачивание не удалось: {e}")
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
        log_update(f"не удалось открыть папку загрузок: {e}")
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
        log_update(f"не удалось записать update_state.json: {e}")

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

def build_update_helper_env(
    installer_path: Path,
    args: Sequence[str],
    install_dir: Optional[Path] = None,
) -> dict:
    """Окружение для bat-помощника: пути передаются переменными, не текстом bat.

    Кириллица в ``C:\\Users\\Иван\\...`` не должна попадать в bat — иначе
    в консольной кодировке она превращалась в кракозябры.
    """
    env = dict(os.environ)
    env["BLK_INSTALLER"] = str(installer_path)
    env["BLK_ARGS"] = " ".join(str(a) for a in args)
    env["BLK_PID"] = str(os.getpid())
    if install_dir:
        exe = Path(install_dir) / "DetectiveBlackville.exe"
        env["BLK_EXE"] = str(exe)
        env["BLK_EXENAME"] = "DetectiveBlackville.exe"
    env["BLK_LOG"] = str(get_update_log_path())
    # Файл-флаг: bat создаёт его первой строкой. Игра ждёт его появления и,
    # если помощник не отчитался, запускает установщик напрямую — без «мёртвого» клика.
    env["BLK_READY"] = str(helper_ready_path())
    return env


def helper_ready_path() -> Path:
    """Путь к файлу-флагу «помощник запустился» для текущего процесса."""
    return Path(tempfile.gettempdir()) / f"blackville_ready_{os.getpid()}.flag"


def _wait_helper_ready(ready: Path, seconds: float = 1.5) -> bool:
    """Ждёт, пока bat-помощник подтвердит запуск (создаст файл-флаг)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if ready.exists():
            return True
        time.sleep(0.05)
    return ready.exists()


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

        bat_content = r"""@echo off
setlocal
if defined BLK_READY >"%BLK_READY%" echo started
if not defined BLK_INSTALLER exit /b 1
:waitgame
if not defined BLK_PID goto install
tasklist /FI "PID eq %BLK_PID%" /NH /FO CSV 2>nul | findstr /C:"%BLK_PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto waitgame
)
:install
timeout /t 1 /nobreak >nul
call "%BLK_INSTALLER%" %BLK_ARGS% >> "%BLK_LOG%" 2>&1
set BLK_RC=%ERRORLEVEL%
echo [blackville] installer exit code %BLK_RC% >> "%BLK_LOG%"
if not defined BLK_EXE goto done
if not exist "%BLK_EXE%" goto done
tasklist /FI "IMAGENAME eq %BLK_EXENAME%" /NH 2>nul | findstr /I "%BLK_EXENAME%" >nul
if not errorlevel 1 goto done
echo [blackville] relaunch game >> "%BLK_LOG%"
start "" "%BLK_EXE%"
:done
(goto) 2>nul & del "%~f0"
"""
        bat_path.write_text(bat_content, encoding="ascii", errors="ignore")
        env = build_update_helper_env(installer_path, args, install_dir)
        log_update(
            f"helper: {bat_path} (installer={installer_path}, args={env['BLK_ARGS']}, "
            f"pid={env['BLK_PID']}, log={env['BLK_LOG']})"
        )
        return bat_path
    except Exception as e:
        log_update(f"не удалось создать helper-bat: {e}")
        return None


def _launch_elevated(exe: Path, args: Sequence[str]) -> bool:
    """Запуск инсталлятора с запросом UAC (нельзя молча писать в Program Files)."""
    try:
        import ctypes

        params = " ".join(str(a) for a in args)
        log_update(f"запуск с правами администратора: {exe} {params}")
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(exe), params, None, 1)
        # >32 — успех; 5 — пользователь отменил UAC
        return int(rc) > 32
    except Exception as e:
        log_update(f"запуск с правами администратора не удался: {e}")
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
            log_update("установщик не найден: None")
            return False
        p = Path(path)
        if not p.exists():
            log_update(f"установщик не найден: {p}")
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
        log_update(f"запуск установщика: {p} {args} (silent={silent}, dir={target})")

        started = False
        if sys.platform == "win32":
            if silent:
                helper = _create_windows_update_helper(p, args, install_dir=target, autolaunch=autolaunch)
                if helper:
                    # ВАЖНО: env обязателен — помощник берёт из него пути и PID игры.
                    # Без него bat сразу выходил по `if not defined BLK_INSTALLER`,
                    # игра закрывалась, и обновление не устанавливалось.
                    env = build_update_helper_env(p, args, target)
                    ready = helper_ready_path()
                    try:
                        ready.unlink()
                    except Exception:
                        pass
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", str(helper)],
                        env=env,
                        creationflags=0x00000008,  # DETACHED_PROCESS
                        close_fds=True,
                    )
                    if _wait_helper_ready(ready):
                        log_update("помощник запущен и ждёт выхода игры")
                        started = True
                    else:
                        # bat не отчитался (антивирус/политика) — не оставляем
                        # пользователя без установки: стартуем Setup напрямую
                        log_update(
                            "помощник не отчитался о запуске — запускаю установщик напрямую"
                        )
                        subprocess.Popen(
                            [str(p), *args], creationflags=0x00000008, close_fds=True
                        )
                        started = True
                    try:
                        ready.unlink()
                    except Exception:
                        pass
                else:
                    log_update("помощник не создан — запускаю установщик напрямую")
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
        log_update(f"запуск установщика не удался: {e}")
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
        self.checked_at: float = 0.0
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

    @property
    def source(self) -> str:
        """Каким каналом получена информация о релизе (api / latest.json / redirect)."""
        return str((self.result or {}).get("source") or "")

    def start(self):
        if self.checking:
            return
        # повторная ручная проверка: сбрасываем прошлый результат
        self.done = False
        self.error = None
        self.result = None
        self.checked_at = 0.0
        self.checking = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            self.result = check_for_updates()
        except UpdateCheckError as e:
            self.error = str(e)
            log_update(f"проверка не удалась: {e}")
        except Exception as e:  # pragma: no cover - защита от неожиданностей
            self.error = f"неизвестная ошибка: {e}"
            log_update(f"проверка не удалась: {e}")
        finally:
            self.checking = False
            self.done = True
            self.checked_at = time.time()

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
                log_update(f"начата загрузка обновления v{self.download_target_version}")
                path = download_update(url, progress_callback=progress)
                if not path:
                    self.download_error = (
                        "Не удалось скачать установщик. Проверьте интернет или скачайте "
                        "вручную со страницы релиза"
                    )
                    log_update("загрузка обновления не удалась")
                    return
                # Проверяем файл по SHA256 из релиза, чтобы не запускать битый/чужой exe
                verified = verify_download(path, self.result.get("sums_url"))
                if verified is False:
                    self.download_error = "Файл обновления повреждён (не сошлась контрольная сумма)"
                    log_update("файл обновления удалён: неверная контрольная сумма")
                    try:
                        path.unlink()
                    except Exception:
                        pass
                    return
                self.downloaded_path = path
                self.download_progress = 100
                log_update(f"обновление скачано: {path} (sha256: {'ok' if verified else 'не проверено'})")
            except Exception as e:
                self.download_error = str(e)
                log_update(f"загрузка обновления: ошибка {e}")
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
