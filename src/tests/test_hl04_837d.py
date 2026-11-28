"""
HL04 handling in the 837D (005010X224A2) parser.

A subscriber loop (HL03 = 22) with HL04 = 1 that carries its own detail segments
must not make the parser fail with a raw builtin exception, and must not have its
detail attached to another subscriber. Either the file parses with each detail
under the subscriber it was written under and round-trips, or it is refused with
a validation error or the library's parse exception. Every sample is built inline.
"""

import pytest

from tests.hl04_support import Family

_HEAD = [
    "BHT*0019*00*1*20260101*1200*CH",
    "NM1*41*2*BILLER*****46*TGJ23",
    "PER*IC*JANE DOE*TE*9005555555",
    "NM1*40*2*PAYER*****46*66783",
    "HL*1**20*1",
    "PRV*BI*PXC*203BF0100Y",
    "NM1*85*2*CLINIC*****XX*1234567893",
    "N3*1 MAIN ST",
    "N4*MIAMI*FL*33111",
    "REF*EI*587654321",
]


def _subscriber(h, p, c, t):
    return [
        f"HL*{h}*{p}*22*{c}",
        "SBR*P**GRP1******CI",
        f"NM1*IL*1*DOE*JANE{t}****MI*W{t}",
        "NM1*PR*2*PAYER*****PI*99999",
    ]


def _dependent(h, p, t):
    return [
        f"HL*{h}*{p}*23*0",
        "PAT*19",
        f"NM1*QC*1*DOE*JUNIOR{t}",
        "N3*2 ELM ST",
        "N4*MIAMI*FL*33111",
        "DMG*D8*20100101*M",
    ]


def _subscribers(model):
    return model.loop_2000a[0].loop_2000b


FAMILIES = {
    "837D": Family(
        "837",
        "HC",
        "005010X224A2",
        _HEAD,
        2,
        1,
        _subscriber,
        _dependent,
        lambda t: [
            f"CLM*C{t}*100.00***11:B:1*Y*A*Y*Y",
            "LX*1",
            "SV3*AD:D2391*100.00****1",
            "DTP*472*D8*20260101",
        ],
        lambda t: f"CLM*C{t}*",
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
    family.check_parses(family.child_one_first(), [{"1"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_child_code_one_detail_is_not_given_to_the_previous_subscriber(
    family: Family,
):
    """
    Subscriber A (HL04 = 0) has detail 1, then subscriber B (HL04 = 1) has
    detail 2. The patient record still points at A, so B's detail must not be
    attached to A (or fail with a raw exception).
    """
    family.check_parses(family.child_one_after_leaf(), [{"1"}, {"2"}])


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_child_code_one_with_dependent_keeps_each_detail_under_its_owner(
    family: Family,
):
    """As above, with a dependent of B carrying detail 3 so the file is complete."""
    family.check_parses(
        family.child_one_after_leaf_with_dependent(), [{"1"}, {"2", "3"}]
    )


@pytest.mark.parametrize("family", FAMILIES.values(), ids=FAMILIES.keys())
def test_two_child_code_one_subscribers_each_keep_their_own_claim(family: Family):
    """Both subscribers have HL04 = 1 and no dependent follows either."""
    family.check_parses(family.two_child_one_subscribers(), [{"1"}, {"2"}])
