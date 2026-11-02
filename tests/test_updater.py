import zipfile
from pathlib import Path

import pytest

from detective_game import updater
from detective_game.updater import _parse_version, is_newer


def test_parse_version():
    assert _parse_version("v0.1.0") == (0,1,0)
    assert _parse_version("1.2.3") == (1,2,3)
    assert _parse_version("v10.20.30") == (10,20,30)
    assert _parse_version("0.0.1") == (0,0,1)

def test_is_newer():
    assert is_newer("v0.2.0", "0.1.0") == True
    assert is_newer("0.1.1", "0.1.0") == True
    assert is_newer("0.1.0", "0.1.0") == False
    assert is_newer("0.0.9", "0.1.0") == False
    assert is_newer("v1.0.0", "0.9.9") == True

def test_version_sync():
    # VERSION file and pyproject should be in sync — checked in CI
    from pathlib import Path
    version_file = Path("VERSION")
    if version_file.exists():
        v = version_file.read_text().strip().lstrip("v")
        # must be semver
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# --- Проверка ошибок/статусов обновления и установки в нужную папку ---


def test_find_download_url_prefers_setup():
    data = {
        "assets": [
            {"name": "DetectiveBlackville-Windows.zip", "browser_download_url": "zip"},
            {"name": "DetectiveBlackville-Setup-0.1.24.exe", "browser_download_url": "setup"},
            {"name": "latest.json", "browser_download_url": "json"},
        ],
        "html_url": "release",
    }
    assert updater._find_download_url(data) == "setup"


def test_check_for_updates_reports_network_error(monkeypatch):
    def boom(*a, **kw):
        raise updater.UpdateCheckError("нет связи с GitHub")

    for name in ("_check_via_api", "_check_via_latest_json", "_check_via_redirect"):
        monkeypatch.setattr(updater, name, boom)
    try:
        updater.check_for_updates()
    except updater.UpdateCheckError as e:
        assert "нет связи" in str(e)
    else:
        raise AssertionError("ожидался UpdateCheckError")


