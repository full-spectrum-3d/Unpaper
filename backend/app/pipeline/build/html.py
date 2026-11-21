"""Pomocniki HTML dla opisów pól (spec §8). Tekst spoza szablonów zawsze escapowany."""

import re
from html import escape, unescape

from app.models.form import EMPTY_HTML


def html_document(body: str) -> str:
    if not body:
        return EMPTY_HTML
    return f"<html><head></head><body>{body}</body></html>"


def paragraphs(*texts: str) -> str:
    return "".join(f"<p>{escape(text)}</p>" for text in texts if text)


NEW_TAB_NOTE = "link otwiera się w nowej karcie"
_LINK = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_ARIA_LABEL = re.compile(r'\s*aria-label="[^"]*"')


def _link_label(text: str) -> str:
    """`aria-label` zastępuje nazwę linku, więc zawiera jego tekst i informację o nowej karcie."""
    return f"{text} – {NEW_TAB_NOTE}"  # noqa: RUF001


def external_link(href: str, text: str) -> str:
    return (
        f'<a href="{escape(href)}" rel="noopener noreferrer" target="_blank" '
        f'title="{escape(text)}" aria-label="{escape(_link_label(text))}">{escape(text)}</a>'
    )


def accessible_links(html: str) -> str:
    """Poprawia linki z szablonów: `aria-label` z tekstem linku, `rel` i `target` na miejscu."""

    def fix(match: re.Match[str]) -> str:
        attrs, inner = match.group(1), match.group(2)
        if "target=" not in attrs:
            return match.group(0)  # link wewnętrzny (np. kotwica) - bez zmian
        text = " ".join(unescape(_TAG.sub("", inner)).split())
        attrs = _ARIA_LABEL.sub("", attrs)
        if "rel=" not in attrs:
            attrs += ' rel="noopener noreferrer"'
        if text:
            attrs += f' aria-label="{escape(_link_label(text))}"'
        return f"<a{attrs}>{inner}</a>"

    return _LINK.sub(fix, html)
