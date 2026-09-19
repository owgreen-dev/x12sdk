"""
transaction_set.py

Defines the Health Care Claims Status 276 005010X212 transaction set model.
"""

from typing import List

from pydantic import Field, root_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.validators import validate_segment_count

from .loops import Footer, Header, Loop2000A


class HealthCareClaimsStatusRequest(X12SegmentGroup):
    """
    The Health Care Claims Status transaction model - 276
    """

    header: Header
    loop_2000a: List[Loop2000A] = Field(min_items=1)
    footer: Footer

    _validate_segment_count = root_validator(allow_reuse=True)(validate_segment_count)