def test_check_for_updates_none_when_latest(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.24")
    monkeypatch.setattr(
        updater, "_check_via_api", lambda timeout: None
    )
    assert updater.check_for_updates() is None


def test_check_for_updates_detects_newer(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.24")
    monkeypatch.setattr(
        updater,
        "_check_via_api",
        lambda timeout: {
            "current": "0.1.24",
            "latest": "0.1.25",
            "tag": "v0.1.25",
            "name": "Релиз",
            "url": "release",
            "download_url": "setup",
            "source": "api",
        },
    )
    info = updater.check_for_updates()
    assert info is not None
    assert info["latest"] == "0.1.25"
    assert info["current"] == "0.1.24"
    assert info["download_url"] == "setup"


def test_check_falls_back_to_next_source(monkeypatch):
    """Если GitHub API отвалился (лимит/SSL), проверка идёт по latest.json."""
    calls = []

    def api(timeout):
        calls.append("api")
        raise updater.UpdateCheckError("HTTP 403")

    def latest_json(timeout):
        calls.append("latest.json")
        return {
            "latest": "0.1.26",
            "tag": "v0.1.26",
            "download_url": "setup-url",
            "source": "latest.json",
        }

    monkeypatch.setattr(updater, "_check_via_api", api)
    monkeypatch.setattr(updater, "_check_via_latest_json", latest_json)
    info = updater.check_for_updates()
    assert calls == ["api", "latest.json"]
    assert info["latest"] == "0.1.26"


def test_check_stops_when_api_says_up_to_date(monkeypatch):
    """Успешный ответ «обновлений нет» не должен дёргать остальные каналы."""
    calls = []
    monkeypatch.setattr(updater, "_check_via_api", lambda timeout: calls.append("api") or None)
    monkeypatch.setattr(
        updater, "_check_via_latest_json", lambda timeout: calls.append("latest.json") or None
    )
    assert updater.check_for_updates() is None
    assert calls == ["api"]


def test_release_download_url_constructed_from_tag():
    url = updater.build_release_download_url("v0.1.26", "0.1.26")
    assert url == (
        "https://github.com/ignatus4405-glitch/detective_game/releases/download/"
        "v0.1.26/DetectiveBlackville-Setup-0.1.26.exe"
    )


def test_latest_json_channel_builds_installer_url(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.24")

    def fake_get_json(url, timeout=6.0, **kw):
        assert url == updater.LATEST_JSON_URL
        return {"version": "0.1.26", "tag": "v0.1.26", "url": "https://github.com/x/y/releases/tag/v0.1.26"}, False

    monkeypatch.setattr(updater, "http_get_json", fake_get_json)
    info = updater._check_via_latest_json(6.0)
    assert info is not None
    assert info["latest"] == "0.1.26"
    assert info["download_url"].endswith("DetectiveBlackville-Setup-0.1.26.exe")
    assert info["source"] == "latest.json"


def test_latest_json_channel_returns_none_when_same_version(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.26")
    monkeypatch.setattr(
        updater, "http_get_json", lambda url, timeout=6.0, **kw: ({"version": "0.1.26"}, False)
    )
    assert updater._check_via_latest_json(6.0) is None


def test_http_get_falls_back_to_urllib_when_requests_fails(monkeypatch):
    """Регрессия: requests падал на SSL (нет certifi), и проверка умирала целиком."""
    import io

    class FakeResp(io.BytesIO):
        headers = {"Content-Length": "2"}

    def failing_requests(*a, **kw):
        raise updater.UpdateCheckError("SSL-сертификат не проверяется (SSLError)")

    def working_urllib(url, timeout, insecure=False, headers=None):
        return FakeResp(b"{}")

    monkeypatch.setattr(updater, "requests", object())
    monkeypatch.setattr(updater, "_requests_get", failing_requests)
    monkeypatch.setattr(updater, "_urllib_get", working_urllib)
    payload, via, insecure = updater.http_get_bytes("https://example.invalid/x")
    assert payload == b"{}"
    assert via == "urllib"
    assert insecure is False


def test_verify_download_detects_corrupted_file(tmp_path, monkeypatch):
    good = tmp_path / "DetectiveBlackville-Setup-0.1.26.exe"
    good.write_bytes(b"installer-bytes")
    sums = f"{updater._sha256_of(good)}  {good.name}\n".encode()

    monkeypatch.setattr(
        updater, "http_get_bytes", lambda *a, **kw: (sums, "urllib", False)
    )
    assert updater.verify_download(good, "https://example.invalid/SHA256SUMS.txt") is True

    good.write_bytes(b"tampered")
    assert updater.verify_download(good, "https://example.invalid/SHA256SUMS.txt") is False


def test_verify_download_returns_none_without_sums(tmp_path):
    f = tmp_path / "x.exe"
    f.write_bytes(b"123")
    assert updater.verify_download(f, None) is None


def test_update_log_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    updater.log_update("тестовая строка")
    content = (tmp_path / "update.log").read_text(encoding="utf-8")
    assert "тестовая строка" in content


def test_installer_args_target_current_folder():
    target = Path("C:/Games/Blackville")
    log_path = Path("C:/Temp/update.log")
    args = updater.build_installer_args(
        Path("setup.exe"),
        silent=True,
        autolaunch=True,
        install_dir=target,
        log_path=log_path,
    )
    assert "/SILENT" in args
    assert "/CLOSEAPPLICATIONS" in args
    assert "/NORESTART" in args
    assert "/AUTOLAUNCH=1" in args
    # str(Path) на Windows даёт обратные слэши — сравниваем через str()
    assert f'/DIR="{target}"' in args
    assert f'/LOG="{log_path}"' in args


def test_installer_args_interactive_without_silent_flags():
    args = updater.build_installer_args(Path("setup.exe"), silent=False, autolaunch=False)
    assert "/SILENT" not in args
    assert "/AUTOLAUNCH=1" not in args
    assert not any(a.startswith("/DIR=") for a in args)


def test_is_dir_writable(tmp_path):
    assert updater.is_dir_writable(tmp_path) is True
    assert updater.is_dir_writable(tmp_path / "nope") is False


def test_pending_update_reports_installed(tmp_path, monkeypatch):
    state = tmp_path / "update_state.json"
    monkeypatch.setattr(updater, "_update_state_path", lambda: state)
    monkeypatch.setattr(updater, "__version__", "0.1.24")
    updater.write_pending_update("0.1.24", Path("setup.exe"), Path("update.log"))
    assert state.exists()
    result = updater.consume_update_result()
    assert result is not None
    assert result["status"] == "installed"
    assert not state.exists()


def test_pending_update_reports_failure(tmp_path, monkeypatch):
    state = tmp_path / "update_state.json"
    monkeypatch.setattr(updater, "_update_state_path", lambda: state)
    monkeypatch.setattr(updater, "__version__", "0.1.23")
    updater.write_pending_update("0.1.24", Path("setup.exe"))
    result = updater.consume_update_result()
    assert result is not None
    assert result["status"] == "failed"
    assert result["target"] == "0.1.24"
    assert result["current"] == "0.1.23"


def test_windows_helper_is_ascii_and_uses_env(tmp_path, monkeypatch):
    """Bat-помощник не должен содержать кириллицу: пути передаются через env."""
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    helper = updater._create_windows_update_helper(
        Path("C:/Users/Иван/Downloads/Setup.exe"),
        ["/SILENT", '/DIR="C:/Games/Игра"'],
        install_dir=Path("C:/Games/Игра"),
    )
    assert helper is not None and helper.exists()
    raw = helper.read_bytes()
    raw.decode("ascii")  # в файле не должно быть не-ASCII байтов
    text = helper.read_text(encoding="ascii")
    assert "%BLK_INSTALLER%" in text
    assert "%BLK_ARGS%" in text
    assert "Setup.exe" not in text
    assert "Игра" not in text


def test_run_installer_passes_env_to_helper(monkeypatch, tmp_path):
    """Регрессия v0.1.26: env не передавался, bat-helpers сразу выходили.

    Игра закрывалась по «Установить», а установщик не запускался никогда.
    """
    installer = tmp_path / "Setup.exe"
    installer.write_bytes(b"x" * 2048)
    calls = []

    class FakePopen:
        """Имитация скрытого запуска: помощник «отчитывается» файлом-флагом."""

        def __init__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            ready = (kwargs.get("env") or {}).get("BLK_READY")
            if ready:
                Path(ready).write_text("started", encoding="utf-8")

    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "should_install_silently", lambda target=None: True)

    ok = updater.run_installer(installer, silent=True, install_dir=tmp_path, target_version="0.1.26")
    assert ok is True
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    # запускаем скрыто: wscript + VBS, а не видимое окно cmd
    assert "wscript" in cmd[0].lower()
    assert cmd[1] == "//B"
    assert cmd[-1].endswith(".bat")
    env = kwargs.get("env")
    assert env is not None, "Popen должен получить env с BLK_INSTALLER"
    assert env["BLK_INSTALLER"] == str(installer)
    assert "/SILENT" in env["BLK_ARGS"]
    assert env["BLK_PID"]
    assert env["BLK_EXE"].endswith("DetectiveBlackville.exe")


def test_helper_bat_waits_and_relaunches(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    helper = updater._create_windows_update_helper(
        Path("C:/Users/Иван/Downloads/Setup.exe"), ["/SILENT"], install_dir=Path("C:/Games/Игра")
    )
    text = helper.read_text(encoding="ascii")
    assert "tasklist" in text and "waitgame" in text
    assert "call \"%BLK_INSTALLER%\"" in text
    assert "BLK_LOG" in text
    assert text.index("waitgame") < text.index('call "%BLK_INSTALLER%"')


def test_update_checker_resets_on_retry(monkeypatch):
    checker = updater.UpdateChecker()
    checker.done = True
    checker.error = "старая ошибка"
    started = {}

    def fake_start():
        started["ok"] = True

    monkeypatch.setattr(updater.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: fake_start()})())
    checker.start()
    assert checker.error is None
    assert checker.done is False
    assert started.get("ok") is True


def test_update_checker_reports_error(monkeypatch):
    def boom(*a, **kw):
        raise updater.UpdateCheckError("нет связи")

    monkeypatch.setattr(updater, "check_for_updates", boom)
    checker = updater.UpdateChecker()
    checker._run()
    assert checker.done is True
    assert checker.checking is False
    assert "нет связи" in (checker.error or "")


def test_download_update_reports_failure(monkeypatch, tmp_path):
    def boom(url, dest, progress_callback=None):
        raise updater.UpdateCheckError("обрыв соединения")

    monkeypatch.setattr(updater, "_download_stream", boom)
    monkeypatch.setattr(updater.Path, "home", lambda: tmp_path)
    assert updater.download_update("https://example.invalid/Setup.exe") is None


def test_run_installer_falls_back_when_helper_silent(monkeypatch, tmp_path):
    """Если bat-помощник не отчитался (антивирус), Setup всё равно запускается."""
    installer = tmp_path / "Setup.exe"
    installer.write_bytes(b"x" * 2048)
    calls = []

    class DeadPopen:
        def __init__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))

    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.subprocess, "Popen", DeadPopen)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "should_install_silently", lambda target=None: True)
    monkeypatch.setattr(updater, "_wait_helper_ready", lambda ready, seconds=1.5: False)

    ok = updater.run_installer(installer, silent=True, install_dir=tmp_path, target_version="0.1.26")
    assert ok is True
    assert len(calls) == 2
    assert calls[1][0][0] == str(installer), "второй запуск — напрямую Setup.exe"
    assert "/SILENT" in calls[1][0]


