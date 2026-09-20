"""
Leg 3: repeat stress.

Generate every transaction the generators can build with three of everything
that may repeat, on both patient branches where the transaction has them, and
require every segment written to come back from the parser exactly once.

Bug class: a parser that keeps only the last occurrence of something that
repeats. The corpus cannot catch it because no inherited sample repeats the
affected loop; a byte-for-byte round trip of a file with one occurrence proves
nothing about the second. This is the dynamic twin of the structural check
that finds assign-instead-of-append in the parser source.

Instances: 270 loop 2110C, 834 loop 2200 (2.0.0); 834 loop 2100D, 837P
loop 2330C, 4010 837 loop 2330C (2.0.1).
"""

from __future__ import annotations

import collections
from typing import Counter

import pytest

from x12sdk.generate import (
    AdjustmentSpec,
    BenefitSpec,
    ClaimSpec,
    ClaimStatusSpec,
    CoverageSpec,
    EligibilitySpec,
    EnrolleeSpec,
    EnrollmentSpec,
    MemberSpec,
    PatientSpec,
    ServiceLineSpec,
    StatusPatientSpec,
    SubmissionSpec,
    TrackedClaimSpec,
    generate_270,
    generate_271,
    generate_276,
    generate_277,
    generate_834,
    generate_835,
    generate_837i,
    generate_837p,
)
from x12sdk.io import X12ModelReader

THREE = 3
ENVELOPE = {"ISA", "GS", "GE", "IEA"}


def _raw_counts(x12: str) -> Counter:
    """Segment name -> occurrences in the text, envelope excluded."""
    names = (s.split("*")[0] for s in x12.replace("\n", "").split("~") if s)
    return collections.Counter(n for n in names if n not in ENVELOPE)


def _model_counts(model) -> Counter:
    """Segment name -> occurrences reachable in the parsed model."""
    counts: Counter = collections.Counter()

    def walk(node):
        if isinstance(node, dict):
            name = node.get("segment_name")
            if name is not None and not isinstance(name, dict):
                counts[str(getattr(name, "value", name))] += 1
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(model.model_dump())
    return counts


def _parse(x12: str, tmp_path, name: str):
    path = tmp_path / name
    path.write_text(x12)
    with X12ModelReader(str(path)) as reader:
        models = list(reader.models())
    assert len(models) == 1
    return models[0]


def _line(charge: str, adjustments=()):
    return ServiceLineSpec(charge=charge, adjustments=tuple(adjustments))


def _claim(charge_per_line: str, adjustments=(), line_adjustments=()):
    return ClaimSpec(
        charge=str(THREE * float(charge_per_line)),
        adjustments=tuple(adjustments),
        lines=tuple(_line(charge_per_line, line_adjustments) for _ in range(THREE)),
    )


def _three_adjustments(group: str = "CO"):
    return tuple(
        AdjustmentSpec(group=group, reason=r, amount="1.00") for r in ("45", "97", "18")
    )


CASES = {
    "835": lambda: generate_835(
        seed=3,
        claims=[
            _claim(
                "30.00",
                adjustments=_three_adjustments(),
                line_adjustments=_three_adjustments("PR"),
            )
            for _ in range(THREE)
        ],
    ),
    "837I": lambda: generate_837i(
        seed=3,
        claims=SubmissionSpec(
            patients=[
                PatientSpec(
                    claims=[_claim("30.00") for _ in range(THREE)],
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
    "837P": lambda: generate_837p(
        seed=3,
        claims=SubmissionSpec(
            patients=[
                PatientSpec(
                    claims=[_claim("30.00") for _ in range(THREE)], dependent=i % 2 == 1
                )
                for i in range(THREE)
            ]
        ),
    ),
    "270": lambda: generate_270(
        seed=3,
        members=EligibilitySpec(
            members=[
                MemberSpec(
                    benefits=tuple(
                        BenefitSpec(service_type=s) for s in ("30", "35", "88")
                    ),
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
    "271": lambda: generate_271(
        seed=3,
        members=EligibilitySpec(
            members=[
                MemberSpec(
                    benefits=tuple(
                        BenefitSpec(service_type=s) for s in ("30", "35", "88")
                    ),
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
    "276": lambda: generate_276(
        seed=3,
        patients=ClaimStatusSpec(
            patients=[
                StatusPatientSpec(
                    claims=[TrackedClaimSpec(charge="10.00") for _ in range(THREE)],
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
    "277": lambda: generate_277(
        seed=3,
        patients=ClaimStatusSpec(
            patients=[
                StatusPatientSpec(
                    claims=[
                        TrackedClaimSpec(charge="10.00", paid="5.00")
                        for _ in range(THREE)
                    ],
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
    "834": lambda: generate_834(
        seed=3,
        enrollees=EnrollmentSpec(
            enrollees=[
                EnrolleeSpec(
                    coverages=tuple(
                        CoverageSpec(insurance_line=line)
                        for line in ("HLT", "DEN", "VIS")
                    ),
                    dependent=i % 2 == 1,
                )
                for i in range(THREE)
            ]
        ),
    ),
}


@pytest.mark.parametrize("label", sorted(CASES))
def test_every_segment_written_comes_back_exactly_once(label, tmp_path):
    """
    The oracle: the multiset of segment names in the text equals the multiset
    reachable in the parsed model. A parser that overwrote a repeated loop
    would come back short by exactly the occurrences it lost.
    """
    x12 = CASES[label]()
    model = _parse(x12, tmp_path, f"stress.{label}")
    written, parsed = _raw_counts(x12), _model_counts(model)
    missing = {k: v - parsed[k] for k, v in written.items() if parsed[k] < v}
    extra = {
        k: parsed[k] - written.get(k, 0)
        for k in parsed
        if parsed[k] > written.get(k, 0)
    }
    assert not missing and not extra, f"lost {missing}, invented {extra}"


@pytest.mark.parametrize("label", sorted(CASES))
def test_repeats_round_trip_byte_for_byte(label, tmp_path):
    """Belt and braces: what was written is exactly what comes back out."""
    x12 = CASES[label]()
    model = _parse(x12, tmp_path, f"stress.{label}")
    body = "\n".join(x12.splitlines()[2:-2])
    assert model.x12() == body


@pytest.mark.parametrize("label", sorted(CASES))
def test_three_of_everything_is_really_three(label):
    """
    Guard the fixtures themselves: each case must actually repeat something
    three times, or the test above is only re-running the corpus.
    """
    counts = _raw_counts(CASES[label]())
    repeated = {name: n for name, n in counts.items() if n >= THREE * THREE}
    assert repeated, f"{label} case repeats nothing enough to matter: {dict(counts)}"
