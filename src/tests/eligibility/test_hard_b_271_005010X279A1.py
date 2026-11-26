"""
Segments that are dropped or rejected in the 271 005010X279A1 response.

* The information source name loop 2100A allows a contact segment PER (up to three). The structure is taken from
  public structure listings, not independently verified here: confirm against the implementation guide before
  relying on it.

Each case has a control built from the same pieces that parses today. A benefit loop with a related entity loop 2120 is kept as a control.
"""

import pytest

from tests.hard_b_support import assert_round_trip, interchange

HEADER = ["ST*271*0001*005010X279A1", "BHT*0022*11*10001234*20260101*1200"]
SOURCE = ["HL*1**20*1", "NM1*PR*2*EXAMPLE PAYER*****PI*99999"]
RECEIVER = ["HL*2*1*21*1", "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893"]
SUBSCRIBER = ["HL*3*2*22*{child}", "NM1*IL*1*DOE*JANE****MI*MEMBER001"]
DEPENDENT = ["HL*4*3*23*0", "NM1*03*1*DOE*JOHN"]
EB = "EB*1**30"
RELATED_ENTITY = ["LS*2120", "NM1*P3*1*ROE*RICHARD****SV*PROV001", "LE*2120"]


def response(benefit, dependent=False, source_extra=()):
    """A 271 whose only benefit loop (2110C, or 2110D for a dependent) is made of the given segments."""
    body = list(SOURCE) + list(source_extra) + RECEIVER
    body += [s.format(child="1" if dependent else "0") for s in SUBSCRIBER]
    if dependent:
        body += DEPENDENT
    body += list(benefit)
    return interchange("HB", "005010X279A1", HEADER, body)


@pytest.mark.parametrize("dependent", [False, True], ids=["subscriber", "dependent"])
def test_control_benefit_with_related_entity_round_trips(dependent):
    text, segments = response([EB] + RELATED_ENTITY, dependent)
    assert_round_trip(text, segments)


def test_control_benefit_alone_round_trips():
    text, segments = response([EB])
    assert_round_trip(text, segments)


def test_information_source_contact_segment_is_kept():
    """A PER after the information source NM1 must not be lost."""
    text, segments = response([EB], source_extra=["PER*IC*HELP DESK*TE*5555550100"])
    assert_round_trip(text, segments)
