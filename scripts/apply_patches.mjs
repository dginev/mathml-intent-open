/**
 * Batch editor for open.yml — applies structured per-entry patches and re-serializes through the
 * MathML-Intent-Open editor's OWN parse → serialize pipeline, so output is byte-identical to what the
 * editor would save (canonical order, lineWidth:0, the notations: shape). Notations authored as TeX are
 * turned into stored MathML exactly as the editor does it (NotationEditor.tsx::deriveNotation):
 *
 *     texToIntent(temml, tex, slug)  →  `<math>${fragment}</math>`  →  minifyMathml(...)
 *
 * Run from the editor repo so vite-node resolves `temml` and transforms the editor's .ts sources:
 *
 *   cd ~/git/mathml-intent-editor && \
 *     npx vite-node ~/git/mathml-intent-open/scripts/apply_patches.mjs -- \
 *       <in.yml> <out.yml> <patch.json|patch.mjs> [more-patches...]
 *
 * Patch file = JSON (or `export default` for .mjs), either a flat map or {edits, adds}:
 *   {
 *     "edits": { "<slug>#<arity>": <patch>, ... },   // (or pass a bare map = edits)
 *     "adds":  [ <concept>, ... ],                    // brand-new entries (splits, etc.)
 *   }
 * <patch> = { remove:true, reason? } | { slug?, arity?, en?, property?, area?, links?[], alias?[],
 *             notations?: Array<string|{tex}|{mathml}>, keepLegacy? }
 * <concept> = { slug, arity, en, property?, area?, links?[], alias?[], notations:[...] }   (for adds)
 *
 * Multiple patch files are MERGED (edits shallow-merged by key, adds concatenated) — so a workflow can
 * fan out one patch file per chunk and we apply them all at once. TeX-render failures are NON-FATAL:
 * the offending entry is left untouched and reported, so the file stays valid and we get a fix-list.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.DOMParser = dom.window.DOMParser;
globalThis.XMLSerializer = dom.window.XMLSerializer;
globalThis.document = dom.window.document;

const ED = '/home/deyan/git/mathml-intent-editor/src';
const temml = (await import('temml')).default;
const { parseDictionary } = await import(`${ED}/data/parse.ts`);
const { serializeConcepts } = await import(`${ED}/data/serialize.ts`);
const { texToIntent, missingSpeechRefs, unusedArgRefs } = await import(`${ED}/render/intent.ts`);
const { minifyMathml } = await import(`${ED}/render/minifyMathml.ts`);

const argv = process.argv.slice(2).filter((a) => a !== '--');
const [inPath, outPath, ...patchPaths] = argv;
if (!inPath || !outPath || patchPaths.length === 0) {
  console.error('usage: apply_patches.mjs -- <in.yml> <out.yml> <patch...>');
  process.exit(1);
}

async function loadPatch(p) {
  if (p.endsWith('.json')) return JSON.parse(readFileSync(p, 'utf8'));
  return (await import(p)).default;
}

/** Merge patch files: edits shallow-merged by key, adds concatenated. Accepts flat-map = edits. */
const edits = {};
const adds = [];
for (const p of patchPaths) {
  const obj = await loadPatch(p);
  const e = obj.edits ?? (obj.adds ? {} : obj);
  Object.assign(edits, e);
  if (Array.isArray(obj.adds)) adds.push(...obj.adds);
}

/** Replicate the editor's TeX→stored-MathML derivation exactly. Throws on a render failure. */
function texToStored(tex, slug) {
  const r = texToIntent(temml, tex, slug);
  if (!r.ok) throw new Error(r.error);
  return minifyMathml(`<math>${r.mathml}</math>`);
}
function buildNotations(list, slug) {
  return list.map((n) => {
    if (typeof n === 'string') return { tex: n, mathml: texToStored(n, slug) };
    if (n.tex !== undefined) return { tex: n.tex, mathml: texToStored(n.tex, slug) };
    if (n.mathml !== undefined) return { mathml: n.mathml };
    throw new Error(`bad notation entry: ${JSON.stringify(n)}`);
  });
}

const concepts = parseDictionary(readFileSync(inPath, 'utf8'));
// Key matches the Python extraction: undefined/null arity → "None" (str(None)).
const keyOf = (c) => `${c.slug}#${c.arity === undefined || c.arity === null ? 'None' : c.arity}`;
const byKey = new Map(concepts.map((c) => [keyOf(c), c]));
const bySlug = new Map();
for (const c of concepts) (bySlug.get(c.slug) ?? bySlug.set(c.slug, []).get(c.slug)).push(c);

