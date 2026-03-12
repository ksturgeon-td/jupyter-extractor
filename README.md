# Jupyter Extractor

Convert Jupyter notebooks (`.ipynb`) into Claude skill files.

Two modes:

- **`extract`** — single consolidated prompt template (Phase 1)
- **`skills`** — modular skill files per notebook section, AI-enriched and MCP-aware (Phase 2)

---

## Features

- Load notebooks from a **local file** or **URL** (including GitHub links)
- Converts **HTML-heavy cells** to clean markdown automatically
- Preserves **cell order** — markdown, code, and outputs interleaved as in the original notebook
- Saves **image outputs** as separate artifact files alongside the `.md`
- **GitHub blob URLs** accepted directly — no need to manually convert to raw URLs
- **Phase 2**: uses the Claude API to identify skills by heading structure, write rich skill prompts, detect MCP tool needs (SQL → database tool, HTTP → fetch, etc.), and render to your target agent format

---

## Installation

**Requirements:** Python 3.11+

```bash
# Clone the repo
git clone <repo-url>
cd Jupyter_Extractor

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install
pip install -e .
```

For Phase 2 (`skills`), set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Usage

### Phase 1 — Single consolidated template

```
jupyter-extractor extract SOURCE OUTPUT_DIR [--verbose]
```

| Argument | Description |
|---|---|
| `SOURCE` | Path to a local `.ipynb` file, or a URL |
| `OUTPUT_DIR` | Directory to write the output files into (created if it doesn't exist) |
| `--verbose` / `-v` | Print cell counts, artifact names, and other details |

**Examples:**

```bash
# Local file
jupyter-extractor extract my_notebook.ipynb ./output/

# GitHub URL (blob URL accepted directly)
jupyter-extractor extract https://github.com/owner/repo/blob/main/notebooks/analysis.ipynb ./output/

# With verbose output
jupyter-extractor extract my_notebook.ipynb ./output/ --verbose
```

---

### Phase 2 — Modular skill files

```
jupyter-extractor skills SOURCE OUTPUT_DIR [--target FORMAT] [--model MODEL] [--verbose]
```

| Argument / Option | Description |
|---|---|
| `SOURCE` | Path to a local `.ipynb` file, or a URL |
| `OUTPUT_DIR` | Directory to write the skill files into |
| `--target` / `-t` | Output format: `claude-code` (default), `claude-desktop`, or `generic` |
| `--model` / `-m` | Claude model for enrichment (default: `claude-opus-4-6`) |
| `--api-key` | Anthropic API key (or set `ANTHROPIC_API_KEY` env var) |
| `--verbose` / `-v` | Print section headings, filenames, and detected MCP tools |

**Examples:**

```bash
# Claude Code slash-command format
jupyter-extractor skills my_notebook.ipynb ./skills/ --target claude-code

# Claude Desktop project-instruction format
jupyter-extractor skills https://github.com/owner/repo/blob/main/analysis.ipynb ./skills/ \
  --target claude-desktop --verbose

# Generic portable format
jupyter-extractor skills my_notebook.ipynb ./skills/ --target generic
```

---

## Output

### Phase 1 — `extract`

Writes one file per notebook:

- **`<notebook-title>.md`** — the Claude prompt template
- **`cell_N_output_M.png`** etc. — any image outputs, saved alongside the `.md`

Template structure:

```
---
title: Notebook Title
source: <original URL or file path>
language: python
kernel: Python 3
created: 2026-02-27
---

# Notebook Title

## Overview
<Description from the first meaningful markdown cell>

## Context

**Cell 1**
<markdown content>

---

**Cell 2 [In: 1]**
```python
<code>
```

**Cell 2 — Output 0**
```
<output text>
```

...

## Prompt
> Replace this section with your prompt.
```

---

### Phase 2 — `skills`

Writes one `.md` file per detected section (identified by `#`/`##`/`###` headings and bold-only cells). Each file is an independent, Claude-ready skill.

**`claude-code` format** (for `.claude/commands/`):

```markdown
---
description: <AI-generated description>
allowed-tools: mcp__database__query, ...
---

# Skill Title

You will ...

## Reference
<relevant code and markdown from the section>
```

**`claude-desktop` format** (project instructions):

```markdown
# Skill Title

**Purpose**: <description>
**Required tools**: `mcp__database__query`

## Instructions

You will ...

## Reference
...
```

**`generic` format** (portable YAML frontmatter):

```markdown
---
title: Skill Title
description: <description>
section: <original heading>
mcp-tools:
  - mcp__database__query
---

# Skill Title

You will ...

## Reference
...
```

---

## MCP tool detection

Phase 2 scans code cells for operation patterns and passes hints to Claude, which decides whether to suggest specific MCP tools and writes skill prompts that use them directly:

| Code pattern | Detected as |
|---|---|
| `SELECT`, `FROM`, `JOIN`, etc. | database/SQL |
| `requests.`, `httpx.`, `urllib` | HTTP/fetch |
| `read_csv`, `open(`, `Path(` | filesystem |

---

## Supported cell and output types

| Type | Handled as |
|---|---|
| Markdown cell | Rendered markdown (HTML converted to markdown) |
| Code cell | Fenced code block with language label |
| `execute_result` output | Plain text code block |
| `stream` output (stdout/stderr) | Plain text code block |
| `error` output | Code block with cleaned traceback (ANSI codes stripped) |
| Image output (`image/png`, `image/jpeg`, `image/svg+xml`) | Saved as artifact file; referenced with `![]()` in the `.md` |
