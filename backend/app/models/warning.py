"""Ostrzeżenie konwersji - wspólne dla analizy, budowy, weryfikacji i raportu (spec §6.2)."""

from pydantic import BaseModel, ConfigDict, Field


class ConversionWarning(BaseModel):
    """Ostrzeżenie z kodem `Wnn_NAZWA` i opcjonalną ścieżką do miejsca, którego dotyczy."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(pattern=r"^W\d{2}_[A-Z0-9_]+$")
    message: str
    path: str | None = None
