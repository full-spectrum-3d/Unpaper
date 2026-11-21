from app.pipeline.extract.layout import TableGrid
from tests.unit.extract.helpers import box, frame, kinds, run_layout, span


def test_label_before_frame() -> None:
    doc = run_layout([span("Miejscowość", 10, 100, 70)], [frame(80, 98, 300, 112)])
    assert kinds(doc) == [("label", "Miejscowość"), ("input_placeholder", "")]


def test_adjacent_frames_merge() -> None:
    combs = [frame(80 + 17 * i, 98, 97 + 17 * i, 118) for i in range(10)]
    doc = run_layout([span("NIP", 10, 102, 30)], combs)
    assert kinds(doc) == [("label", "NIP"), ("input_placeholder", "")]
    assert doc.pages[0].blocks[1].bbox == box(80, 98, 250, 118)


def test_stacked_frames_merge() -> None:
    rows = [frame(10, 100 + 15 * i, 400, 115 + 15 * i) for i in range(3)]
    doc = run_layout([span("Uzasadnienie", 10, 80, 80)], rows)
    assert kinds(doc) == [("label", "Uzasadnienie"), ("input_placeholder", "")]


def test_frame_with_text_inside_is_not_field() -> None:
    doc = run_layout([span("Uwagi", 20, 100, 60)], [frame(10, 95, 300, 115)])
    assert kinds(doc) == [("paragraph", "Uwagi")]


def test_square_frame_makes_checkbox_option() -> None:
    doc = run_layout([span("Gotówką w kasie", 30, 100, 110)], [frame(12, 100, 22, 110)])
    assert kinds(doc) == [("checkbox_option", "Gotówką w kasie")]


def test_square_frame_followed_by_labelled_field_stays_field() -> None:
    doc = run_layout(
        [span("Nr lokalu", 10, 100, 50), span("Kod", 80, 100, 100)],
        [frame(55, 99, 69, 112), frame(105, 98, 200, 112)],
    )
    assert kinds(doc) == [
        ("label", "Nr lokalu"),
        ("input_placeholder", ""),
        ("label", "Kod"),
        ("input_placeholder", ""),
    ]


def test_glyph_options_split() -> None:
    doc = run_layout([span(" Tak  Nie", 10, 100, 80)])
    assert kinds(doc) == [("checkbox_option", "Tak"), ("checkbox_option", "Nie")]


def test_two_columns_two_blocks() -> None:
    doc = run_layout([span("Wnioskodawca:", 10, 100, 80), span("Adresat:", 300, 100, 340)])
    assert kinds(doc) == [("label", "Wnioskodawca:"), ("label", "Adresat:")]


def test_words_join_into_one_segment() -> None:
    doc = run_layout([span("Imię", 10, 100, 30), span("i", 33, 100, 36), span("nazwisko", 39, 100)])
    assert kinds(doc) == [("paragraph", "Imię i nazwisko")]


def test_heading_by_size_and_wrapped_paragraph_merge() -> None:
    doc = run_layout(
        [
            span("Tytuł formularza", 10, 50, 200, h=14, size=14),
            span("Zgodnie z art. 13 ust. 1", 10, 80, 500, size=10),
            span("dalszy ciąg", 10, 92, 100, size=10),
            span("Inny akapit", 10, 130, 100, size=10),
        ]
    )
    assert kinds(doc) == [
        ("heading", "Tytuł formularza"),
        ("paragraph", "Zgodnie z art. 13 ust. 1 dalszy ciąg"),
        ("paragraph", "Inny akapit"),
    ]


def test_fill_only_span_is_placeholder() -> None:
    doc = run_layout([span("…………….", 10, 100), span("(imię i nazwisko)", 10, 115)])
    assert kinds(doc) == [("input_placeholder", ""), ("paragraph", "(imię i nazwisko)")]


def test_table_grid_emits_cells_in_reading_order() -> None:
    grid = TableGrid(
        box(10, 200, 300, 240), [(1, 0, "1"), (0, 1, "Nazwa"), (0, 0, "Lp"), (1, 1, "")]
    )
    doc = run_layout([span("Przed", 10, 100), span("Po", 10, 300)], tables=[grid])
    blocks = list(doc.iter_blocks())
    assert [b.kind for b in blocks] == [
        "paragraph",
        "table",
        "table_cell",
        "table_cell",
        "table_cell",
        "table_cell",
        "paragraph",
    ]
    assert [(b.table.row, b.table.col, b.text) for b in blocks[2:6] if b.table] == [
        (0, 0, "Lp"),
        (0, 1, "Nazwa"),
        (1, 0, "1"),
        (1, 1, ""),
    ]


def test_ocr_confidence_is_mean_of_spans() -> None:
    doc = run_layout(
        [span("Ala", 10, 100, 30, confidence=0.9), span("ma", 33, 100, 45, confidence=0.5)]
    )
    assert doc.pages[0].blocks[0].ocr_confidence == 0.7


def test_tall_frame_is_own_line() -> None:
    doc = run_layout(
        [span("Opis sprawy", 10, 100, 70), span("Dalej", 10, 200, 40)],
        [frame(80, 95, 400, 180)],
    )
    assert kinds(doc) == [
        ("label", "Opis sprawy"),
        ("input_placeholder", ""),
        ("paragraph", "Dalej"),
    ]


def test_consecutive_fields_without_labels_collapse() -> None:
    rows = [
        frame(10 + 120 * c, 100 + 40 * r, 110 + 120 * c, 120 + 40 * r)
        for r in range(3)
        for c in range(3)
    ]
    doc = run_layout([span("Zalaczniki", 10, 60, 80), span("Dalej", 10, 300, 40)], rows)
    assert kinds(doc) == [
        ("label", "Zalaczniki"),
        ("input_placeholder", ""),
        ("paragraph", "Dalej"),
    ]
