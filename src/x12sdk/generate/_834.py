"""
Builds 834 benefit enrollment and maintenance transactions.

The 834 is the one supported transaction with no HL hierarchy. A dependent is
not a loop nested under the subscriber but a separate member record, told
apart by INS01 (Y for the subscriber, N for a dependent) and INS02, the
relationship. So there is no subscriber/dependent branch to fall down here,
but the two kinds of record still have to be generated, because code reading
an 834 has to tell them apart.

As elsewhere, SE01 is counted with :func:`x12sdk.support.count_segments`.
"""

from __future__ import annotations

from typing import Dict, List

from ..support import count_segments
from ..v5010.segments import (
    BgnSegment,
    HdSegment,
    N3Segment,
    N4Segment,
    SeSegment,
)
from ..v5010.x12_834_005010X220A1.loops import (
    Footer,
    Header,
    Loop1000A,
    Loop1000B,
    Loop2000,
    Loop2100A,
    Loop2300,
)
from ..v5010.x12_834_005010X220A1.segments import (
    HeaderStSegment,
    Loop1000AN1Segment,
    Loop1000BN1Segment,
    Loop2000DtpSegment,
    Loop2000InsSegment,
    Loop2000RefSegment,
    Loop2100ADmgSegment,
    Loop2100ANm1Segment,
    Loop2300DtpSegment,
)
from ..v5010.x12_834_005010X220A1.transaction_set import BenefitEnrollmentAndMaintenance
from ._spec import CoverageSpec, EnrolleeSpec, EnrollmentSpec
from ._values import ValueFactory


def _coverage(coverage: CoverageSpec, begins: str) -> Loop2300:
    return Loop2300(
        hd_segment=HdSegment(
            maintenance_type_code=coverage.maintenance_type,
            insurance_line_code=coverage.insurance_line,
            plan_coverage_description=coverage.plan_description,
            coverage_line_code=coverage.coverage_level,
        ),
        dtp_segment=[
            Loop2300DtpSegment(
                date_time_qualifier="348",
                date_time_period_format_qualifier="D8",
                date_time_period=begins,
            )
        ],
    )


def _member(
    enrollee: EnrolleeSpec, group_number: str, values: ValueFactory
) -> Loop2000:
    last, first = values.person_name()
    member_id = enrollee.member_id or values.member_id()
    eligibility = values.service_date().strftime("%Y%m%d")
    coverage_begins = values.service_date().strftime("%Y%m%d")

    return Loop2000(
        ins_segment=Loop2000InsSegment(
            # INS01: Y marks the subscriber, N a dependent of one
            member_indicator="N" if enrollee.dependent else "Y",
            individual_relationship_code=enrollee.relationship,
            maintenance_type_code=enrollee.maintenance_type,
            benefit_status_code=enrollee.benefit_status,
        ),
        ref_segment=[
            Loop2000RefSegment(
                reference_identification_qualifier="0F",
                reference_identification=member_id,
            ),
            Loop2000RefSegment(
                reference_identification_qualifier="1L",
                reference_identification=group_number,
            ),
        ],
        dtp_segment=[
            Loop2000DtpSegment(
                date_time_qualifier="356",
                date_time_period_format_qualifier="D8",
                date_time_period=eligibility,
            )
        ],
        loop_2100a=Loop2100A(
            nm1_segment=Loop2100ANm1Segment(
                entity_identifier_code="IL",
                entity_type_qualifier="1",
                name_last_or_organization_name=last,
                name_first=first,
                identification_code_qualifier="34",
                identification_code=values.tax_id(),
            ),
            n3_segment=N3Segment(address_information_1=values.address()),
            n4_segment=N4Segment(
                city_name=values.city(),
                state_province_code=values.state(),
                postal_code=values.postal_code(),
            ),
            dmg_segment=Loop2100ADmgSegment(
                date_time_period_format_qualifier="D8",
                date_time_period=(
                    values.birth_date(1, 17)
                    if enrollee.dependent
                    else values.birth_date(18)
                ).strftime("%Y%m%d"),
                gender_code=values.rng.choice(("F", "M")),
            ),
        ),
        loop_2300=[
            _coverage(coverage, coverage_begins) for coverage in enrollee.coverages
        ],
    )


def build_834(
    spec: EnrollmentSpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> BenefitEnrollmentAndMaintenance:
    """
    Builds a validated 834 enrollment transaction from a specification.

    :param spec: The sponsor, the payer, and the roster of members.
    :param seed: Seeds the values the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters.
    """
    values = ValueFactory(seed)
    created = values.service_date(30)
    group_number = values.control_number(9)

    structure: Dict = {
        "header": Header(
            st_segment=HeaderStSegment(
                transaction_set_identifier_code="834",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X220",
            ),
            bgn_segment=BgnSegment(
                transaction_set_purpose_code="00",
                transaction_set_reference_number=values.control_number(8),
                transaction_set_creation_date=created.strftime("%Y%m%d"),
                transaction_set_creation_time="1200",
                action_code="2",
            ),
        ),
        "loop_1000a": Loop1000A(
            n1_segment=Loop1000AN1Segment(
                entity_identifier_code="P5",
                name=spec.sponsor_name or values.provider_name(),
                identification_code_qualifier="FI",
                identification_code=values.tax_id(),
            )
        ),
        "loop_1000b": Loop1000B(
            n1_segment=Loop1000BN1Segment(
                entity_identifier_code="IN",
                name=spec.payer_name or values.plan_name(),
                identification_code_qualifier="FI",
                identification_code=values.tax_id(),
            )
        ),
        "loop_2000": [
            _member(enrollee, group_number, values) for enrollee in spec.enrollees
        ],
    }

    placeholder = dict(
        structure,
        footer={
            "se_segment": {
                "transaction_segment_count": 1,
                "transaction_set_control_number": control_number,
            }
        },
    )
    structure["footer"] = Footer(
        se_segment=SeSegment(
            transaction_segment_count=count_segments(placeholder),
            transaction_set_control_number=control_number,
        )
    )
    return BenefitEnrollmentAndMaintenance(**structure)


def random_enrollees(
    count: int, values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[EnrolleeSpec]:
    """
    Builds a roster mixing subscribers and dependents.

    ``dependent_rate`` is the share of records marked as a dependent, so both
    kinds of INS record appear by default.
    """
    enrollees: List[EnrolleeSpec] = []
    for _ in range(count):
        dependent = values.rng.random() < dependent_rate
        lines = values.rng.sample(("HLT", "DEN", "VIS"), values.rng.randint(1, 3))
        enrollees.append(
            EnrolleeSpec(
                coverages=tuple(CoverageSpec(insurance_line=line) for line in lines),
                dependent=dependent,
                relationship=values.rng.choice(("19", "01")) if dependent else "18",
            )
        )
    return enrollees
