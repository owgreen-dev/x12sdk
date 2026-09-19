"""
loops.py

Models the loops, or logical segment groupings, for the HealthCare Claims Professional 837 004010X096A1 transaction set.
The HealthCare Claims Professional set organizes loops into a hierarchical and nested model.

-- Header
    -- Loop 1000A (Submitter Name)
    -- Loop 1000B (Receiver Name)
    -- Loop 2000A (Billing / Pay to Provider)
        -- Loop 2010AA (Billing Provider Name)
        -- Loop 2010AB (Pay to Provider Name)
    -- Loop 2000B (Subscriber)
        -- Loop 2010BA (Subscriber Name)
        -- Loop 2010BB (Credit/Debit Card Account Holder)
        -- Loop 2010BC (Payer Name)
        -- Loop 2010BD (Responsible Party Name)
        -- Loop 2000C (Patient)
            -- Loop 2010CA (Patient Name_
            -- Loop 2300 (Claim)
                -- Loop 2305 (Home Healthcare Plan Information)
                -- Loop 2310A (Referring Provider Name)
                -- Loop 2310B (Rendering Provider)
                -- Loop 2310C (Service Provider)
                -- Loop 2310D (Service Facility)
                -- Loop 2310E (Supervising Provider)
                -- Loop 2320 (Other Subscriber)
                -- Loop 2400 (Service Line)
                    -- Loop 2410 (Drug Identification)
                    -- Loop 2420a (Rendering Provider)
                    -- Loop 2420b (Purchased Service Provider)
                    -- Loop 2420c (Service Facility)
                    -- Loop 2420d (Supervising Provider)
                    -- Loop 2420e (Ordering Provider)
                    -- Loop 2420f (Referring Provider)
                    -- Loop 2420g (Other Payer)
                    -- Loop 2430 (Line Adjudication)
                    -- Loop 2440 (Form Identification)


-- Footer

The Header and Footer components are not "loops" per the specification, but are included to standardize and simplify
transactional modeling and processing.
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.v4010.segments import (
    CasSegment,
    Cl1Segment,
    ClmSegment,
    Cr6Segment,
    CtpSegment,
    CurSegment,
    DmgSegment,
    HcpSegment,
    HiSegment,
    K3Segment,
    LinSegment,
    LxSegment,
    MoaSegment,
    N3Segment,
    N4Segment,
    OiSegment,
    SeSegment,
    Sv2Segment,
    SvdSegment,
)
from x12sdk.validators import (
    validate_duplicate_amt_codes,
    validate_duplicate_date_qualifiers,
)

from .segments import (
    HeaderBhtSegment,
    HeaderRefSegment,
    HeaderStSegment,
    Loop1000ANm1Segment,
    Loop1000APerSegment,
    Loop1000BNm1Segment,
    Loop2000AHlSegment,
    Loop2000APrvSegment,
    Loop2000BHlSegment,
    Loop2000BSbrSegment,
    Loop2000CHlSegment,
    Loop2000CPatSegment,
    Loop2010AaNm1Segment,
    Loop2010AaPerSegment,
    Loop2010AaRefSegment,
    Loop2010AbNm1Segment,
    Loop2010AbRefSegment,
    Loop2010BaNm1Segment,
    Loop2010BaRefSegment,
    Loop2010BbNm1Segment,
    Loop2010BbRefSegment,
    Loop2010BcNm1Segment,
    Loop2010BcRefSegment,
    Loop2010BdNm1Segment,
    Loop2010CaNm1Segment,
    Loop2010CaRefSegment,
    Loop2300AmtSegment,
    Loop2300Cn1Segment,
    Loop2300CrcSegment,
    Loop2300DtpSegment,
    Loop2300NteSegment,
    Loop2300PwkSegment,
    Loop2300QtySegment,
    Loop2300RefSegment,
    Loop2305Cr7Segment,
    Loop2305HsdSegment,
    Loop2310ANm1Segment,
    Loop2310APrvSegment,
    Loop2310ARefSegment,
    Loop2310BNm1Segment,
    Loop2310BRefSegment,
    Loop2310CNm1Segment,
    Loop2310CRefSegment,
    Loop2310ENm1Segment,
    Loop2310ERefSegment,
    Loop2320AmtSegment,
    Loop2320SbrSegment,
    Loop2330aNm1Segment,
    Loop2330aRefSegment,
    Loop2330BDtpSegment,
    Loop2330bNm1Segment,
    Loop2330BRefSegment,
    Loop2330cNm1Segment,
    Loop2330cRefSegment,
    Loop2330dNm1Segment,
    Loop2330dRefSegment,
    Loop2330eNm1Segment,
    Loop2330eRefSegment,
    Loop2330fNm1Segment,
    Loop2330fRefSegment,
    Loop2330HNm1Segment,
    Loop2330HRefSegment,
    Loop2400AmtSegment,
    Loop2400DtpSegment,
    Loop2400PwkSegment,
    Loop2410RefSegment,
    Loop2420ANm1Segment,
    Loop2420ARefSegment,
    Loop2420BNm1Segment,
    Loop2420BRefSegment,
    Loop2420CNm1Segment,
    Loop2420CRefSegment,
    Loop2430DtpSegment,
)


class Loop1000A(X12SegmentGroup):
    """
    Loop 1000A - Submitter Name
    """

    nm1_segment: Loop1000ANm1Segment
    per_segment: List[Loop1000APerSegment] = Field(min_length=1, max_length=2)


class Loop1000B(X12SegmentGroup):
    """
    Loop 1000B - Receiver Name
    """

    nm1_segment: Loop1000BNm1Segment


class Loop2010Aa(X12SegmentGroup):
    """
    Loop 2010AA - Billing Provider Name
    """

    nm1_segment: Loop2010AaNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2010AaRefSegment]] = Field(None, max_length=16)
    per_segment: Optional[List[Loop2010AaPerSegment]] = Field(None, max_length=2)


class Loop2010Ab(X12SegmentGroup):
    """
    Loop 2010AB - Pay to Provider Name
    """

    nm1_segment: Loop2010AbNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2010AbRefSegment]] = Field(None, max_length=5)


class Loop2010Ba(X12SegmentGroup):
    """
    Loop 2010BA - Subscriber Name
    """

    nm1_segment: Loop2010BaNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    dmg_segment: Optional[DmgSegment] = None
    ref_segment: Optional[List[Loop2010BaRefSegment]] = Field(None, max_length=5)


class Loop2010Bb(X12SegmentGroup):
    """
    Loop 2010Bb - Credit/Debit Card Holder Name
    """

    nm1_segment: Loop2010BbNm1Segment
    ref_segment: Optional[List[Loop2010BbRefSegment]] = Field(None, max_length=2)


class Loop2010Bc(X12SegmentGroup):
    """
    Loop 2010Bc - Payer Name
    """

    nm1_segment: Loop2010BcNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop2010BcRefSegment]] = None


class Loop2010Bd(X12SegmentGroup):
    """
    Loop 2010Bd - Responsible Party Name
    """

    nm1_segment: Loop2010BdNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None


class Loop2305(X12SegmentGroup):
    """
    Home Health Care Plan Information
    """

    cr7_segment: Loop2305Cr7Segment
    hsd_segment: Optional[List[Loop2305HsdSegment]] = Field(None, max_length=12)


class Loop2330H(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Service Facility Provider
    """

    nm1_segment: Loop2330HNm1Segment
    ref_segment: List[Loop2330HRefSegment] = Field(min_length=1, max_length=3)


