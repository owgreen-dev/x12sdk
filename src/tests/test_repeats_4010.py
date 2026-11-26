"""
test_repeats_4010.py

Repeated loops in the 4010 837 professional (004010X098A1) and institutional
(004010X096A1) guides. Every input is built inline with invented data. The repeat maxima are unverified (third-party summaries), so
only acceptance up to the counts used is asserted. A count of one is the
positive control; each test asserts acceptance, that the parsed loops are a
list in order, and that the transaction serialises back to its input.
"""

import pytest

from x12sdk.io import X12ModelReader

PRO = "004010X098A1"
INST = "004010X096A1"


def _interchange(version: str, body: list) -> tuple:
    """Wrap body segments in ISA/GS/ST..SE/GE/IEA; returns (text, ST..SE span)."""
    st = ["ST*837*0001"] + body
    st.append(f"SE*{len(st) + 1}*0001")
    span = "".join(f"{s}~" for s in st)
    head = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*200101*1200*^*00501*000000001*0*T*:~"
        f"GS*HC*SENDER*RECEIVER*20200101*1200*1*X*{version}~"
    )
    return head + span + "GE*1*1~IEA*1*000000001~", span


def _round_trip(version: str, body: list) -> list:
    text, span = _interchange(version, body)
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    assert models[0].x12(use_new_lines=False).replace("\n", "") == span
    return models


def _pro(claim_extra=(), after_provider=(), lines=None, other_sub=(), refs=()) -> list:
    """Professional claim: lines is a list of (charge, extra segments)."""
    lines = lines or [("10.00", [])]
    total = sum(float(c) for c, _ in lines)
    body = [
        "BHT*0019*00*0123*19981015*1023*CH",
        "REF*87*004010X098",
        "NM1*41*2*DOE BILLING*****46*567890",
        "PER*IC*JANE*TE*3055551234",
        "NM1*40*2*TEST PAYER*****46*66783",
        "HL*1**20*1",
        "NM1*85*2*DOE CLINIC*****24*587654321",
        "N3*1 MAIN ST",
        "N4*MIAMI*FL*33111",
        "HL*2*1*22*0",
        "SBR*P*18*12312-A******CI",
        "NM1*IL*1*DOE*JANE****MI*000221111",
        "N3*2 MAIN ST",
        "N4*MIAMI*FL*33413",
        "DMG*D8*19430501*F",
        "NM1*PR*2*TEST PAYER*****PI*741234",
        f"CLM*CLAIM1*{total:.2f}***11::1*Y*A*Y*Y*C",
        *refs,
        "HI*BK:4779",
        *claim_extra,
        "NM1*82*1*DOE*JOHN****34*112233334",
        "PRV*PE*ZZ*203BF0100Y",
        "NM1*77*2*DOE CLINIC*****24*581234567",
        "N3*3 MAIN ST",
        "N4*MIAMI*FL*33111",
        *after_provider,
        *other_sub,
    ]
    for n, (charge, extra) in enumerate(lines, 1):
        body += [
            f"LX*{n}",
            f"SV1*HC:99213*{charge}*UN*1.00***1",
            "DTP*472*D8*19981003",
            *extra,
        ]
    return body


def _inst(claim_extra=(), lines=None) -> list:
    """Institutional claim: lines is a list of (charge, extra segments)."""
    lines = lines or [("13.39", [])]
    total = sum(float(c) for c, _ in lines)
    body = [
        "BHT*0019*00*0123*19960918*0932*CH",
        "REF*87*004010X096",
        "NM1*41*2*TEST PAYER*****46*00120",
        "PER*IC*JANE DOE*TE*9005555555",
        "NM1*40*2*TEST HOSPITAL*****46*12345",
        "HL*1**20*1",
        "PRV*BI*ZZ*203BA0200N",
        "NM1*85*2*TEST HOSPITAL*****XX*1234567893",
        "N3*1 MAIN STREET",
        "N4*CENTERVILLE*PA*17111",
        "HL*2*1*22*0",
        "SBR*P*18*******MB",
        "NM1*IL*1*DOE*JOHN*T***MI*030005074A",
        "N3*125 CITY AVENUE",
        "N4*CENTERVILLE*PA*17111",
        "DMG*D8*19261111*M",
        "NM1*PR*2*TEST PAYER*****PI*00435",
        f"CLM*CLAIM1*{total:.2f}***14:A:1**A*Y*Y",
        "DTP*434*D8*19960911",
        "CL1*3*1",
        "HI*BK:3669",
        *claim_extra,
        "NM1*71*1*DOE*JANE****XX*1234567893",
        "PRV*AT*ZZ*363LP0200N",
    ]
    for n, (charge, extra) in enumerate(lines, 1):
        body += [
            f"LX*{n}",
            f"SV2*305*HC:85025*{charge}*UN*1.00",
            "DTP*472*D8*19960911",
            *extra,
        ]
    return body


CR7 = ["CR7*PT*1*1", "CR7*OT*1*1", "CR7*SN*1*1"]
DISCIPLINES = ["PT", "OT", "SN"]
REFERRERS = [
    "NM1*DN*1*ALPHA*AMY****XX*1234567893",
    "NM1*P3*1*BETA*BOB****XX*1234567893",
]


def _referrers(count):
    return [x for nm1 in REFERRERS[:count] for x in (nm1, "PRV*RF*ZZ*203BF0100Y")]


def _claim(models):
    return models[0].loop_2000a[0].loop_2000b[0].loop_2300[0]


