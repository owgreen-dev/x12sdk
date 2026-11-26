"""
test_repeats_837.py

Acceptance tests for loops and segments that the 5010 837 guides let repeat
(professional X222A2, institutional X223A3, dental X224A2). Every input is built inline
from invented values. Each test checks that the model holds every occurrence in order
and that serialising reproduces the transaction segments.
"""

from typing import List

import pytest

from x12sdk.io import X12ModelReader

GUIDES = {
    "P": ("005010X222A2", "SV1*HC:99213*1.00*UN*1***1"),
    "I": ("005010X223A3", "SV2*0450*HC:99283*1.00*UN*1"),
    "D": ("005010X224A2", "SV3*AD:D0120*1.00****1"),
}
LINE_DTP = "DTP*472*D8*20260110"
CL1 = "CL1*3**01"
PATIENT = [
    "PAT*19",
    "NM1*QC*1*DOE*JOHN",
    "N3*200 OAK AVE",
    "N4*SPRINGFIELD*IL*62702",
    "DMG*D8*20100101*M",
]


def _billing(n: int) -> List[str]:
    return [
        "PRV*BI*PXC*203BF0100Y",
        f"NM1*85*2*EXAMPLE GROUP {n}*****XX*1234567893",
        "N3*100 MAIN ST",
        "N4*SPRINGFIELD*IL*62701",
        "REF*EI*123456789",
    ]


def _subscriber(dependent: bool) -> List[str]:
    return [
        "SBR*P*18*GRP001******CI" if not dependent else "SBR*P**GRP001******CI",
        "NM1*IL*1*DOE*JANE****MI*X123456789",
        "N3*200 OAK AVE",
        "N4*SPRINGFIELD*IL*62702",
        "DMG*D8*19800101*F",
        "NM1*PR*2*EXAMPLE PLAN*****PI*99999",
    ]


def _claim(kind, lines, refs, his, loops, claim_id) -> List[str]:
    sv = GUIDES[kind][1]
    out = [f"CLM*{claim_id}*{lines}.00***11:B:1*Y*A*Y*Y"]
    if kind == "I":
        out = [
            f"CLM*{claim_id}*{lines}.00***11:A:1*Y*A*Y*Y",
            "DTP*434*D8*20260110",
            CL1,
        ]
    if kind == "D":
        out.append(LINE_DTP)
    out += list(refs)
    if kind != "D":
        out += ["HI*BK:3669" if kind == "I" else "HI*ABK:E119"] + list(his)
    out += list(loops)
    for n in range(1, lines + 1):
        out += [f"LX*{n}", sv]
        if kind != "D":
            out.append(LINE_DTP)
    return out


def build(
    kind: str,
    billing: int = 1,
    subscribers: int = 1,
    dependent: bool = False,
    claims: int = 1,
    lines: int = 1,
    refs=(),
    his=(),
    loops=(),
) -> str:
    """Return an interchange; claims hang off the dependent when one is requested."""
    version = GUIDES[kind][0]
    seg = [
        "BHT*0019*00*REPEAT0001*20260115*1030*CH",
        "NM1*41*2*EXAMPLE GROUP*****46*SUBMIT01",
        "PER*IC*BILLING OFFICE*TE*5555550100",
        "NM1*40*2*EXAMPLE PLAN*****46*RECV01",
    ]
    hl = 0
    for b in range(1, billing + 1):
        hl += 1
        bp = hl
        seg += [f"HL*{hl}**20*1"] + _billing(b)
        for _ in range(subscribers):
            hl += 1
            sub = hl
            seg += [f"HL*{hl}*{bp}*22*{1 if dependent else 0}"] + _subscriber(False)
            if dependent:
                hl += 1
                seg += [f"HL*{hl}*{sub}*23*0"] + PATIENT
            for c in range(claims):
                seg += _claim(kind, lines, refs, his, loops, f"PCN{b}{hl}{c}")
    st = ["ST*837*0001*" + version] + seg
    st.append(f"SE*{len(st) + 1}*0001")
    isa = (
        "ISA*00*          *00*          *30*SYNTHPROV      *30*SYNTHPAYER     "
        "*260115*1030*^*00501*000000101*0*T*:"
    )
    full = [isa, f"GS*HC*SYNTHPROV*SYNTHPAYER*20260115*1030*101*X*{version}"] + st
    full += ["GE*1*101", "IEA*1*000000101"]
    return "~\n".join(full) + "~\n"


