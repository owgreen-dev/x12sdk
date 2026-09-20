"""
test_generate_837i.py

The institutional claim shares the 837P's hierarchy and specification types,
so the same bar applies: parse, validate, round-trip byte for byte,
reproduce from a seed, and carry both patient branches. What is checked here
beyond that is what makes it institutional: SV2 revenue-code lines rather
than SV1 procedures, CL1 admission and status, and a statement date.
"""

import random
from decimal import Decimal

import pytest

from x12sdk.generate import (
    ClaimSpec,
    PatientSpec,
    ServiceLineSpec,
    SubmissionSpec,
    denial,
    generate_837i,
)
from x12sdk.io import X12ModelReader

from .support import assert_eq_model


def _read(x12: str, tmp_path, name="g.837"):
    path = tmp_path / name
    path.write_text(x12)
    with X12ModelReader(str(path)) as reader:
        return list(reader.models())


def _segments(x12: str):
    return [
        segment.split("*")
        for segment in (s for s in x12.replace("\n", "").split("~") if s)
        if segment.split("*")[0] not in ("ISA", "GS", "GE", "IEA")
    ]


def _hl(x12: str, level_code: str):
    return [s for s in _segments(x12) if s[0] == "HL" and s[3] == level_code]


# --- the output is real X12 -----------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 1234])
@pytest.mark.parametrize("claims", [1, 3, 10])
def test_generated_institutional_claims_parse(seed, claims, tmp_path):
    models = _read(generate_837i(seed=seed, claims=claims), tmp_path)
    assert len(models) == 1
    assert len(list(models[0].claims())) == claims


@pytest.mark.parametrize("seed", [0, 3, 99])
def test_generated_institutional_claims_round_trip(seed, tmp_path):
    path = tmp_path / f"generated-{seed}.837"
    path.write_text(generate_837i(seed=seed, claims=5))
    assert_eq_model(str(path))


def test_segment_count_is_computed_not_guessed():
    segments = _segments(generate_837i(seed=11, claims=4))
    assert segments[-1][0] == "SE"
    assert int(segments[-1][1]) == len(segments)


def test_the_transaction_is_institutional():
    """ST03 names the institutional implementation and GS01 is HC."""
    x12 = generate_837i(seed=2, claims=2)
    st = next(s for s in _segments(x12) if s[0] == "ST")
    assert st[3] == "005010X223A3"
    assert (
        next(line for line in x12.splitlines() if line.startswith("GS*")).split("*")[1]
        == "HC"
    )


# --- what makes it institutional --------------------------------------------


def test_lines_bill_by_revenue_code_in_sv2_not_sv1():
    segments = _segments(generate_837i(seed=4, claims=3))
    assert not [s for s in segments if s[0] == "SV1"]
    sv2 = [s for s in segments if s[0] == "SV2"]
    assert sv2
    for line in sv2:
        assert line[1].isdigit() and len(line[1]) == 4, "SV201 is a revenue code"
        assert line[2].startswith("HC:"), "SV202 carries the procedure composite"
        Decimal(line[3])
        assert line[4] == "UN"


def test_every_claim_carries_admission_status_and_a_statement_date():
    segments = _segments(generate_837i(seed=5, claims=4))
    names = [s[0] for s in segments]
    assert names.count("CLM") == 4
    assert names.count("CL1") == 4
    statement_dates = [s for s in segments if s[0] == "DTP" and s[1] == "434"]
    assert len(statement_dates) == 4


def test_the_claim_charge_equals_the_service_line_total():
    """CLM02 == SUM(SV203), which the model enforces; the generator honours it."""
    segments = _segments(generate_837i(seed=17, claims=8))
    charges, claim_charge, total = [], None, Decimal("0.00")
    for segment in segments:
        if segment[0] == "CLM":
            if claim_charge is not None:
                charges.append((claim_charge, total))
            claim_charge, total = Decimal(segment[2]), Decimal("0.00")
        elif segment[0] == "SV2":
            total += Decimal(segment[3])
    charges.append((claim_charge, total))
    assert charges and all(c == t for c, t in charges)


# --- both branches ---------------------------------------------------------


def test_both_patient_branches_are_generated_by_default():
    x12 = generate_837i(seed=3, claims=20)
    assert _hl(x12, "22") and _hl(x12, "23")


def test_hierarchical_ids_are_unique_and_point_at_a_real_parent():
    seen = set()
    for _, hl_id, parent, level, _child in (
        s for s in _segments(generate_837i(seed=8, claims=12)) if s[0] == "HL"
    ):
        assert hl_id not in seen
        assert parent == "" if level == "20" else parent in seen
        seen.add(hl_id)


def test_a_dependent_omits_the_subscriber_relationship_and_carries_pat():
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(charge="100.00", lines=[ServiceLineSpec(charge="100.00")])
                ],
                dependent=True,
                relationship="19",
            )
        ]
    )
    segments = _segments(generate_837i(seed=1, claims=spec))
    assert next(s for s in segments if s[0] == "SBR")[2] == ""
    assert next(s for s in segments if s[0] == "PAT")[1] == "19"


# --- reproducibility -------------------------------------------------------


def test_the_same_seed_produces_the_same_bytes():
    assert generate_837i(seed=21, claims=6) == generate_837i(seed=21, claims=6)


def test_different_seeds_produce_different_files():
    assert generate_837i(seed=21, claims=6) != generate_837i(seed=22, claims=6)


def test_generation_does_not_disturb_the_global_random_state():
    random.seed(4242)
    expected = [random.random() for _ in range(3)]
    random.seed(4242)
    generate_837i(seed=1, claims=5)
    assert [random.random() for _ in range(3)] == expected


# --- scenario control ------------------------------------------------------


def test_a_specified_claim_appears_verbatim():
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge="450.00",
                        patient_control_number="ACCT-9001",
                        lines=[
                            ServiceLineSpec(charge="300.00", procedure="99214"),
                            ServiceLineSpec(
                                charge="150.00", procedure="85025", units=2
                            ),
                        ],
                    )
                ]
            )
        ],
        billing_provider_name="EXAMPLE HOSPITAL",
        payer_name="EXAMPLE HEALTH PLAN",
    )
    segments = _segments(generate_837i(seed=5, claims=spec))
    clm = next(s for s in segments if s[0] == "CLM")
    assert clm[1] == "ACCT-9001" and clm[2] == "450.00"
    sv2 = [s for s in segments if s[0] == "SV2"]
    assert [s[2] for s in sv2] == ["HC:99214", "HC:85025"]
    assert [s[3] for s in sv2] == ["300.00", "150.00"]
    assert [s[5] for s in sv2] == ["1", "2"]
    names = [s[3] for s in segments if s[0] == "NM1"]
    assert "EXAMPLE HOSPITAL" in names and "EXAMPLE HEALTH PLAN" in names


def test_adjustments_are_rejected_on_a_submission():
    with pytest.raises(ValueError, match="cannot be represented"):
        generate_837i(
            seed=1,
            claims=[
                ClaimSpec(
                    charge="100.00",
                    lines=[
                        ServiceLineSpec(
                            charge="100.00", adjustments=[denial("CO", "45", "20.00")]
                        )
                    ],
                )
            ],
        )


def test_zero_claims_is_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        generate_837i(seed=0, claims=0)
