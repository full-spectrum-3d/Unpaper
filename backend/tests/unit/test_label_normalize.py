"""Normalizacja etykiet: zdaniowe „W miejscowości” → „Miejscowość”, skróty, wielka litera."""

from typing import Any

import pytest

from app.pipeline.draft_normalize import normalize_draft, normalize_label
from tests.unit.test_draft_normalize import DOC, _codes, _field, _fields, _make


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("W miejscowości", "Miejscowość"),
        ("Przy ulicy", "Ulica"),
        ("W obrębie", "Obręb"),
        ("w kwocie", "Kwota"),
        ("Do dnia", "Data"),
        ("Nr ewidencyjny działki", "Numer ewidencyjny działki"),
        ("nr domu", "Numer domu"),
        ("Tel.", "Telefon"),
        ("Ul.", "Ulica"),
        ("numer rachunku", "Numer rachunku"),
        (": Powierzchnia działki :", "Powierzchnia działki"),
        ("...Cel wynajęcia", "Cel wynajęcia"),
        # Bez zmian: reszta nie jest znanym rzeczownikiem albo jest dłuższa.
        ("W terminie od", "W terminie od"),
        ("Do wiadomości", "Do wiadomości"),
        ("W miejscowości Elbląg", "W miejscowości Elbląg"),
        ("Na podstawie", "Na podstawie"),
        ("Numer rachunku", "Numer rachunku"),
        ("Nrówka", "Nrówka"),
        ("Uzasadnienie", "Uzasadnienie"),
    ],
)
def test_normalize_label(label: str, expected: str) -> None:
    assert normalize_label(label) == expected


def test_labels_are_normalized_with_warning() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[0]["label"] = "W miejscowości"

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _field(out, "f1").label == "Miejscowość"
    assert "W28_LABEL_NORMALIZED" in _codes(warnings)
