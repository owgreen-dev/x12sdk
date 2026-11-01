"""
test_generate_pairs.py

A pair is only useful if the two sides agree. Each test joins the 837 to the
835 the way real files are joined, CLM01 to CLP01, and checks that what the
payer answered is what the provider billed: the same claims, charges, lines,
procedures, patient, payer and payee. Both sides must also stand on their
own: parse, validate (the 835 balance rules included) and round-trip.
"""

from decimal import Decimal

import pytest

from x12sdk.generate import (
    ClaimPair,
    ClaimSpec,
    ServiceLineSpec,
    ValueFactory,
    adjudicate,
    denial,
    generate_claim_pair,
    patient_responsibility,
)
from x12sdk.io import X12ModelReader
from x12sdk.v5010.x12_835_005010X221A1.transaction_set import HealthCareClaimPayment
from x12sdk.v5010.x12_837_005010X222A2.transaction_set import (
    HealthCareClaimProfessional,
)
from x12sdk.v5010.x12_837_005010X223A3.transaction_set import (
    HealthCareClaimInstitutional,
)
from x12sdk.v5010.x12_837_005010X224A2.transaction_set import HealthCareClaimDental

from .support import assert_eq_model

CLAIM_TYPES = {
    "837p": HealthCareClaimProfessional,
    "837i": HealthCareClaimInstitutional,
    "837d": HealthCareClaimDental,
}


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        models = list(reader.models())
    assert len(models) == 1
    return models[0]


def _joined(pair: ClaimPair):
    """``(submitted, paid)`` claim pairs, joined on the patient control number."""
    submitted = list(_read(pair.claim).claims())
    paid = {
        claim.patient_control_number: claim for claim in _read(pair.remittance).claims()
    }
    assert len(paid) == len(submitted)
    return [(claim, paid[claim.patient_control_number]) for claim in submitted]


def _service(line):
    """The SV1, SV2 or SV3 on a 2400, whichever the claim type uses."""
    for name in ("sv1_segment", "sv2_segment", "sv3_segment"):
        segment = getattr(line, name, None)
        if segment is not None:
            return segment
    raise AssertionError("a service line without a service segment")


def _procedure(line) -> str:
    """The billed procedure composite, e.g. ``HC:99213`` or ``AD:D2391``."""
    segment = _service(line)
    return getattr(segment, "product_service_id_qualifier", None) or (
        segment.composite_medical_procedure_identifier
    )


# --- both sides are real X12 -------------------------------------------------


@pytest.mark.parametrize("claim_type", CLAIM_TYPES)
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_both_sides_parse_as_the_right_transactions(claim_type, seed):
    pair = generate_claim_pair(seed=seed, claims=6, claim_type=claim_type)
    assert isinstance(_read(pair.claim), CLAIM_TYPES[claim_type])
    assert isinstance(_read(pair.remittance), HealthCareClaimPayment)


@pytest.mark.parametrize("claim_type", CLAIM_TYPES)
def test_both_sides_round_trip(claim_type, tmp_path):
    pair = generate_claim_pair(seed=5, claims=6, claim_type=claim_type)
    for name, x12 in (("claim.837", pair.claim), ("remittance.835", pair.remittance)):
        path = tmp_path / name
        path.write_text(x12)
        assert_eq_model(str(path))


def test_the_same_seed_produces_the_same_pair():
    assert generate_claim_pair(seed=3, claims=5) == generate_claim_pair(
        seed=3, claims=5
    )


def test_the_pair_unpacks_as_claim_then_remittance():
    claim, remittance = generate_claim_pair(seed=1, claims=2)
    assert "ST*837*" in claim
    assert "ST*835*" in remittance


def test_the_provider_sends_the_claim_and_receives_the_remittance():
    pair = generate_claim_pair(seed=1, claims=2, provider_id="PROVX", payer_id="PAYERX")
    claim_group = next(s for s in pair.claim.split("~") if s.strip().startswith("GS"))
    paid_group = next(
        s for s in pair.remittance.split("~") if s.strip().startswith("GS")
    )
    assert claim_group.split("*")[2:4] == ["PROVX", "PAYERX"]
    assert paid_group.split("*")[2:4] == ["PAYERX", "PROVX"]


# --- the two sides agree -----------------------------------------------------


@pytest.mark.parametrize("claim_type", CLAIM_TYPES)
def test_every_claim_is_answered_once_with_the_same_charge_and_lines(claim_type):
    joined = _joined(generate_claim_pair(seed=11, claims=15, claim_type=claim_type))
    for submitted, paid in joined:
        assert paid.charge == submitted.charge
        assert [
            svc.svc_segment.composite_medical_procedure_identifier_1
            for svc in paid.service_lines
        ] == [_procedure(line) for line in submitted.service_lines]
        assert [
            svc.svc_segment.line_item_charge_amount for svc in paid.service_lines
        ] == [
            _service(line).line_item_charge_amount for line in submitted.service_lines
        ]


