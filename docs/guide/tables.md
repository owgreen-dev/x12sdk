# Tables: an 835 or 837 as rows

The most common thing anyone does with an 835 is put it in a spreadsheet. An
X12 file is nested loops, so x12sdk flattens it to **one row per service
line**, with fixed columns.

```shell
x12sdk-table remit.835 -o remit.csv
x12sdk-table claims.837 -o claims.csv
x12sdk-table remit.835 > remit.csv              # without -o, to standard output
```

From Python:

```python
from x12sdk.tables import read_lines, to_dataframe, write_csv

rows = read_lines("remit.835")        # a list of dicts, one per service line
frame = to_dataframe("remit.835")     # pandas: pip install "x12sdk[pandas]"

with open("remit.csv", "w", newline="") as out:
    write_csv("remit.835", out)
```

Each function accepts a path, X12 text, a model from
{class}`~x12sdk.io.X12ModelReader`, or a list of models.
{func}`~x12sdk.tables.iter_lines` yields the same rows one at a time.

## What an 835 row holds

One row per paid service line (SVC): the payment (payer, payee, trace
number, method, amount and date), the claim (patient control number, status,
payer claim number, charge, payment and patient share), the patient, the
procedure and its modifiers, what the line was charged and paid, units, the
service date, and the adjustments:

- totalled by group: `co_amount` (contractual), `pr_amount` (patient
  responsibility), `oa_amount`, `pi_amount`, `cr_amount`;
- and every one listed in `adjustment_codes` as `GROUP-REASON`, for example
  `CO-45;PR-2`;
- with the line's remark codes in `remark_codes`.

The full list is {data}`x12sdk.tables.REMITTANCE_COLUMNS`.

## What an 837 row holds

One row per billed line, for professional, institutional and dental claims
alike: the billing provider, payer, subscriber and patient (with whether the
patient is a dependent), the claim's charge, facility code, frequency and
diagnoses, and the line's procedure, modifiers, charge, units and date, with
the revenue code on institutional claims and the tooth and surfaces on
dental ones. The full list is
{data}`x12sdk.tables.CLAIM_COLUMNS`.

## Joining claims to payments

Claim rows and remittance rows share `patient_control_number` (CLM01 on the
837, CLP01 on the 835), which is how real files link. For the join done for
you, outcomes included, see [Pairs and matching](matching.md).

## Rules worth knowing

- **The columns are fixed**, not inferred from the file, so a pipeline
  built on them does not change shape with its input.
- **Amounts are `Decimal`** in Python, so totals are exact, and plain
  numbers in the CSV.
- **A file holds one kind.** An interchange that mixes 835 and 837
  transactions is refused by `to_dataframe` and `write_csv`, because their
  columns differ; filter `read_lines` on `transaction_set` to split it.
- **5010 only.** A 4010 file is reported as unsupported rather than read
  wrongly.

For one row per *adjustment* rather than per line, and summaries by reason
code, see [Denial analytics](denials.md).
