"""Szkic formularza: odpowiedź LLM (`LlmDraft`) i kontrakt dla `build/` (`FormDraft`).

`LlmDraft` to schemat structured output (spec §5.4, projekt LLM §5.2): płaski, bez
rekurencji i bez `null`, bo Ollama wymusza go przez constrained decoding. Jest luźny:
wartości domyślne skracają odpowiedź (mniej tokenów wyjścia), a błędne odwołania
między polami nie odrzucają szkicu - poprawia je `pipeline/draft_repair.py`.
Oświadczeń model nie przepisuje: wykrywa je kod (`pipeline/draft_rules.py`).

`FormDraft` jest ścisły i zawsze spójny. Komunikaty walidacji są po polsku
i wskazują ścieżkę oraz id pola.
"""

from collections.abc import Iterator
from functools import cache
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

FieldKind = Literal[
    "single_choice", "multi_choice", "short_text", "long_text", "number", "date", "file", "info"
]
ApplicantKind = Literal["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
AuthorityKind = Literal["URZAD", "ORGAN"]
ConditionOp = Literal["equals", "not_equals"]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

CHOICE_KINDS: frozenset[str] = frozenset({"single_choice", "multi_choice"})


class _DraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(_DraftModel):
    field_id: str = Field(description="id pola wyboru, od którego zależy widoczność")
    op: ConditionOp
    value: str = Field(description="jedna z opcji tamtego pola")


class DraftField(_DraftModel):
    id: str = Field(description="f1, f2, ... unikalne w całym szkicu")
    label: str = Field(description="krótka etykieta pola")
    kind: FieldKind
    required: bool
    options: list[str] = Field(default=[], description="opcje pola wyboru")
    visible_when: list[Condition] = Field(default=[], description="pusta = zawsze widoczne")


class DraftSection(_DraftModel):
    title: str
    repeating: bool
    fields: list[DraftField] = Field(min_length=1)


class DraftPage(_DraftModel):
    title: str
    sections: list[DraftSection]


class FormDraft(_DraftModel):
    title: NonEmptyStr = Field(description="pełny tytuł wniosku")
    authority_kind: AuthorityKind
    authority_name: NonEmptyStr = Field(description="adresat wniosku")
    applicant_kinds: list[ApplicantKind] = Field(min_length=1)
    attachments: list[str] = Field(default=[], description="załączniki z blankietu")
    statements: list[str] = Field(default=[], description="oświadczenia dosłownie z blankietu")
    subject_pages: list[DraftPage]

    def iter_fields(self) -> Iterator[tuple[str, DraftField]]:
        """Pola szkicu ze ścieżką `subject_pages[i].sections[j].fields[k]`."""
        for i, page in enumerate(self.subject_pages):
            for j, section in enumerate(page.sections):
                for k, field in enumerate(section.fields):
                    yield f"subject_pages[{i}].sections[{j}].fields[{k}]", field

    @model_validator(mode="after")
    def _validate_references(self) -> Self:
        if len(set(self.applicant_kinds)) != len(self.applicant_kinds):
            raise ValueError("applicant_kinds: wartości nie mogą się powtarzać")

        by_id: dict[str, DraftField] = {}
        for path, field in self.iter_fields():
            if field.id in by_id:
                raise ValueError(f"{path}: id {field.id} występuje więcej niż raz")
            by_id[field.id] = field

        for path, field in self.iter_fields():
            for cond in field.visible_when:
                where = f"{path}.visible_when (pole {field.id})"
                target = by_id.get(cond.field_id)
                if target is None:
                    raise ValueError(f"{where}: pole {cond.field_id} nie istnieje")
                if target is field:
                    raise ValueError(f"{where}: pole {field.id} nie może zależeć od siebie")
                if target.kind not in CHOICE_KINDS:
                    raise ValueError(
                        f"{where}: pole {cond.field_id} nie jest polem wyboru ({target.kind})"
                    )
                if cond.value not in target.options:
                    raise ValueError(
                        f"{where}: wartość {cond.value!r} nie jest opcją pola {cond.field_id}"
                    )
        return self


class _LlmModel(BaseModel):
    """Odpowiedź modelu: nadmiarowe klucze pomijamy zamiast odrzucać całą odpowiedź."""

    model_config = ConfigDict(extra="ignore")


class LlmCondition(_LlmModel):
    field_id: str = Field(description="id pola single_choice lub multi_choice")
    op: ConditionOp
    value: str = Field(description="jedna z opcji tamtego pola")


class LlmField(_LlmModel):
    id: str = Field(description="f1, f2, ... unikalne w całym szkicu")
    label: str = Field(description="krótka etykieta pola")
    kind: FieldKind
    required: bool = Field(default=True, description="pomiń, gdy pole jest wymagane")
    options: list[str] = Field(default=[], description="opcje pola wyboru")
    visible_when: list[LlmCondition] = Field(default=[], description="pomiń = zawsze widoczne")


class LlmSection(_LlmModel):
    title: str
    repeating: bool = Field(default=False, description="pomiń, gdy sekcja się nie powtarza")
    fields: list[LlmField]


class LlmPage(_LlmModel):
    title: str
    sections: list[LlmSection]


class LlmDraft(_LlmModel):
    title: NonEmptyStr = Field(description="pełny tytuł wniosku")
    authority_kind: AuthorityKind
    authority_name: NonEmptyStr = Field(description="adresat wniosku")
    applicant_kinds: list[ApplicantKind]
    attachments: list[str] = Field(default=[], description="załączniki z blankietu")
    subject_pages: list[LlmPage]


@cache
def llm_schema() -> dict[str, Any]:
    """JSON Schema odpowiedzi modelu przekazywany do Ollamy w parametrze `format`.

    Wynik jest współdzielony (cache) - nie modyfikować.
    """
    return LlmDraft.model_json_schema()
