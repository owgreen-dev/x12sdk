"""
hard_b_support.py

Helpers for the tests that check a segment is neither dropped nor mis-routed while parsing.

The rule these tests state: every segment of a valid transaction set must be held by the model, so that
serializing the model gives back the same segments in the same order. A segment that is lost shows up only through
the SE01 count, so the helpers compare whole segment lists rather than looking for one value.
"""

from typing import List, Tuple

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)


def interchange(
    group_code: str, version: str, header: List[str], body: List[str]
) -> Tuple[str, List[str]]:
    """
    Wraps a transaction set in an interchange and a functional group.

    :param group_code: GS01 value
    :param version: GS08 value
    :param header: The segments from ST up to, but not including, the first body segment
    :param body: The remaining segments, without SE
    :return: The interchange text and the ST to SE segment list (SE01 counts the segments correctly)
    """
    segments = header + body
    segments.append(f"SE*{len(segments) + 1}*{header[0].split('*')[2]}")
    text = (
        ISA
        + f"GS*{group_code}*SENDERID*RECEIVERID*20260101*1200*1*X*{version}~"
        + "~".join(segments)
        + "~GE*1*1~IEA*1*000000001~"
    )
    return text, segments


def serialized_segments(text: str, first_segment: str, count: int) -> List[str]:
    """Parses one transaction set and returns the `count` segments it serializes to, starting at ST."""
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    written = [s for s in models[0].x12(use_new_lines=False).split("~") if s]
    start = written.index(first_segment)
    return written[start : start + count]


def assert_round_trip(text: str, segments: List[str]) -> None:
    """Asserts that the input parses and serializes back to exactly the same ST to SE segments."""
    assert serialized_segments(text, segments[0], len(segments)) == segments


def parse_one(text: str):
    """Parses text holding one transaction set and returns its model."""
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    return models[0]
