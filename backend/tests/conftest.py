import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _has_libmagic() -> bool:
    try:
        import magic  # noqa: F401
    except ImportError:
        return False
    return True


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Bez libmagic (np. lokalnie na macOS bez brew) testy `libmagic` są pomijane, nie failują."""
    if _has_libmagic():
        return
    skip = pytest.mark.skip(reason="brak libmagic")
    for item in items:
        if "libmagic" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="development", auth_enabled=False)
    return TestClient(create_app(settings))
