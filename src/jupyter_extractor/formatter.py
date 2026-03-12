"""formatter.py — render EnrichedSection objects to target skill file formats."""

from __future__ import annotations

from .builder import _html_to_md
from .enricher import EnrichedSection

Target = str  # "claude-code" | "claude-desktop" | "generic"


def format_skill(enriched: EnrichedSection, target: Target, language: str) -> str:
    """Render an EnrichedSection as a skill markdown file.

    Args:
        enriched:  The enriched section to render.
        target:    Output format — "claude-code", "claude-desktop", or "generic".
        language:  Notebook language (used for code block fences).

    Returns:
        The full file content as a string.
    """
    if target == "claude-code":
        return _claude_code(enriched, language)
    elif target == "claude-desktop":
        return _claude_desktop(enriched, language)
    else:
        return _generic(enriched, language)


# ---------------------------------------------------------------------------
# Target renderers
# ---------------------------------------------------------------------------

def _claude_code(e: EnrichedSection, language: str) -> str:
    """Claude Code slash-command format (.claude/commands/<name>.md)."""
    tools_line = f"allowed-tools: {', '.join(e.mcp_tools)}\n" if e.mcp_tools else ""
    ref = _reference_block(e, language)
    return (
        f"---\n"
        f"description: {e.description}\n"
        f"{tools_line}"
        f"---\n\n"
        f"# {e.title}\n\n"
        f"{e.prompt}\n\n"
        f"{ref}"
    )


def _claude_desktop(e: EnrichedSection, language: str) -> str:
    """Claude Desktop project-instruction format."""
    tools_note = ""
    if e.mcp_tools:
        tool_list = ", ".join(f"`{t}`" for t in e.mcp_tools)
        tools_note = f"\n**Required tools**: {tool_list}\n"
    ref = _reference_block(e, language)
    return (
        f"# {e.title}\n\n"
        f"**Purpose**: {e.description}\n"
        f"{tools_note}\n"
        f"## Instructions\n\n"
        f"{e.prompt}\n\n"
        f"{ref}"
    )


def _generic(e: EnrichedSection, language: str) -> str:
    """Generic portable format with YAML frontmatter."""
    tools_yaml = ""
    if e.mcp_tools:
        tools_yaml = "mcp-tools:\n" + "".join(f"  - {t}\n" for t in e.mcp_tools)
    ref = _reference_block(e, language)
    return (
        f"---\n"
        f"title: {e.title}\n"
        f"description: {e.description}\n"
        f"section: {e.section.heading}\n"
        f"{tools_yaml}"
        f"---\n\n"
        f"# {e.title}\n\n"
        f"{e.prompt}\n\n"
        f"{ref}"
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _reference_block(e: EnrichedSection, language: str) -> str:
    """Build a ## Reference section from the section's cells."""
    parts: list[str] = []
    for cell in e.section.cells:
        if cell.cell_type == "code" and cell.source.strip():
            parts.append(f"```{language}\n{cell.source.strip()}\n```")
        elif cell.cell_type == "markdown" and cell.source.strip():
            parts.append(_html_to_md(cell.source.strip()))
    if not parts:
        return ""
    return "## Reference\n\n" + "\n\n".join(parts) + "\n"
