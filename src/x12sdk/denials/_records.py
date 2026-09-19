"""
Flattening of 835 adjustments into one record per CAS reason code.

A remittance nests adjustments two levels deep: claim level (loop 2100) and
service line level (loop 2110), and each CAS segment carries up to six
reason/amount pairs. Analysis wants none of that shape — it wants one row per
reason code with the claim context attached, which is what
:func:`iter_adjustments` produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterator, List, Optional, Tuple

from ._categories import categorize

#: Adjustment group codes treated as a denial or payer-side reduction, as
#: opposed to ``PR`` (patient responsibility) and ``CR`` (correction/reversal).
#: Pass your own set to :func:`iter_adjustments` if your analysis differs.
DENIAL_GROUPS: frozenset = frozenset({"CO", "OA", "PI"})

# CAS carries up to six reason/amount/quantity triples per segment.
_CAS_POSITIONS = range(1, 7)


@dataclass(frozen=True)
class Adjustment:
    """
    One CAS reason code, with the claim and line it came from.

    Amounts are the values as adjudicated: ``amount`` is the adjustment, not
    the charge. A positive amount reduces what the payer pays.
    """

    # payer
    payer_name: Optional[str]
    payer_id: Optional[str]

    # claim
    patient_control_number: Optional[str]
    payer_claim_control_number: Optional[str]
    claim_status_code: Optional[str]
    claim_charge_amount: Optional[Decimal]
    claim_payment_amount: Optional[Decimal]
    patient_responsibility_amount: Optional[Decimal]

    # the adjustment itself
    level: str  # "claim" or "line"
    group_code: Optional[str]
    reason_code: Optional[str]
    amount: Decimal
    quantity: Optional[Decimal]
    category: str

    # service line, when level == "line"
    procedure: Optional[str] = None
    revenue_code: Optional[str] = None
    line_charge_amount: Optional[Decimal] = None
    line_payment_amount: Optional[Decimal] = None

    # remittance advice remark codes in scope for this adjustment
    remark_codes: Tuple[str, ...] = field(default_factory=tuple)

    def is_denial(self, denial_groups: frozenset = DENIAL_GROUPS) -> bool:
        """True when the adjustment group is payer-side rather than patient cost share."""
        return self.group_code in denial_groups


def _claim_remark_codes(loop_2100) -> Tuple[str, ...]:
    """Remark codes from the claim-level MIA (inpatient) or MOA (outpatient) segment."""
    codes: List[str] = []
    for segment in (loop_2100.mia_segment, loop_2100.moa_segment):
        if segment is None:
            continue
        for name in type(segment).model_fields:
            if "remark_code" in name:
                value = getattr(segment, name, None)
                if value:
                    codes.append(str(value))
    return tuple(codes)


def _line_remark_codes(loop_2110) -> Tuple[str, ...]:
    """
    Remark codes from a service line's LQ segments.

    LQ01 ``HE`` identifies the remittance advice remark code list; LQ02 carries
    the code.
    """
    codes: List[str] = []
    for segment in getattr(loop_2110, "lq_segment", None) or []:
        if str(getattr(segment, "code_list_qualifier_code", "")).upper() != "HE":
            continue
        value = getattr(segment, "form_identifier", None)
        if value:
            codes.append(str(value))
    return tuple(codes)


def _split_cas(cas_segment) -> Iterator[tuple]:
    """Yields ``(reason_code, amount, quantity)`` for each populated CAS position."""
    for position in _CAS_POSITIONS:
        reason = getattr(cas_segment, f"adjustment_reason_code_{position}", None)
        amount = getattr(cas_segment, f"monetary_amount_{position}", None)
        if reason is None and amount is None:
            continue
        quantity = getattr(cas_segment, f"quantity_{position}", None)
        yield reason, amount, quantity


def iter_adjustments(transaction) -> Iterator[Adjustment]:
    """
    Flattens every CAS adjustment in an 835 into :class:`Adjustment` records.

    :param transaction: A ``HealthCareClaimPayment`` model, as returned by
        :class:`x12sdk.io.X12ModelReader`.
    :return: One record per populated CAS reason code, claim level first then
        each service line, in transaction order.

    >>> from x12sdk.io import X12ModelReader
    >>> from x12sdk.denials import iter_adjustments
    >>> with X12ModelReader(remittance) as reader:      # doctest: +SKIP
    ...     for txn in reader.models():
    ...         rows = list(iter_adjustments(txn))
    """
    payer_n1 = transaction.loop_1000a.n1_segment
    payer_name = getattr(payer_n1, "name", None)
    payer_id = getattr(payer_n1, "identification_code", None)

    for loop_2000 in transaction.loop_2000 or []:
        for loop_2100 in loop_2000.loop_2100 or []:
            clp = loop_2100.clp_segment
            claim_remarks = _claim_remark_codes(loop_2100)
            claim_context = {
                "payer_name": payer_name,
                "payer_id": payer_id,
                "patient_control_number": clp.patient_control_number,
                "payer_claim_control_number": clp.payer_claim_control_number,
                "claim_status_code": clp.claim_status_code,
                "claim_charge_amount": clp.total_claim_charge_amount,
                "claim_payment_amount": clp.claim_payment_amount,
                "patient_responsibility_amount": clp.patient_responsibility_amount,
            }

            for cas in loop_2100.cas_segment or []:
                for reason, amount, quantity in _split_cas(cas):
                    yield Adjustment(
                        level="claim",
                        group_code=cas.adjustment_group_code,
                        reason_code=reason,
                        amount=amount if amount is not None else Decimal("0"),
                        quantity=quantity,
                        category=categorize(reason),
                        remark_codes=claim_remarks,
                        **claim_context,
                    )

            for loop_2110 in getattr(loop_2100, "loop_2110", None) or []:
                svc = loop_2110.svc_segment
                line_remarks = claim_remarks + _line_remark_codes(loop_2110)
                for cas in loop_2110.cas_segment or []:
                    for reason, amount, quantity in _split_cas(cas):
                        yield Adjustment(
                            level="line",
                            group_code=cas.adjustment_group_code,
                            reason_code=reason,
                            amount=amount if amount is not None else Decimal("0"),
                            quantity=quantity,
                            category=categorize(reason),
                            procedure=svc.composite_medical_procedure_identifier_1,
                            revenue_code=getattr(svc, "revenue_code", None),
                            line_charge_amount=svc.line_item_charge_amount,
                            line_payment_amount=svc.line_item_provider_payment_amount,
                            remark_codes=line_remarks,
                            **claim_context,
                        )
