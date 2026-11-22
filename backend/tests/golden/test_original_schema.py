"""Golden: formularze z buildera i wzorce względem ORYGINALNEGO schematu z `wymagania/`.

Weryfikator używa poprawionej kopii schematu, więc ten test pilnuje zgodności z oryginałem.
"""

import json
from functools import cache
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.models.draft import FormDraft
from app.pipeline.build import BuildOptions, build_form
from tests.golden.test_reference_forms import DRAFTS, REFERENCES, SAMPLES

ORIGINAL_SCHEMA = REFERENCES / "importowanyPlikJsonSchemat.json"
STYLES = ("sample", "info_section")


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(ORIGINAL_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _errors(form: dict[str, Any]) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}"
        for e in _validator().iter_errors(form)
    ]


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("sample", sorted(SAMPLES))
def test_built_form_matches_original_schema(sample: str, style: str) -> None:
    _, draft_name, base = SAMPLES[sample]
    draft = FormDraft.model_validate_json((DRAFTS / draft_name).read_text(encoding="utf-8"))
    options = BuildOptions(
        identity_source=base.identity_source,
        signed=base.signed,
        finish_page_style=style,  # type: ignore[arg-type]
    )
    form = build_form(draft, options).form.to_import_json()
    assert _errors(form) == []


@pytest.mark.parametrize("sample", sorted(SAMPLES))
def test_reference_form_matches_original_schema(sample: str) -> None:
    data = json.loads((REFERENCES / SAMPLES[sample][0]).read_text(encoding="utf-8"))
    assert _errors(data) == []


_OUTSIDE_DOCUMENT = {
    "repetingSectionGrid",
    "searchEnabled",
    "multiLevelTree",
    "selectAllEnabled",
    "minItemRows",
}


def _all_keys(node: Any) -> set[str]:
    if isinstance(node, list):
        return set().union(*map(_all_keys, node)) if node else set()
    if isinstance(node, dict):
        return set(node).union(*map(_all_keys, node.values()))
    return set()


@pytest.mark.parametrize("sample", sorted(SAMPLES))
def test_built_form_uses_only_document_keys(sample: str) -> None:
    _, draft_name, base = SAMPLES[sample]
    draft = FormDraft.model_validate_json((DRAFTS / draft_name).read_text(encoding="utf-8"))
    options = BuildOptions(identity_source=base.identity_source, signed=base.signed)
    form = build_form(draft, options).form.to_import_json()
    assert not _OUTSIDE_DOCUMENT & _all_keys(form)
    assert "repetingSectionGrid" not in json.dumps(form)  # także w zapytaniach JSONata
