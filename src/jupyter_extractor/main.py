"""main.py — CLI entrypoint for jupyter-extractor."""

from __future__ import annotations

from pathlib import Path

import click

from .builder import build_template
from .loader import load_notebook
from .parser import parse_notebook
from .writer import write_output


@click.command()
@click.argument("source", metavar="SOURCE")
@click.argument("output_dir", metavar="OUTPUT_DIR", type=click.Path())
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress information.",
)
def cli(source: str, output_dir: str, verbose: bool) -> None:
    """Convert a Jupyter notebook to a Claude prompt template.

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
