"""
HL04 handling in the 270 and 271 (005010X279A1) parsers.

A subscriber loop (HL03 = 22) with HL04 = 1 that carries its own detail segments
must not make the parser fail with a raw builtin exception, and must not have its
detail attached to another subscriber. Either the file parses with each detail
under the subscriber it was written under and round-trips, or it is refused with
a validation error or the library's parse exception. Every sample is built inline.
"""

import pytest

from tests.hl04_support import Family

_SERVICE = {"1": "30", "2": "98", "3": "1"}

_HEAD = [
    "BHT*0022*{bht}*1*20260101*1200",
    "HL*1**20*1",
    "NM1*PR*2*PAYER*****PI*12345",
    "HL*2*1*21*1",
    "NM1*1P*2*CLINIC*****SV*2000035",
]


def _subscribers(model):
    return model.loop_2000a[0].loop_2000b[0].loop_2000c


FAMILIES = {
    "270": Family(
        "270",
        "HS",
        "005010X279A1",
        [s.format(bht="13") for s in _HEAD],
        3,
        2,
        lambda h, p, c, t: [
            f"HL*{h}*{p}*22*{c}",
            f"TRN*1*T{t}*9877281234",
            f"NM1*IL*1*DOE*JANE{t}****MI*W{t}",
        ],
        lambda h, p, t: [
            f"HL*{h}*{p}*23*0",
            f"TRN*1*D{t}*9877281234",
            f"NM1*03*1*DOE*JUNIOR{t}",
        ],
        lambda t: [f"EQ*{_SERVICE[t]}"],
        lambda t: f"EQ*{_SERVICE[t]}~",
        _subscribers,
    ),
    "271": Family(
        "271",
        "HB",
        "005010X279A1",
        [s.format(bht="11") for s in _HEAD],
        3,
        2,
        lambda h, p, c, t: [
            f"HL*{h}*{p}*22*{c}",
            f"NM1*IL*1*DOE*JANE{t}****MI*W{t}",
            "DMG*D8*19800101*F",
        ],
        lambda h, p, t: [
            f"HL*{h}*{p}*23*0",
            f"NM1*03*1*DOE*JUNIOR{t}",
            "DMG*D8*20100101*M",
        ],
        lambda t: [f"EB*1**{_SERVICE[t]}"],
        lambda t: f"EB*1**{_SERVICE[t]}~",
        _subscribers,
    ),
}


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_two_subscribers_each_with_own_detail(family: Family):
    """Control: both subscribers are the patient (HL04 = 0), each with its own detail."""
    family.check_parses(family.two_leaf_subscribers(), [{"1"}, {"2"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_detail_of_a_dependent_stays_with_the_dependent(family: Family):
    """Control: a subscriber with HL04 = 1 holds only a name; the dependent holds the detail."""
    family.check_parses(family.dependent_carries_detail(), [{"2"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_first_subscriber_with_child_code_one_and_own_detail(family: Family):
    """
    No earlier subscriber set the patient record, so the detail handler finds
    nothing to attach to: it must not escape as a raw builtin exception.
    """
    family.check(family.child_one_first(), [{"1"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_child_code_one_detail_is_not_given_to_the_previous_subscriber(
    family: Family,
):
    """
    Subscriber A (HL04 = 0) has detail 1, then subscriber B (HL04 = 1) has
    detail 2. The patient record still points at A, so B's detail must not be
    attached to A (or fail with a raw exception).
    """
    family.check(family.child_one_after_leaf(), [{"1"}, {"2"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_child_code_one_with_dependent_keeps_each_detail_under_its_owner(
    family: Family,
):
    """As above, with a dependent of B carrying detail 3 so the file is complete."""
    family.check(family.child_one_after_leaf_with_dependent(), [{"1"}, {"2", "3"}])