class Loop2330F(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Other Provider
    """

    nm1_segment: Loop2330fNm1Segment
    ref_segment: List[Loop2330fRefSegment] = Field(min_length=1, max_length=3)


class Loop2330E(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Operating Provider
    """

    nm1_segment: Loop2330eNm1Segment
    ref_segment: List[Loop2330eRefSegment] = Field(min_length=1, max_length=3)


class Loop2330D(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Attending Provider
    """

    nm1_segment: Loop2330dNm1Segment
    ref_segment: List[Loop2330dRefSegment] = Field(min_length=1, max_length=3)


class Loop2330C(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Patient Information
    """

    nm1_segment: Loop2330cNm1Segment
    ref_segment: List[Loop2330cRefSegment] = Field(min_length=1, max_length=3)


class Loop2330B(X12SegmentGroup):
    """
    Claim - Other Payer Name
    """

    nm1_segment: Loop2330bNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    dtp_segment: Optional[Loop2330BDtpSegment] = None
    ref_segment: Optional[List[Loop2330BRefSegment]] = Field(None, max_length=2)


class Loop2330A(X12SegmentGroup):
    """
    Claim - Other Subscriber Name
    """

    nm1_segment: Loop2330aNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop2330aRefSegment]] = Field(None, max_length=3)


class Loop2320(X12SegmentGroup):
    """
    Claim Other subscriber information
    """

    sbr_segment: Loop2320SbrSegment
    cas_segment: Optional[List[CasSegment]] = Field(None, min_length=0, max_length=5)
    amt_segment: Optional[List[Loop2320AmtSegment]] = Field(
        None, min_length=0, max_length=8
    )
    dmg_segment: Optional[DmgSegment] = None
    oi_segment: Optional[OiSegment] = None
    moa_segment: Optional[MoaSegment] = None
    loop_2330a: Optional[Loop2330A] = None
    loop_2330b: Optional[Loop2330B] = None
    loop_2330c: Optional[Loop2330C] = None
    loop_2330d: Optional[Loop2330D] = None
    loop_2330e: Optional[Loop2330E] = None
    loop_2330f: Optional[Loop2330F] = None
    loop_2330h: Optional[Loop2330H] = None

    _validate_amt_segments = model_validator(mode="after")(validate_duplicate_amt_codes)


