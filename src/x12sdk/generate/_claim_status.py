"""
Builds 276 claim status inquiries and 277 claim status responses.

The pair shares one hierarchy, a level deeper than eligibility, which is why
one module builds both:

    HL*1**20*1     payer
    HL*2*1*21*1    information receiver
    HL*3*2*19*1    service provider
    HL*4*3*22*0    subscriber is the patient -> the claim hangs here
    HL*4*3*22*1    subscriber has a dependent
      HL*5*4*23*0  the dependent is the patient -> the claim hangs here

That is the same subscriber/dependent branch the 837 and the eligibility pair
have, and the same trap: code written against one path reports nothing on a
file that uses the other.

The inquiry carries identifying detail only; the response adds an STC status
and what was paid. One :class:`ClaimStatusSpec` therefore builds a 276 and the
277 answering it.

As elsewhere, SE01 is counted with :func:`x12sdk.support.count_segments`.
"""

from __future__ import annotations

from typing import Dict, List

from ..support import count_segments
from ..v5010.segments import SeSegment, StcSegment
from ..v5010.x12_276_005010X212 import loops as inquiry_loops
from ..v5010.x12_276_005010X212 import segments as inquiry_segments
from ..v5010.x12_276_005010X212.transaction_set import HealthCareClaimsStatusRequest
from ..v5010.x12_277_005010X212 import loops as response_loops
from ..v5010.x12_277_005010X212 import segments as response_segments
from ..v5010.x12_277_005010X212.transaction_set import HealthCareClaimsStatusResponse
from ._spec import ClaimStatusSpec, StatusPatientSpec, TrackedClaimSpec
from ._values import ValueFactory


def _finish(structure: Dict, footer_class, transaction_class, control_number: str):
    """Counts SE01 over the structure, attaches the footer, and validates."""
    placeholder = dict(
        structure,
        footer={
            "se_segment": {
                "transaction_segment_count": 1,
                "transaction_set_control_number": control_number,
            }
        },
    )
    structure["footer"] = footer_class(
        se_segment=SeSegment(
            transaction_segment_count=count_segments(placeholder),
            transaction_set_control_number=control_number,
        )
    )
    return transaction_class(**structure)


def _tracking(
    claim: TrackedClaimSpec, index: int, values: ValueFactory, service_date: str
) -> Dict:
    """The fields shared by an inquiry's and a response's 2200 loop."""
    return {
        "reference": claim.payer_claim_control_number or values.payer_claim_number(),
        "patient_control_number": claim.patient_control_number
        or values.claim_number(index),
        "charge": claim.charge,
        "service_date": service_date,
    }


