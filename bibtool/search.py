"""Search functionality for BibTeX entries."""

from __future__ import annotations

from typing import Any


def search_entries(
    entries: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Search entries by multiple keywords (AND logic, case-insensitive).

    Search fields: ID, title, author, year, doi, journal, booktitle, eprint, url.
    Keywords are space-separated and all must match (AND).
    """
    if not query.strip():
        return list(entries)

    keywords = query.lower().split()
    if not keywords:
        return list(entries)

    search_fields = [
        "ID", "title", "author", "year", "doi",
        "journal", "booktitle", "eprint", "url",
    ]

    results: list[dict[str, Any]] = []
    for entry in entries:
        # Build a searchable text blob from all search fields
        parts = []
        for f in search_fields:
            val = entry.get(f, "")
            if val:
                parts.append(str(val).lower())
        blob = " ".join(parts)

        if all(kw in blob for kw in keywords):
            results.append(entry)

    return results
