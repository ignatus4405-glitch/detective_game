"""Detective Game: Blackville — нуар-детектив в стиле Код Города."""
from pathlib import Path

def get_version() -> str:
    try:
        version_file = Path(__file__).parent.parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    # fallback: package version
    try:
        from importlib.metadata import version as pkg_version
        return pkg_version("detective-game-blackville")
    except Exception:
        return "0.1.0"

__version__ = get_version()
__author__ = "Blackville Studio"
__game_title__ = "ДЕТЕКТИВ: БЛЭКВИЛ"
__game_subtitle__ = "Код Города — нуар-расследование 80-х"
