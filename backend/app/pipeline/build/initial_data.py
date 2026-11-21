"""Dane inicjalne PESEL / PESEL_ADDRESS / MLPZ (spec §8.5)."""

from app.models.form import ALLOWED_VALIDATORS, EXTERNAL_SYSTEM, FieldType
from app.models.warning import ConversionWarning
from app.pipeline.build.catalogs import load_initial_data_catalog
from app.pipeline.build.ir import PageNode, iter_fields
from app.pipeline.issues import IssueCode

IGNORED_TYPES = frozenset({FieldType.TEXT_BLOCK, FieldType.CONSENT_SECTION, FieldType.INFO_SECTION})


def apply_initial_data(pages: list[PageNode]) -> list[ConversionWarning]:
    catalog = load_initial_data_catalog()
    issues: list[ConversionWarning] = []
    for _, _, node in iter_fields(pages):
        if node.type in IGNORED_TYPES:
            continue
        ref = node.initial_data
        if ref is None:
            continue
        attr = catalog.get(ref)
        if attr is None or node.dictionary_name is not None:
            reason = "spoza katalogu" if attr is None else "pole ma słownik"
            node.initial_data = None
            issues.append(
                ConversionWarning(
                    code=IssueCode.W09_INITIAL_DATA_SKIPPED,
                    message=f"Pominięto dane inicjalne „{ref}” pola {node.tech_name} ({reason}).",
                    path=node.tech_name,
                )
            )
            continue
        if node.type != attr.field_type:
            node.type = attr.field_type
            node.options = []
            allowed = ALLOWED_VALIDATORS[node.type]
            node.validation = [v for v in node.validation if v in allowed]
        node.default_value = ref
        node.default_value_type = EXTERNAL_SYSTEM
        node.read_only = not attr.editable
    return issues
