"""Normalization functions for BibTeX fields used in duplicate detection."""

from __future__ import annotations

import re
from typing import Any


def normalize_title(title: str | None) -> str:
    """Normalize a title for comparison.

    - lowercase
    - remove LaTeX braces
    - remove punctuation
    - collapse whitespace
    - strip
    """
    if not title:
        return ""
    s = title.lower()
    # Remove LaTeX braces but keep content
    s = s.replace("{", "").replace("}", "")
    # Remove punctuation
    s = re.sub(r"[^\w\s]", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_doi(doi: str | None) -> str:
    """Normalize a DOI for comparison.

    - lowercase
    - strip URL prefixes
    - strip
    """
    if not doi:
        return ""
    s = doi.lower().strip()
    # Remove common prefixes
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "doi: "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()


def normalize_author(author: str | None) -> str:
    """Extract and normalize the first author's last name.

    - lowercase
    - remove special characters
    """
    if not author:
        return ""
    s = author.strip()
    # Handle "Last, First" format — take the part before the first comma
    if "," in s:
        s = s.split(",")[0]
    else:
        # "First Last" format — take the last word
        parts = s.split()
        if parts:
            s = parts[-1]
        else:
            s = ""
    # Handle "and" separator — just take the first author
    s = s.split(" and ")[0].strip()
    # Remove braces and special chars
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"[^\w\s]", "", s)
    return s.lower().strip()


def normalize_arxiv(entry: dict[str, Any]) -> str:
    """Try to extract an arXiv ID from an entry.

    Looks in eprint, url, note fields.
    Returns empty string if not found.
    """
    arxiv_pattern = re.compile(
        r"(?:arXiv:|arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)",
        re.IGNORECASE,
    )

    # Check eprint field first
    for field_name in ("eprint", "url", "note", "doi"):
        val = entry.get(field_name, "")
        if not val:
            continue
        m = arxiv_pattern.search(val)
        if m:
            return m.group(1).lower()

    # Also check for old-style arXiv IDs (e.g., hep-th/0601001)
    old_pattern = re.compile(r"((?:[a-z-]+(?:\.[A-Z]+)?)/\d{7}(?:v\d+)?)", re.IGNORECASE)
    for field_name in ("eprint", "url", "note"):
        val = entry.get(field_name, "")
        if not val:
            continue
        m = old_pattern.search(val)
        if m:
            return m.group(1).lower()

    return ""
