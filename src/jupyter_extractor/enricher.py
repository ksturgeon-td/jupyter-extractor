"""enricher.py — enrich Section objects into skill definitions using the Claude API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .parser import NotebookData
from .sectionizer import Section


@dataclass
class EnrichedSection:
    """A notebook section enriched with Claude-generated skill metadata."""

    section: Section
    title: str
    slug: str
    description: str
    prompt: str
    mcp_tools: list[str] = field(default_factory=list)


# --- MCP hint detection patterns ---

_SQL_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|FROM|WHERE|JOIN|REPLACE\s+VIEW)\b",
    re.IGNORECASE,
)
_HTTP_RE = re.compile(r"\b(requests\.|httpx\.|urllib|fetch\()", re.IGNORECASE)
_FILE_RE = re.compile(
    r"\b(open\(|Path\(|read_csv|to_csv|read_json|to_json|read_parquet)\b",
    re.IGNORECASE,
)


def enrich_sections(
    sections: list[Section],
    data: NotebookData,
    *,
    model: str = "claude-opus-4-6",
    api_key: str | None = None,
    on_section: Callable[[Section, int, int], None] | None = None,
) -> list[EnrichedSection]:
    """Enrich a list of sections into skill definitions via the Claude API.

    Args:
        sections:    Sections from sectionize().
        data:        The source NotebookData (for title, language).
        model:       Claude model to use for enrichment.
        api_key:     Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        on_section:  Optional progress callback(section, index, total).

    Returns:
        List of EnrichedSection objects in the same order as input.
    """
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key) if api_key else Anthropic()

    result: list[EnrichedSection] = []
    for i, section in enumerate(sections):
        if on_section:
            on_section(section, i, len(sections))
        result.append(_enrich_one(section, data, client, model))

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are a technical writer creating reusable Claude skill files from Jupyter "
    "notebook sections. Analyse the section content and produce structured skill "
    "metadata. Respond ONLY with a valid JSON object — no markdown fences, "
    "no preamble, no trailing commentary."
)

_USER_TMPL = """\
Create a Claude skill definition for this notebook section.

Notebook: {title}
Language: {language}
Section heading: {heading}{hints_note}

Section content:
{content}

Return a JSON object with exactly these fields:
- title: clean skill name (3–6 words, Title Case)
- slug: kebab-case filename, no extension, max 50 chars
- description: 1–2 sentence description of what this skill does
- prompt: detailed second-person instruction prompt for Claude ("You will...").
  If the section contains SQL or other executable operations, write the prompt
  to invoke MCP tools directly rather than merely generating code.
- mcp_tools: list of MCP tool name suggestions (format "mcp__<server>__<tool>",
  e.g. "mcp__database__query"). Return an empty list if no external tools are needed.\
"""


def _enrich_one(
    section: Section,
    data: NotebookData,
    client,
    model: str,
) -> EnrichedSection:
    hints = _detect_mcp_hints(section)
    hints_note = (
        f"\nDetected operation types: {', '.join(hints)}" if hints else ""
    )

    user_msg = _USER_TMPL.format(
        title=data.title,
        language=data.language,
        heading=section.heading,
        hints_note=hints_note,
        content=_render_section(section, data.language),
    )

    with client.messages.stream(
        model=model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        final = stream.get_final_message()

    raw = next(b.text for b in final.content if b.type == "text")
    parsed = _parse_json(raw)

    return EnrichedSection(
        section=section,
        title=parsed.get("title", section.heading),
        slug=parsed.get("slug") or _slugify(section.heading),
        description=parsed.get("description", ""),
        prompt=parsed.get("prompt", ""),
        mcp_tools=parsed.get("mcp_tools", []),
    )


def _render_section(section: Section, language: str) -> str:
    parts: list[str] = []
    for cell in section.cells:
        if cell.cell_type == "markdown" and cell.source.strip():
            parts.append(cell.source.strip())
        elif cell.cell_type == "code" and cell.source.strip():
            parts.append(f"```{language}\n{cell.source.strip()}\n```")
            for out in cell.outputs:
                if out.kind == "text":
                    body = out.content[:500]
                    suffix = " …[truncated]" if len(out.content) > 500 else ""
                    parts.append(f"```\n{body}{suffix}\n```")
    return "\n\n".join(parts)


def _detect_mcp_hints(section: Section) -> list[str]:
    code = "\n".join(c.source for c in section.cells if c.cell_type == "code")
    hints: list[str] = []
    if _SQL_RE.search(code):
        hints.append("database/SQL")
    if _HTTP_RE.search(code):
        hints.append("HTTP/fetch")
    if _FILE_RE.search(code):
        hints.append("filesystem")
    return hints


def _parse_json(raw: str) -> dict:
    """Strip optional markdown fences and parse JSON."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")[:50]
