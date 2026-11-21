"""Opis ograniczeń pól plikowych ze szkicu (standard, spec §7.4 D8)."""

from app.models.draft import DraftField
from app.models.form import FieldType
from app.pipeline.build.fields import map_draft_field


def _draft(label: str, kind: str) -> DraftField:
    return DraftField(id="f1", label=label, kind=kind, required=False)  # type: ignore[arg-type]


def test_file_field_gets_constraints_description() -> None:
    node, _ = map_draft_field(_draft("Skan umowy", "file"), key="k")
    assert node.type is FieldType.FILE_UPLOADER
    assert "Dopuszczalny format pliku: .jpg, .pdf, .png, .jpeg." in node.description_html
    assert "Maksymalny rozmiar pliku: 10 MB." in node.description_html


def test_non_file_field_has_no_file_description() -> None:
    node, _ = map_draft_field(_draft("Opis", "short_text"), key="k")
    assert node.description_html == ""