def test_helper_env_contains_ready_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    env = updater.build_update_helper_env(Path("/tmp/Setup.exe"), ["/SILENT"], Path("/tmp"))
    assert env["BLK_READY"].startswith(str(tmp_path))
    assert str(updater.os.getpid()) in env["BLK_READY"]


def test_parse_sums_power_shell_format():
    """SHA256SUMS.txt пишется шагом релиза как `SHA256: <hash>  <file>`."""
    digest = "c" * 64
    payload = f"SHA256: {digest}  DetectiveBlackville-Setup-0.1.26.exe\n".encode()
    assert updater.parse_sums(payload) == {"DetectiveBlackville-Setup-0.1.26.exe": digest}


def test_parse_sums_handles_bom_and_bsd():
    digest = "d" * 64
    with_bom = f"\ufeff{digest}  file.exe\n".encode("utf-8")
    assert updater.parse_sums(with_bom) == {"file.exe": digest}
    bsd = f"SHA256 (file.exe) = {digest}\n".encode()
    assert updater.parse_sums(bsd) == {"file.exe": digest}


def test_release_info_has_sums_url_for_every_channel():
    info = updater._release_info("v0.1.26", "0.1.26", source="redirect")
    assert info["sums_url"] == (
        "https://github.com/ignatus4405-glitch/detective_game/releases/download/"
        "v0.1.26/SHA256SUMS.txt"
    )


