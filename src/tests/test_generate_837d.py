"""
test_generate_837d.py

The same bar as the other generators: output must parse, satisfy every model
validator, round-trip byte for byte, and be reproducible from its seed.

What the dental claim adds is the tooth. A line is a procedure done to a tooth
(with surfaces, for a filling), or a procedure that is not (an exam), and code
reading an 837D has to cope with both, so generated files must contain both.
A tooth on a professional or institutional claim has nowhere to go, and is
refused rather than dropped.
"""

from decimal import Decimal

import pytest

from x12sdk.generate import (
    ClaimSpec,
    PatientSpec,
    ServiceLineSpec,
    SubmissionSpec,
    ValueFactory,
    build_837i,
    build_837p,
    generate_837d,
    random_dental_lines,
)
from x12sdk.io import X12ModelReader
from x12sdk.v5010.x12_837_005010X224A2.transaction_set import HealthCareClaimDental

from .support import assert_eq_model


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        return list(reader.models())


def _segments(x12: str):
    """The transaction body, ST through SE, as ``[name, *fields]`` lists."""
    return [
        segment.split("*")
        for segment in (s for s in x12.replace("\n", "").split("~") if s)
        if segment.split("*")[0] not in ("ISA", "GS", "GE", "IEA")
    ]


def _lines(submission):
    return [line for claim in submission.claims() for line in claim.service_lines]


# --- the output is real X12 -----------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 1234])
@pytest.mark.parametrize("claims", [1, 3, 10])
def test_generated_claims_parse(seed, claims):
    models = _read(generate_837d(seed=seed, claims=claims))
    assert len(models) == 1
    assert isinstance(models[0], HealthCareClaimDental)
    assert len(list(models[0].claims())) == claims


@pytest.mark.parametrize("seed", [0, 3, 99])
def test_generated_claims_round_trip(seed, tmp_path):
    path = tmp_path / f"generated-{seed}.837"
    path.write_text(generate_837d(seed=seed, claims=6))
    assert_eq_model(str(path))


def test_the_implementation_guide_is_the_dental_one():
    segments = _segments(generate_837d(seed=2, claims=2))
    assert segments[0][:4] == ["ST", "837", "0001", "005010X224A2"]


def test_segment_count_is_computed_not_guessed():
    segments = _segments(generate_837d(seed=11, claims=4))
    assert segments[-1][0] == "SE"
    assert int(segments[-1][1]) == len(segments)


def test_the_same_seed_produces_the_same_bytes():
    assert generate_837d(seed=9, claims=5) == generate_837d(seed=9, claims=5)


def test_different_seeds_produce_different_files():
    assert generate_837d(seed=1, claims=5) != generate_837d(seed=2, claims=5)


# --- what makes it dental ----------------------------------------------------


def test_every_line_bills_a_cdt_code_under_the_ad_qualifier():
    submission = _read(generate_837d(seed=4, claims=12))[0]
    procedures = [
        line.sv3_segment.composite_medical_procedure_identifier
        for line in _lines(submission)
    ]
    assert procedures
    assert all(p.startswith("AD:D") for p in procedures)


def test_lines_with_and_without_a_tooth_both_appear_by_default():
    """An exam has no tooth and a crown has one; readers must handle both."""
    lines = _lines(_read(generate_837d(seed=3, claims=20))[0])
    assert any(line.too_segment for line in lines), "no line names a tooth"
    assert any(not line.too_segment for line in lines), "every line names a tooth"
    assert any(
        line.too_segment and line.too_segment[0].tooth_surface for line in lines
    ), "no line names a surface"


def test_both_patient_branches_are_generated_by_default():
    claims = list(_read(generate_837d(seed=3, claims=20))[0].claims())
    assert any(claim.is_dependent for claim in claims)
    assert any(not claim.is_dependent for claim in claims)


def test_one_payer_is_named_throughout_the_file():
    """1000B and every subscriber's 2010BB name the same payer."""
    submission = _read(generate_837d(seed=8, claims=10))[0]
    receiver = submission.loop_1000b.nm1_segment.name_last_or_organization_name
    assert {claim.payer_name for claim in submission.claims()} == {receiver}


