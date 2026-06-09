#!/usr/bin/env python3
"""Combine curate-workflow results into an apply_patches patch file.

Input: a JSON file holding the workflow's return value — an array of
  { "index": int, "edits": [{ "key", "action", ... }], "adds": [ {...} ], "flags": [str] }
(or a bare concatenation of such records). Produces:
  - <out>.json           — { "edits": { "slug#arity": <patch> }, "adds": [ ... ] }
  - prints a flags + action summary to stderr.

Usage: python3 scripts/combine_patches.py <results.json> <out.json>
"""
import json
import sys
from collections import Counter

EDIT_FIELDS = ("slug", "arity", "en", "property", "area", "links", "alias", "notations")


def main():
    results_path, out_path = sys.argv[1], sys.argv[2]
    data = json.load(open(results_path))
    if isinstance(data, dict):
        data = [data]

    edits = {}
    adds = []
    flags = []
    actions = Counter()
    seen = set()

    for chunk in data:
        idx = chunk.get("index", "?")
        for rec in chunk.get("edits") or []:
            key = rec.get("key")
            action = rec.get("action", "edit")
            actions[action] += 1
            if not key:
                flags.append(f"[chunk {idx}] edit record with no key: {rec}")
                continue
            if key in seen:
                flags.append(f"[chunk {idx}] DUPLICATE key {key} (overwriting)")
            seen.add(key)
            if action == "keep":
                continue
            if action == "remove":
                edits[key] = {"remove": True, "reason": rec.get("reason", "")}
                continue
            patch = {f: rec[f] for f in EDIT_FIELDS if f in rec and rec[f] is not None}
            edits[key] = patch
        for a in chunk.get("adds") or []:
            adds.append(a)
            actions["add"] += 1
        for f in chunk.get("flags") or []:
            flags.append(f"[chunk {idx}] {f}")

    json.dump({"edits": edits, "adds": adds}, open(out_path, "w"), ensure_ascii=False, indent=1)

    print(f"actions: {dict(actions)}", file=sys.stderr)
    print(f"-> {out_path}: {len(edits)} edits, {len(adds)} adds", file=sys.stderr)
    if flags:
        print(f"\n# flags ({len(flags)}):", file=sys.stderr)
        for f in flags:
            print(f"  - {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
