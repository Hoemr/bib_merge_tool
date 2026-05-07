"""Duplicate detection for BibTeX entries."""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from .normalize import normalize_arxiv, normalize_author, normalize_doi, normalize_title


def _get_year(entry: dict[str, Any]) -> int | None:
    """Extract year as int, or None."""
    y = entry.get("year", "")
    if not y:
        return None
    try:
        return int(str(y).strip()[:4])
    except (ValueError, TypeError):
        return None


def find_duplicate_groups(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Find groups of potentially duplicate entries.

    Rules (applied in priority order):
    1. Same DOI (non-empty) => duplicate
    2. Same arXiv ID (non-empty) => duplicate
    3. Same normalized title + same/missing year => duplicate
    4. Title similarity >= 95 + same first author + year within 1 => likely duplicate
    5. Title similarity >= 90 + DOI/arXiv missing => needs manual review

    Returns a list of groups. Each group is a list of entries that are
    suspected duplicates of each other. Entries not in any group are unique.
    """
    n = len(entries)
    # Union-Find for grouping
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Pre-compute normalized fields
    norm_dois = [normalize_doi(e.get("doi", "")) for e in entries]
    norm_titles = [normalize_title(e.get("title", "")) for e in entries]
    norm_authors = [normalize_author(e.get("author", "")) for e in entries]
    arxiv_ids = [normalize_arxiv(e) for e in entries]
    years = [_get_year(e) for e in entries]

    # Build indexes for fast lookup
    doi_index: dict[str, int] = {}
    arxiv_index: dict[str, int] = {}

    # Rule 1: DOI match
    for i in range(n):
        doi = norm_dois[i]
        if not doi:
            continue
        if doi in doi_index:
            union(i, doi_index[doi])
        else:
            doi_index[doi] = i

    # Rule 2: arXiv ID match
    for i in range(n):
        aid = arxiv_ids[i]
        if not aid:
            continue
        if aid in arxiv_index:
            union(i, arxiv_index[aid])
        else:
            arxiv_index[aid] = i

    # Rules 3-5: pairwise comparison
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue

            ti, tj = norm_titles[i], norm_titles[j]
            if not ti or not tj:
                continue

            ai, aj = norm_authors[i], norm_authors[j]
            yi, yj = years[i], years[j]
            di, dj = norm_dois[i], norm_dois[j]
            xi, xj = arxiv_ids[i], arxiv_ids[j]

            # Rule 3: exact title match + year compatible
            if ti == tj:
                if yi is None or yj is None or yi == yj:
                    union(i, j)
                    continue

            # Defer expensive fuzz.ratio until cheaper checks pass
            sim = None

            # Rule 4: high title similarity + same author + year within 1
            if ai and aj and ai == aj:
                if yi is None or yj is None or abs(yi - yj) <= 1:
                    sim = fuzz.ratio(ti, tj)
                    if sim >= 95:
                        union(i, j)
                        continue

            # Rule 5: title similarity >= 90 + both missing DOI/arXiv
            if not di and not dj and not xi and not xj:
                if sim is None:
                    sim = fuzz.ratio(ti, tj)
                if sim >= 90:
                    union(i, j)

    # Build groups
    from collections import defaultdict
    groups_map: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups_map[find(i)].append(i)

    groups: list[list[dict[str, Any]]] = []
    for indices in groups_map.values():
        if len(indices) > 1:
            groups.append([entries[i] for i in indices])

    return groups
