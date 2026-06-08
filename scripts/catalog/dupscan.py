#!/usr/bin/env python3
"""Duplicate-suspect scan for open.yml — surfaces concepts that share a notation *signature* (the
operator/function symbols of a notation, with argument leaves removed). A shared signature is NOT
proof of duplication — most are legitimate symbol overloads that `intent` disambiguates (e.g. many
distinct concepts written `χ(·)`). But it is exactly where to LOOK for an accidental duplicate
(e.g. lie-bracket vs commutator, both `[ , ]`). Review each group; for a true duplicate, keep one
entry and add the other name to its `alias` list.

Usage: python3 scripts/catalog/dupscan.py [open.yml]
"""
import collections
import re
import sys

import yaml

LEAF = re.compile(r"<m[ion][^>]*>([^<]+)</m[ion]>")
ARGLEAF = re.compile(r"<m[ion][^>]*\barg=[^>]*>([^<]+)</m[ion]>")


def signatures(entry):
    """Notation skeletons: each notation's leaf symbols minus the argument leaves."""
    out = set()
    for n in entry.get("notations") or []:
        mm = n.get("mathml", "") or ""
        skel = LEAF.findall(mm)
        for a in ARGLEAF.findall(mm):
            if a in skel:
                skel.remove(a)
        sig = " ".join(skel).strip()
        if sig:
            out.add(sig)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "open.yml"
    ents = yaml.safe_load(open(path))["concepts"][0]["intents"]
    groups = collections.defaultdict(set)
    for e in ents:
        for s in signatures(e):
            groups[s].add(f"{e['concept']}#{e.get('arity')}")
    shared = {s: sorted(v) for s, v in groups.items() if len(v) > 1}
    print(f"{path}: {len(ents)} entries; {len(shared)} notation signatures shared by >1 concept")
    print("(review for accidental duplicates — most are legitimate symbol overloads)\n")
    for s, v in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  [{s}]  ({len(v)})  {', '.join(v)}")


if __name__ == "__main__":
    main()