class Loop2310E(X12SegmentGroup):
    """
    Service Facility Location
    """

    nm1_segment: Loop2310ENm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2310ERefSegment]] = None


class Loop2310C(X12SegmentGroup):
    """
    Other Provider Name
    """

    nm1_segment: Optional[Loop2310CNm1Segment] = None
    ref_segment: Optional[List[Loop2310CRefSegment]] = Field(None, max_length=5)


class Loop2310B(X12SegmentGroup):
    """
    Claim Operating Physician
    """

    nm1_segment: Loop2310BNm1Segment
    ref_segment: Optional[List[Loop2310BRefSegment]] = Field(None, max_length=5)


class Loop2310A(X12SegmentGroup):
    """
    Claim Attending Physican Name
    """

    nm1_segment: Loop2310ANm1Segment
    prv_segment: Optional[Loop2310APrvSegment] = None
    ref_segment: Optional[List[Loop2310ARefSegment]] = Field(None, max_length=5)


class Loop2430(X12SegmentGroup):
    """
    Claim Service Line - Adjudication Information
    """

    svd_segment: SvdSegment
    cas_segment: Optional[List[CasSegment]] = None
    dtp_segment: Loop2430DtpSegment


class Loop2420C(X12SegmentGroup):
    """
    Claim Service Line - Other Provider Name
    """

    nm1_segment: Loop2420CNm1Segment
    ref_segment: Optional[List[Loop2420CRefSegment]] = Field(None, max_length=5)


class Loop2420B(X12SegmentGroup):
    """
    Claim Service Line - Operating Physician Name
    """

    nm1_segment: Loop2420BNm1Segment
    ref_segment: Optional[List[Loop2420BRefSegment]] = Field(None, max_length=5)


class Loop2420A(X12SegmentGroup):
    """
    Claim Service Line - Attending Physician
    """

    nm1_segment: Loop2420ANm1Segment
    ref_segment: Optional[List[Loop2420ARefSegment]] = Field(None, max_length=5)


class Loop2410(X12SegmentGroup):
    """
    Claim Service Line - Drug Identification
    """

    lin_segment: LinSegment
    ctp_segment: CtpSegment
    ref_segment: Optional[Loop2410RefSegment] = None