def _serve(files):
    """Мини-сервер: отдаёт словарь {путь: (bytes, content-type)}."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            payload, ctype = files.get(self.path.split("?")[0], (None, None))
            if payload is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_HEAD(self):
            self.do_GET()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_full_update_cycle_download_and_checksum(tmp_path, monkeypatch):
    """Проверка → скачивание → сверка SHA256 на живом HTTP-сервере."""
    exe_bytes = b"MZ" + b"installer payload " * 200
    digest = updater._sha256_of_bytes(exe_bytes)
    sums = f"SHA256: {digest}  DetectiveBlackville-Setup-0.1.26.exe\n".encode()
    latest = b'{"version": "0.1.26", "tag": "v0.1.26", "url": "http://example/tag"}'

    srv, base = _serve(
        {
            "/latest.json": (latest, "application/json"),
            "/DetectiveBlackville-Setup-0.1.26.exe": (exe_bytes, "application/octet-stream"),
            "/SHA256SUMS.txt": (sums, "text/plain"),
        }
    )
    try:
        monkeypatch.setattr(updater, "__version__", "0.1.25")
        monkeypatch.setattr(updater, "LATEST_JSON_URL", base + "/latest.json")
        monkeypatch.setattr(updater, "GITHUB_REPO", "local/test")
        # прямой URL инсталлятора строим на локальный сервер
        monkeypatch.setattr(
            updater,
            "build_release_download_url",
            lambda tag, version: f"{base}/DetectiveBlackville-Setup-{version}.exe",
        )
        monkeypatch.setattr(updater, "check_sources", lambda: (("latest.json", updater._check_via_latest_json),))
        monkeypatch.setattr(updater.Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")

        info = updater.check_for_updates()
        assert info is not None and info["latest"] == "0.1.26"
        assert info["download_url"].endswith("Setup-0.1.26.exe")
        info["sums_url"] = base + "/SHA256SUMS.txt"

        got = updater.download_update(info["download_url"])
        assert got is not None and got.read_bytes() == exe_bytes
        assert updater.verify_download(got, info["sums_url"]) is True
    finally:
        srv.shutdown()


def test_downloaded_file_with_wrong_checksum_is_rejected(tmp_path, monkeypatch):
    exe_bytes = b"MZ" + b"bad payload " * 100
    wrong = b"SHA256: " + b"0" * 64 + b"  DetectiveBlackville-Setup-0.1.26.exe\n"
    srv, base = _serve(
        {
            "/DetectiveBlackville-Setup-0.1.26.exe": (exe_bytes, "application/octet-stream"),
            "/SHA256SUMS.txt": (wrong, "text/plain"),
        }
    )
    try:
        monkeypatch.setattr(updater.Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
        got = updater.download_update(base + "/DetectiveBlackville-Setup-0.1.26.exe")
        assert got is not None
        assert updater.verify_download(got, base + "/SHA256SUMS.txt") is False
    finally:
        srv.shutdown()


def test_main_reports_failed_update_without_crash(monkeypatch, tmp_path):
    """Регрессия: main использовал log_update, не импортировав его."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game import main as game_main
    from detective_game import updater as upd

    assert hasattr(game_main, "log_update"), "log_update должен быть импортирован в main"
    monkeypatch.setattr(game_main, "log_update", lambda msg: None)

    game = game_main.Game.__new__(game_main.Game)
    game.notifications = []
    game.failed_update = None
    game.update_dismissed = True

    def add(text):
        game.notifications.append(text)

    game.add_notification = add
    game._report_update_result({"status": "failed", "target": "0.1.26", "current": "0.1.25"})
    # неудачу показываем баннером, а не уведомлением на 4 секунды
    assert game.failed_update is not None
    assert game.failed_update["target"] == "0.1.26"
    assert game.update_dismissed is False