def _last_names(loops):
    return [loop.nm1_segment.name_last_or_organization_name for loop in loops]


GUIDES = [(PRO, _pro), (INST, _inst)]


def _disciplines(plans):
    return [p.cr7_segment.discipline_type_code for p in plans]


# Loop 2305 (home health care plan): counts 1 to 3 are used.
@pytest.mark.parametrize("version,build", GUIDES)
@pytest.mark.parametrize("count", [1, 2, 3])
def test_home_health_care_plan_repeats(version, build, count):
    plans = _claim(_round_trip(version, build(claim_extra=CR7[:count]))).loop_2305
    assert _disciplines(plans) == DISCIPLINES[:count]


@pytest.mark.parametrize("version,build", GUIDES)
@pytest.mark.parametrize("count", [1, 2, 3])
def test_home_health_hsd_attaches_to_its_own_plan(version, build, count):
    extra = []
    for n in range(count):
        extra += [CR7[n], f"HSD*VS*{n + 2}*WK*3*35*1"]
    plans = _claim(_round_trip(version, build(claim_extra=extra))).loop_2305
    assert _disciplines(plans) == DISCIPLINES[:count]
    assert [[int(h.quantity) for h in p.hsd_segment] for p in plans] == [
        [n + 2] for n in range(count)
    ]


# Loop 2310A (referring provider).
@pytest.mark.parametrize("count", [1, 2])
def test_professional_referring_provider_repeats(count):
    extra = _referrers(count)
    loops = _claim(_round_trip(PRO, _pro(claim_extra=extra))).loop_2310a
    assert _last_names(loops) == ["ALPHA", "BETA"][:count]
    assert all(loop.prv_segment.provider_code == "RF" for loop in loops)


# Loop 2420F (service line referring provider).
@pytest.mark.parametrize("count", [1, 2])
def test_professional_line_referring_provider_repeats(count):
    extra = _referrers(count)
    models = _round_trip(PRO, _pro(lines=[("10.00", extra)]))
    loops = _claim(models).loop_2400[0].loop_2420f
    assert _last_names(loops) == ["ALPHA", "BETA"][:count]


# Loop 2420G (line other payer prior authorization): counts 1, 2 and 4.
@pytest.mark.parametrize("count", [1, 2, 4])
def test_professional_line_other_payer_prior_auth_repeats(count):
    extra = []
    for n in range(count):
        extra += [f"NM1*PR*2*OTHER PAYER {n}*****PI*9900{n}", f"REF*G1*AUTH{n}"]
    models = _round_trip(PRO, _pro(lines=[("10.00", extra)]))
    loops = _claim(models).loop_2400[0].loop_2420g
    assert [loop.nm1_segment.identification_code for loop in loops] == [
        f"9900{n}" for n in range(count)
    ]
    assert [loop.ref_segment[0].reference_identification for loop in loops] == [
        f"AUTH{n}" for n in range(count)
    ]


# Loop 2330D (other payer referring provider), inside loop 2320.
@pytest.mark.parametrize("count", [1, 2])
def test_professional_other_payer_referring_provider_repeats(count):
    other = [
        "SBR*S*01***C1****CI",
        "NM1*IL*1*DOE*JOHN****MI*222004433",
        "NM1*PR*2*OTHER PAYER*****PI*99999",
    ]
    for n, nm1 in enumerate(REFERRERS[:count]):
        other += [nm1, f"REF*G2*REF1234{n}"]
    loops = _claim(_round_trip(PRO, _pro(other_sub=other))).loop_2320[0].loop_2330d
    assert _last_names(loops) == ["ALPHA", "BETA"][:count]
    assert [loop.ref_segment[0].reference_identification for loop in loops] == [
        f"REF1234{n}" for n in range(count)
    ]


# Loop 2320 (other subscriber information): counts 1 to 3.
@pytest.mark.parametrize("count", [1, 2, 3])
def test_professional_other_subscriber_loops_repeat(count):
    other = []
    for n in range(count):
        other += [
            "SBR*S*01***C1****CI",
            f"NM1*IL*1*DOE*JOHN****MI*22200443{n}",
            f"NM1*PR*2*OTHER PAYER {n}*****PI*9999{n}",
        ]
    loops = _claim(_round_trip(PRO, _pro(other_sub=other))).loop_2320
    assert [loop.loop_2330a.nm1_segment.identification_code for loop in loops] == [
        f"22200443{n}" for n in range(count)
    ]


# Loop 2400 (service lines). The institutional cap in loops.py is 50; 51 and
# 100 lines are used here. The professional cap of 50 is left as it is.
@pytest.mark.parametrize("count", [1, 50])
def test_professional_service_lines_up_to_fifty(count):
    _round_trip(PRO, _pro(lines=[("1.00", [])] * count))


@pytest.mark.parametrize("count", [1, 50, 51, 100])
def test_institutional_service_lines_beyond_fifty(count):
    _round_trip(INST, _inst(lines=[("1.00", [])] * count))


# Repeated claim-level REF (before HI in segment order) and HI segments.
def test_professional_repeated_claim_references():
    refs = ["REF*D9*A1", "REF*F8*B2", "REF*9A*C3"]
    _round_trip(PRO, _pro(refs=refs))


def test_institutional_repeated_diagnosis_segments():
    his = ["HI*BF:4019*BF:79431", "HI*BQ:153:D8:19960911", "HI*BG:09"]
    _round_trip(INST, _inst(claim_extra=his))
