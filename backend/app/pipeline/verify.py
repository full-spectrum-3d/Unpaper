"""[6] Weryfikacja: JSON Schema + reguły R01-R15 + autonaprawa (spec §5.6, §7.3)."""

import copy
import itertools
import re
import uuid
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator

from app.models.form import (
    ALLOWED_VALIDATORS,
    BASE_FIELD_KEYS,
    CHOICE_TYPES,
    EMPTY_HTML,
    EXTERNAL_SYSTEM,
    GRID_KEY,
    INPUT_TYPES,
    SECTION_TYPES,
    FieldType,
    FormJson,
    StateType,
    TabType,
    to_document_format,
)
from app.models.warning import ConversionWarning
from app.pipeline.build.catalogs import load_form_schema, load_initial_data_catalog
from app.pipeline.build.fields import slugify
from app.pipeline.build.states import query_compiles, query_references
from app.pipeline.issues import Issue, IssueCode

MAX_TITLE = 255
MAX_TECH_NAME = 60
MAX_SCHEMA_ISSUES = 20
DEFAULT_SECTION_TITLE = "Dane"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
TITLE_PREFIXES = ("wniosek", "zgłoszenie", "deklaracja", "oświadczenie")
BASE_DEFAULTS: dict[str, Any] = {
    "id": "",
    "type": None,
    "techName": "",
    "title": "",
    "description": "",
    "options": [],
    "validation": [],
    "readOnly": False,
    GRID_KEY: [],
    "states": [],
    "questionOrder": 0,
    "tooltipMessage": "",
}

type Rule = Callable[[dict[str, Any]], list[Issue]]


@dataclass
class VerifyResult:
    form: FormJson
    errors: list[Issue]
    warnings: list[ConversionWarning]
    fixes: list[Issue]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass
class _Ctx:
    id_factory: Callable[[], str]
    fixes: list[Issue] = field(default_factory=list)
    warnings: list[ConversionWarning] = field(default_factory=list)

    def fix(self, code: IssueCode, message: str, path: str | None) -> None:
        self.fixes.append(Issue(code, message, path))


@dataclass(frozen=True)
class _Node:
    path: str
    question: dict[str, Any]
    field: dict[str, Any]
    tab: dict[str, Any]
    parent: dict[str, Any] | None


# --- Przechodzenie po strukturze (defensywne: złe kształty są pomijane) ---


def _items(value: Any, base: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, dict):
                yield f"{base}[{i}]", item


