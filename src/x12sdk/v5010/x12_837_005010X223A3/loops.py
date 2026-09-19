"""
loops.py

Models the loops, or logical segment groupings, for the HealthCare Claims Institutional 837 005010X223A3 transaction set.
The HealthCare Claims Institutional set organizes loops into a hierarchical and nested model.

-- Header
    -- Loop 1000A (Submitter Name)
        -- Loop 1000B (Receiver Name)
    -- Loop 2000A (Billing Provider)
        -- Loop 2010AA (Billing Provider Name)
        -- Loop 2010AB (Pay to Address)
        -- Loop 2010AC (Pay to Plan Name)
        -- Loop 2000B (Subscriber)
            -- Loop 2010BA (Subscriber Name)
            -- Loop 2010BB (Payer Name)
        -- Loop 2000C (Patient Loop)
            -- Loop 2010CA (Patient Name)
            -- Loop 2300 (Claim Information)
                -- Loop 2310A (Attending Provider Name)
                -- Loop 2310B (Operating Physician Name)
                -- Loop 2310C (Other Operating Physician Name)
                -- Loop 2310D (Rendering Provider Name)
                -- Loop 2310E (Service Facility Location Name)
                -- Loop 2310F (Referring Provider Name)
                -- Loop 2320 (Other Subscriber Information)
                    -- Loop 2330A (Other Subscriber Name)
                    -- Loop 2330B (Other Payer Name)
                    -- Loop 2330C (Other Payer Attending Provider Name)
                    -- Loop 2330D (Other Payer Operating Physician Name)
                    -- Loop 2330E (Other Payer Other Operating Physician Name)
                    -- Loop 2330F (Other Payer Service Facility Location)
                    -- Loop 2330G (Other Payer Rendering Provider Name)
                    -- Loop 2330H (Other Payer Referring Provider Name)
                    -- Loop 2330I (Other Payer Billing Provider Name)
                -- Loop 2400 (Service Line)
                    -- Loop 2410 (Drug Identification Name)
                    -- Loop 2420A (Operating Physician Name)
                    -- Loop 2420B (Other Operating Physician Name)
                    -- Loop 2420C (Rendering Provider Name)
                    -- Loop 2420D (Referring Provider Name)
                    -- Loop 2430 (Line Adjudication Information)
-- Footer

The Header and Footer components are not "loops" per the specification, but are included to standardize and simplify
transactional modeling and processing.
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.v5010.segments import (
    CasSegment,
    Cl1Segment,
    ClmSegment,
    CtpSegment,
    CurSegment,
    DmgSegment,
    FrmSegment,
    HcpSegment,
    HiSegment,
    K3Segment,
    LinSegment,
    LqSegment,
    LxSegment,
    MiaSegment,
    MoaSegment,
    N3Segment,
    N4Segment,
    OiSegment,
    PatSegment,
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
    Loop2010AcNm1Segment,
    Loop2010AcRefSegment,
    Loop2010BaNm1Segment,
    Loop2010BaRefSegment,
    Loop2010BbNm1Segment,
    Loop2010BbRefSegment,
    Loop2010CaNm1Segment,
    Loop2010CaRefSegment,
    Loop2300AmtSegment,
    Loop2300BRefSegment,
    Loop2300Cn1Segment,
    Loop2300CrcEpSdtRefferal,
    Loop2300DtpSegment,
    Loop2300HcpSegment,
    Loop2300NteSegment,
    Loop2300PwkSegment,
    Loop2300RefSegment,
    Loop2310ANm1Segment,
    Loop2310APrvSegment,
    Loop2310ARefSegment,
    Loop2310BNm1Segment,
    Loop2310BRefSegment,
    Loop2310CNm1Segment,
    Loop2310CRefSegment,
    Loop2310DNm1Segment,
    Loop2310DRefSegment,
    Loop2310ENm1Segment,
    Loop2310ERefSegment,
    Loop2310FNm1Segment,
    Loop2310FRefSegment,
    Loop2320AmtSegment,
    Loop2320SbrSegment,
    Loop2330aNm1Segment,
    Loop2330aRefSegment,
    Loop2330BDtpSegment,
    Loop2330bNm1Segment,
    Loop2330cNm1Segment,
    Loop2330cRefSegment,
    Loop2330dNm1Segment,
    Loop2330dRefSegment,
    Loop2330eNm1Segment,
    Loop2330eRefSegment,
    Loop2330fNm1Segment,
    Loop2330fRefSegment,
    Loop2330gNm1Segment,
    Loop2330gRefSegment,
    Loop2330HNm1Segment,
    Loop2330HRefSegment,
    Loop2330INm1Segment,
    Loop2330IRefSegment,
    Loop2400AmtSegment,
    Loop2400DtpSegment,
    Loop2400NteSegment,
    Loop2400PwkSegment,
    Loop2400RefSegment,
    Loop2410RefSegment,
    Loop2420ANm1Segment,
    Loop2420ARefSegment,
    Loop2420BNm1Segment,
    Loop2420BRefSegment,
    Loop2420CNm1Segment,
    Loop2420CRefSegment,
    Loop2420DNm1Segment,
    Loop2420DRefSegment,
    Loop2430AmtSegment,
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
    ref_segment: Loop2010AaRefSegment
    per_segment: Optional[List[Loop2010AaPerSegment]] = Field(
        None, min_length=0, max_length=2
    )


class Loop2010Ab(X12SegmentGroup):
    """
    Loop 2010AB - Pay to Address
    """

    nm1_segment: Loop2010AbNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment


class Loop2010Ac(X12SegmentGroup):
    """
    Loop 2010AC - Pay to Plan
    """

    nm1_segment: Loop2010AcNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: List[Loop2010AcRefSegment] = Field(min_length=1, max_length=2)


class Loop2010Ba(X12SegmentGroup):
    """
    Loop 2010BA - Subscriber Name
    """

    nm1_segment: Loop2010BaNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    dmg_segment: Optional[DmgSegment] = None
    # min_length=0 but no default made this required: constructing a subscriber
    # meant passing ref_segment=[] by hand. The parser already pre-seeds a list.
    ref_segment: List[Optional[Loop2010BaRefSegment]] = Field(
        default_factory=list, min_length=0, max_length=2
    )


class Loop2010Bb(X12SegmentGroup):
    """
    Loop 2010Bb - Payer Name
    """

    nm1_segment: Loop2010BbNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop2010BbRefSegment]] = None


class Loop2330I(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Billing Provider
    """

    nm1_segment: Loop2330INm1Segment
    ref_segment: List[Loop2330IRefSegment] = Field(min_length=1, max_length=2)


