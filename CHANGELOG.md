# Changelog

All notable changes to x12sdk. The project was forked from
[LinuxForHealth x12](https://github.com/LinuxForHealth/x12) at its final
release, 0.57.0 (June 2022); entries below describe changes made since.

## Unreleased (1.0.0.dev0)

### Changed
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

### Migration from `linuxforhealth-x12`
| before | after |
|---|---|
| `pip install linuxforhealth-x12` | `pip install x12sdk` |
| `from linuxforhealth.x12.io import X12ModelReader` | `from x12sdk.io import X12ModelReader` |
| `lfhx12 -m -p file.x12` | `x12sdk -m -p file.x12` |
| `lfhx12-api` | removed |
