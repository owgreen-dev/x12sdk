---
license: cc-by-4.0
pretty_name: x12sdk synthetic health care claims and remittances
language:
- en
tags:
- healthcare
- x12
- edi
- hipaa
- claims
- synthetic
- tabular
size_categories:
- 10K<n<100K
task_categories:
- tabular-classification
- tabular-regression
configs:
- config_name: claims
  data_files: data/claims.csv
  default: true
- config_name: service_lines
  data_files: data/service_lines.csv
---

# x12sdk synthetic health care claims and remittances

Synthetic ASC X12 5010 health care claims, the remittances that answer them,
and the same data as two flat tables. **Every record is synthetic.** Nothing
here is, or is derived from, real patient, provider or payer data.

Real claims and remittances are protected health information, so there is no
public set of them to build or test against. This dataset fills that gap for
anyone who needs X12 in the real format: engineers testing a claims pipeline,
people learning the transactions, and anyone wanting a claim and its outcome
side by side.

It was generated with [x12sdk](https://github.com/owgreen-dev/x12sdk)
{version} and can be rebuilt byte for byte from the seed below.

## What is in it

| Path | Contents |
|---|---|
| `x12/837p/`, `x12/837i/`, `x12/837d/` | {files} X12 files: for each claim type, {pairs} claim submissions (`pair-NNN.837`) each paired with the remittance that answers it (`pair-NNN.835`), {claims_per_pair} claims per file |
| `data/claims.csv` | {claims} rows, one per claim: as billed, and what the payer did |
| `data/service_lines.csv` | {lines} rows, one per service line, likewise |

Claim types: **837P** professional (005010X222A2), **837I** institutional
(005010X223A3), **837D** dental (005010X224A2). Remittances are **835**
(005010X221A1).

Every claim on an 837 is answered by exactly one claim payment on its 835,
linked as real files are, by the patient control number (CLM01 = CLP01), with
the same charge, the same procedure on each line, and the same patient, payer
and payee. Every file parses and validates against the implementation guide
rules the library models, including the 835 balancing rules.

The tables were made by parsing the X12 files with x12sdk, so they are a check
on the files as well as a convenience: `patient_control_number` (with
`claim_type` and `pair`) joins `claims` to `service_lines`.

### `claims` columns

| Column | Meaning |
|---|---|
| `claim_type` | `837p`, `837i` or `837d` |
| `pair` | which file pair the claim is in |
| `patient_control_number` | CLM01 / CLP01, the link between the two files |
| `service_date` | the claim's date of service (or statement date, 837I) |
| `claim_charge` | CLM02, total billed |
| `line_count` | number of service lines |
| `is_dependent` | the patient is a dependent of the subscriber, not the subscriber |
| `relationship_code` | the patient's relationship code (18 = self) |
| `patient_gender`, `patient_birth_year` | from the patient's DMG segment |
| `diagnosis_code` | the principal ICD-10-CM code (none on dental claims) |
| `payer_name`, `billing_provider_name`, `billing_provider_npi` | synthetic placeholders; NPIs carry a valid check digit but are not real |
| `claim_status_code` | CLP02: `1` processed as primary, `4` denied |
| `denied` | `claim_status_code` is `4` |
| `paid_amount` | CLP04 |
| `contractual_adjustment` | total CO (contractual obligation) adjustments |
| `patient_responsibility` | total PR adjustments: deductible, coinsurance, copay |
| `denial_reason_code` | for a denied claim, the claim adjustment reason code |
| `payer_claim_control_number` | CLP07 |

### `service_lines` columns

| Column | Meaning |
|---|---|
| `line_number` | position on the claim |
| `procedure_qualifier`, `procedure_code` | `HC` with a CPT/HCPCS code, or `AD` with a CDT dental code |
| `revenue_code` | institutional claims only |
| `units` | units of service (procedure count on dental claims) |
| `line_charge`, `line_paid` | billed, and paid on the 835 |
| `tooth_number`, `tooth_surfaces` | dental claims: Universal tooth number and surfaces (e.g. `M:O`), where the procedure is done to a tooth |
| `contractual_adjustment`, `patient_responsibility` | the line's CO and PR totals |
| `adjustment_reasons` | every adjustment on the line as `GROUP-REASON`, e.g. `CO-45;PR-2` |

## Outcomes are random

**Read this before using the data for machine learning.** Whether a claim is
paid in full, reduced or denied is decided at random, not learned from any
payer's behaviour. About 15% of claims are denied outright; most of the rest
are reduced by a contractual write-off (CO 45), some also leave a share to the
patient, and some are paid in full. Nothing in a claim predicts its outcome.

That makes the data right for testing that a pipeline reads, joins and totals
claims and remittances correctly, for teaching the transactions, and for
exercising a model's training code, and wrong for training a model you expect
to learn real-world denial patterns. A later version is planned with
published, administrative denial rules (a claim filed too late, missing
required information, lacking a required authorization, or for a service the
plan does not cover), so that outcomes follow documented causes.

Outright denials use administrative reason codes only (16, 27, 29, 96, 197).
Codes appear bare; no code-list descriptions are included.

## Limitations

- Codes come from a short fixed list of common procedure, dental and
  diagnosis codes, so their distribution is not realistic. Fees fall in
  plausible ranges but are random.
- Each file pair has one payer and one billing provider; there is no
  coordination of benefits between payers.
- Names, addresses and identifiers are obvious placeholders. They are kept in
  the X12 files, where the format requires them, and left out of the tables.
- The 835's claim filing indicator is always `CH`, which does not match the
  dental claims' `CI`.

## Rebuilding it

```shell
pip install "x12sdk=={version}"
git clone https://github.com/owgreen-dev/x12sdk && cd x12sdk && git checkout v{version}
python scripts/build_dataset.py --out dataset --seed {seed} --pairs {pairs} --claims-per-pair {claims_per_pair}
```

Or generate your own with any seed and size:

```python
from x12sdk.generate import generate_claim_pair

claim, remittance = generate_claim_pair(seed=7, claims=25, claim_type="837d")
```

## License and citation

Released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
x12sdk itself is Apache-2.0. If you use this data, please credit
"x12sdk synthetic claims and remittances" and link
https://github.com/owgreen-dev/x12sdk.
