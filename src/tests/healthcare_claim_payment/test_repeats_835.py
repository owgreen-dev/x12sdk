"""
test_repeats_835.py

Repeating segments and loops in the 5010 835: inputs are built inline.
"""

from typing import List

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
VER = "005010X221A1"

HEAD = [
    "BPR*I*{pay}*C*CHK************20260101",
    "TRN*1*TRACE0001*1999999999",
    "N1*PR*EXAMPLE PAYER",
    "N3*1 TEST STREET",
    "N4*SPRINGFIELD*SD*55111",
    "N1*PE*EXAMPLE CLINIC*XX*1234567893",
]


def claim(n: int, paid: str = "80.00", extra_cas: List[str] = ()) -> List[str]:
    """One 2100 claim, charge 100.00, one claim-level adjustment closing the gap."""
    gap = f"{100 - float(paid):.2f}"
    return [
        f"CLP*C{n}*1*100.00*{paid}**12*ICN{n}",
        f"CAS*CO*45*{gap}",
        *extra_cas,
        f"NM1*QC*1*DOE*JANE****MI*M{n:03d}",
    ]


def build(pay: str, lx_blocks: List[List[str]], plb: List[str] = ()) -> str:
    """lx_blocks: one list of segments per LX; the LX segment is added here."""
    body = [h.format(pay=pay) for h in HEAD]
    for i, blk in enumerate(lx_blocks, start=1):
        body += [f"LX*{i}", *blk]
    body += list(plb)
    inner = [f"ST*835*0001*{VER}"] + body
    segs = [f"GS*HP*SENDER*RECEIVER*20260101*1200*1*X*{VER}"] + inner
    segs += [f"SE*{len(inner) + 1}*0001", "GE*1*1", "IEA*1*000000001"]
    return ISA + "".join(s + "~" for s in segs)


def parse(text: str):
    with X12ModelReader(text) as r:
        return list(r.models())


def st_to_se(text: str) -> List[str]:
    segs = [s.strip("\n") for s in text.split("~") if s.strip()]
    i = next(k for k, s in enumerate(segs) if s.startswith("ST*"))
    j = next(k for k, s in enumerate(segs) if s.startswith("SE*"))
    return segs[i : j + 1]


def roundtrip(text: str):
    models = parse(text)
    assert len(models) == 1
    out = models[0].x12(use_new_lines=False)
    assert st_to_se(out) == st_to_se(text)
    return models[0]


PLB1 = "PLB*1234567893*20261231*CV:ABC*-5.00"
PLB2 = "PLB*1234567893*20261231*L6:XYZ*3.00"
SVC = "SVC*HC:99211*100.00*80.00"


def test_one_plb_control():
    m = roundtrip(build("75.00", [claim(1)], [PLB1]))
    assert m.footer.plb_segment is not None


def test_one_plb_six_pairs_control():
    plb = "PLB*1234567893*20261231" + "".join(f"*CV:A{i}*1.0{i}" for i in range(1, 7))
    roundtrip(build("80.00", [claim(1)], [plb]))


def test_two_plb_segments():
    m = roundtrip(build("78.00", [claim(1)], [PLB1, PLB2]))
    assert len(m.footer.plb_segment) == 2


def test_three_plb_segments():
    plb3 = "PLB*1234567893*20261231*WO:QRS*1.00"
    m = roundtrip(build("79.00", [claim(1)], [PLB1, PLB2, plb3]))
    assert len(m.footer.plb_segment) == 3


def test_payment_only_with_plb_no_claims():
    roundtrip(build("5.00", [], [PLB1]))


def test_payment_only_no_claims_no_plb():
    roundtrip(build("0.00", []))


def test_several_claims_per_header():
    m = roundtrip(build("160.00", [claim(1) + claim(2)]))
    loops = m.loop_2000[0].loop_2100
    assert [lp.clp_segment.patient_control_number for lp in loops] == ["C1", "C2"]


def test_several_headers():
    m = roundtrip(build("160.00", [claim(1), claim(2)]))
    assert len(m.loop_2000) == 2


def test_several_service_lines():
    cas = ["CAS*CO*45*10.00"]
    line = lambda d: [SVC, f"DTM*472*202601{d:02d}"]  # noqa: E731
    blk = [
        "CLP*C1*1*100.00*80.00**12*ICN1",
        "CAS*CO*45*10.00",
        "NM1*QC*1*DOE*JANE****MI*M001",
        *line(1),
        *cas,
        *line(2),
        *line(3),
    ]
    # the balance counts claim and line adjustments together: 10 + 10 = 20
    m = roundtrip(build("80.00", [blk]))
    assert len(m.loop_2000[0].loop_2100[0].loop_2110) == 3


def test_cas_six_triples_at_claim_and_line_level():
    triple = "*45*1.00*1*45*1.00*1*45*1.00*1*45*1.00*1*45*1.00*1*45*1.00*1"
    blk = [
        "CLP*C1*1*100.00*88.00**12*ICN1",
        f"CAS*CO{triple}",
        "NM1*QC*1*DOE*JANE****MI*M001",
        SVC,
        f"CAS*PR{triple}",
    ]
    m = roundtrip(build("88.00", [blk]))
    assert m.loop_2000[0].loop_2100[0].cas_segment[0].monetary_amount_6 is not None


def test_several_nm1_entities():
    blk = claim(1) + ["NM1*82*1*ROE*RICK****XX*1234567893", "NM1*TT*2*EXAMPLE CO"]
    m = roundtrip(build("80.00", [blk]))
    assert len(m.loop_2000[0].loop_2100[0].nm1_segment) == 3


def test_several_transactions_in_group():
    one = build("80.00", [claim(1)])
    t1 = st_to_se(one)
    t2 = [s.replace("0001", "0002") for s in t1]
    segs = (
        [ISA[:-1], f"GS*HP*SENDER*RECEIVER*20260101*1200*1*X*{VER}"]
        + t1
        + t2
        + ["GE*2*1", "IEA*1*000000001"]
    )
    models = parse("".join(s + "~" for s in segs))
    assert len(models) == 2
