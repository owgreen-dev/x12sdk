"""
test_line_adjudication.py

Loop 2430 (line adjudication) repeats: a service line on a claim sent to a
secondary or tertiary payer carries one adjudication per earlier payer. The
837 parsers guarded the list initializer with ``if TransactionLoops.X:``,
which is always true, so every SVD reset the list and only the last payer's
adjudication survived. The audit's always-true-guard check now catches the
shape; these tests pin the behaviour on real files.
"""

import pathlib

import pytest

from x12sdk.generate import generate_837i
from x12sdk.io import X12ModelReader

RESOURCES = pathlib.Path(__file__).parent / "resources"

SECOND_ADJUDICATION = [
    "SVD*69999*20.00*HC:99203:25**1.00~",
    "CAS*PR*1*20.00~",
    "DTP*573*D8*20050205~",
]


def _with_extra_segments(text: str, after: str, extra) -> str:
    """Inserts segments after the line ``after`` and fixes SE01."""
    lines = text.split("\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(after))
    lines[index + 1 : index + 1] = extra
    se = next(i for i, line in enumerate(lines) if line.startswith("SE*"))
    _, count, control = lines[se].rstrip("~").split("*")
    lines[se] = f"SE*{int(count) + len(extra)}*{control}~"
    return "\n".join(lines)


def _service_lines(model):
    for provider in model.loop_2000a:
        for subscriber in provider.loop_2000b:
            for claim in subscriber.loop_2300 or []:
                yield from claim.loop_2400
            for patient in subscriber.loop_2000c or []:
                for claim in patient.loop_2300 or []:
                    yield from claim.loop_2400


def _read(text: str):
    with X12ModelReader(text) as reader:
        return list(reader.models())[0]


def test_a_professional_line_keeps_every_payers_adjudication():
    original = (RESOURCES / "837_005010X222A2" / "demo.cob.example4.837").read_text()
    text = _with_extra_segments(original, "DTP*573*D8*20050128~", SECOND_ADJUDICATION)

    line = next(line for line in _service_lines(_read(text)) if line.loop_2430)
    payers = [a.svd_segment.other_payer_primary_identifier for a in line.loop_2430]
    assert payers == ["59999", "69999"]


def test_the_professional_file_still_round_trips_with_both_adjudications():
    original = (RESOURCES / "837_005010X222A2" / "demo.cob.example4.837").read_text()
    text = _with_extra_segments(original, "DTP*573*D8*20050128~", SECOND_ADJUDICATION)
    model = _read(text)
    assert "SVD*59999" in model.x12() and "SVD*69999" in model.x12()


@pytest.mark.parametrize("payers", [1, 2, 3])
def test_an_institutional_line_keeps_every_payers_adjudication(payers):
    generated = generate_837i(seed=4, claims=1)
    # generated institutional lines carry no line date, so anchor on the SV2
    first_line = next(line for line in generated.split("\n") if line.startswith("SV2*"))
    extra = []
    for n in range(payers):
        extra += [
            f"SVD*{n + 1}1111*10.00*HC:99213**1~",
            f"DTP*573*D8*2026010{n + 1}~",
        ]
    text = _with_extra_segments(generated, first_line, extra)

    line = next(line for line in _service_lines(_read(text)) if line.loop_2430)
    assert [a.svd_segment.other_payer_primary_identifier for a in line.loop_2430] == [
        f"{n + 1}1111" for n in range(payers)
    ]
