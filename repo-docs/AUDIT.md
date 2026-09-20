# The audit suite

`src/tests/audit/` is a set of generic detectors, one per bug *class* that has
actually shipped in this codebase. It runs in the ordinary `pytest` run and
covers every transaction package automatically; a new transaction set is
audited the moment it exists.

It exists because of a pattern. Every defect found in 2026 had survived years
in a repository with a 66-file sample corpus and a green test suite, and
almost none of them was reachable by parsing a well-formed sample. They were
reachable by constructing a model in Python, by generating a file with
repeats, or by reading what the model declares against what the parser does.
So that is what the suite does.

## The four legs

| leg | file | question it asks |
|---|---|---|
| 1 structural | `test_structural.py` | Does what the models declare agree with what the parser and validators do? |
| 2 construction | `test_construction.py` | Can every loop and segment be built from its required fields alone, and rendered? |
| 3 repeat stress | `test_repeat_stress.py` | If a file repeats everything three times, does every segment come back exactly once? |
| 4 mutation | `test_mutation.py` | If one invariant is broken in a valid file, does the parser reject it? |

### Leg 1: structural

Seven static checks, applied to every package and to both shared segment
modules. Each test's docstring names the real defect that motivated it.

| check | bug class | instance |
|---|---|---|
| list loops are appended, not assigned | parser initializer writes a dict to a key the model declares as a list; every occurrence after the first is lost silently | 834 loop 2200, 834 loop 2100D, 837P loop 2330C, 4010 837 loop 2330C |
| zero-length fields have a default | `min_length=0` with no default is *required* under Pydantic; only construction notices | 837P/837I `Loop2010Ba.ref_segment`, 271 `Loop2000A.loop_2000b` |
| validators do not default an always-present key | `values.get("x", [])` on an optional field; the key is always present and `None`, so the default never fires and the loop raises | 835 `validate_balance`, shared `_validate_duplicate_codes` |
| validators reference fields that exist | a validator reads a field name that is not on the model; the rule silently never applies | 271 Red Cross check read `ref_segments` |
| defaults are values, not types | a constraint object sits in the default slot instead of the annotation | `IdcSegment.identification_card_count` |
| every set validates its segment count | a validator every other set attaches is commented out on one | the 834 |
| list fields declare their item type | a bare `List` validates nothing inside it | `HiSegment`, twelve fields, both versions |

The first check is flow-sensitive for exactly one pattern, the guard the fix
uses (`if loop_name == REPEATING: append ... else: assign`), so fixed code is
not reported for the branch its own guard makes unreachable.

### Leg 2: construction

A generic filler (`_fill.py`) builds every model from its required fields
alone and demands that it validates and renders. Values are deliberately dull;
the point is to reach every validator with something well-formed.

Three things had to be taught to it, and they are the honest limits of the
approach:

- **Companion fields.** A filled `*_qualifier` drags its value field along
  (and the reverse), because the models enforce those pairs as all-or-nothing.
- **Bounded enum rotation.** When a validator rejects an enum's first value
  (ACH payment demands nine bank fields), each enum field is rotated through
  its values, bounded, so a real defect is still surfaced rather than searched
  around.
- **Overrides.** A handful of models carry a cross-field invariant the filler
  cannot infer, such as an 837 claim charge equalling its line total. Each
  override in `_fill.OVERRIDES` says why it exists. `KNOWN_UNFILLABLE` in the
  test is for models that genuinely cannot be built generically; it is empty,
  and any entry is a strict expected failure so a fix is noticed.

"Validates but cannot render" is its own failure mode here, which is how the
4010 ISA defect was found.

### Leg 3: repeat stress

Every generator is asked for three of everything that may repeat, on both
patient branches where the transaction has them, and the multiset of segment
names in the text must equal the multiset reachable in the parsed model. A
parser that overwrote a repeated loop comes back short by exactly what it
lost. A guard test checks each fixture really does repeat something.

### Leg 4: mutation

Every sample in the corpus is taken, one invariant is broken, and the parser
must reject the result: the segment count off by one, an HL pointing at a
parent that does not exist, an 835 payment that no longer balances, an 837
claim total that disagrees with its lines. The unmutated sample must parse
first, or the mutation proves nothing.

Where a transaction set genuinely has no validator for an invariant, that is
recorded in `KNOWN_UNENFORCED` with a reason, as a strict expected failure.
Today that table holds one finding: **no 837 implementation and neither the
276 nor the 277 checks that an HL's parent id names an HL that exists.** The
270 and 271 do. Adding it is a tightening across five sets and awaits a
decision.

## The backtest

The acceptance test for the suite is that it would have caught what was found
by hand. `scripts/backtest_audit.sh <tag>` checks the tag out in a worktree,
drops the current suite in, and runs it against that code with its own corpus.

Against `v1.0.0`, where every 2026 defect was still present:

| leg | result | what fired |
|---|---|---|
| 1 structural | 12 failed | all seven checks, on every affected package and both shared modules |
| 2 construction | 29 failed | every loop whose validator crashed on a constructed model |
| 4 mutation | 10 failed | all ten 834 samples accepted a wrong SE01 |
| 3 repeat stress | not run | needs the generators, which did not exist at 1.0.0 |

Against current `main` the suite is clean apart from the expected failures in
`KNOWN_UNENFORCED`.

## What it cannot do

- It finds recurrences of classes that have already been seen. A defect of a
  shape nobody has hit yet is not in here, and will not be until it is.
- It does not validate against the X12 implementation guides, which are not
  available to this project. A model that mis-states a repeat count or a
  required element to the guide is beyond it. One consequence: the structural
  check for repeating loops keys off what the *model* declares. The 270's
  eligibility loop was wrongly declared singular, so on v1.0.0 that check
  does not fire for it; only leg 3 catches that shape, and only for
  transactions with a generator.
- Leg 2's overrides are a place where a real defect could be papered over.
  The rule is that an override must name the invariant it satisfies, and a
  `KNOWN_UNFILLABLE` entry must name the reason; both are reviewed like code.

## Adding to it

A new bug class earns a new check, written generically over every package,
with a docstring naming the instance that motivated it, and a line in this
document. A new transaction set needs nothing: it is picked up by all four
legs when its package appears. If it has a generator, add a case to the
repeat-stress table.