# ---------------------------------------------------------------------------
# Обновление файлов из архива (0.1.28): без инсталлятора и без окна консоли
# ---------------------------------------------------------------------------


def _make_release_zip(path, version="0.1.28", *, exe=True, top="DetectiveBlackville"):
    import zipfile

    with zipfile.ZipFile(path, "w") as zf:
        prefix = f"{top}/" if top else ""
        if exe:
            zf.writestr(prefix + "DetectiveBlackville.exe", b"MZ" + b"x" * 2048)
        if top:
            zf.writestr(prefix + "_internal/VERSION", version + "\n")
        else:
            zf.writestr("VERSION", version + "\n")
        zf.writestr(prefix + "_internal/python311.dll", b"dll")
    return path


def test_stage_zip_update_extracts_and_promotes_top_folder(tmp_path, monkeypatch):
    archive = _make_release_zip(tmp_path / "DetectiveBlackville-Windows.zip")
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))

    stage = updater.stage_zip_update(archive, "0.1.28", target_dir=tmp_path / "game")
    assert (stage / "DetectiveBlackville.exe").exists()
    assert (stage / "_internal" / "python311.dll").exists()
    assert updater._version_in_dir(stage) == "0.1.28"


def test_stage_zip_update_rejects_wrong_version(tmp_path, monkeypatch):
    archive = _make_release_zip(tmp_path / "zip.zip", version="0.1.20")
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    with pytest.raises(updater.UpdateCheckError):
        updater.stage_zip_update(archive, "0.1.28", target_dir=tmp_path / "game")


