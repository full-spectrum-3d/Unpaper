"""Układ siatki pytań na stronach (spec §8.1)."""

from dataclasses import dataclass

from app.pipeline.build.ir import PageNode

GRID_COLS = 3


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    rows: int
    cols: int


def compute_layout(pages: list[PageNode]) -> dict[str, Placement]:
    """Sekcje jedna pod drugą, pola w sekcji jedno pod drugim. Klucz to `key` węzła."""
    layout: dict[str, Placement] = {}
    for page in pages:
        y = 0
        for section in page.sections:
            rows = len(section.fields) + 1
            layout[section.key] = Placement(0, y, rows, GRID_COLS)
            for index, node in enumerate(section.fields):
                layout[node.key] = Placement(0, index, 1, GRID_COLS)
            y += rows
    return layout
