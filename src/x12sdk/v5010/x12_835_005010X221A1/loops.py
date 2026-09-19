"""
loops.py

Models the loops, or logical segment groupings, for the Health Care Claim Payment 835 005010X221A1 transaction set model.
The Health Care Claim Payment transaction set organizes loops into a hierarchical and nested model.
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.v5010.segments import (
    BprSegment,
    ClpSegment,
    DtmSegment,
    LxSegment,
    MiaSegment,
    MoaSegment,
    N3Segment,
    N4Segment,
    Nm1Segment,
    PlbSegment,
    RdmSegment,
    SeSegment,
    SvcSegment,
    Ts2Segment,
    Ts3Segment,
)

from .segments import (
    HeaderCurSegment,
    HeaderRefSegment,
    HeaderStSegment,
    HeaderTrnSegment,
    Loop1000AN1Segment,
    Loop1000APerSegment,
    Loop1000ARefSegment,
    Loop1000BN1Segment,
    Loop1000BRefSegment,
    Loop2100AmtSegment,
    Loop2100CasSegment,
    Loop2100DtmSegment,
    Loop2100PerSegment,
    Loop2100QtySegment,
    Loop2100RefSegment,
    Loop2110AmtSegment,
    Loop2110CasSegment,
    Loop2110DtmSegment,
    Loop2110LqSegment,
    Loop2110QtySegment,
    Loop2110RefSegment,
)


class Header(X12SegmentGroup):
    """
    Transaction Header Information
    """

    st_segment: HeaderStSegment
    bpr_segment: BprSegment
    trn_segment: HeaderTrnSegment
    cur_segment: Optional[HeaderCurSegment] = None
    ref_segment: Optional[List[HeaderRefSegment]] = Field(
        None, min_length=0, max_length=2
    )
    dtm_segment: Optional[DtmSegment] = None


class Loop1000A(X12SegmentGroup):
    """
    Loop 1000A - Payer Identification
    """

    n1_segment: Loop1000AN1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop1000ARefSegment]] = Field(
        None, min_length=0, max_length=4
    )
    per_segment: Optional[List[Loop1000APerSegment]] = None


class Loop1000B(X12SegmentGroup):
    """
    Loop 1000B - Payee Identification
    """

    n1_segment: Loop1000BN1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop1000BRefSegment]] = None
    rdm_segment: Optional[RdmSegment] = None


class Loop2110(X12SegmentGroup):
    """
    Loop 2110 - Service Line Payment Information
    """

    svc_segment: SvcSegment
    dtm_segment: Optional[List[Loop2110DtmSegment]] = Field(
        None, min_length=0, max_length=2
    )
    cas_segment: Optional[List[Loop2110CasSegment]] = Field(
        None, min_length=0, max_length=99
    )
    ref_segment: Optional[List[Loop2110RefSegment]] = Field(
        None, min_length=0, max_length=24
    )
    amt_segment: Optional[List[Loop2110AmtSegment]] = Field(
        None, min_length=0, max_length=9
    )
    qty_segment: Optional[List[Loop2110QtySegment]] = Field(
        None, min_length=0, max_length=6
    )
    lq_segment: Optional[List[Loop2110LqSegment]] = Field(
        None, min_length=0, max_length=99
    )


class Loop2100(X12SegmentGroup):
    """
    Loop 2100 - Claim Payment Information
    """

    clp_segment: ClpSegment
    cas_segment: Optional[List[Loop2100CasSegment]] = Field(
        None, min_length=0, max_length=99
    )
    nm1_segment: List[Nm1Segment] = Field(min_length=1, max_length=7)
    mia_segment: Optional[MiaSegment] = None
    moa_segment: Optional[MoaSegment] = None
    ref_segment: Optional[List[Loop2100RefSegment]] = Field(
        None, min_length=0, max_length=15
    )
    dtm_segment: Optional[List[Loop2100DtmSegment]] = Field(
        None, min_length=0, max_length=5
    )
    per_segment: Optional[List[Loop2100PerSegment]] = Field(
        None, min_length=0, max_length=2
    )
    amt_segment: Optional[List[Loop2100AmtSegment]] = Field(
        None, min_length=0, max_length=13
    )
    qty_segment: Optional[List[Loop2100QtySegment]] = Field(
        None, min_length=0, max_length=14
    )
    loop_2110: Optional[List[Loop2110]] = Field(None, min_length=0, max_length=99)

    @model_validator(mode="after")
    def validate_balance(self):
        """
        Validates the claim totals reported in the CLP segment against the adjustments made in CAS segments.
        The balance is calculated as:
            clp.charge amount - cas.adjustments = clp.payment_amount

        CAS segments exist within loops 2100 and 2110
        """
        values = self.__dict__
        clp_segment = values.get("clp_segment")
        if not clp_segment:
            return self
        charge_amount = clp_segment.total_claim_charge_amount
        payment_amount = clp_segment.claim_payment_amount
        adjustment_amount = Decimal("0.0")

        cas_segments = values.get("cas_segment", [])
        for adjustment in cas_segments:
            adjustment_data = adjustment.model_dump()
            for i in range(1, 7, 1):
                amount = adjustment_data.get(f"monetary_amount_{i}")
                adjustment_amount += amount if amount else Decimal("0.0")

        loop_2110 = values.get("loop_2110") or []
        for service_payment in loop_2110:
            adjustments = service_payment.cas_segment or []
            for adjustment in adjustments:
                adjustment_data = adjustment.model_dump()
                for i in range(1, 7, 1):
                    amount = adjustment_data.get(f"monetary_amount_{i}")
                    adjustment_amount += amount if amount else Decimal("0.0")

        if charge_amount - payment_amount != adjustment_amount:
            raise ValueError(
                f"Unable to balance charge amount {charge_amount} paid amount {payment_amount} against adjustments {adjustment_amount}"
            )

        return self


class Loop2000(X12SegmentGroup):
    """
    Loop 2000 - Claim Payment Header Number
    """

    lx_segment: LxSegment
    ts3_segment: Optional[Ts3Segment] = None
    ts2_segment: Optional[Ts2Segment] = None
    loop_2100: List[Loop2100]


class Footer(X12SegmentGroup):
    """
    Transaction Footer Information
    """

    plb_segment: Optional[PlbSegment] = None
    se_segment: SeSegment
