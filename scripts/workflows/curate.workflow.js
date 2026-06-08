export const meta = {
  name: 'curate-open-dictionary',
  description: 'Curate MathML Intent Open entries: rename args, author TeX notations, fix arity, classify keep/remove/split',
  phases: [{ title: 'Curate', detail: 'one agent per ~18-entry chunk' }],
}

// Structured patch each chunk-agent returns. Notations are authored as TeX strings (we regenerate the
// canonical MathML centrally via Temml + minifyMathml, exactly as the editor saves).
const PATCH_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    edits: {
      type: 'array',
      description: 'one record per input entry',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          key: { type: 'string', description: 'the entry\'s exact "slug#arity" from the input' },
          action: { type: 'string', enum: ['edit', 'remove', 'keep'] },
          reason: { type: 'string', description: 'why (required for remove)' },
          slug: { type: 'string' },
          arity: { type: 'integer' },
          en: { type: 'string', description: 'speech template with $argname refs' },
          property: { type: 'string' },
          area: { type: 'string' },
          links: { type: 'array', items: { type: 'string' } },
          alias: { type: 'array', items: { type: 'string' } },
          notations: { type: 'array', items: { type: 'string', description: 'TeX with \\arg/\\intent' } },
        },
        required: ['key', 'action'],
      },
    },
    adds: {
      type: 'array',
      description: 'brand-new concepts (splits)',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          slug: { type: 'string' },
          arity: { type: 'integer' },
          en: { type: 'string' },
          property: { type: 'string' },
          area: { type: 'string' },
          links: { type: 'array', items: { type: 'string' } },
          alias: { type: 'array', items: { type: 'string' } },
          notations: { type: 'array', items: { type: 'string' } },
        },
        required: ['slug', 'arity', 'en', 'notations'],
      },
    },
    flags: { type: 'array', items: { type: 'string' }, description: 'notes for a human to double-check' },
  },
  required: ['edits'],
}

const A = typeof args === 'string' ? JSON.parse(args) : args || {}
const workDir = A.workDir
const indices = A.indices

phase('Curate')
const results = await parallel(
  indices.map((i) => async () => {
    const tag = String(i).padStart(3, '0')
    const out = await agent(
      [
        'You are curating the W3C MathML Intent **Open** concept dictionary (a list of interesting',
        'notations beyond the standard Core list).',
        '',
        `STEP 1 — Read the full conventions: ${workDir}/conventions.md`,
        `STEP 2 — Read your assigned chunk of existing entries: ${workDir}/chunks/chunk_${tag}.json`,
        '',
        'Then curate EVERY entry in the chunk per the conventions:',
        '- rename arguments to letter-initial names (role > object-kind > conventional symbol; never $1/$a1);',
        '- rewrite `en` with those named refs (natural English, no $1/$2, no HTML, no trailing dots);',
        '- author each notation as a TeX string using \\arg{name}{body} (and \\intent{expr}{body} only',
        '  when the root intent is not the simple positional composition, e.g. arity-0 symbols);',
        '- fix wrong/missing `arity` (= number of distinct args), clean `area`, keep `property` only as a hint;',
        '- action:"remove" ONLY for Core-overlap (coreOverlap:true) or a non-spoken property/type entry;',
        '  KEEP explicit-expression concepts (matrix, column-vector, …). When in doubt, edit/keep.',
        '- split a conflated entry into `adds` (new concepts) when it mixes two distinct objects.',
        '',
        'Do NOT write MathML — only TeX. Do NOT trust the current values; fix them.',
        'Return the structured patch: one `edits` record per input entry (keyed by its exact "slug#arity"),',
        'plus any `adds`, plus `flags` for anything uncertain.',
      ].join('\n'),
      { schema: PATCH_SCHEMA, phase: 'Curate', label: `chunk ${tag}` },
    )
    return { index: i, edits: out.edits ?? [], adds: out.adds ?? [], flags: out.flags ?? [] }
  }),
)
return results
