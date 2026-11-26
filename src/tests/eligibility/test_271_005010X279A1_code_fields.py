"""
271 005010X279A1: AAA03, AAA04 and EB03 accept any well-formed code, whatever the loop.

Every input is built inline from invented values.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader

ISA = "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *260101*1200*^*00501*000000001*0*T*:~"
SUBSCRIBER = ["HL*3*2*22*0", "NM1*IL*1*DOE*JANE****MI*MEMBER001"]
PAYER = "NM1*PR*2*EXAMPLE PAYER*****PI*99999"
RECEIVER = "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893"


def build_271(loop: str, segment: str) -> str:
    """Builds a 271 with `segment` placed in the named loop."""
    in_2000a = [segment] if loop == "2000A" else []
    in_2100a = [segment] if loop == "2100A" else []
    in_2100b = [segment] if loop == "2100B" else []
    sub: list[str] = []
    if loop == "2100C":
        sub = [segment]
    elif loop == "2110C":
        sub = ["EB*1**30", segment]
    elif loop == "2110C-EB":
        sub = [segment]
    st = (
        ["ST*271*0001*005010X279A1", "BHT*0022*11*10001*20260101*1200", "HL*1**20*1"]
        + in_2000a
        + [PAYER]
        + in_2100a
        + ["HL*2*1*21*1", RECEIVER]
        + in_2100b
        + SUBSCRIBER
        + sub
    )
    st.append(f"SE*{len(st) + 1}*0001")
    segments = ["GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1"] + st
    segments += ["GE*1*1", "IEA*1*000000001"]
    return ISA + "".join(s + "~" for s in segments)


def st_to_se(text: str) -> list[str]:
    segments = [s for s in text.replace("\n", "").split("~") if s]
    start = next(i for i, s in enumerate(segments) if s.startswith("ST*"))
    end = next(i for i, s in enumerate(segments) if s.startswith("SE*"))
    return segments[start : end + 1]


def parse(text: str) -> list:
    with X12ModelReader(text) as reader:
        return list(reader.models())


def assert_round_trip(text: str) -> None:
    models = parse(text)
    assert len(models) == 1
    assert st_to_se(models[0].x12(use_new_lines=False)) == st_to_se(text)


AAA_LOOPS = ["2000A", "2100A", "2100B", "2100C", "2110C"]

# One value already in each loop's own enum, kept as controls.
AAA03_CONTROL = {
    "2000A": "42",
    "2100A": "80",
    "2100B": "43",
    "2100C": "15",
    "2110C": "33",
}


@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa03_value_in_loop_enum_round_trips(loop):
    assert_round_trip(build_271(loop, f"AAA*N**{AAA03_CONTROL[loop]}*C"))


@pytest.mark.parametrize("code", ["72", "73", "ZZ", "99"])
@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa03_well_formed_code_outside_loop_enum_is_accepted_and_unchanged(loop, code):
    assert_round_trip(build_271(loop, f"AAA*N**{code}*C"))


@pytest.mark.parametrize("code", ["", "7", "723"])
@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa03_malformed_length_is_rejected(loop, code):
    with pytest.raises(ValidationError):
        parse(build_271(loop, f"AAA*N**{code}*C"))


@pytest.mark.parametrize("code", ["C", "N"])
@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa04_value_in_loop_enum_round_trips(loop, code):
    assert_round_trip(build_271(loop, f"AAA*N**{AAA03_CONTROL[loop]}*{code}"))


@pytest.mark.parametrize("code", ["P", "Q", "Z", "9"])
@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa04_any_one_character_code_is_accepted_and_unchanged(loop, code):
    assert_round_trip(build_271(loop, f"AAA*N**{AAA03_CONTROL[loop]}*{code}"))


@pytest.mark.parametrize("code", ["", "CC", "P1"])
@pytest.mark.parametrize("loop", AAA_LOOPS)
def test_aaa04_malformed_length_is_rejected(loop, code):
    with pytest.raises(ValidationError):
        parse(build_271(loop, f"AAA*N**{AAA03_CONTROL[loop]}*{code}"))


@pytest.mark.parametrize("code", ["30", "AL"])
def test_eb03_value_in_enum_round_trips(code):
    assert_round_trip(build_271("2110C-EB", f"EB*1**{code}"))


@pytest.mark.parametrize("code", ["A8", "ZZ", "9", "Q"])
def test_eb03_any_one_or_two_character_code_is_accepted_and_unchanged(code):
    assert_round_trip(build_271("2110C-EB", f"EB*1**{code}"))


def test_eb03_empty_is_rejected():
    with pytest.raises(ValidationError):
        parse(build_271("2110C-EB", "EB*1**"))


@pytest.mark.parametrize("code", ["A8Z", "300"])
def test_eb03_longer_than_two_characters_is_accepted_and_unchanged(code):
    assert_round_trip(build_271("2110C-EB", f"EB*1**{code}"))


# EB03 repetitions use the repetition separator declared in ISA11 (`^` here).
@pytest.mark.parametrize("value", ["30^A8", "30^A8^ZZ", "ZZ^30", "A8^30"])
def test_eb03_repeated_codes_are_accepted_and_unchanged(value):
    text = build_271("2110C-EB", f"EB*1**{value}")
    models = parse(text)
    assert len(models) == 1
    eb = (
        models[0]
        .loop_2000a[0]
        .loop_2000b[0]
        .loop_2000c[0]
        .loop_2100c.loop_2110c[0]
        .eb_segment
    )
    assert list(eb.service_type_code) == value.split("^")
    assert_round_trip(text)


@pytest.mark.parametrize("value", ["30^", "^30", "30^^A8"])
def test_eb03_repetition_with_an_empty_member_is_accepted_and_unchanged(value):
    assert_round_trip(build_271("2110C-EB", f"EB*1**{value}"))


# Dependent as patient: 2000D / 2100D (name loop) / 2110D (benefit loop).
DEPENDENT = [
    "HL*3*2*22*1",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
    "HL*4*3*23*0",
    "NM1*03*1*DOE*JOHN",
]


def build_271_dependent(*segments: str) -> str:
    """A 271 whose dependent loop 2100D carries `segments` after the dependent's NM1."""
    st = [
        "ST*271*0001*005010X279A1",
        "BHT*0022*11*10001*20260101*1200",
        "HL*1**20*1",
        PAYER,
        "HL*2*1*21*1",
        RECEIVER,
        *DEPENDENT,
        *segments,
    ]
    st.append(f"SE*{len(st) + 1}*0001")
    envelope = [
        "GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1",
        *st,
        "GE*1*1",
        "IEA*1*000000001",
    ]
    return ISA + "".join(s + "~" for s in envelope)


