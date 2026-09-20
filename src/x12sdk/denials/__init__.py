"""
Denial analytics over 835 remittance advice.

An 835 tells you what a payer did to a claim, but it tells you in a shape
built for transmission: adjustments nested at claim and service line level,
six reason/amount pairs to a CAS segment, remark codes parked in a different
segment again. This package flattens that into one record per reason code and
aggregates it the way a recovery or program integrity analyst asks the
question — which payer denied what, how often, for how much.

```python
from x12sdk.io import X12ModelReader
from x12sdk.denials import denial_summary, iter_adjustments

with X12ModelReader("remit.835") as reader:
    for transaction in reader.models():
        rows = list(iter_adjustments(transaction))
        for row in denial_summary(rows):
            print(row.payer_name, row.reason_code, row.category,
                  row.claim_count, row.total_amount)
```

**On code lists.** CARC and RARC *descriptions* are published by X12 and the
Washington Publishing Company and licensed separately, so x12sdk ships none of
that text. What it ships is :func:`categorize`, which is x12sdk's own grouping
of reason codes into analysis categories, and
:func:`load_code_descriptions`, which reads a list you supply. See
<https://x12.org/codes>.

*Prior art: a CARC/RARC decoder with denial aggregation was proposed for
edi-835-parser in PR #33. This implementation is independent and works from
the 835 models rather than a parsed DataFrame.*
"""

from ._categories import (
    AUTHORIZATION,
    BENEFIT_MAXIMUM,
    BUNDLING,
    CODING,
    CONTRACTUAL,
    COORDINATION_OF_BENEFITS,
    DUPLICATE,
    ELIGIBILITY,
    MEDICAL_NECESSITY,
    MISSING_INFORMATION,
    NON_COVERED,
    OTHER,
    PATIENT_RESPONSIBILITY,
    TIMELY_FILING,
    categorize,
    category_map,
    load_code_descriptions,
)
from ._records import DENIAL_GROUPS, Adjustment, iter_adjustments
from ._summary import (
    FRAME_COLUMNS,
    DenialSummaryRow,
    denial_summary,
    describe,
    to_dataframe,
)

__all__ = [
    "Adjustment",
    "DenialSummaryRow",
    "DENIAL_GROUPS",
    "FRAME_COLUMNS",
    "categorize",
    "category_map",
    "denial_summary",
    "describe",
    "iter_adjustments",
    "load_code_descriptions",
    "to_dataframe",
    # categories
    "AUTHORIZATION",
    "BENEFIT_MAXIMUM",
    "BUNDLING",
    "CODING",
    "CONTRACTUAL",
    "COORDINATION_OF_BENEFITS",
    "DUPLICATE",
    "ELIGIBILITY",
    "MEDICAL_NECESSITY",
    "MISSING_INFORMATION",
    "NON_COVERED",
    "OTHER",
    "PATIENT_RESPONSIBILITY",
    "TIMELY_FILING",
]
