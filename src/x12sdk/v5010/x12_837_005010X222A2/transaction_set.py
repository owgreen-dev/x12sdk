"""
transaction_set.py

Defines the Professional Claims 837 005010X222A2 transaction set model.
"""

from typing import List

from pydantic import Field, model_validator

from x12sdk.access import ClaimSubmissionAccess
from x12sdk.models import X12SegmentGroup
from x12sdk.validators import validate_segment_count

from .loops import Footer, Header, Loop1000A, Loop1000B, Loop2000A


class HealthCareClaimProfessional(ClaimSubmissionAccess, X12SegmentGroup):
    """
    The HealthCare Claim - Professional transaction model (837)
    """

    header: Header
    loop_1000a: Loop1000A
    loop_1000b: Loop1000B
    loop_2000a: List[Loop2000A] = Field(min_length=1)
    footer: Footer

    _validate_segment_count = model_validator(mode="after")(validate_segment_count)
