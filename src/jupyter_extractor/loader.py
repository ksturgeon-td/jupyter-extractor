"""loader.py — fetch a .ipynb notebook from a URL or local file path."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import nbformat


def load_notebook(source: str) -> nbformat.NotebookNode:
    """Load and validate a Jupyter notebook from a URL or file path.

    GitHub blob URLs (github.com/.../blob/...) are automatically converted to
    their raw.githubusercontent.com equivalents.

    Args:
        source: A URL (http/https) or a local .ipynb file path.

    Returns:
        A parsed nbformat.NotebookNode object.

    Raises:
        ValueError: If the source is not a valid URL or .ipynb file.
        httpx.HTTPError: If the URL fetch fails.
        FileNotFoundError: If the local file does not exist.
    """
    if source.startswith("http://") or source.startswith("https://"):
        return _load_from_url(_normalize_url(source))
    else:
        return _load_from_file(Path(source))


def _normalize_url(url: str) -> str:
    """Convert a GitHub blob URL to a raw content URL if needed."""
    import re
    # https://github.com/owner/repo/blob/branch/path -> raw.githubusercontent.com
    pattern = r"https://github\.com/([^/]+/[^/]+)/blob/(.+)"
    m = re.match(pattern, url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}"
    return url


def _load_from_url(url: str) -> nbformat.NotebookNode:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    raw = response.json()
    return nbformat.reads(json.dumps(raw), as_version=4)


def _load_from_file(path: Path) -> nbformat.NotebookNode:
    if not path.exists():
        raise FileNotFoundError(f"Notebook not found: {path}")
    if path.suffix != ".ipynb":
        raise ValueError(f"Expected a .ipynb file, got: {path.suffix}")
    with path.open("r", encoding="utf-8") as f:
        return nbformat.read(f, as_version=4)
