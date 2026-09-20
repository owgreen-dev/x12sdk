"""
Builds 270 eligibility inquiries and 271 eligibility responses.

Both sit on the same four-level hierarchy, which is why one module builds
them: an information source at level 20 (the payer), an information receiver
at level 21 (the provider asking), a subscriber at level 22, and, only where
the patient is not the subscriber, a dependent at level 23.

    HL*1**20*1     payer
    HL*2*1*21*1    provider
    HL*3*2*22*0    subscriber is the patient -> the question hangs here
    HL*3*2*22*1    subscriber has a dependent
      HL*4*3*23*0  the dependent is the patient -> the question hangs here

That is the same branch the 837 has, and the same trap: code written against
one path reports nothing on a file that uses the other.

As elsewhere, SE01 is counted with :func:`x12sdk.support.count_segments`
rather than guessed.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from ..support import count_segments
from ..v5010.segments import DmgSegment, EbSegment, N3Segment, N4Segment, SeSegment
from ..v5010.x12_270_005010X279A1 import loops as inquiry_loops
from ..v5010.x12_270_005010X279A1 import segments as inquiry_segments
from ..v5010.x12_270_005010X279A1.transaction_set import EligibilityInquiry
from ..v5010.x12_271_005010X279A1 import loops as response_loops
from ..v5010.x12_271_005010X279A1 import segments as response_segments
from ..v5010.x12_271_005010X279A1.transaction_set import EligibilityBenefit
from ._spec import BenefitSpec, EligibilitySpec, MemberSpec
from ._values import ValueFactory


def _address(values: ValueFactory) -> Tuple[N3Segment, N4Segment]:
    return (
        N3Segment(address_information_1=values.address()),
        N4Segment(
            city_name=values.city(),
            state_province_code=values.state(),
            postal_code=values.postal_code(),
        ),
    )


def _demographics(values: ValueFactory, *, dependent: bool) -> DmgSegment:
    birth = values.birth_date(1, 17) if dependent else values.birth_date(18)
    return DmgSegment(
        date_time_period_format_qualifier="D8",
        date_time_period=birth.strftime("%Y%m%d"),
        gender_code=values.rng.choice(("F", "M")),
    )


def _hierarchy(members: Sequence[MemberSpec]) -> List[Dict]:
    """
    Assigns HL ids over the members, and says where each one's payload goes.

    Returns one entry per member carrying its subscriber id, its dependent id
    where it has one, and whether the subscriber declares a child.
    """
    plan: List[Dict] = []
    next_id = 3  # 1 is the payer, 2 the provider
    for member in members:
        subscriber_id = next_id
        next_id += 1
        dependent_id = None
        if member.dependent:
            dependent_id = next_id
            next_id += 1
        plan.append(
            {
                "member": member,
                "subscriber_id": str(subscriber_id),
                "dependent_id": str(dependent_id) if dependent_id else None,
            }
        )
    return plan


# --- 270 eligibility inquiry ------------------------------------------------


def build_270(
    spec: EligibilitySpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> EligibilityInquiry:
    """
    Builds a validated 270 eligibility inquiry from a specification.

    :param spec: Who is asking, of whom, and about which members.
    :param seed: Seeds the values the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters.

    Every benefit in the specification is rendered. EQ repeats within loop
    2110, so an inquiry can ask about several service types at once.
    """
    values = ValueFactory(seed)
    created = values.service_date(30)
    provider_name = spec.provider_name or values.provider_name()
    payer_name = spec.payer_name or values.plan_name()

    subscribers: List[inquiry_loops.Loop2000C] = []
    for entry in _hierarchy(spec.members):
        member: MemberSpec = entry["member"]
        eligibility = [
            inquiry_loops.Loop2110C(
                eq_segment=inquiry_segments.Loop2110EqSegment(
                    # EQ01 itself also repeats, so it is a list even for one
                    # service type
                    service_type_code=[benefit.service_type]
                )
            )
            for benefit in member.benefits
        ]
        n3_segment, n4_segment = _address(values)
        subscriber_name = inquiry_loops.Loop2100C(
            nm1_segment=inquiry_segments.Loop2100CNm1Segment(
                entity_identifier_code="IL",
                entity_type_qualifier="1",
                **_person(values, member, dependent=False),
            ),
            n3_segment=n3_segment,
            n4_segment=n4_segment,
            dmg_segment=_demographics(values, dependent=False),
            dtp_segment=inquiry_segments.Loop2100DtpSegment(
                date_time_qualifier="291",
                date_time_period_format_qualifier="D8",
                date_time_period=created.strftime("%Y%m%d"),
            ),
            loop_2110c=None if member.dependent else eligibility,
        )

        loop_2000c = inquiry_loops.Loop2000C(
            hl_segment=inquiry_segments.Loop2000CHlSegment(
                hierarchical_id_number=entry["subscriber_id"],
                hierarchical_parent_id_number="2",
                hierarchical_level_code="22",
                hierarchical_child_code="1" if member.dependent else "0",
            ),
            trn_segment=[_trace(values)],
            loop_2100c=subscriber_name,
        )

        if member.dependent:
            dependent_n3, dependent_n4 = _address(values)
            last, first = values.person_name()
            loop_2000c.loop_2000d = [
                inquiry_loops.Loop2000D(
                    hl_segment=inquiry_segments.Loop2000DHlSegment(
                        hierarchical_id_number=entry["dependent_id"],
                        hierarchical_parent_id_number=entry["subscriber_id"],
                        hierarchical_level_code="23",
                        hierarchical_child_code="0",
                    ),
                    loop_2100d=inquiry_loops.Loop2100D(
                        nm1_segment=inquiry_segments.Loop2100DNm1Segment(
                            entity_identifier_code="03",
                            entity_type_qualifier="1",
                            name_last_or_organization_name=last,
                            name_first=first,
                        ),
                        n3_segment=dependent_n3,
                        n4_segment=dependent_n4,
                        dmg_segment=_demographics(values, dependent=True),
                        dtp_segment=inquiry_segments.Loop2100DtpSegment(
                            date_time_qualifier="291",
                            date_time_period_format_qualifier="D8",
                            date_time_period=created.strftime("%Y%m%d"),
                        ),
                        loop_2110d=[
                            inquiry_loops.Loop2110D(
                                eq_segment=inquiry_segments.Loop2110EqSegment(
                                    service_type_code=[benefit.service_type]
                                )
                            )
                            for benefit in member.benefits
                        ],
                    ),
                )
            ]
        subscribers.append(loop_2000c)

    structure: Dict = {
        "header": inquiry_loops.Header(
            st_segment=inquiry_segments.HeaderStSegment(
                transaction_set_identifier_code="270",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X279",
            ),
            bht_segment=inquiry_segments.HeaderBhtSegment(
                hierarchical_structure_code="0022",
                transaction_set_purpose_code="01",
                submitter_transactional_identifier=values.control_number(8),
                transaction_set_creation_date=created.strftime("%Y%m%d"),
                transaction_set_creation_time="1200",
            ),
        ),
        "loop_2000a": [
            inquiry_loops.Loop2000A(
                hl_segment=inquiry_segments.Loop2000AHlSegment(
                    hierarchical_id_number="1",
                    hierarchical_level_code="20",
                    hierarchical_child_code="1",
                ),
                loop_2100a=inquiry_loops.Loop2100A(
                    nm1_segment=inquiry_segments.Loop2100ANm1Segment(
                        entity_identifier_code="PR",
                        entity_type_qualifier="2",
                        name_last_or_organization_name=payer_name,
                        identification_code_qualifier="PI",
                        identification_code=values.control_number(9),
                    )
                ),
                loop_2000b=[
                    inquiry_loops.Loop2000B(
                        hl_segment=inquiry_segments.Loop2000BHlSegment(
                            hierarchical_id_number="2",
                            hierarchical_parent_id_number="1",
                            hierarchical_level_code="21",
                            hierarchical_child_code="1",
                        ),
                        loop_2100b=inquiry_loops.Loop2100B(
                            nm1_segment=inquiry_segments.Loop2100BNm1Segment(
                                entity_identifier_code="1P",
                                entity_type_qualifier="2",
                                name_last_or_organization_name=provider_name,
                                identification_code_qualifier="XX",
                                identification_code=values.npi(),
                            )
                        ),
                        loop_2000c=subscribers,
                    )
                ],
            )
        ],
    }
    return _finish(structure, inquiry_loops.Footer, EligibilityInquiry, control_number)


# --- 271 eligibility response -----------------------------------------------


def build_271(
    spec: EligibilitySpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> EligibilityBenefit:
    """
    Builds a validated 271 eligibility response from a specification.

    The 271 carries a list of EB segments per member, so every benefit in the
    specification appears. This is the asymmetry that makes the 270 raise.
    """
    values = ValueFactory(seed)
    created = values.service_date(30)
    provider_name = spec.provider_name or values.provider_name()
    payer_name = spec.payer_name or values.plan_name()

    subscribers: List[response_loops.Loop2000C] = []
    for entry in _hierarchy(spec.members):
        member: MemberSpec = entry["member"]
        benefits = [_eb(benefit) for benefit in member.benefits]
        n3_segment, n4_segment = _address(values)

        loop_2000c = response_loops.Loop2000C(
            hl_segment=response_segments.Loop2000CHlSegment(
                hierarchical_id_number=entry["subscriber_id"],
                hierarchical_parent_id_number="2",
                hierarchical_level_code="22",
                hierarchical_child_code="1" if member.dependent else "0",
            ),
            trn_segment=[_trace(values)],
            loop_2100c=response_loops.Loop2100C(
                nm1_segment=response_segments.Loop2100CNm1Segment(
                    entity_identifier_code="IL",
                    entity_type_qualifier="1",
                    **_person(values, member, dependent=False),
                ),
                n3_segment=n3_segment,
                n4_segment=n4_segment,
                dmg_segment=_demographics(values, dependent=False),
                loop_2110c=None
                if member.dependent
                else [response_loops.Loop2110C(eb_segment=eb) for eb in benefits],
            ),
        )

        if member.dependent:
            dependent_n3, dependent_n4 = _address(values)
            last, first = values.person_name()
            loop_2000c.loop_2000d = [
                response_loops.Loop2000D(
                    hl_segment=response_segments.Loop2000DHlSegment(
                        hierarchical_id_number=entry["dependent_id"],
                        hierarchical_parent_id_number=entry["subscriber_id"],
                        hierarchical_level_code="23",
                        hierarchical_child_code="0",
                    ),
                    loop_2100d=response_loops.Loop2100D(
                        nm1_segment=response_segments.Loop2100DNm1Segment(
                            entity_identifier_code="03",
                            entity_type_qualifier="1",
                            name_last_or_organization_name=last,
                            name_first=first,
                        ),
                        n3_segment=dependent_n3,
                        n4_segment=dependent_n4,
                        dmg_segment=_demographics(values, dependent=True),
                        loop_2110d=[
                            response_loops.Loop2110D(eb_segment=eb) for eb in benefits
                        ],
                    ),
                )
            ]
        subscribers.append(loop_2000c)

    structure: Dict = {
        "header": response_loops.Header(
            st_segment=response_segments.HeaderStSegment(
                transaction_set_identifier_code="271",
                transaction_set_control_number=control_number,
                implementation_convention_reference="005010X279",
            ),
            bht_segment=response_segments.HeaderBhtSegment(
                hierarchical_structure_code="0022",
                transaction_set_purpose_code="11",
                submitter_transactional_identifier=values.control_number(8),
                transaction_set_creation_date=created.strftime("%Y%m%d"),
                transaction_set_creation_time="1200",
            ),
        ),
        "loop_2000a": [
            response_loops.Loop2000A(
                hl_segment=response_segments.Loop2000AHlSegment(
                    hierarchical_id_number="1",
                    hierarchical_level_code="20",
                    hierarchical_child_code="1",
                ),
                loop_2100a=response_loops.Loop2100A(
                    nm1_segment=response_segments.Loop2100ANm1Segment(
                        entity_identifier_code="PR",
                        entity_type_qualifier="2",
                        name_last_or_organization_name=payer_name,
                        identification_code_qualifier="PI",
                        identification_code=values.control_number(9),
                    )
                ),
                loop_2000b=[
                    response_loops.Loop2000B(
                        hl_segment=response_segments.Loop2000BHlSegment(
                            hierarchical_id_number="2",
                            hierarchical_parent_id_number="1",
                            hierarchical_level_code="21",
                            hierarchical_child_code="1",
                        ),
                        loop_2100b=response_loops.Loop2100B(
                            nm1_segment=response_segments.Loop2100BNm1Segment(
                                entity_identifier_code="1P",
                                entity_type_qualifier="2",
                                name_last_or_organization_name=provider_name,
                                identification_code_qualifier="XX",
                                identification_code=values.npi(),
                            )
                        ),
                        loop_2000c=subscribers,
                    )
                ],
            )
        ],
    }
    return _finish(structure, response_loops.Footer, EligibilityBenefit, control_number)


# --- shared helpers ---------------------------------------------------------


def _person(values: ValueFactory, member: MemberSpec, *, dependent: bool) -> Dict:
    last, first = values.person_name()
    return {
        "name_last_or_organization_name": last,
        "name_first": first,
        "identification_code_qualifier": "MI",
        "identification_code": member.member_id or values.member_id(),
    }


def _trace(values: ValueFactory):
    from ..v5010.segments import TrnSegment

    return TrnSegment(
        trace_type_code="1",
        reference_identification_1=values.control_number(12),
        originating_company_identifier=values.tax_id() + "0",
    )


def _eb(benefit: BenefitSpec) -> EbSegment:
    return EbSegment(
        eligibility_benefit_information=benefit.status,
        coverage_level_code=benefit.coverage_level,
        service_type_code=[benefit.service_type],
        plan_coverage_description=benefit.plan_description,
    )


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


def random_members(
    count: int, values: ValueFactory, *, dependent_rate: float = 0.3
) -> List[MemberSpec]:
    """
    Builds members asking about whole-plan coverage.

    ``dependent_rate`` is the share who are a dependent of the subscriber
    rather than the subscriber themselves, so both branches appear by default.
    """
    return [
        MemberSpec(
            benefits=(BenefitSpec(service_type=values.rng.choice(("30", "1", "35"))),),
            dependent=values.rng.random() < dependent_rate,
        )
        for _ in range(count)
    ]
