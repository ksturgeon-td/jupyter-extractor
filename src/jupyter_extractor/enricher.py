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


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

# Default model IDs per provider.  Users can override with --model.
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-4-6",
    "bedrock":   "anthropic.claude-opus-4-6-20250514-v1:0",
    "vertex":    "claude-opus-4-6@20250514",
}

PROVIDERS = list(PROVIDER_DEFAULT_MODELS.keys())


def default_model(provider: str) -> str:
    return PROVIDER_DEFAULT_MODELS.get(provider, "claude-opus-4-6")


def make_client(
    provider: str,
    *,
    api_key: str | None = None,
    aws_region: str | None = None,
    aws_profile: str | None = None,
    vertex_project: str | None = None,
    vertex_region: str | None = None,
):
    """Construct the appropriate Anthropic SDK client for the given provider.

    - anthropic: direct API (ANTHROPIC_API_KEY env var or api_key param)
    - bedrock:   AnthropicBedrock — requires `pip install 'anthropic[bedrock]'`
                 and standard AWS credentials in the environment
    - vertex:    AnthropicVertex  — requires `pip install 'anthropic[vertex]'`
                 and GCP credentials in the environment
    """
    if provider == "anthropic":
        from anthropic import Anthropic
        return Anthropic(api_key=api_key) if api_key else Anthropic()

    elif provider == "bedrock":
        try:
            from anthropic import AnthropicBedrock
        except ImportError:
            raise RuntimeError(
                "AWS Bedrock support requires: pip install 'anthropic[bedrock]'"
            )
        kwargs: dict = {}
        if aws_region:
            kwargs["aws_region"] = aws_region
        if aws_profile:
            kwargs["aws_profile"] = aws_profile
        return AnthropicBedrock(**kwargs)

    elif provider == "vertex":
        try:
            from anthropic import AnthropicVertex
        except ImportError:
            raise RuntimeError(
                "Google Vertex AI support requires: pip install 'anthropic[vertex]'"
            )
        kwargs = {}
        if vertex_project:
            kwargs["project_id"] = vertex_project
        if vertex_region:
            kwargs["region"] = vertex_region
        return AnthropicVertex(**kwargs)

    else:
        raise ValueError(f"Unknown provider {provider!r}. Choose from: {', '.join(PROVIDERS)}")


# ---------------------------------------------------------------------------
# MCP hint detection
# ---------------------------------------------------------------------------

_SQL_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|FROM|WHERE|JOIN|REPLACE\s+VIEW)\b",
    re.IGNORECASE,
)
_HTTP_RE = re.compile(r"\b(requests\.|httpx\.|urllib|fetch\()", re.IGNORECASE)
_FILE_RE = re.compile(
    r"\b(open\(|Path\(|read_csv|to_csv|read_json|to_json|read_parquet)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_sections(
    sections: list[Section],
    data: NotebookData,
    *,
    provider: str = "anthropic",
    model: str | None = None,
    api_key: str | None = None,
    aws_region: str | None = None,
    aws_profile: str | None = None,
    vertex_project: str | None = None,
    vertex_region: str | None = None,
    on_section: Callable[[Section, int, int], None] | None = None,
) -> list[EnrichedSection]:
    """Enrich a list of sections into skill definitions via the Claude API.

    Args:
        sections:       Sections from sectionize().
        data:           The source NotebookData (for title, language).
        provider:       LLM provider — "anthropic", "bedrock", or "vertex".
        model:          Model ID override (defaults to PROVIDER_DEFAULT_MODELS[provider]).
        api_key:        Anthropic API key (direct provider only).
        aws_region:     AWS region override (bedrock only).
        aws_profile:    AWS CLI profile name (bedrock only; or set AWS_PROFILE env var).
        vertex_project: GCP project ID (vertex only).
        vertex_region:  GCP region (vertex only).
        on_section:     Optional progress callback(section, index, total).

    Returns:
        List of EnrichedSection objects in the same order as input.
    """
    resolved_model = model or default_model(provider)
    client = make_client(
        provider,
        api_key=api_key,
        aws_region=aws_region,
        aws_profile=aws_profile,
        vertex_project=vertex_project,
        vertex_region=vertex_region,
    )
    use_thinking = (provider == "anthropic")

    result: list[EnrichedSection] = []
    for i, section in enumerate(sections):
        if on_section:
            on_section(section, i, len(sections))
        result.append(_enrich_one(section, data, client, resolved_model, use_thinking))

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
    use_thinking: bool,
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

    stream_kwargs: dict = dict(
        model=model,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    if use_thinking:
        stream_kwargs["thinking"] = {"type": "adaptive"}

    with client.messages.stream(**stream_kwargs) as stream:
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
