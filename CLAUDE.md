# Jupyter Extractor — Project Checkpoint

## Goal
Convert Jupyter notebooks (`.ipynb`) into Claude skill files with associated artifacts.

## Features
1. **Load** a notebook from a URL or local file upload
2. **Parse** markdown cells, code cells, and cell outputs
3. **Construct** a Claude skill file (`.md`) with extracted data and metadata
4. **Write** the skill file + artifacts to a user-chosen output folder

## Architecture Plan
- **CLI entrypoint**: `main.py` — accepts a URL or file path + output folder
- **Loader** (`loader.py`): fetches/reads `.ipynb` JSON
- **Parser** (`parser.py`): extracts cells (markdown, code, output) and notebook metadata
- **Builder** (`builder.py`): constructs the Claude skill `.md` format from parsed data
- **Writer** (`writer.py`): writes the skill file and any artifacts (images, data) to disk
- CLI only (no web UI)

## Output Format — Claude Prompt Template
A standalone `.md` file structured as a reusable prompt. Notebook content is embedded
as labeled context blocks. Format:

```
---
title: <notebook title>
source: <url or filename>
created: <date>
---

# <Notebook Title>

## Overview
<first markdown cell or notebook description>

## Context

### Markdown
<all markdown cells, in order>

### Code
<all code cells with language label>

### Outputs
<text/image outputs per cell>

## Prompt
<placeholder prompt for the user to fill in>
```

## Stack
- Python 3.11+
- `nbformat` for parsing `.ipynb` files
- `httpx` for URL fetching
- `click` for CLI

## Progress Checkpoints
- [x] Project scaffolded (pyproject.toml, folder structure)
- [x] Loader module: URL + file path loading  (`src/jupyter_extractor/loader.py`)
- [x] Parser module: extract cells and metadata  (`src/jupyter_extractor/parser.py`)
- [x] Builder module: construct skill `.md`  (`src/jupyter_extractor/builder.py`)
- [x] Writer module: write output to chosen folder  (`src/jupyter_extractor/writer.py`)
- [x] CLI wired up end-to-end  (`src/jupyter_extractor/main.py`)
- [x] Install dependencies and smoke test (`tests/sample.ipynb` → `tests/output/`)
- [x] Real-world test: Teradata CSA notebook (28 markdown, 61 code cells via GitHub blob URL)
- [x] GitHub blob URL auto-conversion (`loader._normalize_url`)
- [x] HTML title extraction (large font-size / h1/h2 fallbacks in `parser._infer_title`)
- [x] HTML-stripped Overview with title-dedup logic (`builder._overview`)
- [x] HTML→markdown conversion in Context blocks via `html2text` (`builder._html_to_md`)
- [x] Cells rendered in notebook order (markdown + code + outputs interleaved)
- [x] README.md with installation, usage, examples, and output format docs

## Resolved Decisions
- Output format: Claude prompt template `.md`
- UI: CLI only
- Images: saved as separate artifact files alongside the `.md`
- HTML-heavy notebooks: converted to markdown in both Overview and Context blocks
- One `.md` per notebook; cells in original order

## Potential Next Steps

### 1. `--max-output-chars N` — Truncate large cell outputs
Large notebooks (e.g. with DataFrame reprs or long logs) can produce very long output
sections. Add a click option that truncates any single output block to N characters
and appends a `… [truncated]` note.
- Add `max_output_chars: int | None` param to `build_template()` and `_output_block()`
- Wire up in `main.py` as `--max-output-chars` / `-n`

### 2. `--skip-outputs` — Omit the Outputs section entirely
For code-focused use cases where outputs are noise. A flag that skips all output
rendering and artifact saving.
- Pass `skip_outputs: bool` into `build_template()`; skip the `cell.outputs` loop

### 3. Colab URL support
Google Colab notebooks are stored in Google Drive. Colab URLs look like:
  `https://colab.research.google.com/drive/<file-id>`
or open via GitHub:
  `https://colab.research.google.com/github/<owner>/<repo>/blob/<branch>/<path>`
The GitHub variant can be converted to a raw GitHub URL (already supported).
The Drive variant requires the Google Drive export API or user-supplied credentials —
flag as out-of-scope unless auth solution is clear.

### 4. PyPI packaging
- Add `[project.urls]` and `[project.optional-dependencies]` to `pyproject.toml`
- Write a `CHANGELOG.md` and tag a `v0.1.0` release
- `python -m build && twine upload dist/*`
