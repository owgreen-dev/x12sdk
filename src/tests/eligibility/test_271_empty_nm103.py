"""
An empty NM103 (last name or organization name) is accepted in the 271 information source (2100A),
information receiver (2100B), subscriber (2100C) and dependent (2100D) loops, and is written back
unchanged. Other transactions that share the NM1 model keep rejecting it.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader

ISA = "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *260101*1200*^*00501*000000001*0*T*:~"

PAYER = "NM1*PR*2*EXAMPLE PAYER*****PI*99999"
RECEIVER = "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893"
SUBSCRIBER = "NM1*IL*1*DOE*JANE****MI*MEMBER001"


def _wrap(
    code: str, functional_id: str, body: list[str], version: str = "005010X279A1"
) -> tuple[str, list[str]]:
    inner = [f"ST*{code}*0001*{version}"] + body
    inner.append(f"SE*{len(inner) + 1}*0001")
    segments = [
        f"GS*{functional_id}*SENDER*RECEIVER*20260101*1200*1*X*{version}"
    ] + inner
    segments += ["GE*1*1", "IEA*1*000000001"]
    return ISA + "".join(s + "~" for s in segments), inner


def _271(payer: str = PAYER, receiver: str = RECEIVER, tail: list[str] | None = None):
    body = [
        "BHT*0022*11*10001*20260101*1200",
        "HL*1**20*1",
        payer,
        "HL*2*1*21*1",
        receiver,
    ]
    body += tail if tail is not None else ["HL*3*2*22*0", SUBSCRIBER]
    return _wrap("271", "HB", body)


def _270(payer: str = PAYER, receiver: str = RECEIVER):
    body = [
        "BHT*0022*13*10001*20260101*1200",
        "HL*1**20*1",
        payer,
        "HL*2*1*21*1",
        receiver,
        "HL*3*2*22*0",
        "TRN*1*93175*9877281234",
        SUBSCRIBER,
        "DMG*D8*19430519",
        "DTP*291*D8*20260101",
        "EQ*30",
    ]
    return _wrap("270", "HS", body)


def _277(dependent: str):
    body = [
        "BHT*0010*08*277X212*20260101*1200*DG",
        "HL*1**20*1",
        PAYER,
        "HL*2*1*21*1",
        "NM1*41*2*EXAMPLE CLEARINGHOUSE*****46*SUBMITTER1",
        "HL*3*2*19*1",
        RECEIVER,
        "HL*4*3*22*0",
        dependent,
        "TRN*2*PCN000001",
        "STC*F1:1*20250214**100*100",
    ]
    return _wrap("277", "HN", body, "005010X212")


def _read(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())


def _assert_round_trip(case):
    text, expected = case
    models = _read(text)
    assert len(models) == 1
    assert models[0].x12(use_new_lines=False) == "".join(s + "~" for s in expected)


DEPENDENT_TAIL = ["HL*3*2*22*1", SUBSCRIBER, "HL*4*3*23*0"]


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_271(payer="NM1*PR*2******PI*99999"), id="2100A-empty"),
        pytest.param(_271(receiver="NM1*1P*2******XX*1234567893"), id="2100B-empty"),
        pytest.param(_271(tail=DEPENDENT_TAIL + ["NM1*03*1**JOHN"]), id="2100D-empty"),
    ],
)
def test_empty_nm103_accepted_and_round_trips(case):
    _assert_round_trip(case)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _271(tail=["HL*3*2*22*0", "NM1*IL*1**JANE****MI*MEMBER001"]),
            id="2100C-empty",
        ),
        pytest.param(_271(), id="2100A-2100B-2100C-named"),
        pytest.param(_271(payer="NM1*PR*2*ACME PAYER*****PI*99999"), id="2100A-named"),
        pytest.param(
            _271(receiver="NM1*1P*2*ACME CLINIC*****XX*1234567893"), id="2100B-named"
        ),
        pytest.param(
            _271(tail=DEPENDENT_TAIL + ["NM1*03*1*DOE*JOHN"]), id="2100D-named"
        ),
    ],
)
def test_controls_round_trip(case):
    _assert_round_trip(case)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_270(payer="NM1*PR*2******PI*99999"), id="270-2100A"),
        pytest.param(_270(receiver="NM1*1P*2******XX*1234567893"), id="270-2100B"),
        pytest.param(_277("NM1*IL*1**JANE****MI*M1"), id="277-2100D"),
    ],
)
def test_empty_nm103_still_rejected_in_other_transactions(case):
    text, _ = case
    with pytest.raises(ValidationError) as excinfo:
        _read(text)
    assert any(
        e["loc"][-1] == "name_last_or_organization_name" for e in excinfo.value.errors()
    )


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_270(), id="270-named"),
        pytest.param(_277("NM1*IL*1*DOE*JANE****MI*M1"), id="277-named"),
    ],
)
def test_other_transaction_controls_round_trip(case):
    _assert_round_trip(case)


def _loop_case(loop: str, nm103: str, nm102: str = "2", nm104: str = ""):
    if loop == "2100A":
        return _271(payer=f"NM1*PR*{nm102}*{nm103}*{nm104}****PI*99999")
    if loop == "2100B":
        return _271(receiver=f"NM1*1P*{nm102}*{nm103}*{nm104}****XX*1234567893")
    segment = f"NM1*03*{nm102}*{nm103}" + (f"*{nm104}" if nm104 else "")
    return _271(tail=DEPENDENT_TAIL + [segment])


LOOPS = ["2100A", "2100B", "2100D"]


@pytest.mark.parametrize("loop", LOOPS)
def test_nm103_of_60_characters_accepted(loop):
    _assert_round_trip(_loop_case(loop, "A" * 60))


@pytest.mark.parametrize("loop", LOOPS)
def test_nm103_of_61_characters_rejected(loop):
    text, _ = _loop_case(loop, "A" * 61)
    with pytest.raises(ValidationError) as excinfo:
        _read(text)
    assert any(
        e["loc"][-1] == "name_last_or_organization_name" for e in excinfo.value.errors()
    )


@pytest.mark.parametrize("loop", ["2100A", "2100B"])
def test_empty_nm103_person_type_with_first_name(loop):
    _assert_round_trip(_loop_case(loop, "", nm102="1", nm104="JOHN"))


def test_absent_trailing_nm103_in_2100d_round_trips():
    _assert_round_trip(_271(tail=DEPENDENT_TAIL + ["NM1*03*1"]))
