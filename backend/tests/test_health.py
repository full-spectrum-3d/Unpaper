from fastapi.testclient import TestClient


def test_live(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
