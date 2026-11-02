from pathlib import Path

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
    def boom(url, timeout):
        raise updater.UpdateCheckError("нет связи с GitHub")

    monkeypatch.setattr(updater, "_http_get_json", boom)
    try:
        updater.check_for_updates()
    except updater.UpdateCheckError as e:
        assert "нет связи" in str(e)
    else:
        raise AssertionError("ожидался UpdateCheckError")


def test_check_for_updates_none_when_latest(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.24")
    monkeypatch.setattr(
        updater, "_http_get_json", lambda url, timeout: {"tag_name": "v0.1.24", "assets": []}
    )
    assert updater.check_for_updates() is None


def test_check_for_updates_detects_newer(monkeypatch):
    monkeypatch.setattr(updater, "__version__", "0.1.24")
    monkeypatch.setattr(
        updater,
        "_http_get_json",
        lambda url, timeout: {
            "tag_name": "v0.1.25",
            "html_url": "release",
            "assets": [
                {
                    "name": "DetectiveBlackville-Setup-0.1.25.exe",
                    "browser_download_url": "setup",
                }
            ],
        },
    )
    info = updater.check_for_updates()
    assert info is not None
    assert info["latest"] == "0.1.25"
    assert info["current"] == "0.1.24"
    assert info["download_url"] == "setup"


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
