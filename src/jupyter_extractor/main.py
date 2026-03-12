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
    "--model", "-m",
    default="claude-opus-4-6",
    show_default=True,
    help="Claude model for enrichment.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (or set ANTHROPIC_API_KEY env var).",
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
    model: str,
    api_key: str | None,
    verbose: bool,
) -> None:
    """Convert a notebook into modular Claude skill files.

    \b
    SOURCE      URL (http/https) or local .ipynb file path
    OUTPUT_DIR  Directory where the skill files will be written
    """
    from .enricher import enrich_sections
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

    click.echo(f"Enriching with Claude ({model})...")

    def _progress(section, idx, total):
        click.echo(f"  [{idx + 1}/{total}] {section.heading} …")

    try:
        enriched = enrich_sections(
            sections,
            data,
            model=model,
            api_key=api_key,
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
