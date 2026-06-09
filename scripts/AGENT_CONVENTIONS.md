# Curating the MathML Intent **Open** concept dictionary

You are curating entries in the W3C MathML Intent **Open** list — an open, community list of
*interesting* mathematical notations that go **beyond** the standard **Core** list. Readers (assistive
technology) use these to speak notation. The Open list works by **remixing intent expressions** built
from **concept names**, **`$arg` references**, and **`_literal` values**; it mostly *ignores* the
property/fixity machinery (some W3C members reject core properties outright and use concept names +
expressions instead). So: get the **concept name, arguments, speech, and notation** right; treat
`property:` as a soft hint only.

You will receive a chunk of existing entries (JSON). **Do not trust the current values** — they are an
old, messy draft. Fix names, arities, speech, args, and notations. Each entry needs a decision.

## Inclusion criteria — a concept belongs in Open only if BOTH hold

1. **Speakable & relevant.** It has a clear notation whose **pronunciation differs from its symbolic
   appearance** — AT needs the intent to say it correctly. `\binom{n}{k}` is "n choose k" (not "n over k
   in parentheses"); `M/A` is "Schur complement of A in M" (not "M over A"). A notation that is read
   exactly as it looks adds little and usually does **not** belong.
2. **Documented.** A healthy encyclopedia page **actually contains** the concept — ideally Wikipedia,
   otherwise MathWorld / DLMF / nLab / Encyclopedia of Math. Link it in `links`; verify the page truly
   covers the concept (not merely that the URL resolves), and never invent a URL.

Before adding, check for a **semantic duplicate** — exact-name screening is not enough. Run
`scripts/catalog/dupscan.py` (concepts sharing a notation signature are suspects; most are legitimate
symbol overloads, but some are the same concept under another name, e.g. `lie-bracket` = `commutator`,
`d-alembertian` = `dalembert-operator`). **If the concept already exists under another name, do NOT add
a new entry — add the new name to the existing entry's `alias` list instead.**

## Per-entry decision

For every entry, choose an `action`:

- **`edit`** — migrate/fix it (the common case). Provide the corrected fields + TeX notations.
- **`remove`** — drop it (give a `reason`). Remove ONLY when:
  - the concept name **exactly duplicates a W3C Core concept** (the entry is flagged
    `coreOverlap: true`) — and ONLY then. A concept that merely *shares meaning* with a Core entry
    under a **different name** (e.g. `additive-inverse` vs Core `minus`, `alternation` vs Core `or`) is
    a **distinct Open entry — keep it, and do NOT flag it** as an overlap. Or
  - it is **not a spoken mathematical object** — it names a *property/type annotation of* an object
    rather than an object spoken in practice. E.g. if `x` is "a variable that is a natural number,"
    neither `variable` nor `natural-number` belongs here. **But** `the-natural-numbers` (ℕ, written
    `\mathbb{N}`, spoken as a set) **does** belong.
  - When in doubt, **keep it** (`edit`). Do NOT remove a concept merely because a property/preset
    *could* express it: explicit concept+expression forms are wanted (e.g. `matrix`, `column-vector`,
    `binomial-coefficient` all stay — they let authors write explicit expressions).
- **`keep`** — already correct and in the new shape; leave as-is (rare; most need at least arg renaming).

You may also **split** one entry into several via `adds` (new concepts) — e.g. if a single entry
conflates two distinct objects (Airy `Ai` = first kind vs `Bi` = second kind → keep one, add the other).

## Argument naming — the layered rule

Every argument referenced in speech and marked in the notation gets a **letter-initial, lowercase
NCName** (no leading digit; never `$1`/`$a1`). Choose the name by this priority:

1. **Role** when one exists: `$base`/`$power`, `$numerator`/`$denominator`, `$dividend`/`$divisor`,
   `$real`/`$imaginary`, `$lower`/`$upper`.
2. **Object kind** for a single typed argument: `$matrix`, `$operator`, `$set`, `$space`, `$ring`,
   `$group`, `$field`, `$vector`, `$angle`, `$point`, `$function`; `$number` for an integer/real;
   `$value` as the generic catch-all.
3. **Conventional symbol** when arguments are *interchangeable same-kind operands* with standard
   letters: `A(m,n)` → `$m,$n`; divided difference `[x,y,z]` → `$x,$y,$z`. (Object-kind here would
   force ugly `$number1/$number2`.)

The speech template (`en`) and the notation must use the **same** names.

## Speech template (`en`)

Natural English with `$argname` placeholders. No positional `$1`/`$2`, no HTML (`<i>`…), no trailing
`..`/`…`, no double spaces. Lowercase (e.g. `adjoint of $operator`, `$base to the $power`,
`first adiabatic invariant`). An arity-0 concept has no `$` refs.

## Notations — author in TeX (we regenerate the MathML)

Provide each notation as a **TeX string**. Do NOT write MathML — a downstream step renders your TeX with
the official Temml engine and stores canonical MathML. Use real LaTeX (`\frac`, `\binom`, `\sqrt`,
`\mathbb`, `\mathrm`, `\sigma`, `\dagger`, `^`, `_`, …).

- Mark each argument with **`\arg{name}{body}`** → sets `arg="name"`. The `body` is the visible TeX for
  that argument (a sample identifier like `x`, `n`, `A`).
- The **root intent** auto-composes as `concept($a,$b,…)` from your `\arg` names in document order — so
  for an ordinary application you usually do **not** write `\intent`. Just `\arg`-mark the arguments,
  e.g. `\mathrm{Aff}(\arg{space}{V})`, `\arg{base}{x}^{\arg{power}{n}}`.
- Write **`\intent{expr}{body}`** explicitly only when the root intent isn't the simple positional
  composition — most commonly **arity-0** symbols/constants: `\intent{the-reals}{\mathbb{R}}`,
  `\intent{first-adiabatic-invariant}{\mu}` (no args, so there's nothing to auto-compose).
- An argument may appear **more than once** in one notation (mark each occurrence with the same
  `\arg{name}{…}`), e.g. abundancy `\frac{\sigma(\arg{number}{n})}{\arg{number}{n}}`.
- Provide **multiple notations** when a concept has several common forms (list them); the first is
  primary. Keep only notations that genuinely render the **same** concept (drop misfiled ones).

## Other fields

- **`arity`** = number of distinct `\arg` names. Fix wrong/missing arities (e.g. Ackermann is binary).
  For **function-like** concepts (special functions, transforms, named operators), model the notation
  **as written/spoken — include the evaluation argument**: `P_\ell^m(x)` (arity counts `$value`),
  `\mathrm{Ai}(x)`, `\hat{f}(\xi)`. Don't reduce to the bare operator.
- **`property`** — a soft fixity hint, kept only when clear: one of
  `symbol`/`function`/`prefix`/`infix`/`postfix`/`mixfix`/`fenced`/`indexed`/`constant`/`unit`. Don't
  agonize; omit if unsure.
- **`area`** — the math subfield, lowercase, cleaned (no `?`): e.g. `number theory`, `linear algebra`.
- **`links`** — keep the existing reference URLs. Every concept must carry at least one healthy
  reference that contains it (see Inclusion criteria); add a canonical one (Wikipedia / MathWorld / DLMF
  / nLab / Encyclopedia of Math) if missing. Never invent URLs.
- **`alias`** — keep existing alternative names; add obvious synonyms if helpful. **If this concept is
  the same operation as a W3C Core concept under a different name, add that Core name to `alias`** (e.g.
  `additive-inverse` → alias `minus`; `alternation` → alias `or`). Recognize Core matches against the
  Core name list at the end of this document.

## Worked examples (before → after)

```
abundancy 1:  en "abundancy index  of $1"   → "abundancy index of $number"
              tex \frac{\sigma(\arg{number}{n})}{\arg{number}{n}}
adjoint 1:    3 notations incl. Ad_g (= adjoint action, a DIFFERENT concept)
              → en "adjoint of $operator"; notations ["\arg{operator}{G}'", "\arg{operator}{G}^\dagger"]
ackermann 1:  WRONG arity → arity 2, en "ackermann function of $m and $n", tex A(\arg{m}{m},\arg{n}{n})
the-reals 0:  tex \intent{the-reals}{\mathbb{R}}
```

## Output (structured)

Return an object `{ edits: [...], adds: [...], flags: [...] }`:

- `edits`: one record per input entry, each `{ key, action, ... }` where `key` is the entry's exact
  `"slug#arity"` from the input.
  - `action:"edit"` → include any of: `slug`, `arity`, `en`, `property`, `area`, `links` (string[]),
    `alias` (string[]), `notations` (array of **TeX strings**).
  - `action:"remove"` → include `reason`.
  - `action:"keep"` → no other fields needed.
- `adds`: brand-new concepts (splits), each `{ slug, arity, en, property?, area?, links?, alias?,
  notations: [TeX strings] }`.
- `flags`: short human-readable notes about anything uncertain you want a human to double-check.

## W3C Core concept names (for alias cross-referencing & exact-name removal)

These names live in the **Core** list. Remove an Open entry whose `slug` is an EXACT match
(also marked `coreOverlap:true`). For a same-meaning concept under a different name, keep it and
add the matching Core name to `alias`.

`and`, `angle`, `angle-measure`, `applied-to`, `approximately`, `cartesian-product`, `change`, `composed-with`, `congruent`, `cross-product`, `curl`, `defined-as`, `diameter`, `dimensional-product`, `direct-product`, `distance`, `divergence`, `divided-by`, `divides`, `does-not-belong-to`, `does-not-divide`, `dot-product`, `downwards-diagonal-ellipsis`, `element-of`, `ellipsis`, `equals`, `equivalent-to`, `evaluates-to`, `factorial`, `for-all`, `given`, `gradient`, `greater-than`, `greater-than-or-equal-to`, `identically-equals`, `if-and-only-if`, `implies`, `inner-product`, `intersection`, `invisible-separator`, `invisible-times`, `laplacian`, `less-than`, `less-than-or-equal-to`, `list-separator`, `maps-to`, `measured-angle`, `member-of`, `minus`, `minus-or-plus`, `not`, `not-equal-to`, `not-member-of`, `not-parallel-to`, `not-subset`, `not-superset`, `number-of`, `obtained-from`, `or`, `outer-product`, `parallel-to`, `partial-derivative`, `percent`, `perpendicular`, `plus`, `plus-or-minus`, `precedes`, `probability`, `proportional`, `radius`, `range-separator`, `ratio`, `right-angle`, `set-difference`, `similar`, `square-root-of`, `subset`, `subset-or-equal`, `succeeds`, `such-that`, `superset`, `superset-or-equal`, `there-does-not-exist`, `there-exists`, `tilde`, `times`, `union`, `upwards-diagonal-ellipsis`, `vertical-ellipsis`, `volume`, `xor`
