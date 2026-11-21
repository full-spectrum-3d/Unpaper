"""Minimalny generator PDF do testów: tekst Helvetica (ASCII), prostokąty, strona-skan.

Współrzędne jak w pdfplumber: punkty od lewego górnego rogu strony A4 (595 x 842).
"""

from dataclasses import dataclass, field

WIDTH, HEIGHT = 595, 842


@dataclass
class PdfPage:
    ops: list[str] = field(default_factory=list)
    scanned: bool = False

    def text(
        self, x: float, top: float, text: str, *, size: float = 10, bold: bool = False
    ) -> PdfPage:
        font = "F2" if bold else "F1"
        baseline = HEIGHT - top - size * 0.8
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.ops.append(f"BT /{font} {size} Tf {x} {baseline} Td ({escaped}) Tj ET")
        return self

    def rect(self, x0: float, top: float, x1: float, bottom: float) -> PdfPage:
        """Ramka z czterech cienkich wypełnionych pasków (jak w blankietach z Worda)."""
        for bx0, btop, bx1, bbottom in (
            (x0, top, x1, top + 0.5),
            (x0, bottom - 0.5, x1, bottom),
            (x0, top, x0 + 0.5, bottom),
            (x1 - 0.5, top, x1, bottom),
        ):
            self.ops.append(f"{bx0} {HEIGHT - bbottom} {bx1 - bx0} {bbottom - btop} re f")
        return self


def make_pdf(pages: list[PdfPage]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    bold = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    image = add(
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream"
    )
    pages_id = len(objects) + 1 + 2 * len(pages)
    kids: list[int] = []
    for page in pages:
        content = (
            f"q {WIDTH} 0 0 {HEIGHT} 0 0 cm /Im1 Do Q" if page.scanned else "\n".join(page.ops)
        ).encode("cp1252")
        stream = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        kids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] "
                f"/Resources << /Font << /F1 {font} 0 R /F2 {bold} 0 R >> "
                f"/XObject << /Im1 {image} 0 R >> >> /Contents {stream} 0 R >>".encode()
            )
        )
    refs = " ".join(f"{k} 0 R" for k in kids)
    assert add(f"<< /Type /Pages /Kids [{refs}] /Count {len(kids)} >>".encode()) == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref,
    )
    return bytes(out)
