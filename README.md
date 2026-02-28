# Jupyter Extractor

Convert Jupyter notebooks (`.ipynb`) into Claude prompt template files.

Extracts markdown cells, code cells, and cell outputs from a notebook and renders them as a clean, structured `.md` file you can use as a reusable Claude prompt template.

---

## Features

- Load notebooks from a **local file** or **URL** (including GitHub links)
- Converts **HTML-heavy cells** to clean markdown automatically
- Preserves **cell order** — markdown, code, and outputs interleaved as in the original notebook
- Saves **image outputs** as separate artifact files alongside the `.md`
- **GitHub blob URLs** are accepted directly — no need to manually convert to raw URLs

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

---

## Usage

```
jupyter-extractor SOURCE OUTPUT_DIR [--verbose]
```

| Argument | Description |
|---|---|
| `SOURCE` | Path to a local `.ipynb` file, or a URL |
| `OUTPUT_DIR` | Directory to write the output files into (created if it doesn't exist) |
| `--verbose` / `-v` | Print cell counts, artifact names, and other details |

### Examples

**Local file:**
```bash
jupyter-extractor my_notebook.ipynb ./output/
```

**Raw URL:**
```bash
jupyter-extractor https://example.com/path/to/notebook.ipynb ./output/
```

**GitHub URL** (blob URL accepted directly):
```bash
jupyter-extractor https://github.com/owner/repo/blob/main/notebooks/analysis.ipynb ./output/
```

**With verbose output:**
```bash
jupyter-extractor my_notebook.ipynb ./output/ --verbose
```

---

## Output

For each notebook, the tool writes:

- **`<notebook-title>.md`** — the Claude prompt template
- **`cell_N_output_M.png`** (etc.) — any image outputs, saved alongside the `.md`

### Template structure

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

---

...

## Prompt

> Replace this section with your prompt. Reference the context
> sections above to ground Claude in the notebook's content.

Using the notebook **Notebook Title**, ...
```

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

---

## Tips

- The `## Prompt` section at the bottom is a placeholder. Edit it to write your actual prompt using the notebook context above as grounding.
- For large notebooks with many outputs, the output file can get long. A `--max-output-chars` flag for truncating outputs is planned.
- Notebooks that use HTML styling (common in vendor/tutorial notebooks) are handled automatically — tags are converted to markdown equivalents.
