#!/usr/bin/env python3
"""Structural validation for open.yml (run in CI on every PR).

Checks
------
1. No duplicate (concept, arity) pairs: a concept name may be overloaded across
   arities (e.g. disjoint-union at 1 and 2), but each (name, arity) pair must be
   unique - it is the row identity the editor and the W3C list rely on.

The reader accepts both rendering shapes (the legacy `mathml:` list and the
current `notations:` list of {tex?, mathml} hashes); neither matters for the
identity checks here.

(A "no overlap with the W3C Core list" check was considered and deferred -
to be revisited with the W3C group.)

Usage: python3 scripts/validate_open.py [open.yml]
Exits non-zero listing every offender when a check fails.
"""

import sys
from collections import Counter

import yaml


def load_entries(path):
    """Yield every `intents:` entry across all concept groups."""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    for group in (doc or {}).get("concepts") or []:
        for entry in group.get("intents") or []:
            if isinstance(entry, dict) and isinstance(entry.get("concept"), str):
                yield entry


def check_duplicates(entries):
    """Return error lines for every (concept, arity) pair seen more than once."""
    counts = Counter((e["concept"], e.get("arity")) for e in entries)
    return [
        f"duplicate (concept, arity): {name!r} at arity {arity} appears {n} times"
        for (name, arity), n in sorted(counts.items())
        if n > 1
    ]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "open.yml"
    entries = list(load_entries(path))
    if not entries:
        print(f"{path}: no concept entries found - is the file shaped correctly?")
        return 1

    errors = check_duplicates(entries)
    if errors:
        print(f"{path}: {len(errors)} problem(s):")
        for line in errors:
            print(f"  - {line}")
        return 1

    print(f"{path}: OK ({len(entries)} entries, no duplicate (concept, arity) pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