@pytest.mark.parametrize("claim_type", CLAIM_TYPES)
def test_the_patient_payer_and_payee_are_the_same_on_both_sides(claim_type):
    pair = generate_claim_pair(seed=12, claims=15, claim_type=claim_type)
    for submitted, paid in _joined(pair):
        assert paid.patient_name == submitted.patient_name
        assert paid.patient.identification_code == submitted.member_id
        assert paid.payer_name == submitted.payer_name
        assert paid.payee_name == submitted.billing_provider_name
        assert (
            paid.payee.n1_segment.identification_code == submitted.billing_provider_npi
        )


def test_both_patient_branches_are_paired():
    joined = _joined(generate_claim_pair(seed=4, claims=20))
    assert any(submitted.is_dependent for submitted, _ in joined)
    assert any(not submitted.is_dependent for submitted, _ in joined)


def test_a_dental_remittance_pays_cdt_codes():
    joined = _joined(generate_claim_pair(seed=2, claims=8, claim_type="837d"))
    codes = [
        svc.svc_segment.composite_medical_procedure_identifier_1
        for _, paid in joined
        for svc in paid.service_lines
    ]
    assert codes and all(code.startswith("AD:D") for code in codes)


# --- outcomes ------------------------------------------------------------------


def test_invented_outcomes_mix_paid_reduced_and_denied():
    joined = _joined(generate_claim_pair(seed=6, claims=60))
    paid = [p for _, p in joined]
    denied = [p for p in paid if p.status == "4"]
    assert denied and all(p.paid == 0 for p in denied)
    in_full = [p for p in paid if p.status == "1" and p.paid == p.charge]
    reduced = [p for p in paid if p.status == "1" and 0 < p.paid < p.charge]
    assert in_full and reduced
    assert all(0 <= p.paid <= p.charge for p in paid)


@pytest.mark.parametrize("rate,expected", [(0.0, 0), (1.0, 20)])
def test_the_denial_rate_controls_how_many_are_denied(rate, expected):
    joined = _joined(generate_claim_pair(seed=6, claims=20, denial_rate=rate))
    assert sum(paid.status == "4" for _, paid in joined) == expected


def test_a_specified_outcome_appears_on_the_remittance_only():
    """
    One spec describes both sides: the claim as billed, and what the payer did
    with it. The decision reaches the 835 and is kept off the 837.
    """
    spec = [
        ClaimSpec(
            charge="500.00",
            patient_control_number="ACCT-1",
            lines=[
                ServiceLineSpec(
                    charge="300.00",
                    procedure="99214",
                    adjustments=[denial("CO", "45", "60.00")],
                ),
                ServiceLineSpec(
                    charge="200.00",
                    procedure="85025",
                    adjustments=[patient_responsibility("1", "40.00")],
                ),
            ],
        ),
        ClaimSpec(
            charge="120.00",
            patient_control_number="ACCT-2",
            status="4",
            lines=[
                ServiceLineSpec(
                    charge="120.00",
                    procedure="93000",
                    adjustments=[denial("CO", "29", "120.00")],
                )
            ],
        ),
    ]
    pair = generate_claim_pair(seed=1, claims=spec)
    assert "CAS*" not in pair.claim

    joined = dict(
        (submitted.patient_control_number, paid) for submitted, paid in _joined(pair)
    )
    assert joined["ACCT-1"].paid == Decimal("400.00")
    assert joined["ACCT-1"].status == "1"
    assert joined["ACCT-2"].paid == Decimal("0.00")
    assert joined["ACCT-2"].status == "4"
    assert "CAS*CO*29*120.00" in pair.remittance


def test_adjudication_never_breaks_the_balance_rule():
    values = ValueFactory(8)
    claim = ClaimSpec(
        charge="300.00",
        lines=[ServiceLineSpec(charge="100.00"), ServiceLineSpec(charge="200.00")],
    )
    for _ in range(200):
        decided = adjudicate(claim, values, denial_rate=0.3)
        assert 0 <= decided.paid <= decided.charge
        assert all(0 <= line.paid <= line.charge for line in decided.lines)


# --- what cannot be paired -------------------------------------------------------


def test_an_unknown_claim_type_is_rejected():
    with pytest.raises(ValueError, match="claim_type must be one of"):
        generate_claim_pair(seed=0, claims=2, claim_type="835")


def test_zero_claims_is_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        generate_claim_pair(seed=0, claims=0)


def test_duplicate_patient_control_numbers_are_rejected():
    """CLM01 = CLP01 is the link; two claims sharing it could not be told apart."""
    line = [ServiceLineSpec(charge="10.00", procedure="99213")]
    spec = [
        ClaimSpec(charge="10.00", lines=line, patient_control_number="SAME"),
        ClaimSpec(charge="10.00", lines=line, patient_control_number="SAME"),
    ]
    with pytest.raises(ValueError, match="must be unique"):
        generate_claim_pair(seed=0, claims=spec)


def test_invented_denials_are_administrative_only():
    """
    Outright denials are for paperwork and coverage reasons, never a judgment
    about the care (medical necessity, CARC 50) or a billing pattern.
    """
    pair = generate_claim_pair(seed=3, claims=200, denial_rate=1.0)
    reasons = {
        cas.adjustment_reason_code_1
        for _, paid in _joined(pair)
        for svc in paid.service_lines
        for cas in svc.cas_segment or []
    }
    assert reasons
    assert reasons <= {"16", "27", "29", "96", "197"}
