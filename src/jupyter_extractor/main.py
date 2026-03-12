"""main.py — CLI entrypoint for jupyter-extractor."""

from __future__ import annotations

from pathlib import Path

import click

from .builder import build_template
from .loader import load_notebook
from .parser import parse_notebook
from .writer import write_output


@click.group()
def cli() -> None:
    """Convert Jupyter notebooks into Claude skill files."""


# ---------------------------------------------------------------------------
# Phase 1: extract — single consolidated prompt template
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("source", metavar="SOURCE")
@click.argument("output_dir", metavar="OUTPUT_DIR", type=click.Path())
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress information.",
)
def extract(source: str, output_dir: str, verbose: bool) -> None:
    """Convert a notebook to a single Claude prompt template.

    \b
    SOURCE      URL (http/https) or local .ipynb file path
    OUTPUT_DIR  Directory where the skill file and artifacts will be written
    """
    out_path = Path(output_dir)

    click.echo(f"Loading notebook from: {source}")
    try:
        nb = load_notebook(source)
    except Exception as e:
        raise click.ClickException(f"Failed to load notebook: {e}") from e

    if verbose:
        click.echo(f"  Notebook format version: {nb.nbformat}.{nb.nbformat_minor}")

    click.echo("Parsing cells...")
    data = parse_notebook(nb, source)

    if verbose:
        n_markdown = sum(1 for c in data.cells if c.cell_type == "markdown")
        n_code = sum(1 for c in data.cells if c.cell_type == "code")
        click.echo(f"  Title    : {data.title}")
        click.echo(f"  Language : {data.language} ({data.kernel_name})")
        click.echo(f"  Cells    : {n_markdown} markdown, {n_code} code")

    click.echo("Building template...")
    markdown, artifacts = build_template(data)

    if verbose and artifacts:
        click.echo(f"  Artifacts: {', '.join(artifacts.keys())}")

    click.echo(f"Writing output to: {out_path}/")
    skill_path = write_output(markdown, artifacts, out_path, data.title)

    click.echo(click.style(f"Done. Skill file written to: {skill_path}", fg="green"))


# ---------------------------------------------------------------------------
# Phase 2: skills — modular skill files via Claude API
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("source", metavar="SOURCE")
@click.argument("output_dir", metavar="OUTPUT_DIR", type=click.Path())
@click.option(
    "--target", "-t",
    type=click.Choice(["claude-code", "claude-desktop", "generic"]),
    default="claude-code",
    show_default=True,
    help="Output format for skill files.",
)
@click.option(
    "--provider", "-p",
    type=click.Choice(["anthropic", "bedrock", "vertex"]),
    default="anthropic",
    show_default=True,
    help="LLM provider for enrichment.",
)
@click.option(
    "--model", "-m",
    default=None,
    help=(
        "Model ID override. Defaults per provider: "
        "anthropic=claude-opus-4-6, "
        "bedrock=anthropic.claude-opus-4-6-20250514-v1:0, "
        "vertex=claude-opus-4-6@20250514."
    ),
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key — direct provider only (or set ANTHROPIC_API_KEY env var).",
)
@click.option(
    "--aws-region",
    envvar="AWS_DEFAULT_REGION",
    default=None,
    help="AWS region — bedrock only (or set AWS_DEFAULT_REGION env var).",
)
@click.option(
    "--aws-profile",
    envvar="AWS_PROFILE",
    default=None,
    help="AWS CLI profile name — bedrock only (or set AWS_PROFILE env var).",
)
@click.option(
    "--vertex-project",
    envvar="GOOGLE_CLOUD_PROJECT",
    default=None,
    help="GCP project ID — vertex provider only (or set GOOGLE_CLOUD_PROJECT env var).",
)
@click.option(
    "--vertex-region",
    envvar="GOOGLE_CLOUD_REGION",
    default=None,
    help="GCP region — vertex provider only (or set GOOGLE_CLOUD_REGION env var).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress information.",
)
def skills(
    source: str,
    output_dir: str,
    target: str,
    provider: str,
    model: str | None,
    api_key: str | None,
    aws_region: str | None,
    aws_profile: str | None,
    vertex_project: str | None,
    vertex_region: str | None,
    verbose: bool,
) -> None:
    """Convert a notebook into modular Claude skill files.

    \b
    SOURCE      URL (http/https) or local .ipynb file path
    OUTPUT_DIR  Directory where the skill files will be written

    Provider setup:
      anthropic  ANTHROPIC_API_KEY env var (or --api-key)
      bedrock    AWS credentials in environment + AWS_DEFAULT_REGION;
                 requires: pip install 'anthropic[bedrock]'
      vertex     GCP credentials in environment + GOOGLE_CLOUD_PROJECT;
                 requires: pip install 'anthropic[vertex]'
    """
    from .enricher import enrich_sections, default_model
    from .formatter import format_skill
    from .sectionizer import sectionize

    out_path = Path(output_dir)

    click.echo(f"Loading notebook from: {source}")
    try:
        nb = load_notebook(source)
    except Exception as e:
        raise click.ClickException(f"Failed to load notebook: {e}") from e

    click.echo("Parsing cells...")
    data = parse_notebook(nb, source)

    if verbose:
        n_markdown = sum(1 for c in data.cells if c.cell_type == "markdown")
        n_code = sum(1 for c in data.cells if c.cell_type == "code")
        click.echo(f"  Title    : {data.title}")
        click.echo(f"  Language : {data.language} ({data.kernel_name})")
        click.echo(f"  Cells    : {n_markdown} markdown, {n_code} code")

    click.echo("Identifying sections...")
    sections = sectionize(data)
    headings = ", ".join(s.heading for s in sections)
    click.echo(f"  Found {len(sections)} section(s): {headings}")

    resolved_model = model or default_model(provider)
    click.echo(f"Enriching with Claude ({provider} / {resolved_model})...")

    def _progress(section, idx, total):
        click.echo(f"  [{idx + 1}/{total}] {section.heading} …")

    try:
        enriched = enrich_sections(
            sections,
            data,
            provider=provider,
            model=model,
            api_key=api_key,
            aws_region=aws_region,
            aws_profile=aws_profile,
            vertex_project=vertex_project,
            vertex_region=vertex_region,
            on_section=_progress,
        )
    except Exception as e:
        raise click.ClickException(f"Claude API error: {e}") from e

    out_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    click.echo(f"Writing {target} skill files to: {out_path}/")
    for es in enriched:
        content = format_skill(es, target, data.language)
        skill_file = out_path / f"{es.slug}.md"
        skill_file.write_text(content, encoding="utf-8")
        written.append(skill_file)
        if verbose:
            tools_note = f" [{', '.join(es.mcp_tools)}]" if es.mcp_tools else ""
            click.echo(f"  {skill_file.name} — {es.title}{tools_note}")

    click.echo(
        click.style(
            f"Done. {len(written)} skill file(s) written to: {out_path}/",
            fg="green",
        )
    )
