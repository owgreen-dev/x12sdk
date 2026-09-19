"""
Builds 837P professional claim transactions from a specification.

The 837 arranges its content as a hierarchy of HL segments: a billing provider
at level 20, the subscribers it bills for at level 22, and, only where the
patient is not the subscriber, a dependent at level 23. Each HL names its own
id and its parent's, and the parent declares whether it has children, so the
numbering is assigned here in one pass rather than left to the caller.

As with the 835, SE01 must equal every segment from ST through SE, and it is
counted with :func:`x12sdk.support.count_segments` rather than guessed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Sequence

from ..support import count_segments
from ..v5010.segments import (
    ClmSegment,
    DmgSegment,
    HiSegment,
    N3Segment,
    N4Segment,
    SeSegment,
    Sv1Segment,
)
from ..v5010.x12_837_005010X222A2.loops import (
    Footer,
    Header,
    Loop1000A,
    Loop1000B,
    Loop2000A,
    Loop2000B,
    Loop2000C,
    Loop2010Aa,
    Loop2010Ba,
    Loop2010Bb,
    Loop2010Ca,
    Loop2300,
    Loop2400,
)
from ..v5010.x12_837_005010X222A2.segments import (
    HeaderBhtSegment,
    HeaderStSegment,
    Loop1000ANm1Segment,
    Loop1000APerSegment,
    Loop1000BNm1Segment,
    Loop2000AHlSegment,
    Loop2000BHlSegment,
    Loop2000BSbrSegment,
    Loop2000CHlSegment,
    Loop2000CPatSegment,
    Loop2010AaNm1Segment,
    Loop2010AaRefSegment,
    Loop2010BaNm1Segment,
    Loop2010BbNm1Segment,
    Loop2010CaNm1Segment,
    Loop2300DtpSegment,
    Loop2400DtpSegment,
)
from ..v5010.x12_837_005010X222A2.transaction_set import HealthCareClaimProfessional
from ._spec import ClaimSpec, PatientSpec, ServiceLineSpec, SubmissionSpec
from ._values import ValueFactory

#: CLM05: place of service 11 (office), qualifier B, frequency 1 (original).
_SERVICE_LOCATION = "11:B:1"


def _service_line(
    line: ServiceLineSpec, number: int, service_date: str, values: ValueFactory
) -> Loop2400:
    procedure = line.procedure or values.procedure()
    return Loop2400(
        lx_segment={"assigned_number": str(number)},
        sv1_segment=Sv1Segment(
            product_service_id_qualifier=f"HC:{procedure}",
            line_item_charge_amount=line.charge,
            unit_basis_measurement_code="UN",
            service_unit_count=Decimal(line.units),
            # points at the single HI diagnosis on the claim
            composite_diagnosis_code_pointer="1",
        ),
        dtp_segment=[
            Loop2400DtpSegment(
                date_time_qualifier="472",
                date_time_period_format_qualifier="D8",
                date_time_period=service_date,
            )
        ],
    )


def _claim(claim: ClaimSpec, index: int, values: ValueFactory) -> Loop2300:
    service_date = values.service_date().strftime("%Y%m%d")
    return Loop2300(
        clm_segment=ClmSegment(
            patient_control_number=claim.patient_control_number
            or values.claim_number(index),
            total_claim_charge_amount=claim.charge,
            health_care_service_location_information=_SERVICE_LOCATION,
            provider_or_supplier_signature_indicator="Y",
            provider_accept_assignment_code="A",
            benefit_assignment_certification_indicator="Y",
            release_of_information_code="Y",
        ),
        dtp_segment=[
            Loop2300DtpSegment(
                date_time_qualifier="431",
                date_time_period_format_qualifier="D8",
                date_time_period=service_date,
            )
        ],
        # HI components are a list, unlike SV101; the serializer joins them
        hi_segment=[HiSegment(health_care_code_1=["BK", values.diagnosis()])],
        loop_2400=[
            _service_line(line, number, service_date, values)
            for number, line in enumerate(claim.lines, start=1)
        ],
    )


def _subscriber_name(values: ValueFactory) -> Loop2010Ba:
    last, first = values.person_name()
    return Loop2010Ba(
        nm1_segment=Loop2010BaNm1Segment(
            entity_identifier_code="IL",
            entity_type_qualifier="1",
            name_last_or_organization_name=last,
            name_first=first,
            identification_code_qualifier="MI",
            identification_code=values.member_id(),
        ),
        n3_segment=N3Segment(address_information_1=values.address()),
        n4_segment=N4Segment(
            city_name=values.city(),
            state_province_code=values.state(),
            postal_code=values.postal_code(),
        ),
        dmg_segment=DmgSegment(
            date_time_period_format_qualifier="D8",
            date_time_period=values.birth_date(18).strftime("%Y%m%d"),
            gender_code=values.rng.choice(("F", "M")),
        ),
    )


def _patient_name(values: ValueFactory) -> Loop2010Ca:
    last, first = values.person_name()
    return Loop2010Ca(
        nm1_segment=Loop2010CaNm1Segment(
            entity_identifier_code="QC",
            entity_type_qualifier="1",
            name_last_or_organization_name=last,
            name_first=first,
        ),
        n3_segment=N3Segment(address_information_1=values.address()),
        n4_segment=N4Segment(
            city_name=values.city(),
            state_province_code=values.state(),
            postal_code=values.postal_code(),
        ),
        dmg_segment=DmgSegment(
            date_time_period_format_qualifier="D8",
            date_time_period=values.birth_date(1, 17).strftime("%Y%m%d"),
            gender_code=values.rng.choice(("F", "M")),
        ),
    )


def _payer_name(spec: SubmissionSpec, values: ValueFactory) -> Loop2010Bb:
    return Loop2010Bb(
        nm1_segment=Loop2010BbNm1Segment(
            entity_identifier_code="PR",
            entity_type_qualifier="2",
            name_last_or_organization_name=spec.payer_name or values.plan_name(),
            identification_code_qualifier="PI",
            identification_code=values.control_number(6),
        ),
        n3_segment=N3Segment(address_information_1=values.address()),
        n4_segment=N4Segment(
            city_name=values.city(),
            state_province_code=values.state(),
            postal_code=values.postal_code(),
        ),
    )


def _subscriber(
    patient: PatientSpec,
    hl_id: int,
    next_hl_id: int,
    claim_index: int,
    spec: SubmissionSpec,
    values: ValueFactory,
) -> Loop2000B:
    """
    Builds one subscriber, and the dependent beneath them where there is one.

    ``hierarchical_child_code`` is "1" only when a dependent follows, which is
    also what decides whether the claims hang off this loop or the 2000C.
    """
    claims = [
        _claim(claim, claim_index + offset, values)
        for offset, claim in enumerate(patient.claims)
    ]

    loop = Loop2000B(
        hl_segment=Loop2000BHlSegment(
            hierarchical_id_number=str(hl_id),
            hierarchical_parent_id_number="1",
            hierarchical_level_code="22",
            hierarchical_child_code="1" if patient.dependent else "0",
        ),
        sbr_segment=Loop2000BSbrSegment(
            payer_responsibility_code="P",
            # SBR02 is the subscriber's relationship to themselves, and is
            # present only when the subscriber is also the patient.
            individual_relationship_code=None if patient.dependent else "18",
            claim_filing_indicator_code="CH",
        ),
        loop_2010ba=_subscriber_name(values),
        loop_2010bb=_payer_name(spec, values),
        loop_2300=None if patient.dependent else claims,
    )

    if patient.dependent:
        loop.loop_2000c = [
            Loop2000C(
                hl_segment=Loop2000CHlSegment(
                    hierarchical_id_number=str(next_hl_id),
                    hierarchical_parent_id_number=str(hl_id),
                    hierarchical_level_code="23",
                    hierarchical_child_code="0",
                ),
                pat_segment=Loop2000CPatSegment(
                    individual_relationship_code=patient.relationship
                ),
                loop_2010ca=_patient_name(values),
                loop_2300=claims,
            )
        ]
    return loop


def build_837p(
    spec: SubmissionSpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> HealthCareClaimProfessional:
    """
    Builds a validated 837P transaction model from a specification.

    :param spec: What the submission should contain.
    :param seed: Seeds the values that the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters, per the standard.
    :return: A validated ``HealthCareClaimProfessional``.
    """
    values = ValueFactory(seed)
    provider_name = spec.billing_provider_name or values.provider_name()
    submitter_name = spec.submitter_name or provider_name
    tax_id = values.tax_id()
    created = values.service_date(30)

    subscribers: List[Loop2000B] = []
    hl_id = 2
    claim_index = 1
    for patient in spec.patients:
        subscribers.append(
            _subscriber(patient, hl_id, hl_id + 1, claim_index, spec, values)
        )
        claim_index += len(patient.claims)
        hl_id += 2 if patient.dependent else 1

    structure: Dict = {
        "header": Header(
            st_segment=HeaderStSegment(
                transaction_set_identifier_code="837",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X222A2",
            ),
            bht_segment=HeaderBhtSegment(
                hierarchical_structure_code="0019",
                transaction_set_purpose_code="00",
                submitter_transactional_identifier=values.control_number(9),
                transaction_set_creation_date=created.strftime("%Y%m%d"),
                transaction_set_creation_time="1200",
                transaction_type_code="CH",
            ),
        ),
        "loop_1000a": Loop1000A(
            nm1_segment=Loop1000ANm1Segment(
                entity_identifier_code="41",
                entity_type_qualifier="2",
                name_last_or_organization_name=submitter_name,
                identification_code_qualifier="46",
                identification_code=tax_id,
            ),
            per_segment=[
                Loop1000APerSegment(
                    contact_function_code="IC",
                    name="SYNTHETIC CONTACT",
                    communication_number_qualifier_1="TE",
                    communication_number_1=values.phone_number(),
                )
            ],
        ),
        "loop_1000b": Loop1000B(
            nm1_segment=Loop1000BNm1Segment(
                entity_identifier_code="40",
                entity_type_qualifier="2",
                name_last_or_organization_name=spec.payer_name or values.plan_name(),
                identification_code_qualifier="46",
                identification_code=values.control_number(6),
            ),
        ),
        "loop_2000a": [
            Loop2000A(
                hl_segment=Loop2000AHlSegment(
                    hierarchical_id_number="1",
                    hierarchical_level_code="20",
                    hierarchical_child_code="1",
                ),
                loop_2010aa=Loop2010Aa(
                    nm1_segment=Loop2010AaNm1Segment(
                        entity_identifier_code="85",
                        entity_type_qualifier="2",
                        name_last_or_organization_name=provider_name,
                        identification_code_qualifier="XX",
                        identification_code=values.npi(),
                    ),
                    n3_segment=N3Segment(address_information_1=values.address()),
                    n4_segment=N4Segment(
                        city_name=values.city(),
                        state_province_code=values.state(),
                        postal_code=values.postal_code(),
                    ),
                    ref_segment=[
                        Loop2010AaRefSegment(
                            reference_identification_qualifier="EI",
                            reference_identification=tax_id,
                        )
                    ],
                ),
                loop_2000b=subscribers,
            )
        ],
    }

    # SE01 counts every segment from ST through SE inclusive. Count the
    # structure with a stand-in footer, then attach the real one.
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

    return HealthCareClaimProfessional(**structure)


def random_patients(
    count: int, values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[PatientSpec]:
    """
    Builds plausible patients carrying one claim each.

    ``dependent_rate`` is the share of patients who are a dependent of the
    subscriber rather than the subscriber themselves. Both branches appear by
    default, because code that walks an 837 tends to handle only one of them.
    """
    patients: List[PatientSpec] = []
    for _ in range(count):
        charge = values.amount(80, 3000)
        line_charges = values.split(charge, values.rng.randint(1, 3))
        patients.append(
            PatientSpec(
                claims=[
                    ClaimSpec(
                        charge=charge,
                        lines=[ServiceLineSpec(charge=c) for c in line_charges],
                    )
                ],
                dependent=values.rng.random() < dependent_rate,
            )
        )
    return patients


def claim_specs_to_patients(
    claims: Sequence[ClaimSpec], values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[PatientSpec]:
    """Puts one claim on each patient, splitting them across both branches."""
    return [
        PatientSpec(claims=[claim], dependent=values.rng.random() < dependent_rate)
        for claim in claims
    ]
