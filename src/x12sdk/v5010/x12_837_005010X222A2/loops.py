"""
loops.py

Models the loops, or logical segment groupings, for the HealthCare Claims Professional 837 005010X222A2 transaction set.
The HealthCare Claims Professional set organizes loops into a hierarchical and nested model.

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
                -- Loop 2310A (Referring Provider Name)
                -- Loop 2310B (Rendering Provider Name)
                -- Loop 2310C (Service Facility Location Name)
                -- Loop 2310D (Supervising Provider Name)
                -- Loop 2310E (Ambulance Pickup Location)
                -- Loop 2310F (Ambulance Dropoff Location)
                -- Loop 2320 (Other Subscriber Information)
                    -- Loop 2330A (Other Subscriber Name)
                    -- Loop 2330B (Other Payer Name)
                    -- Loop 2330C (Other Payer Referring Provider Name)
                    -- Loop 2330D (Other Payer Rendering Provider Name)
                    -- Loop 2330E (Other Payer Service Facility Location)
                    -- Loop 2330F (Other Payer Supervising Provider Name)
                    -- Loop 2330G (Other Payer Billing Provider Name)
                -- Loop 2400 (Service Line)
                    -- Loop 2410 (Drug Identification Name)
                    -- Loop 2420A (Rendering Provider Name)
                    -- Loop 2420B (Purchased Service Provider Name)
                    -- Loop 2420C (Service Facility Location Name)
                    -- Loop 2420D (Supervising Provider Name)
                    -- Loop 2420E (Ordering Provider Name)
                    -- Loop 2420F (Referring Provider Name)
                    -- Loop 2420G (Ambulance Pickup Location)
                    -- Loop 2420H (Ambulance Dropoff Location)
                    -- Loop 2430 (Line Adjudication Information)
                    -- Loop 2440 (Form Identification)
-- Footer

The Header and Footer components are not "loops" per the specification, but are included to standardize and simplify
transactional modeling and processing.
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.v5010.segments import (
    AmtSegment,
    CasSegment,
    ClmSegment,
    Cr1Segment,
    Cr2Segment,
    Cr3Segment,
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
    MeaSegment,
    MoaSegment,
    N3Segment,
    N4Segment,
    OiSegment,
    PatSegment,
    Ps1Segment,
    RefSegment,
    SeSegment,
    Sv1Segment,
    Sv5Segment,
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
    Loop2010BaNm1Segment,
    Loop2010BaPerSegment,
    Loop2010BbNm1Segment,
    Loop2010BbRefSegment,
    Loop2010CaNm1Segment,
    Loop2010CaPerSegment,
    Loop2010CaRefSegment,
    Loop2300AmtSegment,
    Loop2300BRefSegment,
    Loop2300Cn1Segment,
    Loop2300CrcSegment,
    Loop2300DtpSegment,
    Loop2300NteSegment,
    Loop2300PwkSegment,
    Loop2300RefSegment,
    Loop2310ANm1Segment,
    Loop2310ARefSegment,
    Loop2310BNm1Segment,
    Loop2310BPrvSegment,
    Loop2310BRefSegment,
    Loop2310CNm1Segment,
    Loop2310CPerSegment,
    Loop2310CRefSegment,
    Loop2310DNm1Segment,
    Loop2310DRefSegment,
    Loop2310ENm1Segment,
    Loop2310FNm1Segment,
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
    Loop2400AmtSegment,
    Loop2400Cn1Segment,
    Loop2400CrcSegment,
    Loop2400DtpSegment,
    Loop2400NteSegment,
    Loop2400PwkSegment,
    Loop2400QtySegment,
    Loop2400RefSegment,
    Loop2410RefSegment,
    Loop2420ANm1Segment,
    Loop2420APrvSegment,
    Loop2420ARefSegment,
    Loop2420BNm1Segment,
    Loop2420BRefSegment,
    Loop2420CNm1Segment,
    Loop2420CRefSegment,
    Loop2420DNm1Segment,
    Loop2420DRefSegment,
    Loop2420ENm1Segment,
    Loop2420EPerSegment,
    Loop2420ERefSegment,
    Loop2420FNm1Segment,
    Loop2420FRefSegment,
    Loop2420GNm1Segment,
    Loop2420HNm1Segment,
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
    ref_segment: List[Loop2010AaRefSegment] = Field(min_length=1, max_length=3)
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
    ref_segment: List[Loop2010AaRefSegment] = Field(min_length=1, max_length=2)


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
    ref_segment: List[Optional[RefSegment]] = Field(
        default_factory=list, min_length=0, max_length=2
    )
    per_segment: Optional[Loop2010BaPerSegment] = None


class Loop2010Bb(X12SegmentGroup):
    """
    Loop 2010Bb - Payer Name
    """

    nm1_segment: Loop2010BbNm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop2010BbRefSegment]] = None


class Loop2330G(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Billing Provider
    """

    nm1_segment: Loop2330gNm1Segment
    ref_segment: List[Loop2330gRefSegment] = Field(min_length=1, max_length=3)


