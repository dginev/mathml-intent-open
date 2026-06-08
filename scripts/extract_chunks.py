#!/usr/bin/env python3
"""Extract open.yml entries into per-chunk JSON files for the curation workflow.

- Groups entries by slug (so a concept's overloaded arities stay together for split/merge decisions).
- Chunks WITHIN each first letter (never spans letters), target ~CHUNK_SIZE entries per chunk.
- Flags Core-overlap (name in the W3C Core list).
- Writes <workdir>/chunks/chunk_NNN.json, <workdir>/manifest.json (index→letter, slugs, size),
  <workdir>/core_names.json, and copies the conventions doc in.

Usage: python3 scripts/extract_chunks.py [open.yml] [workdir]
"""
import json
import os
import shutil
import sys
from itertools import groupby

import yaml

CHUNK_SIZE = 18
HERE = os.path.dirname(os.path.abspath(__file__))


def core_names(path="/home/deyan/git/mathml-docs/_data/core.yml"):
    core = yaml.safe_load(open(path))
    names = set()
    for grp in core.get("defaultfixity", []):
        for c in grp.get("concepts", []):
            if isinstance(c, dict) and c.get("concept"):
                names.add(c["concept"])
    return names


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "open.yml"
    workdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/intent_work"
    core = core_names()

    doc = yaml.safe_load(open(src))
    entries = doc["concepts"][0]["intents"]

    # canonical order: by slug, then arity (matches the editor's byConcept)
    entries.sort(key=lambda e: (e["concept"], e.get("arity") if e.get("arity") is not None else -1))

    def to_rec(e):
        return {
            "key": f"{e['concept']}#{e.get('arity')}",
            "slug": e["concept"],
            "arity": e.get("arity"),
            "en": e.get("en"),
            "property": e.get("property"),
            "area": e.get("area"),
            "urls": e.get("urls") or [],
            "alias": e.get("alias") or [],
            "notations": e.get("notations") or [],
            "legacy_notation": {k: e[k] for k in ("notation", "notationa", "notationb") if k in e},
            "coreOverlap": e["concept"] in core,
        }

    # group by slug to keep overloaded arities together
    slug_groups = [list(g) for _, g in groupby(entries, key=lambda e: e["concept"])]

    chunks, cur, cur_letter = [], [], None
    for grp in slug_groups:
        letter = grp[0]["concept"][0].lower()
        if cur and (letter != cur_letter or len(cur) + len(grp) > CHUNK_SIZE):
            chunks.append(cur)
            cur = []
        cur_letter = letter
        cur.extend(grp)
    if cur:
        chunks.append(cur)

    cdir = os.path.join(workdir, "chunks")
    os.makedirs(cdir, exist_ok=True)
    manifest = []
    for i, ch in enumerate(chunks):
        recs = [to_rec(e) for e in ch]
        with open(os.path.join(cdir, f"chunk_{i:03d}.json"), "w") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
        manifest.append(
            {
                "index": i,
                "letter": ch[0]["concept"][0].lower(),
                "size": len(recs),
                "first": recs[0]["slug"],
                "last": recs[-1]["slug"],
            }
        )

    json.dump(manifest, open(os.path.join(workdir, "manifest.json"), "w"), indent=1)
    json.dump(sorted(core), open(os.path.join(workdir, "core_names.json"), "w"), indent=1)
    shutil.copy(os.path.join(HERE, "AGENT_CONVENTIONS.md"), os.path.join(workdir, "conventions.md"))

    # letter → [chunk indices], for selecting waves
    by_letter = {}
    for m in manifest:
        by_letter.setdefault(m["letter"], []).append(m["index"])
    json.dump(by_letter, open(os.path.join(workdir, "letters.json"), "w"), indent=1)

    print(f"{len(entries)} entries → {len(chunks)} chunks in {cdir}")
    print("letters:", {k: f"{v[0]}-{v[-1]}" for k, v in by_letter.items()})


if __name__ == "__main__":
    main()
