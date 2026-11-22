import json

from fastapi.testclient import TestClient


def _find(nodes: list[dict], name: str) -> dict:
    return next(n for n in nodes if n["name"] == name)


def test_teryt_has_full_hierarchy(client: TestClient) -> None:
    response = client.get("/api/v1/dictionaries/teryt")
    assert response.status_code == 200
    body = response.json()
    assert body["levels"] == ["Województwo", "Powiat", "Gmina", "Miejscowość"]

    voivodeships = body["items"]
    assert len(voivodeships) == 16
    counties = [c for v in voivodeships for c in v["children"]]
    assert len(counties) == 380
    assert len(_find(voivodeships, "małopolskie")["children"]) == 22

    communes = [g for c in counties for g in c["children"]]
    assert len(communes) > 2400
    wieliczka = _find(
        _find(_find(voivodeships, "małopolskie")["children"], "wielicki")["children"], "Wieliczka"
    )
    assert wieliczka["code"] == "1219053"
    assert {"Wieliczka", "Kokotów"} <= {m["name"] for m in wieliczka["children"]}


def test_teryt_disambiguates_same_named_communes(client: TestClient) -> None:
    body = client.get("/api/v1/dictionaries/teryt").json()
    county = _find(_find(body["items"], "dolnośląskie")["children"], "bolesławiecki")
    names = {g["name"] for g in county["children"]}
    assert {"Bolesławiec (gmina miejska)", "Bolesławiec (gmina wiejska)"} <= names


def test_teryt_served_gzipped_when_accepted(client: TestClient) -> None:
    raw = client.get("/api/v1/dictionaries/teryt", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in raw.headers
    assert json.loads(raw.content)["levels"][0] == "Województwo"

    zipped = client.get("/api/v1/dictionaries/teryt", headers={"Accept-Encoding": "gzip, deflate"})
    assert zipped.headers["content-encoding"] == "gzip"
    assert zipped.json() == json.loads(raw.content)
