"""Generator zapytań JSONata dla states SHOW/READ_ONLY i ich test semantyczny (spec §8.7).

Escapowanie literałów w jsonata-python 0.7 (sprawdzone empirycznie):
- `\\"` i `\\\\` działają w `"…"` i w `'…'`, podobnie `\\n`, `\\r`, `\\t`, `\\uXXXX`;
- `\\'` kończy się błędem kompilacji w obu rodzajach cudzysłowu, więc apostrofu nie da się
  escapować;
- typograficzne cudzysłowy (`„”`) przechodzą bez zmian.
Dlatego wartości zawsze trafiają do `"…"` (escape `\\\\` i `\\"`), a tytuł lub techName
idzie do `'…'`, chyba że zawiera apostrof; wtedy użyty jest `"…"`.
"""

import itertools
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import jsonata

from app.models.form import FieldType, StateType
from app.models.warning import ConversionWarning
from app.pipeline.build.ir import AllOf, AnyOf, Condition, Eq, Not, PageNode
from app.pipeline.issues import IssueCode

OTHER_VALUE = "__inna_wartosc__"
MAX_COMBINATIONS = 64


@dataclass(frozen=True)
class FieldLocation:
    page_title: str
    section_tech_name: str
    field_tech_name: str
    repeating: bool
    section_key: str


Locate = Callable[[str], FieldLocation]


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _value_literal(value: str) -> str:
    return f'"{_escape(value)}"'


def _name_literal(name: str) -> str:
    return f'"{_escape(name)}"' if "'" in name else f"'{_escape(name)}'"


def _path(loc: FieldLocation, context_section_key: str | None) -> str:
    tab = f"tabs[{_name_literal(loc.page_title)} in title]"
    section = f"questions[{_name_literal(loc.section_tech_name)} in field.techName]"
    if not loc.repeating:
        fld = f"repeatingSectionGrid[{_name_literal(loc.field_tech_name)} in field.techName]"
        return f"{tab}.{section}.field.{fld}.field.__userAnswer"
    if context_section_key != loc.section_key:
        raise ValueError(
            f"Pole {loc.field_tech_name!r} z sekcji powtarzającej jest poza jej kontekstem"
        )
    fld = f"[{_name_literal(loc.field_tech_name)} in fieldTechName]"
    return f"{tab}.{section}.field.__userAnswer[$repeatingSectionIndex]{fld}.answers"


def _atom(eq: Eq, locate: Locate, context: str | None) -> str:
    return f"{_value_literal(eq.value)} in {_path(locate(eq.ref), context)}"


def _render(cond: Condition, locate: Locate, context: str | None) -> str:
    match cond:
        case Eq():
            return f"({_atom(cond, locate, context)})"
        case Not(cond=Eq() as inner):
            return f"$not({_atom(inner, locate, context)})"
        case Not(cond=inner):
            return f"$not({_render(inner, locate, context)})"
        case AllOf(items=items) | AnyOf(items=items):
            op = " and " if isinstance(cond, AllOf) else " or "
            parts = []
            for item in items:
                text = _render(item, locate, context)
                parts.append(f"({text})" if isinstance(item, AllOf | AnyOf) else text)
            return op.join(parts)


def condition_to_jsonata(
    cond: Condition, locate: Locate, *, context_section_key: str | None
) -> str:
    return _render(cond, locate, context_section_key)


def query_compiles(query: str) -> str | None:
    try:
        jsonata.Jsonata(query)
    except Exception as exc:
        return str(exc)
    return None


_LITERAL = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", re.DOTALL)
_UNESCAPES = {"n": "\n", "r": "\r", "t": "\t"}


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: _UNESCAPES.get(m.group(1), m.group(1)), text, flags=re.DOTALL)


def query_references(query: str) -> tuple[set[str], set[str]]:
    """Zwraca (tytuły stron, techName) użyte w zapytaniu."""
    titles: set[str] = set()
    names: set[str] = set()
    for match in _LITERAL.finditer(query):
        text = _unescape(match.group(1) if match.group(1) is not None else match.group(2))
        end = match.end()  # startswith z pozycją: bez kopiowania reszty zapytania
        if query.startswith(" in title", end):
            titles.add(text)
        elif query.startswith((" in field.techName", " in fieldTechName"), end):
            names.add(text)
    return titles, names


