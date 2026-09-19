"""
loops.py

Models the loops, or logical segment groupings, for the Eligibility 271 005010X279A1 transaction set.
The Eligibility Transaction set organizes loops into a hierarchical and nested model.

- Header
- Loop 2000A (Information Source)
    -- Loop 2100A (Information Source Name)
    -- Loop 2000B (Information Receiver)
        --- Loop 2100B (Information Receiver Name)
        --- Loop 2000C (Subscriber)
            --- Loop 2100C (Subscriber Name)
                --- Loop 2110C (Subscriber Eligibility)
            --- Loop 2000D (Dependent)
                --- Loop 2100D (Dependent Name)
                    --- Loop 2110D (Dependent Eligibility)
-- Footer

The Header and Footer components are not "loops" per the specification, but are included to standardize and simplify
transactional modeling and processing.
"""

from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.v5010.segments import (
    DmgSegment,
    EbSegment,
    HiSegment,
    HsdSegment,
    IiiSegment,
    LeSegment,
    LsSegment,
    MpiSegment,
    MsgSegment,
    N3Segment,
    N4Segment,
    PerSegment,
    PrvSegment,
    SeSegment,
    TrnSegment,
)
from x12sdk.validators import validate_duplicate_ref_codes

from .segments import (
    HeaderBhtSegment,
    HeaderStSegment,
    Loop2000AAaaSegment,
    Loop2000AHlSegment,
    Loop2000BHlSegment,
    Loop2000CHlSegment,
    Loop2000DHlSegment,
    Loop2100AAaaSegment,
    Loop2100ANm1Segment,
    Loop2100BAaaSegment,
    Loop2100BNm1Segment,
    Loop2100BPrvSegment,
    Loop2100BRefSegment,
    Loop2100CInsSegment,
    Loop2100CNm1Segment,
    Loop2100DInsSegment,
    Loop2100DNm1Segment,
    Loop2100DtpSegment,
    Loop2100RefSegment,
    Loop2110CAaaSegment,
    Loop2110DtpSegment,
    Loop2110RefSegment,
    Loop2120Nm1Segment,
)


class Header(X12SegmentGroup):
    """
    Transaction Header Information
    """

    st_segment: HeaderStSegment
    bht_segment: HeaderBhtSegment


class Loop2120D(X12SegmentGroup):
    """
    Loop 2120D
    """

    nm1_segment: Loop2120Nm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    per_segment: Optional[List[PerSegment]] = Field(None, min_length=0, max_length=3)
    prv_segment: Optional[PrvSegment] = None


class Loop2115D(X12SegmentGroup):
    """
    Loop 2115D - Dependent Eligibility or Benefit Additional Information
    """

    iii_segment: IiiSegment
    ls_segment: LsSegment
    loop_2120c: Optional[List[Loop2120D]] = Field(None, min_length=0, max_length=23)
    le_segment: LeSegment


