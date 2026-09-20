"""
test_access_eligibility_status.py

Accessors for the 270/271 and 276/277 pairs, which carry the same
subscriber/dependent branch as the 837.

The oracle is reachability, checked against the raw text of every sample in
the corpus: every EQ or EB segment in an eligibility file must be reachable
through ``members()``, and every claim-status TRN inside a patient level must
be reachable through ``claims()``. A traversal that skipped a branch fails
there rather than quietly under-reporting in someone's pipeline.
"""

import pathlib

import pytest

from x12sdk.access import EligibilityMember, TrackedClaim
from x12sdk.generate import generate_270, generate_271, generate_276, generate_277
from x12sdk.io import X12ModelReader

RESOURCES = pathlib.Path(__file__).parent / "resources"
ELIGIBILITY = (("270_005010X279A1", "EQ"), ("271_005010X279A1", "EB"))
CLAIM_STATUS = ("276_005010X212", "277_005010X212")


def _samples(directory):
    return sorted((RESOURCES / directory).glob("*"))


def _read(path):
    with X12ModelReader(str(path)) as reader:
        return list(reader.models())


def _raw(path):
    text = pathlib.Path(path).read_text().replace("\n", "")
    return [s.split("*") for s in text.split("~") if s]


def _count(path, name):
    return sum(1 for s in _raw(path) if s[0] == name)


def _count_patient_level_trn(path):
    """
    TRN segments that sit inside a subscriber or dependent level.

    A 277 may also carry TRN at the information receiver and service provider
    levels, which are not tracked claims, so counting TRN alone would not do.
    """
    total = 0
    level = None
    for segment in _raw(path):
        if segment[0] == "HL":
            level = segment[3]
        elif segment[0] == "TRN" and level in ("22", "23"):
            total += 1
    return total


def _from_text(text, tmp_path, name):
    path = tmp_path / name
    path.write_text(text)
    return _read(path)[0]


# --- the oracle: nothing is missed ----------------------------------------


@pytest.mark.parametrize("directory,segment_name", ELIGIBILITY)
def test_members_reaches_every_benefit_in_the_corpus(directory, segment_name):
    """
    Every EQ on a 270 and every EB on a 271 must be reachable. This is what a
    traversal that handled only one branch would fail.
    """
    for path in _samples(directory):
        expected = _count(path, segment_name)
        found = sum(
            len(member.benefits) for model in _read(path) for member in model.members()
        )
        assert found == expected, f"{path.name}: {found} reached of {expected}"


@pytest.mark.parametrize("directory", CLAIM_STATUS)
def test_claims_reaches_every_tracked_claim_in_the_corpus(directory):
    """Every TRN inside a patient level must be reachable through claims()."""
    for path in _samples(directory):
        expected = _count_patient_level_trn(path)
        found = sum(len(list(model.claims())) for model in _read(path))
        assert found == expected, f"{path.name}: {found} reached of {expected}"


@pytest.mark.parametrize("directory,segment_name", ELIGIBILITY)
def test_every_dependent_in_the_corpus_is_reported(directory, segment_name):
    """One member per HL at level 23, counted from the raw file."""
    for path in _samples(directory):
        expected = sum(1 for s in _raw(path) if s[0] == "HL" and s[3] == "23")
        found = sum(
            1
            for model in _read(path)
            for member in model.members()
            if member.is_dependent
        )
        assert found == expected, f"{path.name}"


# --- both branches ---------------------------------------------------------


@pytest.mark.parametrize(
    "generate,kind,suffix",
    (
        (generate_270, "members", ".270"),
        (generate_271, "members", ".271"),
    ),
)
def test_eligibility_finds_both_branches(generate, kind, suffix, tmp_path):
    for rate, dependent in ((0.0, False), (1.0, True)):
        model = _from_text(
            generate(seed=1, members=4, dependent_rate=rate), tmp_path, f"g{suffix}"
        )
        members = list(model.members())
        assert len(members) == 4
        assert all(m.is_dependent is dependent for m in members)


@pytest.mark.parametrize(
    "generate,suffix", ((generate_276, ".276"), (generate_277, ".277"))
)
def test_claim_status_finds_both_branches(generate, suffix, tmp_path):
    for rate, dependent in ((0.0, False), (1.0, True)):
        model = _from_text(
            generate(seed=1, patients=4, dependent_rate=rate), tmp_path, f"g{suffix}"
        )
        claims = list(model.claims())
        assert len(claims) == 4
        assert all(c.is_dependent is dependent for c in claims)


