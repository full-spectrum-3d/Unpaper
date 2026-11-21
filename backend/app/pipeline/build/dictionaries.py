"""Powiązania pól ze słownikami po semantyce z etykiety (spec §8.4)."""

from app.models.form import ALLOWED_VALIDATORS, FieldType
from app.pipeline.build.catalogs import DictionaryEntry, load_dictionary_catalog
from app.pipeline.build.ir import FieldNode, PageNode, iter_fields


def _find_entry(node: FieldNode, catalog: dict[str, DictionaryEntry]) -> DictionaryEntry | None:
    if node.semantic is None:
        return None
    return next((entry for entry in catalog.values() if node.semantic in entry.semantics), None)


def _bind(node: FieldNode, entry: DictionaryEntry) -> None:
    node.dictionary_name = entry.name
    node.type = entry.field_types[0]
    allowed = ALLOWED_VALIDATORS[node.type]
    node.validation = [v for v in node.validation if v in allowed]
    node.options = []
    node.search_enabled = True
    node.multi_level_tree = True if entry.multi_level_tree else None


def apply_dictionaries(pages: list[PageNode]) -> None:
    catalog = load_dictionary_catalog()
    for _, _, node in iter_fields(pages):
        # tylko wolny tekst: wybór z własnymi opcjami zachowuje je (warunki odwołują się do opcji)
        if node.type is not FieldType.TEXT_FIELD or node.dictionary_name is not None:
            continue
        entry = _find_entry(node, catalog)
        if entry is not None:
            _bind(node, entry)
