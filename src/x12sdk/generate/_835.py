"""
Builds 835 remittance advice transactions from a specification.

The segment count in SE01 must equal every segment from ST through SE, and the
transaction refuses to validate otherwise. Rather than guess it, the structure
is counted with the same :func:`x12sdk.support.count_segments` the validator
uses, then the footer is attached.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Sequence

from ..support import count_segments
from ..v5010.segments import (
    BprSegment,
    ClpSegment,
    N3Segment,
    N4Segment,
    Nm1Segment,
    SeSegment,
    SvcSegment,
)
from ..v5010.x12_835_005010X221A1.loops import (
    Footer,
    Header,
    Loop1000A,
    Loop1000B,
    Loop2000,
    Loop2100,
    Loop2110,
)
from ..v5010.x12_835_005010X221A1.segments import (
    HeaderStSegment,
    HeaderTrnSegment,
    Loop1000AN1Segment,
    Loop1000BN1Segment,
    Loop2100CasSegment,
    Loop2110CasSegment,
)
from ..v5010.x12_835_005010X221A1.transaction_set import HealthCareClaimPayment
from ._spec import AdjustmentSpec, ClaimSpec, RemittanceSpec, ServiceLineSpec
from ._values import ValueFactory


def _cas_segments(adjustments: Sequence[AdjustmentSpec], segment_class):
    """
    Renders adjustments as CAS segments, one per adjustment.

    A CAS segment can carry up to six reason/amount pairs, but writing one
    adjustment per segment keeps generated files easy to read and eyeball
    against an expected denial summary.
    """
    return [
        segment_class(
            adjustment_group_code=adjustment.group,
            adjustment_reason_code_1=adjustment.reason,
            monetary_amount_1=adjustment.amount,
            quantity_1=adjustment.quantity,
        )
        for adjustment in adjustments
    ]


def _service_line(line: ServiceLineSpec, values: ValueFactory) -> Loop2110:
    procedure = line.procedure or values.procedure()
    return Loop2110(
        svc_segment=SvcSegment(
            composite_medical_procedure_identifier_1=f"HC:{procedure}",
            line_item_charge_amount=line.charge,
            line_item_provider_payment_amount=line.paid,
            units_of_service_paid_count=Decimal(line.units),
        ),
        cas_segment=_cas_segments(line.adjustments, Loop2110CasSegment) or None,
    )


def _claim(claim: ClaimSpec, index: int, values: ValueFactory) -> Loop2100:
    last, first = values.person_name()
    return Loop2100(
        clp_segment=ClpSegment(
            patient_control_number=claim.patient_control_number
            or values.claim_number(index),
            claim_status_code=claim.status,
            total_claim_charge_amount=claim.charge,
            claim_payment_amount=claim.paid,
            claim_filing_indicator_code="CH",
            payer_claim_control_number=values.payer_claim_number(),
        ),
        cas_segment=_cas_segments(claim.adjustments, Loop2100CasSegment) or None,
        nm1_segment=[
            Nm1Segment(
                entity_identifier_code="QC",
                entity_type_qualifier="1",
                name_last_or_organization_name=last,
                name_first=first,
                identification_code_qualifier="MI",
                identification_code=values.member_id(),
            )
        ],
        loop_2110=[_service_line(line, values) for line in claim.lines] or None,
    )


def build_835(
    spec: RemittanceSpec,
    *,
    seed: int = 0,
    control_number: str = "0001",
) -> HealthCareClaimPayment:
    """
    Builds a validated 835 transaction model from a specification.

    :param spec: What the remittance should contain.
    :param seed: Seeds the values that the specification leaves unstated.
    :param control_number: ST02/SE02. At least 4 characters, per the standard.
    :return: A validated ``HealthCareClaimPayment``.
    """
    values = ValueFactory(seed)

    structure: Dict = {
        "header": Header(
            st_segment=HeaderStSegment(
                transaction_set_identifier_code="835",
                transaction_set_control_number=control_number,
            ),
            bpr_segment=BprSegment(
                transaction_handling_code="I",
                total_actual_provider_payment_amount=spec.total_paid,
                credit_debit_flag_code="C",
                # CHK avoids the nine DFI fields that ACH/BOP/FWT make mandatory
                payment_method_code="CHK",
            ),
            trn_segment=HeaderTrnSegment(
                trace_type_code="1",
                reference_identification_1=values.control_number(10),
                originating_company_identifier=values.tax_id() + "0",
            ),
        ),
        "loop_1000a": Loop1000A(
            n1_segment=Loop1000AN1Segment(
                entity_identifier_code="PR",
                name=spec.payer_name or values.plan_name(),
            ),
            n3_segment=N3Segment(address_information_1=values.address()),
            n4_segment=N4Segment(
                city_name=values.city(),
                state_province_code=values.state(),
                postal_code=values.postal_code(),
            ),
        ),
        "loop_1000b": Loop1000B(
            n1_segment=Loop1000BN1Segment(
                entity_identifier_code="PE",
                name=spec.payee_name or values.provider_name(),
                identification_code_qualifier="XX",
                identification_code=values.npi(),
            ),
        ),
        "loop_2000": [
            Loop2000(
                lx_segment={"assigned_number": "1"},
                loop_2100=[
                    _claim(claim, index, values)
                    for index, claim in enumerate(spec.claims, start=1)
                ],
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

    return HealthCareClaimPayment(**structure)


def random_claims(
    count: int, values: ValueFactory, *, denial_rate: float = 0.4
) -> List[ClaimSpec]:
    """
    Builds plausible claims with a mix of paid, adjusted and denied outcomes.

    Used when a caller asks for a number of claims rather than describing each
    one. ``denial_rate`` is the share of claims carrying a payer-side
    adjustment; the rest are paid in full or carry only patient cost share.
    """
    claims: List[ClaimSpec] = []
    for _ in range(count):
        charge = values.amount(100, 4000)
        line_count = values.rng.randint(1, 3)
        line_charges = values.split(charge, line_count)

        adjustments: List[AdjustmentSpec] = []
        lines: List[ServiceLineSpec] = []
        roll = values.rng.random()

        if roll < denial_rate:
            # a contractual write-off on the first line, the commonest case
            reason = values.rng.choice(("45", "97", "197", "18", "29", "96"))
            write_off = (line_charges[0] * Decimal("0.3")).quantize(Decimal("0.01"))
            lines.append(
                ServiceLineSpec(
                    charge=line_charges[0],
                    adjustments=[
                        AdjustmentSpec(group="CO", reason=reason, amount=write_off)
                    ],
                )
            )
            lines.extend(ServiceLineSpec(charge=c) for c in line_charges[1:])
        elif roll < denial_rate + 0.3:
            # patient cost share only: a deductible, not a denial
            deductible = (line_charges[0] * Decimal("0.2")).quantize(Decimal("0.01"))
            lines.append(
                ServiceLineSpec(
                    charge=line_charges[0],
                    adjustments=[
                        AdjustmentSpec(group="PR", reason="1", amount=deductible)
                    ],
                )
            )
            lines.extend(ServiceLineSpec(charge=c) for c in line_charges[1:])
        else:
            lines.extend(ServiceLineSpec(charge=c) for c in line_charges)

        claims.append(ClaimSpec(charge=charge, adjustments=adjustments, lines=lines))
    return claims
