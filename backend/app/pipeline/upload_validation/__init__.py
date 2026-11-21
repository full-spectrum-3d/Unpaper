"""[1] Walidacja wejścia: nazwa, rozmiar, rozszerzenie, MIME, bomby ZIP (spec §6.3).

Moduły:
- `receive`    - strumieniowy odbiór multipart: dokładnie 1 plik, limit rozmiaru, spool,
                 opcjonalne pole `password`
- `filename`   - długość i znaki nazwy, rozszerzenie
- `mime`       - MIME z zawartości (libmagic) vs rozszerzenie
- `containers` - DOCX/XLSX/ODS (ZIP: struktura, bomby, XML bez DTD) i DOC (OLE)
- `documents`  - PDF (strony) i obrazy (piksele, uszkodzenia)
- `encryption` - wykrycie hasła i odszyfrowanie PDF, DOCX, XLSX, DOC (msoffcrypto), ODS
- `odf_encryption` - odszyfrowanie ODF: AES-CBC + PBKDF2 oraz AES-GCM + Argon2id
- `validate`   - kolejność sprawdzeń i wynik `ValidatedUpload`

Użycie w endpoincie (bez parametru `UploadFile`, żeby FastAPI nie wczytał ciała wcześniej):

    upload = await accept_upload(request.stream(), request.headers.get("content-type"), limits)
    with upload:
        ...  # upload.file, upload.kind, upload.mime, upload.page_count, upload.decrypted

Plik z hasłem bez pola `password` kończy się `DOCUMENT_PASSWORD_REQUIRED` (422), a złe
hasło `DOCUMENT_PASSWORD_INVALID` (422). Frontend pyta wtedy o hasło i ponawia żądanie.
"""

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.validate import ValidatedUpload, accept_upload, validate_file

__all__ = [
    "FileKind",
    "UploadError",
    "UploadErrorCode",
    "UploadLimits",
    "ValidatedUpload",
    "accept_upload",
    "validate_file",
]
