"""Ocena szkicu względem oczekiwanych pól przypadku.

Etykiety porównujemy luźno (model ma prawo napisać „Nr działki” zamiast „Numer
ewidencyjny działki”): podobieństwo znaków albo wspólne rdzenie słów. Pola oznaczone
`optional` nie liczą się do trafności, ale ich dopasowanie nie jest też „nadmiarowym” polem.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from app.models.draft import FormDraft

MATCH_THRESHOLD = 0.6
TITLE_THRESHOLD = 0.8
STEM = 4
_WORD = re.compile(r"\w+")
_STOP = frozenset({"i", "w", "z", "o", "na", "do", "od", "lub", "oraz", "nr", "numer", "się"})


@dataclass
class CaseScore:
    expected: int
    matched: int
    draft_fields: int
    extra: int
    kind_ok: int
    title_ok: bool | None
    authority_ok: bool | None
    missing: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    wrong_kinds: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.matched / self.expected if self.expected else 1.0

    @property
    def precision(self) -> float:
        counted = self.draft_fields
        return (counted - self.extra) / counted if counted else 0.0


def similarity(a: str, b: str) -> float:
    """Od 0 do 1: maksimum z podobieństwa znaków i pokrycia rdzeni słów krótszej etykiety."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    chars = SequenceMatcher(None, na, nb, autojunk=False).ratio()
    sa, sb = _stems(na), _stems(nb)
    if not sa or not sb:
        return chars
    shorter, longer = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    words = len(shorter & longer) / len(shorter) * (0.85 if len(shorter) < len(longer) else 1.0)
    return max(chars, words)


def score_draft(draft: FormDraft | None, expected: dict[str, Any]) -> CaseScore:
    specs: list[dict[str, Any]] = expected["fields"]
    fields = [f for _, f in draft.iter_fields()] if draft else []
    pairs = sorted(
        (
            (max(similarity(f.label, name) for name in [s["label"], *s["aliases"]]), i, j)
            for i, f in enumerate(fields)
            for j, s in enumerate(specs)
        ),
        reverse=True,
    )
    used_f: set[int] = set()
    used_s: set[int] = set()
    matches: list[tuple[int, int]] = []
    for value, i, j in pairs:
        if value < MATCH_THRESHOLD:
            break
        if i in used_f or j in used_s:
            continue
        used_f.add(i)
        used_s.add(j)
        matches.append((i, j))

    required = [j for j, s in enumerate(specs) if not s["optional"]]
    matched_required = [(i, j) for i, j in matches if not specs[j]["optional"]]
    kind_ok = [(i, j) for i, j in matched_required if fields[i].kind in specs[j]["kind"]]
    return CaseScore(
        expected=len(required),
        matched=len(matched_required),
        draft_fields=len(fields),
        extra=len(fields) - len(used_f),
        kind_ok=len(kind_ok),
        title_ok=_ok(draft.title if draft else "", expected.get("title"), TITLE_THRESHOLD),
        authority_ok=None
        if not expected.get("authority_name")
        else bool(draft)
        and draft is not None
        and draft.authority_kind == expected["authority_kind"]
        and similarity(draft.authority_name, expected["authority_name"]) >= TITLE_THRESHOLD,
        missing=[specs[j]["label"] for j in required if j not in used_s],
        extras=[f.label for i, f in enumerate(fields) if i not in used_f],
        wrong_kinds=[
            f"{fields[i].label}: {fields[i].kind} (oczekiwano {'/'.join(specs[j]['kind'])})"
            for i, j in matched_required
            if (i, j) not in kind_ok
        ],
    )


def _ok(actual: str, wanted: str | None, threshold: float) -> bool | None:
    if not wanted:
        return None
    return SequenceMatcher(None, _norm(actual), _norm(wanted), autojunk=False).ratio() >= threshold


def _norm(text: str) -> str:
    return " ".join(_WORD.findall(text.casefold()))


def _stems(text: str) -> set[str]:
    return {w[:STEM] for w in text.split() if w not in _STOP}
