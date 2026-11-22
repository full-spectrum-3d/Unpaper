"""Kontenery dokumentów: ZIP (DOCX, XLSX, ODS) i OLE (DOC) (spec §6.3 pkt 7 i 9, §10.2).

ZIP sprawdzamy bez rozpakowywania na dysk:
- liczba wpisów i suma rozmiarów po dekompresji z katalogu centralnego (ochrona przed bombą
  ZIP). `zipfile` nie odda więcej bajtów, niż deklaruje wpis, a przy niezgodności CRC rzuca
  błąd, więc fałszywe rozmiary nie omijają limitu,
- struktura OOXML/ODF: główna część dokumentu ma właściwy typ (docm/xlsm/szablony odpadają),
- każda część XML parsuje się w `defusedxml` z zakazem DTD. Odrzucamy XXE i „billion laughs”,
  więc późniejsze etapy (python-docx, openpyxl) dostają tylko XML bez deklaracji encji.

OLE sprawdzamy przez `olefile`: DOC musi mieć strumień `WordDocument` z poprawnym FIB i bez
flagi szyfrowania.

Pliki z hasłem odszyfrowuje wcześniej moduł `encryption`. Komunikaty „zabezpieczony hasłem”
w tym module to zabezpieczenie na wypadek, gdyby zaszyfrowany plik tam nie został rozpoznany.
"""

import struct
import zipfile
import zlib
from typing import IO

import olefile
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring, iterparse

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import MIB, FileKind, UploadLimits

_CONTENT_TYPES_PART = "[Content_Types].xml"
_CONTENT_TYPES_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
_OOXML = "application/vnd.openxmlformats-officedocument"
_OOXML_MAIN_CONTENT_TYPE: dict[FileKind, str] = {
    FileKind.DOCX: f"{_OOXML}.wordprocessingml.document.main+xml",
    FileKind.XLSX: f"{_OOXML}.spreadsheetml.sheet.main+xml",
}
_ODS_MIMETYPE = b"application/vnd.oasis.opendocument.spreadsheet"
_ODF_MANIFEST = "META-INF/manifest.xml"
_ODF_MANIFEST_NS = "{urn:oasis:names:tc:opendocument:xmlns:manifest:1.0}"
_XML_SUFFIXES = (".xml", ".rels")
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_MAX_CONTENT_TYPES_BYTES = 1 * MIB

_WORD_FIB_MAGIC = 0xA5EC
_WORD_FIB_ENCRYPTED = 0x0100
_ZIP_FLAG_ENCRYPTED = 0x1

_ZIP_READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, OSError)


def _unreadable(detail: str) -> UploadError:
    return UploadError(UploadErrorCode.DOCUMENT_UNREADABLE, detail)


def _mismatch(detail: str) -> UploadError:
    return UploadError(UploadErrorCode.MIME_MISMATCH, detail)


# --- OLE ---------------------------------------------------------------------------------


def inspect_doc(file: IO[bytes]) -> None:
    """DOC (Word 97-2003): strumień WordDocument, sygnatura FIB, brak szyfrowania."""
    ident, flags = _read_word_fib(file)
    if ident != _WORD_FIB_MAGIC:
        raise _unreadable("Plik .doc jest uszkodzony (niepoprawna sygnatura FIB)")
    if flags & _WORD_FIB_ENCRYPTED:
        raise _unreadable("Dokument jest zabezpieczony hasłem")


def word_document_encrypted(file: IO[bytes]) -> bool:
    """Czy to dokument Word 97-2003 z ustawioną flagą fEncrypted (bez rzucania błędów)."""
    try:
        ident, flags = _read_word_fib(file)
    except UploadError:
        return False
    return ident == _WORD_FIB_MAGIC and bool(flags & _WORD_FIB_ENCRYPTED)


def _read_word_fib(file: IO[bytes]) -> tuple[int, int]:
    """Zwraca (wIdent, flagi) z początku FIB w strumieniu WordDocument."""
    file.seek(0)
    try:
        if not olefile.isOleFile(file):
            raise _mismatch("Plik .doc nie jest dokumentem Microsoft Word 97-2003")
        file.seek(0)
        with olefile.OleFileIO(file) as ole:
            if not ole.exists("WordDocument"):
                raise _mismatch("Plik .doc nie zawiera dokumentu Word (brak WordDocument)")
            with ole.openstream("WordDocument") as stream:
                fib = stream.read(12)
    except UploadError:
        raise
    except Exception as exc:  # olefile rzuca różne wyjątki dla uszkodzonych plików
        raise _unreadable("Plik .doc jest uszkodzony") from exc
    finally:
        file.seek(0)

    if len(fib) < 12:
        raise _unreadable("Plik .doc jest uszkodzony (niepełny nagłówek FIB)")
    ident, _, _, _, _, flags = struct.unpack("<HHHHHH", fib)
    return ident, flags


# --- ZIP ---------------------------------------------------------------------------------


