# Pairs and matching

## Matching your own files

```python
from x12sdk.matching import match_claims, match_rows

for match in match_claims("claims.837", ["remit-1.835", "remit-2.835"]):
    print(match.patient_control_number, match.outcome, match.billed, match.paid)
```

Claims and payments join on the patient control number (CLM01 on the 837,
CLP01 on the 835), which is how real files link. Each argument takes a path,
X12 text, a model, or a list of any of those.

Nothing is dropped:

| `outcome` | Meaning |
|---|---|
| `paid` | The payments for the claim net to more than zero |
| `denied` | They net to zero or less |
| `no remittance` | No payment answers the claim |
| `no claim` | A payment for a claim that is not among the 837s given |

Every payment for a number is kept, in order: a payment, a reversal and a
corrected payment all appear on one {class}`~x12sdk.matching.Match`, and
`paid` nets them. {func}`~x12sdk.matching.match_rows` gives the same as flat
rows with {data}`~x12sdk.matching.MATCH_COLUMNS`, for a CSV or a DataFrame.

## Generating matched pairs

A claim and the remittance that answers it can be generated together. Every
claim on the 837 is answered by exactly one claim payment on the 835, with
the same charge, the same procedure on each line, and the same patient, payer
and payee. Outcomes are mixed: some claims paid in full, most reduced by a
contractual write-off, some leaving a share to the patient, and a share
denied outright (`denial_rate`, 0.15 by default). Real pairs are PHI, so this
is the only way to have claims and their outcomes side by side in the open.

```python
from x12sdk.generate import generate_claim_pair

claim, remittance = generate_claim_pair(seed=7, claims=25, claim_type="837d")
```

`claim_type` is `"837p"`, `"837i"` or `"837d"`. To decide the outcome
yourself, give `ClaimSpec`s: the lines and charges are what was submitted,
the adjustments and `status` what the payer decided. The decision reaches the
835 and is kept off the 837:

```python
from x12sdk.generate import ClaimSpec, ServiceLineSpec, denial, generate_claim_pair

spec = [
    ClaimSpec(charge="120.00", status="4",   # denied
              lines=[ServiceLineSpec(charge="120.00", procedure="93000",
                                     adjustments=[denial("CO", "29", "120.00")])]),
]
claim, remittance = generate_claim_pair(seed=1, claims=spec)
```

## The dataset

A prebuilt set of 300 files (30,000 claims with their remittances), with the
claims and service lines as tables, is published as
[x12sdk synthetic claims and remittances](https://huggingface.co/datasets/owgreen-dev/x12sdk)
on Hugging Face. `scripts/build_dataset.py` in the repository rebuilds it byte
for byte.
