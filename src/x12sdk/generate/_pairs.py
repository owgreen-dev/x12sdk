"""
Matched claim and remittance pairs.

A claim submission (837) says what a provider billed; a remittance (835) says
what the payer decided. Real pairs are PHI and cannot be shared, so there is
no public set of claims with their outcomes. This builds both sides from one
specification and keeps them in step: every claim on the 837 is answered by
exactly one claim payment on the 835, linked the way real files link them, by
CLM01 = CLP01, with the same charges, the same procedure on each line, the
same patient, payer and payee.

One specification describes both because a ``ClaimSpec`` already holds the
claim and the decision on it: the charges and lines are what was submitted,
the adjustments and status are what the payer did. The 837 is built with the
adjustments taken off (a submission cannot carry them), and the 835 is built
with them on.

Every value the two sides must agree on is decided once, before either is
built: each line's procedure, each claim's patient control number, the payer
and the billing provider. The patient's name and member id are read back from
the built 837 rather than invented again.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from ._835 import build_835
from ._837d import build_837d, random_dental_lines
from ._837i import build_837i
from ._837p import build_837p, claim_specs_to_patients
from ._spec import (
    AdjustmentSpec,
    ClaimSpec,
    RemittanceSpec,
    ServiceLineSpec,
    SubmissionSpec,
)
from ._values import ValueFactory


class ClaimPair(NamedTuple):
    """
    A claim submission and the remittance that answers it, as two complete
    interchanges. Unpacks as ``claim, remittance = generate_claim_pair(...)``.
    """

    claim: str
    remittance: str


class _ClaimType(NamedTuple):
    build: Callable
    procedure_qualifier: str
    dental: bool


#: The claim types a pair can be built from.
_CLAIM_TYPES: Dict[str, _ClaimType] = {
    "837p": _ClaimType(build_837p, "HC", False),
    "837i": _ClaimType(build_837i, "HC", False),
    "837d": _ClaimType(build_837d, "AD", True),
}

#: CLP02 values used here: processed as primary, and denied.
_PAID, _DENIED = "1", "4"

#: Reason codes for a claim denied outright (bare CARC codes; no descriptions
#: are carried, see the denials module).
_DENIAL_REASONS = ("16", "27", "29", "50", "197")


def _invent_claims(count: int, values: ValueFactory, dental: bool) -> List[ClaimSpec]:
    """Submitted claims, with every line's procedure decided."""
    claims: List[ClaimSpec] = []
    for _ in range(count):
        if dental:
            lines = random_dental_lines(values, values.rng.randint(1, 4))
        else:
            charge = values.amount(80, 3000)
            lines = [
                ServiceLineSpec(charge=c, procedure=values.procedure())
                for c in values.split(charge, values.rng.randint(1, 3))
            ]
        charge = sum((line.charge for line in lines), Decimal("0.00"))
        claims.append(ClaimSpec(charge=charge, lines=lines))
    return claims


def _share(amount: Decimal, low: float, high: float, values: ValueFactory) -> Decimal:
    rate = Decimal(str(round(values.rng.uniform(low, high), 2)))
    return (amount * rate).quantize(Decimal("0.01"))


def adjudicate(
    claim: ClaimSpec, values: ValueFactory, *, denial_rate: float = 0.15
) -> ClaimSpec:
    """
    Decides an invented outcome for a submitted claim.

    A share ``denial_rate`` of claims is denied outright (CLP02 4, every line
    adjusted to nothing). The rest are processed as primary: most with a
    contractual write-off on each line (CO 45, the usual gap between charge
    and fee schedule), some also leaving a deductible or coinsurance to the
    patient (PR), and some paid in full. Outcomes are made of adjustments, so
    the payment is derived and the 835 balances by construction.
    """
    roll = values.rng.random()
    if roll < denial_rate:
        reason = values.rng.choice(_DENIAL_REASONS)
        lines = [
            dataclasses.replace(
                line,
                adjustments=(
                    AdjustmentSpec(group="CO", reason=reason, amount=line.charge),
                ),
            )
            for line in claim.lines
        ]
        return dataclasses.replace(claim, lines=lines, status=_DENIED)

    lines = []
    paid_in_full = values.rng.random() < 0.15
    patient_share = not paid_in_full and values.rng.random() < 0.4
    for number, line in enumerate(claim.lines):
        adjustments: List[AdjustmentSpec] = []
        if not paid_in_full:
            write_off = _share(line.charge, 0.10, 0.45, values)
            if write_off:
                adjustments.append(
                    AdjustmentSpec(group="CO", reason="45", amount=write_off)
                )
            if patient_share and number == 0:
                left = line.charge - write_off
                owed = _share(left, 0.10, 0.30, values)
                if owed:
                    reason = values.rng.choice(("1", "2", "3"))
                    adjustments.append(
                        AdjustmentSpec(group="PR", reason=reason, amount=owed)
                    )
        lines.append(dataclasses.replace(line, adjustments=tuple(adjustments)))
    return dataclasses.replace(claim, lines=lines, status=_PAID)


