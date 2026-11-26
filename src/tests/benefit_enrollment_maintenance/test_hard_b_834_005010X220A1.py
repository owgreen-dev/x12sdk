"""
Segments mis-routed in the 834 005010X220A1 enrollment.

A coordination of benefits loop 2320 (COB) holds related entity loops 2330, each an NM1 with a qualifier of 36, GW
or IN. Qualifier 36 is also the qualifier of the member's employer loop 2100D, which sits before the coverage. An
NM1*36 that follows a COB belongs to 2330 and must not open an employer loop for the member. NM108 of the 2330 cases is FI, one of the qualifiers the 2330 NM1 model allows (FI, NI, XV; the 2100D employer allows 34 and ZZ), so only the routing is under test. Controls: the same
2330 with qualifier IN, and a genuine 2100D employer, both of which parse today.
"""

from tests.hard_b_support import assert_round_trip, interchange, parse_one

HEADER = ["ST*834*0001*005010X220A1", "BGN*00*12456*20260101*1200****2"]
BODY = [
    "N1*P5**FI*999888777",
    "N1*IN**FI*654456654",
    "INS*Y*18*021*20*A***FT",
    "REF*0F*123456789",
    "REF*1L*123456001",
    "DTP*356*D8*20260101",
    "NM1*IL*1*DOE*JANE****34*202443307",
    "N3*1715 SOUTHWIND AVENUE",
    "N4*ANYTOWN*PA*171110000",
    "DMG*D8*19700614*F",
    "HD*021**HMO",
    "DTP*348*D8*20260101",
    "LX*01",
    "NM1*P3*1*ROE*RICHARD**DR**SV*143766*25",
]
COB = "COB*P*POL123*1"
EMPLOYER = ["NM1*36*2*EXAMPLE EMPLOYER*****34*123456789"]


def enrollment(employer=False, cob_entities=None):
    """An 834 for one member; cob_entities is None for no COB, else the segments after the COB segment."""
    body = list(BODY)
    if employer:
        at = body.index("HD*021**HMO")
        body[at:at] = EMPLOYER
    if cob_entities is not None:
        body += [COB] + list(cob_entities)
    return interchange("BE", "005010X220A1", HEADER, body)


def test_control_enrollment_round_trips():
    text, segments = enrollment()
    assert_round_trip(text, segments)


def test_control_employer_loop_2100d_round_trips():
    text, segments = enrollment(employer=True)
    assert_round_trip(text, segments)


def test_control_cob_related_entity_in_qualifier_in_round_trips():
    text, segments = enrollment(
        cob_entities=["NM1*IN*2*EXAMPLE INSURER*****FI*123456789"]
    )
    assert_round_trip(text, segments)


def test_cob_related_entity_with_qualifier_36():
    text, segments = enrollment(
        cob_entities=["NM1*36*2*EXAMPLE EMPLOYER*****FI*123456789"]
    )
    assert_round_trip(text, segments)
    _assert_36_is_in_2330(text, employers=0)


def test_cob_related_entity_with_qualifier_36_beside_an_employer_loop():
    """Both an employer loop (2100D) and a COB related entity (2330) with the same qualifier keep their own place."""
    text, segments = enrollment(
        employer=True,
        cob_entities=["NM1*36*2*OTHER EMPLOYER*****FI*987654321"],
    )
    assert_round_trip(text, segments)
    _assert_36_is_in_2330(text, employers=1)


def test_cob_related_entity_with_qualifier_36_after_an_in_entity():
    text, segments = enrollment(
        cob_entities=[
            "NM1*IN*2*EXAMPLE INSURER*****FI*123456789",
            "NM1*36*2*EXAMPLE EMPLOYER*****FI*123456789",
        ]
    )
    assert_round_trip(text, segments)
    _assert_36_is_in_2330(text, employers=0)


def _assert_36_is_in_2330(text: str, employers: int) -> None:
    """The NM1*36 after the COB is a 2330 entity, and 2100D holds only the genuine employers."""
    member = parse_one(text).loop_2000[0]
    related = member.loop_2300[0].loop_2320[0].loop_2330
    assert "36" in [r.nm1_segment.entity_identifier_code for r in related]
    assert len(member.loop_2100d or []) == employers
