"""Golden: pola nadmiarowe w wyniku buildera względem wzorców (w obie strony).

`test_reference_forms.py` sprawdza tylko, że pola wzorca są w wyniku. Tu porównujemy zbiory
par (techName sekcji, techName pola; nazwy wzorca mapowane przez RENAMES), a TEXT_BLOCK
pomijamy (teksty informacyjne bez danych).
Pole wyniku spoza wzorca musi być na liście ALLOWED_EXTRAS z uzasadnieniem.
"""

from typing import Any

import pytest

from tests.golden.test_reference_forms import (
    RENAMES,
    SAMPLES,
    SECTION_RENAMES,
    _build,
    _fields,
    _load,
    _sections,
)

type Pair = tuple[str, str]

# (wzorzec) -> {(techName sekcji, techName pola): uzasadnienie}.
# Uzasadnienia: decyzja D13 w docs/specyfikacja-techniczna.md (sekcje predefiniowane wg standardu).
_STANDARD_PHONE = (
    "standard sekcji kontaktowej ma osobne pole numeru kierunkowego, którego wzorce nie mają"
)
_STANDARD_PESEL = "standard sekcji osoby (PESEL innej osoby) jest pełniejszy niż wzorzec"
ALLOWED_EXTRAS: dict[str, dict[Pair, str]] = {
    "nadplata": {
        ("dane_do_kontaktu", "numer_kierunkowy"): _STANDARD_PHONE,
        ("dane_innej_osoby", "numer_pesel_inna_osoba"): _STANDARD_PESEL,
        ("dane_podmiotu", "numer_krs"): "standard sekcji podmiotu wymaga KRS (wzorzec go pomija)",
        ("dane_podmiotu", "regon"): "standard sekcji podmiotu wymaga REGON (wzorzec go pomija)",
    },
    "numer_porzadkowy": {
        ("dane_do_kontaktu", "numer_kierunkowy"): _STANDARD_PHONE,
        ("dane_innej_osoby", "numer_pesel_inna_osoba"): _STANDARD_PESEL,
        ("twoje_dane", "numer_pesel"): "tożsamość z MLPZ: PESEL pokazany jako dane inicjalne",
    },
}


def _pairs(form: dict[str, Any], sample: str | None = None) -> set[Pair]:
    """Pary (sekcja, pole) po techName; z `sample` nazwy wzorca mapowane na nasze (RENAMES)."""
    result: set[Pair] = set()
    for tab in form["tabs"]:
        for section in _sections(tab):
            sec = section["techName"]
            for field in _fields(section):
                if field["type"] == "TEXT_BLOCK":
                    continue
                name = field["techName"]
                if sample is not None:
                    name = RENAMES.get((sample, sec, name), name)
                    sec_ours = SECTION_RENAMES.get((sample, sec), sec)
                else:
                    sec_ours = sec
                result.add((sec_ours, name))
    return result


@pytest.fixture(params=sorted(SAMPLES))
def sample(request: pytest.FixtureRequest) -> str:
    name: str = request.param
    return name


def _diff(sample: str) -> tuple[set[Pair], set[Pair]]:
    ref, ours = _pairs(_load(SAMPLES[sample][0]), sample), _pairs(_build(sample))
    return ours - ref, ref - ours


def test_no_unjustified_extra_fields(sample: str) -> None:
    extra, _ = _diff(sample)
    unexplained = extra - set(ALLOWED_EXTRAS[sample])
    assert not unexplained, f"{sample}: pola spoza wzorca bez uzasadnienia: {sorted(unexplained)}"


def test_no_missing_fields(sample: str) -> None:
    _, missing = _diff(sample)
    assert not missing, f"{sample}: pola wzorca nieobecne w wyniku: {sorted(missing)}"


def test_allowlist_is_not_stale(sample: str) -> None:
    extra, _ = _diff(sample)
    assert set(ALLOWED_EXTRAS[sample]) <= extra, "wpis ALLOWED_EXTRAS przestarzały"
