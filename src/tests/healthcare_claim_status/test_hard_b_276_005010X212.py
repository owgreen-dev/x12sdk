"""
Control for the 276 005010X212 claim status request: a claim with one service line round-trips.
"""

import pytest

from tests.hard_b_support import assert_round_trip, interchange

HEADER = ["ST*276*0001*005010X212", "BHT*0010*13*ABC276XXX*20260101*1425"]
HIERARCHY = [
    "HL*1**20*1",
    "NM1*PR*2*EXAMPLE PAYER*****PI*12345",
    "HL*2*1*21*1",
    "NM1*41*2*EXAMPLE SERVICE*****46*X67E",
    "HL*3*2*19*1",
    "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893",
]
SUBSCRIBER = [
    "HL*4*3*22*0",
    "DMG*D8*19301210*M",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
]
DEPENDENT = [
    "HL*4*3*22*1",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
    "HL*5*4*23",
    "DMG*D8*19951101*M",
    "NM1*QC*1*DOE*JOHN",
]
CLAIM = ["TRN*1*CLAIM0001", "REF*EJ*ACCT0001"]
LINE_1 = ["SVC*HC:99203*150.00*****1.00", "DTP*472*D8*20260101"]


def request(lines, dependent=False):
    """A 276 for one patient, whose first claim holds the given service line segments."""
    body = HIERARCHY + (DEPENDENT if dependent else SUBSCRIBER) + CLAIM
    for line in lines:
        body += line
    return interchange("HR", "005010X212", HEADER, body)


@pytest.mark.parametrize("dependent", [False, True], ids=["subscriber", "dependent"])
def test_control_one_service_line_round_trips(dependent):
    text, segments = request([LINE_1], dependent)
    assert_round_trip(text, segments)