class Loop2330F(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Supervising Provider
    """

    nm1_segment: Loop2330fNm1Segment
    ref_segment: List[Loop2330fRefSegment] = Field(min_length=1, max_length=3)


class Loop2330E(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Service Facility Location
    """

    nm1_segment: Loop2330eNm1Segment
    ref_segment: List[Loop2330eRefSegment] = Field(min_length=1, max_length=3)


class Loop2330D(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Rendering Provider
    """

    nm1_segment: Loop2330dNm1Segment
    ref_segment: List[Loop2330dRefSegment] = Field(min_length=1, max_length=3)


class Loop2330C(X12SegmentGroup):
    """
    Claim - Other Subscriber Other Payer Referring Provider
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
    amt_segment: Optional[List[AmtSegment]] = Field(None, min_length=0, max_length=3)
    oi_segment: Optional[OiSegment] = None
    moa_segment: Optional[MoaSegment] = None
    loop_2330a: Optional[Loop2330A] = None
    loop_2330b: Optional[Loop2330B] = None
    loop_2330c: Optional[List[Loop2330C]] = None
    loop_2330d: Optional[Loop2330D] = None
    loop_2330e: Optional[Loop2330E] = None
    loop_2330f: Optional[Loop2330F] = None
    loop_2330g: Optional[Loop2330G] = None

    _validate_amt_segments = model_validator(mode="after")(validate_duplicate_amt_codes)


class Loop2310F(X12SegmentGroup):
    """
    Claim ambulance drop-off location
    """

    nm1_segment: Loop2310FNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment


class Loop2310E(X12SegmentGroup):
    """
    Claim ambulance pickup location
    """

    nm1_segment: Loop2310ENm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment


class Loop2310D(X12SegmentGroup):
    """
    Claim Supervising Provider
    """

    nm1_segment: Loop2310DNm1Segment
    ref_segment: Optional[List[Loop2310DRefSegment]] = None


class Loop2310C(X12SegmentGroup):
    """
    Claim Service Facility Location
    """

    nm1_segment: Optional[Loop2310CNm1Segment] = None
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2310CRefSegment]] = Field(
        None, min_length=0, max_length=3
    )
    per_segment: Optional[Loop2310CPerSegment] = None


class Loop2310B(X12SegmentGroup):
    """
    Claim Rendering Provider
    """

    nm1_segment: Loop2310BNm1Segment
    prv_segment: Optional[Loop2310BPrvSegment] = None
    ref_segment: Optional[List[Loop2310BRefSegment]] = Field(
        None, min_length=0, max_length=4
    )


