"""Metryka podobieństwa strukturalnego wynik vs wzorzec (testy golden, spec §13.1).

    uv run --project backend python scripts/compare.py out/wynik.json wymagania/wzorzec.json

Liczy pokrycie sekcji wzorca (po tytule), pokrycie pól (po `techName`, inaczej po etykiecie)
i zgodność typów dopasowanych pól. Kod wyjścia 1, gdy pokrycie pól < --threshold
(domyślnie 0.85, spec §13.2). Plik wyniku może być samym formularzem albo `{form, report}`.
Szczegółowe porównanie (stany, słowniki, kolejność) robią testy `backend/tests/golden`.

    python3 scripts/compare.py --self-test
"""

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SECTION_TYPES = {"SECTION", "REPEATING_SECTION", "INFO_SECTION"}


def _norm(text: str) -> str:
    """Porównanie tekstu bez wielkości liter i nadmiarowych spacji.

    >>> _norm('  Imię  i NAZWISKO ')
    'imię i nazwisko'
    """
    return " ".join(text.lower().split())


def nodes(tree: Any) -> Iterator[dict[str, Any]]:
    """Wszystkie elementy formularza (słowniki z `type` i `techName`), w dowolnym zagnieżdżeniu.

    >>> [n["techName"] for n in nodes({"tabs": [{"questions": [{"field": {"type": "SECTION",
    ...     "techName": "s", "repeatingSectionGrid": [{"field": {"type": "TEXT_FIELD",
    ...     "techName": "a"}}]}}]}]})]
    ['s', 'a']
    """
    if isinstance(tree, dict):
        if "type" in tree and "techName" in tree:
            yield tree
        for value in tree.values():
            yield from nodes(value)
    elif isinstance(tree, list):
        for value in tree:
            yield from nodes(value)


def compare(result: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Pokrycie wzorca przez wynik: (trafienia, wszystkie) dla sekcji, pól i typów.

    >>> ref = {"tabs": [{"type": "SECTION", "techName": "s", "title": "Dane"},
    ...     {"type": "TEXT_FIELD", "techName": "imie", "label": "Imię"},
    ...     {"type": "TEXT_FIELD", "techName": "pesel", "label": "PESEL"}]}
    >>> out = {"tabs": [{"type": "SECTION", "techName": "x", "title": "dane"},
    ...     {"type": "TEXT_FIELD", "techName": "imie_1", "label": "imię"},
    ...     {"type": "NUMBER", "techName": "pesel", "label": "Numer"}]}
    >>> r = compare(out, ref)
    >>> r["sections"], r["fields"], r["types"], r["missing_fields"]
    ((1, 1), (2, 2), (1, 2), [])
    """
    ours = list(nodes(result))
    ref = list(nodes(reference))

    our_titles = {_norm(n.get("title", "")) for n in ours if n["type"] in SECTION_TYPES}
    ref_sections = [n for n in ref if n["type"] in SECTION_TYPES]
    missing_sections = [
        n.get("title", "") for n in ref_sections if _norm(n.get("title", "")) not in our_titles
    ]

    our_fields = [n for n in ours if n["type"] not in SECTION_TYPES]
    by_tech = {n["techName"]: n for n in our_fields}
    by_label = {_norm(n.get("label", "")): n for n in our_fields if n.get("label")}
    ref_fields = [n for n in ref if n["type"] not in SECTION_TYPES]
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    missing_fields: list[str] = []
    for field in ref_fields:
        twin = by_tech.get(field["techName"]) or by_label.get(_norm(field.get("label", "")))
        if twin is None:
            missing_fields.append(field["techName"])
        else:
            matched.append((field, twin))

    return {
        "sections": (len(ref_sections) - len(missing_sections), len(ref_sections)),
        "fields": (len(matched), len(ref_fields)),
        "types": (sum(a["type"] == b["type"] for a, b in matched), len(matched)),
        "missing_sections": missing_sections,
        "missing_fields": missing_fields,
    }


def _ratio(pair: tuple[int, int]) -> float:
    return pair[0] / pair[1] if pair[1] else 1.0


def _load_form(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data["form"] if "form" in data and "report" in data else data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("result", type=Path, nargs="?")
    parser.add_argument("reference", type=Path, nargs="?")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--self-test", action="store_true", help="uruchom doctesty i wyjdź")
    args = parser.parse_args()
    if args.self_test:
        import doctest

        sys.exit(1 if doctest.testmod().failed else 0)
    if args.result is None or args.reference is None:
        parser.error("podaj plik wyniku i plik wzorca")

    r = compare(_load_form(args.result), _load_form(args.reference))
    for name in ("sections", "fields", "types"):
        hit, total = r[name]
        print(f"{name:9} {hit}/{total} ({_ratio(r[name]):.0%})")
    if r["missing_sections"]:
        print("brak sekcji:", ", ".join(r["missing_sections"]))
    if r["missing_fields"]:
        print("brak pól:", ", ".join(r["missing_fields"]))
    sys.exit(0 if _ratio(r["fields"]) >= args.threshold else 1)


if __name__ == "__main__":
    main()
