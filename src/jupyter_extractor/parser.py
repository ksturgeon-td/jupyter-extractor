"""parser.py — extract structured data from a parsed NotebookNode."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Literal

import nbformat


CellType = Literal["markdown", "code", "raw"]


@dataclass
class Output:
    """A single cell output (text, error, or image)."""
    kind: Literal["text", "error", "image"]
    content: str          # text content or base64-encoded image data
    mime_type: str = ""   # e.g. "image/png" for images


@dataclass
class Cell:
    """A single notebook cell with its outputs."""
    cell_type: CellType
    source: str
    outputs: list[Output] = field(default_factory=list)
    execution_count: int | None = None


@dataclass
class NotebookData:
    """All structured data extracted from a notebook."""
    title: str
    source: str           # original URL or file path
    language: str         # kernel language, e.g. "python"
    kernel_name: str
    cells: list[Cell]


def parse_notebook(nb: nbformat.NotebookNode, source: str) -> NotebookData:
    """Extract structured data from a NotebookNode.

    Args:
        nb: A parsed nbformat.NotebookNode.
        source: The original URL or file path (for metadata).

    Returns:
        A NotebookData instance with all cells and metadata.
    """
    lang = nb.metadata.get("kernelspec", {}).get("language", "python")
    kernel_name = nb.metadata.get("kernelspec", {}).get("display_name", "Python")
    title = _infer_title(nb)

    cells: list[Cell] = []
    for raw_cell in nb.cells:
        cell = _parse_cell(raw_cell)
        cells.append(cell)

    return NotebookData(
        title=title,
        source=source,
        language=lang,
        kernel_name=kernel_name,
        cells=cells,
    )


def _infer_title(nb: nbformat.NotebookNode) -> str:
    """Infer a title from the notebook.

    Priority order:
    1. First markdown H1 heading (# Title)
    2. Largest HTML heading text in a markdown cell (h1/h2 or large styled element)
    3. Notebook metadata 'title' field
    4. 'Untitled Notebook' fallback
    """
    import re

    for cell in nb.cells:
        if cell.cell_type != "markdown" or not cell.source.strip():
            continue
        src = cell.source

        # 1. Markdown H1
        for line in src.splitlines():
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()

        # 2. HTML <h1> or <h2>
        m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", src, re.IGNORECASE | re.DOTALL)
        if m:
            text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if text:
                return text

        # 3. HTML element with large font-size (e.g. font-size:36px style)
        m = re.search(
            r"font-size:\s*(?:3[0-9]|[4-9]\d)\w+[^>]*>(.*?)</[a-z]+>",
            src,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            # Take only the first non-empty line
            first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
            if first_line:
                return first_line

    return nb.metadata.get("title", "Untitled Notebook")


def _parse_cell(raw: nbformat.NotebookNode) -> Cell:
    outputs: list[Output] = []

    if raw.cell_type == "code":
        for out in raw.get("outputs", []):
            outputs.extend(_parse_output(out))

    return Cell(
        cell_type=raw.cell_type,
        source=raw.source,
        outputs=outputs,
        execution_count=raw.get("execution_count"),
    )


def _parse_output(out: nbformat.NotebookNode) -> list[Output]:
    results: list[Output] = []
    output_type = out.get("output_type", "")

    if output_type in ("stream", "display_data", "execute_result"):
        # Plain text
        text = None
        if output_type == "stream":
            text = "".join(out.get("text", []))
        else:
            data = out.get("data", {})
            # Prefer plain text; fall back to markdown
            text = data.get("text/plain") or data.get("text/markdown")
            if isinstance(text, list):
                text = "".join(text)

            # Images
            for mime in ("image/png", "image/jpeg", "image/svg+xml"):
                img_data = data.get(mime)
                if img_data:
                    if isinstance(img_data, list):
                        img_data = "".join(img_data)
                    results.append(Output(kind="image", content=img_data, mime_type=mime))

        if text:
            results.append(Output(kind="text", content=text.rstrip()))

    elif output_type == "error":
        tb = "\n".join(out.get("traceback", []))
        # Strip ANSI escape codes for clean text
        import re
        tb = re.sub(r"\x1b\[[0-9;]*m", "", tb)
        results.append(Output(kind="error", content=tb))

    return results
