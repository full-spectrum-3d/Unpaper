"""Problemy zgłaszane przez build i verify (spec §8, §9)."""

from dataclasses import dataclass
from enum import StrEnum


class IssueCode(StrEnum):
    SCHEMA = "SCHEMA"
    # Reguły (błędy)
    R01_TITLE = "R01_TITLE"
    R02_TABS = "R02_TABS"
    R03_EMPTY_PAGE = "R03_EMPTY_PAGE"
    R03_FIELD_OUTSIDE_SECTION = "R03_FIELD_OUTSIDE_SECTION"
    R04_NESTED_SECTION = "R04_NESTED_SECTION"
    R05_FINISH_INPUT = "R05_FINISH_INPUT"
    R06_REQUIREDNESS = "R06_REQUIREDNESS"
    R07_FLOW = "R07_FLOW"
    R08_DICTIONARY = "R08_DICTIONARY"
    R09_OPTIONS = "R09_OPTIONS"
    R10_INITIAL_DATA = "R10_INITIAL_DATA"
    R11_STATE = "R11_STATE"
    R12_DUPLICATE_TECH_NAME = "R12_DUPLICATE_TECH_NAME"
    R12_DUPLICATE_ID = "R12_DUPLICATE_ID"
    R13_CONSENT = "R13_CONSENT"
    R14_INFO_SECTION = "R14_INFO_SECTION"
    R15_VALIDATOR = "R15_VALIDATOR"
    R16_SECTION_TITLE = "R16_SECTION_TITLE"
    # Ostrzeżenia
    W01_LLM_FALLBACK = "W01_LLM_FALLBACK"
    W02_LABEL_TOO_LONG = "W02_LABEL_TOO_LONG"
    W03_CONDITION_UNRESOLVED = "W03_CONDITION_UNRESOLVED"
    W05_TITLE_PREFIX = "W05_TITLE_PREFIX"
    W06_STATE_REMOVED = "W06_STATE_REMOVED"
    W07_CHOICE_OPTIONS = "W07_CHOICE_OPTIONS"
    W08_TITLE_TRUNCATED = "W08_TITLE_TRUNCATED"
    W09_INITIAL_DATA_SKIPPED = "W09_INITIAL_DATA_SKIPPED"
    W10_ATTACHMENT_DUPLICATE = "W10_ATTACHMENT_DUPLICATE"
    W11_FINISH_NOT_INFO = "W11_FINISH_NOT_INFO"
    W12_ID_FORMAT = "W12_ID_FORMAT"


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result
