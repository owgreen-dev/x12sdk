"""
test_repeats_claim_status.py

Acceptance of repeated loops and segments in the 276 and 277 005010X212 transactions. Every input is built inline.
Each repeat has a one-occurrence positive control.
"""

import re
from typing import List

import pytest
from pydantic import BaseModel

from x12sdk.io import X12ModelReader

NPI_A = "1234567893"
NPI_B = "1234567801"
REF_QUALIFIERS = {
    "276": ["1K", "BLT", "LU", "6P", "EJ", "XZ", "D9"],
    "277": ["1K", "BLT", "EJ", "XZ", "VV", "D9"],
}


def _claim(t: str, n: int, refs: int = 0, stc: int = 1) -> List[str]:
    segs = [f"TRN*{'1' if t == '276' else '2'}*CLM{n}"]
    if t == "277":
        segs += [f"STC*P3:{317 + i}*2005091{i}**{100 + i}.00" for i in range(stc)]
    segs += [f"REF*{q}*R{i}" for i, q in enumerate(REF_QUALIFIERS[t][:refs])]
    return segs


def _hl(i, parent, code, child):
    return f"HL*{i}*{parent}*{code}" + (f"*{child}" if child != "" else "")


def _tree(
    t: str,
    sources=1,
    receivers=1,
    providers=1,
    subs=1,
    deps=0,
    claims=1,
    npis=(NPI_A,),
    stc=1,
    refs=0,
):
    """Builds the body segments of a 276 or 277 (HL tree in file order) with the given repeat counts."""
    segs: List[str] = []
    n = 0
    hid = 0

    def nid():
        nonlocal hid
        hid += 1
        return hid

    def claims_for():
        nonlocal n
        out: List[str] = []
        for _ in range(claims):
            n += 1
            out += _claim(t, n, refs, stc)
        return out

    dmg = ["DMG*D8*19800101*F"] if t == "276" else []
    for s in range(sources):
        a = nid()
        segs += [_hl(a, "", "20", 1), f"NM1*PR*2*PAYER{s}*****PI*PAY{s}"]
        for r in range(receivers):
            b = nid()
            segs += [_hl(b, a, "21", 1), f"NM1*41*2*RECEIVER{r}*****46*RCV{r}"]
            for p in range(providers):
                c = nid()
                segs += [_hl(c, b, "19", 1)]
                segs += [
                    f"NM1*1P*2*PROVIDER{p}{'ALT' * k}*****XX*{x}"
                    for k, x in enumerate(npis)
                ]
                for u in range(subs):
                    d = nid()
                    segs += [_hl(d, c, "22", 1 if deps else 0)] + dmg
                    segs += [f"NM1*IL*1*DOE{u}*JANE****MI*MEM{u}"]
                    if not deps:
                        segs += claims_for()
                    for k in range(deps):
                        e = nid()
                        segs += [_hl(e, d, "23", "")] + dmg
                        segs += [f"NM1*QC*1*DOE{u}*KID{k}"] + claims_for()
    return segs


def _interchange(t: str, body: List[str]) -> tuple:
    head = ["ST*%s*0001*005010X212" % t]
    head.append(
        "BHT*0010*13*REQ1*20250101*1200"
        if t == "276"
        else "BHT*0010*08*RSP1*20250101*1200*DG"
    )
    st_se = head + body
    st_se.append(f"SE*{len(st_se) + 1}*0001")
    func = "HR" if t == "276" else "HN"
    outer = [
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250101*1200*^*00501*000000001*0*T*:",
        f"GS*{func}*SENDER*RECEIVER*20250101*1200*1*X*005010X212",
        *st_se,
        "GE*1*1",
        "IEA*1*000000001",
    ]
    return "~".join(outer) + "~", "".join(s + "~" for s in st_se)


def _walk(obj, found: list):
    if isinstance(obj, BaseModel):
        if hasattr(obj, "hierarchical_id_number") or hasattr(obj, "trace_type_code"):
            found.append(obj)
        for name in type(obj).model_fields:
            _walk(getattr(obj, name), found)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, found)


def _roundtrip(t: str, body: List[str]):
    text, span = _interchange(t, body)
    with X12ModelReader(text) as r:
        models = list(r.models())
    assert len(models) == 1
    out = models[0].x12(use_new_lines=False)
    got = out[out.index("ST*") : out.index("SE*")]
    got = got + out[out.index("SE*") :].split("~")[0] + "~"
    assert got.replace("\n", "") == span
    found: list = []
    _walk(models[0], found)
    ids = [
        o.hierarchical_id_number for o in found if hasattr(o, "hierarchical_id_number")
    ]
    traces = [
        o.reference_identification_1 for o in found if hasattr(o, "trace_type_code")
    ]
    assert ids == [m.group(1) for s in body if (m := re.match(r"HL\*(\d+)\*", s))]
    assert traces == [s.split("*")[2] for s in body if s.startswith("TRN*")]
    return models[0]


