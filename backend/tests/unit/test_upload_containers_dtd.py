"""Skan DTD/encji obejmuje części XML niezależnie od rozszerzenia (spec §6.3 pkt 7)."""

import io
import zipfile

import pytest

from app.pipeline.upload_validation.containers import inspect_zip_document
from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from tests.unit.fakes import office_bytes

_BOMB = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "x">]><a>&x;</a>'


def _with_part(name: str, data: bytes) -> io.BytesIO:
    buffer = io.BytesIO(office_bytes("docx"))
    with zipfile.ZipFile(buffer, "a") as archive:
        archive.writestr(name, data)
    buffer.seek(0)
    return buffer


def test_clean_docx_passes() -> None:
    inspect_zip_document(io.BytesIO(office_bytes("docx")), FileKind.DOCX, UploadLimits())


def test_dtd_in_part_with_other_extension_is_rejected() -> None:
    with pytest.raises(UploadError) as info:
        inspect_zip_document(_with_part("word/ukryty.bin", _BOMB), FileKind.DOCX, UploadLimits())
    assert info.value.code is UploadErrorCode.DOCUMENT_UNREADABLE


def test_binary_part_is_not_parsed() -> None:
    part = _with_part("word/media/image1.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    inspect_zip_document(part, FileKind.DOCX, UploadLimits())
