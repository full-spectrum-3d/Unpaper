import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_package_import_does_not_load_libmagic() -> None:
    """libmagic ładujemy dopiero przy wykrywaniu MIME: bez niego (Windows) reszta pakietu działa."""
    code = (
        "import sys; import app.pipeline.upload_validation; "
        "sys.exit(1 if 'magic' in sys.modules else 0)"
    )
    result = subprocess.run(  # noqa: S603 - stałe argumenty
        [sys.executable, "-c", code], cwd=BACKEND, timeout=60, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
