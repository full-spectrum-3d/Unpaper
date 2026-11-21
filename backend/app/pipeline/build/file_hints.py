"""Opis ograniczeń pól plikowych: formaty, rozmiar, liczba plików (standard, spec §7.4 D8)."""

from app.pipeline.build.html import paragraphs

FILE_FORMATS = ".jpg, .pdf, .png, .jpeg"
FILE_LIMITS_TEXT = "Maksymalny rozmiar pliku: 10 MB. Maksymalna liczba plików: 1."


def file_constraints_html() -> str:
    return paragraphs(f"Dopuszczalny format pliku: {FILE_FORMATS}. {FILE_LIMITS_TEXT}")
