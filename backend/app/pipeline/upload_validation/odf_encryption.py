"""Odszyfrowanie dokumentów OpenDocument (ODS) zabezpieczonych hasłem.

Brak gotowej biblioteki bez copyleftu, więc implementujemy specyfikację ODF (cz. 3, §3.4
„Encryption”) na `cryptography` i `argon2-cffi`. Obsługujemy dwa warianty:

1. **Szyfrowanie per plik** (ODF 1.2/1.3, LibreOffice < 24.x): każdy wpis z
   `<manifest:encryption-data>` to `deflate → AES-256-CBC`. Klucz:
   `PBKDF2-HMAC-SHA1(SHA-256(hasło), salt, iteracje)`. Poprawność hasła sprawdzamy sumą
   `sha256-1k` (SHA-256 pierwszych 1024 bajtów po odszyfrowaniu).
2. **Szyfrowanie całego pakietu** („wholesome”, ODF 1.4, domyślne w LibreOffice 24.8+):
   jedyny wpis `encrypted-package` to `deflate(wewnętrzny ZIP) → AES-256-GCM`, a IV
   (12 B) poprzedza szyfrogram. Klucz: `Argon2id(SHA-256(hasło), salt, t, m, p)`.
   Niepoprawne hasło = niezgodny tag GCM.

Wynik to zwykły, niezaszyfrowany pakiet ODS, który potem przechodzi pełną walidację
(MIME, struktura, XML bez DTD). Parametry KDF pochodzą z pliku, więc je ograniczamy, żeby
spreparowany dokument nie zajął CPU ani RAM na długo.
"""

import base64
import binascii
import hashlib
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import IO
from xml.etree.ElementTree import Element, register_namespace, tostring

from argon2.exceptions import HashingError
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode

MANIFEST_PATH = "META-INF/manifest.xml"
WHOLESOME_ENTRY = "encrypted-package"

_NS_MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
_NS_LOEXT = "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"
_M = f"{{{_NS_MANIFEST}}}"
_L = f"{{{_NS_LOEXT}}}"

_AES_CBC = frozenset(
    {
        "http://www.w3.org/2001/04/xmlenc#aes256-cbc",
        "http://www.w3.org/2001/04/xmlenc#aes192-cbc",
        "http://www.w3.org/2001/04/xmlenc#aes128-cbc",
    }
)
_AES_GCM = frozenset(
    {
        "http://www.w3.org/2009/xmlenc11#aes256-gcm",
        "http://www.w3.org/2009/xmlenc11#aes192-gcm",
        "http://www.w3.org/2009/xmlenc11#aes128-gcm",
    }
)
_START_SHA256 = frozenset(
    {"http://www.w3.org/2000/09/xmldsig#sha256", "http://www.w3.org/2001/04/xmlenc#sha256"}
)
_START_SHA1 = frozenset({"http://www.w3.org/2000/09/xmldsig#sha1", "SHA1"})
_KDF_PBKDF2 = frozenset({"PBKDF2", f"{_NS_MANIFEST}#pbkdf2"})
_KDF_ARGON2ID = frozenset(
    {
        "urn:org:documentfoundation:names:experimental:office:manifest:argon2id",
        f"{_NS_MANIFEST}#argon2id",
    }
)
_CHECKSUM_SHA256_1K = frozenset({f"{_NS_MANIFEST}#sha256-1k"})
_CHECKSUM_SHA1_1K = frozenset({"SHA1/1K", f"{_NS_MANIFEST}#sha1-1k"})

_GCM_IV_BYTES = 12
_GCM_TAG_BYTES = 16
_CHECKSUM_SPAN = 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_ENCRYPTED_ENTRIES = 512

# Limity kosztu KDF. LibreOffice używa PBKDF2 100 000 iteracji i Argon2id t=3, m=64 MiB, p=4.
MAX_PBKDF2_ITERATIONS = 1_000_000
MAX_PBKDF2_TOTAL_ITERATIONS = 10_000_000
MAX_ARGON2_TIME_COST = 10
MAX_ARGON2_MEMORY_KIB = 256 * 1024
MAX_ARGON2_LANES = 16
MAX_ARGON2_DERIVATIONS = 4


