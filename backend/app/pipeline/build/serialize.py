"""Serializacja IR do FormDefinition w formacie importu COI (spec §7.1, §8)."""

from collections.abc import Callable
from typing import Any

from app.models.form import (
    GRID_KEY,
    FieldType,
    FormJson,
    default_value_string,
)
from app.pipeline.build.fields import slugify
from app.pipeline.build.html import html_document
from app.pipeline.build.ir import FieldNode, PageNode, SectionNode
from app.pipeline.build.layout import Placement, compute_layout
from app.pipeline.build.pages import flow_links

type States = dict[str, list[dict[str, str]]]


def _field(
    node: FieldNode | SectionNode,
    placement: Placement,
    states: States,
    id_factory: Callable[[], str],
    layout: dict[str, Placement],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": id_factory(),
        "type": str(node.type),
        "techName": node.tech_name,
        "title": node.title,
    }
    grid: list[dict[str, Any]] = []
    if isinstance(node, SectionNode):
        result["description"] = html_document(node.description_html)
        result["options"] = []
        result["validation"] = []
        result["readOnly"] = False
        grid = [_question(child, states, id_factory, layout) for child in node.fields]
        tooltip = ""
    else:
        result["description"] = (
            html_document(node.description_html) if node.description_html else ""
        )
        result["options"] = [{"id": o, "name": o, "techName": slugify(o)} for o in node.options]
        result["validation"] = [str(v) for v in node.validation]
        result["readOnly"] = node.read_only
        tooltip = node.tooltip
    result[GRID_KEY] = grid
    result["states"] = list(states.get(node.key, []))
    result["questionOrder"] = placement.y
    result["tooltipMessage"] = tooltip
    if isinstance(node, FieldNode):
        optional: dict[str, Any] = {
            "defaultValue": default_value_string(node.default_value),
            "defaultValueType": node.default_value_type,
            "dictionaryName": node.dictionary_name,
            "consentSectionConfig": (
                {
                    "consents": [
                        {"description": html_document(c.description_html)} for c in node.consents
                    ],
                    # OpisImportowanegoPlikuJSON.md: wymagalność na poziomie sekcji zgód.
                    "required": any(c.required for c in node.consents),
                    "files": [],
                }
                if node.type is FieldType.CONSENT_SECTION
                else None
            ),
        }
        result.update({k: v for k, v in optional.items() if v is not None})
    return result


def _question(
    node: FieldNode | SectionNode,
    states: States,
    id_factory: Callable[[], str],
    layout: dict[str, Placement],
) -> dict[str, Any]:
    place = layout[node.key]
    return {
        "x": place.x,
        "y": place.y,
        "rows": place.rows,
        "cols": place.cols,
        "field": _field(node, place, states, id_factory, layout),
    }


def to_form_definition(
    title: str,
    pages: list[PageNode],
    states: States,
    id_factory: Callable[[], str],
) -> FormJson:
    layout = compute_layout(pages)
    tab_ids = [id_factory() for _ in pages]
    tabs = [
        {
            "id": tab_id,
            "title": page.title,
            "type": str(page.type),
            "questions": [
                _question(section, states, id_factory, layout) for section in page.sections
            ],
        }
        for tab_id, page in zip(tab_ids, pages, strict=True)
    ]
    return {"title": title, "tabs": tabs, "flow": {"links": flow_links(tab_ids, id_factory)}}
