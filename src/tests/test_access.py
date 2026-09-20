"""
test_access.py

The accessors exist to stop code losing claims down the branch it forgot, so
the test that matters is a count against the file itself: sweep every sample
in the corpus, count the CLM (or CLP) segments in the raw text, and require
``claims()`` to yield exactly that many. A traversal that skips the dependent
branch, or any loop 2000A after the first, fails here rather than silently
under-reporting in someone's pipeline.
"""

import pathlib
from decimal import Decimal

import pytest

from x12sdk.access import PaidClaim, SubmittedClaim
from x12sdk.generate import generate_835, generate_837p
from x12sdk.io import X12ModelReader

RESOURCES = pathlib.Path(__file__).parent / "resources"
CLAIM_SETS = ("837_005010X222A2", "837_005010X223A3")


def _samples(*directories):
    return [
        path
        for directory in directories
        for path in sorted((RESOURCES / directory).glob("*"))
    ]


def _read(path):
    with X12ModelReader(str(path)) as reader:
        return list(reader.models())


def _count(path, segment_name):
    """Occurrences of a segment in the raw file, counted without the models."""
    text = pathlib.Path(path).read_text()
    return sum(
        1
        for segment in text.replace("\n", "").split("~")
        if segment.split("*")[0] == segment_name
    )


def _from_text(text, tmp_path, name):
    path = tmp_path / name
    path.write_text(text)
    return _read(path)[0]


# --- the oracle: nothing is missed ----------------------------------------


@pytest.mark.parametrize("path", _samples(*CLAIM_SETS), ids=lambda p: p.name)
def test_claims_finds_every_submitted_claim(path):
    """``claims()`` must yield exactly the CLM segments present in the file."""
    expected = _count(path, "CLM")
    found = sum(len(list(model.claims())) for model in _read(path))
    assert found == expected


@pytest.mark.parametrize("path", _samples("835_005010X221A1"), ids=lambda p: p.name)
def test_claims_finds_every_paid_claim(path):
    """``claims()`` must yield exactly the CLP segments present in the file."""
    expected = _count(path, "CLP")
    found = sum(len(list(model.claims())) for model in _read(path))
    assert found == expected


def _count_hl(path, level_code):
    """HL segments at one hierarchical level, counted from the raw file."""
    text = pathlib.Path(path).read_text()
    return sum(
        1
        for segment in text.replace("\n", "").split("~")
        if segment.startswith("HL*") and segment.split("*")[3] == level_code
    )


@pytest.mark.parametrize("path", _samples(*CLAIM_SETS), ids=lambda p: p.name)
def test_subscribers_finds_every_subscriber(path):
    """
    One subscriber per HL at level 22, counted from the file rather than from
    the models, so the traversal is checked against something independent.
    SBR would not do: it appears again in loop 2320 for the other payers on a
    coordination of benefits claim.
    """
    expected = _count_hl(path, "22")
    found = sum(len(list(model.subscribers())) for model in _read(path))
    assert found == expected


@pytest.mark.parametrize("path", _samples(*CLAIM_SETS), ids=lambda p: p.name)
def test_dependents_are_reported_on_their_subscriber(path):
    """Every HL at level 23 must appear as a dependent of some subscriber."""
    expected = _count_hl(path, "23")
    found = sum(
        len(subscriber.dependents)
        for model in _read(path)
        for subscriber in model.subscribers()
    )
    assert found == expected


# --- both branches ---------------------------------------------------------


def test_a_claim_for_a_dependent_is_found(tmp_path):
    """The branch that walking only loop 2000B would miss entirely."""
    model = _from_text(
        generate_837p(seed=1, claims=4, dependent_rate=1.0), tmp_path, "dep.837"
    )
    claims = list(model.claims())
    assert len(claims) == 4
    assert all(claim.is_dependent for claim in claims)


def test_a_claim_for_the_subscriber_is_found(tmp_path):
    model = _from_text(
        generate_837p(seed=1, claims=4, dependent_rate=0.0), tmp_path, "sub.837"
    )
    claims = list(model.claims())
    assert len(claims) == 4
    assert not any(claim.is_dependent for claim in claims)


def test_the_patient_is_the_dependent_not_the_subscriber(tmp_path):
    """
    ``patient`` points at whoever was treated, so a caller never has to know
    which branch the claim came from. On a dependent claim that is loop
    2010CA, and it is a different person from the subscriber.
    """
    model = _from_text(
        generate_837p(seed=2, claims=1, dependent_rate=1.0), tmp_path, "who.837"
    )
    claim = next(iter(model.claims()))
    assert claim.is_dependent
    assert claim.patient is not claim.subscriber
    assert claim.patient.nm1_segment.entity_identifier_code == "QC"
    assert claim.subscriber.nm1_segment.entity_identifier_code == "IL"


def test_the_patient_is_the_subscriber_when_there_is_no_dependent(tmp_path):
    model = _from_text(
        generate_837p(seed=2, claims=1, dependent_rate=0.0), tmp_path, "self.837"
    )
    claim = next(iter(model.claims()))
    assert not claim.is_dependent
    assert claim.patient is claim.subscriber
    assert claim.relationship == "18"