class Loop2400(X12SegmentGroup):
    """
    Claim - Service Line
    """

    lx_segment: LxSegment
    sv2_segment: Sv2Segment
    pwk_segment: Optional[List[Loop2400PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    dtp_segment: Optional[List[Loop2400DtpSegment]] = Field(None, max_length=2)
    amt_segment: Optional[List[Loop2400AmtSegment]] = Field(None, max_length=2)
    hcp_segment: Optional[HcpSegment] = None
    loop_2410: Optional[Loop2410] = None
    loop_2420a: Optional[Loop2420A] = None
    loop_2420b: Optional[Loop2420B] = None
    loop_2420c: Optional[Loop2420C] = None
    loop_2430: Optional[List[Loop2430]] = None

    _validate_dtp_qualifiers = model_validator(mode="after")(
        validate_duplicate_date_qualifiers
    )


class Loop2300(X12SegmentGroup):
    """
    Loop 2300 - Claims
    """

    clm_segment: ClmSegment
    dtp_segment: Optional[List[Loop2300DtpSegment]] = Field(
        None, min_length=0, max_length=4
    )
    cl1_segment: Optional[Cl1Segment] = None
    pwk_segment: Optional[List[Loop2300PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    cn1_segment: Optional[Loop2300Cn1Segment] = None
    amt_segment: Optional[List[Loop2300AmtSegment]] = Field(None, max_length=5)
    ref_segment: Optional[List[Loop2300RefSegment]] = Field(None, max_length=15)
    k3_segment: Optional[List[K3Segment]] = Field(None, max_length=10)
    nte_segment: Optional[Loop2300NteSegment] = None
    cr6_segment: Optional[Cr6Segment] = None
    crc_segment: Optional[List[Loop2300CrcSegment]] = Field(None, max_length=8)
    hi_segment: Optional[List[HiSegment]] = Field(None, max_length=20)
    qty_segment: Optional[List[Loop2300QtySegment]] = Field(None, max_length=4)
    hcp_segment: Optional[HcpSegment] = None
    loop_2305: Optional[Loop2305] = None
    loop_2310a: Optional[Loop2310A] = None
    loop_2310b: Optional[Loop2310B] = None
    loop_2310c: Optional[Loop2310C] = None
    loop_2310e: Optional[Loop2310E] = None
    loop_2320: Optional[List[Loop2320]] = Field(None, min_length=0, max_length=10)
    loop_2400: List[Loop2400] = Field(min_length=1, max_length=50)

    _validate_dtp_qualifiers = model_validator(mode="after")(
        validate_duplicate_date_qualifiers
    )

    @model_validator(mode="after")
    def validate_claim_amounts(self):
        """
        Validates that CLM02 == SUM(Loop2400.SV102)
        """
        values = self.__dict__
        claim_amount: Decimal = values.get("clm_segment").total_claim_charge_amount
        line_total: Decimal = Decimal("0.0")

        for line in values.get("loop_2400", []):
            line_total += line.sv2_segment.line_item_charge_amount

        if claim_amount != line_total:
            raise ValueError(
                f"Claim Amount {claim_amount} != Service Line Total {line_total}"
            )

        return self


class Loop2010Ca(X12SegmentGroup):
    """
    Loop 2010CA Patient Name
    """

    nm1_segment: Loop2010CaNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    dmg_segment: DmgSegment
    ref_segment: Optional[List[Loop2010CaRefSegment]] = Field(None, max_length=6)


class Loop2000C(X12SegmentGroup):
    """
    Loop 2000C - Patient
    """

    hl_segment: Loop2000CHlSegment
    pat_segment: Loop2000CPatSegment
    loop_2010ca: Loop2010Ca
    loop_2300: Optional[List[Loop2300]] = Field(None, min_length=0, max_length=100)


class Loop2000B(X12SegmentGroup):
    """
    Loop 2000B - Subscriber
    """

    hl_segment: Loop2000BHlSegment
    sbr_segment: Loop2000BSbrSegment
    loop_2010ba: Loop2010Ba
    loop_2010bb: Optional[Loop2010Bb] = None
    loop_2010bc: Loop2010Bc
    loop_2010bd: Optional[Loop2010Bd] = None
    loop_2300: Optional[List[Loop2300]] = Field(None, min_length=0, max_length=100)
    loop_2000c: Optional[List[Loop2000C]] = None


class Loop2000A(X12SegmentGroup):
    """
    Loop 2000A - Billing / Pay to Provider
    """

    hl_segment: Loop2000AHlSegment
    prv_segment: Optional[Loop2000APrvSegment] = None
    cur_segment: Optional[CurSegment] = None
    loop_2010aa: Loop2010Aa
    loop_2010ab: Optional[Loop2010Ab] = None
    loop_2000b: List[Loop2000B]


class Header(X12SegmentGroup):
    """
    Transaction Header Information
    """

    st_segment: HeaderStSegment
    bht_segment: HeaderBhtSegment
    ref_segment: HeaderRefSegment


class Footer(X12SegmentGroup):
    """
    Transaction Footer Information
    """

    se_segment: SeSegment