@dataclass(frozen=True, slots=True)
class _EncryptionData:
    algorithm: str
    iv: bytes
    start_key_algorithm: str
    kdf: str
    salt: bytes
    key_size: int
    pbkdf2_iterations: int
    argon2_params: tuple[int, int, int]  # (time_cost, memory_kib, lanes)
    checksum_type: str | None
    checksum: bytes | None


def _unreadable(detail: str) -> UploadError:
    return UploadError(UploadErrorCode.DOCUMENT_UNREADABLE, detail)


def _invalid_password() -> UploadError:
    return UploadError(
        UploadErrorCode.DOCUMENT_PASSWORD_INVALID,
        "Podane hasło nie odblokowuje dokumentu",
    )


# --- manifest ----------------------------------------------------------------------------


def read_manifest(archive: zipfile.ZipFile) -> Element | None:
    """Parsuje META-INF/manifest.xml (bez DTD). None, gdy pakiet go nie ma."""
    try:
        info = archive.getinfo(MANIFEST_PATH)
    except KeyError:
        return None
    if info.file_size > _MAX_MANIFEST_BYTES:
        raise _unreadable("Plik META-INF/manifest.xml jest za duży")
    try:
        root: Element = fromstring(archive.read(info), forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise _unreadable("Niepoprawny plik META-INF/manifest.xml") from exc
    return root


def encrypted_entries(manifest: Element) -> dict[str, Element]:
    """Ścieżka wpisu → element `encryption-data` dla wszystkich zaszyfrowanych wpisów."""
    found: dict[str, Element] = {}
    for entry in manifest.iter(f"{_M}file-entry"):
        data = entry.find(f"{_M}encryption-data")
        path = entry.get(f"{_M}full-path")
        if data is not None and path:
            found[path] = data
    return found


def _parse_encryption_data(element: Element) -> _EncryptionData:
    algorithm = element.find(f"{_M}algorithm")
    derivation = element.find(f"{_M}key-derivation")
    start = element.find(f"{_M}start-key-generation")
    if algorithm is None or derivation is None:
        raise _unreadable("Niepełny opis szyfrowania w manifeście")
    try:
        checksum_raw = element.get(f"{_M}checksum")
        return _EncryptionData(
            algorithm=algorithm.get(f"{_M}algorithm-name", ""),
            iv=base64.b64decode(algorithm.get(f"{_M}initialisation-vector", ""), validate=True),
            start_key_algorithm=(
                start.get(f"{_M}start-key-generation-name", "SHA1") if start is not None else "SHA1"
            ),
            kdf=derivation.get(f"{_M}key-derivation-name", ""),
            salt=base64.b64decode(derivation.get(f"{_M}salt", ""), validate=True),
            key_size=int(derivation.get(f"{_M}key-size", "16")),
            pbkdf2_iterations=int(derivation.get(f"{_M}iteration-count", "0")),
            argon2_params=(
                int(_attr(derivation, "argon2-iterations", "0")),
                int(_attr(derivation, "argon2-memory", "0")),
                int(_attr(derivation, "argon2-lanes", "0")),
            ),
            checksum_type=element.get(f"{_M}checksum-type"),
            checksum=base64.b64decode(checksum_raw, validate=True) if checksum_raw else None,
        )
    except (ValueError, binascii.Error) as exc:
        raise _unreadable("Niepoprawne parametry szyfrowania w manifeście") from exc


def _attr(element: Element, name: str, default: str) -> str:
    """Parametry Argon2 są w przestrzeni loext (LibreOffice) albo manifest (ODF 1.4)."""
    return element.get(f"{_L}{name}") or element.get(f"{_M}{name}") or default


# --- klucze ------------------------------------------------------------------------------


class _KeyDeriver:
    """Wyprowadza klucze z hasła, z pamięcią podręczną i budżetem kosztu."""

    def __init__(self, password: str) -> None:
        self._password = password.encode("utf-8")
        self._cache: dict[tuple[object, ...], bytes] = {}
        self._pbkdf2_total = 0
        self._argon2_count = 0

    def derive(self, enc: _EncryptionData) -> bytes:
        start_key = self._start_key(enc.start_key_algorithm)
        if enc.key_size not in (16, 24, 32):
            raise _unreadable(f"Nieobsługiwana długość klucza: {enc.key_size} B")
        cache_key = (
            enc.kdf,
            enc.start_key_algorithm,
            enc.salt,
            enc.key_size,
            enc.pbkdf2_iterations,
            enc.argon2_params,
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        if enc.kdf in _KDF_PBKDF2:
            key = self._pbkdf2(start_key, enc)
        elif enc.kdf in _KDF_ARGON2ID:
            key = self._argon2(start_key, enc)
        else:
            raise _unreadable(f"Nieobsługiwana metoda wyprowadzania klucza: {enc.kdf}")
        self._cache[cache_key] = key
        return key

    def _start_key(self, algorithm: str) -> bytes:
        if algorithm in _START_SHA256:
            return hashlib.sha256(self._password).digest()
        if algorithm in _START_SHA1:
            return hashlib.sha1(self._password).digest()  # noqa: S324 - wymagane przez ODF 1.0-1.1
        raise _unreadable(f"Nieobsługiwany skrót klucza startowego: {algorithm}")

    def _pbkdf2(self, start_key: bytes, enc: _EncryptionData) -> bytes:
        iterations = enc.pbkdf2_iterations
        self._pbkdf2_total += iterations
        if not 1 <= iterations <= MAX_PBKDF2_ITERATIONS:
            raise _unreadable(f"Niedozwolona liczba iteracji PBKDF2: {iterations}")
        if self._pbkdf2_total > MAX_PBKDF2_TOTAL_ITERATIONS:
            raise _unreadable("Wyprowadzenie kluczy dokumentu jest zbyt kosztowne")
        kdf = PBKDF2HMAC(hashes.SHA1(), enc.key_size, enc.salt, iterations)  # noqa: S303 - ODF
        return kdf.derive(start_key)

    def _argon2(self, start_key: bytes, enc: _EncryptionData) -> bytes:
        time_cost, memory_kib, lanes = enc.argon2_params
        self._argon2_count += 1
        if not (
            1 <= time_cost <= MAX_ARGON2_TIME_COST
            and 8 * lanes <= memory_kib <= MAX_ARGON2_MEMORY_KIB
            and 1 <= lanes <= MAX_ARGON2_LANES
        ):
            raise _unreadable(
                f"Niedozwolone parametry Argon2id (t={time_cost}, m={memory_kib}, p={lanes})"
            )
        if self._argon2_count > MAX_ARGON2_DERIVATIONS:
            raise _unreadable("Wyprowadzenie kluczy dokumentu jest zbyt kosztowne")
        try:
            return hash_secret_raw(
                start_key, enc.salt, time_cost, memory_kib, lanes, enc.key_size, Type.ID
            )
        except HashingError as exc:
            raise _unreadable("Nie można wyprowadzić klucza Argon2id") from exc


# --- odszyfrowanie wpisu -----------------------------------------------------------------


def _decrypt_entry(data: bytes, enc: _EncryptionData, key: bytes) -> bytes:
    """Zwraca dane po odszyfrowaniu, wciąż skompresowane (raw deflate)."""
    if enc.algorithm in _AES_GCM:
        if len(data) < _GCM_IV_BYTES + _GCM_TAG_BYTES:
            raise _unreadable("Zaszyfrowany wpis jest za krótki")
        try:
            return AESGCM(key).decrypt(data[:_GCM_IV_BYTES], data[_GCM_IV_BYTES:], None)
        except InvalidTag:
            raise _invalid_password() from None

    if enc.algorithm in _AES_CBC:
        if len(enc.iv) != 16 or len(data) % 16:
            raise _unreadable("Niepoprawne dane zaszyfrowane AES-CBC")
        decryptor = Cipher(algorithms.AES(key), modes.CBC(enc.iv)).decryptor()
        plain = decryptor.update(data) + decryptor.finalize()
        _verify_checksum(plain, enc)
        padding = plain[-1] if plain else 0
        if not 1 <= padding <= 16:
            raise _invalid_password()
        return plain[:-padding]

    raise _unreadable(f"Nieobsługiwany algorytm szyfrowania: {enc.algorithm}")


def _verify_checksum(plain: bytes, enc: _EncryptionData) -> None:
    if enc.checksum_type is None or enc.checksum is None:
        return  # bez sumy kontrolnej zły klucz wykryje dopiero dekompresja
    if enc.checksum_type in _CHECKSUM_SHA256_1K:
        digest = hashlib.sha256
    elif enc.checksum_type in _CHECKSUM_SHA1_1K:
        digest = hashlib.sha1
    else:
        raise _unreadable(f"Nieobsługiwany typ sumy kontrolnej: {enc.checksum_type}")
    # Dla krótkich wpisów LibreOffice liczy sumę po zdjęciu dopełnienia; akceptujemy oba.
    padding = plain[-1] if plain else 0
    candidates = [plain[:_CHECKSUM_SPAN]]
    if 1 <= padding <= 16:
        candidates.append(plain[:-padding][:_CHECKSUM_SPAN])
    if not any(digest(chunk).digest() == enc.checksum for chunk in candidates):
        raise _invalid_password()


def _inflate(data: bytes, budget: int) -> bytes:
    """Raw deflate z limitem rozmiaru wyniku (ochrona przed bombą dekompresyjną)."""
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        out = decompressor.decompress(data, budget + 1)
    except zlib.error as exc:
        raise _unreadable("Odszyfrowane dane są uszkodzone") from exc
    if len(out) > budget or decompressor.unconsumed_tail:
        raise UploadError(
            UploadErrorCode.ARCHIVE_TOO_LARGE,
            "Dokument po odszyfrowaniu i rozpakowaniu jest za duży",
        )
    return out


# --- całość ------------------------------------------------------------------------------


def decrypt_odf(
    archive: zipfile.ZipFile,
    manifest: Element,
    password: str,
    out: IO[bytes],
    *,
    max_uncompressed_bytes: int,
) -> None:
    """Zapisuje do `out` niezaszyfrowany pakiet ODF."""
    entries = encrypted_entries(manifest)
    if len(entries) > _MAX_ENCRYPTED_ENTRIES:
        raise _unreadable("Dokument ma zbyt wiele zaszyfrowanych wpisów")
    deriver = _KeyDeriver(password)

    if WHOLESOME_ENTRY in entries:
        enc = _parse_encryption_data(entries[WHOLESOME_ENTRY])
        data = _read_entry(archive, WHOLESOME_ENTRY)
        out.write(_inflate(_decrypt_entry(data, enc, deriver.derive(enc)), max_uncompressed_bytes))
        return

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info, payload in _decrypted_entries(archive, entries, deriver, max_uncompressed_bytes):
            compression = zipfile.ZIP_STORED if info.filename == "mimetype" else None
            target.writestr(info.filename, payload, compress_type=compression)
        target.writestr(MANIFEST_PATH, _strip_encryption(manifest))


def _decrypted_entries(
    archive: zipfile.ZipFile,
    entries: dict[str, Element],
    deriver: _KeyDeriver,
    budget: int,
) -> Iterator[tuple[zipfile.ZipInfo, bytes]]:
    infos = archive.infolist()
    # `mimetype` musi być pierwszym wpisem pakietu ODF.
    infos.sort(key=lambda info: info.filename != "mimetype")
    for info in infos:
        if info.filename == MANIFEST_PATH or info.is_dir():
            continue
        data = archive.read(info)
        if info.filename in entries:
            enc = _parse_encryption_data(entries[info.filename])
            data = _inflate(_decrypt_entry(data, enc, deriver.derive(enc)), budget)
        budget -= len(data)
        if budget < 0:
            raise UploadError(
                UploadErrorCode.ARCHIVE_TOO_LARGE,
                "Dokument po odszyfrowaniu i rozpakowaniu jest za duży",
            )
        yield info, data


def _read_entry(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except KeyError as exc:
        raise _unreadable(f"Brak wpisu {name} opisanego w manifeście") from exc


def _strip_encryption(manifest: Element) -> bytes:
    """Manifest bez `encryption-data`, żeby kolejne etapy (LibreOffice) czytały pakiet jawnie."""
    for entry in manifest.iter(f"{_M}file-entry"):
        for data in entry.findall(f"{_M}encryption-data"):
            entry.remove(data)
    register_namespace("manifest", _NS_MANIFEST)
    register_namespace("loext", _NS_LOEXT)
    serialized: bytes = tostring(manifest, encoding="utf-8", xml_declaration=True)
    return serialized