def test_the_relationship_comes_from_pat01_for_a_dependent(tmp_path):
    model = _from_text(
        generate_837p(seed=5, claims=3, dependent_rate=1.0), tmp_path, "rel.837"
    )
    assert all(claim.relationship == "19" for claim in model.claims())


# --- laziness and order ----------------------------------------------------


def test_claims_is_lazy(tmp_path):
    """A generator, not a list: a large file must not be materialised."""
    model = _from_text(generate_837p(seed=6, claims=5), tmp_path, "lazy.837")
    claims = model.claims()
    assert not isinstance(claims, list)
    assert next(claims).patient_control_number == "PCN000001"


def test_claims_are_yielded_in_file_order(tmp_path):
    model = _from_text(generate_837p(seed=7, claims=8), tmp_path, "order.837")
    numbers = [claim.patient_control_number for claim in model.claims()]
    assert numbers == sorted(numbers)


# --- what a record carries -------------------------------------------------


def test_a_submitted_claim_carries_its_context(tmp_path):
    model = _from_text(
        generate_837p(
            seed=9,
            claims=2,
            billing_provider_name="EXAMPLE MEDICAL GROUP",
            payer_name="EXAMPLE HEALTH PLAN",
        ),
        tmp_path,
        "ctx.837",
    )
    claim = next(iter(model.claims()))
    assert isinstance(claim, SubmittedClaim)
    assert claim.billing_provider_name == "EXAMPLE MEDICAL GROUP"
    assert claim.payer_name == "EXAMPLE HEALTH PLAN"
    assert claim.billing_provider_npi and len(claim.billing_provider_npi) == 10
    assert claim.member_id
    assert claim.charge == sum(
        line.sv1_segment.line_item_charge_amount for line in claim.service_lines
    )
    assert claim.claim is not None


def test_a_paid_claim_carries_its_context(tmp_path):
    model = _from_text(
        generate_835(
            seed=9,
            claims=3,
            payer_name="EXAMPLE HEALTH PLAN",
            payee_name="EXAMPLE MEDICAL GROUP",
        ),
        tmp_path,
        "ctx.835",
    )
    claim = next(iter(model.claims()))
    assert isinstance(claim, PaidClaim)
    assert claim.payer_name == "EXAMPLE HEALTH PLAN"
    assert claim.payee_name == "EXAMPLE MEDICAL GROUP"
    assert claim.header_number == "1"
    assert isinstance(claim.charge, Decimal)
    assert claim.paid == claim.charge - sum(
        (
            amount
            for record in claim.adjustments
            + [
                adjustment
                for line in claim.service_lines
                for adjustment in (line.cas_segment or [])
            ]
            for amount in [getattr(record, f"monetary_amount_{i}") for i in range(1, 7)]
            if amount is not None
        ),
        Decimal("0.00"),
    )


def test_the_835_patient_name_is_found_among_the_nm1_segments(tmp_path):
    """Loop 2100 carries up to seven NM1s; the patient is the one marked QC."""
    model = _from_text(generate_835(seed=4, claims=2), tmp_path, "who.835")
    for claim in model.claims():
        assert claim.patient.entity_identifier_code == "QC"
        last, first = claim.patient_name
        assert last and first


def test_accessor_records_are_immutable(tmp_path):
    model = _from_text(generate_837p(seed=8, claims=1), tmp_path, "frozen.837")
    claim = next(iter(model.claims()))
    with pytest.raises(Exception):
        claim.is_dependent = True


# --- the institutional model shares the traversal --------------------------


def test_the_institutional_model_has_the_same_accessors():
    """837I loop names match 837P at every level walked, so one pass serves both."""
    from x12sdk.v5010.x12_837_005010X223A3.transaction_set import (
        HealthCareClaimInstitutional,
    )

    assert hasattr(HealthCareClaimInstitutional, "claims")
    assert hasattr(HealthCareClaimInstitutional, "subscribers")

    path = RESOURCES / "837_005010X223A3"
    sample = sorted(path.glob("*"))[0]
    model = _read(sample)[0]
    assert isinstance(model, HealthCareClaimInstitutional)
    assert list(model.claims())


def test_the_accessors_do_not_add_model_fields():
    """
    The mixin must contribute behaviour only. A field slipping in would change
    what serializes and break the round trip on every sample.
    """
    from x12sdk.v5010.x12_835_005010X221A1.transaction_set import (
        HealthCareClaimPayment,
    )
    from x12sdk.v5010.x12_837_005010X222A2.transaction_set import (
        HealthCareClaimProfessional,
    )

    assert set(HealthCareClaimProfessional.model_fields) == {
        "header",
        "loop_1000a",
        "loop_1000b",
        "loop_2000a",
        "footer",
    }
    assert set(HealthCareClaimPayment.model_fields) == {
        "header",
        "loop_1000a",
        "loop_1000b",
        "loop_2000",
        "footer",
    }