def inspect_zip_document(file: IO[bytes], kind: FileKind, limits: UploadLimits) -> None:
    file.seek(0)
    try:
        with zipfile.ZipFile(file) as archive:
            check_archive_limits(archive, limits)
            if kind is FileKind.ODS:
                _check_ods_structure(archive)
            else:
                _check_ooxml_structure(archive, kind)
            _check_xml_parts(archive)
    except UploadError:
        raise
    except _ZIP_READ_ERRORS as exc:
        raise _unreadable(f"Plik .{kind} jest uszkodzony") from exc
    finally:
        file.seek(0)


def check_archive_limits(archive: zipfile.ZipFile, limits: UploadLimits) -> None:
    entries = archive.infolist()
    if len(entries) > limits.max_archive_entries:
        raise UploadError(
            UploadErrorCode.ARCHIVE_TOO_LARGE,
            f"Liczba wpisów w archiwum: {len(entries)}, dopuszczalna: {limits.max_archive_entries}",
        )
    total = sum(entry.file_size for entry in entries)
    if total > limits.max_uncompressed_bytes:
        raise UploadError(
            UploadErrorCode.ARCHIVE_TOO_LARGE,
            f"Dokument po rozpakowaniu ma {total / MIB:.1f} MB, "
            f"dopuszczalne jest {limits.max_uncompressed_bytes / MIB:g} MB",
        )
    if any(entry.flag_bits & _ZIP_FLAG_ENCRYPTED for entry in entries):
        raise _unreadable("Dokument jest zaszyfrowany")


def _check_ooxml_structure(archive: zipfile.ZipFile, kind: FileKind) -> None:
    names = set(archive.namelist())
    if _CONTENT_TYPES_PART not in names:
        raise _mismatch(f"Plik .{kind} nie ma struktury Office Open XML ([Content_Types].xml)")
    info = archive.getinfo(_CONTENT_TYPES_PART)
    if info.file_size > _MAX_CONTENT_TYPES_BYTES:
        raise _unreadable("Plik [Content_Types].xml jest za duży")
    try:
        root = fromstring(archive.read(info), forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise _unreadable("Niepoprawny plik [Content_Types].xml") from exc

    expected = _OOXML_MAIN_CONTENT_TYPE[kind]
    main_parts = [
        override.get("PartName", "")
        for override in root.iter(f"{_CONTENT_TYPES_NS}Override")
        if override.get("ContentType") == expected
    ]
    if len(main_parts) != 1:
        raise _mismatch(
            f"Plik .{kind} nie zawiera głównej części dokumentu odpowiedniego typu "
            "(np. plik z makrami albo szablon)"
        )
    if main_parts[0].lstrip("/") not in names:
        raise _unreadable(f"Brak głównej części dokumentu {main_parts[0]}")


def _check_ods_structure(archive: zipfile.ZipFile) -> None:
    entries = archive.infolist()
    first = entries[0] if entries else None
    if first is None or first.filename != "mimetype" or first.file_size > len(_ODS_MIMETYPE):
        raise _mismatch("Plik .ods nie ma struktury OpenDocument (wpis mimetype)")
    if archive.read(first).strip() != _ODS_MIMETYPE:
        raise _mismatch("Plik .ods nie jest arkuszem OpenDocument")
    names = set(archive.namelist())
    if _ODF_MANIFEST in names and _manifest_declares_encryption(archive):
        raise _unreadable("Dokument jest zabezpieczony hasłem")
    if "content.xml" not in names:
        raise _unreadable("Plik .ods nie zawiera content.xml")


def _manifest_declares_encryption(archive: zipfile.ZipFile) -> bool:
    with archive.open(_ODF_MANIFEST) as stream:
        try:
            for _, element in iterparse(stream, events=("end",), forbid_dtd=True):
                if element.tag == f"{_ODF_MANIFEST_NS}encryption-data":
                    return True
                element.clear()
        except (ParseError, DefusedXmlException) as exc:
            raise _unreadable("Niepoprawny plik META-INF/manifest.xml") from exc
    return False


def _check_xml_parts(archive: zipfile.ZipFile) -> None:
    """Każda część XML musi być poprawna składniowo i wolna od DTD/encji.

    Część XML rozpoznajemy po rozszerzeniu albo po treści: [Content_Types].xml może
    przypisać typ XML dowolnej nazwie (np. `word/document.bin`).
    """
    for entry in archive.infolist():
        if entry.is_dir() or not (
            entry.filename.lower().endswith(_XML_SUFFIXES) or _looks_like_xml(archive, entry)
        ):
            continue
        with archive.open(entry) as stream:
            try:
                for _, element in iterparse(stream, events=("end",), forbid_dtd=True):
                    element.clear()
            except DefusedXmlException as exc:
                raise _unreadable(
                    f"Część {entry.filename} zawiera niedozwolone deklaracje DTD lub encje"
                ) from exc
            except ParseError as exc:
                raise _unreadable(f"Część {entry.filename} nie jest poprawnym XML") from exc


def _looks_like_xml(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bool:
    with archive.open(entry) as stream:
        head = stream.read(64)
    return head.startswith(_UTF16_BOMS) or head.removeprefix(b"\xef\xbb\xbf").lstrip().startswith(
        b"<?xml"
    )
