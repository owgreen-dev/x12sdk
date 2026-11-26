"""
271 005010X279A1: EB03 (service type code) and the AAA03 / AAA04 code fields
after the code-field loosening.

EB03 is a repeating element: up to 99 repetitions, each one to two
characters, separated by the repetition separator (^ in the samples). A code
missing from the library's own list is accepted when it is one or two
characters, so the cases here use list members and non-members alike. AAA03
is two characters and AAA04 one.

Cases whose correct outcome is a design decision are named
`..._decision_pending` and state the recommended behaviour in the docstring.
The tests behind that name record what the library does today and what is
recommended; they are the ones to revisit when the decision is made.
Every input is built inline from invented values.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader
from x12sdk.v5010.code_tables import ServiceTypeCode

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
GS = "GS*HB*SENDERID*RECEIVERID*20260101*1200*1*X*005010X279A1~"
HEAD = [
    "ST*271*0001*005010X279A1",
    "BHT*0022*11*10001234*20260101*1200",
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
    text = ISA + GS + "~".join(segs) + "~GE*1*1~IEA*1*000000001~"
    return text, segs


def parse(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())


def eb03_of(model) -> list:
    sub = model.loop_2000a[0].loop_2000b[0].loop_2000c[0]
    return sub.loop_2100c.loop_2110c[0].eb_segment.service_type_code


def round_trips(detail: list):
    text, segs = build(detail)
    models = parse(text)
    assert len(models) == 1
    out = models[0].x12(use_new_lines=False).replace("\n", "")
    start = out.index("ST*")
    end = out.index("~", out.index("SE*", start)) + 1
    assert out[start:end].rstrip("~").split("~") == segs
    return models[0]


def plain(values) -> list:
    """Enum members compare equal to their string value; normalise for lists."""
    return [getattr(v, "value", v) for v in values]


def error_types(text: str) -> set:
    with pytest.raises(ValidationError) as caught:
        parse(text)
    return {d["type"] for d in caught.value.errors()}


# EB03: values and repetition counts that are unambiguous


@pytest.mark.parametrize("code", ["1", "9", "30", "A8", "UC", "ZZ", "Q", "9Z"])
def test_eb03_one_or_two_character_code(code):
    """A code in the library's list, or any other of one or two characters."""
    model = round_trips([f"EB*1**{code}"])
    assert plain(eb03_of(model)) == [code]


def test_eb03_two_codes():
    model = round_trips(["EB*1**30^33"])
    assert plain(eb03_of(model)) == ["30", "33"]


@pytest.mark.parametrize("count", [36, 99])
def test_eb03_long_repetition_list(count):
    codes = [f"{i:02d}" for i in range(1, count + 1)]
    model = round_trips([f"EB*1**{'^'.join(codes)}"])
    assert plain(eb03_of(model)) == codes


def test_eb03_long_repetition_list_with_codes_outside_the_library_list():
    codes = ["ZZ", "Q", "9Z", "30", "A8"] * 8  # 40 repetitions
    model = round_trips([f"EB*1**{'^'.join(codes)}"])
    assert plain(eb03_of(model)) == codes


def test_eb03_long_list_followed_by_a_later_element():
    """The element after EB03 keeps its position when EB03 repeats."""
    codes = [f"{i:02d}" for i in range(1, 37)]
    text, _ = build([f"EB*1**{'^'.join(codes)}*MC"])
    sub = parse(text)[0].loop_2000a[0].loop_2000b[0].loop_2000c[0]
    eb = sub.loop_2100c.loop_2110c[0].eb_segment
    assert len(eb.service_type_code) == 36
    assert plain([eb.insurance_type_code]) == ["MC"]


# EB03: the two design decisions


@pytest.mark.parametrize("value", ["UCMB", "ZZZ", "A8B"])
def test_eb03_longer_than_two_characters_is_accepted(value):
    """
    Operator decision: any non-empty string is accepted as a service type
    code. A value such as UCMB is kept as written and serializes back byte for
    byte (value types are tested separately below).
    """
    model = round_trips([f"EB*1**{value}"])
    assert plain(eb03_of(model)) == [value]


def test_eb03_longer_than_two_characters_inside_a_repetition_list():
    model = round_trips(["EB*1**30^UCMB^ZZ^ABCDEF^33"])
    assert plain(eb03_of(model)) == ["30", "UCMB", "ZZ", "ABCDEF", "33"]


