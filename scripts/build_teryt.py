"""Buduje backend/app/resources/teryt.json.gz z urzędowych plików TERC i SIMC (GUS).

Użycie:
    python scripts/build_teryt.py                 # pobiera aktualne pliki z eteryt.stat.gov.pl
    python scripts/build_teryt.py TERC.csv SIMC.csv

Wynik: województwo → powiat → gmina → miejscowość (tylko miejscowości samodzielne,
bez części miejscowości, dzielnic i delegatur). Gminy i miejscowości o powtórzonej nazwie
w obrębie rodzica dostają dopisek z rodzajem, np. „Bolesławiec (gmina miejska)”,
a jeśli to nie wystarcza — także z identyfikatorem TERYT/SIMC.
"""

from __future__ import annotations

import csv
import gzip
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from http.cookiejar import CookieJar
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "resources" / "teryt.json.gz"
PAGE = (
    "https://eteryt.stat.gov.pl/eTeryt/rejestr_teryt/udostepnianie_danych/baza_teryt/"
    "uzytkownicy_indywidualni/pobieranie/pliki_pelne.aspx?contrast=default"
)
LEVELS = ["Województwo", "Powiat", "Gmina", "Miejscowość"]
GMINA_KINDS = {"1": "gmina miejska", "2": "gmina wiejska", "3": "gmina miejsko-wiejska"}
LOCALITY_KINDS = {
    "01": "wieś",
    "02": "kolonia",
    "03": "przysiółek",
    "04": "osada",
    "05": "osada leśna",
    "06": "osiedle",
    "07": "schronisko turystyczne",
    "96": "miasto",
}


def _download(button: str) -> str:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    page = opener.open(PAGE).read().decode("utf-8")
    fields = {
        m.group(1): html.unescape(m.group(2))
        for m in re.finditer(
            r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page
        )
    }
    fields |= {"__EVENTTARGET": f"ctl00$body${button}", "__EVENTARGUMENT": ""}
    data = opener.open(PAGE, urllib.parse.urlencode(fields).encode()).read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        return zf.read(name).decode("utf-8-sig")


def _rows(text: str) -> list[dict[str, str]]:
    return [r for r in csv.DictReader(io.StringIO(text), delimiter=";") if r.get("WOJ")]


def _disambiguate(items: list[dict], kind_of) -> None:
    """Powtórzone nazwy dostają „(rodzaj)”, a gdy to nie wystarcza — także identyfikator TERYT."""
    counts = Counter(i["name"] for i in items)
    for item in items:
        if counts[item["name"]] > 1:
            item["label"] = f"{item['name']} ({kind_of(item)})"
    counts = Counter(i.get("label", i["name"]) for i in items)
    for item in items:
        if counts[item.get("label", item["name"])] > 1:
            item["label"] = f"{item['name']} ({kind_of(item)}, {item['code']})"
    for item in items:
        item["name"] = item.pop("label", item["name"])


def _sort(items: list[dict]) -> None:
    items.sort(key=lambda i: (i["name"].casefold(), i["name"]))


def build(terc_csv: str, simc_csv: str) -> dict:
    terc, simc = _rows(terc_csv), _rows(simc_csv)
    voivodeships: dict[str, dict] = {}
    counties: dict[tuple[str, str], dict] = {}
    communes: dict[tuple[str, str, str], dict] = {}
    for r in terc:
        woj, pow_, gmi, rodz = r["WOJ"], r["POW"], r["GMI"], r["RODZ"]
        if not pow_:
            voivodeships[woj] = {"name": r["NAZWA"].lower(), "children": []}
        elif not gmi:
            counties[(woj, pow_)] = {"name": r["NAZWA"], "children": []}
        elif rodz in GMINA_KINDS:
            communes[(woj, pow_, gmi)] = {
                "name": r["NAZWA"],
                "code": woj + pow_ + gmi + rodz,
                "kind": rodz,
                "children": [],
            }

    for r in simc:
        if r["SYM"] != r["SYMPOD"] or r["RM"] not in LOCALITY_KINDS:
            continue
        commune = communes.get((r["WOJ"], r["POW"], r["GMI"]))
        if commune is None:  # dzielnice i delegatury należą do gminy miejskiej powiatu
            commune = next(
                c
                for (w, p, _), c in communes.items()
                if (w, p) == (r["WOJ"], r["POW"]) and c["kind"] == "1"
            )
        commune["children"].append({"name": r["NAZWA"], "kind": r["RM"], "code": r["SYM"]})

    for (woj, pow_, _), commune in communes.items():
        counties[(woj, pow_)]["children"].append(commune)
    for (woj, _), county in counties.items():
        voivodeships[woj]["children"].append(county)

    for county in counties.values():
        _disambiguate(county["children"], lambda c: GMINA_KINDS[c["kind"]])
        for commune in county["children"]:
            _disambiguate(commune["children"], lambda m: LOCALITY_KINDS[m["kind"]])
            _sort(commune["children"])
            commune["children"] = [{"name": m["name"]} for m in commune["children"]]
            del commune["kind"]
        _sort(county["children"])
    for voivodeship in voivodeships.values():
        _sort(voivodeship["children"])
    tree = sorted(voivodeships.values(), key=lambda v: v["name"])
    as_of = max((r["STAN_NA"] for r in terc if r.get("STAN_NA")), default="")
    return {"asOf": as_of, "levels": LEVELS, "items": tree}


def main(argv: list[str]) -> None:
    if len(argv) == 2:
        terc, simc = (Path(p).read_text(encoding="utf-8-sig") for p in argv)
    else:
        terc, simc = _download("BTERCUrzedowyPobierz"), _download("BSIMCUrzedowyPobierz")
    data = build(terc, simc)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    OUT.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    tree = data["items"]
    counties = [c for v in tree for c in v["children"]]
    communes = [g for c in counties for g in c["children"]]
    stats = defaultdict(int, woj=len(tree), pow=len(counties), gmi=len(communes))
    stats["miejsc"] = sum(len(g["children"]) for g in communes)
    print(f"{OUT} ({OUT.stat().st_size} B, stan na {data['asOf']}): {dict(stats)}")


if __name__ == "__main__":
    main(sys.argv[1:])