@pytest.mark.parametrize("code", ["15", "33", "72", "73", "ZZ"])
def test_dependent_2100d_aaa03_code_is_accepted_and_unchanged(code):
    assert_round_trip(build_271_dependent(f"AAA*N**{code}*C"))


@pytest.mark.parametrize("code", ["", "7", "723"])
def test_dependent_2100d_aaa03_malformed_length_is_rejected(code):
    with pytest.raises(ValidationError):
        parse(build_271_dependent(f"AAA*N**{code}*C"))


@pytest.mark.parametrize("code", ["30", "A8", "ZZ", "Q"])
def test_dependent_2110d_eb03_code_is_accepted_and_unchanged(code):
    assert_round_trip(build_271_dependent(f"EB*1**{code}"))


def test_dependent_2110d_eb03_empty_is_rejected():
    with pytest.raises(ValidationError):
        parse(build_271_dependent("EB*1**"))


@pytest.mark.parametrize("code", ["A8Z"])
def test_dependent_2110d_eb03_longer_than_two_characters_is_accepted_and_unchanged(
    code,
):
    assert_round_trip(build_271_dependent(f"EB*1**{code}"))


@pytest.mark.parametrize("code", ["33", "72", "73", "ZZ"])
def test_dependent_2110d_aaa03_code_is_accepted_and_unchanged(code):
    assert_round_trip(build_271_dependent("EB*1**30", f"AAA*N**{code}*C"))


@pytest.mark.parametrize("code", ["C", "P", "Q"])
def test_dependent_2110d_aaa04_code_is_accepted_and_unchanged(code):
    assert_round_trip(build_271_dependent("EB*1**30", f"AAA*N**33*{code}"))


@pytest.mark.parametrize("code", ["", "7", "723"])
def test_dependent_2110d_aaa03_malformed_length_is_rejected(code):
    with pytest.raises(ValidationError):
        parse(build_271_dependent("EB*1**30", f"AAA*N**{code}*C"))
