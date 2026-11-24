# x12sdk

Read, check and generate HIPAA X12 health care transactions in Python:
claims (837P, 837I, 837D), remittances (835), eligibility (270/271), claim
status (276/277) and enrollment (834).

```shell
pip install x12sdk
x12sdk-table remit.835 -o remit.csv          # an 835 as one row per service line
x12sdk-validate claims.837                   # valid, or where it breaks
x12sdk-generate 837p --seed 7 --claims 25    # synthetic claims, no PHI
```

Everything runs locally; no file is uploaded anywhere.

## Start where you are

| You have… | Go to |
|---|---|
| A file and no Python | The [browser playground](https://huggingface.co/spaces/owgreen-dev/x12sdk-playground): check it, get a CSV, nothing to install |
| An 835 you want in a spreadsheet | [Tables](guide/tables.md) |
| A file a payer or clearinghouse rejected | [Checking files](guide/validation.md) |
| Code to test, and no X12 you can share | [Generating synthetic files](guide/generating.md) |
| Claims and the remittances that paid them | [Pairs and matching](guide/matching.md) |
| Denials to understand across many remittances | [Denial analytics](guide/denials.md) |
| An AI assistant that should read X12 | [MCP server](guide/mcp.md) |
| Code on `linuxforhealth-x12` | [Migrating](migrating.md) |

A ready-made [dataset of 30,000 synthetic claims with their remittances](https://huggingface.co/datasets/owgreen-dev/x12sdk)
is on Hugging Face.

## Supported transaction sets

| Set | Implementation | What it is | Generate | Accessors |
|---|---|---|---|---|
| 837P | 005010X222A2 | Professional claim | `generate_837p` | `claims()`, `subscribers()` |
| 837I | 005010X223A3 | Institutional claim | `generate_837i` | `claims()`, `subscribers()` |
| 837D | 005010X224A2 | Dental claim | `generate_837d` | `claims()`, `subscribers()` |
| 835 | 005010X221A1 | Claim payment / remittance advice | `generate_835` | `claims()` |
| 834 | 005010X220A1 | Benefit enrollment and maintenance | `generate_834` | |
| 270 / 271 | 005010X279A1 | Eligibility inquiry / response | `generate_270` / `generate_271` | `members()` |
| 276 / 277 | 005010X212 | Claim status inquiry / response | `generate_276` / `generate_277` | `claims()` |

Every transaction parses into a validated Pydantic v2 model and serializes
back to X12; the test suite asserts the round trip reproduces each sample
file byte for byte. x12sdk runs on Python 3.10–3.14.

```{toctree}
:hidden:
:caption: Get started

install
```

```{toctree}
:hidden:
:caption: Guides

guide/tables
guide/validation
guide/generating
guide/matching
guide/reading
guide/denials
guide/mcp
guide/cli
```

```{toctree}
:hidden:
:caption: Reference

api
performance
migrating
about
```
