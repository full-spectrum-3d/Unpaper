import asyncio
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from app.core.errors import AppError, ErrorCode
from app.pipeline import normalize as normalize_module
from app.pipeline.converter import LibreOfficeConverter
from app.pipeline.normalize import NormalizedDocument, normalize
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.validate import ValidatedUpload
from tests.unit.fakes import FakeRunner, RunnerBehavior

_EXT = {
    FileKind.PDF: "pdf",
    FileKind.DOC: "doc",
    FileKind.DOCX: "docx",
    FileKind.XLSX: "xlsx",
    FileKind.ODS: "ods",
    FileKind.JPEG: "jpg",
    FileKind.PNG: "png",
}


def _upload(kind: FileKind = FileKind.DOC) -> ValidatedUpload:
    ext = _EXT[kind]
    return ValidatedUpload(
        filename=f"wniosek.{ext}",
        extension=ext,
        kind=kind,
        mime="application/octet-stream",
        size_bytes=4,
        file=BytesIO(b"fake"),
    )


def _converter(runner: FakeRunner) -> LibreOfficeConverter:
    return LibreOfficeConverter("soffice", 60, runner)


def _empty(path: Path) -> bool:
    return list(path.iterdir()) == []


@pytest.mark.parametrize(
    "kind", [FileKind.PDF, FileKind.DOCX, FileKind.XLSX, FileKind.JPEG, FileKind.PNG]
)
async def test_passthrough(kind: FileKind, tmp_path: Path) -> None:
    upload = _upload(kind)
    doc = await normalize(upload, None, UploadLimits(), tmp_dir=str(tmp_path))
    assert doc.kind is kind
    assert doc.file is upload.file
    assert not doc.converted
    assert _empty(tmp_path)


@pytest.mark.parametrize(
    ("kind", "target"), [(FileKind.DOC, FileKind.DOCX), (FileKind.ODS, FileKind.XLSX)]
)
async def test_converts(kind: FileKind, target: FileKind, tmp_path: Path) -> None:
    runner = FakeRunner()
    doc = await normalize(_upload(kind), _converter(runner), UploadLimits(), tmp_dir=str(tmp_path))
    with doc:
        assert doc.kind is target
        assert doc.converted
        assert doc.file.tell() == 0
        assert zipfile.is_zipfile(doc.file)
    assert runner.calls[0][-1].endswith(f"input.{kind}")
    assert "wniosek" not in " ".join(runner.calls[0])
    assert _empty(tmp_path)


@pytest.mark.parametrize("kind", [FileKind.DOC, FileKind.ODS])
async def test_no_converter_415(kind: FileKind, tmp_path: Path) -> None:
    with pytest.raises(AppError) as info:
        await normalize(_upload(kind), None, UploadLimits(), tmp_dir=str(tmp_path))
    assert info.value.code is ErrorCode.UNSUPPORTED_EXTENSION
    assert info.value.status == 415
    assert info.value.detail is not None and "LibreOffice" in info.value.detail
    assert f".{kind}" in info.value.detail


async def test_timeout_504(tmp_path: Path) -> None:
    with pytest.raises(AppError) as info:
        await normalize(
            _upload(), _converter(FakeRunner("timeout")), UploadLimits(), tmp_dir=str(tmp_path)
        )
    assert info.value.code is ErrorCode.PROCESSING_TIMEOUT
    assert _empty(tmp_path)


@pytest.mark.parametrize("behavior", ["exit1", "no_output", "garbage", "oserror"])
async def test_failure_422(behavior: RunnerBehavior, tmp_path: Path) -> None:
    with pytest.raises(AppError) as info:
        await normalize(
            _upload(), _converter(FakeRunner(behavior)), UploadLimits(), tmp_dir=str(tmp_path)
        )
    assert info.value.code is ErrorCode.DOCUMENT_UNREADABLE
    assert _empty(tmp_path)


async def test_zip_bomb_output_422(tmp_path: Path) -> None:
    limits = UploadLimits(max_uncompressed_bytes=10)
    with pytest.raises(AppError) as info:
        await normalize(_upload(), _converter(FakeRunner()), limits, tmp_dir=str(tmp_path))
    assert info.value.code is ErrorCode.DOCUMENT_UNREADABLE
    assert _empty(tmp_path)


async def test_cancel_cleans_up(tmp_path: Path) -> None:
    runner = FakeRunner("hang")
    task = asyncio.create_task(
        normalize(_upload(), _converter(runner), UploadLimits(), tmp_dir=str(tmp_path))
    )
    await asyncio.wait_for(runner.started.wait(), 5)
    assert not _empty(tmp_path)  # katalog roboczy istnieje w trakcie konwersji
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert _empty(tmp_path)


async def test_concurrent_calls_use_separate_profiles(tmp_path: Path) -> None:
    runner = FakeRunner()
    converter = _converter(runner)
    docs = await asyncio.gather(
        normalize(_upload(), converter, UploadLimits(), tmp_dir=str(tmp_path)),
        normalize(_upload(FileKind.ODS), converter, UploadLimits(), tmp_dir=str(tmp_path)),
    )
    for doc in docs:
        doc.close()
    profiles = {call[1] for call in runner.calls}
    assert len(profiles) == 2


@pytest.mark.parametrize("kind", [FileKind.DOC, FileKind.PDF])
async def test_upload_stream_rewound(kind: FileKind, tmp_path: Path) -> None:
    upload = _upload(kind)
    upload.file.seek(2)
    doc = await normalize(upload, _converter(FakeRunner()), UploadLimits(), tmp_dir=str(tmp_path))
    doc.close()
    assert upload.file.tell() == 0


async def test_oserror_on_copy_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def full_disk(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(normalize_module.shutil, "copyfileobj", full_disk)
    with pytest.raises(OSError, match="No space"):
        await normalize(_upload(), _converter(FakeRunner()), UploadLimits(), tmp_dir=str(tmp_path))
    assert _empty(tmp_path)


@pytest.mark.parametrize("phase", ["_write_input", "_load_output"])
async def test_cancel_waits_for_worker_thread(
    phase: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anulowanie w trakcie pracy wątku: katalog znika dopiero po jego zakończeniu."""
    original = getattr(normalize_module, phase)
    entered = asyncio.Event()
    loop = asyncio.get_running_loop()
    workdir_alive_at_end: list[bool] = []
    spools: list[object] = []

    def slow(*args: object) -> object:
        loop.call_soon_threadsafe(entered.set)
        time.sleep(0.3)
        workdir_alive_at_end.append(any(tmp_path.iterdir()))
        result = original(*args)
        spools.append(result)
        return result

    monkeypatch.setattr(normalize_module, phase, slow)
    task = asyncio.create_task(
        normalize(_upload(), _converter(FakeRunner()), UploadLimits(), tmp_dir=str(tmp_path))
    )
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert workdir_alive_at_end == [True]
    assert _empty(tmp_path)
    for spool in spools:
        if spool is not None:
            assert spool.closed  # type: ignore[attr-defined]


def test_close_ownership() -> None:
    upload = _upload(FileKind.PDF)
    NormalizedDocument(FileKind.PDF, upload.file, converted=False).close()
    assert not upload.file.closed

    own = BytesIO(b"x")
    NormalizedDocument(FileKind.DOCX, own, converted=True).close()
    assert own.closed
