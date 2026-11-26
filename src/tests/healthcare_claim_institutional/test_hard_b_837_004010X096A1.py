"""
Segments that are dropped or mis-routed in the 004010X096A1 institutional claim.

Each case builds a valid claim inline and asks for a round trip: every segment kept, in order. Controls differ only by
using a sibling segment or loop that is routed today.

* 2310E, the service facility location, accepts NM1 qualifiers 77, FA, LI and TL in its model.
* 2330H, the other payer service facility, accepts NM1*FA in its model.
* 2010BD, the responsible party name, is NM1*QD after the payer name 2010BC.
* NM1*QC inside an other subscriber loop belongs to 2330C (other payer patient information) and must not replace
  the dependent's own patient name loop 2010CA.
"""

import pytest

from tests.hard_b_support import assert_round_trip, interchange, parse_one

HEADER = [
    "ST*837*0001",
    "BHT*0019*00*0123*20260101*0932*CH",
    "REF*87*004010X096",
]
BILLING = [
    "NM1*41*2*EXAMPLE SUBMITTER*****46*SUB001",
    "PER*IC*JANE DOE*TE*5555550100",
    "NM1*40*2*EXAMPLE RECEIVER*****46*REC001",
    "HL*1**20*1",
    "PRV*BI*ZZ*203BA0200N",
    "NM1*85*2*EXAMPLE HOSPITAL*****XX*1234567893",
    "N3*1 MAIN ST",
    "N4*SPRINGFIELD*IL*62701",
    "REF*G2*PROV001",
]
SUBSCRIBER = [
    "HL*2*1*22*{child}",
    "SBR*P*18*******CI",
    "NM1*IL*1*DOE*JOHN*T***MI*MEMBER001",
    "N3*2 ELM ST",
    "N4*SPRINGFIELD*IL*62702",
    "DMG*D8*19700101*M",
    "NM1*PR*2*EXAMPLE PAYER*****PI*99999",
]
DEPENDENT = [
    "HL*3*2*23*0",
    "PAT*01",
    "NM1*QC*1*DOE*JANE*S",
    "N3*2 ELM ST",
    "N4*SPRINGFIELD*IL*62702",
    "DMG*D8*19900101*F",
]
CLAIM = [
    "CLM*CLAIM0001*89.93***14:A:1**A*Y*Y",
    "DTP*434*D8*20260101",
    "CL1*3*1",
    "HI*BK:3669",
]
OTHER_SUBSCRIBER = [
    "SBR*S*01*GRP002*OTHER PLAN*GP****CI",
    "OI***Y***Y",
    "NM1*IL*1*DOE*JOHN*S***MI*MEMBER002",
    "NM1*PR*2*OTHER PAYER*****PI*77777",
]
LINE = [
    "LX*1",
    "SV2*305*HC:85025*89.93*UN*1.00",
    "DTP*472*D8*20260101",
]


def claim(after_payer=(), after_claim=(), other_subscriber=None, dependent=False):
    """Builds the claim; `other_subscriber` is None for no 2320 loop, else the segments after its 2330B."""
    body = list(BILLING)
    body += [s.format(child="1" if dependent else "0") for s in SUBSCRIBER]
    body += list(after_payer)
    body += DEPENDENT if dependent else []
    body += CLAIM + list(after_claim)
    if other_subscriber is not None:
        body += OTHER_SUBSCRIBER + list(other_subscriber)
    body += LINE
    return interchange("HC", "004010X096A1", HEADER, body)


def test_control_claim_round_trips():
    text, segments = claim()
    assert_round_trip(text, segments)


def test_control_dependent_claim_with_other_subscriber_round_trips():
    text, segments = claim(dependent=True, other_subscriber=[])
    assert_round_trip(text, segments)


def test_control_service_facility_fa_in_2310e_round_trips():
    text, segments = claim(
        after_claim=[
            "NM1*FA*2*EXAMPLE CLINIC*****XX*1234567893",
            "N3*5 PINE ST",
            "N4*SPRINGFIELD*IL*62702",
        ]
    )
    assert_round_trip(text, segments)


@pytest.mark.parametrize("qualifier", ["77", "LI", "TL"])
def test_service_facility_other_qualifiers_in_2310e(qualifier):
    """The model for 2310E lists 77, LI and TL beside FA, so each must open the same loop FA opens."""
    text, segments = claim(
        after_claim=[
            f"NM1*{qualifier}*2*EXAMPLE CLINIC*****XX*1234567893",
            "N3*5 PINE ST",
            "N4*SPRINGFIELD*IL*62702",
        ]
    )
    assert_round_trip(text, segments)
    claim_loop = parse_one(text).loop_2000a[0].loop_2000b[0].loop_2300[0]
    assert claim_loop.loop_2310e.nm1_segment.entity_identifier_code == qualifier
    assert claim_loop.loop_2310a is None


def test_other_payer_service_facility_loop_2330h():
    """NM1*FA after the other payer name opens loop 2330H, which requires a REF."""
    text, segments = claim(
        other_subscriber=["NM1*FA*2*EXAMPLE CLINIC*****XX*1234567893", "REF*G2*FAC001"]
    )
    assert_round_trip(text, segments)
    other = parse_one(text).loop_2000a[0].loop_2000b[0].loop_2300[0].loop_2320[0]
    assert other.loop_2330h.nm1_segment.entity_identifier_code == "FA"
    assert other.loop_2330b.nm1_segment.entity_identifier_code == "PR"


def test_subscriber_responsible_party_loop_2010bd():
    """NM1*QD follows the payer name loop 2010BC and opens the responsible party name loop 2010BD."""
    text, segments = claim(after_payer=["NM1*QD*1*ROE*RICHARD"])
    assert_round_trip(text, segments)
    subscriber = parse_one(text).loop_2000a[0].loop_2000b[0]
    assert subscriber.loop_2010bd.nm1_segment.entity_identifier_code == "QD"
    assert subscriber.loop_2010bc.nm1_segment.entity_identifier_code == "PR"


def test_other_payer_patient_information_does_not_replace_dependent_name():
    """
    A dependent patient has its own name loop 2010CA. NM1*QC inside the other subscriber loop is the other payer's
    patient information (2330C) and the dependent's name loop stays as it was.
    """
    text, segments = claim(
        dependent=True,
        other_subscriber=[
            "NM1*QC*1*DOE*JANE*S***MI*MEMBER003",
            "REF*SY*123456789",
        ],
    )
    assert_round_trip(text, segments)
