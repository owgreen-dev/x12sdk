"""
A 271 subscriber loop that says it has a child (HL04 = 1) but carries its own
benefit (EB) segments.

The structure rules allow a benefit on a subscriber loop, and they define HL04
as a flag saying whether a lower-level loop follows. Whether a file whose HL04
disagrees with what follows should be read or refused is a separate decision;
what is required here is that the library never answers with a raw
TypeError. It either reads the file or refuses it with a validation error or
the library's own parse exception.

The samples are invented and built inline.
"""

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader
from x12sdk.parsing import X12ParseException

ISA = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
HEAD = [
    "BHT*0022*11*10001*20260101*1200",
    "HL*1**20*1",
    "NM1*PR*2*EXAMPLE PAYER*****PI*12345",
    "HL*2*1*21*1",
    "NM1*1P*2*EXAMPLE CLINIC*****XX*1234567893",
]
SUBSCRIBER = [
    "NM1*IL*1*DOE*JANE****MI*W000000001",
    "EB*1**30",
]
DEPENDENT = [
    "HL*4*3*23*0",
    "NM1*03*1*DOE*JUNIOR",
    "EB*1**30",
]


def _text(hl03_child: str, with_eb: bool, with_dependent: bool) -> str:
    sub = ["HL*3*2*22*" + hl03_child] + [
        s for s in SUBSCRIBER if with_eb or not s.startswith("EB")
    ]
    body = ["ST*271*0001*005010X279A1"] + HEAD + sub
    if with_dependent:
        body += DEPENDENT
    body.append(f"SE*{len(body) + 1}*0001")
    gs = "GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1"
    return ISA + gs + "~" + "".join(s + "~" for s in body) + "GE*1*1~IEA*1*000000001~"


def _read(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())


def test_control_subscriber_that_is_the_patient_reads():
    """Positive control: HL04 = 0 with an EB reads and writes back."""
    models = _read(_text("0", with_eb=True, with_dependent=False))
    assert len(models) == 1
    models[0].x12()


def test_control_subscriber_with_child_and_dependent_reads():
    """Positive control: HL04 = 1 with the dependent loop that it announces reads."""
    models = _read(_text("1", with_eb=False, with_dependent=True))
    assert len(models) == 1
    models[0].x12()


@pytest.mark.parametrize(
    "with_dependent", [False, True], ids=["no-dependent", "dependent"]
)
def test_subscriber_hl04_1_with_benefit_is_not_a_raw_error(with_dependent):
    """HL04 = 1 plus EB segments on the subscriber: a model or a clean error, never TypeError."""
    try:
        models = _read(_text("1", with_eb=True, with_dependent=with_dependent))
        for model in models:
            model.x12()
    except (ValidationError, X12ParseException):
        return
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"raw {type(exc).__name__}: {exc}")
