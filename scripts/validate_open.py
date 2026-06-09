#!/usr/bin/env python3
"""Quality gate for open.yml — run in CI on every PR; rejects contributions below the bar.

Each check appends offender lines; any failure exits non-zero with the full list. The bar encodes the
curation conventions (see scripts/AGENT_CONVENTIONS.md):

  1. schema           every entry has concept(str), arity(int>=0), en(str), notations(non-empty;
                      each {mathml:str, tex?:str})
  2. duplicates       (concept, arity) is globally unique (the row identity)
  3. core-overlap     no slug exactly equal to a W3C Core concept name  (needs --core core.yml)
  4. arg-names        arg="..." / $refs are letter-initial NCNames; no positional $1 / arg="a1"
  5. arg-coverage     every $ref in en is marked arg= in a notation, and every arg= is spoken in en
  6. arity-matches    arity == number of distinct $refs in en (and 0 ⇒ no $refs)
  7. no-legacy        no free-text notation/notationa/notationb keys
  8. clean-text       no HTML in en; no '?' in area; no '$N' positional refs in en
  9. mathml-shape     each notation mathml is a <math>…</math> carrying intent=
 10. intent-syntax    each notation's ROOT carries intent=; its concept == slug; and the intent
                      expression's $refs == the notation's arg= markers (catches a $-less arg ref,
                      a mismatched concept name, or intent/arg drift)

Usage: python3 scripts/validate_open.py [open.yml] [--core path/to/core.yml]
"""
import collections
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

import yaml

# A $ref names an argument (NCName: letter/_-initial, may contain letters/digits/_/-/.; no trailing -/.)
SPEECH_REF = re.compile(r"\$([A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_])?)")
NCNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
POSITIONAL_ARG = re.compile(r"^[a_]?\d+$")  # 1, a1, _1, a2 … the old positional convention
ARG_ATTR = re.compile(r"""\barg=["']([^"']+)["']""")
INTENT_REF = re.compile(r"\$([A-Za-z0-9_][A-Za-z0-9_.\-]*)")  # a $ref inside an intent expression


def load(path):
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    out = []
    for group in (doc or {}).get("concepts") or []:
        out.extend(group.get("intents") or [])
    return [e for e in out if isinstance(e, dict) and isinstance(e.get("concept"), str)]


def core_names(path):
    core = yaml.safe_load(open(path, encoding="utf-8"))
    names = set()
    for grp in core.get("defaultfixity", []):
        for c in grp.get("concepts", []):
            if isinstance(c, dict) and c.get("concept"):
                names.add(c["concept"])
    return names


def tag(e):
    return f"{e.get('concept')}#{e.get('arity')}"


def check_schema(entries):
    errs = []
    for e in entries:
        if not isinstance(e.get("arity"), int) or e["arity"] < 0:
            errs.append(f"{tag(e)}: arity must be a non-negative integer")
        if not (isinstance(e.get("en"), str) and e["en"].strip()):
            errs.append(f"{tag(e)}: missing/empty en")
        nots = e.get("notations")
        if not (isinstance(nots, list) and nots):
            errs.append(f"{tag(e)}: notations must be a non-empty list")
            continue
        for i, n in enumerate(nots):
            if not (isinstance(n, dict) and isinstance(n.get("mathml"), str) and n["mathml"].strip()):
                errs.append(f"{tag(e)}: notations[{i}] missing mathml")
            if "tex" in n and not isinstance(n["tex"], str):
                errs.append(f"{tag(e)}: notations[{i}] tex must be a string")
    return errs


# Slug charset: lowercase, letter-initial, single dashes between segments. Digits ARE allowed
# (established names carry them: s5-modal-logic, l2-space) — but no uppercase, spaces, or other chars.
SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def check_slug_charset(entries):
    return [
        f"{tag(e)}: slug {e['concept']!r} must be lowercase letters/digits in single-dash segments, letter-initial"
        for e in entries
        if not SLUG_RE.match(e["concept"])
    ]