/** Resolve an edit key to its concept, tolerating an agent that mutated the arity in the key. */
function resolve(key) {
  if (byKey.has(key)) return byKey.get(key);
  const slug = key.slice(0, key.lastIndexOf('#'));
  const cands = bySlug.get(slug);
  if (cands && cands.length === 1) {
    report.push(`~~ SLUGMATCH ${key} → ${keyOf(cands[0])}`);
    return cands[0];
  }
  return undefined;
}

const removed = new Set();
const touched = new Set();
const report = [];
const failures = [];
const argWarnings = [];
const nIn = concepts.length;
let edited = 0;
let added = 0;

function applyFields(c, p) {
  if (p.slug !== undefined) c.slug = p.slug;
  if (p.arity !== undefined) c.arity = p.arity;
  if (p.en !== undefined) c.en = p.en;
  if (p.area !== undefined) c.area = p.area;
  if (p.property !== undefined) c.property = p.property;
  if (p.links !== undefined) c.links = p.links;
  if (p.alias !== undefined) c.alias = p.alias;
}

// --- edits / removals ---
for (const [key, p] of Object.entries(edits)) {
  const c = resolve(key);
  if (!c) {
    report.push(`!! MISSING  ${key}`);
    continue;
  }
  if (p.remove) {
    removed.add(c);
    report.push(`-- REMOVE   ${key}${p.reason ? ` — ${p.reason}` : ''}`);
    continue;
  }
  // Build notations first; a TeX failure leaves the entry fully untouched (and reported).
  let nots;
  if (p.notations !== undefined) {
    try {
      nots = buildNotations(p.notations, p.slug ?? c.slug);
    } catch (err) {
      failures.push(`${key}: ${err.message}`);
      report.push(`XX TEXFAIL  ${key} — ${err.message}`);
      continue;
    }
  }
  if (!p.keepLegacy && c.raw) {
    delete c.raw.notation;
    delete c.raw.notationa;
    delete c.raw.notationb;
  }
  applyFields(c, p);
  if (nots !== undefined) c.notations = nots;
  touched.add(c);
  edited += 1;
  report.push(`** EDIT     ${key}`);
}

// --- adds (new concepts / splits) ---
for (const a of adds) {
  let nots;
  try {
    nots = buildNotations(a.notations ?? [], a.slug);
  } catch (err) {
    failures.push(`ADD ${a.slug}#${a.arity}: ${err.message}`);
    report.push(`XX TEXFAIL  ADD ${a.slug}#${a.arity} — ${err.message}`);
    continue;
  }
  const nc = {
    slug: a.slug,
    arity: a.arity,
    en: a.en,
    speech: [],
    area: a.area,
    property: a.property,
    notations: nots,
    links: a.links ?? [],
    alias: a.alias ?? [],
    raw: {},
  };
  concepts.push(nc);
  touched.add(nc);
  added += 1;
  report.push(`++ ADD      ${a.slug}#${a.arity}`);
}

const kept = concepts.filter((c) => !removed.has(c));

// --- arg-ref sanity: speech refs vs notation arg= names (across all notations of a touched entry) ---
for (const c of kept) {
  const key = keyOf(c);
  if (!touched.has(c) || c.arity === 0) continue;
  const mm = c.notations.map((n) => n.mathml).join(' ');
  const en = c.en ?? '';
  const miss = missingSpeechRefs(en, mm);
  const unused = unusedArgRefs(en, mm);
  if (miss.length || unused.length) {
    argWarnings.push(
      `${key}: ${miss.length ? `speech refs not in notation: ${miss.join(',')}` : ''}` +
        `${miss.length && unused.length ? ' | ' : ''}` +
        `${unused.length ? `notation args not spoken: ${unused.join(',')}` : ''}`,
    );
  }
}

writeFileSync(outPath, serializeConcepts(kept));

console.error(report.join('\n'));
if (argWarnings.length) console.error('\n# arg-ref warnings:\n  ' + argWarnings.join('\n  '));
if (failures.length) console.error('\n# TeX failures (entries left untouched):\n  ' + failures.join('\n  '));
console.error(
  `\n${inPath} → ${outPath}: ${nIn} in, ${kept.length} out ` +
    `(${edited} edited, ${added} added, ${removed.size} removed, ${failures.length} tex-failed)`,
);
