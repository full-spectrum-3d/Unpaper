"""Golden: wynik buildera kontra oficjalne konfiguracje wzorcowe (plan, Task 8)."""

import json
import os
import re
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any

import pytest

from app.models.draft import FormDraft
from app.pipeline.build import BuildOptions, build_form
from app.pipeline.verify import verify_form

ROOT = Path(__file__).parents[3]
REFERENCES = ROOT / "wymagania"
DRAFTS = Path(__file__).parent / "drafts"

SAMPLES: dict[str, tuple[str, str, BuildOptions]] = {
    "nadplata": (
        "konfiguracja_form_wniosekOStwierdzenieNadplatyPodatku.json",
        "nadplata.json",
        BuildOptions(identity_source="PESEL"),
    ),
    "numer_porzadkowy": (
        "konfiguracja_form_wniosekOUstalenieNumeruPorzadkowegoNieruchomosci.json",
        "numer_porzadkowy.json",
        BuildOptions(identity_source="MLPZ", signed=False),
    ),
}

_P_FILE = "wzorce są sprzeczne: P nazywa pola plików inaczej niż N; szablon wg N"

# Pole wzorca pod inną nazwą u nas: (wzorzec, sekcja, techName wzorca) -> nasz techName.
# Przemianowane pola są nadal porównywane (typ, stany, dane inicjalne).
RENAMES: dict[tuple[str, str, str], str] = {
    ("numer_porzadkowy", "lokalizacja_budynku", "obreb_numer"): "obreb",
    ("numer_porzadkowy", "lokalizacja_budynku", "ulica_budynku"): "ulica_2",
    ("numer_porzadkowy", "pelnomocnictwo", "dokument_z_potwierdzeniem_podpisany_elektronicznie"): (
        "plik_dokumentu_z_pelnomocnictwem"
    ),
    ("numer_porzadkowy", "oplata_skarbowa_pelnomocnictwo_1", "potwierdzenie_przelewu"): (
        "plik_z_potwierdzeniem_przelewu"
    ),
    ("numer_porzadkowy", "oplata_skarbowa_pelnomocnictwo_2", "potwierdzenie_przelewu_2"): (
        "plik_z_potwierdzeniem_przelewu_2"
    ),
}

# Różnice w słowniku (dictionaryName, multiLevelTree, searchEnabled); typ i stany nadal porównywane.
DICTIONARY_DEVIATIONS: dict[tuple[str, str, str], str] = {
    ("numer_porzadkowy", "adres_zamieszkania", "wojewodztwo"): (
        "wzorce są sprzeczne: P ma TERYT_DOWODOWY, N i standard TERYT_4G_DOWODOWY"
    ),
    (
        "nadplata",
        "adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem",
        "wojewodztwo_inna_osoba",
    ): ("wzorzec N ma TERYT_DOWODOWY, a standard i P TERYT_4G_DOWODOWY"),
}

# Sekcje o innej nazwie u nas (P: „zgoda_sekcja”).
SECTION_RENAMES: dict[tuple[str, str], str] = {
    ("numer_porzadkowy", "zgoda_sekcja"): "zgoda_wyrazenie"
}

# Pola adresu, które zasłania checkbox „Brak …” (standard; wzorce go nie zawierają).
NO_DATA_GUARDED = re.compile(
    r"(ulica|kod_pocztowy|numer_lokalu)(_(siedziba|inna_osoba))?(_zagranica)?"
)

_DICT_KEYS = ("dictionaryName", "multiLevelTree", "searchEnabled")
# Minimalne liczby faktycznie porównanych elementów (ochrona przed pustymi testami).
MIN_COUNTS = {
    "nadplata": {"nodes": 73, "states": 31, "initial": 9},
    "numer_porzadkowy": {"nodes": 69, "states": 29, "initial": 8},
}


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((REFERENCES / name).read_text(encoding="utf-8"))
    return data


