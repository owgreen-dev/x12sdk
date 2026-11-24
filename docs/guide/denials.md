# Denial analytics

An 835 tells you what a payer did to a claim, but in a shape built for
transmission: adjustments nested at claim and service line level, up to six
reason/amount pairs per CAS segment, remark codes in a different segment
again. {mod}`x12sdk.denials` flattens that to one record per reason code and
aggregates it the way a revenue-cycle or payer analytics team asks the
question.

```python
from x12sdk.io import X12ModelReader
from x12sdk.denials import denial_summary, iter_adjustments

with X12ModelReader("remit.835") as reader:
    for transaction in reader.models():
        rows = list(iter_adjustments(transaction))
        for row in denial_summary(rows):
            print(row.payer_name, row.group_code, row.reason_code,
                  row.category, row.claim_count, row.total_amount)
```

- `denial_summary` counts payer-side groups (`CO`, `OA`, `PI`) by default and
  leaves out patient cost share (`PR`), because a deductible is not a
  denial; pass `include_patient_responsibility=True` to keep it.
- Amounts stay `Decimal`, so totals are exact.
- `claim_count` counts distinct claims, so a reason hitting three lines of
  one claim counts once.
- For DataFrame work, install the `pandas` extra and use
  {func}`x12sdk.denials.to_dataframe`.

## Code lists

CARC and RARC **descriptions** are published by X12 and the Washington
Publishing Company and are licensed separately, so **x12sdk ships none of
that text**. What it ships is {func}`~x12sdk.denials.categorize`, x12sdk's own
grouping of reason codes into analysis categories such as `eligibility`,
`authorization`, `duplicate` and `timely_filing`, with anything unmapped
resolving to `other`.

If you need the official wording, obtain the list from
[x12.org/codes](https://x12.org/codes) under whatever licence applies to you
and load it yourself:

```python
from x12sdk.denials import describe, load_code_descriptions

descriptions = load_code_descriptions("carc.csv")   # your file, not ours
for row in describe(denial_summary(rows), descriptions):
    print(row["reason_code"], row["description"], row["total_amount"])
```
