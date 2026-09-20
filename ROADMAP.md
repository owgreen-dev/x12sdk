# Roadmap

Dates are intentions, not promises; the [changelog](CHANGELOG.md) is the
record. One release a month, around the 20th, each with at least one line of
user-visible value. Patch releases are for bugs only and are unscheduled.

Labels: **Committed** ships in that quarter or the next with a note.
**Target** is intended and may move. **Possible** is an idea that ships only
if someone wants it, which could be you.

## Principles

1. A new transaction set is done when it has models, a parser, at least two
   samples in the byte-for-byte round-trip sweep, a generator, an accessor
   where it has a hierarchy, and a green audit suite, which covers it
   automatically.
2. Breaking changes are batched into one major release with a migration
   table. The next is 3.0.0.
3. Every claim in the README is true of the package on PyPI the day it is
   made.
4. No X12 or WPC code-list text is ever vendored, and no sample ever
   contains PHI, real or realistic-looking.

## Q4 2026 — 2.2, 2.3, 2.4

- **Committed:** `x12sdk-generate`, a console script so a synthetic file is
  one shell command. Python 3.14 in the test matrix. An `X12ModelWriter`
  context manager to mirror the reader.
- **Committed:** the 837D dental claim ([#2](https://github.com/owgreen-dev/x12sdk/issues/2)), with generator and accessor.
- **Committed:** denial analytics carry RARC remark codes, and the reason-code
  category table gets a documented override API.
- **Target:** [#7](https://github.com/owgreen-dev/x12sdk/issues/7), ISO 3166-1 alpha-3 currency codes in CUR. This is a good first issue and is held open for a contributor first.
- **Target:** the 835 generator emits provider-level adjustments (PLB); the
  834 generator emits disability periods and multiple employers; the 837
  generators emit coordination-of-benefits loops.
- **Target:** the 277CA claim acknowledgment (005010X214).
- **Possible:** matched 837 and 835 pairs from one specification, a claim as
  submitted and as adjudicated. Property-based tests as an optional audit
  leg.

## Q1 2027 — 2.5, 2.6, 2.7

- **Committed:** the 278 health care services review ([#4](https://github.com/owgreen-dev/x12sdk/issues/4)).
- **Committed:** the 820 premium payment ([#3](https://github.com/owgreen-dev/x12sdk/issues/3)).
- **Committed:** deprecation warnings for everything 3.0.0 changes, with the
  migration table published a release early.
- **Target:** an `enrollees()` accessor on the 834; the audit suite's
  backtest run on a schedule against the previous tag; a written decision
  on the two 4010 implementations (maintained, no new features).
- **Target:** 999 and TA1 acknowledgment generation for a received
  interchange.
- **Possible:** a structural diff of two transactions; a documentation site
  built from the docstrings.

## Q2 2027 — 3.0, 3.1, 3.2

- **Committed, 3.0.0:** composite fields become first-class models with named
  parts ([#6](https://github.com/owgreen-dev/x12sdk/issues/6)). Python 3.10 support ends (it reached end of life in October 2026). Every queued reader-visible correction lands here, with a migration guide.
- **Target:** a corruption mode for the generators, producing deliberately
  invalid files with the defect named, for testing error handling. Python
  3.15 beta in the matrix.
- **Target:** descriptive analytics beyond denials: provider- and
  procedure-level aggregates over claims and remittances. Descriptive only;
  no clinical rules and no fraud scoring live here.
- **Possible:** a streaming performance pass for very large files; example
  notebooks on generated data.

## Q3 2027 — 3.3, 3.4, 3.5

- **Target:** a release reserved for what external contributors need.
- **Target:** a fifth leg for the audit suite, for whichever bug class the
  year surfaces that the four legs miss.
- **Committed, 3.5.0:** a one-year retrospective and the next roadmap.
- **Out of scope, recorded so it is not re-litigated:** NCPDP and the 275
  attachment transaction.

## Contributing to any of it

Every open issue carries a "Where to start" section. The audit suite
(`repo-docs/AUDIT.md`) is what makes an outside change safe to accept: if it
is green, the change has not reintroduced any defect this codebase has ever
shipped. See [CONTRIBUTING.md](CONTRIBUTING.md).
