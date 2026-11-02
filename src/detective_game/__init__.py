"""Detective Game: Blackville — нуар-детектив в стиле Код Города."""
import sys
from pathlib import Path
from typing import List, Optional

__author__ = "Sams_studio128"
__game_title__ = "ДЕТЕКТИВ: БЛЭКВИЛ"
__game_subtitle__ = "Код Города — нуар-расследование 80-х"

# Страховка на случай, если версию не удалось определить вообще.
_FALLBACK_VERSION = "0.1.0"


def _looks_like_version(value: str) -> bool:
    """Похоже ли значение на semver (0.1.24 / v0.1.24 / 0.1.24.0)."""
    parts = str(value).strip().lstrip("vV").split(".")
    if not 2 <= len(parts) <= 4:
        return False
    return all(part.isdigit() for part in parts)


def _read_version_file(path) -> Optional[str]:
    """Читает VERSION, если файл существует и содержит валидную версию."""
    try:
        candidate = Path(path)
        if not candidate.is_file():
            return None
        raw = candidate.read_text(encoding="utf-8").strip().lstrip("vV")
        return raw if _looks_like_version(raw) else None
    except Exception:
        return None


def _version_candidates(
    *,
    frozen: Optional[bool] = None,
    executable: Optional[str] = None,
    meipass: Optional[str] = None,
    package_dir: Optional[Path] = None,
) -> List[Path]:
    """Все места, где может лежать файл VERSION.

    Порядок важен: сначала «живые» исходники, затем папка установленной
    (frozen) игры. В onedir-сборке PyInstaller 6 файлы данных лежат в
    ``<app>/_internal`` (это и есть ``sys._MEIPASS``), а exe — в ``<app>``,
    поэтому проверяем оба уровня. Именно из-за отсутствия этих путей
    собранная игра раньше всегда сообщала версию 0.1.0.
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if executable is None:
        executable = getattr(sys, "executable", None)
    if meipass is None:
        meipass = getattr(sys, "_MEIPASS", None)
    pkg = Path(package_dir) if package_dir is not None else Path(__file__).resolve().parent

    candidates: List[Path] = []

    def add(path: Optional[Path]) -> None:
        if path is None:
            return
        path = Path(path)
        if path not in candidates:
            candidates.append(path)

    # 1. Внутри пакета (если VERSION положили как package data)
    add(pkg / "VERSION")
    # 2. Исходники / editable install: <repo>/src/detective_game/__init__.py -> <repo>/VERSION
    add(pkg.parent.parent / "VERSION")

    # 3. Рядом с exe (портативная распаковка, ручная сборка)
    if executable:
        exe_dir = Path(executable).parent
        add(exe_dir / "VERSION")
        add(exe_dir / "_internal" / "VERSION")  # onedir PyInstaller >= 6

    # 4. Внутри бандла (_MEIPASS): onefile и onedir
    if meipass:
        mp = Path(meipass)
        add(mp / "VERSION")
        add(mp / "detective_game" / "VERSION")

    # 5. Последний шанс для frozen: exe внутри временной распаковки
    if frozen and executable:
        add(Path(executable).parent.parent / "VERSION")

    return candidates


def _read_packaged_version() -> Optional[str]:
    """Версия, вшитая в сборку скриптом tools/generate_version_info.py."""
    try:
        from ._build_version import BUILD_VERSION

        value = str(BUILD_VERSION).strip().lstrip("vV")
        return value if _looks_like_version(value) else None
    except Exception:
        return None


def _read_metadata_version() -> Optional[str]:
    """Версия из метаданных пакета (pip install)."""
    try:
        from importlib.metadata import version as pkg_version

        value = pkg_version("detective-game-blackville").strip().lstrip("vV")
        return value if _looks_like_version(value) else None
    except Exception:
        return None


def get_version() -> str:
    """Определяет версию игры: VERSION-файл → вшитая в сборку → метаданные pip."""
    for candidate in _version_candidates():
        found = _read_version_file(candidate)
        if found:
            return found
    packaged = _read_packaged_version()
    if packaged:
        return packaged
    metadata = _read_metadata_version()
    if metadata:
        return metadata
    return _FALLBACK_VERSION


def get_version_source() -> str:
    """Откуда взята версия — полезно для диагностики (настройки, баг-репорты)."""
    for candidate in _version_candidates():
        if _read_version_file(candidate):
            return str(candidate)
    if _read_packaged_version():
        return "build (detective_game._build_version)"
    if _read_metadata_version():
        return "package metadata"
    return "fallback"


__version__ = get_version()
