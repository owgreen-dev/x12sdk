# Changelog

All notable changes to x12sdk. The project was forked from
[LinuxForHealth x12](https://github.com/LinuxForHealth/x12) at its final
release, 0.57.0 (June 2022); entries below describe changes made since.

## 1.2.0 — 2026-09-19

### Added
- **`generate_270()` and `generate_271()`** — synthetic eligibility inquiries
  and responses. Both sit on the same four-level hierarchy, and it carries the
  same subscriber/dependent branch as the 837, so generated files contain both
  by default. One `EligibilitySpec` builds an inquiry and the response to it,
  which is usually what a test fixture wants.
- **`generate_276()` and `generate_277()`** — synthetic claim status
  inquiries and responses. They share a five-level hierarchy, one deeper than
  eligibility, and carry the same subscriber/dependent branch, so generated
  files contain both by default. The inquiry states what was billed and the
  response answers with an STC status; on one seed the pair describes the same
  people and the same claims, because the demographics only the 276 renders
  are still drawn for both.
- **`generate_834()`** — synthetic benefit enrollment. The 834 is the one
  supported transaction with no HL hierarchy: a dependent is a separate member
  record told apart by INS01 and INS02 rather than a loop nested under the
  subscriber, and both kinds appear by default. **Every supported transaction
  set can now be generated.**
- **`members()` on the 270 and 271, and `claims()` on the 276 and 277**, in
  `x12sdk.access`. Both pairs carry the same subscriber/dependent branch as
  the 837, so the same correctness trap applies: code written against one path
  reports nothing on a file using the other. Each yields a flat, frozen record
  carrying its context. A tracked claim reads its charge from AMT on an
  inquiry and from STC on a response, so a caller need not know which it
  holds. Verified against the whole corpus by requiring every EQ, EB and
  patient-level TRN segment in the raw files to be reachable.
- Fifteen generated files added to the sample corpus, which the round-trip
  sweep now covers (72 files to 87): six eligibility, six claim status and
  three enrollment, each covering subscriber-only, dependent-only and mixed.

### Changed
- **The 834 now validates SE01.** `validate_segment_count` was commented out on
  that transaction set alone, so it was the only one that accepted a wrong
  segment count in silence; every other set has always rejected it. All ten
  inherited 834 samples already carry a correct count, so nothing in the corpus
  changes. If you parse 834 files from a partner who miscounts SE01, they will
  now be rejected rather than parsed.

### Fixed
- `validate_hierarchy_ids` (270, 271) required every HL segment to be parented
  by the *previous* HL in the file, which is not an X12 rule. It made more than
  one subscriber per information receiver impossible: the second subscriber
  would have had to be parented by the first, while another check in the same
  validator required the information receiver. A provider checking eligibility
  for a list of patients is the ordinary use of a 270. The real parent-identity
  rules are kept, so nothing that validated before stops validating. No sample
  in the corpus has more than one subscriber, which is why it never fired.
- `_validate_duplicate_codes` in `x12sdk.validators` read `ref_segment` with a
  `get()` default, but on a model built in Python the key is always present and
  set to `None`; only the parser pre-seeds a list. Any constructed loop that
  left REF out raised `TypeError`. This affects every transaction set using the
  duplicate-REF and duplicate-AMT checks, not only eligibility.

## 1.1.0 — 2026-09-19

### Added
- **`write_transactions()`** in `x12sdk.io`. The library could read a complete
  file but not produce one: transaction models cover ST through SE, and the
  reader discards the ISA/GS/GE/IEA envelopes after reading delimiters and
  version. The writer supplies them, keeping IEA02 aligned with ISA13 and GE02
  with GS06, and deriving GS01/GS08 from the transaction's package rather than
  from ST03, which is optional on the 835. Consecutive transactions of the same
  type share a functional group.
- **`x12sdk.generate`** — synthetic transaction generation, because real files
  contain PHI and no public corpus exists. `generate_835(seed=..., claims=...)`
  returns a complete file; the same seed reproduces the same bytes and the
  global random state is never touched. Claims can be described exactly
  (`ClaimSpec`, `ServiceLineSpec`, `denial()`), with payment derived from charge
  minus adjustments so an unbalanced remittance cannot be specified.
- **`generate_837p()`** — synthetic professional claim submissions, built the
  same way. An 837 files a claim under the subscriber when the patient is the
  subscriber and under a dependent when they are not; generated files contain
  both branches by default, because code that walks the hierarchy commonly
  handles only the first and silently skips the other. `dependent_rate`
  chooses the mix and `SubmissionSpec` places each claim exactly. HL
  numbering, parent links and child flags are assigned by the builder, and
  the claim charge is checked against the service line total that the model
  requires.
- **`claims()` and `subscribers()`** on the 835, 837P and 837I transaction
  models, in the new `x12sdk.access` module. Answers the upstream request in
  LinuxForHealth/x12#77. On an 837 a claim sits under the subscriber when the
  patient is the subscriber and under a dependent when they are not; code
  written against one path runs without error on a file using the other and
  reports no claims, so this is a correctness trap rather than an
  inconvenience. `claims()` walks both and yields a flat, frozen record
  carrying the claim with its billing provider, subscriber, payer, patient,
  `is_dependent` and relationship. `patient` already points at whoever was
  treated. Yielded lazily, so a large file is not materialized. The 835
  version yields charge, payment, status, adjustments, service lines and the
  LX header number. Verified against the whole corpus by counting CLM, CLP and
  HL segments in the raw files and requiring the accessors to match.
- Six generated files added to the sample corpus, which the round-trip sweep
  now covers (66 files to 72): three remittances and three claim submissions,
  the latter covering the subscriber branch, the dependent branch and a mix.
- **`x12sdk.denials`** — denial analytics over 835 remittance advice.
  `iter_adjustments()` flattens every CAS adjustment (claim level and service
  line, all six reason positions per segment) into one record per reason code
  with the claim, line and remark-code context attached.
  `denial_summary()` aggregates by payer, adjustment group and reason code,
  counting payer-side groups (`CO`, `OA`, `PI`) by default and distinct claims
  rather than occurrences. Amounts stay `Decimal` throughout, so totals are
  exact. `to_dataframe()` is available with the new `pandas` extra.
- `iter_adjustments()` reaches claims through the transaction's own `claims()`
  accessor rather than walking loops itself, so there is one definition of how
  to reach a claim in an 835 and one place for it to be wrong.
- `categorize()` groups reason codes into analysis categories (eligibility,
  authorization, duplicate, timely filing, coordination of benefits and
  others). **No X12/WPC code-list text ships with x12sdk** — the descriptions
  are licensed separately. `load_code_descriptions()` reads a list you supply,
  and a test guards against that text being vendored in future.
- The category table deliberately leaves `A2` and `42` in `other`, although
  both are contractual write-offs in routine work. `contractual` is the
  category a denial review skips: `A2` is payer-discretionary in practice, and
  `42` was retired in favour of `45`, so a payer still sending it is itself
  worth a second look. The reasoning is recorded in the table and pinned by a
  test, so it is not later closed as an oversight. Override it with your own
  mapping if your book of business treats them as routine.

### Fixed
- `Loop2010Ba.ref_segment` (837P and 837I) and `Loop2000A.loop_2000b` (271)
  were declared `min_length=0` with no default, which made them required:
  building a subscriber in Python meant passing `ref_segment=[]` by hand, and
  omitting it failed validation. They now default to an empty list. The parser
  already pre-seeded one, so parsing and serialized output are unchanged.
- `Loop2100.validate_balance` (835) raised `TypeError` on any claim with no
  adjustments. It read `cas_segment` with a `get()` default, but the key is
  always present and set to `None` on a model built in Python; only the parser
  pre-seeds a list. A fully paid claim is ordinary, and constructing one was
  impossible.
- `Loop2110C.validate_red_cross_eb_ref_codes` (271) read a field named
  `ref_segments`, which does not exist — the field is `ref_segment`. The lookup
  always returned empty, so the American Red Cross reference check silently
  passed on every transaction. It now enforces the rule.

## 1.0.0 — 2026-09-19

First release of x12sdk, continuing [LinuxForHealth x12](https://github.com/LinuxForHealth/x12)
from its final 0.57.0 (June 2022).

### Changed
- **Migrated to Pydantic v2** (`pydantic>=2,<3`, plus `pydantic-settings`).
  Closes the upstream request in LinuxForHealth/x12#141. The round-trip oracle
  over all 66 sample files passes unchanged, so parsing and serialization
  behaviour is preserved. What this means if you use the models directly:
  - Model methods follow v2 names: `model_dump()` / `model_validate()` rather
    than `dict()` / `parse_obj()`, and `model_fields` rather than `__fields__`.
  - `Optional[...]` fields now carry an explicit `None` default, so they stay
    optional under v2 rules.
  - Cross-field checks are `@model_validator(mode="after")` and receive the
    model instance; per-field checks are `@field_validator` and take
    `info: ValidationInfo` when they need other fields.
  - Date fields that the parser resolves to a `date`/`datetime` now declare
    that in their annotations (previously some claimed `str` only).
  - `x12.api` / the `api` extra remain removed (see below), and
    `pydantic.BaseSettings` moved to `pydantic-settings`.

### Fixed (during the v2 port)
- `IdcSegment.identification_card_count` was declared
  `Optional[int] = conint(gt=0)`, which put a *type* in the default slot
  instead of constraining the field. It is now
  `Optional[Annotated[int, Field(gt=0)]] = None`, so the bound is enforced.
  Serialized output is unchanged.
- `Cr5Segment.segment_name` in the 4010 module overrode a base field without a
  type annotation, which v2 rejects outright.
- Renamed the package and import namespace from `linuxforhealth.x12` to
  `x12sdk`; the CLI command is now `x12sdk` (was `lfhx12`).
- Moved packaging from `setup.cfg` to `pyproject.toml` (`[project]`);
  fixed the invalid `setuptools>-42` build requirement that broke
  `pip install -e .`.
- Minimum Python is now 3.10 (was 3.8).
- Adopted ruff for linting.

### Fixed
- 834: the member coverage provider information loop (LX, loop 2310) raised
  `TypeError` because the parser tested loop membership on the parser
  context instead of the coverage record. The `enroll-employee-managed-care`
  sample now parses.
- `LxSegment.assigned_number` (LX01, an N0 element) is now the digit string
  from the transaction instead of an `int`, so values written with leading
  zeros (`LX*01`) serialize back unchanged. Call `int()` where a number is
  needed. The 835 duplicate-line check compares numeric values, so `01` and
  `1` are still treated as the same line number.
- Corrected the `enroll-employee-managed-care.834` sample: its member-level
  `DTP*358` is not a valid loop 2000 date qualifier; the sibling enrollment
  sample's `356` (eligibility begin) is used.
- Repeated segments are never dropped. The parser stored the first
  occurrence of a segment as a dict and appended only when the loop
  initializer had pre-seeded a list; a second occurrence of any segment the
  initializer missed was silently discarded, and the first failed validation
  (dict where a list was declared). Two safety nets now apply to every
  transaction: the parser promotes a repeated dict to a list, and
  `X12SegmentGroup` accepts a single record for a `List[...]` field.
- Pre-seeded the repeatable segments that initializers missed: 835 loop 1000A
  `PER`; 837I loop 2300 `NTE`; 271 loop 2100A `PRV`. (Independently confirmed
  by MdClarity/x12 PR #5 for the 835 and 837I cases.)
- 837I: loop 2440 (`LQ` form identification + `FRM`) had a model but no
  initializer, so the segments were dropped from every service line. Added
  the initializer and the `loop_2440` field on loop 2400.
- 837 4010 (X096A1, X098A1): loop 2305 (`CR7` home health care plan + `HSD`)
  had a model but no initializer, so the segments were dropped. Added the
  initializer, and allowed the claim entity loops (2310) to follow loop 2305.
- Decimal fields serialize with the scale they were parsed with (`HSD*VS*2`
  no longer comes back as `HSD*VS*2.00`). Amounts written with two decimals
  are unchanged. **Behaviour change for segments you construct yourself:**
  `Decimal("37.5")` now serializes as `37.5`, not `37.50`; pass
  `Decimal("37.50")` when two places are required.
- `test_loop_initializers.py` asserts every list-typed segment field is
  pre-seeded by its transaction's parsing module; `test_repeatable_segments.py`
  and five new synthetic samples cover the repaired loops.

### Added
- `test_resource_roundtrip.py`: every sample under `src/tests/resources/`
  (61 files) must parse, validate, and serialize back byte for byte.
  Upstream exercised only a subset of the samples.

### Removed
- The experimental FastAPI endpoint (`lfhx12-api`, `x12.api`,
  `X12ApiConfig`), its `api` extra, and the Dockerfile / container tooling.
  x12sdk is an SDK and CLI; wrap it in the web framework of your choice.

### Upstream issues (LinuxForHealth/x12) and their status in x12sdk
- Carried over as x12sdk issues: #102 837D dental, #101 820 premium payment,
  #100 278 services review, #77 generator-based accessors, #40 composite
  fields as first-class models, #50 ISO 3166-1 alpha-3 in CUR, #141 Pydantic
  v2 port.
- Done here: #38 import sorting (ruff `I` rules); #125 coverage (measured in
  CI with a fail-under gate); #124 source code scanning (CodeQL workflow);
  #126 license scanning (`pip-licenses` CI step).
- Won't do, because the API and container layer was removed: #140 s390x
  image, #135 OAuth2 for the API, #134 HTTPS for the API, #133 Basic Auth
  for the API, #123 image scans, #120 Helm chart. Wrap the SDK in your own
  service if you need an endpoint.
- Dropped: #59 model generation; its tracker (LinuxForHealth/bluesteel) is
  inactive.

### Migration from `linuxforhealth-x12`
| before | after |
|---|---|
| `pip install linuxforhealth-x12` | `pip install x12sdk` |
| `from linuxforhealth.x12.io import X12ModelReader` | `from x12sdk.io import X12ModelReader` |
| `lfhx12 -m -p file.x12` | `x12sdk -m -p file.x12` |
| `lfhx12-api` | removed |