def roundtrip(text: str):
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    model = models[0]
    out = model.x12(use_new_lines=False)
    assert _span(out) == _span(text)
    return model


def _span(text: str) -> str:
    flat = text.replace("\n", "")
    return (
        flat[flat.index("ST*") : flat.index("SE*")].rstrip("~")
        + "~"
        + flat[flat.index("SE*") : flat.index("~", flat.index("SE*"))]
    )


def _claims(model) -> list:
    found = []
    for a in model.loop_2000a:
        for b in a.loop_2000b:
            found += b.loop_2300 or []
            for c in b.loop_2000c or []:
                found += c.loop_2300 or []
    return found


ALL = pytest.mark.parametrize("kind", ["P", "I", "D"])
REF = ["REF*D9*A1", "REF*F8*B2"]
OTHER = [
    [
        f"SBR*S*01*GRP00{n}******CI",
        "OI***Y***Y",
        f"NM1*IL*1*DOE*JANE****MI*X12345678{n}",
        f"NM1*PR*2*OTHER PLAN {n}*****PI*8888{n}",
    ]
    for n in (1, 2)
]
PROVIDERS = [
    "NM1*DN*1*DOE*JOHN****XX*1234567893",
    "NM1*P3*1*ROE*RICK****XX*1234567893",
]


@ALL
def test_control_single_claim(kind):
    model = roundtrip(build(kind))
    assert len(_claims(model)) == 1


@ALL
def test_two_billing_providers(kind):
    model = roundtrip(build(kind, billing=2))
    assert len(model.loop_2000a) == 2
    assert len(_claims(model)) == 2


@ALL
def test_two_subscribers(kind):
    model = roundtrip(build(kind, subscribers=2))
    assert len(model.loop_2000a[0].loop_2000b) == 2


@ALL
def test_dependent_with_two_claims(kind):
    model = roundtrip(build(kind, dependent=True, claims=2))
    dependents = model.loop_2000a[0].loop_2000b[0].loop_2000c
    assert len(dependents) == 1
    assert len(dependents[0].loop_2300) == 2


@ALL
def test_fifty_service_lines(kind):
    model = roundtrip(build(kind, lines=50))
    assert len(_claims(model)[0].loop_2400) == 50


@ALL
def test_two_claim_references_in_order(kind):
    claim = _claims(roundtrip(build(kind, refs=REF)))[0]
    assert [r.reference_identification for r in claim.ref_segment] == ["A1", "B2"]


@ALL
def test_two_other_subscriber_loops(kind):
    claim = _claims(roundtrip(build(kind, loops=OTHER[0] + OTHER[1])))[0]
    assert [o.sbr_segment.group_policy_number for o in claim.loop_2320] == [
        "GRP001",
        "GRP002",
    ]


@pytest.mark.parametrize("kind", ["P", "I"])
def test_two_diagnosis_segments(kind):
    claim = _claims(roundtrip(build(kind, his=["HI*ABF:I10"])))[0]
    assert len(claim.hi_segment) == 2


@pytest.mark.parametrize("kind", ["P", "D"])
def test_control_one_referring_provider(kind):
    claim = _claims(roundtrip(build(kind, loops=PROVIDERS[:1])))[0]
    assert claim.loop_2310a is not None


@pytest.mark.parametrize("kind", ["P", "D"])
def test_two_referring_providers_in_order(kind):
    claim = _claims(roundtrip(build(kind, loops=PROVIDERS)))[0]
    assert len(claim.loop_2310a) == 2
    assert [p.nm1_segment.name_last_or_organization_name for p in claim.loop_2310a] == [
        "DOE",
        "ROE",
    ]


@pytest.mark.parametrize("lines", [51, 100])
def test_institutional_service_lines_beyond_fifty(lines):
    model = roundtrip(build("I", lines=lines))
    assert len(_claims(model)[0].loop_2400) == lines
