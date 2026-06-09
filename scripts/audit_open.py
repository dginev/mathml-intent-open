#!/usr/bin/env python3
"""Migration-completeness audit for a curated open.yml. Reports residual old-format artifacts and
structural gaps so we can target a fix pass. Usage: python3 scripts/audit_open.py [open.yml]"""
import re
import sys

import yaml


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "open.yml"
    entries = yaml.safe_load(open(path))["concepts"][0]["intents"]
    n = len(entries)

    def has_old_argref(e):
        if re.search(r"\$(?:a?\d)", e.get("en", "") or ""):
            return True
        for nt in e.get("notations") or []:
            if re.search(r"arg=['\"]a?\d", nt.get("mathml", "") or ""):
                return True
            if re.search(r"\$a?\d\b", nt.get("mathml", "") or ""):
                return True
        return False

    checks = {
        "no arity": [e for e in entries if e.get("arity") is None],
        "no notations": [e for e in entries if not e.get("notations")],
        "no en": [e for e in entries if not e.get("en")],
        "no tex in any notation": [
            e for e in entries if not any("tex" in nt for nt in (e.get("notations") or []))
        ],
        "old $1/$a1 argref remains": [e for e in entries if has_old_argref(e)],
        "legacy notation* key remains": [
            e for e in entries if any(k in e for k in ("notation", "notationa", "notationb"))
        ],
        "html in en": [e for e in entries if re.search(r"<\w+>", e.get("en", "") or "")],
        "area with '?'": [e for e in entries if "?" in (e.get("area") or "")],
        "en uses $ref but arity 0": [
            e for e in entries if e.get("arity") == 0 and re.search(r"\$[A-Za-z]", e.get("en", "") or "")
        ],
    }

    print(f"{path}: {n} entries")
    for label, bad in checks.items():
        mark = "OK " if not bad else "!! "
        print(f"  {mark}{label}: {len(bad)}")
        if bad and len(bad) <= 20:
            for e in bad:
                print(f"       - {e['concept']}#{e.get('arity')}")
        elif bad:
            for e in bad[:20]:
                print(f"       - {e['concept']}#{e.get('arity')}")
            print(f"       … and {len(bad) - 20} more")


if __name__ == "__main__":
    main()