def test_stage_zip_update_requires_exe(tmp_path, monkeypatch):
    archive = _make_release_zip(tmp_path / "zip.zip", exe=False)
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    with pytest.raises(updater.UpdateCheckError):
        updater.stage_zip_update(archive, "0.1.28", target_dir=tmp_path / "game")


def test_stage_zip_update_blocks_zip_slip(tmp_path, monkeypatch):
    import zipfile

    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("DetectiveBlackville.exe", b"MZ")
        zf.writestr("../../evil.txt", b"pwned")
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    stage = updater.stage_zip_update(archive, "0.1.28", target_dir=tmp_path / "game")
    assert not (tmp_path / "evil.txt").exists()
    assert (stage / "DetectiveBlackville.exe").exists()


def test_apply_helper_copies_files_and_relaunches(tmp_path, monkeypatch):
    stage = tmp_path / "stage" / "DetectiveBlackville"
    stage.mkdir(parents=True)
    (stage / "DetectiveBlackville.exe").write_bytes(b"MZ")
    target = tmp_path / "game"
    target.mkdir()
    (target / "DetectiveBlackville.exe").write_bytes(b"MZ old")

    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "get_update_log_path", lambda: tmp_path / "inst.log")
    monkeypatch.setattr(updater, "helper_ready_path", lambda: tmp_path / "ready.flag")
    monkeypatch.setattr(updater, "get_install_dir", lambda: target)
    monkeypatch.setattr(updater, "is_dir_writable", lambda p: True)
    monkeypatch.setattr(updater, "write_pending_update", lambda *a, **kw: None)

    calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            ready = (kwargs.get("env") or {}).get("BLK_READY")
            if ready:
                Path(ready).write_text("started", encoding="utf-8")

    monkeypatch.setattr(updater.subprocess, "Popen", FakePopen)
    ok = updater.run_staged_update(stage, version="0.1.28")
    assert ok is True

    bat = next(Path(c[-1]) for c, _ in calls if str(c[-1]).endswith(".bat"))
    text = bat.read_text(encoding="ascii")
    bat.read_bytes().decode("ascii")  # помощник без кириллицы
    assert "xcopy" in text and "/E" in text and "/Y" in text
    assert "%BLK_STAGE%" in text and "%BLK_TARGET%" in text
    assert "tasklist" in text and "waitgame" in text
    assert "start \"\" \"%BLK_EXE%\"" in text
    # запуск скрытый: wscript, а не видимая консоль cmd /c start
    cmd = calls[0][0]
    assert "wscript" in cmd[0].lower() and cmd[1] == "//B"
    env = calls[0][1]["env"]
    assert env["BLK_STAGE"] == str(stage)
    assert env["BLK_TARGET"] == str(target)
    assert env["BLK_PID"]
    assert env["BLK_EXE"].endswith("DetectiveBlackville.exe")


def test_staged_update_refuses_readonly_dir(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    stage.mkdir()
    monkeypatch.setattr(updater, "get_install_dir", lambda: tmp_path / "game")
    monkeypatch.setattr(updater, "is_dir_writable", lambda p: False)
    assert updater.run_staged_update(stage, version="0.1.28") is False


def test_preferred_download_uses_zip_when_writable(tmp_path, monkeypatch):
    checker = updater.UpdateChecker()
    checker.result = {
        "download_url": "https://x/Setup.exe",
        "zip_url": "https://x/DetectiveBlackville-Windows.zip",
    }
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "get_install_dir", lambda: tmp_path)
    monkeypatch.setattr(updater, "is_dir_writable", lambda p: True)
    url, kind = checker.preferred_download()
    assert kind == "zip" and url.endswith(".zip")

    monkeypatch.setattr(updater, "is_dir_writable", lambda p: False)
    url, kind = checker.preferred_download()
    assert kind == "setup" and url.endswith(".exe")


