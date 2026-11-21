import json
from pathlib import Path

from jsonschema import Draft202012Validator

from app.models.form import ALLOWED_VALIDATORS, EMPTY_HTML, FieldType, Validator
from app.pipeline.build.catalogs import (
    load_dictionary_catalog,
    load_form_schema,
    load_initial_data_catalog,
)
from app.pipeline.build.html import external_link, html_document, paragraphs
from app.pipeline.build.ir import Semantic

WYMAGANIA = Path(__file__).parents[4] / "wymagania"


def test_allowed_validators() -> None:
    assert ALLOWED_VALIDATORS[FieldType.NUMBER] == {Validator.REQUIRED}
    assert ALLOWED_VALIDATORS[FieldType.TEXT_BLOCK] == frozenset()
    assert len(ALLOWED_VALIDATORS[FieldType.TEXT_FIELD]) == 9


def test_html_helpers() -> None:
    assert paragraphs("a<b", "") == "<p>a&lt;b</p>"
    assert 'rel="noopener noreferrer"' in external_link("https://x.pl", "x")
    assert html_document("") == EMPTY_HTML


def test_initial_data_catalog() -> None:
    catalog = load_initial_data_catalog()
    assert catalog["PESEL.birthDate"].field_type is FieldType.DATEPICKER
    counts = {
        prefix: sum(1 for ref in catalog if ref.startswith(prefix))
        for prefix in ("PESEL.", "PESEL_ADDRESS.", "MLPZ.")
    }
    assert counts == {"PESEL.": 16, "PESEL_ADDRESS.": 18, "MLPZ.": 17}
    assert catalog["MLPZ.email"].editable is True
    assert catalog["MLPZ.name"].editable is False


def test_dictionary_catalog() -> None:
    catalog = load_dictionary_catalog()
    assert catalog["TERYT_4G_DOWODOWY"].multi_level_tree is True
    assert Semantic.COUNTRY in catalog["Kraje"].semantics


def test_schema_accepts_reference_samples() -> None:
    schema = load_form_schema()
    validator = Draft202012Validator(schema)
    samples = sorted(WYMAGANIA.glob("konfiguracja_form_*.json"))
    assert len(samples) == 2
    for sample in samples:
        errors = list(validator.iter_errors(json.loads(sample.read_text(encoding="utf-8"))))
        assert errors == []


def test_schema_rejects_numeric_default_in_nested_grid() -> None:
    nested = {"x": 0, "y": 0, "rows": 1, "cols": 3, "field": {"defaultValue": 5}}
    form = {
        "tabs": [
            {
                "questions": [
                    {"field": {"repeatingSectionGrid": [nested]}},
                ]
            }
        ]
    }
    assert list(Draft202012Validator(load_form_schema()).iter_errors(form))


def test_external_link_keeps_accessible_name() -> None:
    link = external_link("https://x.pl", "Tekst <linku>")
    assert 'target="_blank"' in link and 'rel="noopener noreferrer"' in link
    assert 'aria-label="Tekst &lt;linku&gt; – link otwiera się w nowej karcie"' in link  # noqa: RUF001
    assert 'title="Tekst &lt;linku&gt;"' in link


def test_accessible_links_rewrites_template_labels() -> None:
    from app.pipeline.build.html import accessible_links

    old = (
        '<p><a href="https://x.pl" rel="noopener noreferrer" target="_blank" '
        'aria-label="Link otwiera się w nowej karcie" title="x">'
        '<b>Urząd</b> Miasta</a> i <a href="#kotwica">wewn.</a> '
        '<a href="https://y.pl" target="_blank">bez rel</a></p>'
    )
    fixed = accessible_links(old)
    assert 'aria-label="Link otwiera się w nowej karcie"' not in fixed
    assert 'aria-label="Urząd Miasta – link otwiera się w nowej karcie"' in fixed  # noqa: RUF001
    assert '<a href="#kotwica">wewn.</a>' in fixed
    assert 'rel="noopener noreferrer"' in fixed.split("bez rel")[0].rsplit("<a", 1)[1]