class Loop2310A(X12SegmentGroup):
    """
    Claim Referring Provider
    """

    nm1_segment: Loop2310ANm1Segment
    ref_segment: Optional[List[Loop2310ARefSegment]] = Field(
        None, min_length=0, max_length=3
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
    cas_segment: Optional[List[CasSegment]] = Field(
        None,
    )
    dtp_segment: Loop2430DtpSegment
    amt_segment: Optional[Loop2430AmtSegment] = None


class Loop2420H(X12SegmentGroup):
    """
    Claim Service Line - Ambulance Drop-Off Location
    """

    nm1_segment: Loop2420HNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment


class Loop2420G(X12SegmentGroup):
    """
    Claim Service Line - Ambulance Pick-Up Location
    """

    nm1_segment: Loop2420GNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment


class Loop2420F(X12SegmentGroup):
    """
    Claim Service Line - Referring Provider Name
    """

    nm1_segment: Loop2420FNm1Segment
    ref_segment: Optional[List[Loop2420FRefSegment]] = Field(
        None, min_length=0, max_length=20
    )


class Loop2420E(X12SegmentGroup):
    """
    Claim Service Line - Ordering Provider Name
    """

    nm1_segment: Loop2420ENm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    ref_segment: Optional[List[Loop2420ERefSegment]] = Field(
        None, min_length=0, max_length=20
    )
    per_segment: Optional[Loop2420EPerSegment] = None


class Loop2420D(X12SegmentGroup):
    """
    Claim Service Line - Supervising Provider Name
    """

    nm1_segment: Loop2420DNm1Segment
    ref_segment: Optional[List[Loop2420DRefSegment]] = Field(
        None, min_length=0, max_length=20
    )


class Loop2420C(X12SegmentGroup):
    """
    Claim Service Line - Service Facility Location Name
    """

    nm1_segment: Loop2420CNm1Segment
    n3_segment: N3Segment
    n4_segment: N4Segment
    ref_segment: Optional[List[Loop2420CRefSegment]] = Field(
        None, min_length=0, max_length=3
    )


class Loop2420B(X12SegmentGroup):
    """
    Claim Service Line - Purchased Service Provider
    """

    nm1_segment: Loop2420BNm1Segment
    ref_segment: Optional[List[Loop2420BRefSegment]] = Field(
        None, min_length=0, max_length=20
    )


class Loop2420A(X12SegmentGroup):
    """
    Claim Service Line - Rendering Provider
    """

    nm1_segment: Loop2420ANm1Segment
    prv_segment: Optional[Loop2420APrvSegment] = None
    ref_segment: Optional[List[Loop2420ARefSegment]] = Field(
        None, min_length=0, max_length=20
    )


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
    sv1_segment: Sv1Segment
    sv5_segment: Optional[Sv5Segment] = None
    pwk_segment: Optional[List[Loop2400PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    cr1_segment: Optional[Cr1Segment] = None
    cr3_segment: Optional[Cr3Segment] = None
    crc_segment: Optional[List[Loop2400CrcSegment]] = Field(
        None, min_length=0, max_length=5
    )
    dtp_segment: List[Loop2400DtpSegment] = Field(min_length=1, max_length=11)
    qty_segment: Optional[List[Loop2400QtySegment]] = Field(
        None, min_length=0, max_length=2
    )
    mea_segment: Optional[List[MeaSegment]] = Field(None, min_length=0, max_length=5)
    cn1_segment: Optional[Loop2400Cn1Segment] = None
    ref_segment: Optional[List[Loop2400RefSegment]] = Field(
        None, min_length=0, max_length=11
    )
    amt_segment: Optional[List[Loop2400AmtSegment]] = Field(
        None, min_length=0, max_length=2
    )
    k3_segment: Optional[List[K3Segment]] = Field(None, min_length=0, max_length=10)
    nte_segment: Optional[List[Loop2400NteSegment]] = Field(
        None, min_length=0, max_length=2
    )
    ps1_segment: Optional[Ps1Segment] = None
    hcp_segment: Optional[HcpSegment] = None
    loop_2410: Optional[Loop2410] = None
    loop_2420a: Optional[Loop2420A] = None
    loop_2420b: Optional[Loop2420B] = None
    loop_2420c: Optional[Loop2420C] = None
    loop_2420d: Optional[Loop2420D] = None
    loop_2420e: Optional[Loop2420E] = None
    loop_2420f: Optional[Loop2420F] = None
    loop_2420g: Optional[Loop2420G] = None
    loop_2420h: Optional[Loop2420H] = None
    loop_2430: Optional[List[Loop2430]] = Field(None, min_length=0, max_length=15)
    loop_2440: Optional[List[Loop2440]] = Field(None, min_length=0)

    _validate_dtp_qualifiers = model_validator(mode="after")(
        validate_duplicate_date_qualifiers
    )


class Loop2300(X12SegmentGroup):
    """
    Loop 2300 - Claims
    """

    clm_segment: ClmSegment
    dtp_segment: Optional[List[Loop2300DtpSegment]] = Field(
        None, min_length=0, max_length=17
    )
    pwk_segment: Optional[List[Loop2300PwkSegment]] = Field(
        None, min_length=0, max_length=10
    )
    cn1_segment: Optional[Loop2300Cn1Segment] = None
    amt_segment: Optional[Loop2300AmtSegment] = None
    ref_segment: Optional[List[Loop2300RefSegment]] = Field(
        None, min_length=0, max_length=14
    )
    k3_segment: Optional[List[K3Segment]] = Field(None, min_length=0, max_length=10)
    nte_segment: Optional[Loop2300NteSegment] = None
    cr1_segment: Optional[Cr1Segment] = None
    cr2_segment: Optional[Cr2Segment] = None
    crc_segment: Optional[List[Loop2300CrcSegment]] = Field(
        None, min_length=0, max_length=8
    )
    hi_segment: Optional[List[HiSegment]] = Field(None, min_length=1, max_length=4)
    hcp_segment: Optional[HcpSegment] = None
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
            line_total += line.sv1_segment.line_item_charge_amount

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
    per_segment: Optional[Loop2010CaPerSegment] = None


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
