#!/usr/bin/env python3
"""Harvest candidate concept names from encyclopedia sources into a worklist, screened against the
current open.yml (and Core). Sources are intentionally broad/noisy — the two inclusion criteria are
applied per-candidate downstream (this only collects + dedups + screens).

Outputs <workdir>/pool.jsonl: one {name, slug, source, source_id, status} per NOT-yet-covered candidate
(status 'pending'); already-covered names are dropped (matched by slug or alias).

Usage: python3 harvest.py [open.yml] [workdir]
"""
import json, re, sys, time, urllib.parse, urllib.request

UA = "mathml-intent-open-catalog/0.1 (deyan.ginev@gmail.com)"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def slugify(title):
    t = re.sub(r"\s*\(.*?\)\s*", "", title)          # drop "(mathematics)" disambiguators
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t

def wp_category(cat, depth=1):
    """Page titles in a Wikipedia category, expanding subcategories `depth` levels."""
    titles, subcats = [], []
    cont = {}
    while True:
        q = {"action":"query","list":"categorymembers","cmtitle":f"Category:{cat}",
             "cmlimit":"500","format":"json", **cont}
        d = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q))
        for m in d["query"]["categorymembers"]:
            (subcats if m["title"].startswith("Category:") else titles).append(m["title"])
        if "continue" in d: cont = d["continue"]; time.sleep(0.1)
        else: break
    if depth > 0:
        for sc in subcats:
            titles += wp_category(sc.split("Category:",1)[1], depth-1)
    return titles

def wikidata(query):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query":query,"format":"json"})
    return [b["itemLabel"]["value"] for b in get(url)["results"]["bindings"] if "itemLabel" in b]

# meta/non-concept pages to drop outright
SKIP = re.compile(r"\b(notation|abuse|ambiguity|glossary|list of|table of|calculator|formula$|"
                  r"letters used|braille|history|introduction|template|index)\b", re.I)

def main():
    import yaml
    src = sys.argv[1] if len(sys.argv) > 1 else "open.yml"
    workdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/intent_work/catalog"
    import os; os.makedirs(workdir, exist_ok=True)
    ents = yaml.safe_load(open(src))["concepts"][0]["intents"]
    covered = {e["concept"] for e in ents} | {a for e in ents for a in (e.get("alias") or [])}
    core = set(json.load(open("/tmp/intent_work/core_names.json")))

    raw = []  # (name, source, source_id)
    cats = ["Special functions", "Mathematical constants", "Mathematical notation",
            "Operators (physics)", "Binary operations"]
    for c in cats:
        try:
            for t in wp_category(c, depth=1):
                raw.append((t, "wikipedia", f"Category:{c}"))
        except Exception as e:
            print(f"  (wp {c}: {e})", file=sys.stderr)
    try:
        wd = wikidata('SELECT DISTINCT ?itemLabel WHERE { ?i wdt:P279* wd:Q207643. '
                      '?a schema:about ?i; schema:isPartOf <https://en.wikipedia.org/>. '
                      'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 400')
        raw += [(n, "wikidata", "Q207643") for n in wd]
    except Exception as e:
        print(f"  (wikidata: {e})", file=sys.stderr)

    seen, pool = set(), []
    for name, source, sid in raw:
        if SKIP.search(name): continue
        slug = slugify(name)
        if not slug or slug in seen: continue
        seen.add(slug)
        if slug in covered or slug in core: continue
        # also skip if a near-form is covered (singular/plural)
        if slug.rstrip("s") in covered or (slug + "s") in covered: continue
        pool.append({"name": name, "slug": slug, "source": source, "source_id": sid, "status": "pending"})

    with open(f"{workdir}/pool.jsonl", "w") as fh:
        for p in pool: fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"harvested {len(raw)} raw → {len(seen)} unique → {len(pool)} NEW (not covered) candidates")

if __name__ == "__main__":
    main()
