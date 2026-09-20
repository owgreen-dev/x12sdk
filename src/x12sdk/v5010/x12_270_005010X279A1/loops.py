"""
loops.py

Models the loops, or logical segment groupings, for the Eligibility 270 005010X279A1 transaction set.
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
    HiSegment,
    N3Segment,
    N4Segment,
    SeSegment,
    TrnSegment,
)
from x12sdk.validators import validate_duplicate_ref_codes

from .segments import (
    HeaderBhtSegment,
    HeaderStSegment,
    Loop2000AHlSegment,
    Loop2000BHlSegment,
    Loop2000CHlSegment,
    Loop2000DHlSegment,
    Loop2100ANm1Segment,
    Loop2100BNm1Segment,
    Loop2100BPrvSegment,
    Loop2100BRefSegment,
    Loop2100CInsSegment,
    Loop2100CNm1Segment,
    Loop2100CPrvSegment,
    Loop2100DInsSegment,
    Loop2100DNm1Segment,
    Loop2100DtpSegment,
    Loop2100RefSegment,
    Loop2110AmtSegment,
    Loop2110DtpSegment,
    Loop2110EqSegment,
    Loop2110IiiSegment,
    Loop2110RefSegment,
)


class Header(X12SegmentGroup):
    """
    Transaction Header Information
    """

    st_segment: HeaderStSegment
    bht_segment: HeaderBhtSegment


class Loop2110D(X12SegmentGroup):
    """
    Loop 2110D Dependent Eligibility
    """

    eq_segment: Optional[Loop2110EqSegment] = None
    amt_segment: Optional[List[Loop2110AmtSegment]] = Field(
        None, min_length=0, max_length=2
    )
    iii_segment: Optional[Loop2110IiiSegment] = None
    ref_segment: Optional[Loop2110RefSegment] = None
    dtp_segment: Optional[Loop2110DtpSegment] = None


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
    prv_segment: Optional[Loop2100CPrvSegment] = None
    dmg_segment: Optional[DmgSegment] = None
    ins_segment: Optional[Loop2100DInsSegment] = None
    hi_segment: Optional[HiSegment] = None
    dtp_segment: Optional[Loop2100DtpSegment] = None
    # EQ repeats within loop 2110, up to 99 times: one inquiry may ask about
    # several service types. min_length=1 keeps the loop required, as the
    # implementation guide has it for a dependent, while allowing repeats.
    loop_2110d: List[Loop2110D] = Field(min_length=1)

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2000D(X12SegmentGroup):
    """
    Loop 2000D - Dependent
    """

    hl_segment: Loop2000DHlSegment
    trn_segment: Optional[List[TrnSegment]] = Field(None, min_length=0, max_length=2)
    loop_2100d: Loop2100D


class Loop2110C(X12SegmentGroup):
    """
    Loop2110C - Subscriber Eligibility
    """

    eq_segment: Optional[Loop2110EqSegment] = None
    amt_segment: Optional[List[Loop2110AmtSegment]] = Field(
        None, min_length=0, max_length=2
    )
    iii_segment: Optional[Loop2110IiiSegment] = None
    ref_segment: Optional[Loop2110RefSegment] = None
    dtp_segment: Optional[Loop2110DtpSegment] = None


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
    prv_segment: Optional[Loop2100CPrvSegment] = None
    dmg_segment: Optional[DmgSegment] = None
    ins_segment: Optional[Loop2100CInsSegment] = None
    hi_segment: Optional[HiSegment] = None
    dtp_segment: Optional[Loop2100DtpSegment] = None
    # repeats, as loop_2110d does; optional because a subscriber may appear
    # only to carry a dependent whose eligibility is being asked about
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
    prv_segment: Optional[Loop2100BPrvSegment] = None

    _validate_ref_segments = model_validator(mode="after")(validate_duplicate_ref_codes)


class Loop2000B(X12SegmentGroup):
    """
    Loop 2000B - Information Receiver
    """

    hl_segment: Loop2000BHlSegment
    loop_2100b: Loop2100B
    loop_2000c: List[Loop2000C] = Field(min_length=1)


class Loop2100A(X12SegmentGroup):
    """
    Loop 2100A - Information Source Name
    """

    nm1_segment: Loop2100ANm1Segment


class Loop2000A(X12SegmentGroup):
    """
    Loop 2000A - Information Source
    The root node/loop for the 270 transaction

    """

    hl_segment: Loop2000AHlSegment
    loop_2100a: Loop2100A
    loop_2000b: List[Loop2000B] = Field(min_length=1)


class Footer(X12SegmentGroup):
    """
    Transaction Footer Information
    """

    se_segment: SeSegment