def test_the_claim_charge_equals_the_service_line_total():
    for claim in _read(generate_837d(seed=17, claims=8))[0].claims():
        line_total = sum(
            (line.sv3_segment.line_item_charge_amount for line in claim.service_lines),
            Decimal("0.00"),
        )
        assert claim.charge == line_total


def test_a_specified_line_appears_verbatim():
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge="395.00",
                        patient_control_number="DENT-1",
                        lines=[
                            ServiceLineSpec(charge="55.00", procedure="D0120"),
                            ServiceLineSpec(
                                charge="340.00",
                                procedure="D2392",
                                tooth="19",
                                surfaces=("M", "O"),
                            ),
                        ],
                    )
                ]
            )
        ],
        payer_name="EXAMPLE DENTAL PLAN",
    )
    segments = _segments(generate_837d(seed=5, claims=spec))

    assert next(s for s in segments if s[0] == "CLM")[1:3] == ["DENT-1", "395.00"]
    sv3 = [s for s in segments if s[0] == "SV3"]
    assert [s[1] for s in sv3] == ["AD:D0120", "AD:D2392"]
    assert [s for s in segments if s[0] == "TOO"] == [["TOO", "JP", "19", "M:O"]]
    # the exam carries no tooth: the only TOO follows the filling's SV3
    too_at = next(i for i, s in enumerate(segments) if s[0] == "TOO")
    assert segments[too_at - 1][1] == "AD:D2392"


def test_a_specified_procedure_without_a_tooth_gets_none_invented():
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge="900.00",
                        lines=[ServiceLineSpec(charge="900.00", procedure="D2740")],
                    )
                ]
            )
        ]
    )
    segments = _segments(generate_837d(seed=1, claims=spec))
    assert not [s for s in segments if s[0] == "TOO"]


def test_a_tooth_with_no_procedure_keeps_the_tooth_given():
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge="100.00",
                        lines=[ServiceLineSpec(charge="100.00", tooth="A")],
                    )
                ]
            )
        ]
    )
    too = [s for s in _segments(generate_837d(seed=1, claims=spec)) if s[0] == "TOO"]
    assert too == [["TOO", "JP", "A"]]


def test_invented_lines_already_carry_their_procedure_and_tooth():
    """So a caller can build one spec and feed it to the 837D and the 835 alike."""
    lines = random_dental_lines(ValueFactory(6), 30)
    assert all(line.procedure and line.procedure.startswith("D") for line in lines)
    assert any(line.tooth for line in lines)
    assert all(not line.surfaces or line.tooth for line in lines)


# --- what cannot be written down -----------------------------------------------


@pytest.mark.parametrize(
    "fields,match",
    [
        ({"tooth": "33"}, "tooth must be"),
        ({"tooth": "Z"}, "tooth must be"),
        ({"surfaces": ("M",)}, "give the tooth"),
        ({"tooth": "3", "surfaces": ("X",)}, "surfaces must be among"),
        ({"tooth": "3", "surfaces": ("M", "M")}, "named twice"),
        ({"tooth": "3", "surfaces": ("B", "D", "F", "L", "M", "O")}, "at most five"),
    ],
)
def test_an_impossible_tooth_is_rejected(fields, match):
    with pytest.raises(ValueError, match=match):
        ServiceLineSpec(charge="10.00", **fields)


@pytest.mark.parametrize("build,label", [(build_837p, "837P"), (build_837i, "837I")])
def test_a_tooth_is_refused_on_a_claim_with_nowhere_to_put_it(build, label):
    spec = SubmissionSpec(
        patients=[
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge="10.00",
                        lines=[ServiceLineSpec(charge="10.00", tooth="8")],
                    )
                ]
            )
        ]
    )
    with pytest.raises(ValueError, match=f"an {label} has nowhere"):
        build(spec)


def test_zero_claims_is_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        generate_837d(seed=0, claims=0)
