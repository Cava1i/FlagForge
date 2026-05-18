import stat
from pathlib import Path


def test_start_script_exists_and_uses_expected_ports():
    script = Path("scripts/start-flagforge.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "BACKEND_PORT" in content
    assert "FRONTEND_PORT" in content
    assert "5001" in content
    assert "5174" in content
    assert "VITE_API_TARGET" in content
    assert "backend.web.app" in content
    assert "npm --prefix" in content


def test_start_script_cleans_up_child_processes():
    content = Path("scripts/start-flagforge.sh").read_text(encoding="utf-8")

    assert "trap cleanup" in content
    assert "BACKEND_PID" in content
    assert "FRONTEND_PID" in content


def test_root_start_wrapper_points_to_main_script():
    script = Path("start.sh")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "scripts/start-flagforge.sh" in content
    assert "exec bash" in content


def test_start_scripts_are_executable():
    for script in [Path("start.sh"), Path("scripts/start-flagforge.sh")]:
        mode = script.stat().st_mode
        assert mode & stat.S_IXUSR
