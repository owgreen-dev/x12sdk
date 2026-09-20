"""
transaction_set.py

Defines the Health Care Claims Payment 835 005010X221A1 transaction set model.
"""

from typing import List, Set

from pydantic import model_validator

from x12sdk.access import RemittanceAccess
from x12sdk.models import X12SegmentGroup
from x12sdk.validators import validate_segment_count

from .loops import Footer, Header, Loop1000A, Loop1000B, Loop2000


class HealthCareClaimPayment(RemittanceAccess, X12SegmentGroup):
    """
    The Health Care Claim Payment/835 transaction
    """

    header: Header
    loop_1000a: Loop1000A
    loop_1000b: Loop1000B
    loop_2000: List[Loop2000]
    footer: Footer

    _validate_segment_count = model_validator(mode="after")(validate_segment_count)

    @model_validator(mode="after")
    def validate_lx_header(self):
        """
        Validates that LX numbers within a transaction set are unique.
        """
        values = self.__dict__
        numbers: Set = set()
        for loop in values.get("loop_2000", []):
            # LX01 is kept as text to preserve leading zeros; compare values
            n: int = int(loop.lx_segment.assigned_number)
            if n in numbers:
                raise ValueError(f"duplicate assigned_numbers {n}")
            numbers.add(n)

        return self
