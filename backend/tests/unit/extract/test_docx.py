import io

import docx
from docx.enum.text import WD_BREAK
from docx.oxml import parse_xml

from app.models.document import DocumentModel
from app.pipeline.extract.docx import extract_docx
from tests.unit.extract.helpers import kinds

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = (
    f'xmlns:w="{W}" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def roundtrip(document: docx.document.Document) -> DocumentModel:
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return extract_docx(buffer)


def textbox_run(text: str, x_pt: float, y_pt: float, *, with_fallback: bool = True) -> str:
    emu = 12700
    fallback = (
        f'<mc:Fallback><w:pict><v:shape style="position:absolute;margin-left:{x_pt}pt;'
        f'margin-top:{y_pt}pt;width:100pt;height:12pt"><v:textbox><w:txbxContent>'
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape>"
        "</w:pict></mc:Fallback>"
        if with_fallback
        else ""
    )
    return (
        f'<w:r {NS}><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wp:anchor>'
        f'<wp:positionH relativeFrom="column"><wp:posOffset>{int(x_pt * emu)}</wp:posOffset>'
        f'</wp:positionH><wp:positionV relativeFrom="paragraph"><wp:posOffset>'
        f"{int(y_pt * emu)}</wp:posOffset></wp:positionV>"
        f'<wp:extent cx="{100 * emu}" cy="{12 * emu}"/><a:graphic><a:graphicData><wps:wsp>'
        f"<wps:txbx><w:txbxContent><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:txbxContent>"
        f"</wps:txbx></wps:wsp></a:graphicData></a:graphic></wp:anchor></w:drawing>"
        f"</mc:Choice>{fallback}</mc:AlternateContent></w:r>"
    )


def test_paragraphs_headings_and_tables() -> None:
    document = docx.Document()
    document.add_heading("Dane wnioskodawcy", level=1)
    document.add_paragraph("Zwykły akapit z treścią.")
    table = document.add_table(rows=2, cols=2)
    for r, row in enumerate([["Imię", ""], ["Nazwisko", "x"]]):
        for c, text in enumerate(row):
            table.cell(r, c).text = text
    doc = roundtrip(document)
    blocks = list(doc.iter_blocks())
    assert [(b.kind, b.text) for b in blocks[:3]] == [
        ("heading", "Dane wnioskodawcy"),
        ("paragraph", "Zwykły akapit z treścią."),
        ("table", ""),
    ]
    assert [(b.table.row, b.table.col, b.text) for b in blocks[3:] if b.table] == [
        (0, 0, "Imię"),
        (0, 1, ""),
        (1, 0, "Nazwisko"),
        (1, 1, "x"),
    ]
    assert doc.source.method == "docx"


def test_merged_cells_once() -> None:
    document = docx.Document()
    table = document.add_table(rows=2, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Scalona"
    table.cell(0, 2).text = "Prawa"
    blocks = [b for b in roundtrip(document).iter_blocks() if b.kind == "table_cell"]
    assert [(b.table.row, b.table.col) for b in blocks if b.table][:2] == [(0, 0), (0, 2)]
    assert [b.text for b in blocks].count("Scalona") == 1


def test_single_column_table_is_flattened() -> None:
    document = docx.Document()
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Ramka wokół tekstu"
    assert kinds(roundtrip(document)) == [("paragraph", "Ramka wokół tekstu")]


def test_page_break_starts_new_page() -> None:
    document = docx.Document()
    document.add_paragraph("Strona pierwsza").add_run().add_break(WD_BREAK.PAGE)
    document.add_paragraph("Strona druga")
    doc = roundtrip(document)
    assert [[b.text for b in p.blocks] for p in doc.pages] == [
        ["Strona pierwsza"],
        ["Strona druga"],
    ]


def test_checkbox_bullet_from_numbering() -> None:
    document = docx.Document()
    paragraph = document.add_paragraph("ilości użytków rolnych", style="List Bullet")
    numbering = document.part.numbering_part.element
    num_id = paragraph._p.pPr.numPr.numId.val if paragraph._p.pPr.numPr is not None else None
    if num_id is None:  # styl listy trzyma numPr w definicji stylu - dopnij jawnie
        num_id = 1
        paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = num_id
        paragraph._p.pPr.numPr.get_or_add_ilvl().val = 0
    abstract = parse_xml(
        f'<w:abstractNum {NS} w:abstractNumId="77"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
        '<w:lvlText w:val=""/></w:lvl></w:abstractNum>'
    )
    numbering.insert(0, abstract)
    for num in numbering.findall(f"{{{W}}}num"):
        if num.get(f"{{{W}}}numId") == str(num_id):
            num.find(f"{{{W}}}abstractNumId").set(f"{{{W}}}val", "77")
    assert kinds(roundtrip(document)) == [("checkbox_option", "ilości użytków rolnych")]


def test_glyph_in_text_and_label() -> None:
    document = docx.Document()
    document.add_paragraph("□ Stypendium □ Nagroda")
    document.add_paragraph("Wnioskodawca:")
    document.add_paragraph("……………………")
    assert kinds(roundtrip(document)) == [
        ("checkbox_option", "Stypendium"),
        ("checkbox_option", "Nagroda"),
        ("label", "Wnioskodawca:"),
        ("input_placeholder", ""),
    ]


def test_tabs_split_segments() -> None:
    document = docx.Document()
    paragraph = document.add_paragraph("Wnioskodawca:")
    paragraph.add_run().add_tab()
    paragraph.add_run("Adresat:")
    assert kinds(roundtrip(document)) == [("label", "Wnioskodawca:"), ("label", "Adresat:")]


def test_textbox_alternate_content_not_duplicated() -> None:
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph._p.append(parse_xml(textbox_run("Treść pola", 10, 10)))
    texts = [b.text for b in roundtrip(document).iter_blocks()]
    assert texts == ["Treść pola"]


def test_textboxes_ordered_by_position() -> None:
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph._p.append(parse_xml(textbox_run("Drugi", 10, 200, with_fallback=False)))
    paragraph._p.append(parse_xml(textbox_run("Pierwszy", 10, 100, with_fallback=False)))
    assert [b.text for b in roundtrip(document).iter_blocks()] == ["Pierwszy", "Drugi"]
