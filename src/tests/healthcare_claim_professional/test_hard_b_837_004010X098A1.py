"""
Segments that are dropped or mis-routed in the 004010X098A1 professional claim.

The structure gives the subscriber a responsible party name loop (2010BC, NM1*QD) and a credit or debit card holder
loop (2010BD, NM1*AO), and the other payer loops of 2330 include a supervising provider loop (2330H, NM1*DQ). Each
loop is declared in the loop and segment models and each has a name in the parser's loop table. A valid claim that
carries one of them must parse and serialize back to the same segments. Each case has a control that differs only by
leaving the loop out (or by using a sibling loop that is routed today).
"""

import pytest

from tests.hard_b_support import assert_round_trip, interchange, parse_one

HEADER = [
    "ST*837*0001",
    "BHT*0019*00*0123*20260101*1023*RP",
    "REF*87*004010X098",
]
SUBMITTER = [
    "NM1*41*2*EXAMPLE SUBMITTER*****46*SUB001",
    "PER*IC*JANE DOE*TE*5555550100",
    "NM1*40*2*EXAMPLE RECEIVER*****46*REC001",
]
BILLING = [
    "HL*1**20*1",
    "NM1*85*2*EXAMPLE CLINIC*****24*123456789",
    "N3*1 MAIN ST",
    "N4*SPRINGFIELD*IL*62701",
]
SUBSCRIBER = [
    "HL*2*1*22*0",
    "SBR*P*18*GRP001******HM",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
    "N3*2 ELM ST",
    "N4*SPRINGFIELD*IL*62702",
    "DMG*D8*19800101*F",
    "NM1*PR*2*EXAMPLE PAYER*****PI*99999",
]
CLAIM = ["CLM*CLAIM0001*40.00***11::1*Y*A*Y*Y*C", "HI*BK:0340"]
LINE = [
    "LX*1",
    "SV1*HC:99213*40.00*UN*1.00***1",
    "DTP*472*D8*20260101",
]
# an other subscriber (2320) with its subscriber name (2330A) and payer name (2330B)
OTHER_SUBSCRIBER = [
    "SBR*S*18*GRP002**HM****CI",
    "AMT*D*10.00",
    "OI***Y***Y",
    "NM1*IL*1*DOE*JOHN****MI*MEMBER002",
    "N3*3 OAK ST",
    "N4*SPRINGFIELD*IL*62702",
    "NM1*PR*2*OTHER PAYER*****PI*77777",
]


def claim_with(after_payer=(), after_claim=(), other_subscriber=None):
    """
    Builds the claim text; each argument is a list of segments added at that position. `other_subscriber` adds the
    2320 loop with its 2330A and 2330B and then the given segments (an empty list adds the 2320 loop alone).
    """
    body = (
        SUBMITTER
        + BILLING
        + SUBSCRIBER
        + list(after_payer)
        + CLAIM
        + list(after_claim)
        + (
            OTHER_SUBSCRIBER + list(other_subscriber)
            if other_subscriber is not None
            else []
        )
        + LINE
    )
    return interchange("HC", "004010X098A1", HEADER, body)


def test_control_claim_round_trips():
    text, segments = claim_with()
    assert_round_trip(text, segments)


def test_control_other_subscriber_round_trips():
    """A claim with an other subscriber and no 2330H parses today; it anchors the 2330H cases below."""
    text, segments = claim_with(other_subscriber=[])
    assert_round_trip(text, segments)


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(
            ["NM1*QD*1*ROE*RICHARD", "N3*3 OAK ST", "N4*SPRINGFIELD*IL*62702"],
            id="2010BC-responsible-party",
        ),
        pytest.param(
            ["NM1*AO*1*ROE*RICHARD****MI*CARD0001", "REF*AB*ABC123"],
            id="2010BD-card-holder",
        ),
        pytest.param(
            ["NM1*QD*1*ROE*RICHARD", "NM1*AO*1*ROE*RICHARD****MI*CARD0001"],
            id="2010BC-and-2010BD",
        ),
    ],
)
def test_subscriber_responsible_party_and_card_holder_loops(extra):
    """
    NM1*QD (2010BC) and NM1*AO (2010BD) follow the payer name loop 2010BB and must each open their own loop, and
    the payer name loop keeps its single NM1.
    """
    text, segments = claim_with(after_payer=extra)
    assert_round_trip(text, segments)
    subscriber = parse_one(text).loop_2000a[0].loop_2000b[0]
    codes = [s.split("*")[1] for s in extra if s.startswith("NM1*")]
    assert (subscriber.loop_2010bc is not None) == ("QD" in codes)
    assert (subscriber.loop_2010bd is not None) == ("AO" in codes)
    assert subscriber.loop_2010bb.nm1_segment.entity_identifier_code == "PR"


def test_other_payer_supervising_provider_loop_2330h():
    """
    NM1*DQ after an other payer name opens loop 2330H, whose model accepts exactly that qualifier and requires a REF.
    """
    text, segments = claim_with(
        other_subscriber=["NM1*DQ*1*ROE*RICHARD", "REF*G2*SUP001"]
    )
    assert_round_trip(text, segments)
    other = parse_one(text).loop_2000a[0].loop_2000b[0].loop_2300[0].loop_2320[0]
    assert other.loop_2330h.nm1_segment.entity_identifier_code == "DQ"
    assert other.loop_2330b.nm1_segment.entity_identifier_code == "PR"


def test_control_other_payer_rendering_provider_loop_2330e_round_trips():
    """The sibling loop 2330E (NM1*82) is routed today, so the 2330H failure is about NM1*DQ only."""
    text, segments = claim_with(
        other_subscriber=["NM1*82*1*ROE*RICHARD", "REF*G2*REND001"]
    )
    assert_round_trip(text, segments)
