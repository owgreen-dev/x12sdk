# Contributing to x12sdk

Thanks for helping. Bug reports, sample files that break the parser, new
transaction sets, and documentation fixes are all welcome.

## Ground rules

- **License.** Contributions are accepted under the Apache License 2.0
  (inbound = outbound). Do not contribute code you do not have the right to
  license this way.
- **DCO sign-off.** Every commit must carry a `Signed-off-by:` line
  certifying the [Developer Certificate of Origin](https://developercertificate.org/).
  Use `git commit -s`.
- **No copyrighted standards text.** Do not add X12 implementation guide
  (TR3) prose or X12/WPC code-list descriptions (CARC, RARC, etc.) to the
  repository. Segment and element *structure* expressed as code is fine;
  descriptive text is not. See NOTICE.
- **No real PHI.** Sample X12 files must be synthetic. Never commit a real
  claim, remittance, or eligibility file, even de-identified.
- **AI-assisted changes** are fine; say so in the PR description and make
  sure you have reviewed and can explain every line.

## Development setup

```shell
git clone https://github.com/owgreen-dev/x12sdk
cd x12sdk
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

## Making a change

1. Branch from `main`.
2. Add or update tests under `src/tests/`. Every transaction set has a
   directory of tests and synthetic samples under `src/tests/resources/`;
   parse → validate → serialize must reproduce each sample byte for byte.
3. Run `ruff check src` and `pytest` locally.
4. Open a pull request. Describe what changed and why, and whether any
   behaviour visible to users of `linuxforhealth-x12` changed.

## Adding a transaction set

See [repo-docs/NEW_TRANSACTION.md](repo-docs/NEW_TRANSACTION.md).
