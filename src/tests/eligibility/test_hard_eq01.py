"""
270 005010X279A1: EQ01 (service type code), a repeating element like the 271
EB03. Same rule as EB03: a known code or any other one or two character
string is accepted, a repetition longer than two characters fails the segment,
known codes come back as their text, repetitions and an empty repetition do not
fail the transaction, and the file serializes back byte for byte.

The 271 file also defines a Loop2110EqSegment with an enum-only
service_type_code, but no 271 loop imports or uses it, so no 271 input can
reach it and it has no test here. Inputs are built inline from invented values.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader
from x12sdk.v5010.x12_270_005010X279A1.segments import Loop2110EqSegment

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
GS = "GS*HS*SENDERID*RECEIVERID*20260101*1200*1*X*005010X279A1~"
HEAD = [
    "ST*270*0001*005010X279A1",
    "BHT*0022*13*10001234*20260101*1200",
    "HL*1**20*1",
    "NM1*PR*2*EXAMPLE PAYER*****PI*99999",
    "HL*2*1*21*1",
    "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893",
    "HL*3*2*22*0",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
]


def build(detail: list) -> tuple:
    segs = HEAD + detail
    segs.append(f"SE*{len(segs) + 1}*0001")
    return ISA + GS + "~".join(segs) + "~GE*1*1~IEA*1*000000001~", segs


def parse(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())


def round_trips(detail: list):
    text, segs = build(detail)
    models = parse(text)
    assert len(models) == 1
    out = models[0].x12(use_new_lines=False).replace("\n", "")
    start = out.index("ST*")
    end = out.index("~", out.index("SE*", start)) + 1
    assert out[start:end].rstrip("~").split("~") == segs
    return models[0]


def eq01_of(model) -> list:
    sub = model.loop_2000a[0].loop_2000b[0].loop_2000c[0]
    eq = sub.loop_2100c.loop_2110c[0].eq_segment
    return [getattr(v, "value", v) for v in eq.service_type_code]


@pytest.mark.parametrize("code", ["1", "30", "A8", "UC"])
def test_eq01_known_codes_control(code):
    assert eq01_of(round_trips([f"EQ*{code}"])) == [code]


def test_eq01_two_known_codes_control():
    assert eq01_of(round_trips(["EQ*30^33"])) == ["30", "33"]


@pytest.mark.parametrize("code", ["ZZ", "Q", "9Z"])
def test_eq01_one_or_two_character_code_outside_the_library_list(code):
    assert eq01_of(round_trips([f"EQ*{code}"])) == [code]


def test_eq01_repetition_with_a_code_outside_the_library_list():
    assert eq01_of(round_trips(["EQ*30^ZZ"])) == ["30", "ZZ"]


@pytest.mark.parametrize("value", ["1", "9", "ZZ", "Q", "9Z", "30", "A8"])
def test_eq01_boundary_one_and_two_characters_are_accepted(value):
    """Positive control for the length rule: the same shape with 1 or 2 characters."""
    assert eq01_of(round_trips([f"EQ*{value}"])) == [value]


@pytest.mark.parametrize(
    "value", ["UCMB", "ZZZ", "A8B", "ABC", "1234", "30X", "300", "ABCDEF"]
)
def test_eq01_longer_than_two_characters_is_rejected(value):
    text, _ = build([f"EQ*{value}"])
    with pytest.raises(ValidationError):
        parse(text)


@pytest.mark.parametrize("value", ["30X", "A8Z", "ZZZ"])
def test_eq01_known_code_with_a_suffix_is_rejected(value):
    text, _ = build([f"EQ*{value}"])
    with pytest.raises(ValidationError):
        parse(text)


def test_eq01_two_character_control_for_the_suffix_case_is_accepted():
    for value in ["30", "A8", "ZZ"]:
        text, _ = build([f"EQ*{value}"])
        assert len(parse(text)) == 1


@pytest.mark.parametrize(
    "value",
    ["ABC^30^33", "30^ABC^33", "30^33^ABC"],
    ids=["first", "middle", "last"],
)
def test_eq01_longer_value_in_any_repetition_fails_the_segment(value):
    text, _ = build([f"EQ*{value}"])
    with pytest.raises(ValidationError):
        parse(text)


@pytest.mark.parametrize(
    "value",
    ["ZZ^30^33", "30^ZZ^33", "30^33^ZZ"],
    ids=["first", "middle", "last"],
)
def test_eq01_two_character_value_in_any_repetition_is_accepted(value):
    """Positive control for the position tests: the same lists with 2 characters."""
    assert eq01_of(round_trips([f"EQ*{value}"])) == value.split("^")


def test_eq01_long_value_among_empty_repetitions_is_rejected():
    text, _ = build(["EQ*30^^UCMB"])
    with pytest.raises(ValidationError):
        parse(text)


def test_eq01_rejection_is_a_pydantic_validation_error_naming_the_field():
    text, _ = build(["EQ*30^UCMB^33"])
    with pytest.raises(ValidationError) as caught:
        parse(text)
    assert isinstance(caught.value, ValidationError)
    locs = [d["loc"] for d in caught.value.errors()]
    assert any(loc[-2:] == ("eq_segment", "service_type_code") for loc in locs)


def test_eq01_two_character_control_for_the_field_naming_test():
    assert eq01_of(round_trips(["EQ*30^UC^33"])) == ["30", "UC", "33"]


@pytest.mark.parametrize("count", [36, 99])
def test_eq01_long_repetition_list(count):
    codes = [f"{i:02d}" for i in range(1, count + 1)]
    assert eq01_of(round_trips([f"EQ*{'^'.join(codes)}"])) == codes


@pytest.mark.parametrize(
    "value", ["30^", "2^^30", "^30"], ids=["end", "middle", "start"]
)
def test_eq01_empty_repetition_keeps_the_file_intact(value):
    """Same chosen behaviour as EB03: kept as an empty member, exact round trip."""
    kept = [v for v in eq01_of(round_trips([f"EQ*{value}"])) if v]
    assert kept == [v for v in value.split("^") if v]


def test_eq01_absent_without_a_procedure_is_still_rejected():
    """Unchanged control: EQ needs a service type code or a procedure id."""
    text, _ = build(["EQ"])
    with pytest.raises(ValidationError):
        parse(text)


# EQ01 value types: every value, known or not, comes back as plain text


def eq01_raw(detail: str) -> list:
    text, _ = build([detail])
    sub = parse(text)[0].loop_2000a[0].loop_2000b[0].loop_2000c[0]
    return list(sub.loop_2100c.loop_2110c[0].eq_segment.service_type_code)


@pytest.mark.parametrize("code", ["1", "30", "A8", "UC"])
def test_eq01_known_code_is_a_plain_str(code):
    """X12Segment uses enum values, so a known code comes back as its text."""
    (value,) = eq01_raw(f"EQ*{code}")
    assert type(value) is str and value == code


def test_eq01_known_codes_in_a_repetition_are_plain_str():
    values = eq01_raw("EQ*30^A8^ZZ")
    assert [type(v) for v in values] == [str, str, str]
    assert values == ["30", "A8", "ZZ"]


def test_eq01_known_code_equals_the_enum_value():
    (value,) = eq01_raw("EQ*30")
    assert Loop2110EqSegment.ServiceTypeCode("30").value == "30"
    assert value == Loop2110EqSegment.ServiceTypeCode("30").value


@pytest.mark.parametrize("code", ["ZZ", "Q", "9Z"])
def test_eq01_unknown_value_stays_a_plain_str(code):
    (value,) = eq01_raw(f"EQ*{code}")
    assert type(value) is str and value == code


def test_eq01_empty_member_stays_an_empty_str():
    first, second, third = eq01_raw("EQ*30^^A8")
    assert second == "" and type(second) is str
    assert first == "30" and third == "A8"


@pytest.mark.parametrize("code", ["30", "A8", "ZZ", "Q"])
def test_service_type_codes_helper_returns_plain_code_text_for_an_inquiry(code):
    text, _ = build([f"EQ*{code}"])
    member = next(iter(parse(text)[0].members()))
    assert member.service_type_codes == (code,)
