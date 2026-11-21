"""Dokumenty zabezpieczone hasłem: wykrycie i odszyfrowanie przed walidacją zawartości.

| Format     | Jak wygląda zabezpieczenie                          | Czym odszyfrowujemy     |
|------------|-----------------------------------------------------|-------------------------|
| PDF        | hasło użytkownika (RC4 / AES-128 / AES-256)         | PDFium (pypdfium2)      |
| DOCX, XLSX | kontener OLE z `EncryptionInfo` + `EncryptedPackage` | msoffcrypto-tool        |
|            | (ECMA-376 Agile lub Standard)                        |                         |
| DOC        | flaga fEncrypted w FIB (RC4 / RC4 CryptoAPI)         | msoffcrypto-tool        |
| ODS        | `encryption-data` w manifeście (AES-CBC lub GCM)     | `odf_encryption`        |
| JPG, PNG   | formaty nie mają zabezpieczenia hasłem               | -                       |

Wynik to nowy strumień z jawną treścią. Dalsza walidacja (MIME, struktura, bomby, XML bez
DTD) i kolejne etapy pipeline'u pracują już na nim, więc hasło nie wychodzi poza ten moduł.
Plik bez zabezpieczenia przechodzi bez zmian, nawet jeśli klient podał hasło.

Hasła nie logujemy i nie umieszczamy w komunikatach błędów. Koszt wyprowadzania klucza
(spinCount, iteracje PBKDF2, parametry Argon2) pochodzi z pliku, więc go ograniczamy.
"""

import struct
import tempfile
import zipfile
import zlib
from collections.abc import Callable
from typing import IO

import olefile
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from msoffcrypto import exceptions as msoff_errors
from msoffcrypto.format.doc97 import Doc97File
from msoffcrypto.format.ooxml import OOXMLFile

from app.pipeline.pdfium_lock import PDFIUM_LOCK
from app.pipeline.upload_validation.containers import check_archive_limits, word_document_encrypted
from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.odf_encryption import (
    decrypt_odf,
    encrypted_entries,
    read_manifest,
)
from app.pipeline.upload_validation.policy import ACCEPTED_MIME, FileKind, UploadLimits

MAX_AGILE_SPIN_COUNT = 1_000_000
"""ECMA-376 Agile: Office i LibreOffice używają 100 000. msoffcrypto dopuszcza 10 mln."""
_MAX_ENCRYPTION_INFO_BYTES = 64 * 1024
_AGILE_VERSION = (4, 4)

Decryptor = Callable[[IO[bytes]], None]


def _unreadable(detail: str) -> UploadError:
    return UploadError(UploadErrorCode.DOCUMENT_UNREADABLE, detail)


def _invalid_password() -> UploadError:
    return UploadError(
        UploadErrorCode.DOCUMENT_PASSWORD_INVALID, "Podane hasło nie odblokowuje dokumentu"
    )


def _require_password(password: str | None) -> str:
    if not password:
        raise UploadError(
            UploadErrorCode.DOCUMENT_PASSWORD_REQUIRED,
            "Dokument jest zabezpieczony hasłem. Prześlij hasło w polu 'password'",
        )
    return password


