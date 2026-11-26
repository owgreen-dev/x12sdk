"""
test_repeats_834.py

834 005010X220A1: loops and segments that the structure lets repeat must be
accepted and must round trip with every occurrence kept, in order. Each input
is built inline from invented data. Every repeating case has a single
occurrence control that must pass, which shows the input itself is valid.

Repeat maxima relied on (taken from a public structure listing, unverified):
2100E up to 3, 2100G up to 13, 2310 N3 up to 2, 1000C up to 2. Loop 2700 and
the 2300, 2310, 2320 and 2330 loops are listed as repeating without a small
limit. The tests assert acceptance only, never rejection above a maximum.
"""

import pytest

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*>*00501*000000001*0*T*:~"
)
HEAD = ["BGN*00*12456*19980520*1200****2", "N1*P5**FI*999888777", "N1*IN**FI*654456654"]
MEMBER = [
    "INS*Y*18*021*20*A***FT",
    "REF*0F*123456789",
    "REF*1L*123456001",
    "DTP*356*D8*19960523",
    "NM1*IL*1*DOE*JANE*P***34*123456789",
    "N3*100 MARKET ST",
    "N4*CAMP HILL*PA*17011",
    "DMG*D8*19400816*F",
]
COVERAGE = ["HD*021**HLT", "DTP*348*D8*19960601"]
PROVIDER = "NM1*P3*1*DOE*JOHN****XX*1234567893"


def build(body, head=HEAD):
    """Returns (interchange text, ST..SE segments) with the SE count computed."""
    inner = ["ST*834*0001*005010X220A1", *head, *body]
    inner.append(f"SE*{len(inner) + 1}*0001")
    gs = "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1"
    text = ISA + "".join(f"{s}~" for s in [gs, *inner, "GE*1*1", "IEA*1*000000001"])
    return text, inner


def parse(body, head=HEAD):
    text, segments = build(body, head)
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    return models[0], segments


def assert_round_trip(model, segments):
    out = model.x12(use_new_lines=False).replace("\n", "").rstrip("~")
    assert out == "~".join(segments)


def assert_list_of(value, length):
    assert isinstance(value, list)
    assert len(value) == length


def category(n, name, ref):
    return [f"LX*{n}", f"N1*75*{name}", f"REF*17*{ref}"]


def test_one_reporting_category_control():
    body = MEMBER + COVERAGE + ["LS*2700", *category(1, "GRPA", "A1"), "LE*2700"]
    model, segments = parse(body)
    assert_list_of(model.loop_2000[0].loop_2700, 1)
    assert_round_trip(model, segments)


@pytest.mark.parametrize("count", [2, 3])
def test_reporting_categories_repeat(count):
    cats = [s for n in range(1, count + 1) for s in category(n, f"GRP{n}", f"A{n}")]
    body = MEMBER + COVERAGE + ["LS*2700", *cats, "LE*2700"]
    model, segments = parse(body)
    assert_list_of(model.loop_2000[0].loop_2700, count)
    assert_round_trip(model, segments)


def test_one_school_control():
    model, segments = parse(MEMBER + ["NM1*M8*1*ONE*SCHOOL"] + COVERAGE)
    assert_list_of(model.loop_2000[0].loop_2100e, 1)
    assert_round_trip(model, segments)


@pytest.mark.parametrize("count", [2, 3])
def test_member_school_repeats(count):
    schools = [f"NM1*M8*1*SCHOOL{n}*ONE" for n in range(1, count + 1)]
    model, segments = parse(MEMBER + schools + COVERAGE)
    assert_list_of(model.loop_2000[0].loop_2100e, count)
    assert_round_trip(model, segments)


def test_one_responsible_person_control():
    model, segments = parse(MEMBER + ["NM1*S1*1*DOE*SAM"] + COVERAGE)
    assert_list_of(model.loop_2000[0].loop_2100g, 1)
    assert_round_trip(model, segments)


@pytest.mark.parametrize("count", [2, 13])
def test_responsible_person_repeats(count):
    people = [f"NM1*S1*1*DOE*PERSON{n}" for n in range(1, count + 1)]
    model, segments = parse(MEMBER + people + COVERAGE)
    assert_list_of(model.loop_2000[0].loop_2100g, count)
    assert_round_trip(model, segments)


def provider_loop(*addresses):
    return COVERAGE + ["LX*1", PROVIDER, *addresses]


def test_one_provider_address_control():
    model, segments = parse(MEMBER + provider_loop("N3*1 MAIN ST"))
    provider = model.loop_2000[0].loop_2300[0].loop_2310[0]
    assert_list_of(provider.n3_segment, 1)
    assert_round_trip(model, segments)


def test_provider_address_two_lines():
    body = MEMBER + provider_loop("N3*1 MAIN ST", "N3*SUITE 2")
    model, segments = parse(body)
    provider = model.loop_2000[0].loop_2300[0].loop_2310[0]
    assert_list_of(provider.n3_segment, 2)
    assert_round_trip(model, segments)


def test_several_coverages_providers_and_cob_loops():
    """Loops reported as repeating that already work: kept as regression cover."""
    first = COVERAGE + ["LX*1", PROVIDER, "LX*2", PROVIDER]
    first += ["COB*P*POLICYONE*1", "NM1*IN*2*OTHER PAYER", "NM1*GW*2*OTHER TPA"]
    first += ["COB*S*POLICYTWO*5"]
    second = ["HD*021**DEN", "DTP*348*D8*19960601"]
    model, segments = parse(MEMBER + first + second)
    coverages = model.loop_2000[0].loop_2300
    assert len(coverages) == 2
    assert len(coverages[0].loop_2310) == 2
    assert len(coverages[0].loop_2320) == 2
    assert len(coverages[0].loop_2320[0].loop_2330) == 2
    assert_round_trip(model, segments)


def test_several_members_in_one_transaction():
    second = [s.replace("JANE", "JOHN") for s in MEMBER]
    model, segments = parse(MEMBER + COVERAGE + second + COVERAGE)
    assert len(model.loop_2000) == 2
    assert_round_trip(model, segments)


@pytest.mark.parametrize("count", [1, 2])
def test_broker_name_loop_repeats(count):
    brokers = ["N1*BO*BROKER ONE*FI*111222333", "N1*TV*BROKER TWO*FI*444555666"]
    head = HEAD + brokers[:count]
    model, segments = parse(MEMBER + COVERAGE, head)
    assert len(model.loop_1000c) == count
    assert_round_trip(model, segments)


def test_absent_school_person_and_address_values():
    """Absent loops stay None (the member dict never gets the key); an absent
    2310 N3 is [] because the parser pre-seeds it (parsing.py, the 2310 dict
    created with "n3_segment": [])."""
    model, segments = parse(MEMBER + COVERAGE + ["LX*1", PROVIDER])
    member = model.loop_2000[0]
    assert member.loop_2100e is None
    assert member.loop_2100g is None
    assert member.loop_2300[0].loop_2310[0].n3_segment == []
    assert_round_trip(model, segments)
