from pathlib import Path

import pytest

from app.core.config import Settings
from app.pipeline import converter as converter_module
from app.pipeline.converter import (
    _MACRO_LOCKDOWN_XCU,
    ConversionError,
    ConverterTimeoutError,
    LibreOfficeConverter,
    find_converter,
)
from app.pipeline.upload_validation.policy import FileKind
from tests.unit.fakes import FakeRunner, RunnerBehavior

SOFFICE = "/usr/bin/soffice"


def _source(workdir: Path, ext: str = "doc") -> Path:
    source = workdir / "in" / f"input.{ext}"
    source.parent.mkdir()
    source.write_bytes(b"fake")
    return source


def _converter(runner: FakeRunner) -> LibreOfficeConverter:
    return LibreOfficeConverter(SOFFICE, 60, runner)


async def test_convert_doc_returns_output(tmp_path: Path) -> None:
    out = await _converter(FakeRunner()).convert(_source(tmp_path), FileKind.DOCX, tmp_path)
    assert out == tmp_path / "out" / "input.docx"
    assert out.stat().st_size > 0


async def test_convert_argv_and_env(tmp_path: Path) -> None:
    runner = FakeRunner()
    source = _source(tmp_path)
    await _converter(runner).convert(source, FileKind.DOCX, tmp_path)
    assert runner.calls[0] == [
        SOFFICE,
        f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}",
        "--headless",
        "--invisible",
        "--norestore",
        "--nolockcheck",
        "--nodefault",
        "--nologo",
        "--convert-to",
        "docx:MS Word 2007 XML",
        "--outdir",
        str(tmp_path / "out"),
        str(source),
    ]
    env = runner.envs[0]
    assert set(env) == {"PATH", "HOME", "TMPDIR", "LANG"}
    assert env["HOME"] == env["TMPDIR"] == str(tmp_path)
    assert env["LANG"] == "C.UTF-8"


async def test_convert_ods_uses_calc_filter(tmp_path: Path) -> None:
    runner = FakeRunner()
    out = await _converter(runner).convert(_source(tmp_path, "ods"), FileKind.XLSX, tmp_path)
    assert "xlsx:Calc MS Excel 2007 XML" in runner.calls[0]
    assert out == tmp_path / "out" / "input.xlsx"


async def test_convert_seeds_macro_lockdown(tmp_path: Path) -> None:
    runner = FakeRunner()
    await _converter(runner).convert(_source(tmp_path), FileKind.DOCX, tmp_path)
    xcu = tmp_path / "profile" / "user" / "registrymodifications.xcu"
    assert xcu.read_text(encoding="utf-8") == _MACRO_LOCKDOWN_XCU
    assert runner.profile_seeded == [True]
    assert "DisableMacrosExecution" in _MACRO_LOCKDOWN_XCU


@pytest.mark.parametrize("behavior", ["no_output", "exit1"])
async def test_convert_failure(tmp_path: Path, behavior: RunnerBehavior) -> None:
    with pytest.raises(ConversionError) as info:
        await _converter(FakeRunner(behavior)).convert(_source(tmp_path), FileKind.DOCX, tmp_path)
    assert not isinstance(info.value, ConverterTimeoutError)


async def test_convert_output_under_other_name(tmp_path: Path) -> None:
    with pytest.raises(ConversionError):
        await _converter(FakeRunner("other_name")).convert(
            _source(tmp_path), FileKind.DOCX, tmp_path
        )


async def test_convert_empty_output(tmp_path: Path) -> None:
    with pytest.raises(ConversionError):
        await _converter(FakeRunner("empty")).convert(_source(tmp_path), FileKind.DOCX, tmp_path)


async def test_convert_timeout_propagates(tmp_path: Path) -> None:
    with pytest.raises(ConverterTimeoutError):
        await _converter(FakeRunner("timeout")).convert(_source(tmp_path), FileKind.DOCX, tmp_path)


async def test_convert_oserror_wrapped(tmp_path: Path) -> None:
    with pytest.raises(ConversionError) as info:
        await _converter(FakeRunner("oserror")).convert(_source(tmp_path), FileKind.DOCX, tmp_path)
    assert isinstance(info.value.__cause__, FileNotFoundError)


async def test_convert_rejects_unsupported_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pdf"):
        await _converter(FakeRunner()).convert(_source(tmp_path), FileKind.PDF, tmp_path)


def test_find_converter(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(app_env="development", auth_enabled=False, _env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(converter_module.shutil, "which", lambda _name: None)
    assert find_converter(settings) is None

    monkeypatch.setattr(converter_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    found = find_converter(settings)
    assert isinstance(found, LibreOfficeConverter)
    assert found.soffice_path == "/usr/bin/soffice"
    assert found.timeout_s == settings.converter_timeout_s
