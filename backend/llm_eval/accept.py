"""Agregacja powtórzeń i reguła przyjęcia zmiany względem stanu wyjściowego."""

from collections import defaultdict
from statistics import fmean
from typing import Any

MEAN_TOLERANCE = 0.02  # holdout: spadek średniej o więcej niż 2 pp to naruszenie
CASE_TOLERANCE = 0.10  # holdout: spadek pojedynczego dokumentu o więcej niż 10 pp
EPS = 1e-9
METRICS = (("recall", "trafność"), ("precision", "precyzja"))


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jeden wiersz na (set, case, model); fallback liczy się jak każdy inny przebieg."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r.get("set", "cases"), r["case"], r["model"])].append(r)
    out = []
    for (set_name, case, model), rs in groups.items():
        item: dict[str, Any] = {"set": set_name, "case": case, "model": model, "runs": len(rs)}
        for key, _ in METRICS:
            vals = [r[key] for r in rs]
            item[key] = fmean(vals)
            item[f"{key}_min"] = min(vals)
            item[f"{key}_max"] = max(vals)
        out.append(item)
    return out


def _means(rows: list[dict[str, Any]], key: str) -> float:
    return fmean(r[key] for r in rows)


def violations(baseline: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]:
    """Opisy naruszeń reguły przyjęcia; pusta lista oznacza przyjęcie."""
    base = {(r["set"], r["case"], r["model"]): r for r in baseline}
    found: list[str] = []
    for model in dict.fromkeys(r["model"] for r in current):
        for set_name in ("cases", "holdout"):
            cur = [r for r in current if r["model"] == model and r["set"] == set_name]
            known = []
            for r in cur:
                b = base.get((set_name, r["case"], model))
                if b is None:
                    found.append(f"{model}: {set_name}/{r['case']} brak w stanie wyjściowym")
                    continue
                known.append((b, r))
                if set_name != "holdout":
                    continue
                for key, name in METRICS:
                    drop = b[key] - r[key]
                    if drop > CASE_TOLERANCE + EPS:
                        found.append(
                            f"{model}: holdout/{r['case']} {name} spadła o {drop:.0%} "
                            f"({b[key]:.0%} -> {r[key]:.0%})"
                        )
            if not known:
                continue
            tol = MEAN_TOLERANCE if set_name == "holdout" else 0.0
            for key, name in METRICS:
                b_mean = _means([b for b, _ in known], key)
                c_mean = _means([r for _, r in known], key)
                if b_mean - c_mean > tol + EPS:
                    found.append(
                        f"{model}: {set_name} średnia {name} spadła ({b_mean:.1%} -> {c_mean:.1%})"
                    )
    return found