class Loop2110D(X12SegmentGroup):
    """
    Loop 2110D Dependent Eligibility or Benefit Information
    """

    eb_segment: EbSegment
    hsd_segment: Optional[List[HsdSegment]] = Field(None, min_length=0, max_length=9)
    ref_segment: Optional[List[Loop2110RefSegment]] = Field(
        None, min_length=0, max_length=9
    )
    dtp_segment: Optional[List[Loop2110DtpSegment]] = Field(
        None, min_length=0, max_length=20
    )
    aaa_segment: Optional[List[Loop2110CAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )
    msg_segment: Optional[List[MsgSegment]] = Field(None, min_length=0, max_length=10)
    loop_2115d: Optional[List[Loop2115D]] = Field(None, min_length=0, max_length=10)
    ls_segment: Optional[LsSegment] = None
    loop_2120d: Optional[List[Loop2120D]] = Field(None, min_length=0, max_length=23)
    le_segment: Optional[LeSegment] = None

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2100D(X12SegmentGroup):
    """
    Loop 2100D - Dependent Name
    """

    nm1_segment: Loop2100DNm1Segment
    ref_segment: Optional[List[Loop2100RefSegment]] = Field(
        None, min_length=0, max_length=9
    )
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    # Loop2100D AAA is identical to Loop2100B AAA
    aaa_segment: Optional[List[Loop2100BAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )
    prv_segment: Optional[PrvSegment] = None
    dmg_segment: Optional[DmgSegment] = None
    ins_segment: Optional[Loop2100DInsSegment] = None
    hi_segment: Optional[HiSegment] = None
    dtp_segment: Optional[List[Loop2100DtpSegment]] = Field(
        None, min_length=0, max_length=9
    )
    mpi_segment: Optional[MpiSegment] = None
    loop_2110d: Optional[List[Loop2110D]] = Field(None, min_length=0)

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2000D(X12SegmentGroup):
    """
    Loop 2000D - Dependent
    """

    hl_segment: Loop2000DHlSegment
    trn_segment: Optional[List[TrnSegment]] = Field(None, min_length=0, max_length=2)
    loop_2100d: Loop2100D


class Loop2120C(X12SegmentGroup):
    """
    Loop 2120C Subscriber Benefit Related Entity Name
    """

    nm1_segment: Loop2120Nm1Segment
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    per_segment: Optional[List[PerSegment]] = Field(None, min_length=0, max_length=3)
    prv_segment: Optional[PrvSegment] = None


class Loop2115C(X12SegmentGroup):
    """
    Loop 2115C - Subscriber Eligibility or Benefit Information Additional Information
    """

    iii_segment: IiiSegment
    ls_segment: LsSegment
    loop_2120c: Optional[List[Loop2120C]] = Field(None, min_length=0, max_length=23)
    le_segment: LeSegment


class Loop2110C(X12SegmentGroup):
    """
    Loop2110C - Subscriber Eligibility or Benefit Information
    """

    eb_segment: EbSegment
    hsd_segment: Optional[List[HsdSegment]] = Field(None, min_length=0, max_length=9)
    ref_segment: Optional[List[Loop2110RefSegment]] = Field(
        None, min_length=0, max_length=9
    )
    dtp_segment: Optional[List[Loop2110DtpSegment]] = Field(
        None, min_length=0, max_length=20
    )
    aaa_segment: Optional[List[Loop2110CAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )
    msg_segment: Optional[List[MsgSegment]] = Field(None, min_length=0, max_length=10)
    loop_2115c: Optional[List[Loop2115C]] = Field(None, min_length=0, max_length=10)
    ls_segment: Optional[LsSegment] = None
    loop_2120c: Optional[List[Loop2120C]] = Field(None, min_length=0, max_length=23)
    le_segment: Optional[LeSegment] = None

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)

    @model_validator(mode="after")
    def validate_red_cross_eb_ref_codes(self):
        """
        Validates that reference identification codes are limited when American Red Cross is the eligibility benefit.

        :@param values: The validated model values
        """
        values = self.__dict__
        benefit_code = values["eb_segment"].eligibility_benefit_information
        arc_ref_types = {"1W", "49", "F6", "NQ"}
        ref_types = {
            r.reference_identification_qualifier for r in values.get("ref_segments", [])
        }

        if ref_types and benefit_code == "R" and (ref_types - arc_ref_types):
            raise ValueError(f"{ref_types} are not valid for American Red Cross")

        return self


class Loop2100C(X12SegmentGroup):
    """
    Loop 2100C - Subscriber Name
    """

    nm1_segment: Loop2100CNm1Segment
    ref_segment: Optional[List[Loop2100RefSegment]] = Field(
        None, min_length=0, max_length=9
    )
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    # Loop2100C AAA is identical to Loop2100B AAA
    aaa_segment: Optional[List[Loop2100BAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )
    prv_segment: Optional[PrvSegment] = None
    dmg_segment: Optional[DmgSegment] = None
    ins_segment: Optional[Loop2100CInsSegment] = None
    hi_segment: Optional[HiSegment] = None
    dtp_segment: Optional[List[Loop2100DtpSegment]] = Field(
        None, min_length=0, max_length=9
    )
    mpi_segment: Optional[MpiSegment] = None
    loop_2110c: Optional[List[Loop2110C]] = Field(None, min_length=0)

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2000C(X12SegmentGroup):
    """
    Loop 2000C - Subscriber
    """

    hl_segment: Loop2000CHlSegment
    trn_segment: Optional[List[TrnSegment]] = Field(None, min_length=0, max_length=2)
    loop_2100c: Loop2100C
    loop_2000d: Optional[List[Loop2000D]] = Field(None, min_length=0)


class Loop2100B(X12SegmentGroup):
    """
    Loop 2100B - Information Receiver Name
    """

    nm1_segment: Loop2100BNm1Segment
    ref_segment: Optional[List[Loop2100BRefSegment]] = None
    n3_segment: Optional[N3Segment] = None
    n4_segment: Optional[N4Segment] = None
    aaa_segment: Optional[List[Loop2100BAaaSegment]] = None
    prv_segment: Optional[Loop2100BPrvSegment] = None

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2000B(X12SegmentGroup):
    """
    Loop 2000B - Information Receiver
    """

    hl_segment: Loop2000BHlSegment
    loop_2100b: Loop2100B
    loop_2000c: Optional[List[Loop2000C]] = None


class Loop2100A(X12SegmentGroup):
    """
    Loop 2100A - Information Source Name
    """

    nm1_segment: Loop2100ANm1Segment
    prv_segment: Optional[List[PrvSegment]] = Field(None, min_length=0, max_length=3)
    aaa_segment: Optional[List[Loop2100AAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )


class Loop2000A(X12SegmentGroup):
    """
    Loop 2000A - Information Source
    The root node/loop for the 271 transaction

    """

    hl_segment: Loop2000AHlSegment
    aaa_segment: Optional[List[Loop2000AAaaSegment]] = Field(
        None, min_length=0, max_length=9
    )
    loop_2100a: Loop2100A
    loop_2000b: List[Loop2000B] = Field(min_length=0)


class Footer(X12SegmentGroup):
    """
    Transaction Footer Information
    """

    se_segment: SeSegment