def _build(sample: str) -> dict[str, Any]:
    _, draft_name, options = SAMPLES[sample]
    draft = FormDraft.model_validate_json((DRAFTS / draft_name).read_text(encoding="utf-8"))
    counter = count()
    options = BuildOptions(
        identity_source=options.identity_source,
        signed=options.signed,
        id_factory=lambda: f"id-{next(counter)}",
    )
    form = build_form(draft, options).form.to_import_json()
    if os.environ.get("GOLDEN_WRITE") == "1":
        out = ROOT / "out" / "golden"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{sample}.json").write_text(
            json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return form


def _sections(tab: dict[str, Any]) -> list[dict[str, Any]]:
    return [q["field"] for q in tab["questions"]]


def _fields(section: dict[str, Any]) -> list[dict[str, Any]]:
    return [g["field"] for g in section["repeatingSectionGrid"]]


def _squash(query: str) -> str:
    return re.sub(r"\s+", "", query)


def _states(node: dict[str, Any]) -> list[tuple[str, str]]:
    return [(s["type"], _squash(s["query"])) for s in node.get("states") or []]


def _dict_diffs(ours: dict[str, Any], ref: dict[str, Any]) -> list[str]:
    """Różnice słownikowe; flagi, których wzorzec nie podaje (P bywa niespójny), pomijamy."""
    return [
        k for k in _DICT_KEYS if (k == "dictionaryName" or k in ref) and ours.get(k) != ref.get(k)
    ]


@dataclass
class Item:
    """Para węzłów (wzorzec, nasz) o tej samej roli; `ours` to None, gdy nie ma odpowiednika."""

    section: str
    name: str
    ref: dict[str, Any]
    ours: dict[str, Any] | None
    is_section: bool

    @property
    def key(self) -> tuple[str, str]:
        return (self.section, self.name)


def _aligned(sample: str) -> list[Item]:
    """Wszystkie sekcje i pola wzorca zestawione z naszymi (z uwzględnieniem RENAMES)."""
    ref, ours = _load(SAMPLES[sample][0]), _build(sample)
    items: list[Item] = []
    for rt, ot in zip(ref["tabs"], ours["tabs"], strict=True):
        ours_sections = {s["techName"]: s for s in _sections(ot)}
        for rs in _sections(rt):
            rs_name = rs["techName"]
            os_ = ours_sections.get(SECTION_RENAMES.get((sample, rs_name), rs_name))
            items.append(Item(rs_name, rs_name, rs, os_, True))
            have = {f["techName"]: f for f in _fields(os_)} if os_ else {}
            for rf in _fields(rs):
                our_name = RENAMES.get((sample, rs_name, rf["techName"]), rf["techName"])
                items.append(Item(rs_name, rf["techName"], rf, have.get(our_name), False))
    return items


@pytest.fixture(params=sorted(SAMPLES))
def sample(request: pytest.FixtureRequest) -> str:
    name: str = request.param
    return name


def test_structure_matches_reference(sample: str) -> None:
    ref, ours = _load(SAMPLES[sample][0]), _build(sample)
    assert len(ours["tabs"]) == len(ref["tabs"])
    for index, (rt, ot) in enumerate(zip(ref["tabs"], ours["tabs"], strict=True)):
        if sample == "numer_porzadkowy" and index == len(ref["tabs"]) - 2:
            # znane odstępstwo: wzorzec P nazywa tę stronę „Kontakt z urzędem”
            assert rt["title"] == "Kontakt z urzędem"
            assert ot["title"] == "Kontakt i zgody"
        else:
            assert ot["title"] == rt["title"]
        assert ot["type"] == rt["type"]
        ref_names = [
            SECTION_RENAMES.get((sample, s["techName"]), s["techName"]) for s in _sections(rt)
        ]
        assert [s["techName"] for s in _sections(ot)] == ref_names, rt["title"]