@pytest.mark.parametrize(
    "value",
    ["30^", "2^^30", "^30", "30^^33", "UCMB^^30"],
    ids=["end", "middle", "start", "middle_two", "middle_long"],
)
def test_eb03_empty_repetition_keeps_the_file_intact(value):
    """
    Operator decision: an empty repetition does not fail the transaction.
    Chosen behaviour: the empty repetition is kept as an empty member so the
    file serializes back byte for byte (round_trips compares every segment
    of the transaction); the non-empty repetitions stay in order.
    """
    model = round_trips([f"EB*1**{value}"])
    kept = [v for v in plain(eb03_of(model)) if v]
    assert kept == [v for v in value.split("^") if v]


def test_eb03_entirely_empty_is_still_rejected():
    """Unchanged: an EB03 that is empty throughout is not a service type code."""
    text, _ = build(["EB*1**^"])
    with pytest.raises(ValidationError):
        parse(text)


# AAA03 and AAA04 after the same change


@pytest.mark.parametrize("reason", ["42", "72", "ZZ", "9Q"])
def test_aaa03_two_characters_any_value(reason):
    text, _ = build([f"AAA*N**{reason}*Y"])
    assert len(parse(text)) == 1


@pytest.mark.parametrize("reason", ["4", "421"])
def test_aaa03_wrong_length_is_a_validation_error(reason):
    text, _ = build([f"AAA*N**{reason}*Y"])
    assert error_types(text) & {"string_too_short", "string_too_long"}


@pytest.mark.parametrize("action", ["C", "Y", "Q"])
def test_aaa04_one_character_any_value(action):
    text, _ = build([f"AAA*N**42*{action}"])
    assert len(parse(text)) == 1


def test_aaa04_two_characters_is_a_validation_error():
    text, _ = build(["AAA*N**42*YY"])
    assert "string_too_long" in error_types(text)


@pytest.mark.parametrize("aaa", ["AAA*N***Y", "AAA*N**42", "AAA*N**42*"])
def test_aaa03_and_aaa04_empty_or_absent_decision_pending(aaa):
    """
    DECISION PENDING. AAA03 and AAA04 are declared required in the shared
    AAA segment, so an empty or absent one is rejected with a ValidationError
    today. Whether the structure makes either conditional is not established
    by anything checked here. Recommended: keep rejecting until the structure
    listing for loop 2100C shows the element as conditional.
    """
    text, _ = build([aaa])
    with pytest.raises(ValidationError):
        parse(text)


# EB03 value types: every value, known or not, comes back as plain text


def eb03_raw(detail: str) -> list:
    text, _ = build([detail])
    return list(eb03_of(parse(text)[0]))


@pytest.mark.parametrize("code", ["1", "30", "A8", "UC"])
def test_eb03_known_code_is_a_plain_str(code):
    """X12Segment uses enum values, so a known code comes back as its text."""
    (value,) = eb03_raw(f"EB*1**{code}")
    assert type(value) is str and value == code


def test_eb03_known_codes_in_a_repetition_are_plain_str():
    values = eb03_raw("EB*1**30^A8^ZZZ")
    assert [type(v) for v in values] == [str, str, str]
    assert values == ["30", "A8", "ZZZ"]


def test_eb03_known_code_equals_the_shared_enum_value():
    (value,) = eb03_raw("EB*1**30")
    assert ServiceTypeCode("30").value == "30"
    assert value == ServiceTypeCode("30").value


@pytest.mark.parametrize("code", ["ZZ", "Q", "UCMB"])
def test_eb03_unknown_value_stays_a_plain_str(code):
    (value,) = eb03_raw(f"EB*1**{code}")
    assert type(value) is str and value == code


def test_eb03_empty_member_stays_an_empty_str():
    first, second, third = eb03_raw("EB*1**30^^A8")
    assert second == "" and type(second) is str
    assert first == "30" and third == "A8"


@pytest.mark.parametrize("code", ["30", "A8", "ZZ", "UCMB"])
def test_service_type_codes_helper_returns_plain_code_text(code):
    """
    The access helper that lists a member's service type codes returns the
    code text itself ("30"), whether the code is a known one or not.
    """
    text, _ = build([f"EB*1**{code}"])
    member = next(iter(parse(text)[0].members()))
    assert member.service_type_codes == (code,)
