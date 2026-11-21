from typing import Any

from app.models.draft import FormDraft
from app.pipeline.draft_merge import merge_drafts, split_prompt_text


def _pages(*sizes: int) -> str:
    return "\n".join(f"=== strona {i}\n" + "x" * size for i, size in enumerate(sizes, 1))


def _flat(chunks: list[str]) -> str:
    return "".join(c.replace("\n", "") for c in chunks)


def test_short_text_single_chunk() -> None:
    text = _pages(100, 100, 100)
    assert split_prompt_text(text, 10_000) == [text]


def test_split_on_page_boundaries() -> None:
    text = _pages(400, 400, 400)
    chunks = split_prompt_text(text, 900)
    assert len(chunks) == 2
    assert chunks[1].startswith("=== strona 3")
    assert "\n".join(chunks) == text


def test_oversized_page_split_on_lines() -> None:
    text = "=== strona 1\n" + "\n".join("y" * 50 for _ in range(40))
    chunks = split_prompt_text(text, 300)
    assert len(chunks) > 1 and all(len(c) <= 300 for c in chunks)
    assert "\n".join(chunks) == text


def test_overlong_line_hard_cut() -> None:
    text = "=== strona 1\n" + "z" * 1000
    chunks = split_prompt_text(text, 300)
    assert all(len(c) <= 300 for c in chunks)
    assert _flat(chunks) == text.replace("\n", "")


def _field(fid: str, label: str, **kw: Any) -> dict[str, Any]:
    return {"id": fid, "label": label, "kind": "short_text", "required": True, **kw}


def _draft(page: str, fields: list[dict[str, Any]], **kw: Any) -> FormDraft:
    return FormDraft.model_validate(
        {
            "title": kw.get("title", "Wniosek A"),
            "authority_kind": "ORGAN",
            "authority_name": "Wójt",
            "applicant_kinds": ["SELF"],
            "attachments": kw.get("attachments", []),
            "statements": [],
            "subject_pages": [
                {"title": page, "sections": [{"title": "S", "repeating": False, "fields": fields}]}
            ],
        }
    )


def _choice_pair(choice: str, dependent: str) -> list[dict[str, Any]]:
    return [
        _field("f1", choice, kind="single_choice", options=["Tak", "Nie"]),
        _field("f2", dependent, visible_when=[{"field_id": "f1", "op": "equals", "value": "Tak"}]),
    ]


def test_merge_renumbers_and_remaps_conditions() -> None:
    merged = merge_drafts(
        [
            _draft("Strona A", _choice_pair("Czy A?", "Opis A")),
            _draft("Strona B", _choice_pair("Czy B?", "Opis B")),
        ]
    )
    fields = [f for _, f in merged.iter_fields()]
    assert [f.id for f in fields] == ["f1", "f2", "f3", "f4"]
    assert fields[3].visible_when[0].field_id == "f3"
    assert fields[1].visible_when[0].field_id == "f1"


def test_merge_dedupes_by_label() -> None:
    merged = merge_drafts(
        [
            _draft("Strona A", [_field("f1", "Miejscowość")]),
            _draft("Strona B", [_field("f1", " miejscowość "), _field("f2", "Ulica")]),
        ]
    )
    assert [f.label for _, f in merged.iter_fields()] == ["Miejscowość", "Ulica"]


def test_merge_joins_same_titled_pages_and_takes_first_meta() -> None:
    merged = merge_drafts(
        [
            _draft("Informacje", [_field("f1", "A")], attachments=["Mapa"]),
            _draft("informacje", [_field("f1", "B")], title="Inny", attachments=["Mapa", "Akt"]),
        ]
    )
    assert [p.title for p in merged.subject_pages] == ["Informacje"]
    assert len(merged.subject_pages[0].sections) == 2
    assert merged.title == "Wniosek A" and merged.attachments == ["Mapa", "Akt"]