def check_duplicates(entries):
    counts = Counter((e["concept"], e.get("arity")) for e in entries)
    return [
        f"duplicate (concept, arity): {n!r} at arity {a} appears {c} times"
        for (n, a), c in sorted(counts.items())
        if c > 1
    ]


def check_core_overlap(entries, core):
    return [
        f"{tag(e)}: slug exactly matches a W3C Core concept name (move to Core or rename)"
        for e in entries
        if e["concept"] in core
    ]


def _aliases(e):
    a = e.get("alias")
    return set(a) if isinstance(a, list) else set()


def check_intra_dup(entries):
    """Mutual aliases (A lists B and B lists A) mean one concept under two names → merge them."""
    al = {e["concept"]: _aliases(e) for e in entries}
    pairs = set()
    for s, names in al.items():
        for a in names:
            if a == s:
                pairs.add((s, "(self)"))  # a concept listing itself as an alias
            elif a in al and s in al[a]:
                pairs.add(tuple(sorted((s, a))))
    return [f"mutual/self alias {x!r} ↔ {y!r} — same concept under two names; merge (keep one, alias the other)" for x, y in sorted(pairs)]


def warn_alias_is_slug(entries):
    """A one-directional alias pointing at another concept's slug — a possible duplicate to review."""
    slugs = {e["concept"] for e in entries}
    out = []
    for e in entries:
        for a in sorted(_aliases(e)):
            if a in slugs and a != e["concept"]:
                out.append(f"{e['concept']}: alias '{a}' is itself a concept slug (merge candidate?)")
    return out


def warn_speech_collision(entries):
    """Distinct concepts whose speech template is identical once arg names are blanked → AT would
    speak them the same. Often fine (e.g. 'degree of X'), but worth an eyeball."""
    groups = collections.defaultdict(set)
    for e in entries:
        norm = re.sub(r"\$[A-Za-z][\w.\-]*", "$_", (e.get("en") or "").strip().lower())
        if norm:
            groups[norm].add(e["concept"])
    return [
        f"speech '{k}' shared by: {', '.join(sorted(v))}"
        for k, v in sorted(groups.items())
        if len(v) > 1
    ]


def _arg_attrs(e):
    args = set()
    for n in e.get("notations") or []:
        for m in ARG_ATTR.finditer(n.get("mathml", "") or ""):
            args.add(m.group(1))
    return args


def _en_refs(e):
    return {m.group(1) for m in SPEECH_REF.finditer(e.get("en", "") or "")}


def check_arg_names(entries):
    errs = []
    for e in entries:
        for a in _arg_attrs(e):
            if POSITIONAL_ARG.match(a):
                errs.append(f"{tag(e)}: positional arg='{a}' — use a meaningful letter-initial name")
            elif not NCNAME.match(a):
                errs.append(f"{tag(e)}: arg='{a}' is not a letter-initial NCName")
        for r in _en_refs(e):
            if r[0].isdigit():
                errs.append(f"{tag(e)}: positional en ref ${r} — use a meaningful name")
            elif not NCNAME.match(r):
                errs.append(f"{tag(e)}: en ref ${r} is not a letter-initial NCName")
    return errs


def check_arg_coverage(entries):
    errs = []
    for e in entries:
        refs, args = _en_refs(e), _arg_attrs(e)
        for r in sorted(refs - args):
            errs.append(f"{tag(e)}: en uses ${r} but no notation marks arg='{r}'")
        for a in sorted(args - refs):
            errs.append(f"{tag(e)}: notation marks arg='{a}' but en never speaks ${a}")
    return errs


def check_arity_matches(entries):
    errs = []
    for e in entries:
        if not isinstance(e.get("arity"), int):
            continue
        nrefs = len(_en_refs(e))
        if e["arity"] != nrefs:
            errs.append(f"{tag(e)}: arity {e['arity']} but en has {nrefs} distinct $refs")
    return errs


def check_no_legacy(entries):
    return [
        f"{tag(e)}: legacy free-text '{k}' key (use notations:)"
        for e in entries
        for k in ("notation", "notationa", "notationb")
        if k in e
    ]