def unlock_if_protected(
    file: IO[bytes],
    kind: FileKind,
    detected_mime: str,
    password: str | None,
    limits: UploadLimits,
    *,
    tmp_dir: str | None = None,
) -> IO[bytes] | None:
    """Nowy strumień z odszyfrowaną treścią albo None, gdy plik nie ma zabezpieczenia.

    Rozpoznanie jest tolerancyjne: plik uszkodzony albo innego typu niż rozszerzenie zwraca
    None, a błąd zgłosi dalsza walidacja. Właścicielem zwróconego strumienia jest wołający.
    """
    try:
        match kind:
            case FileKind.PDF:
                if detected_mime in ACCEPTED_MIME[kind] and _pdf_requires_password(file):
                    secret = _require_password(password)
                    return _decrypt_into(
                        lambda out: _decrypt_pdf(file, secret, out), limits, tmp_dir
                    )
            case FileKind.DOCX | FileKind.XLSX:
                if _is_encrypted_ooxml(file):
                    secret = _require_password(password)
                    return _decrypt_into(
                        lambda out: _decrypt_ooxml(file, secret, out), limits, tmp_dir
                    )
            case FileKind.DOC:
                if detected_mime in ACCEPTED_MIME[kind] and word_document_encrypted(file):
                    secret = _require_password(password)
                    return _decrypt_into(
                        lambda out: _decrypt_doc(file, secret, out), limits, tmp_dir
                    )
            case FileKind.ODS:
                if detected_mime in ACCEPTED_MIME[kind]:
                    return _unlock_odf(file, password, limits, tmp_dir)
            case FileKind.JPEG | FileKind.PNG:
                pass
        return None
    finally:
        file.seek(0)


def _decrypt_into(decrypt: Decryptor, limits: UploadLimits, tmp_dir: str | None) -> IO[bytes]:
    out = tempfile.SpooledTemporaryFile(  # noqa: SIM115 - zwracany wołającemu
        max_size=limits.spool_max_bytes, mode="w+b", dir=tmp_dir
    )
    try:
        decrypt(out)
        size = out.seek(0, 2)
        if size == 0:
            raise _unreadable("Odszyfrowany dokument jest pusty")
        if size > limits.max_uncompressed_bytes:
            raise UploadError(
                UploadErrorCode.ARCHIVE_TOO_LARGE, "Dokument po odszyfrowaniu jest za duży"
            )
        out.seek(0)
        return out
    except BaseException:
        out.close()
        raise


# --- PDF ---------------------------------------------------------------------------------


def _pdf_requires_password(file: IO[bytes]) -> bool:
    file.seek(0)
    with PDFIUM_LOCK:
        try:
            pdfium.PdfDocument(file).close()
        except pdfium.PdfiumError as exc:
            return bool(exc.err_code == pdfium_c.FPDF_ERR_PASSWORD)
    return False


def _decrypt_pdf(file: IO[bytes], password: str, out: IO[bytes]) -> None:
    """Zapis kopii bez zabezpieczeń (FPDF_REMOVE_SECURITY). PDFium sam dobiera kodowanie hasła."""
    file.seek(0)
    with PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(file, password=password)
        except pdfium.PdfiumError as exc:
            if exc.err_code == pdfium_c.FPDF_ERR_PASSWORD:
                raise _invalid_password() from None
            if exc.err_code == pdfium_c.FPDF_ERR_SECURITY:
                raise _unreadable("Nieobsługiwany sposób zabezpieczenia PDF") from None
            raise _unreadable("Plik PDF jest uszkodzony") from None
        try:
            document.save(out, flags=pdfium_c.FPDF_REMOVE_SECURITY)
        except pdfium.PdfiumError as exc:
            raise _unreadable("Nie można zapisać odszyfrowanego PDF") from exc
        finally:
            document.close()


# --- DOCX / XLSX (ECMA-376) --------------------------------------------------------------


def _is_encrypted_ooxml(file: IO[bytes]) -> bool:
    file.seek(0)
    try:
        if not olefile.isOleFile(file):
            return False
        file.seek(0)
        with olefile.OleFileIO(file) as ole:
            return bool(ole.exists("EncryptionInfo") and ole.exists("EncryptedPackage"))
    except Exception:
        return False  # uszkodzony OLE: zgłosi go sprawdzenie MIME


