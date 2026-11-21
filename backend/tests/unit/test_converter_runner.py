import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

from app.pipeline.converter import STDERR_TAIL_BYTES, ConverterTimeoutError, run_process


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _alive_windows(pid: int) -> bool:
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _alive(pid: int) -> bool:
    # Na Windows os.kill(pid, 0) zabija proces, więc pytamy WinAPI.
    if sys.platform == "win32":
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        return stat.read_text().split()[2] != "Z"  # zombie = już nie działa
    return True


def _wait_dead(pid: int, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


async def _wait_file(path: Path, timeout_s: float = 5.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        await asyncio.sleep(0.05)
    raise AssertionError(f"brak pliku {path}")


async def test_run_process_returns_code_and_stderr_tail(tmp_path: Path) -> None:
    code = "import sys; sys.stderr.write('x' * 5000 + 'END'); sys.exit(3)"
    result = await run_process(_python(code), env=dict(os.environ), cwd=tmp_path, timeout_s=30)
    assert result.returncode == 3
    assert len(result.stderr_tail) == STDERR_TAIL_BYTES
    assert result.stderr_tail.endswith(b"END")


async def test_run_process_timeout(tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(ConverterTimeoutError):
        await run_process(
            _python("import time; time.sleep(30)"),
            env=dict(os.environ),
            cwd=tmp_path,
            timeout_s=0.5,
        )
    assert time.monotonic() - started < 5


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="grupy procesów tylko na POSIX")
async def test_run_process_timeout_kills_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    code = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    with pytest.raises(ConverterTimeoutError):
        await run_process(_python(code), env=dict(os.environ), cwd=tmp_path, timeout_s=1)
    grandchild = int(pid_file.read_text())
    assert _wait_dead(grandchild)


async def test_run_process_cancel_kills_process(tmp_path: Path) -> None:
    pid_file = tmp_path / "self.pid"
    code = f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); time.sleep(30)"
    task = asyncio.create_task(
        run_process(_python(code), env=dict(os.environ), cwd=tmp_path, timeout_s=60)
    )
    pid = int(await _wait_file(pid_file))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert _wait_dead(pid)
