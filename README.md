# BibTeX Merge Tool

A lightweight desktop tool for merging, deduplicating, and searching multiple `.bib` files. Built with Python + tkinter, packaged as a standalone `.exe`.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the GUI
python gui.py
```

## Build Standalone .exe

```bash
python build.py
# Output: dist/BibMergeTool.exe
```

Or directly:

```bash
pyinstaller --onefile --windowed --name BibMergeTool --add-data "bibtool;bibtool" gui.py
```

## CLI Usage

```bash
# Auto-merge all duplicates
python -m bibtool.cli --input raw/*.bib --output master.bib --auto-merge

# Without --auto-merge, keeps all entries and generates a report
python -m bibtool.cli --input raw/*.bib --output master.bib

# Keep abstract/keywords fields
python -m bibtool.cli --input raw/*.bib --output master.bib --auto-merge --keep-extras
```

## Features

- **Import** multiple `.bib` files via file dialog
- **Auto-detect** duplicate entries using DOI, arXiv ID, title similarity, and author matching
- **Manual review** of duplicate groups with per-field merge control
- **Auto-merge** mode for quick deduplication
- **Search** across all entries with multi-keyword AND logic
- **Export** clean `master.bib`, search results, and duplicate reports

## Duplicate Detection Rules

Rules are applied in priority order:

| Priority | Rule | Confidence |
|----------|------|------------|
| 1 | Same DOI (non-empty) | High |
| 2 | Same arXiv ID (non-empty) | High |
| 3 | Exact normalized title + same/missing year | High |
| 4 | Title similarity >= 95% + same first author + year within 1 | High |
| 5 | Title similarity >= 90% + both DOI and arXiv missing | Low (needs manual review) |

### Normalization Details

- **Title**: lowercase, remove LaTeX braces, remove punctuation, collapse whitespace
- **DOI**: lowercase, strip `https://doi.org/` and `doi:` prefixes
- **Author**: extract first author's last name, lowercase
- **arXiv ID**: extract from `eprint`, `url`, or `note` fields

## Merge Rules

### Auto-Merge Field Priority

| Field | Rule |
|-------|------|
| doi | First non-empty |
| author | Longest non-empty |
| title | Longest (preserves LaTeX braces) |
| journal/booktitle | Journal preferred over booktitle |
| year, volume, number, pages, publisher | First non-empty |
| eprint, archivePrefix, primaryClass | First non-empty |

### Dirty Fields (stripped by default)

`abstract`, `keywords`, `file`, `timestamp`, `owner`, `mendeley-groups`, `annote`, `zotero-*`, `bdsk-*`

Enable "Keep abstract/keywords" checkbox to preserve these.

## Citation Key Generation

Default pattern: `{firstAuthorLastName}{year}{firstMeaningfulTitleWord}`

Examples:
- `rafailov2023direct`
- `song2021score`
- `vaswani2017attention`

Conflicts are resolved by appending `a`, `b`, `c`, etc.

## Export Formats

| File | Description |
|------|-------------|
| `master.bib` | Final deduplicated bibliography |
| `selected.bib` | Current search results |
| `duplicate_report.md` | Markdown report of all duplicate groups |
| `unresolved_duplicates.bib` | Entries from skipped duplicate groups |

## Project Structure

```
bib_merge_tool/
├── gui.py                  # Desktop GUI (tkinter)
├── build.py                # PyInstaller build script
├── requirements.txt
├── README.md
├── bibtool/
│   ├── __init__.py
│   ├── parser.py           # BibTeX parsing with fallback
│   ├── normalize.py        # Field normalization
│   ├── deduplicate.py      # Duplicate detection logic
│   ├── merge.py            # Merge strategies
│   ├── keygen.py           # Citation key generation
│   ├── search.py           # Search functionality
│   ├── export.py           # BibTeX & report export
│   └── cli.py              # Command-line interface
└── tests/
    ├── test_normalize.py
    ├── test_deduplicate.py
    ├── test_merge.py
    └── sample_data/
        ├── refs1.bib
        └── refs2.bib
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Requirements

- Python 3.9+
- No external services or databases required
- All processing is local
