"""
test_audit_found_segment_defects.py

Regression tests for three shared-segment defects the audit suite found on
its first full run. None is reachable by parsing a sample file, which is why
the corpus never caught them.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

import x12sdk.v4010.segments as v4010
import x12sdk.v5010.segments as v5010


@pytest.mark.parametrize("segments", [v5010, v4010], ids=["v5010", "v4010"])
def test_hi_composite_fields_validate_their_items(segments):
    """
    Every HI composite field was annotated as a bare ``List``, so Pydantic
    validated nothing inside it and ``[1, None, {}]`` was accepted where a
    list of code strings was meant. They are ``List[str]`` now.
    """
    ok = segments.HiSegment(health_care_code_1=["BK", "8628"])
    assert ok.health_care_code_1 == ["BK", "8628"]
    with pytest.raises(ValidationError):
        segments.HiSegment(health_care_code_1=[1, None, {}])


@pytest.mark.parametrize("segments", [v5010, v4010], ids=["v5010", "v4010"])
def test_hsd_with_only_period_information_is_valid(segments):
    """
    HSD01 and HSD02 are a conditional pair: if either is present the other
    is required. The validator rejected a segment with *neither*, so an HSD
    carrying only period information could not be constructed at all.
    """
    segments.HsdSegment()  # neither: valid
    segments.HsdSegment(quantity_qualifier="VS", quantity=Decimal("2"))  # both: valid
    with pytest.raises(ValidationError, match="qualifier and value"):
        segments.HsdSegment(quantity=Decimal("2"))  # one without the other


def test_a_constructed_4010_isa_segment_renders():
    """
    The 4010 ISA's ``x12()`` read ``self.delimiters``, which is ``None`` on any
    constructed segment, so a built ISA validated but raised on rendering.
    The 5010 segment defaulted the delimiters; the 4010 one now matches it.
    """
    isa = v4010.IsaSegment(
        authorization_information_qualifier="00",
        authorization_information=" " * 10,
        security_information_qualifier="00",
        security_information=" " * 10,
        interchange_sender_qualifier="ZZ",
        interchange_sender_id="SENDER".ljust(15),
        interchange_receiver_qualifier="ZZ",
        interchange_receiver_id="RECEIVER".ljust(15),
        interchange_date="260101",
        interchange_time="1200",
        repetition_separator="^",
        interchange_control_version_number="00401",
        interchange_control_number="000000001",
        acknowledgment_requested="0",
        interchange_usage_indicator="T",
        component_element_separator=":",
    )
    rendered = isa.x12()
    assert rendered.startswith("ISA*00*")
    assert rendered.endswith("*:~")