def _check_encryption_info(file: IO[bytes]) -> None:
    """msoffcrypto parsuje XML Agile przez minidom; najpierw sprawdzamy go w defusedxml."""
    file.seek(0)
    try:
        with olefile.OleFileIO(file) as ole:
            if ole.get_size("EncryptionInfo") > _MAX_ENCRYPTION_INFO_BYTES:
                raise _unreadable("Nagłówek szyfrowania dokumentu jest za duży")
            with ole.openstream("EncryptionInfo") as stream:
                info = stream.read()
    except UploadError:
        raise
    except Exception as exc:
        raise _unreadable("Uszkodzony nagłówek szyfrowania dokumentu") from exc
    finally:
        file.seek(0)
    if len(info) < 8:
        raise _unreadable("Uszkodzony nagłówek szyfrowania dokumentu")
    if struct.unpack("<HH", info[:4]) == _AGILE_VERSION:
        try:
            fromstring(info[8:], forbid_dtd=True)
        except (ParseError, DefusedXmlException) as exc:
            raise _unreadable("Uszkodzony nagłówek szyfrowania dokumentu") from exc


def _decrypt_ooxml(file: IO[bytes], password: str, out: IO[bytes]) -> None:
    _check_encryption_info(file)
    try:
        office = OOXMLFile(file)
    except Exception as exc:  # msoffcrypto rzuca różne wyjątki dla uszkodzonych nagłówków
        raise _unreadable("Uszkodzony nagłówek szyfrowania dokumentu") from exc
    try:
        if office.type not in ("agile", "standard"):
            raise _unreadable(f"Nieobsługiwany sposób szyfrowania dokumentu ({office.type})")
        if office.type == "agile" and office.info["spinValue"] > MAX_AGILE_SPIN_COUNT:
            raise _unreadable("Wyprowadzenie klucza dokumentu jest zbyt kosztowne")
        try:
            office.load_key(password=password, verify_password=True)
        except msoff_errors.InvalidKeyError:
            raise _invalid_password() from None
        try:
            office.decrypt(out, verify_integrity=office.type == "agile")
        except (msoff_errors.DecryptionError, ValueError, zlib.error) as exc:
            # Hasło już zweryfikowane, więc błąd tutaj oznacza uszkodzone lub zmienione dane.
            raise _unreadable("Zaszyfrowana treść dokumentu jest uszkodzona") from exc
    finally:
        office.file.close()


# --- DOC (Word 97-2003) ------------------------------------------------------------------


def _decrypt_doc(file: IO[bytes], password: str, out: IO[bytes]) -> None:
    file.seek(0)
    try:
        office = Doc97File(file)
    except Exception as exc:
        raise _unreadable("Plik .doc jest uszkodzony") from exc
    if office.info.fib.base.fObfuscation == 1:
        raise _unreadable("Nieobsługiwany sposób zabezpieczenia .doc (zaciemnianie XOR)")
    try:
        office.load_key(password=password)
    except msoff_errors.InvalidKeyError:
        raise _invalid_password() from None
    except msoff_errors.DecryptionError as exc:
        raise _unreadable("Nieobsługiwany sposób szyfrowania dokumentu .doc") from exc
    try:
        office.decrypt(out)
    except Exception as exc:
        raise _unreadable("Zaszyfrowana treść dokumentu .doc jest uszkodzona") from exc


# --- ODS ---------------------------------------------------------------------------------


def _unlock_odf(
    file: IO[bytes], password: str | None, limits: UploadLimits, tmp_dir: str | None
) -> IO[bytes] | None:
    file.seek(0)
    try:
        with zipfile.ZipFile(file) as archive:
            check_archive_limits(archive, limits)
            manifest = read_manifest(archive)
            if manifest is None or not encrypted_entries(manifest):
                return None
            secret = _require_password(password)
            return _decrypt_into(
                lambda out: decrypt_odf(
                    archive,
                    manifest,
                    secret,
                    out,
                    max_uncompressed_bytes=limits.max_uncompressed_bytes,
                ),
                limits,
                tmp_dir,
            )
    except UploadError:
        raise
    except zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, OSError:
        return None  # uszkodzony ZIP: zgłosi go sprawdzenie struktury