def test_install_applies_staged_zip(tmp_path, monkeypatch):
    """install() для .zip не зовёт инсталлятор, а копирует файлы."""
    archive = _make_release_zip(tmp_path / "DetectiveBlackville-Windows.zip")
    checker = updater.UpdateChecker()
    checker.downloaded_path = archive
    checker.download_target_version = "0.1.28"

    monkeypatch.setattr(updater, "stage_zip_update", lambda *a, **kw: tmp_path / "stage")
    called = {}
    monkeypatch.setattr(
        updater,
        "run_staged_update",
        lambda stage, **kw: called.setdefault("stage", stage) is not None,
    )
    monkeypatch.setattr(
        updater, "run_installer", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("setup"))
    )
    assert checker.install() is True
    assert called["stage"] == tmp_path / "stage"


def test_install_reports_staging_error(tmp_path, monkeypatch):
    archive = tmp_path / "DetectiveBlackville-Windows.zip"
    archive.write_bytes(b"not a zip")
    checker = updater.UpdateChecker()
    checker.downloaded_path = archive
    checker.download_target_version = "0.1.28"
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    assert checker.install() is False
    assert "подготовить" in (checker.download_error or "")


def test_stage_env_logs_to_app_log(tmp_path, monkeypatch):
    """Помощник пишет в тот же журнал, который открывает кнопка «ЖУРНАЛ»."""
    log = tmp_path / "update.log"
    monkeypatch.setattr(updater, "get_app_log_path", lambda: log)
    env = updater.build_stage_env(tmp_path / "stage", tmp_path / "game", "0.1.28")
    assert env["BLK_LOG"] == str(log)


def test_stage_helper_logs_copy_result():
    """bat-помощник сообщает код xcopy и версию установленных файлов."""
    text = updater._stage_bat_script()
    assert "xcopy" in text
    assert "xcopy exit code" in text
    assert "NEW EXE MISSING" in text
    assert "copy /y" in text  # синхронизация корневого VERSION


def test_install_reports_setup_failure(tmp_path, monkeypatch):
    """Провал установщика тоже даёт причину для баннера, а не тишину."""
    installer = tmp_path / "DetectiveBlackville-Setup-0.1.28.exe"
    installer.write_bytes(b"MZ")
    checker = updater.UpdateChecker()
    checker.downloaded_path = installer
    checker.download_target_version = "0.1.28"
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")
    monkeypatch.setattr(updater, "run_installer", lambda *a, **kw: False)
    assert checker.install() is False
    assert "установщик" in (checker.download_error or "").lower()


def test_stage_creates_root_version_when_archive_has_none(tmp_path, monkeypatch):
    """Корневой VERSION обязателен: без него игра снова предложит обновление."""
    archive = tmp_path / "DetectiveBlackville-Windows.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("DetectiveBlackville/DetectiveBlackville.exe", b"MZ")
        zf.writestr("DetectiveBlackville/_internal/VERSION", "0.1.28\n")
    stage = updater.stage_zip_update(
        archive, "0.1.28", target_dir=tmp_path / "game", work_dir=tmp_path / "temp"
    )
    assert (stage / "VERSION").read_text(encoding="utf-8").strip() == "0.1.28"


def test_version_in_dir_reads_packaged_candidate(tmp_path):
    """VERSION может лежать только в _internal/detective_game (package data)."""
    packaged = tmp_path / "_internal" / "detective_game"
    packaged.mkdir(parents=True)
    (packaged / "VERSION").write_text("0.1.28\n", encoding="utf-8")
    assert updater._version_in_dir(tmp_path) == "0.1.28"


