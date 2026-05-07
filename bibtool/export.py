"""Export functions for BibTeX entries and reports."""

from __future__ import annotations

from typing import Any

from .merge import FIELD_ORDER


def format_entry(entry: dict[str, Any]) -> str:
    """Format a single entry as a BibTeX string."""
    entry_type = entry.get("ENTRYTYPE", "misc")
    entry_id = entry.get("ID", "unknown")

    lines = [f"@{entry_type}{{{entry_id},"]

    # Fields in preferred order
    seen = set()
    for fname in FIELD_ORDER:
        val = entry.get(fname, "")
        if val:
            lines.append(f"  {fname} = {{{val}}},")
            seen.add(fname)

    # Remaining fields (except internal ones)
    for k, v in entry.items():
        if k in seen or k in ("ENTRYTYPE", "ID", "_source_file"):
            continue
        if k.startswith("_"):
            continue
        if v:
            lines.append(f"  {k} = {{{v}}},")

    # Remove trailing comma from last field
    if lines and lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]

    lines.append("}")
    return "\n".join(lines)


def export_bib(entries: list[dict[str, Any]]) -> str:
    """Export entries as a BibTeX string."""
    parts = [format_entry(e) for e in entries]
    return "\n\n".join(parts) + "\n"


def export_duplicate_report(groups: list[list[dict[str, Any]]]) -> str:
    """Generate a markdown report of duplicate groups."""
    if not groups:
        return "# Duplicate Report\n\nNo duplicates found.\n"

    lines = [
        "# Duplicate Report",
        "",
        f"Found **{len(groups)}** duplicate group(s).",
        "",
    ]

    for i, group in enumerate(groups, 1):
        lines.append(f"## Group {i} ({len(group)} entries)")
        lines.append("")
        lines.append("| # | ID | Title | Author | Year | DOI | Source |")
        lines.append("|---|-----|-------|--------|------|-----|--------|")
        for j, entry in enumerate(group, 1):
            eid = entry.get("ID", "")
            title = entry.get("title", "")[:60]
            author = entry.get("author", "")[:40]
            year = entry.get("year", "")
            doi = entry.get("doi", "")[:40]
            source = entry.get("_source_file", "")
            lines.append(f"| {j} | {eid} | {title} | {author} | {year} | {doi} | {source} |")
        lines.append("")

    return "\n".join(lines)
