"""Настоящая проверка bat-помощника обновления на Windows.

Тесты запускают сгенерированный помощник так же, как это делает игра
(через переменные окружения), и проверяют результат: файлы скопированы,
VERSION обновился, игра перезапущена, окно консоли не мешает.

На Linux/macOS тесты пропускаются — там помощник не используется.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from detective_game import updater

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only помощник")


def _make_stage(root: Path, version: str = "0.1.28") -> Path:
    stage = root / "stage" / "DetectiveBlackville"
    (stage / "_internal").mkdir(parents=True)
    (stage / "DetectiveBlackville.exe").write_bytes(b"MZ" + b"x" * 64)
    (stage / "_internal" / "VERSION").write_text(version + "\n", encoding="utf-8")
    (stage / "_internal" / "new_file.txt").write_text("new", encoding="utf-8")
    return stage


def _make_target(root: Path) -> Path:
    target = root / "game"
    (target / "_internal").mkdir(parents=True)
    (target / "DetectiveBlackville.exe").write_bytes(b"MZ old")
    (target / "_internal" / "VERSION").write_text("0.1.27\n", encoding="utf-8")
    return target


def _run_helper(stage: Path, target: Path, root: Path, launch_marker: Path, pid="") -> int:
    helper = updater._create_stage_apply_helper(stage, target, "0.1.28")
    assert helper is not None
    launcher = root / "fake_game.bat"
    launcher.write_text(f'echo launched > "{launch_marker}"\r\n', encoding="ascii")

    env = dict(os.environ)
    env.update(
        {
            "BLK_STAGE": str(stage),
            "BLK_STAGE_ROOT": str(stage.parent),
            "BLK_TARGET": str(target),
            "BLK_EXE": str(launcher),
            "BLK_EXENAME": "DetectiveBlackville.exe",
            "BLK_LOG": str(root / "inst.log"),
            "BLK_READY": str(root / "ready.flag"),
            "BLK_PID": pid,
            "BLK_VERSION": "0.1.28",
        }
    )
    proc = subprocess.run(
        ["cmd", "/c", str(helper)],
        env=env,
        capture_output=True,
        timeout=180,
        creationflags=0x08000000,
    )
    return proc.returncode


def test_helper_copies_files_and_relaunches(tmp_path):
    stage = _make_stage(tmp_path)
    target = _make_target(tmp_path)
    marker = tmp_path / "launched.txt"

    _run_helper(stage, target, tmp_path, marker)  # без BLK_PID — сразу копирует

    assert (target / "DetectiveBlackville.exe").read_bytes().startswith(b"MZx")
    assert (target / "_internal" / "new_file.txt").read_text() == "new"
    assert (target / "_internal" / "VERSION").read_text().strip() == "0.1.28"
    # корневой VERSION синхронизирован — иначе игра снова предложит обновление
    assert (target / "VERSION").read_text().strip() == "0.1.28"
    # игра перезапущена
    deadline = time.time() + 10
    while time.time() < deadline and not marker.exists():
        time.sleep(0.2)
    assert marker.exists(), "после обновления игра должна запуститься сама"
    # журнал содержит код возврата xcopy
    log = (tmp_path / "inst.log").read_text(encoding="utf-8", errors="replace")
    assert "xcopy exit code" in log


def test_helper_waits_for_game_process(tmp_path):
    """Помощник не копирует файлы, пока процесс игры жив."""
    stage = _make_stage(tmp_path)
    target = _make_target(tmp_path)
    marker = tmp_path / "launched.txt"

    sleeper = subprocess.Popen(
        ["cmd", "/c", "ping -n 4 127.0.0.1 >nul"],
        creationflags=0x08000000,
    )
    try:
        _run_helper(stage, target, tmp_path, marker, pid=str(sleeper.pid))
        # процесс завершился до копирования — файлы всё равно обновлены
        assert (target / "_internal" / "VERSION").read_text().strip() == "0.1.28"
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_helper_survives_dead_pid(tmp_path):
    """Если игра уже закрыта (PID не найден), помощник не висит и работает."""
    stage = _make_stage(tmp_path)
    target = _make_target(tmp_path)
    marker = tmp_path / "launched.txt"
    started = time.time()
    _run_helper(stage, target, tmp_path, marker, pid="999999")
    assert time.time() - started < 60
    assert (target / "_internal" / "VERSION").read_text().strip() == "0.1.28"