def test_run_installer_does_not_open_explorer_for_zip(tmp_path, monkeypatch):
    """Регрессия: одно нажатие «Установить» открывало проводник по разу за кадр."""
    archive = tmp_path / "DetectiveBlackville-Windows.zip"
    archive.write_bytes(b"PK")
    calls = []
    monkeypatch.setattr(updater, "open_download_folder", lambda p: calls.append(p))

    assert updater.run_installer(archive) is False
    assert calls == []


def test_install_update_stages_zip_instead_of_manual_unpack(tmp_path, monkeypatch):
    """Кнопка «Установить» должна ставить архив, а не просить распаковать вручную."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game import main as game_main

    archive = tmp_path / "DetectiveBlackville-Windows.zip"
    archive.write_bytes(b"PK")

    class Checker:
        downloaded_path = archive
        download_error = None

        def __init__(self):
            self.installed = 0

        def install(self, silent=None):
            self.installed += 1
            return True

    game = game_main.Game.__new__(game_main.Game)
    game.notifications = []
    game.update_checker = Checker()
    monkeypatch.setattr(game_main, "install_requires_elevation", lambda: False)
    monkeypatch.setattr(game_main, "pygame", pygame)
    opened = []
    monkeypatch.setattr(updater, "open_download_folder", lambda p: opened.append(p))

    with pytest.raises(SystemExit):
        game._install_update()

    assert game.update_checker.installed == 1
    assert opened == [], "архив должен ставиться сам, а не открываться в проводнике"


def test_click_once_fires_until_mouse_released():
    """Защёлка клика: удержание мыши — одно действие, а не по действию на кадр."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((320, 200))
    from detective_game import main as game_main

    game = game_main.Game.__new__(game_main.Game)
    game._click_latch = False
    pressed = {"value": True}
    monkeypatch_target = pygame.mouse
    original = monkeypatch_target.get_pressed
    try:
        pygame.mouse.get_pressed = lambda *a, **kw: (pressed["value"], False, False)
        assert game._click_once() is True   # первый кадр нажатия
        assert game._click_once() is False  # кнопка всё ещё удерживается
        assert game._click_once() is False
        pressed["value"] = False
        assert game._click_once() is False  # отпустили — защёлка сброшена
        assert game._click_latch is False
        pressed["value"] = True
        assert game._click_once() is True   # новое нажатие снова работает
    finally:
        pygame.mouse.get_pressed = original


def test_staged_update_refuses_folder_without_game(tmp_path, monkeypatch):
    """Не копируем файлы в папку, где нет exe игры (защита от «обновилось в никуда»)."""
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "DetectiveBlackville.exe").write_bytes(b"MZ")
    target = tmp_path / "not_a_game"
    target.mkdir()
    monkeypatch.setattr(updater, "get_install_dir", lambda: target)
    monkeypatch.setattr(updater, "is_dir_writable", lambda p: True)
    monkeypatch.setattr(updater, "get_app_log_path", lambda: tmp_path / "update.log")

    assert updater.run_staged_update(stage, version="0.1.28") is False


def test_update_banner_click_does_not_repeat_every_frame(tmp_path, monkeypatch):
    """Регрессия «8 окон проводника»: одно нажатие = одно действие.

    Кнопки баннера создаются в draw() заново каждый кадр, поэтому при
    удержании мыши clicked=True всё время. Проверяем, что установка
    запускается ровно один раз за нажатие.
    """
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((1280, 720))
    from detective_game import main as game_main

    game = game_main.Game()
    game.notifications.clear()
    game.screen_name = "menu"
    game.update_dismissed = False
    archive = tmp_path / "DetectiveBlackville-Windows.zip"
    archive.write_bytes(b"PK")
    game.update_checker.downloaded_path = archive
    game.update_checker.downloading = False
    game.update_checker.done = False
    game.update_checker.result = None

    calls = []
    monkeypatch.setattr(game_main.Game, "_install_update", lambda self: calls.append(1) or False)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda *a, **kw: (True, False, False))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (850, 35))

    for _ in range(8):  # восемь кадров с зажатой кнопкой мыши
        game.draw()

    assert len(calls) == 1, f"установка запускалась {len(calls)} раз за одно нажатие"
