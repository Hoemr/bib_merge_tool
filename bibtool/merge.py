"""Merge strategies for duplicate BibTeX entries."""

from __future__ import annotations

from typing import Any


# Fields to strip by default
DIRTY_FIELDS = {
    "abstract",
    "keywords",
    "file",
    "timestamp",
    "owner",
    "mendeley-groups",
    "annote",
}
DIRTY_PREFIXES = ("zotero-", "bdsk-")

# Field order for output
FIELD_ORDER = [
    "author",
    "title",
    "journal",
    "booktitle",
    "year",
    "volume",
    "number",
    "pages",
    "publisher",
    "doi",
    "url",
    "eprint",
    "archiveprefix",
    "primaryclass",
    "note",
]


def _is_dirty(field_name: str) -> bool:
    """Check if a field should be stripped by default."""
    fn = field_name.lower()
    if fn in DIRTY_FIELDS:
        return True
    for prefix in DIRTY_PREFIXES:
        if fn.startswith(prefix):
            return True
    return False


def _pick_best(existing: str | None, candidate: str | None) -> str | None:
    """Pick the better value: prefer non-empty, then longer."""
    if not existing:
        return candidate
    if not candidate:
        return existing
    return candidate if len(candidate) > len(existing) else existing


def auto_merge_group(
    group: list[dict[str, Any]],
    keep_extras: bool = False,
) -> dict[str, Any]:
    """Auto-merge a group of duplicate entries into one.

    Field priority:
    - doi: non-empty normalized DOI
    - author: longest non-empty
    - title: longest (preserves LaTeX braces)
    - journal/booktitle: prefer journal, then booktitle
    - year, volume, number, pages, publisher: prefer non-empty
    - url: keep if present
    - eprint/archivePrefix/primaryClass: prefer arXiv entries
    """
    if len(group) == 1:
        result = _clean_entry(dict(group[0]), keep_extras)
        return result

    merged: dict[str, Any] = {}

    # Start with the first entry as base
    base = group[0]
    for k, v in base.items():
        if not _is_dirty(k) or keep_extras:
            merged[k] = v

    # Merge remaining entries
    for entry in group[1:]:
        for k, v in entry.items():
            if not v:
                continue
            lk = k.lower()

            # Skip dirty fields unless keep_extras
            if _is_dirty(lk) and not keep_extras:
                continue

            if lk == "doi":
                existing = merged.get("doi", "")
                if not existing:
                    merged["doi"] = v
            elif lk == "title":
                merged["title"] = _pick_best(merged.get("title"), v)
            elif lk == "author":
                merged["author"] = _pick_best(merged.get("author"), v)
            elif lk == "journal":
                # Journal takes priority over booktitle
                merged["journal"] = v
                merged.pop("booktitle", None)
            elif lk == "booktitle":
                # Only use booktitle if journal is not present
                if not merged.get("journal"):
                    merged["booktitle"] = v
            elif lk in ("year", "volume", "number", "pages", "publisher"):
                if not merged.get(lk):
                    merged[lk] = v
            elif lk == "url":
                if not merged.get("url"):
                    merged["url"] = v
            elif lk in ("eprint", "archiveprefix", "primaryclass"):
                # Prefer arXiv-related fields
                if not merged.get(lk):
                    merged[lk] = v
            elif lk not in ("entrytype", "id", "_source_file"):
                # Generic: prefer longer
                if lk not in merged or (v and len(str(v)) > len(str(merged.get(lk, "")))):
                    merged[lk] = v

    # Ensure ENTRYTYPE and ID are set
    merged["ENTRYTYPE"] = base.get("ENTRYTYPE", "article")
    merged["ID"] = base.get("ID", "unknown")

    # Collect source files
    sources = list({e.get("_source_file", "") for e in group if e.get("_source_file")})
    if sources:
        merged["_source_file"] = ", ".join(sources)

    return merged


def manual_merge(
    group: list[dict[str, Any]],
    base_index: int,
    field_choices: dict[str, int],
    keep_extras: bool = False,
) -> dict[str, Any]:
    """Manually merge entries with user-specified field choices.

    Args:
        group: list of duplicate entries
        base_index: index of the base entry (for ENTRYTYPE, ID)
        field_choices: mapping field_name -> index in group to take value from
        keep_extras: whether to keep dirty fields
    """
    base = group[base_index]
    merged: dict[str, Any] = {
        "ENTRYTYPE": base.get("ENTRYTYPE", "article"),
        "ID": base.get("ID", "unknown"),
    }

    for fname, idx in field_choices.items():
        if 0 <= idx < len(group):
            val = group[idx].get(fname, "")
            if val:
                if _is_dirty(fname) and not keep_extras:
                    continue
                merged[fname] = val

    # Fill remaining from base
    for k, v in base.items():
        if k not in merged and v:
            if _is_dirty(k) and not keep_extras:
                continue
            merged[k] = v

    sources = list({e.get("_source_file", "") for e in group if e.get("_source_file")})
    if sources:
        merged["_source_file"] = ", ".join(sources)

    return merged


def _clean_entry(entry: dict[str, Any], keep_extras: bool = False) -> dict[str, Any]:
    """Remove dirty fields from an entry."""
    if keep_extras:
        return entry
    return {k: v for k, v in entry.items() if not _is_dirty(k) or k in ("ENTRYTYPE", "ID", "_source_file")}
