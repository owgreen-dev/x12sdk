"""
test_x12_277_dropped_segments.py

277 claim status (005010X212): every segment in a patient loop, claim and service line loop
must be kept by the parser, so the SE segment count agrees and the model writes back the input.
All interchanges are invented and built inline.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)

HEAD = [
    "BHT*0010*08*277X212*20260101*1200*DG",
    "HL*1**20*1",
    "NM1*PR*2*EXAMPLE PAYER*****PI*99999",
    "HL*2*1*21*1",
    "NM1*41*2*EXAMPLE CLEARINGHOUSE*****46*SUBMITTER1",
    "HL*3*2*19*1",
    "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893",
]

CLAIM = ["STC*P3:317*20260101**100.00", "REF*1K*CLAIM001", "DTP*472*D8*20251201"]


def trn(tag):
    return [f"TRN*2*TRACE{tag}"]


def svc(code):
    return [
        f"SVC*HC:{code}*100.00*50.00****1",
        "STC*P3:317*20260101",
        "DTP*472*D8*20251201",
    ]


def sub(hl, tag):
    return [f"HL*{hl}*3*22*0", f"NM1*IL*1*DOE*JANE****MI*MEMBER00{tag}"]


SUB_WITH_CHILD = ["HL*4*3*22*1", "NM1*IL*1*DOE*JANE****MI*MEMBER00A"]
DEP = ["HL*5*4*23", "NM1*QC*1*DOE*JIMMY"]


def build(body, se_count=None):
    inner = ["ST*277*0001*005010X212"] + HEAD + body
    n = len(inner) + 1 if se_count is None else se_count
    segs = (
        ["GS*HN*SENDER*RECEIVER*20260101*1200*1*X*005010X212"]
        + inner
        + [f"SE*{n}*0001", "GE*1*1", "IEA*1*000000001"]
    )
    return ISA + "".join(s + "~" for s in segs)


def st_to_se(text):
    segs = [s for s in text.split("~") if s.strip()]
    i = next(k for k, s in enumerate(segs) if s.startswith("ST*"))
    j = next(k for k, s in enumerate(segs) if s.startswith("SE*"))
    return segs[i : j + 1]


def parse(text):
    with X12ModelReader(text) as r:
        return list(r.models())


CONTROLS = {
    "one-svc": sub(4, "A") + trn("A") + CLAIM + svc("99213"),
    "no-svc": sub(4, "A") + trn("A") + CLAIM,
    "two-patients-one-provider": sub(4, "A")
    + trn("A")
    + CLAIM
    + sub(5, "B")
    + trn("B")
    + CLAIM,
    "two-providers": sub(4, "A")
    + trn("A")
    + CLAIM
    + [
        "HL*5*2*19*1",
        "NM1*1P*2*SECOND CLINIC*****XX*1234567893",
        "HL*6*5*22*0",
        "NM1*IL*1*DOE*JOHN****MI*MEMBER00C",
    ]
    + trn("C")
    + CLAIM,
    "subscriber-dependent-one-svc": SUB_WITH_CHILD
    + DEP
    + trn("D")
    + CLAIM
    + svc("99213"),
    "two-trn-one-patient": sub(4, "A") + trn("A") + CLAIM + trn("B") + CLAIM,
}

TWO_SVC = svc("99213") + svc("99214")

DEFECTS = {
    "claim-two-svc": sub(4, "A") + trn("A") + CLAIM + TWO_SVC,
    "claim-three-svc": sub(4, "A")
    + trn("A")
    + CLAIM
    + svc("99213")
    + svc("99214")
    + svc("99215"),
    "subscriber-dependent-two-svc": SUB_WITH_CHILD + DEP + trn("D") + CLAIM + TWO_SVC,
    "subscriber-no-trn-with-svc": sub(4, "A") + CLAIM + svc("99213"),
    "dependent-no-trn": SUB_WITH_CHILD + DEP + CLAIM,
    "dependent-no-trn-with-svc": SUB_WITH_CHILD + DEP + CLAIM + svc("99213"),
    "no-trn-two-svc": sub(4, "A") + CLAIM + TWO_SVC,
}


def _check_round_trip(body):
    text = build(body)
    models = parse(text)
    assert len(models) == 1
    assert st_to_se(models[0].x12(use_new_lines=False)) == st_to_se(text)


@pytest.mark.parametrize("body", CONTROLS.values(), ids=CONTROLS.keys())
def test_277_working_arrangements_round_trip(body):
    _check_round_trip(body)


@pytest.mark.parametrize("body", DEFECTS.values(), ids=DEFECTS.keys())
def test_277_no_segments_dropped(body):
    _check_round_trip(body)


def test_277_wrong_se_count_is_still_rejected():
    body = CONTROLS["one-svc"]
    good = build(body)
    assert len(parse(good)) == 1
    bad = build(body, se_count=len(st_to_se(good)) + 1)
    with pytest.raises(ValidationError, match="SE segment count"):
        parse(bad)


def _subscriber(model):
    return model.loop_2000a[0].loop_2000b[0].loop_2000c[0].loop_2000d[0]


def _segment_ids(group, names):
    """Count the segments of each name held directly by one loop instance."""
    out = {}
    for name in names:
        value = getattr(group, name, None)
        out[name] = len(value) if isinstance(value, list) else int(value is not None)
    return out


@pytest.mark.parametrize(
    "n_svc, codes", [(2, ("99213", "99214")), (3, ("99213", "99214", "99215"))]
)
def test_277_subscriber_claim_holds_every_service_line(n_svc, codes):
    body = sub(4, "A") + trn("A") + CLAIM + sum((svc(c) for c in codes), [])
    models = parse(build(body))
    assert len(models) == 1
    claims = _subscriber(models[0]).loop_2200d
    assert len(claims) == 1
    lines = claims[0].loop_2220d
    assert len(lines) == n_svc
    for line in lines:
        assert _segment_ids(line, ["svc_segment", "stc_segment", "dtp_segment"]) == {
            "svc_segment": 1,
            "stc_segment": 1,
            "dtp_segment": 1,
        }
    # the claim's own STC, REF and DTP are not moved onto a service line
    assert _segment_ids(claims[0], ["stc_segment", "ref_segment", "dtp_segment"]) == {
        "stc_segment": 1,
        "ref_segment": 1,
        "dtp_segment": 1,
    }


def test_277_dependent_claim_holds_every_service_line():
    body = SUB_WITH_CHILD + DEP + trn("D") + CLAIM + TWO_SVC
    models = parse(build(body))
    assert len(models) == 1
    dependent = _subscriber(models[0]).loop_2000e[0]
    claims = dependent.loop_2200e
    assert len(claims) == 1
    lines = claims[0].loop_2220e
    assert len(lines) == 2
    for line in lines:
        assert _segment_ids(line, ["svc_segment", "stc_segment", "dtp_segment"]) == {
            "svc_segment": 1,
            "stc_segment": 1,
            "dtp_segment": 1,
        }


def test_277_claim_without_trn_has_no_trace_number():
    body = sub(4, "A") + CLAIM + svc("99213")
    models = parse(build(body))
    assert len(models) == 1
    claims = list(models[0].claims())
    assert len(claims) == 1
    assert claims[0].trace_number is None


def test_277_claim_with_trn_has_trace_number():
    models = parse(build(CONTROLS["one-svc"]))
    claims = list(models[0].claims())
    assert [c.trace_number for c in claims] == ["TRACEA"]


def test_277_stc_after_dependent_name_then_later_trn_round_trips():
    body = (
        SUB_WITH_CHILD
        + DEP
        + ["STC*P3:317*20260101**100.00"]
        + trn("D")
        + CLAIM
        + TWO_SVC
    )
    _check_round_trip(body)


def _assert_rejected_or_held_by_its_subscriber(body):
    """
    A segment placed directly under a subscriber that has dependents (HL04 = 1),
    with no dependent loop opened, has two acceptable outcomes: the file is
    rejected with a ValidationError, or it parses and the segment is held by the
    subscriber it followed, not by an earlier subscriber, with nothing dropped
    (each subscriber writes back exactly its own segments, and the transaction
    set round-trips). Silent attachment to another subscriber, a dropped segment
    and a raw exception are not acceptable.
    """
    text = build(body)
    try:
        models = parse(text)
    except ValidationError:
        return
    assert len(models) == 1
    assert models[0].x12(use_new_lines=False).strip().rstrip("~").split("~") == (
        st_to_se(text)
    )
    owned = []
    for segment in body:
        if segment.startswith("HL*") and segment.split("*")[3] == "22":
            owned.append([])
        if owned:
            owned[-1].append(segment)
    subscribers = models[0].loop_2000a[0].loop_2000b[0].loop_2000c[0].loop_2000d
    assert [s.x12(use_new_lines=False) for s in subscribers] == [
        "~".join(segments) + "~" for segments in owned
    ]


def test_277_stc_after_subscriber_with_dependents_and_no_dependent_loop():
    """
    STC straight after a subscriber that has dependents, with no dependent loop
    opened: either a ValidationError, or the STC stays with that subscriber and
    the file round-trips.
    """
    _assert_rejected_or_held_by_its_subscriber(
        SUB_WITH_CHILD + ["STC*P3:317*20260101**100.00"]
    )


def test_277_stc_after_second_subscriber_with_dependents_is_not_attached_to_first():
    """
    Subscriber A (no dependents) has a claim; subscriber B (has dependents) is
    followed directly by an STC. Either a ValidationError, or the STC is held by
    subscriber B and subscriber A still holds only its own segments.
    """
    body = (
        sub(4, "A")
        + trn("A")
        + CLAIM
        + ["HL*5*3*22*1", "NM1*IL*1*DOE*JANE****MI*MEMBER00B"]
        + ["STC*P3:317*20260101**100.00"]
    )
    _assert_rejected_or_held_by_its_subscriber(body)


_SUB_B_WITH_DEPENDENTS = ["HL*5*3*22*1", "NM1*IL*1*DOE*JANE****MI*MEMBER00B"]

_MISPLACED = {
    "trn": trn("B"),
    "svc": svc("99213"),
}


@pytest.mark.parametrize("tail", _MISPLACED.values(), ids=_MISPLACED.keys())
def test_277_misplaced_segment_after_subscriber_with_dependents_after_prior_subscriber(
    tail,
):
    """
    A TRN or SVC directly after a subscriber that has dependents (no dependent
    loop opened), following an earlier subscriber with a claim: either a
    ValidationError, or the segment is held by the later subscriber and the
    earlier one is unchanged.
    """
    body = sub(4, "A") + trn("A") + CLAIM + _SUB_B_WITH_DEPENDENTS + tail
    _assert_rejected_or_held_by_its_subscriber(body)


@pytest.mark.parametrize("tail", _MISPLACED.values(), ids=_MISPLACED.keys())
def test_277_misplaced_segment_after_first_subscriber_with_dependents(tail):
    """
    A TRN or SVC directly after the first patient, a subscriber that has
    dependents (no dependent loop opened): either a ValidationError, or the
    segment is held by that subscriber and the file round-trips.
    """
    _assert_rejected_or_held_by_its_subscriber(SUB_WITH_CHILD + tail)
