"""BibTeX file parser with error handling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase


@dataclass
class ParseResult:
    entries: list[dict[str, Any]]
    warnings: list[str]


def parse_bib_string(content: str, source: str = "<string>") -> ParseResult:
    """Parse a BibTeX string and return entries with warnings."""
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenise_fields = False

    try:
        db: BibDatabase = bibtexparser.loads(content, parser=parser)
    except Exception as exc:
        warnings.append(f"[{source}] Parse error: {exc}")
        # Fallback: try to extract entries manually
        entries, fallback_warnings = _fallback_parse(content, source)
        warnings.extend(fallback_warnings)
        return ParseResult(entries=entries, warnings=warnings)

    for entry in db.entries:
        entry["_source_file"] = source
        # Normalize entry_type casing
        if "ENTRYTYPE" in entry:
            entry["ENTRYTYPE"] = entry["ENTRYTYPE"].lower()
        entries.append(entry)

    if not entries and content.strip():
        warnings.append(f"[{source}] No entries found in file.")

    return ParseResult(entries=entries, warnings=warnings)


def parse_bib_file(filepath: str) -> ParseResult:
    """Parse a .bib file from disk."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, encoding="latin-1") as f:
            content = f.read()
    import os
    source = os.path.basename(filepath)
    return parse_bib_string(content, source)


def parse_multiple_files(filepaths: list[str]) -> ParseResult:
    """Parse multiple .bib files and merge results."""
    all_entries: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    for fp in filepaths:
        result = parse_bib_file(fp)
        all_entries.extend(result.entries)
        all_warnings.extend(result.warnings)
    return ParseResult(entries=all_entries, warnings=all_warnings)


def _fallback_parse(content: str, source: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Regex-based fallback parser for malformed .bib files."""
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    # Match @type{key, ... }
    pattern = re.compile(
        r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(content):
        entry_type = m.group(1).lower()
        citation_key = m.group(2).strip()
        body = m.group(3)

        if entry_type == "string":
            continue

        entry: dict[str, Any] = {
            "ENTRYTYPE": entry_type,
            "ID": citation_key,
            "_source_file": source,
        }

        # Parse fields: key = {value} or key = value
        field_pattern = re.compile(
            r"(\w+)\s*=\s*[{\"](.+?)[}\"]\s*,?\s*",
            re.DOTALL,
        )
        for fm in field_pattern.finditer(body):
            fname = fm.group(1).strip().lower()
            fval = fm.group(2).strip()
            entry[fname] = fval

        entries.append(entry)

    if not entries and content.strip():
        warnings.append(f"[{source}] Fallback parser could not extract any entries.")

    return entries, warnings