def test_field_coverage(sample: str) -> None:
    items = _aligned(sample)
    assert len(items) >= MIN_COUNTS[sample]["nodes"]
    for item in items:
        assert item.ours is not None, f"{sample} {item.key}: brak odpowiednika"
        assert item.ours["type"] == item.ref["type"], (sample, item.key)
        if (sample, *item.key) in DICTIONARY_DEVIATIONS:
            continue
        assert not _dict_diffs(item.ours, item.ref), (sample, item.key)
        if not item.is_section and (sample, *item.key) not in RENAMES:
            assert item.ours["title"] == item.ref["title"], (sample, item.key)


def test_field_order_matches_reference(sample: str) -> None:
    ref, ours = _load(SAMPLES[sample][0]), _build(sample)
    compared = 0
    for rt, ot in zip(ref["tabs"], ours["tabs"], strict=True):
        ours_sections = {s["techName"]: s for s in _sections(ot)}
        for rs in _sections(rt):
            rs_name = rs["techName"]
            os_ = ours_sections[SECTION_RENAMES.get((sample, rs_name), rs_name)]
            ref_order = [
                RENAMES.get((sample, rs_name, g["field"]["techName"]), g["field"]["techName"])
                for g in sorted(rs["repeatingSectionGrid"], key=lambda g: g["y"])
            ]
            our_order = [
                g["field"]["techName"]
                for g in sorted(os_["repeatingSectionGrid"], key=lambda g: g["y"])
            ]
            shared = set(ref_order) & set(our_order)
            assert [n for n in our_order if n in shared] == [n for n in ref_order if n in shared], (
                sample,
                rs_name,
            )
            compared += len(shared)
    assert compared >= MIN_COUNTS[sample]["nodes"] // 2


def test_states_match_reference(sample: str) -> None:
    compared = 0
    for item in _aligned(sample):
        if not item.ref.get("states"):
            continue
        assert item.ours is not None, (sample, item.key)
        ours, ref = _states(item.ours), _states(item.ref)
        if NO_DATA_GUARDED.fullmatch(item.key[1]):
            # checkbox „Brak …” (standard) dokłada do warunku wzorca drugi człon
            assert len(ours) == len(ref), (sample, item.key)
            for (o_type, o_query), (r_type, r_query) in zip(ours, ref, strict=True):
                assert o_type == r_type
                assert r_query in o_query and "Brak" in o_query, (sample, item.key)
        else:
            assert ours == ref, (sample, item.key)
        compared += 1
    assert compared >= MIN_COUNTS[sample]["states"]


def test_initial_data_match_reference(sample: str) -> None:
    compared = 0
    for item in _aligned(sample):
        if item.ref.get("defaultValueType") != "EXTERNAL_SYSTEM":
            continue
        assert item.ours is not None, (sample, item.key)
        assert item.ours.get("defaultValue") == item.ref.get("defaultValue"), item.key
        assert item.ours.get("defaultValueType") == item.ref.get("defaultValueType"), item.key
        compared += 1
    assert compared >= MIN_COUNTS[sample]["initial"]


def test_output_is_valid(sample: str) -> None:
    result = verify_form(_build(sample), autofix=False)
    assert result.valid, result.errors


def test_known_deviations_still_deviate() -> None:
    """Każdy wpis ma nadal różnić się od wzorca; inaczej jest przestarzały."""
    for (sample, section, ref_name), our_name in RENAMES.items():
        ours = {i.key: i.ours for i in _aligned(sample)}
        assert ours[(section, ref_name)] is not None, (sample, section, ref_name)
        assert our_name != ref_name
        names = {o["techName"] for o in ours.values() if o is not None}
        assert our_name in names
        assert ref_name not in names, f"wpis RENAMES przestarzały: {ref_name}"
    for sample, section, name in DICTIONARY_DEVIATIONS:
        item = next(i for i in _aligned(sample) if i.key == (section, name))
        assert item.ours is not None
        assert _dict_diffs(item.ours, item.ref), f"wpis DICTIONARY_DEVIATIONS przestarzały: {name}"
    for sample, section in SECTION_RENAMES:
        names = {s["techName"] for t in _build(sample)["tabs"] for s in _sections(t)}
        assert section not in names
