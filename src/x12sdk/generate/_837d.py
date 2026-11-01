"""
Builds 837D dental claim transactions from a specification.

The hierarchy is the 837P's: a billing provider at HL level 20, subscribers at
22, and a dependent at 23 only where the patient is not the subscriber. What
changes is the service line. A dental line is an SV3 carrying a CDT code under
the ``AD`` qualifier, and when the procedure is done to a tooth, a TOO segment
naming the tooth and the surfaces treated. An exam or a cleaning has no tooth,
so not every line carries one.

The claim's service date sits on the claim (DTP*472 in loop 2300), as it does
when every line was done on the same visit.

SE01 is counted with :func:`x12sdk.support.count_segments`, as elsewhere.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from ..support import count_segments
from ..v5010.segments import (
    ClmSegment,
    DmgSegment,
    N3Segment,
    N4Segment,
    SeSegment,
    Sv3Segment,
)
from ..v5010.x12_837_005010X224A2.loops import (
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
from ..v5010.x12_837_005010X224A2.segments import (
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
    Loop2400TooSegment,
)
from ..v5010.x12_837_005010X224A2.transaction_set import HealthCareClaimDental
from ._spec import ClaimSpec, PatientSpec, ServiceLineSpec, SubmissionSpec
from ._values import ValueFactory

#: CLM05: place of service 11 (office), qualifier B, frequency 1 (original).
_SERVICE_LOCATION = "11:B:1"


def _service_line(line: ServiceLineSpec, number: int, values: ValueFactory) -> Loop2400:
    """
    One SV3 line. A line with no procedure gets an invented one, together with
    the tooth and surfaces that procedure implies; a line that names its
    procedure keeps exactly the tooth and surfaces it was given.
    """
    if line.procedure:
        procedure, tooth, surfaces = line.procedure, line.tooth, tuple(line.surfaces)
    else:
        procedure, tooth, surfaces = values.dental_procedure()
        if line.tooth:
            tooth, surfaces = line.tooth, tuple(line.surfaces)

    return Loop2400(
        lx_segment={"assigned_number": str(number)},
        sv3_segment=Sv3Segment(
            composite_medical_procedure_identifier=f"AD:{procedure}",
            line_item_charge_amount=line.charge,
            procedure_count=Decimal(line.units),
        ),
        too_segment=[
            Loop2400TooSegment(
                code_list_qualifier_code="JP",
                tooth_number=tooth,
                tooth_surface=list(surfaces) or None,
            )
        ]
        if tooth
        else None,
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
                date_time_qualifier="472",
                date_time_period_format_qualifier="D8",
                date_time_period=service_date,
            )
        ],
        loop_2400=[
            _service_line(line, number, values)
            for number, line in enumerate(claim.lines, start=1)
        ],
    )


def _person(nm1_class, entity_code: str, values: ValueFactory, *, member: bool):
    last, first = values.person_name()
    fields: Dict = {
        "entity_identifier_code": entity_code,
        "entity_type_qualifier": "1",
        "name_last_or_organization_name": last,
        "name_first": first,
    }
    if member:
        fields["identification_code_qualifier"] = "MI"
        fields["identification_code"] = values.member_id()
    return nm1_class(**fields)


def _address(values: ValueFactory) -> Dict:
    return {
        "n3_segment": N3Segment(address_information_1=values.address()),
        "n4_segment": N4Segment(
            city_name=values.city(),
            state_province_code=values.state(),
            postal_code=values.postal_code(),
        ),
    }


def _demographics(values: ValueFactory, *, dependent: bool) -> DmgSegment:
    birth = values.birth_date(1, 17) if dependent else values.birth_date(18)
    return DmgSegment(
        date_time_period_format_qualifier="D8",
        date_time_period=birth.strftime("%Y%m%d"),
        gender_code=values.rng.choice(("F", "M")),
    )


def _subscriber(
    patient: PatientSpec,
    hl_id: int,
    next_hl_id: int,
    claim_index: int,
    payer_name: str,
    payer_id: str,
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
            # SBR02 is present only when the subscriber is also the patient
            individual_relationship_code=None if patient.dependent else "18",
            claim_filing_indicator_code="CI",
        ),
        loop_2010ba=Loop2010Ba(
            nm1_segment=_person(Loop2010BaNm1Segment, "IL", values, member=True),
            **_address(values),
            dmg_segment=_demographics(values, dependent=False),
        ),
        loop_2010bb=Loop2010Bb(
            nm1_segment=Loop2010BbNm1Segment(
                entity_identifier_code="PR",
                entity_type_qualifier="2",
                name_last_or_organization_name=payer_name,
                identification_code_qualifier="PI",
                identification_code=payer_id,
            ),
        ),
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
                loop_2010ca=Loop2010Ca(
                    nm1_segment=_person(
                        Loop2010CaNm1Segment, "QC", values, member=False
                    ),
                    **_address(values),
                    dmg_segment=_demographics(values, dependent=True),
                ),
                loop_2300=claims,
            )
        ]
    return loop


def build_837d(
    spec: SubmissionSpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> HealthCareClaimDental:
    """
    Builds a validated 837D transaction model from a specification.

    :param spec: What the submission should contain. A line's ``tooth`` and
        ``surfaces`` become its TOO segment.
    :param seed: Seeds the values that the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters, per the standard.
    :return: A validated ``HealthCareClaimDental``.
    """
    values = ValueFactory(seed)
    provider_name = spec.billing_provider_name or values.dental_provider_name()
    submitter_name = spec.submitter_name or provider_name
    tax_id = values.tax_id()
    created = values.service_date(30)
    # one payer receives the whole file, so 1000B and every 2010BB name it
    payer_name = spec.payer_name or values.plan_name()
    payer_id = values.control_number(6)

    subscribers: List[Loop2000B] = []
    hl_id = 2
    claim_index = 1
    for patient in spec.patients:
        subscribers.append(
            _subscriber(
                patient, hl_id, hl_id + 1, claim_index, payer_name, payer_id, values
            )
        )
        claim_index += len(patient.claims)
        hl_id += 2 if patient.dependent else 1

    structure: Dict = {
        "header": Header(
            st_segment=HeaderStSegment(
                transaction_set_identifier_code="837",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X224A2",
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
                name_last_or_organization_name=payer_name,
                identification_code_qualifier="46",
                identification_code=payer_id,
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
                    **_address(values),
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

    return HealthCareClaimDental(**structure)


def random_dental_lines(values: ValueFactory, count: int) -> List[ServiceLineSpec]:
    """
    Invents ``count`` dental lines, each with its procedure, and the tooth and
    surfaces that procedure implies, already decided.
    """
    lines: List[ServiceLineSpec] = []
    for _ in range(count):
        procedure, tooth, surfaces = values.dental_procedure()
        lines.append(
            ServiceLineSpec(
                charge=values.dental_fee(procedure),
                procedure=procedure,
                tooth=tooth,
                surfaces=surfaces,
            )
        )
    return lines


def random_dental_patients(
    count: int, values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[PatientSpec]:
    """
    Builds plausible dental patients carrying one claim each.

    A visit is one to four lines, so files mix lines with a tooth, lines with
    a tooth and surfaces, and lines with neither. ``dependent_rate`` is the
    share of patients who are a dependent rather than the subscriber.
    """
    patients: List[PatientSpec] = []
    for _ in range(count):
        lines = random_dental_lines(values, values.rng.randint(1, 4))
        charge = sum((line.charge for line in lines), Decimal("0.00"))
        patients.append(
            PatientSpec(
                claims=[ClaimSpec(charge=charge, lines=lines)],
                dependent=values.rng.random() < dependent_rate,
            )
        )
    return patients