def _tabs(form: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return list(_items(form.get("tabs"), "tabs"))


def _walk(
    questions: Any, base: str, tab: dict[str, Any], parent: dict[str, Any] | None
) -> Iterator[_Node]:
    for path, question in _items(questions, base):
        fld = question.get("field")
        if isinstance(fld, dict):
            yield _Node(path, question, fld, tab, parent)
            grid = f"{path}.field.{GRID_KEY}"
            yield from _walk(fld.get(GRID_KEY), grid, tab, fld)


def _nodes(form: dict[str, Any]) -> list[_Node]:
    return [
        node
        for path, tab in _tabs(form)
        for node in _walk(tab.get("questions"), f"{path}.questions", tab, None)
    ]


def _ftype(fld: dict[str, Any]) -> FieldType | None:
    value = fld.get("type")
    return FieldType(value) if isinstance(value, str) and value in FieldType else None


def _is_section(fld: dict[str, Any]) -> bool:
    return _ftype(fld) in SECTION_TYPES


def _id_holders(form: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    flow = form.get("flow")
    links = _items(flow.get("links"), "flow.links") if isinstance(flow, dict) else ()
    return [*_tabs(form), *((n.path, n.field) for n in _nodes(form)), *links]


def _tab_titles(form: dict[str, Any]) -> set[str]:
    return {t["title"] for _, t in _tabs(form) if isinstance(t.get("title"), str)}


def _tech_names(form: dict[str, Any]) -> set[str]:
    return {n.field["techName"] for n in _nodes(form) if isinstance(n.field.get("techName"), str)}


# --- Autonaprawy ---


def _fix_document_format(form: dict[str, Any], ctx: _Ctx) -> None:
    """Starszy format (wzorce COI) -> klucze z OpisImportowanegoPlikuJSON.md."""
    converted, changes = to_document_format(form)
    if not changes:
        return
    form.clear()
    form.update(converted)
    message = f"Dostosowano klucze do dokumentu importu ({len(changes)} zmian)"
    ctx.fix(IssueCode.SCHEMA, message, None)


def _fix_base_keys(form: dict[str, Any], ctx: _Ctx) -> None:
    for node in _nodes(form):
        fld = node.field
        defaults = {**BASE_DEFAULTS, "description": EMPTY_HTML if _is_section(fld) else ""}
        missing = [k for k in BASE_FIELD_KEYS if k not in fld and k != "type"]
        for key in missing:
            fld[key] = copy.deepcopy(defaults[key])
        if "validation" in fld and not isinstance(fld["validation"], list):
            fld["validation"] = []
            missing.append("validation")
        if missing:
            ctx.fix(IssueCode.R06_REQUIREDNESS, f"Uzupełniono: {', '.join(missing)}", node.path)


def _fix_field_outside_section(form: dict[str, Any], ctx: _Ctx) -> None:
    for tab_path, tab in _tabs(form):
        questions = tab.get("questions")
        for path, question in _items(questions, f"{tab_path}.questions"):
            fld = question.get("field")
            if not isinstance(fld, dict) or _is_section(fld):
                continue
            inner = {**question, "x": 0, "y": 0, "rows": 1, "cols": 3}
            tech = fld.get("techName")
            title = fld.get("title")
            if isinstance(tech, str) and tech:
                wrapper_tech = f"{tech}_sekcja"
            elif isinstance(title, str) and title.strip():
                wrapper_tech = slugify(title)
            else:
                wrapper_tech = "sekcja"
            wrapper = {
                **copy.deepcopy({k: BASE_DEFAULTS[k] for k in BASE_FIELD_KEYS}),
                "id": ctx.id_factory(),
                "type": FieldType.SECTION.value,
                "techName": wrapper_tech[:MAX_TECH_NAME],
                "title": fld.get("title", ""),
                "description": EMPTY_HTML,
                GRID_KEY: [inner],
                "questionOrder": fld.get("questionOrder", 0),
            }
            question["field"] = wrapper
            for key in ("x", "y", "rows", "cols"):
                question.setdefault(key, inner[key])
            ctx.fix(IssueCode.R03_FIELD_OUTSIDE_SECTION, "Opakowano pole w sekcję", path)


def _flatten(grid: list[Any], base: str, ctx: _Ctx) -> list[Any]:
    result: list[Any] = []
    for i, item in enumerate(grid):
        inner = item.get("field") if isinstance(item, dict) else None
        if isinstance(inner, dict) and _is_section(inner):
            nested = inner.get(GRID_KEY)
            result.extend(_flatten(nested if isinstance(nested, list) else [], base, ctx))
            ctx.fix(
                IssueCode.R04_NESTED_SECTION,
                "Przeniesiono pola z zagnieżdżonej sekcji",
                f"{base}[{i}]",
            )
        else:
            result.append(item)
    return result


def _fix_nested_sections(form: dict[str, Any], ctx: _Ctx) -> None:
    for node in _nodes(form):
        grid = node.field.get(GRID_KEY)
        if node.parent is None and _is_section(node.field) and isinstance(grid, list):
            base = f"{node.path}.field.{GRID_KEY}"
            node.field[GRID_KEY] = _flatten(grid, base, ctx)


def _fix_empty_pages(form: dict[str, Any], ctx: _Ctx) -> None:
    tabs = form.get("tabs")
    if not isinstance(tabs, list):
        return
    kept = []
    for i, tab in enumerate(tabs):
        if isinstance(tab, dict) and not tab.get("questions"):
            ctx.fix(IssueCode.R03_EMPTY_PAGE, "Usunięto pustą stronę", f"tabs[{i}]")
        else:
            kept.append(tab)
    form["tabs"] = kept


def _fix_duplicate_ids(form: dict[str, Any], ctx: _Ctx) -> None:
    seen: set[str] = set()
    for path, holder in _id_holders(form):
        value = holder.get("id")
        if not isinstance(value, str) or not value or value in seen:
            holder["id"] = ctx.id_factory()
            ctx.fix(IssueCode.R12_DUPLICATE_ID, "Nadano nowe id", path)
        seen.add(holder["id"])


def _fix_duplicate_tech_names(form: dict[str, Any], ctx: _Ctx) -> None:
    taken = _tech_names(form)
    seen: set[str] = set()
    for node in _nodes(form):
        name = node.field.get("techName")
        if not isinstance(name, str) or not name:
            continue
        if name in seen:
            n = 2
            while True:
                suffix = f"_{n}"
                candidate = f"{name[: MAX_TECH_NAME - len(suffix)]}{suffix}"
                if candidate not in taken:
                    break
                n += 1
            node.field["techName"] = candidate
            taken.add(candidate)
            name = candidate
            ctx.fix(
                IssueCode.R12_DUPLICATE_TECH_NAME, f"Zmieniono techName na {candidate}", node.path
            )
        seen.add(name)


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _fix_section_titles(form: dict[str, Any], ctx: _Ctx) -> None:
    # Tytuły sekcji nie są celem odwołań stanów (te wskazują strony i techName).
    for node in _nodes(form):
        if not _is_section(node.field) or not _blank(node.field.get("title")):
            continue
        titles = (
            q["field"].get("title")
            for _, q in _items(node.field.get(GRID_KEY), "")
            if isinstance(q.get("field"), dict)
        )
        title = next((t for t in titles if not _blank(t)), DEFAULT_SECTION_TITLE)
        node.field["title"] = title
        ctx.fix(IssueCode.R16_SECTION_TITLE, f"Nadano tytuł sekcji: {title}", node.path)


def _fix_id_format(form: dict[str, Any], ctx: _Ctx) -> None:
    renamed: dict[str, str] = {}
    for path, holder in _id_holders(form):
        value = holder.get("id")
        if isinstance(value, str) and not UUID_RE.match(value):
            renamed[value] = holder["id"] = ctx.id_factory()
            ctx.fix(IssueCode.W30_ID_FORMAT, f"Zamieniono id {value!r} na UUID", path)
    # Jedyne odwołania do id w formularzu to końce połączeń przepływu.
    flow = form.get("flow")
    for _, link in _items(flow.get("links"), "flow.links") if isinstance(flow, dict) else ():
        for end in ("source", "target"):
            if isinstance(link.get(end), str) and link[end] in renamed:
                link[end] = renamed[link[end]]


def _state_problem(
    state: Any, fld: dict[str, Any], titles: set[str], names: set[str]
) -> str | None:
    if not isinstance(state, dict):
        return "stan nie jest obiektem"
    kind = state.get("type")
    allowed = {StateType.SHOW} if _is_section(fld) else set(StateType)
    if not isinstance(kind, str) or kind not in allowed:
        return f"niedozwolony typ stanu: {kind!r}"
    query = state.get("query")
    if not isinstance(query, str) or not query.strip():
        return "pusty warunek stanu"
    if (error := query_compiles(query)) is not None:
        return f"warunek nie kompiluje się w JSONata: {error}"
    ref_titles, ref_names = query_references(query)
    if missing := sorted((ref_titles - titles) | (ref_names - names)):
        return f"odwołanie do nieistniejących elementów: {', '.join(missing)}"
    return None


def _fix_states(form: dict[str, Any], ctx: _Ctx) -> None:
    titles, names = _tab_titles(form), _tech_names(form)
    for node in _nodes(form):
        states = node.field.get("states")
        if not isinstance(states, list):
            continue
        kept = []
        for state in states:
            problem = _state_problem(state, node.field, titles, names)
            if problem is None:
                kept.append(state)
                continue
            ctx.fix(IssueCode.R11_STATE, f"Usunięto stan: {problem}", node.path)
            ctx.warnings.append(
                ConversionWarning(
                    code=IssueCode.W06_STATE_REMOVED,
                    message=f"Usunięto stan: {problem}",
                    path=node.path,
                )
            )
        node.field["states"] = kept


def _fix_validators(form: dict[str, Any], ctx: _Ctx) -> None:
    for node in _nodes(form):
        ftype, validation = _ftype(node.field), node.field.get("validation")
        if ftype is None or not isinstance(validation, list):
            continue
        allowed = ALLOWED_VALIDATORS[ftype]
        kept = [v for v in validation if isinstance(v, str) and v in allowed]
        if kept != validation:
            node.field["validation"] = kept
            ctx.fix(IssueCode.R15_VALIDATOR, "Usunięto niedozwolone walidatory", node.path)


def _fix_dictionaries(form: dict[str, Any], ctx: _Ctx) -> None:
    for node in _nodes(form):
        fld = node.field
        if "dictionaryName" not in fld:
            continue
        if not fld["dictionaryName"]:
            del fld["dictionaryName"]
            ctx.fix(IssueCode.R08_DICTIONARY, "Usunięto puste dictionaryName", node.path)
        elif _ftype(fld) not in CHOICE_TYPES:
            del fld["dictionaryName"]
            ctx.fix(IssueCode.R08_DICTIONARY, "Usunięto dictionaryName", node.path)
        elif fld.get("options"):
            fld["options"] = []
            ctx.fix(IssueCode.R08_DICTIONARY, "Wyczyszczono options przy słowniku", node.path)


def _flow_problems(form: dict[str, Any]) -> list[str]:
    tabs = [t for _, t in _tabs(form)]
    ids = [t.get("id") for t in tabs]
    flow = form.get("flow")
    links = flow.get("links") if isinstance(flow, dict) else None
    if not isinstance(links, list):
        return ["Brak flow.links"]
    problems: list[str] = []
    graph: dict[str, set[str]] = {}
    for n, link in enumerate(links):
        ends = [link.get("source"), link.get("target")] if isinstance(link, dict) else []
        if len(ends) != 2 or any(e not in ids for e in ends):
            problems.append(f"flow.links[{n}] wskazuje nieistniejącą stronę")
        elif isinstance(ends[0], str) and isinstance(ends[1], str):
            graph.setdefault(ends[0], set()).add(ends[1])
    if tabs and isinstance(ids[0], str):
        seen = _reachable(graph, {ids[0]})
        problems += [
            f"Strona '{t.get('title')}' jest nieosiągalna z pierwszej strony"
            for t in tabs
            if t.get("id") not in seen
        ]
        problems += _flow_exit_problems(tabs, graph, seen)
    return problems


def _reachable(graph: dict[str, set[str]], start: set[str]) -> set[str]:
    seen, queue = set(start), deque(start)
    while queue:
        for nxt in graph.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _flow_exit_problems(
    tabs: list[dict[str, Any]], graph: dict[str, set[str]], reachable: set[str]
) -> list[str]:
    """Rozgałęzienia są dozwolone, ale z każdej strony musi dać się dojść do FINISH, bez cykli."""
    finish = {
        t["id"] for t in tabs if t.get("type") == TabType.FINISH and isinstance(t.get("id"), str)
    }
    if not finish:
        return []  # brak FINISH zgłasza reguła struktury stron
    reverse: dict[str, set[str]] = {}
    for src, targets in graph.items():
        for tgt in targets:
            reverse.setdefault(tgt, set()).add(src)
    can_finish = _reachable(reverse, finish)
    problems = [
        f"Ze strony '{t.get('title')}' nie da się dojść do strony końcowej"
        for t in tabs
        if t.get("id") in reachable and t.get("id") not in can_finish
    ]
    if _has_cycle(graph):
        problems.append("Przepływ stron zawiera cykl")
    return problems


def _has_cycle(graph: dict[str, set[str]]) -> bool:
    indegree = dict.fromkeys(graph, 0)
    for targets in graph.values():
        for tgt in targets:
            indegree[tgt] = indegree.get(tgt, 0) + 1
    queue = deque(n for n, d in indegree.items() if d == 0)
    done = 0
    while queue:
        done += 1
        for nxt in graph.get(queue.popleft(), ()):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return done < len(indegree)


def _fix_flow(form: dict[str, Any], ctx: _Ctx) -> None:
    if not _flow_problems(form):
        return
    ids = [t.get("id") for _, t in _tabs(form)]
    form["flow"] = {
        "links": [
            {"id": ctx.id_factory(), "source": a, "target": b} for a, b in itertools.pairwise(ids)
        ]
    }
    ctx.fix(IssueCode.R07_FLOW, "Przebudowano flow liniowo", "flow")


FIXES: tuple[Callable[[dict[str, Any], _Ctx], None], ...] = (
    _fix_document_format,
    _fix_base_keys,
    _fix_field_outside_section,
    _fix_nested_sections,
    _fix_empty_pages,
    _fix_duplicate_ids,
    _fix_id_format,
    _fix_section_titles,
    _fix_duplicate_tech_names,
    _fix_states,
    _fix_validators,
    _fix_dictionaries,
    _fix_flow,
)


# --- Reguły ---


def _format_path(parts: Any) -> str | None:
    text = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)
    return text.lstrip(".") or None


def _is_null_option_tech_name(error: Any) -> bool:
    path = list(error.absolute_path)
    return error.instance is None and path[-1:] == ["techName"] and "options" in path


@cache
def _schema_validator() -> Draft202012Validator:
    """Walidator budowany raz: schemat jest stały, a kompilacja referencji kosztowna."""
    return Draft202012Validator(load_form_schema())


def _rule_schema(form: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for error in _schema_validator().iter_errors(form):
        if _is_null_option_tech_name(error):
            continue
        issues.append(
            Issue(IssueCode.SCHEMA, error.message[:300], _format_path(error.absolute_path))
        )
        if len(issues) == MAX_SCHEMA_ISSUES:
            break
    for node in _nodes(form):
        if _ftype(node.field) is None:
            msg = f"Nieznany typ pola: {node.field.get('type')!r}"
            issues.append(Issue(IssueCode.SCHEMA, msg, node.path))
    for change in to_document_format(form)[1][:MAX_SCHEMA_ISSUES]:
        issues.append(Issue(IssueCode.SCHEMA, f"Klucz spoza dokumentu importu: {change}", None))
    return issues


def _rule_title(form: dict[str, Any]) -> list[Issue]:
    title = form.get("title")
    if not isinstance(title, str) or not title.strip():
        return [Issue(IssueCode.R01_TITLE, "Tytuł formularza jest pusty", "title")]
    if len(title) > MAX_TITLE:
        return [Issue(IssueCode.R01_TITLE, f"Tytuł dłuższy niż {MAX_TITLE} znaków", "title")]
    if not title.casefold().startswith(TITLE_PREFIXES):
        return [
            Issue(
                IssueCode.W05_TITLE_PREFIX,
                "Tytuł nie zaczyna się od Wniosek, Zgłoszenie, Deklaracja lub Oświadczenie",
                "title",
            )
        ]
    return []


def _rule_tabs(form: dict[str, Any]) -> list[Issue]:
    tabs = _tabs(form)
    issues = (
        [Issue(IssueCode.R02_TABS, "Formularz wymaga co najmniej 2 stron", "tabs")]
        if len(tabs) < 2
        else []
    )
    for i, (path, tab) in enumerate(tabs):
        expected = TabType.FINISH if i == len(tabs) - 1 else TabType.MAIN
        if tab.get("type") != expected:
            msg = f"Strona {i + 1} powinna mieć typ {expected.value}, a ma {tab.get('type')!r}"
            issues.append(Issue(IssueCode.R02_TABS, msg, path))
    return issues


def _rule_structure(form: dict[str, Any]) -> list[Issue]:
    issues = [
        Issue(IssueCode.R03_EMPTY_PAGE, "Strona nie zawiera pól", path)
        for path, tab in _tabs(form)
        if not tab.get("questions")
    ]
    for node in _nodes(form):
        if node.parent is None and not _is_section(node.field):
            msg = "Pole poza sekcją"
            issues.append(Issue(IssueCode.R03_FIELD_OUTSIDE_SECTION, msg, node.path))
        elif node.parent is not None and _is_section(node.field):
            issues.append(Issue(IssueCode.R04_NESTED_SECTION, "Sekcja w sekcji", node.path))
    return issues


def _rule_finish(form: dict[str, Any]) -> list[Issue]:
    return [
        Issue(IssueCode.R05_FINISH_INPUT, "Pole do wprowadzania danych na stronie końcowej", n.path)
        for n in _nodes(form)
        if n.tab.get("type") == TabType.FINISH and _ftype(n.field) in INPUT_TYPES
    ]


def _rule_finish_content(form: dict[str, Any]) -> list[Issue]:
    # Reguła 7: na stronie końcowej wyłącznie INFO_SECTION (pola wejściowe to błąd R05).
    return [
        Issue(
            IssueCode.W29_FINISH_NOT_INFO,
            "Strona końcowa powinna zawierać wyłącznie sekcje informacyjne (INFO_SECTION)",
            n.path,
        )
        for n in _nodes(form)
        if n.tab.get("type") == TabType.FINISH
        and n.parent is not None
        and _ftype(n.field) not in INPUT_TYPES | {FieldType.INFO_SECTION, None}
    ]


def _rule_section_titles(form: dict[str, Any]) -> list[Issue]:
    return [
        Issue(IssueCode.R16_SECTION_TITLE, "Sekcja bez tytułu", n.path)
        for n in _nodes(form)
        if _is_section(n.field) and _blank(n.field.get("title"))
    ]


def _rule_id_format(form: dict[str, Any]) -> list[Issue]:
    return [
        Issue(IssueCode.W30_ID_FORMAT, f"id nie jest UUID: {holder['id']!r}", path)
        for path, holder in _id_holders(form)
        if isinstance(holder.get("id"), str) and not UUID_RE.match(holder["id"])
    ]


def _rule_requiredness(form: dict[str, Any]) -> list[Issue]:
    return [
        Issue(IssueCode.R06_REQUIREDNESS, "validation nie jest listą", n.path)
        for n in _nodes(form)
        if not isinstance(n.field.get("validation"), list)
    ]


def _rule_flow(form: dict[str, Any]) -> list[Issue]:
    return [Issue(IssueCode.R07_FLOW, p, "flow") for p in _flow_problems(form)]


def _rule_choices(form: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for n in _nodes(form):
        ftype, fld = _ftype(n.field), n.field
        options = fld.get("options")
        count = len(options) if isinstance(options, list) else 0
        if fld.get("dictionaryName"):
            if ftype not in CHOICE_TYPES:
                issues.append(
                    Issue(IssueCode.R08_DICTIONARY, "dictionaryName w polu bez wyboru", n.path)
                )
            elif count:
                issues.append(
                    Issue(IssueCode.R08_DICTIONARY, "Pole ze słownikiem ma options", n.path)
                )
        elif ftype in CHOICE_TYPES:
            needed = 1 if ftype == FieldType.CHECKBOX else 2
            if count < needed:
                msg = f"Pole wyboru wymaga co najmniej {needed} opcji"
                issues.append(Issue(IssueCode.R09_OPTIONS, msg, n.path))
    return issues


def _rule_initial_data(form: dict[str, Any]) -> list[Issue]:
    catalog, issues = load_initial_data_catalog(), []
    for n in _nodes(form):
        if n.field.get("defaultValueType") != EXTERNAL_SYSTEM:
            continue
        ref = n.field.get("defaultValue")
        attr = catalog.get(ref) if isinstance(ref, str) else None
        if attr is None:
            issues.append(
                Issue(IssueCode.R10_INITIAL_DATA, f"Nieznane dane inicjalne: {ref!r}", n.path)
            )
        elif n.field.get("readOnly") is not True and not attr.editable:
            issues.append(
                Issue(IssueCode.R10_INITIAL_DATA, f"{attr.ref} wymaga readOnly: true", n.path)
            )
    return issues


def _rule_states(form: dict[str, Any]) -> list[Issue]:
    titles, names, issues = _tab_titles(form), _tech_names(form), []
    for n in _nodes(form):
        states = n.field.get("states")
        if not isinstance(states, list):
            issues.append(Issue(IssueCode.R11_STATE, "states nie jest listą", n.path))
            continue
        for state in states:
            if problem := _state_problem(state, n.field, titles, names):
                issues.append(Issue(IssueCode.R11_STATE, problem, n.path))
    return issues


def _rule_uniqueness(form: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    seen_ids: set[str] = set()
    for path, holder in _id_holders(form):
        value = holder.get("id")
        if not isinstance(value, str) or not value or value in seen_ids:
            issues.append(
                Issue(IssueCode.R12_DUPLICATE_ID, f"Brakujące lub zduplikowane id: {value!r}", path)
            )
        elif isinstance(value, str):
            seen_ids.add(value)
    seen_names: set[str] = set()
    for n in _nodes(form):
        name = n.field.get("techName")
        if not isinstance(name, str) or not name or name in seen_names:
            msg = f"Brakujący lub zduplikowany techName: {name!r}"
            issues.append(Issue(IssueCode.R12_DUPLICATE_TECH_NAME, msg, n.path))
        elif isinstance(name, str):
            seen_names.add(name)
    return issues


def _consent_ok(config: Any) -> bool:
    consents = config.get("consents") if isinstance(config, dict) else None
    return (
        isinstance(consents, list)
        and bool(consents)
        and all(
            isinstance(c, dict)
            and isinstance(c.get("description"), str)
            and bool(c["description"].strip())
            for c in consents
        )
        and isinstance(config.get("required"), bool)
    )


def _rule_content(form: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for n in _nodes(form):
        ftype, fld = _ftype(n.field), n.field
        if ftype == FieldType.CONSENT_SECTION and not _consent_ok(fld.get("consentSectionConfig")):
            msg = "Sekcja zgód wymaga zgód z opisem i required"
            issues.append(Issue(IssueCode.R13_CONSENT, msg, n.path))
        description = fld.get("description")
        if ftype == FieldType.INFO_SECTION and (
            not isinstance(description, str) or description.strip() in ("", EMPTY_HTML)
        ):
            issues.append(
                Issue(IssueCode.R14_INFO_SECTION, "Sekcja informacyjna bez opisu", n.path)
            )
    return issues


def _rule_validators(form: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for n in _nodes(form):
        ftype, validation = _ftype(n.field), n.field.get("validation")
        if ftype is None or not isinstance(validation, list):
            continue
        allowed = ALLOWED_VALIDATORS[ftype]
        for item in validation:
            if not isinstance(item, str) or item not in allowed:
                msg = f"Walidator {item!r} niedozwolony dla {ftype.value}"
                issues.append(Issue(IssueCode.R15_VALIDATOR, msg, n.path))
    return issues


RULES: tuple[Rule, ...] = (
    _rule_schema,
    _rule_title,
    _rule_tabs,
    _rule_structure,
    _rule_finish,
    _rule_finish_content,
    _rule_section_titles,
    _rule_id_format,
    _rule_requiredness,
    _rule_flow,
    _rule_choices,
    _rule_initial_data,
    _rule_states,
    _rule_uniqueness,
    _rule_content,
    _rule_validators,
)


def verify_form(
    form: Mapping[str, Any],
    *,
    autofix: bool = True,
    id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> VerifyResult:
    """Naprawia (opcjonalnie) i weryfikuje formularz. Nigdy nie rzuca wyjątku."""
    if not isinstance(form, Mapping):
        return VerifyResult({}, [Issue(IssueCode.SCHEMA, "Formularz nie jest obiektem")], [], [])
    try:
        data: dict[str, Any] = copy.deepcopy(dict(form))
    except Exception as exc:
        return VerifyResult(
            {}, [Issue(IssueCode.SCHEMA, f"Nie można skopiować formularza: {exc}")], [], []
        )
    ctx = _Ctx(id_factory)
    problems: list[Issue] = []
    for step in FIXES if autofix else ():
        try:
            step(data, ctx)
        except Exception as exc:
            problems.append(Issue(IssueCode.SCHEMA, f"Błąd autonaprawy {step.__name__}: {exc}"))
    for rule in RULES:
        try:
            problems.extend(rule(data))
        except Exception as exc:
            problems.append(Issue(IssueCode.SCHEMA, f"Błąd reguły {rule.__name__}: {exc}"))
    errors = [i for i in problems if not i.code.startswith("W")]
    warnings = ctx.warnings + [
        ConversionWarning(code=i.code, message=i.message, path=i.path)
        for i in problems
        if i.code.startswith("W")
    ]
    return VerifyResult(data, errors, warnings, ctx.fixes)
