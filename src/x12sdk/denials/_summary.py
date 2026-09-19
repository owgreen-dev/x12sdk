"""
Aggregation of flattened adjustments into a denial view.

The question this answers is the one a recovery or integrity analyst actually
asks: which payer is denying which reason, how often, and for how much.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence, Tuple

from ._records import DENIAL_GROUPS, Adjustment

#: Columns produced by :func:`to_dataframe`, in order.
FRAME_COLUMNS: Tuple[str, ...] = (
    "payer_name",
    "payer_id",
    "patient_control_number",
    "payer_claim_control_number",
    "claim_status_code",
    "level",
    "group_code",
    "reason_code",
    "category",
    "amount",
    "quantity",
    "procedure",
    "revenue_code",
    "claim_charge_amount",
    "claim_payment_amount",
    "patient_responsibility_amount",
    "line_charge_amount",
    "line_payment_amount",
    "remark_codes",
)


@dataclass(frozen=True)
class DenialSummaryRow:
    """One payer/group/reason combination, with its volume and value."""

    payer_name: Optional[str]
    group_code: Optional[str]
    reason_code: Optional[str]
    category: str
    adjustment_count: int
    claim_count: int
    total_amount: Decimal


def denial_summary(
    adjustments: Iterable[Adjustment],
    *,
    denial_groups: frozenset = DENIAL_GROUPS,
    include_patient_responsibility: bool = False,
) -> List[DenialSummaryRow]:
    """
    Aggregates adjustments by payer, adjustment group and reason code.

    By default only payer-side groups are counted (``CO``, ``OA``, ``PI``);
    patient cost share (``PR``) and corrections (``CR``) are excluded, because
    a deductible is not a denial. Set ``include_patient_responsibility`` to
    keep every group.

    ``claim_count`` counts distinct claims, so a reason appearing on three
    lines of one claim counts once. ``adjustment_count`` counts every
    occurrence.

    :return: Rows sorted by ``total_amount`` descending.
    """
    buckets: dict = defaultdict(
        lambda: {"adjustments": 0, "claims": set(), "amount": Decimal("0")}
    )

    for adjustment in adjustments:
        if not include_patient_responsibility and not adjustment.is_denial(
            denial_groups
        ):
            continue
        key = (
            adjustment.payer_name,
            adjustment.group_code,
            adjustment.reason_code,
            adjustment.category,
        )
        bucket = buckets[key]
        bucket["adjustments"] += 1
        bucket["amount"] += adjustment.amount or Decimal("0")
        claim_id = (
            adjustment.payer_claim_control_number or adjustment.patient_control_number
        )
        if claim_id is not None:
            bucket["claims"].add(claim_id)

    rows = [
        DenialSummaryRow(
            payer_name=payer,
            group_code=group,
            reason_code=reason,
            category=category,
            adjustment_count=bucket["adjustments"],
            claim_count=len(bucket["claims"]),
            total_amount=bucket["amount"],
        )
        for (payer, group, reason, category), bucket in buckets.items()
    ]
    rows.sort(key=lambda row: (-row.total_amount, str(row.reason_code)))
    return rows


def describe(rows: Sequence[DenialSummaryRow], descriptions: dict) -> List[dict]:
    """
    Attaches descriptions from a code list **you** loaded.

    x12sdk ships no CARC/RARC text; see
    :func:`x12sdk.denials.load_code_descriptions`.

    :param rows: Output of :func:`denial_summary`.
    :param descriptions: Mapping of code to description.
    :return: One dict per row with a ``description`` key added.
    """
    described = []
    for row in rows:
        entry = row.__dict__.copy()
        code = (row.reason_code or "").strip().upper()
        entry["description"] = descriptions.get(code)
        described.append(entry)
    return described


def to_dataframe(adjustments: Iterable[Adjustment]):
    """
    Returns the adjustments as a pandas ``DataFrame``.

    Requires the optional pandas dependency: ``pip install 'x12sdk[pandas]'``.
    Amounts stay as ``Decimal`` so totals are exact; cast them yourself if you
    need float maths.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "to_dataframe requires pandas. Install it with: "
            "pip install 'x12sdk[pandas]'"
        ) from exc

    records = [
        {
            column: (
                ",".join(getattr(adjustment, column))
                if column == "remark_codes"
                else getattr(adjustment, column)
            )
            for column in FRAME_COLUMNS
        }
        for adjustment in adjustments
    ]
    return pd.DataFrame.from_records(records, columns=list(FRAME_COLUMNS))
