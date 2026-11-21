"""Propozycje nowych słowników eUsług (spec §8.6).

Słownik proponowany jeszcze nie istnieje w Generatorze Formularzy COI: pole
zachowuje opcje inline, a propozycja trafia do raportu konwersji
(`report.dictionaryProposals`) i do `GET /dictionaries` ze statusem `PROPOSED`.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _ProposalModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True
    )


class DictionaryItem(_ProposalModel):
    code: str
    name: str
    tech_name: str
    valid_from: str | None = None
    valid_to: str | None = None


class DictionaryProposal(_ProposalModel):
    name: str
    title: str
    description: str
    item_structure: tuple[str, ...]
    items: tuple[DictionaryItem, ...]
    used_by: tuple[str, ...]
