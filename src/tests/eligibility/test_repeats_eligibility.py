"""
Repeats in the 270 and 271 005010X279A1 transactions: a loop or segment the
structure lets repeat must be accepted, keep every occurrence in order and
serialize back to the same segments. Each case has a one-occurrence control.

Repeat maxima relied on (from public structure listings, not independently
verified): 2100C and 2100D DTP in the 270 repeat up to 9 times, 2110C and
2110D EQ repeat up to 99 times, 2120 NM1 loops repeat up to 23 times per
2110. Only acceptance is asserted, with two occurrences.
"""

import pytest

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
GS = "GS*{}*SENDERID*RECEIVERID*20260101*1200*1*X*005010X279A1~"
PAYER = ["HL*1**20*1", "NM1*PR*2*EXAMPLE PAYER*****PI*99999"]
PROVIDER = ["HL*2*1*21*1", "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893"]
SUBSCRIBER = ["HL*3*2*22*{}", "NM1*IL*1*DOE*JANE****MI*MEMBER001"]
DEPENDENT = ["HL*4*3*23*0", "NM1*03*1*DOE*JOHN"]
EB = "EB*1**30"
LS_BLOCK = ["LS*2120", "NM1*P3*1*ROE*RICHARD****SV*PROV001", "LE*2120"]


def build(kind: str, body: list) -> tuple:
    """Return the full interchange text and the ST..SE segment list."""
    code, group, bht = ("271", "HB", "11") if kind == "271" else ("270", "HS", "13")
    st = [f"ST*{code}*0001*005010X279A1", f"BHT*0022*{bht}*10001234*20260101*1200"]
    segs = st + PAYER + PROVIDER + body
    segs.append(f"SE*{len(segs) + 1}*0001")
    text = ISA + GS.format(group) + "~".join(segs) + "~GE*1*1~IEA*1*000000001~"
    return text, segs


def members(level: str, subscriber_detail: list, dependent_detail: list) -> list:
    """A subscriber, plus a dependent when level is D, each with its detail."""
    if level == "C":
        return [s.format("0") for s in SUBSCRIBER] + subscriber_detail
    return (
        [s.format("1") for s in SUBSCRIBER]
        + subscriber_detail
        + DEPENDENT
        + dependent_detail
    )


def parse(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())


def collect(node, key: str) -> list:
    """Every value stored under `key`, in document order, lists flattened."""
    found = []
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                found.extend(value if isinstance(value, list) else [value])
            else:
                found.extend(collect(value, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect(item, key))
    return found


def multi(kind: str, count: int) -> list:
    """count 1: one subscriber with one dependent; 2: two dependents, then a second subscriber."""
    tail = [EB] if kind == "271" else ["EQ*30"]

    def sub(hid, child):
        return [f"HL*{hid}*2*22*{child}", f"NM1*IL*1*DOE*S{hid}****MI*MEMBER00{hid}"]

    def dep(hid):
        return [f"HL*{hid}*3*23*0", f"NM1*03*1*DOE*D{hid}", *tail]

    if count == 1:
        return sub(3, 1) + dep(4)
    return sub(3, 1) + dep(4) + dep(5) + sub(6, 0) + tail


def check(kind: str, body: list, key: str, field: str, expected: list, codes=None):
    """Parse; check `field` of every `key` segment in order, then the round trip."""
    text, segs = build(kind, body)
    models = parse(text)
    assert len(models) == 1
    dump = models[0].model_dump(exclude_none=True)
    found = collect(dump, key)
    if codes:
        found = [f for f in found if f.get("entity_identifier_code") in codes]
    assert [f[field] for f in found] == expected
    out = models[0].x12(use_new_lines=False).replace("\n", "")
    start = out.index("ST*")
    end = out.index("~", out.index("SE*", start)) + 1
    assert out[start:end].rstrip("~").split("~") == segs


LEVELS = pytest.mark.parametrize("level", ["C", "D"])
LAST = "name_last_or_organization_name"


def entity(level: str, *detail: str) -> list:
    """271 member body where the detail belongs to the subscriber or dependent."""
    return (
        members(level, list(detail), [])
        if level == "C"
        else members(level, [], list(detail))
    )


# 271 loop 2120 (benefit related entity) and 2110 repeats


@LEVELS
def test_271_2120_one_block_control(level):
    check("271", entity(level, EB, *LS_BLOCK), "nm1_segment", LAST, ["ROE"], {"P3"})


@LEVELS
def test_271_2120_two_nm1_in_one_block(level):
    block = [LS_BLOCK[0], LS_BLOCK[1], "NM1*P3*1*POE*PAULA****SV*PROV002", LS_BLOCK[2]]
    check("271", entity(level, EB, *block), "nm1_segment", LAST, ["ROE", "POE"], {"P3"})


@LEVELS
def test_271_2110_two_ls_le_blocks(level):
    second = ["LS*2120", "NM1*P3*1*POE*PAULA****SV*PROV002", "LE*2120"]
    body = entity(level, EB, *LS_BLOCK, *second)
    check("271", body, "nm1_segment", LAST, ["ROE", "POE"], {"P3"})


@LEVELS
def test_271_two_eb_in_2110(level):
    check(
        "271",
        entity(level, EB, "EB*1**33"),
        "eb_segment",
        "service_type_code",
        [["30"], ["33"]],
    )


def test_271_several_subscribers_and_dependents_control():
    check("271", multi("271", 1), "nm1_segment", "name_first", ["S3"], {"IL"})
    check("271", multi("271", 1), "nm1_segment", "name_first", ["D4"], {"03"})


def test_271_several_subscribers_and_dependents():
    check("271", multi("271", 2), "nm1_segment", "name_first", ["S3", "S6"], {"IL"})
    check("271", multi("271", 2), "nm1_segment", "name_first", ["D4", "D5"], {"03"})


# 270 repeats


@LEVELS
def test_270_one_dtp_control(level):
    dtp = ["DTP*291*D8*20260101"]
    body = members(level, dtp, []) if level == "C" else members(level, [], dtp)
    check("270", body + ["EQ*30"], "dtp_segment", "date_time_qualifier", ["291"])


@LEVELS
def test_270_two_dtp_in_2100(level):
    dtps = ["DTP*102*D8*20260101", "DTP*291*D8*20260102"]
    body = members(level, dtps, []) if level == "C" else members(level, [], dtps)
    check("270", body + ["EQ*30"], "dtp_segment", "date_time_qualifier", ["102", "291"])


@LEVELS
def test_270_two_eq_in_2110(level):
    check(
        "270",
        members(level, [], []) + ["EQ*30", "EQ*33"],
        "eq_segment",
        "service_type_code",
        [["30"], ["33"]],
    )


def test_270_several_subscribers_and_dependents():
    check("270", multi("270", 2), "nm1_segment", "name_first", ["S3", "S6"], {"IL"})
    check("270", multi("270", 2), "nm1_segment", "name_first", ["D4", "D5"], {"03"})
