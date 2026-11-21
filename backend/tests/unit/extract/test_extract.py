import io

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.pipeline.extract import extract
from app.pipeline.normalize import NormalizedDocument
from app.pipeline.upload_validation.policy import FileKind
from tests.unit.extract.fake_ocr import FakeOcr, word
from tests.unit.fakes import FakeClock, office_bytes

SETTINGS = Settings(app_env="development", auth_enabled=False)


def normalized(kind: FileKind, data: bytes) -> NormalizedDocument:
    return NormalizedDocument(kind, io.BytesIO(data), converted=False)


def png_bytes(width: int = 100, height: int = 141) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(("kind", "ext"), [(FileKind.DOCX, "docx"), (FileKind.XLSX, "xlsx")])
def test_dispatch_by_kind(kind: FileKind, ext: str) -> None:
    doc = normalized(kind, office_bytes(ext))
    result = extract(doc, SETTINGS, ocr=FakeOcr())
    assert result.document.source.method == ext
    assert [b.text for b in result.document.iter_blocks()] == ["Wniosek"]
    assert result.warnings == []
    assert doc.file.tell() == 0


@pytest.mark.parametrize("kind", [FileKind.DOCX, FileKind.XLSX, FileKind.PDF, FileKind.PNG])
def test_corrupt_file_is_unreadable(kind: FileKind) -> None:
    with pytest.raises(AppError) as info:
        extract(normalized(kind, b"PK\x03\x04garbage"), SETTINGS, ocr=FakeOcr())
    assert info.value.code == ErrorCode.DOCUMENT_UNREADABLE
    assert "garbage" not in str(info.value)


def test_ocr_unavailable_warns() -> None:
    result = extract(normalized(FileKind.PNG, png_bytes()), SETTINGS, ocr=FakeOcr(fail=True))
    assert [w.code for w in result.warnings] == ["W11_OCR_UNAVAILABLE"]
    assert len(result.document.pages) == 1
    assert result.document.pages[0].blocks == []


def test_low_confidence_warns() -> None:
    engine = FakeOcr([[word("Wniosek", 10, 10, conf=0.4)]])
    result = extract(normalized(FileKind.PNG, png_bytes()), SETTINGS, ocr=engine)
    assert [w.code for w in result.warnings] == ["W12_LOW_OCR_CONFIDENCE"]
    assert "1" in result.warnings[0].message
    assert result.document.ocr_mean_confidence == pytest.approx(0.4)


def test_deadline_between_pages() -> None:
    clock = FakeClock(100.0)
    with pytest.raises(AppError) as info:
        extract(
            normalized(FileKind.PNG, png_bytes()),
            SETTINGS,
            ocr=FakeOcr(),
            deadline=50.0,
            clock=clock,
        )
    assert info.value.code == ErrorCode.PROCESSING_TIMEOUT
