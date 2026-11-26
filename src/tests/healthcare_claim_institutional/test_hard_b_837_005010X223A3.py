"""
Billing provider pay-to plan loop 2010AC in the 005010X223A3 institutional claim.

Loop 2010AC (NM1*PE, N3, N4 and the REF segments) follows the billing provider loops and is a different loop with
a different reference qualifier list from the billing provider's own REF in 2010AA. A claim that carries a 2010AC
REF with one of the qualifiers its own loop allows must parse and serialize back to the same segments. The
qualifiers used are 2U, EI, FY and NF (taken from public structure listings, not independently verified here:
confirm against the implementation guide before relying on the list). The cases that pass today act as controls.
"""

import pytest

from tests.hard_b_support import assert_round_trip, interchange

HEADER = [
    "ST*837*0001*005010X223A3",
    "BHT*0019*00*REF0001*20260101*1030*CH",
]
BODY = [
    "NM1*41*2*EXAMPLE SUBMITTER*****46*SUB001",
    "PER*IC*JANE DOE*TE*5555550100",
    "NM1*40*2*EXAMPLE RECEIVER*****46*REC001",
    "HL*1**20*1",
    "PRV*BI*PXC*203BA0200N",
    "NM1*85*2*EXAMPLE CLINIC*****XX*1234567893",
    "N3*1 MAIN ST",
    "N4*SPRINGFIELD*IL*62701",
    "REF*EI*123456789",
    "HL*2*1*22*0",
    "SBR*P*18*GRP001******CI",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
    "N3*2 ELM ST",
    "N4*SPRINGFIELD*IL*62702",
    "DMG*D8*19800101*F",
    "NM1*PR*2*EXAMPLE PAYER*****PI*99999",
    "CLM*CLAIM0001*89.93***14:A:1*Y*A*Y*Y",
    "DTP*434*D8*20260101",
    "CL1*3**01",
    "HI*BK:3669",
    "LX*1",
    "SV2*0305*HC:85025*89.93*UN*1.00",
    "DTP*472*D8*20260101",
]


def claim(qualifier=None):
    """The claim, with a 2010AC loop holding a REF of the given qualifier when one is given."""
    body = list(BODY)
    if qualifier is not None:
        at = body.index("REF*EI*123456789") + 1
        body[at:at] = [
            "NM1*PE*2*EXAMPLE PLAN*****XV*123456789",
            "N3*9 ELM ST",
            "N4*SPRINGFIELD*IL*62701",
            f"REF*{qualifier}*A1234",
        ]
    return interchange("HC", "005010X223A3", HEADER, body)


def test_control_claim_without_pay_to_plan_round_trips():
    text, segments = claim()
    assert_round_trip(text, segments)


@pytest.mark.parametrize("qualifier", ["2U", "EI", "FY", "NF"])
def test_pay_to_plan_reference_qualifiers(qualifier):
    text, segments = claim(qualifier)
    assert_round_trip(text, segments)
