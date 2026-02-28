"""writer.py — write the skill file and artifacts to a chosen output folder."""

from __future__ import annotations

import re
from pathlib import Path


def write_output(
    markdown: str,
    artifacts: dict[str, bytes],
    output_dir: Path,
    notebook_title: str,
) -> Path:
    """Write the skill markdown and any binary artifacts to output_dir.

    Creates output_dir if it does not exist. The skill file is named after
    the notebook title (slugified). Artifacts are written alongside it.

    Args:
        markdown: The rendered Claude prompt template string.
        artifacts: Dict of {filename: raw_bytes} for images/data.
        output_dir: Destination directory (created if needed).
        notebook_title: Used to derive the output filename.

    Returns:
        Path to the written skill file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(notebook_title)
    skill_path = output_dir / f"{slug}.md"

    skill_path.write_text(markdown, encoding="utf-8")

    for fname, raw in artifacts.items():
        artifact_path = output_dir / fname
        artifact_path.write_bytes(raw)

    return skill_path


def _slugify(text: str) -> str:
    """Convert a title string to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text or "notebook"
