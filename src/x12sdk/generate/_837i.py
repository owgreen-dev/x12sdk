"""
Builds 837I institutional claim transactions from a specification.

The institutional claim sits on the same hierarchy as the professional one,
and carries the same subscriber/dependent branch:

    HL*1**20*1     billing provider
    HL*2*1*22*0    subscriber is the patient -> the claim hangs here
    HL*2*1*22*1    subscriber has a dependent
      HL*3*2*23*0  the dependent is the patient -> the claim hangs here

What differs is the claim itself. An institutional claim reports a facility
type rather than a place of service, carries admission and patient status in
CL1, states a statement date, and bills by revenue code in SV2 rather than by
procedure in SV1. The specification types are shared with the 837P: a
ServiceLineSpec's procedure becomes the SV2 procedure composite.

Segments are supplied as dicts, which the models accept exactly as the parser
supplies them, so the builder depends on loop classes only.

As elsewhere, SE01 is counted with :func:`x12sdk.support.count_segments`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from ..support import count_segments
from ..v5010.x12_837_005010X223A3.loops import (
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
from ..v5010.x12_837_005010X223A3.transaction_set import HealthCareClaimInstitutional
from ._spec import ClaimSpec, PatientSpec, ServiceLineSpec, SubmissionSpec
from ._values import ValueFactory

#: CLM05: facility type 13 (hospital outpatient), qualifier A, frequency 1.
_SERVICE_LOCATION = "13:A:1"
#: SV201: a revenue code for a clinic visit line.
_REVENUE_CODE = "0510"


def _address(values: ValueFactory) -> Dict:
    return {
        "n3_segment": {"address_information_1": values.address()},
        "n4_segment": {
            "city_name": values.city(),
            "state_province_code": values.state(),
            "postal_code": values.postal_code(),
        },
    }


def _demographics(values: ValueFactory, *, dependent: bool) -> Dict:
    birth = values.birth_date(1, 17) if dependent else values.birth_date(18)
    return {
        "date_time_period_format_qualifier": "D8",
        "date_time_period": birth.strftime("%Y%m%d"),
        "gender_code": values.rng.choice(("F", "M")),
    }


def _service_line(line: ServiceLineSpec, number: int, values: ValueFactory) -> Loop2400:
    procedure = line.procedure or values.procedure()
    return Loop2400(
        lx_segment={"assigned_number": str(number)},
        sv2_segment={
            "service_line_revenue_code": _REVENUE_CODE,
            "composite_medical_procedure_identifier": f"HC:{procedure}",
            "line_item_charge_amount": line.charge,
            "measurement_code": "UN",
            "service_unit_count": Decimal(line.units),
        },
    )


def _claim(claim: ClaimSpec, index: int, values: ValueFactory) -> Loop2300:
    statement_date = values.service_date().strftime("%Y%m%d")
    return Loop2300(
        clm_segment={
            "patient_control_number": claim.patient_control_number
            or values.claim_number(index),
            "total_claim_charge_amount": claim.charge,
            "health_care_service_location_information": _SERVICE_LOCATION,
            "provider_or_supplier_signature_indicator": "Y",
            "provider_accept_assignment_code": "A",
            "benefit_assignment_certification_indicator": "Y",
            "release_of_information_code": "Y",
        },
        dtp_segment=[
            {
                # 434: statement dates, the institutional claim's service period
                "date_time_qualifier": "434",
                "date_time_period_format_qualifier": "D8",
                "date_time_period": statement_date,
            }
        ],
        cl1_segment={
            "admission_type_code": "3",  # elective
            "patient_status_code": "01",  # discharged home
        },
        hi_segment=[{"health_care_code_1": ["BK", values.diagnosis()]}],
        loop_2400=[
            _service_line(line, number, values)
            for number, line in enumerate(claim.lines, start=1)
        ],
    )


def _subscriber(
    patient: PatientSpec,
    hl_id: int,
    next_hl_id: int,
    claim_index: int,
    spec: SubmissionSpec,
    values: ValueFactory,
) -> Loop2000B:
    claims = [
        _claim(claim, claim_index + offset, values)
        for offset, claim in enumerate(patient.claims)
    ]
    last, first = values.person_name()

    loop = Loop2000B(
        hl_segment={
            "hierarchical_id_number": str(hl_id),
            "hierarchical_parent_id_number": "1",
            "hierarchical_level_code": "22",
            "hierarchical_child_code": "1" if patient.dependent else "0",
        },
        sbr_segment={
            "payer_responsibility_code": "P",
            # SBR02 is present only when the subscriber is also the patient
            "individual_relationship_code": None if patient.dependent else "18",
            "claim_filing_indicator_code": "CI",
        },
        loop_2010ba=Loop2010Ba(
            nm1_segment={
                "entity_identifier_code": "IL",
                "entity_type_qualifier": "1",
                "name_last_or_organization_name": last,
                "name_first": first,
                "identification_code_qualifier": "MI",
                "identification_code": values.member_id(),
            },
            dmg_segment=_demographics(values, dependent=False),
            **_address(values),
        ),
        loop_2010bb=Loop2010Bb(
            nm1_segment={
                "entity_identifier_code": "PR",
                "entity_type_qualifier": "2",
                "name_last_or_organization_name": spec.payer_name or values.plan_name(),
                "identification_code_qualifier": "PI",
                "identification_code": values.control_number(6),
            },
            **_address(values),
        ),
        loop_2300=None if patient.dependent else claims,
    )

    if patient.dependent:
        dependent_last, dependent_first = values.person_name()
        loop.loop_2000c = [
            Loop2000C(
                hl_segment={
                    "hierarchical_id_number": str(next_hl_id),
                    "hierarchical_parent_id_number": str(hl_id),
                    "hierarchical_level_code": "23",
                    "hierarchical_child_code": "0",
                },
                pat_segment={"individual_relationship_code": patient.relationship},
                loop_2010ca=Loop2010Ca(
                    nm1_segment={
                        "entity_identifier_code": "QC",
                        "entity_type_qualifier": "1",
                        "name_last_or_organization_name": dependent_last,
                        "name_first": dependent_first,
                    },
                    dmg_segment=_demographics(values, dependent=True),
                    **_address(values),
                ),
                loop_2300=claims,
            )
        ]
    return loop


def build_837i(
    spec: SubmissionSpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> HealthCareClaimInstitutional:
    """
    Builds a validated 837I transaction model from a specification.

    :param spec: What the submission should contain.
    :param seed: Seeds the values that the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters, per the standard.
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
            st_segment={
                "transaction_set_identifier_code": "837",
                "transaction_set_control_number": control_number,
                "implementation_convention_reference": "005010X223A3",
            },
            bht_segment={
                "hierarchical_structure_code": "0019",
                "transaction_set_purpose_code": "00",
                "submitter_transactional_identifier": values.control_number(9),
                "transaction_set_creation_date": created.strftime("%Y%m%d"),
                "transaction_set_creation_time": "1200",
                "transaction_type_code": "CH",
            },
        ),
        "loop_1000a": Loop1000A(
            nm1_segment={
                "entity_identifier_code": "41",
                "entity_type_qualifier": "2",
                "name_last_or_organization_name": submitter_name,
                "identification_code_qualifier": "46",
                "identification_code": tax_id,
            },
            per_segment=[
                {
                    "contact_function_code": "IC",
                    "name": "SYNTHETIC CONTACT",
                    "communication_number_qualifier_1": "TE",
                    "communication_number_1": values.phone_number(),
                }
            ],
        ),
        "loop_1000b": Loop1000B(
            nm1_segment={
                "entity_identifier_code": "40",
                "entity_type_qualifier": "2",
                "name_last_or_organization_name": spec.payer_name or values.plan_name(),
                "identification_code_qualifier": "46",
                "identification_code": values.control_number(6),
            },
        ),
        "loop_2000a": [
            Loop2000A(
                hl_segment={
                    "hierarchical_id_number": "1",
                    "hierarchical_level_code": "20",
                    "hierarchical_child_code": "1",
                },
                loop_2010aa=Loop2010Aa(
                    nm1_segment={
                        "entity_identifier_code": "85",
                        "entity_type_qualifier": "2",
                        "name_last_or_organization_name": provider_name,
                        "identification_code_qualifier": "XX",
                        "identification_code": values.npi(),
                    },
                    # a single REF here, where the 837P carries a list
                    ref_segment={
                        "reference_identification_qualifier": "EI",
                        "reference_identification": tax_id,
                    },
                    **_address(values),
                ),
                loop_2000b=subscribers,
            )
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
        se_segment={
            "transaction_segment_count": count_segments(placeholder),
            "transaction_set_control_number": control_number,
        }
    )
    return HealthCareClaimInstitutional(**structure)
