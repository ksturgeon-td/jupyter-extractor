"""sectionizer.py — group NotebookData cells into sections by heading."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import Cell, NotebookData


@dataclass
class Section:
    """A group of notebook cells under a common heading."""

    heading: str       # heading text (no # prefix)
    level: int         # 0=preamble, 1=H1, 2=H2, 3=H3
    cells: list[Cell] = field(default_factory=list)


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)")
_BOLD_ONLY_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")


def sectionize(data: NotebookData) -> list[Section]:
    """Group notebook cells into sections based on markdown headings.

    Markdown headings (# ## ###) and bold-only cells start new sections.
    Cells before the first heading go into a preamble section (level=0).
    Sections with no meaningful content are filtered out.
    """
    sections: list[Section] = []
    current = Section(heading=data.title, level=0)

    for cell in data.cells:
        if cell.cell_type == "markdown" and cell.source.strip():
            heading, level = _detect_heading(cell.source)
            if heading:
                if _has_content(current):
                    sections.append(current)
                current = Section(heading=heading, level=level)
                continue

        current.cells.append(cell)

    if _has_content(current):
        sections.append(current)

    return sections


def _detect_heading(source: str) -> tuple[str, int]:
    """Return (heading_text, level) from the first line, or ("", 0) if not a heading."""
    first_line = source.strip().splitlines()[0]

    # Standard markdown heading: # / ## / ###
    m = _HEADING_RE.match(first_line)
    if m:
        return m.group(2).strip(), len(m.group(1))

    # Bold-only cell — treat as H2 only if nothing else follows
    m = _BOLD_ONLY_RE.match(first_line)
    if m:
        remaining = source.strip()[len(first_line):].strip()
        if not remaining:
            return m.group(1).strip(), 2

    return "", 0


def _has_content(section: Section) -> bool:
    return any(
        c.source.strip()
        for c in section.cells
        if c.cell_type in ("markdown", "code")
    )