def check_clean_text(entries):
    errs = []
    for e in entries:
        en = e.get("en", "") or ""
        if re.search(r"<\w+>", en):
            errs.append(f"{tag(e)}: HTML tag in en")
        if re.search(r"\$\d", en):
            errs.append(f"{tag(e)}: positional $N in en")
        if "?" in (e.get("area") or ""):
            errs.append(f"{tag(e)}: '?' in area")
    return errs


def check_mathml_shape(entries):
    errs = []
    for e in entries:
        for i, n in enumerate(e.get("notations") or []):
            mm = n.get("mathml", "") or ""
            if not (mm.strip().startswith("<math") and mm.strip().endswith("</math>")):
                errs.append(f"{tag(e)}: notations[{i}] is not a full <math>…</math>")
            elif "intent=" not in mm:
                errs.append(f"{tag(e)}: notations[{i}] has no intent= annotation")
    return errs


def check_intent_syntax(entries):
    """Verify each notation's ROOT element carries an `intent` whose concept == slug and whose $refs
    exactly match the notation's `arg=` markers. (Malformed XML is left to mathml-shape.)"""
    errs = []
    for e in entries:
        slug = e["concept"]
        for i, n in enumerate(e.get("notations") or []):
            mm = n.get("mathml", "") or ""
            args = set(ARG_ATTR.findall(mm))
            try:
                math = ET.fromstring(mm)
            except ET.ParseError:
                continue  # mathml-shape reports malformed markup
            kids = list(math)
            root = kids[0] if len(kids) == 1 else math
            intent = root.get("intent")
            if intent is None:
                errs.append(f"{tag(e)}: notations[{i}] root <{root.tag}> has no intent=")
                continue
            concept = intent.split("(")[0].split(":")[0].strip()
            if concept != slug:
                errs.append(f"{tag(e)}: notations[{i}] intent concept {concept!r} != slug {slug!r}")
            refs = set(INTENT_REF.findall(intent))
            if refs != args:
                errs.append(
                    f"{tag(e)}: notations[{i}] intent $refs {sorted(refs)} != arg= markers {sorted(args)}"
                )
    return errs


def main():
    args = [a for a in sys.argv[1:]]
    core_path = None
    if "--core" in args:
        i = args.index("--core")
        core_path = args[i + 1]
        del args[i : i + 2]
    path = args[0] if args else "open.yml"

    entries = load(path)
    if not entries:
        print(f"{path}: no concept entries found")
        return 1

    checks = [
        ("schema", check_schema(entries)),
        ("slug-charset", check_slug_charset(entries)),
        ("duplicates", check_duplicates(entries)),
        ("intra-dup", check_intra_dup(entries)),
        ("arg-names", check_arg_names(entries)),
        ("arg-coverage", check_arg_coverage(entries)),
        ("arity-matches", check_arity_matches(entries)),
        ("no-legacy", check_no_legacy(entries)),
        ("clean-text", check_clean_text(entries)),
        ("mathml-shape", check_mathml_shape(entries)),
        ("intent-syntax", check_intent_syntax(entries)),
    ]
    if core_path:
        checks.insert(2, ("core-overlap", check_core_overlap(entries, core_names(core_path))))
    else:
        print("note: --core not given; skipping core-overlap check")

    # Warnings: surfaced for curator review, but they do NOT fail the gate.
    warnings = [
        ("alias-is-slug", warn_alias_is_slug(entries)),
        ("speech-collision", warn_speech_collision(entries)),
    ]

    total = 0
    for name, errs in checks:
        if errs:
            total += len(errs)
            print(f"\n[{name}] {len(errs)} problem(s):")
            for line in errs[:50]:
                print(f"  - {line}")
            if len(errs) > 50:
                print(f"  … and {len(errs) - 50} more")

    for name, warns in warnings:
        if warns:
            print(f"\n[{name}] {len(warns)} warning(s) (review, non-failing):")
            for line in warns[:50]:
                print(f"  ~ {line}")
            if len(warns) > 50:
                print(f"  … and {len(warns) - 50} more")

    if total:
        print(f"\n{path}: FAILED — {total} problem(s) across {len(entries)} entries")
        return 1
    print(f"{path}: OK — {len(entries)} entries pass all quality checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
