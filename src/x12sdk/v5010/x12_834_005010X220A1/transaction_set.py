"""
transaction_set.py

Defines the Enrollment 834 005010X220A1 transaction set model.
"""

from typing import List, Optional

from pydantic import Field, model_validator

from x12sdk.models import X12SegmentGroup
from x12sdk.validators import validate_segment_count

from .loops import Footer, Header, Loop1000A, Loop1000B, Loop1000C, Loop2000


class BenefitEnrollmentAndMaintenance(X12SegmentGroup):
    """
    The ASC X12 834 (Benefit Enrollment and Maintenance) transaction model.
    """

    header: Header
    loop_1000a: Loop1000A
    loop_1000b: Loop1000B
    loop_1000c: Optional[List[Loop1000C]] = Field(None, max_length=2)
    loop_2000: List[Loop2000]
    footer: Footer

    # Enabled here as it is on every other transaction set. It had been
    # commented out, so the 834 alone accepted a wrong SE01 in silence. All
    # ten inherited samples already carry a correct count.
    _validate_segment_count = model_validator(mode="after")(validate_segment_count)
