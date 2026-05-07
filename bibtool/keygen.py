"""Citation key generation and conflict resolution."""

from __future__ import annotations

import re
from typing import Any

_STOP_WORDS = frozenset({
    "a", "an", "the", "on", "in", "of", "for", "to", "and", "or",
    "with", "by", "from", "at", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can",
    "that", "which", "who", "whom", "this", "these", "those",
    "it", "its", "we", "our", "you", "your", "they", "their",
})


def _extract_first_author_last_name(author: str) -> str:
    """Extract the last name of the first author."""
    if not author:
        return ""
    # Split on "and" to get first author
    first = author.split(" and ")[0].strip()
    # "Last, First" format
    if "," in first:
        last = first.split(",")[0].strip()
    else:
        parts = first.split()
        last = parts[-1] if parts else ""
    # Clean
    last = re.sub(r"[^a-zA-Z]", "", last)
    return last.lower()


def _extract_first_meaningful_word(title: str) -> str:
    """Extract the first 'meaningful' word from a title.

    Skips common stop words and short words.
    """
    if not title:
        return ""
    clean = re.sub(r"[^a-zA-Z\s]", "", title.lower())
    words = clean.split()
    for w in words:
        if w not in _STOP_WORDS and len(w) >= 2:
            return w
    # Fallback: return first word
    return words[0] if words else ""


def generate_key(entry: dict[str, Any]) -> str:
    """Generate a citation key: firstAuthorLastName + year + firstMeaningfulTitleWord."""
    author = entry.get("author", "")
    title = entry.get("title", "")
    year = entry.get("year", "")

    last_name = _extract_first_author_last_name(author)
    word = _extract_first_meaningful_word(title)

    year_str = ""
    if year:
        try:
            year_str = str(int(str(year)[:4]))
        except (ValueError, TypeError):
            year_str = ""

    parts = [p for p in (last_name, year_str, word) if p]
    if not parts:
        return "unknown"
    return "".join(parts)


def resolve_key_conflicts(
    entries: list[dict[str, Any]],
    preserve_existing: bool = True,
) -> list[dict[str, Any]]:
    """Assign citation keys, resolving conflicts by appending a/b/c/....

    Args:
        entries: list of entries (modified in-place for ID field)
        preserve_existing: if True, try to keep original keys

    Returns:
        the same list with updated ID fields
    """
    seen: dict[str, int] = {}

    for entry in entries:
        existing_key = entry.get("ID", "")

        if preserve_existing and existing_key:
            key = existing_key
        else:
            key = generate_key(entry)

        if key in seen:
            seen[key] += 1
            suffix = chr(ord("a") + seen[key] - 1)
            # Find a unique key
            attempt = key + suffix
            while attempt in seen:
                seen[key] += 1
                suffix = chr(ord("a") + seen[key] - 1)
                attempt = key + suffix
            seen[attempt] = 0
            entry["ID"] = attempt
        else:
            seen[key] = 0
            entry["ID"] = key

    return entries
