"""builder.py — construct a Claude prompt template from NotebookData."""

from __future__ import annotations

import base64
import re
from datetime import date
from functools import cache
from pathlib import Path

import html2text as _h2t

from .parser import Cell, NotebookData, Output


# ---------------------------------------------------------------------------
# HTML → Markdown converter (shared, configured once)
# ---------------------------------------------------------------------------

@cache
def _h2t_converter() -> _h2t.HTML2Text:
    h = _h2t.HTML2Text()
    h.ignore_links = False       # preserve hyperlinks
    h.ignore_images = True       # images handled separately as artifacts
    h.body_width = 0             # no line-wrapping
    h.single_line_break = False  # blank line between paragraphs
    h.bypass_tables = False      # convert tables to markdown
    h.ignore_tables = False
    return h


_HTML_TAG = re.compile(r"<[a-zA-Z/!][^>]*>")


def _has_html(text: str) -> bool:
    """Return True if the text contains at least one HTML tag."""
    return bool(_HTML_TAG.search(text))


def _html_to_md(text: str) -> str:
    """Convert HTML to markdown, or return the text unchanged if no HTML found."""
    if not _has_html(text):
        return text
    md = _h2t_converter().handle(text)
    # Collapse runs of 3+ blank lines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def build_template(data: NotebookData) -> tuple[str, dict[str, bytes]]:
    """Build a Claude prompt template markdown string and any binary artifacts.

    Args:
        data: Parsed NotebookData from the parser.

    Returns:
        A tuple of:
          - The rendered markdown string for the skill file.
          - A dict mapping artifact filenames to their raw bytes
            (e.g. {"cell_3_output_0.png": <bytes>}).
    """
    artifacts: dict[str, bytes] = {}
    sections: list[str] = []

    # --- Frontmatter ---
    sections.append(_frontmatter(data))

    # --- Overview ---
    overview = _overview(data)
    if overview:
        sections.append(f"## Overview\n\n{overview}")

    # --- Context blocks (cells in notebook order) ---
    cell_blocks: list[str] = []

    for idx, cell in enumerate(data.cells):
        cell_label = f"Cell {idx + 1}"

        if cell.cell_type == "markdown" and cell.source.strip():
            cell_blocks.append(_markdown_block(cell, cell_label))

        elif cell.cell_type == "code" and cell.source.strip():
            parts = [_code_block(cell, cell_label, data.language)]

            for out_idx, out in enumerate(cell.outputs):
                artifact_name = f"cell_{idx + 1}_output_{out_idx}"
                rendered, artifact = _output_block(out, cell_label, out_idx, artifact_name)
                if rendered:
                    parts.append(rendered)
                if artifact:
                    fname, raw = artifact
                    artifacts[fname] = raw

            cell_blocks.append("\n\n".join(parts))

    if cell_blocks:
        sections.append("## Context\n\n" + "\n\n---\n\n".join(cell_blocks))
    else:
        sections.append("## Context")

    # --- Prompt placeholder ---
    sections.append(_prompt_placeholder(data))

    return "\n\n".join(sections) + "\n", artifacts


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _frontmatter(data: NotebookData) -> str:
    return (
        f"---\n"
        f"title: {data.title}\n"
        f"source: {data.source}\n"
        f"language: {data.language}\n"
        f"kernel: {data.kernel_name}\n"
        f"created: {date.today().isoformat()}\n"
        f"---\n\n"
        f"# {data.title}"
    )


def _overview(data: NotebookData) -> str:
    """Return a clean overview from the first descriptive markdown cell.

    HTML is converted to markdown. Cells that resolve to just the notebook
    title are skipped.
    """
    for cell in data.cells:
        if cell.cell_type != "markdown" or not cell.source.strip():
            continue

        lines = cell.source.splitlines()
        # Drop a leading H1 (title already rendered above)
        if lines and lines[0].strip().startswith("# "):
            lines = lines[1:]

        text = "\n".join(lines).strip()
        if not text:
            continue

        text = _html_to_md(text)
        # Skip if the meaningful content is just the notebook title (redundant).
        # Strip markdown horizontal rules and whitespace before comparing.
        bare = re.sub(r"(\*\s*\*\s*\*|---+)", "", text).strip()
        if bare and bare != data.title.strip():
            return text

    return ""


def _markdown_block(cell: Cell, label: str) -> str:
    content = _html_to_md(cell.source.strip())
    return f"**{label}**\n\n{content}"


def _code_block(cell: Cell, label: str, language: str) -> str:
    exec_note = ""
    if cell.execution_count is not None:
        exec_note = f" [In: {cell.execution_count}]"
    return f"**{label}{exec_note}**\n\n```{language}\n{cell.source.strip()}\n```"


def _output_block(
    out: Output,
    cell_label: str,
    out_idx: int,
    artifact_name: str,
) -> tuple[str, tuple[str, bytes] | None]:
    """Render a single output as markdown.

    Returns:
        (rendered_markdown, (artifact_filename, artifact_bytes) | None)
    """
    if out.kind == "text":
        rendered = f"**{cell_label} — Output {out_idx}**\n\n```\n{out.content}\n```"
        return rendered, None

    elif out.kind == "error":
        rendered = f"**{cell_label} — Error {out_idx}**\n\n```\n{out.content}\n```"
        return rendered, None

    elif out.kind == "image":
        ext = _mime_ext(out.mime_type)
        fname = f"{artifact_name}{ext}"
        raw = base64.b64decode(out.content)
        rendered = f"**{cell_label} — Image {out_idx}**\n\n![{cell_label} output](./{fname})"
        return rendered, (fname, raw)

    return "", None


def _prompt_placeholder(data: NotebookData) -> str:
    return (
        "## Prompt\n\n"
        "> Replace this section with your prompt. "
        "Reference the context sections above to ground Claude in the notebook's content.\n\n"
        f"Using the notebook **{data.title}**, ..."
    )


def _mime_ext(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/svg+xml": ".svg",
    }.get(mime_type, ".bin")