def test_a_subscriber_with_benefits_and_a_dependent_yields_both():
    """
    The subscriber is a member in their own right whenever the transaction
    says something about them. Yielding only the dependents in that case
    would drop the subscriber's own coverage, which is the bug this pins.
    """
    from x12sdk.access import EligibilityAccess
    from x12sdk.v5010.segments import EbSegment
    from x12sdk.v5010.x12_271_005010X279A1 import loops as L
    from x12sdk.v5010.x12_271_005010X279A1 import segments as S

    def eb(code):
        return EbSegment(eligibility_benefit_information="1", service_type_code=[code])

    subscriber = L.Loop2100C(
        nm1_segment=S.Loop2100CNm1Segment(
            entity_identifier_code="IL",
            entity_type_qualifier="1",
            name_last_or_organization_name="DOE",
            name_first="JOHN",
            identification_code_qualifier="MI",
            identification_code="W123456789",
        ),
        loop_2110c=[L.Loop2110C(eb_segment=eb("30"))],
    )
    dependent = L.Loop2000D(
        hl_segment=S.Loop2000DHlSegment(
            hierarchical_id_number="4",
            hierarchical_parent_id_number="3",
            hierarchical_level_code="23",
            hierarchical_child_code="0",
        ),
        loop_2100d=L.Loop2100D(
            nm1_segment=S.Loop2100DNm1Segment(
                entity_identifier_code="03",
                entity_type_qualifier="1",
                name_last_or_organization_name="DOE",
                name_first="JANE",
            ),
            loop_2110d=[L.Loop2110D(eb_segment=eb("35"))],
        ),
    )
    loop_2000c = L.Loop2000C(
        hl_segment=S.Loop2000CHlSegment(
            hierarchical_id_number="3",
            hierarchical_parent_id_number="2",
            hierarchical_level_code="22",
            hierarchical_child_code="1",
        ),
        loop_2100c=subscriber,
        loop_2000d=[dependent],
    )
    loop_2000b = L.Loop2000B(
        hl_segment=S.Loop2000BHlSegment(
            hierarchical_id_number="2",
            hierarchical_parent_id_number="1",
            hierarchical_level_code="21",
            hierarchical_child_code="1",
        ),
        loop_2100b=L.Loop2100B(
            nm1_segment=S.Loop2100BNm1Segment(
                entity_identifier_code="1P",
                entity_type_qualifier="2",
                name_last_or_organization_name="EXAMPLE CLINIC",
                identification_code_qualifier="XX",
                identification_code="1234567893",
            )
        ),
        loop_2000c=[loop_2000c],
    )
    loop_2000a = L.Loop2000A(
        hl_segment=S.Loop2000AHlSegment(
            hierarchical_id_number="1",
            hierarchical_level_code="20",
            hierarchical_child_code="1",
        ),
        loop_2100a=L.Loop2100A(
            nm1_segment=S.Loop2100ANm1Segment(
                entity_identifier_code="PR",
                entity_type_qualifier="2",
                name_last_or_organization_name="EXAMPLE HEALTH PLAN",
                identification_code_qualifier="PI",
                identification_code="999888777",
            )
        ),
        loop_2000b=[loop_2000b],
    )

    class Transaction(EligibilityAccess):
        pass

    transaction = Transaction()
    transaction.loop_2000a = [loop_2000a]

    members = list(transaction.members())
    assert [m.is_dependent for m in members] == [False, True]
    reached = sorted(code for m in members for code in m.service_type_codes)
    assert reached == ["30", "35"]


# --- what a record carries -------------------------------------------------


def test_an_eligibility_member_carries_its_context(tmp_path):
    model = _from_text(
        generate_271(
            seed=9,
            members=3,
            payer_name="EXAMPLE HEALTH PLAN",
            provider_name="EXAMPLE MEDICAL GROUP",
        ),
        tmp_path,
        "ctx.271",
    )
    member = next(iter(model.members()))
    assert isinstance(member, EligibilityMember)
    assert member.payer_name == "EXAMPLE HEALTH PLAN"
    assert member.provider_name == "EXAMPLE MEDICAL GROUP"
    assert member.member_id
    assert member.service_type_codes


def test_the_member_is_the_dependent_not_the_subscriber(tmp_path):
    model = _from_text(
        generate_271(seed=2, members=1, dependent_rate=1.0), tmp_path, "who.271"
    )
    member = next(iter(model.members()))
    assert member.is_dependent
    assert member.member is not member.subscriber
    assert member.name != member.subscriber_name or member.member_id


def test_a_tracked_claim_exposes_the_charge_from_either_transaction(tmp_path):
    """
    The inquiry states the charge in AMT and the response in STC04, so a
    caller reading ``charge`` does not have to know which it is holding.
    """
    inquiry = _from_text(generate_276(seed=4, patients=2), tmp_path, "i.276")
    response = _from_text(generate_277(seed=4, patients=2), tmp_path, "r.277")

    asked = list(inquiry.claims())
    answered = list(response.claims())
    assert [c.charge for c in asked] == [c.charge for c in answered]
    assert all(c.paid is None for c in asked), "an inquiry reports no payment"
    assert all(c.paid is not None for c in answered)
    assert all(isinstance(c, TrackedClaim) for c in asked)


def test_a_tracked_claim_ties_an_inquiry_to_its_response(tmp_path):
    """TRN02 is the thread between the two transactions."""
    inquiry = _from_text(generate_276(seed=4, patients=3), tmp_path, "i.276")
    response = _from_text(generate_277(seed=4, patients=3), tmp_path, "r.277")
    assert [c.trace_number for c in inquiry.claims()] == [
        c.trace_number for c in response.claims()
    ]


def test_accessor_records_are_immutable(tmp_path):
    model = _from_text(generate_271(seed=8, members=1), tmp_path, "frozen.271")
    member = next(iter(model.members()))
    with pytest.raises(Exception):
        member.is_dependent = True


def test_the_accessors_do_not_add_model_fields():
    """
    The mixins must contribute behaviour only. A field slipping in would
    change what serializes and break the round trip on every sample.
    """
    from x12sdk.v5010.x12_270_005010X279A1.transaction_set import EligibilityInquiry
    from x12sdk.v5010.x12_277_005010X212.transaction_set import (
        HealthCareClaimsStatusResponse,
    )

    assert set(EligibilityInquiry.model_fields) == {
        "header",
        "loop_2000a",
        "footer",
    }
    assert set(HealthCareClaimsStatusResponse.model_fields) == {
        "header",
        "loop_2000a",
        "footer",
    }