TRANSACTIONS = ["276", "277"]

CASES = {
    "several_2000a": dict(sources=2),
    "several_2000b": dict(receivers=2),
    "several_2000c": dict(providers=2),
    "several_2000d": dict(subs=3),
    "several_claims_per_subscriber": dict(claims=3),
    "several_dependents_each_with_claim": dict(deps=3),
    "several_claims_per_dependent": dict(deps=2, claims=2),
    "claim_refs_distinct_qualifiers": dict(refs=5),
}


@pytest.mark.parametrize("t", TRANSACTIONS)
@pytest.mark.parametrize("case", sorted(CASES))
def test_repeat_accepted(t, case):
    _roundtrip(t, _tree(t, **CASES[case]))


@pytest.mark.parametrize("t", TRANSACTIONS)
def test_control_single_occurrence(t):
    _roundtrip(t, _tree(t))


@pytest.mark.parametrize("t", TRANSACTIONS)
def test_second_service_provider_name_for_npi_transition(t):
    """Two NM1*1P in one 2000C: both are kept, in order."""
    _roundtrip(t, _tree(t, npis=(NPI_A, NPI_B)))


def test_277_several_stc_per_claim():
    _roundtrip("277", _tree("277", stc=3))


def test_277_all_ref_qualifiers_on_claim():
    _roundtrip("277", _tree("277", refs=6))


def test_276_all_ref_qualifiers_on_claim():
    _roundtrip("276", _tree("276", refs=7))


def _with_trace_levels(receivers: int, providers: int, stc: int) -> List[str]:
    """277 body where each 2000B gets a 2200B and each 2000C a 2200C, then the claim-level loops follow."""
    body = _tree("277", receivers=receivers, providers=providers)
    out: List[str] = []
    n = 0
    for seg in body:
        out.append(seg)
        if seg.startswith("NM1*41*") or seg.startswith("NM1*1P*"):
            n += 1
            out.append(f"TRN*{'2' if seg.startswith('NM1*41') else '1'}*LVL{n}")
            out += [f"STC*P3:{317 + i}*2005091{i}" for i in range(stc)]
    return out


@pytest.mark.parametrize(
    "receivers,providers,stc", [(1, 1, 1), (2, 1, 1), (1, 2, 1), (1, 1, 3)]
)
def test_277_receiver_and_provider_level_trace_loops(receivers, providers, stc):
    """The first case is the one-occurrence control."""
    _roundtrip("277", _with_trace_levels(receivers, providers, stc))


@pytest.mark.parametrize("t", TRANSACTIONS)
@pytest.mark.parametrize("npis", [(NPI_A,), (NPI_A, NPI_B)])
def test_tracked_claim_properties(t, npis):
    """One and two NM1*1P: the provider is the first occurrence and every claim is still yielded."""
    text, _ = _interchange(t, _tree(t, npis=npis, subs=2, claims=2))
    with X12ModelReader(text) as r:
        model = next(iter(r.models()))
    claims = list(model.claims())
    assert [c.trace_number for c in claims] == ["CLM1", "CLM2", "CLM3", "CLM4"]
    for c in claims:
        assert c.provider_name == "PROVIDER0"
        assert c.payer_name == "PAYER0"
        assert not c.is_dependent
    assert [c.member_id for c in claims] == ["MEM0", "MEM0", "MEM1", "MEM1"]
    assert [c.patient_name for c in claims] == [("DOE0", "JANE")] * 2 + [
        ("DOE1", "JANE")
    ] * 2


@pytest.mark.parametrize("t", TRANSACTIONS)
def test_tracked_claim_dependent_properties(t):
    text, _ = _interchange(t, _tree(t, npis=(NPI_A, NPI_B), deps=2))
    with X12ModelReader(text) as r:
        model = next(iter(r.models()))
    claims = list(model.claims())
    assert [c.is_dependent for c in claims] == [True, True]
    assert [c.patient_name for c in claims] == [("DOE0", "KID0"), ("DOE0", "KID1")]
    assert {(c.provider_name, c.member_id) for c in claims} == {("PROVIDER0", "MEM0")}