def _build(
    spec: ClaimStatusSpec,
    *,
    seed: int,
    control_number: str,
    response: bool,
):
    """
    Builds a 276 or a 277 from one specification.

    The two differ only in the header codes, the trace type, and whether the
    2200 loop carries an STC status, so the traversal is written once.
    """
    loops = response_loops if response else inquiry_loops
    segments = response_segments if response else inquiry_segments
    values = ValueFactory(seed)
    created = values.service_date(30)

    payer_name = spec.payer_name or values.plan_name()
    requester_name = spec.requester_name or values.provider_name()
    provider_name = spec.provider_name or values.provider_name()

    subscribers: List = []
    hl_id = 4  # 1 payer, 2 information receiver, 3 service provider
    claim_index = 1

    for patient in spec.patients:
        subscriber_id = hl_id
        hl_id += 1
        dependent_id = None
        if patient.dependent:
            dependent_id = hl_id
            hl_id += 1

        service_date = values.service_date().strftime("%Y%m%d")
        trackers = [
            _tracking(claim, claim_index + offset, values, service_date)
            for offset, claim in enumerate(patient.claims)
        ]
        claim_index += len(patient.claims)

        last, first = values.person_name()
        subscriber = loops.Loop2000D(
            hl_segment=segments.Loop2000DHlSegment(
                hierarchical_id_number=str(subscriber_id),
                hierarchical_parent_id_number="3",
                hierarchical_level_code="22",
                hierarchical_child_code="1" if patient.dependent else "0",
            ),
            loop_2100d=loops.Loop2100D(
                nm1_segment=segments.Loop2100DNm1Segment(
                    entity_identifier_code="IL",
                    entity_type_qualifier="1",
                    name_last_or_organization_name=last,
                    name_first=first,
                    identification_code_qualifier="MI",
                    identification_code=patient.member_id or values.member_id(),
                )
            ),
            loop_2200d=None
            if patient.dependent
            else [
                _status_loop(loops, segments, patient.claims[i], tracker, response, "D")
                for i, tracker in enumerate(trackers)
            ],
        )

        if patient.dependent:
            dependent_last, dependent_first = values.person_name()
            # Drawn for both transactions even though only the 276 renders it,
            # so the two stay in step on the same seed and an inquiry and its
            # response describe the same people.
            dependent_birth = values.birth_date(1, 17).strftime("%Y%m%d")
            dependent_gender = values.rng.choice(("F", "M"))
            dependent_kwargs = dict(
                hl_segment=segments.Loop2000EHlSegment(
                    hierarchical_id_number=str(dependent_id),
                    hierarchical_parent_id_number=str(subscriber_id),
                    hierarchical_level_code="23",
                ),
                loop_2100e=loops.Loop2100E(
                    nm1_segment=segments.Loop2100ENm1Segment(
                        entity_identifier_code="QC",
                        entity_type_qualifier="1",
                        name_last_or_organization_name=dependent_last,
                        name_first=dependent_first,
                    )
                ),
                loop_2200e=[
                    _status_loop(
                        loops, segments, patient.claims[i], tracker, response, "E"
                    )
                    for i, tracker in enumerate(trackers)
                ],
            )
            if not response:
                # the 276 requires demographics on a dependent; the 277 does not
                dependent_kwargs["dmg_segment"] = segments.Loop2000DDmgSegment(
                    date_time_period_format_qualifier="D8",
                    date_time_period=dependent_birth,
                    gender_code=dependent_gender,
                )
            subscriber.loop_2000e = [loops.Loop2000E(**dependent_kwargs)]

        subscribers.append(subscriber)

    structure: Dict = {
        "header": loops.Header(
            st_segment=segments.HeaderStSegment(
                transaction_set_identifier_code="277" if response else "276",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X212",
            ),
            bht_segment=segments.HeaderBhtSegment(
                hierarchical_structure_code="0010",
                transaction_set_purpose_code="08" if response else "13",
                submitter_transactional_identifier=values.control_number(8),
                transaction_set_creation_date=created.strftime("%Y%m%d"),
                transaction_set_creation_time="1200",
            ),
        ),
        "loop_2000a": [
            loops.Loop2000A(
                hl_segment=segments.Loop2000AHlSegment(
                    hierarchical_id_number="1",
                    hierarchical_level_code="20",
                    hierarchical_child_code="1",
                ),
                loop_2100a=loops.Loop2100A(
                    nm1_segment=segments.Loop2100ANm1Segment(
                        entity_identifier_code="PR",
                        entity_type_qualifier="2",
                        name_last_or_organization_name=payer_name,
                        identification_code_qualifier="PI",
                        identification_code=values.control_number(9),
                    )
                ),
                loop_2000b=[
                    loops.Loop2000B(
                        hl_segment=segments.Loop2000BHlSegment(
                            hierarchical_id_number="2",
                            hierarchical_parent_id_number="1",
                            hierarchical_level_code="21",
                            hierarchical_child_code="1",
                        ),
                        loop_2100b=loops.Loop2100B(
                            nm1_segment=segments.Loop2100BNm1Segment(
                                entity_identifier_code="41",
                                entity_type_qualifier="2",
                                name_last_or_organization_name=requester_name,
                                identification_code_qualifier="46",
                                identification_code=values.tax_id(),
                            )
                        ),
                        loop_2000c=[
                            loops.Loop2000C(
                                hl_segment=segments.Loop2000CHlSegment(
                                    hierarchical_id_number="3",
                                    hierarchical_parent_id_number="2",
                                    hierarchical_level_code="19",
                                    hierarchical_child_code="1",
                                ),
                                loop_2100c=loops.Loop2100C(
                                    nm1_segment=segments.Loop2100CNm1Segment(
                                        entity_identifier_code="1P",
                                        entity_type_qualifier="2",
                                        name_last_or_organization_name=provider_name,
                                        identification_code_qualifier="XX",
                                        identification_code=values.npi(),
                                    )
                                ),
                                loop_2000d=subscribers,
                            )
                        ],
                    )
                ],
            )
        ],
    }
    return _finish(
        structure,
        loops.Footer,
        HealthCareClaimsStatusResponse if response else HealthCareClaimsStatusRequest,
        control_number,
    )