class Loop2330H(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Referring Provider
    """

    nm1_segment: Loop2330HNm1Segment
    ref_segment: List[Loop2330HRefSegment] = Field(min_length=1, max_length=3)


class Loop2330G(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Rendering Provider
    """

    nm1_segment: Loop2330gNm1Segment
    ref_segment: List[Loop2330gRefSegment] = Field(min_length=1, max_length=3)


class Loop2330F(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Service Facility Location
    """

    nm1_segment: Loop2330fNm1Segment
    ref_segment: List[Loop2330fRefSegment] = Field(min_length=1, max_length=3)


class Loop2330E(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Other Operating Physician
    """

    nm1_segment: Loop2330eNm1Segment
    ref_segment: List[Loop2330eRefSegment] = Field(min_length=1, max_length=3)


class Loop2330D(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Operating Physician
    """

    nm1_segment: Loop2330dNm1Segment
    ref_segment: List[Loop2330dRefSegment] = Field(min_length=1, max_length=3)


class Loop2330C(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Attending Provider
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
    ref_segment: Optional[List[Loop2300BRefSegment]] = Field(
        None, min_length=0, max_length=6
    )


class Loop2330A(X12SegmentGroup):
    """
    Claim - Other Subscriber Name
    """

    nm1_segment: Loop2330aNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[Loop2330aRefSegment] = None


class Loop2320(X12SegmentGroup):
    """
    Claim Other subscriber information
    """

    sbr_segment: Loop2320SbrSegment
    cas_segment: Optional[List[CasSegment]] = Field(None, min_length=0, max_length=5)
    amt_segment: Optional[List[Loop2320AmtSegment]] = Field(
        None, min_length=0, max_length=3
    )
    oi_segment: OiSegment
    mia_segment: Optional[MiaSegment] = None
    moa_segment: Optional[MoaSegment] = None
    loop_2330a: Optional[Loop2330A] = None
    loop_2330b: Optional[Loop2330B] = None
    loop_2330c: Optional[Loop2330C] = None
    loop_2330d: Optional[Loop2330D] = None
    loop_2330e: Optional[Loop2330E] = None
    loop_2330f: Optional[Loop2330F] = None
    loop_2330g: Optional[Loop2330G] = None
    loop_2330h: Optional[Loop2330H] = None
    loop_2330i: Optional[Loop2330I] = None

    _validate_amt_segments = model_validator(mode="after")(validate_duplicate_amt_codes)


class Loop2310F(X12SegmentGroup):
    """
    Claim referring provider
    """

    nm1_segment: Loop2310FNm1Segment
    ref_segment: Optional[List[Loop2310FRefSegment]] = Field(
        None, min_length=0, max_length=3
    )


class Loop2310E(X12SegmentGroup):
    """
    Service Facility Location
    """

    nm1_segment: Loop2310ENm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2310ERefSegment]] = Field(
        None, min_length=0, max_length=3
    )


class Loop2310D(X12SegmentGroup):
    """
    Claim Rendering Provider
    """

    nm1_segment: Loop2310DNm1Segment
    ref_segment: Optional[List[Loop2310DRefSegment]] = None


class Loop2310C(X12SegmentGroup):
    """
    Claim Other Operating Physician Name
    """

    nm1_segment: Optional[Loop2310CNm1Segment] = None
    ref_segment: Optional[List[Loop2310CRefSegment]] = Field(
        None, min_length=0, max_length=3
    )


class Loop2310B(X12SegmentGroup):
    """
    Claim Operating Physician Name
    """

    nm1_segment: Loop2310BNm1Segment
    ref_segment: Optional[List[Loop2310BRefSegment]] = Field(
        None, min_length=0, max_length=4
    )


class Loop2310A(X12SegmentGroup):
    """
    Claim Referring Provider
    """

    nm1_segment: Loop2310ANm1Segment
    prv_segment: Optional[Loop2310APrvSegment] = None
    ref_segment: Optional[List[Loop2310ARefSegment]] = Field(
        None, min_length=0, max_length=4
    )


class Loop2440(X12SegmentGroup):
    """
    Form Identification Code
    """

    lq_segment: LqSegment
    frm_segment: List[FrmSegment] = Field(min_length=1, max_length=99)


class Loop2430(X12SegmentGroup):
    """
    Claim Service Line - Adjudication Information
    """

    svd_segment: SvdSegment
    cas_segment: Optional[List[CasSegment]] = Field(None, min_length=0, max_length=5)
    dtp_segment: Loop2430DtpSegment
    amt_segment: Optional[Loop2430AmtSegment] = None


class Loop2420D(X12SegmentGroup):
    """
    Claim Service Line - Referring Provider Name
    """

    nm1_segment: Loop2420DNm1Segment
    ref_segment: Optional[List[Loop2420DRefSegment]] = Field(
        None, min_length=0, max_length=20
    )


class Loop2420C(X12SegmentGroup):
    """
    Claim Service Line - Rendering Provider
    """

    nm1_segment: Loop2420CNm1Segment
    ref_segment: Optional[List[Loop2420CRefSegment]] = Field(
        None, min_length=0, max_length=3
    )


class Loop2420B(X12SegmentGroup):
    """
    Claim Service Line - Other Operating Physician
    """

    nm1_segment: Loop2420BNm1Segment
    ref_segment: Optional[List[Loop2420BRefSegment]] = Field(
        None, min_length=0, max_length=4
    )


class Loop2420A(X12SegmentGroup):
    """
    Claim Service Line - Operating Physician
    """

    nm1_segment: Loop2420ANm1Segment
    ref_segment: Optional[List[Loop2420ARefSegment]] = Field(
        None, min_length=0, max_length=20
    )


class Loop2410(X12SegmentGroup):
    """
    Claim Service Line - Drug Identification
    """

    lin_segment: LinSegment
    ctp_segment: CtpSegment
    ref_segment: Loop2410RefSegment


class Loop2400(X12SegmentGroup):
    """
    Claim - Service Line
    """

    lx_segment: LxSegment
    sv2_segment: Sv2Segment
    pwk_segment: Optional[List[Loop2400PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    dtp_segment: Optional[Loop2400DtpSegment] = None
    ref_segment: Optional[List[Loop2400RefSegment]] = Field(
        None, min_length=0, max_length=3
    )
    amt_segment: Optional[List[Loop2400AmtSegment]] = Field(
        None, min_length=0, max_length=2
    )
    nte_segment: Optional[Loop2400NteSegment] = None
    hcp_segment: Optional[HcpSegment] = None
    loop_2410: Optional[Loop2410] = None
    loop_2420a: Optional[Loop2420A] = None
    loop_2420b: Optional[Loop2420B] = None
    loop_2420c: Optional[Loop2420C] = None
    loop_2420d: Optional[Loop2420D] = None
    loop_2430: Optional[List[Loop2430]] = Field(None, min_length=0, max_length=15)
    loop_2440: Optional[List[Loop2440]] = Field(None, min_length=0)


class Loop2300(X12SegmentGroup):
    """
    Loop 2300 - Claims
    """

    clm_segment: ClmSegment
    dtp_segment: List[Loop2300DtpSegment] = Field(min_length=1, max_length=4)
    cl1_segment: Cl1Segment
    pwk_segment: Optional[List[Loop2300PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    cn1_segment: Optional[Loop2300Cn1Segment] = None
    amt_segment: Optional[Loop2300AmtSegment] = None
    ref_segment: Optional[List[Loop2300RefSegment]] = Field(
        None, min_length=0, max_length=16
    )
    k3_segment: Optional[List[K3Segment]] = Field(None, min_length=0, max_length=10)
    nte_segment: Optional[List[Loop2300NteSegment]] = Field(
        None, min_length=0, max_length=11
    )
    crc_segment: Optional[Loop2300CrcEpSdtRefferal] = None
    hi_segment: List[HiSegment] = Field(min_length=1, max_length=20)
    hcp_segment: Optional[Loop2300HcpSegment] = None
    loop_2310a: Optional[Loop2310A] = None
    loop_2310b: Optional[Loop2310B] = None
    loop_2310c: Optional[Loop2310C] = None
    loop_2310d: Optional[Loop2310D] = None
    loop_2310e: Optional[Loop2310E] = None
    loop_2310f: Optional[Loop2310F] = None
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
    ref_segment: Optional[List[Loop2010CaRefSegment]] = Field(
        None, min_length=0, max_length=2
    )


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
    pat_segment: Optional[PatSegment] = None
    loop_2010ba: Loop2010Ba
    loop_2010bb: Loop2010Bb
    loop_2300: Optional[List[Loop2300]] = Field(None, min_length=0, max_length=100)
    loop_2000c: Optional[List[Loop2000C]] = None


class Loop2000A(X12SegmentGroup):
    """
    Loop 2000A - Billing Provider
    """

    hl_segment: Loop2000AHlSegment
    prv_segment: Optional[Loop2000APrvSegment] = None
    cur_segment: Optional[CurSegment] = None
    loop_2010aa: Loop2010Aa
    loop_2010ab: Optional[Loop2010Ab] = None
    loop_2010ac: Optional[Loop2010Ac] = None
    loop_2000b: List[Loop2000B]


class Header(X12SegmentGroup):
    """
    Transaction Header Information
    """

    st_segment: HeaderStSegment
    bht_segment: HeaderBhtSegment


class Footer(X12SegmentGroup):
    """
    Transaction Footer Information
    """

    se_segment: SeSegment
