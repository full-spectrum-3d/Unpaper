"""Tytuł formularza bez odwołań do przepisów (standard, W11)."""

import pytest

from app.pipeline.build.fields import normalize_title
from app.pipeline.issues import IssueCode

# --- D1: tytuł ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Wniosek o wydanie zaświadczenia na podstawie art. 12 ust. 3 ustawy z dnia "
            "14 czerwca 1960 r. Kodeks postępowania administracyjnego",
            "Wniosek o wydanie zaświadczenia",
        ),
        (
            "Wniosek o zwrot opłaty (Dz. U. z 2023 r. poz. 123 z późn. zm.)",
            "Wniosek o zwrot opłaty",
        ),
        ("Wniosek o zwrot, zgodnie z art. 75 § 2 Ordynacji podatkowej", "Wniosek o zwrot"),
        (
            "Wniosek o rejestrację, o którym mowa w art. 5 ust. 1 pkt 2",
            "Wniosek o rejestrację",
        ),
        ("Wniosek o wpis (na podstawie art. 7 ustawy)", "Wniosek o wpis"),
    ],
)
def test_title_legal_reference_removed(raw: str, expected: str) -> None:
    title, issues = normalize_title(raw)
    assert title == expected
    assert [i.code for i in issues] == [IssueCode.W11_TITLE_LEGAL_REFERENCE]


def test_title_without_prefix_still_warns_after_cleaning() -> None:
    title, issues = normalize_title("Karta pobytu na podstawie art. 3 ust. 1")
    assert title == "Karta pobytu"
    assert {i.code for i in issues} == {
        IssueCode.W11_TITLE_LEGAL_REFERENCE,
        IssueCode.W05_TITLE_PREFIX,
    }


def test_long_title_is_still_truncated() -> None:
    title, issues = normalize_title("Wniosek " + "x" * 300 + " na podstawie art. 3")
    assert len(title) <= 255
    assert IssueCode.W08_TITLE_TRUNCATED in {i.code for i in issues}


@pytest.mark.parametrize(
    "raw",
    ["Wniosek o wydanie karty", "Wniosek o artykuły biurowe", "Deklaracja o wysokości opłaty"],
)
def test_clean_title_unchanged(raw: str) -> None:
    title, issues = normalize_title(raw)
    assert title == raw
    assert issues == []


def test_title_made_only_of_reference_is_kept() -> None:
    title, _ = normalize_title("na podstawie art. 3")
    assert title == "na podstawie art. 3"
