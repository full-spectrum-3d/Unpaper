"""Pomocniki HTML dla opisów pól (spec §8). Tekst spoza szablonów zawsze escapowany."""

from html import escape

from app.models.form import EMPTY_HTML


def html_document(body: str) -> str:
    if not body:
        return EMPTY_HTML
    return f"<html><head></head><body>{body}</body></html>"


def paragraphs(*texts: str) -> str:
    return "".join(f"<p>{escape(text)}</p>" for text in texts if text)


def external_link(href: str, text: str) -> str:
    return (
        f'<a href="{escape(href)}" rel="noopener noreferrer" target="_blank" '
        f'aria-label="Link otwiera się w nowej karcie">{escape(text)}</a>'
    )
