export const meta = {
  name: 'catalog-open-dictionary',
  description: 'Gate + author new Open concepts from a harvested candidate pool (two inclusion criteria; TeX notations)',
  phases: [{ title: 'Author', detail: 'one agent per ~20-candidate chunk' }],
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    adds: {
      type: 'array',
      description: 'admissible new concepts, authored',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          slug: { type: 'string', description: 'lowercase, letter-initial, dash-separated (digits ok)' },
          arity: { type: 'integer' },
          en: { type: 'string', description: 'speech template with $argname refs (named, never $1)' },
          area: { type: 'string' },
          property: { type: 'string' },
          links: { type: 'array', items: { type: 'string' }, description: 'the encyclopedia page URL(s) that contain it' },
          alias: { type: 'array', items: { type: 'string' } },
          notations: { type: 'array', items: { type: 'string', description: 'TeX with \\arg/\\intent' } },
        },
        required: ['slug', 'arity', 'en', 'area', 'links', 'notations'],
      },
    },
    rejects: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { name: { type: 'string' }, reason: { type: 'string' } },
        required: ['name', 'reason'],
      },
    },
  },
  required: ['adds', 'rejects'],
}

const A = typeof args === 'string' ? JSON.parse(args) : args || {}
const workDir = A.workDir
const indices = A.indices

phase('Author')
const results = await parallel(
  indices.map((i) => async () => {
    const tag = String(i).padStart(3, '0')
    const out = await agent(
      [
        'You are EXTENDING the W3C MathML Intent **Open** concept dictionary with new entries.',
        '',
        `STEP 1 — Read the conventions (esp. the two Inclusion criteria): ${workDir}/conventions.md`,
        `STEP 2 — Read the names ALREADY in the dictionary (skip anything present, incl. as a synonym): ${workDir}/existing.txt`,
        `STEP 3 — Read your candidate names: ${workDir}/chunks/cand_${tag}.json`,
        '',
        'For EACH candidate, decide whether it belongs, applying BOTH inclusion criteria strictly:',
        '  (1) speakable & relevant — a clear mathematical NOTATION whose pronunciation differs from its',
        '      symbolic appearance. REJECT: theorems/problems/algorithms/methods, research programs, books,',
        '      meta/notation-style pages, named constants with no distinctive symbol, and anything already',
        '      covered (by name or synonym).',
        '  (2) documented — confirm a healthy encyclopedia page (ideally Wikipedia) that actually contains',
        '      the concept; put its URL in `links`. Do not invent URLs.',
        '',
        'For each ADMISSIBLE candidate author it per the conventions: a lowercase letter-initial `slug`,',
        '`arity` (= number of distinct args), an `en` speech template using $argname refs (role/object-kind',
        'names, never $1), `area`, the `links` URL, and one or more `notations` authored as TeX with',
        '\\arg{name}{body} (and \\intent{expr}{body} only when the root intent is not the simple positional',
        'composition — e.g. arity-0 symbols). Do NOT write MathML — only TeX. Prefer the common notation;',
        'include the evaluation argument for function-like concepts.',
        '',
        'Return { adds: [...], rejects: [{name, reason}, ...] } — every candidate appears in exactly one list.',
      ].join('\n'),
      { schema: SCHEMA, phase: 'Author', label: `cand ${tag}` },
    )
    return { index: i, adds: out.adds ?? [], rejects: out.rejects ?? [] }
  }),
)
return results
