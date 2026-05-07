"""Command-line interface for bibtool."""

from __future__ import annotations

import argparse
import glob
import sys

from .deduplicate import find_duplicate_groups
from .export import export_bib, export_duplicate_report
from .keygen import resolve_key_conflicts
from .merge import auto_merge_group
from .parser import parse_multiple_files


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="bibtool",
        description="BibTeX merge & dedup tool",
    )
    ap.add_argument(
        "--input", "-i",
        nargs="+",
        required=True,
        help="Input .bib files (supports glob patterns)",
    )
    ap.add_argument(
        "--output", "-o",
        default="master.bib",
        help="Output .bib file (default: master.bib)",
    )
    ap.add_argument(
        "--auto-merge",
        action="store_true",
        help="Automatically merge high-confidence duplicates",
    )
    ap.add_argument(
        "--keep-extras",
        action="store_true",
        help="Keep abstract/keywords and other extra fields",
    )
    ap.add_argument(
        "--report",
        default="duplicate_report.md",
        help="Duplicate report file (default: duplicate_report.md)",
    )
    args = ap.parse_args(argv)

    # Expand globs
    files: list[str] = []
    for pattern in args.input:
        expanded = glob.glob(pattern)
        if expanded:
            files.extend(expanded)
        else:
            files.append(pattern)

    if not files:
        print("Error: no input files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {len(files)} file(s)...")
    result = parse_multiple_files(files)

    for w in result.warnings:
        print(f"  WARNING: {w}")

    entries = result.entries
    print(f"Parsed {len(entries)} entries total.")

    # Detect duplicates
    groups = find_duplicate_groups(entries)
    print(f"Found {len(groups)} duplicate group(s).")

    # Collect entries in duplicate groups
    grouped_ids: set[int] = set()
    for g in groups:
        for e in g:
            grouped_ids.add(id(e))

    unique_entries = [e for e in entries if id(e) not in grouped_ids]

    # Merge or keep duplicates
    unresolved_groups: list[list[dict]] = []
    merged_entries: list[dict] = []

    if args.auto_merge:
        for g in groups:
            merged = auto_merge_group(g, keep_extras=args.keep_extras)
            merged_entries.append(merged)
        print(f"Auto-merged {len(groups)} group(s).")
    else:
        # Without --auto-merge, just keep all entries
        unresolved_groups = groups
        for g in groups:
            merged_entries.extend(g)

    all_final = unique_entries + merged_entries

    # Resolve key conflicts
    resolve_key_conflicts(all_final, preserve_existing=True)

    # Write output
    bib_content = export_bib(all_final)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(bib_content)
    print(f"Wrote {len(all_final)} entries to {args.output}")

    # Write report
    if groups:
        report = export_duplicate_report(groups)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Wrote duplicate report to {args.report}")

    # Write unresolved if any
    if unresolved_groups:
        unresolved_entries = []
        for g in unresolved_groups:
            unresolved_entries.extend(g)
        unresolved_bib = export_bib(unresolved_entries)
        with open("unresolved_duplicates.bib", "w", encoding="utf-8") as f:
            f.write(unresolved_bib)
        print(f"Wrote unresolved duplicates to unresolved_duplicates.bib")


if __name__ == "__main__":
    main()