def _settled(
    claim: ClaimSpec, index: int, values: ValueFactory, claim_type: _ClaimType
) -> ClaimSpec:
    """Decides what the two sides must agree on and the spec left open."""
    lines = []
    for line in claim.lines:
        if line.procedure:
            lines.append(line)
        elif claim_type.dental:
            procedure, tooth, surfaces = values.dental_procedure()
            if line.tooth:
                tooth, surfaces = line.tooth, tuple(line.surfaces)
            lines.append(
                dataclasses.replace(
                    line, procedure=procedure, tooth=tooth, surfaces=surfaces
                )
            )
        else:
            lines.append(dataclasses.replace(line, procedure=values.procedure()))
    return dataclasses.replace(
        claim,
        lines=lines,
        patient_control_number=claim.patient_control_number
        or values.claim_number(index),
    )


def _as_submitted(claim: ClaimSpec) -> ClaimSpec:
    """The claim with the payer's decision taken off."""
    return dataclasses.replace(
        claim,
        adjustments=(),
        status="1",
        lines=[dataclasses.replace(line, adjustments=()) for line in claim.lines],
    )


def build_claim_pair(
    claims: Sequence[ClaimSpec],
    *,
    claim_type: str = "837p",
    seed: int = 0,
    dependent_rate: float = 0.3,
    billing_provider_name: Optional[str] = None,
    payer_name: Optional[str] = None,
    control_number: str = "0001",
) -> Tuple:
    """
    Builds a claim submission model and the remittance model that answers it.

    :param claims: The claims, each with its outcome: adjustments and status
        are what the payer decided, everything else is what was submitted.
    :return: ``(submission, remittance)`` models, both validated.
    """
    if claim_type not in _CLAIM_TYPES:
        raise ValueError(
            f"claim_type must be one of {tuple(_CLAIM_TYPES)}, got {claim_type!r}"
        )
    kind = _CLAIM_TYPES[claim_type]
    values = ValueFactory(seed)

    decided = [
        _settled(claim, index, values, kind)
        for index, claim in enumerate(claims, start=1)
    ]
    numbers = [claim.patient_control_number for claim in decided]
    if len(set(numbers)) != len(numbers):
        raise ValueError(
            "patient control numbers must be unique: they are what links each "
            "claim to its payment"
        )
    payer_name = payer_name or values.plan_name()
    provider_name = billing_provider_name or (
        values.dental_provider_name() if kind.dental else values.provider_name()
    )

    submission = kind.build(
        SubmissionSpec(
            patients=claim_specs_to_patients(
                [_as_submitted(claim) for claim in decided],
                values,
                dependent_rate=dependent_rate,
            ),
            billing_provider_name=provider_name,
            payer_name=payer_name,
        ),
        seed=seed,
        control_number=control_number,
    )

    # who each claim was for, as the 837 ended up saying it
    submitted = {claim.patient_control_number: claim for claim in submission.claims()}
    patients = []
    for number in numbers:
        claim = submitted[number]
        last, first = claim.patient_name
        patients.append((last, first, claim.member_id))
    payee_npi = next(iter(submitted.values())).billing_provider_npi

    remittance = build_835(
        RemittanceSpec(claims=decided, payer_name=payer_name, payee_name=provider_name),
        seed=seed,
        control_number=control_number,
        procedure_qualifier=kind.procedure_qualifier,
        patients=patients,
        payee_npi=payee_npi,
    )
    return submission, remittance


def claim_pair_specs(
    count: int,
    values: ValueFactory,
    *,
    claim_type: str = "837p",
    denial_rate: float = 0.15,
) -> List[ClaimSpec]:
    """Invents ``count`` claims of a type, each with an invented outcome."""
    if claim_type not in _CLAIM_TYPES:
        raise ValueError(
            f"claim_type must be one of {tuple(_CLAIM_TYPES)}, got {claim_type!r}"
        )
    dental = _CLAIM_TYPES[claim_type].dental
    return [
        adjudicate(claim, values, denial_rate=denial_rate)
        for claim in _invent_claims(count, values, dental)
    ]