def _status_loop(loops, segments, claim: TrackedClaimSpec, tracker, response, level):
    """
    Builds a 2200D or 2200E loop, as an inquiry or as a response.

    Both levels reuse the ``Loop2200D`` segment classes, so only the loop
    class differs between the subscriber and dependent branches.
    """
    loop_class = getattr(loops, f"Loop2200{level}")
    kwargs = {
        "trn_segment": segments.Loop2200DTrnSegment(
            trace_type_code="2" if response else "1",
            reference_identification_1=tracker["patient_control_number"],
        ),
        "ref_segment": [
            segments.Loop2200DRefSegment(
                reference_identification_qualifier="XZ",
                reference_identification=tracker["reference"],
            )
        ],
        "dtp_segment": segments.Loop2200DDtpSegment(
            date_time_qualifier="472",
            date_time_period_format_qualifier="D8",
            date_time_period=tracker["service_date"],
        ),
    }
    if response:
        paid = claim.paid if claim.paid is not None else claim.charge
        kwargs["stc_segment"] = [
            StcSegment(
                health_care_claim_status_1=(
                    f"{claim.status_category}:{claim.status_code}"
                ),
                status_effective_date=tracker["service_date"],
                total_claim_charge_amount=claim.charge,
                claim_payment_amount=paid,
            )
        ]
    else:
        # AMT is the inquiry's statement of what was billed; the response
        # carries the amounts inside STC instead and has no AMT at all.
        kwargs["amt_segment"] = segments.Loop2200DAmtSegment(
            amount_qualifier_code="T3", monetary_amount=claim.charge
        )
    return loop_class(**kwargs)


def build_276(
    spec: ClaimStatusSpec, *, seed: int = 0, control_number: str = "0001"
) -> HealthCareClaimsStatusRequest:
    """Builds a validated 276 claim status inquiry from a specification."""
    return _build(spec, seed=seed, control_number=control_number, response=False)


def build_277(
    spec: ClaimStatusSpec, *, seed: int = 0, control_number: str = "0001"
) -> HealthCareClaimsStatusResponse:
    """
    Builds a validated 277 claim status response from a specification.

    Takes the same specification as :func:`build_276`, so an inquiry and the
    response to it can be built as a matched pair.
    """
    return _build(spec, seed=seed, control_number=control_number, response=True)


def random_status_patients(
    count: int, values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[StatusPatientSpec]:
    """
    Builds patients each tracking one claim, across both branches.

    ``dependent_rate`` is the share who are a dependent of the subscriber
    rather than the subscriber themselves.
    """
    patients: List[StatusPatientSpec] = []
    for _ in range(count):
        charge = values.amount(80, 3000)
        finalized = values.rng.random() < 0.7
        patients.append(
            StatusPatientSpec(
                claims=[
                    TrackedClaimSpec(
                        charge=charge,
                        paid=charge if finalized else values.amount(0, 50),
                        status_category="F1" if finalized else "A2",
                        status_code="1" if finalized else "20",
                    )
                ],
                dependent=values.rng.random() < dependent_rate,
            )
        )
    return patients
