import pytest

from app.core.text import to_tech_name


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Numer PESEL", "numer_pesel"),
        ("Łączne zobowiązanie pieniężne", "laczne_zobowiazanie_pieniezne"),
        ("  Kraj / państwo  ", "kraj_panstwo"),
        ("Źdźbło", "zdzblo"),
    ],
)
def test_to_tech_name(text: str, expected: str) -> None:
    assert to_tech_name(text) == expected
