"""Plik .doc z treścią DOCX (zapis Worda pod starym rozszerzeniem) - spec §6.3."""

import io

import pytest

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.validate import validate_file
from tests.unit.fakes import office_bytes

pytestmark = pytest.mark.libmagic


def test_doc_with_docx_content_is_docx() -> None:
    upload = validate_file("Wniosek.DOC", io.BytesIO(office_bytes("docx")), UploadLimits())
    assert upload.kind is FileKind.DOCX
    assert upload.extension == "doc"


def test_doc_with_xlsx_content_still_rejected() -> None:
    with pytest.raises(UploadError) as info:
        validate_file("Wniosek.doc", io.BytesIO(office_bytes("xlsx")), UploadLimits())
    assert info.value.code is UploadErrorCode.MIME_MISMATCH


def test_zip_with_doc_extension_needs_valid_docx() -> None:
    with pytest.raises(UploadError) as info:
        validate_file("Wniosek.doc", io.BytesIO(b"PK\x03\x04" + b"\x00" * 64), UploadLimits())
    assert info.value.code in (UploadErrorCode.MIME_MISMATCH, UploadErrorCode.DOCUMENT_UNREADABLE)