def _refs(cond: Condition) -> Iterator[Eq]:
    match cond:
        case Eq():
            yield cond
        case Not(cond=inner):
            yield from _refs(inner)
        case AllOf(items=items) | AnyOf(items=items):
            for item in items:
                yield from _refs(item)


def _evaluate(cond: Condition, answers: dict[str, str]) -> bool:
    match cond:
        case Eq():
            return answers[cond.ref] == cond.value
        case Not(cond=inner):
            return not _evaluate(inner, answers)
        case AllOf(items=items):
            return all(_evaluate(i, answers) for i in items)
        case AnyOf(items=items):
            return any(_evaluate(i, answers) for i in items)


def _document(answers: dict[str, str], locate: Locate) -> dict[str, Any]:
    tabs: dict[str, dict[str, dict[str, Any]]] = {}
    for ref, value in answers.items():
        loc = locate(ref)
        section = tabs.setdefault(loc.page_title, {}).setdefault(
            loc.section_tech_name, {"repeating": loc.repeating, "fields": []}
        )
        section["fields"].append((loc.field_tech_name, value))
    doc_tabs = []
    for title, sections in tabs.items():
        questions = []
        for tech, data in sections.items():
            if data["repeating"]:
                row = [{"fieldTechName": f, "answers": [v]} for f, v in data["fields"]]
                field: dict[str, Any] = {"techName": tech, "__userAnswer": [row]}
            else:
                grid = [{"field": {"techName": f, "__userAnswer": [v]}} for f, v in data["fields"]]
                field = {"techName": tech, "repeatingSectionGrid": grid}
            questions.append({"field": field})
        doc_tabs.append({"title": title, "questions": questions})
    return {"tabs": doc_tabs}


def check_condition_query(query: str, cond: Condition, locate: Locate) -> bool:
    """Porównuje wynik zapytania z ewaluacją warunku na syntetycznych dokumentach."""
    candidates: dict[str, list[str]] = {}
    for eq in _refs(cond):
        values = candidates.setdefault(eq.ref, [OTHER_VALUE])
        if eq.value not in values:
            values.insert(0, eq.value)
    refs = list(candidates)
    try:
        compiled = jsonata.Jsonata(query)
        compiled.assign("repeatingSectionIndex", 0)
        for combo in itertools.islice(
            itertools.product(*(candidates[r] for r in refs)), MAX_COMBINATIONS
        ):
            answers = dict(zip(refs, combo, strict=True))
            result = compiled.evaluate(_document(answers, locate))
            if bool(result) != _evaluate(cond, answers):
                return False
    except Exception:
        return False
    return True


def build_states(
    pages: list[PageNode],
) -> tuple[dict[str, list[dict[str, str]]], list[ConversionWarning]]:
    locations: dict[str, FieldLocation] = {}
    for page in pages:
        for section in page.sections:
            repeating = section.type is FieldType.REPEATING_SECTION
            for node in section.fields:
                locations[node.key] = FieldLocation(
                    page.title, section.tech_name, node.tech_name, repeating, section.key
                )

    def locate(ref: str) -> FieldLocation:
        try:
            return locations[ref]
        except KeyError:
            raise ValueError(f"Nieznane pole {ref!r} w warunku") from None

    states: dict[str, list[dict[str, str]]] = {}
    issues: list[ConversionWarning] = []

    def add(key: str, kind: StateType, cond: Condition | None, context: str | None) -> None:
        if cond is None:
            return
        try:
            query = condition_to_jsonata(cond, locate, context_section_key=context)
            error = query_compiles(query)
            if error is None and not check_condition_query(query, cond, locate):
                error = "test semantyczny zapytania nie powiódł się"
        except ValueError as exc:
            error = str(exc)
        if error is not None:
            issues.append(
                ConversionWarning(
                    code=IssueCode.W06_STATE_REMOVED,
                    message=f"Usunięto stan {kind}: {error}",
                    path=key,
                )
            )
            return
        states.setdefault(key, []).append({"type": str(kind), "query": query})

    for page in pages:
        for section in page.sections:
            add(section.key, StateType.SHOW, section.show_when, None)
            for node in section.fields:
                add(node.key, StateType.SHOW, node.show_when, section.key)
                add(node.key, StateType.READ_ONLY, node.read_only_when, section.key)
    return states, issues
