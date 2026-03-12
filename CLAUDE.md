# Jupyter Extractor — Project Checkpoint

## Goal
Convert Jupyter notebooks (`.ipynb`) into Claude skill files — either as a single
consolidated prompt template (Phase 1) or as modular, AI-enriched skill files per
notebook section (Phase 2).

## Features
1. **Load** a notebook from a URL or local file path
2. **Parse** markdown cells, code cells, and cell outputs
3. **Phase 1** — Construct a single Claude prompt template `.md` with all content
4. **Phase 2** — Sectionize by headings, enrich with Claude API, render per-section skill files
5. **Write** output to a user-chosen folder

## Architecture

### Phase 1 pipeline
```
loader → parser → builder → writer
```

### Phase 2 pipeline
```
loader → parser → sectionizer → enricher (Claude API) → formatter → writer
```

### Module responsibilities
- **CLI entrypoint**: `main.py` — Click group with `extract` (Phase 1) and `skills` (Phase 2) subcommands
- **Loader** (`loader.py`): fetches/reads `.ipynb` JSON; normalizes GitHub blob URLs
- **Parser** (`parser.py`): produces `NotebookData` with `Cell` and `Output` dataclasses
- **Builder** (`builder.py`): constructs Phase 1 consolidated `.md` + artifacts dict
- **Writer** (`writer.py`): writes `.md` and binary artifacts to disk
- **Sectionizer** (`sectionizer.py`): groups cells into `Section` objects by heading (`#`/`##`/`###` and bold-only cells)
- **Enricher** (`enricher.py`): calls `claude-opus-4-6` (adaptive thinking + streaming) per section; returns `EnrichedSection` with title, slug, description, prompt, mcp_tools
- **Formatter** (`formatter.py`): renders `EnrichedSection` to `claude-code`, `claude-desktop`, or `generic` format

## Stack
- Python 3.11+
- `nbformat>=5.9` for parsing `.ipynb` files
- `httpx>=0.27` for URL fetching
- `click>=8.1` for CLI
- `html2text>=2024.2` for HTML→markdown conversion
- `anthropic>=0.40` for Phase 2 skill enrichment

## CLI
```
jupyter-extractor extract SOURCE OUTPUT_DIR [--verbose]
jupyter-extractor skills  SOURCE OUTPUT_DIR [--target claude-code|claude-desktop|generic]
                                             [--model MODEL] [--api-key KEY] [--verbose]
```

## Phase 2 output formats

### `claude-code` (default)
YAML frontmatter with `description` + `allowed-tools`, then skill prompt + Reference block.
Intended for `.claude/commands/<slug>.md`.

### `claude-desktop`
Title + Purpose + optional Required tools note + Instructions + Reference block.
Intended for Claude Desktop project instructions.

### `generic`
YAML frontmatter (title, description, section, mcp-tools) + prompt + Reference block.
Portable across agent frameworks.

## MCP tool detection
Code cells are scanned for SQL keywords, HTTP library calls, and file I/O patterns.
Hints are passed to Claude, which decides whether to include `mcp_tools` suggestions
and writes prompts that invoke tools directly rather than just generating code.

## Progress Checkpoints
- [x] Project scaffolded (pyproject.toml, folder structure)
- [x] Loader module: URL + file path loading (`src/jupyter_extractor/loader.py`)
- [x] Parser module: extract cells and metadata (`src/jupyter_extractor/parser.py`)
- [x] Builder module: construct skill `.md` (`src/jupyter_extractor/builder.py`)
- [x] Writer module: write output to chosen folder (`src/jupyter_extractor/writer.py`)
- [x] CLI wired up end-to-end (`src/jupyter_extractor/main.py`)
- [x] Install dependencies and smoke test (`tests/sample.ipynb` → `tests/output/`)
- [x] Real-world test: Teradata CSA notebook (28 markdown, 61 code cells via GitHub blob URL)
- [x] GitHub blob URL auto-conversion (`loader._normalize_url`)
- [x] HTML title extraction (`parser._infer_title`)
- [x] HTML-stripped Overview with title-dedup logic (`builder._overview`)
- [x] HTML→markdown conversion via `html2text` (`builder._html_to_md`)
- [x] Cells rendered in notebook order (markdown + code + outputs interleaved)
- [x] README.md with installation, usage, examples, and output format docs
- [x] Phase 2: Sectionizer (`sectionizer.py`) — groups cells by heading into `Section` objects
- [x] Phase 2: Enricher (`enricher.py`) — Claude API per section → `EnrichedSection`
- [x] Phase 2: Formatter (`formatter.py`) — renders to claude-code / claude-desktop / generic
- [x] Phase 2: `skills` CLI subcommand wired up in `main.py`
- [x] `anthropic>=0.40` added to dependencies

## Resolved Decisions
- Output format: Claude prompt template `.md` (Phase 1); per-section skill `.md` files (Phase 2)
- UI: CLI only
- Images: saved as separate artifact files alongside the `.md`
- HTML-heavy notebooks: converted to markdown in Overview and Context blocks
- One `.md` per notebook (Phase 1); one `.md` per section (Phase 2)
- Phase 2 uses `claude-opus-4-6` with adaptive thinking + streaming by default
- Breaking change: `extract` is now an explicit subcommand (no backwards-compat shim)

## Potential Next Steps

### 1. `--max-output-chars N` — Truncate large cell outputs (Phase 1)
Add a click option that truncates any single output block to N characters.
- Add `max_output_chars: int | None` param to `build_template()` and `_output_block()`
- Wire up in `extract` subcommand as `--max-output-chars` / `-n`

### 2. `--skip-outputs` — Omit outputs entirely (Phase 1)
Pass `skip_outputs: bool` into `build_template()`; skip the `cell.outputs` loop.

### 3. Colab URL support
The GitHub-via-Colab variant can already be converted to a raw GitHub URL.
The Drive variant requires Google Drive API or user credentials — out of scope for now.

### 4. Phase 2 batch mode — process all `.ipynb` in a directory
Walk a directory, run `skills` on each notebook, write to organised output tree.

### 5. PyPI packaging
- Add `[project.urls]` and `[project.optional-dependencies]` to `pyproject.toml`
- Write a `CHANGELOG.md` and tag a release
- `python -m build && twine upload dist/*`
