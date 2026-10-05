"""
Specifications describing what to generate.

These say what you want to be true of the output, not how to build it. Where a
value is implied by others it is derived rather than asked for: a claim's
payment is charge minus adjustments, so a specification that fails the 835
balance rule cannot be written down in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Sequence

#: Adjustment group codes. CO/OA/PI are payer-side; PR is patient cost share.
GROUP_CODES = ("CO", "OA", "PI", "PR")


@dataclass(frozen=True)
class AdjustmentSpec:
    """One CAS adjustment: why an amount was not paid."""

    group: str
    reason: str
    amount: Decimal
    quantity: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if self.group not in GROUP_CODES:
            raise ValueError(
                f"adjustment group must be one of {GROUP_CODES}, got {self.group!r}"
            )
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))


@dataclass(frozen=True)
class ServiceLineSpec:
    """One service line on a claim."""

    charge: Decimal
    procedure: Optional[str] = None
    adjustments: Sequence[AdjustmentSpec] = field(default_factory=tuple)
    units: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.charge, Decimal):
            object.__setattr__(self, "charge", Decimal(str(self.charge)))

    @property
    def adjustment_total(self) -> Decimal:
        return sum((a.amount for a in self.adjustments), Decimal("0.00"))

    @property
    def paid(self) -> Decimal:
        """What the payer allowed on this line."""
        return self.charge - self.adjustment_total


@dataclass(frozen=True)
class ClaimSpec:
    """
    One claim on a remittance.

    Give the charge and the adjustments; the payment is derived. Claim-level
    adjustments and service-line adjustments both count toward the balance,
    which is what the 835 requires.
    """

    charge: Decimal
    adjustments: Sequence[AdjustmentSpec] = field(default_factory=tuple)
    lines: Sequence[ServiceLineSpec] = field(default_factory=tuple)
    status: str = "1"
    patient_control_number: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.charge, Decimal):
            object.__setattr__(self, "charge", Decimal(str(self.charge)))
        line_total = sum((line.charge for line in self.lines), Decimal("0.00"))
        if self.lines and line_total != self.charge:
            raise ValueError(
                f"service line charges total {line_total} but the claim charge "
                f"is {self.charge}; they must agree"
            )

    @property
    def adjustment_total(self) -> Decimal:
        """Every adjustment on the claim, at claim level and on its lines."""
        claim_level = sum((a.amount for a in self.adjustments), Decimal("0.00"))
        line_level = sum(
            (line.adjustment_total for line in self.lines), Decimal("0.00")
        )
        return claim_level + line_level

    @property
    def paid(self) -> Decimal:
        """Derived, never supplied: charge minus every adjustment."""
        return self.charge - self.adjustment_total


@dataclass(frozen=True)
class ProviderAdjustmentSpec:
    """
    One provider-level adjustment: money moved at the payee level, outside any
    claim, carried in the PLB segment. A positive amount is taken out of the
    payment (an overpayment recovery, a withholding); a negative amount is added
    to it (interest owed to the provider).
    """

    reason: str
    amount: Decimal
    identifier: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("a provider adjustment needs a reason code (PLB03-1)")
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))


@dataclass(frozen=True)
class RemittanceSpec:
    """
    A whole 835: one payer paying one payee for a set of claims.

    The check amount in BPR02 is derived: every claim's payment, less the
    provider-level adjustments. A remittance whose adjustments exceed what the
    claims pay would need a negative check, which the 835 does not allow, so
    it cannot be written down.
    """

    claims: Sequence[ClaimSpec]
    payer_name: Optional[str] = None
    payee_name: Optional[str] = None
    provider_adjustments: Sequence[ProviderAdjustmentSpec] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if len(self.provider_adjustments) > 6:
            raise ValueError(
                "at most six provider adjustments fit on a remittance (one PLB "
                f"segment); got {len(self.provider_adjustments)}"
            )
        if self.total_paid < 0:
            raise ValueError(
                f"provider adjustments total {self.provider_adjustment_total} but "
                f"the claims pay only {self.claims_paid}; BPR02 cannot be negative"
            )

    @property
    def claims_paid(self) -> Decimal:
        """The sum of CLP04 over every claim, before provider-level adjustments."""
        return sum((claim.paid for claim in self.claims), Decimal("0.00"))

    @property
    def provider_adjustment_total(self) -> Decimal:
        return sum((a.amount for a in self.provider_adjustments), Decimal("0.00"))

    @property
    def total_paid(self) -> Decimal:
        """BPR02: what the check is for. Derived, never supplied."""
        return self.claims_paid - self.provider_adjustment_total


#: PAT01 relationship codes, used when the patient is not the subscriber.
PATIENT_RELATIONSHIP_CODES = ("01", "19", "20", "21", "39", "40", "53", "G8")


@dataclass(frozen=True)
class PatientSpec:
    """
    One patient on a claim submission, with the claims filed for them.

    In an 837 a patient is either the subscriber themselves or a dependent of
    one, and the two sit at different depths in the hierarchy. Saying which
    here is what puts the claim on the right branch.
    """

    claims: Sequence[ClaimSpec]
    dependent: bool = False
    relationship: str = "19"

    def __post_init__(self) -> None:
        if not self.claims:
            raise ValueError("a patient must have at least one claim")
        if self.dependent and self.relationship not in PATIENT_RELATIONSHIP_CODES:
            raise ValueError(
                f"relationship must be one of {PATIENT_RELATIONSHIP_CODES}, "
                f"got {self.relationship!r}"
            )


@dataclass(frozen=True)
class SubmissionSpec:
    """A whole 837: one billing provider filing claims with one payer."""

    patients: Sequence[PatientSpec]
    billing_provider_name: Optional[str] = None
    payer_name: Optional[str] = None
    submitter_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.patients:
            raise ValueError("a submission must have at least one patient")
        # A claim submission has no way to say what a payer did not pay, so an
        # adjustment here would silently vanish from the output.
        for patient in self.patients:
            for claim in patient.claims:
                if claim.adjustments or any(line.adjustments for line in claim.lines):
                    raise ValueError(
                        "adjustments describe a payer's decision and cannot be "
                        "represented on a claim submission; put them on the "
                        "remittance instead"
                    )
                if not claim.lines:
                    raise ValueError(
                        "a submitted claim must have at least one service line"
                    )

    @property
    def total_charge(self) -> Decimal:
        return sum(
            (claim.charge for patient in self.patients for claim in patient.claims),
            Decimal("0.00"),
        )


# --- eligibility (270 / 271) ------------------------------------------------

#: EB01 / benefit status. "1" is active coverage; "6" inactive.
BENEFIT_STATUS_CODES = ("1", "2", "3", "4", "5", "6", "7", "8")


@dataclass(frozen=True)
class BenefitSpec:
    """
    One line of coverage: a question on a 270, an answer on a 271.

    The same description serves both, so an inquiry and the response to it can
    be generated as a matched pair from one specification.
    """

    service_type: str = "30"
    status: str = "1"
    coverage_level: Optional[str] = None
    plan_description: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.service_type:
            raise ValueError('service_type is required; "30" is whole-plan coverage')
        if self.status not in BENEFIT_STATUS_CODES:
            raise ValueError(
                f"status must be one of {BENEFIT_STATUS_CODES}, got {self.status!r}"
            )


@dataclass(frozen=True)
class MemberSpec:
    """
    One person an eligibility transaction is about.

    As on an 837, the person is either the subscriber or a dependent of one,
    and the two sit at different depths of the hierarchy. Unlike an 837 the
    payload is coverage rather than claims, so this is a separate type from
    :class:`PatientSpec`.
    """

    benefits: Sequence[BenefitSpec] = field(default_factory=tuple)
    dependent: bool = False
    relationship: str = "19"
    member_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.benefits:
            object.__setattr__(self, "benefits", (BenefitSpec(),))
        if self.dependent and self.relationship not in PATIENT_RELATIONSHIP_CODES:
            raise ValueError(
                f"relationship must be one of {PATIENT_RELATIONSHIP_CODES}, "
                f"got {self.relationship!r}"
            )


@dataclass(frozen=True)
class EligibilitySpec:
    """A whole 270 or 271: one payer, one provider, a set of members."""

    members: Sequence[MemberSpec]
    payer_name: Optional[str] = None
    provider_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("an eligibility transaction must have at least one member")


# --- claim status (276 / 277) -----------------------------------------------


@dataclass(frozen=True)
class TrackedClaimSpec:
    """
    One claim whose status is asked about on a 276 or reported on a 277.

    ``paid`` and the status codes are only rendered on the response; an
    inquiry carries the identifying detail and nothing else, so the same
    specification builds a 276 and the 277 answering it.
    """

    charge: Decimal
    patient_control_number: Optional[str] = None
    payer_claim_control_number: Optional[str] = None
    paid: Optional[Decimal] = None
    status_category: str = "F1"
    status_code: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.charge, Decimal):
            object.__setattr__(self, "charge", Decimal(str(self.charge)))
        if self.paid is not None and not isinstance(self.paid, Decimal):
            object.__setattr__(self, "paid", Decimal(str(self.paid)))
        if self.paid is not None and self.paid > self.charge:
            raise ValueError(f"paid {self.paid} cannot exceed the charge {self.charge}")


@dataclass(frozen=True)
class StatusPatientSpec:
    """A patient on a 276 or 277, and the claims being tracked for them."""

    claims: Sequence[TrackedClaimSpec]
    dependent: bool = False
    relationship: str = "19"
    member_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.claims:
            raise ValueError("a patient must have at least one tracked claim")
        if self.dependent and self.relationship not in PATIENT_RELATIONSHIP_CODES:
            raise ValueError(
                f"relationship must be one of {PATIENT_RELATIONSHIP_CODES}, "
                f"got {self.relationship!r}"
            )


@dataclass(frozen=True)
class ClaimStatusSpec:
    """A whole 276 or 277: one payer, one requester, one provider, its patients."""

    patients: Sequence[StatusPatientSpec]
    payer_name: Optional[str] = None
    requester_name: Optional[str] = None
    provider_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.patients:
            raise ValueError("a claim status transaction needs at least one patient")


# --- benefit enrollment (834) -----------------------------------------------


@dataclass(frozen=True)
class CoverageSpec:
    """One HD coverage line on an enrollment: what the member is enrolled in."""

    insurance_line: str = "HLT"
    maintenance_type: str = "021"
    coverage_level: Optional[str] = None
    plan_description: Optional[str] = None


#: DSB01 disability type codes: short-term, long-term, permanent total, none.
DISABILITY_TYPE_CODES = ("1", "2", "3", "4")


@dataclass(frozen=True)
class DisabilitySpec:
    """
    One disability period on a member (loop 2200: a DSB with its dates).

    A member can carry several, and they repeat as separate loops; code that
    keeps only the last one is a bug this generator exists to expose.
    """

    type: str = "2"
    begins: Optional[str] = None
    ends: Optional[str] = None
    diagnosis: Optional[str] = None

    def __post_init__(self) -> None:
        if self.type not in DISABILITY_TYPE_CODES:
            raise ValueError(
                f"disability type must be one of {DISABILITY_TYPE_CODES}, "
                f"got {self.type!r}"
            )


@dataclass(frozen=True)
class EmployerSpec:
    """One employer of a member (loop 2100D). Up to three per member."""

    name: str
    identifier: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("an employer needs a name")


@dataclass(frozen=True)
class EnrolleeSpec:
    """
    One member on an 834.

    The 834 has no HL hierarchy. A dependent is a separate member record
    marked by INS01 rather than a loop nested under the subscriber, so
    ``dependent`` changes the record rather than where it sits.
    """

    coverages: Sequence[CoverageSpec] = field(default_factory=tuple)
    dependent: bool = False
    relationship: str = "19"
    member_id: Optional[str] = None
    benefit_status: str = "A"
    maintenance_type: str = "021"
    employers: Sequence[EmployerSpec] = field(default_factory=tuple)
    disabilities: Sequence[DisabilitySpec] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.coverages:
            object.__setattr__(self, "coverages", (CoverageSpec(),))
        if not self.dependent and self.relationship != "18":
            # INS02 is 18, self, whenever the member is the subscriber
            object.__setattr__(self, "relationship", "18")
        if len(self.employers) > 3:
            raise ValueError(
                f"a member can have at most three employers (loop 2100D), "
                f"got {len(self.employers)}"
            )


@dataclass(frozen=True)
class EnrollmentSpec:
    """A whole 834: one sponsor, one payer, a roster of members."""

    enrollees: Sequence[EnrolleeSpec]
    sponsor_name: Optional[str] = None
    payer_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.enrollees:
            raise ValueError("an enrollment must have at least one member")


def denial(group: str, reason: str, amount) -> AdjustmentSpec:
    """
    Shorthand for a payer-side adjustment.

    >>> denial("CO", "45", "30.00").amount
    Decimal('30.00')
    """
    return AdjustmentSpec(group=group, reason=reason, amount=Decimal(str(amount)))


def patient_responsibility(reason: str, amount) -> AdjustmentSpec:
    """Shorthand for a ``PR`` adjustment: deductible, coinsurance or copay."""
    return AdjustmentSpec(group="PR", reason=reason, amount=Decimal(str(amount)))


def provider_adjustment(
    reason: str, amount, identifier: Optional[str] = None
) -> ProviderAdjustmentSpec:
    """
    Shorthand for a PLB provider-level adjustment.

    >>> provider_adjustment("WO", "25.00", "PCN000001").amount
    Decimal('25.00')
    """
    return ProviderAdjustmentSpec(
        reason=reason, amount=Decimal(str(amount)), identifier=identifier
    )


__all__ = [
    "AdjustmentSpec",
    "BENEFIT_STATUS_CODES",
    "BenefitSpec",
    "ClaimSpec",
    "ClaimStatusSpec",
    "CoverageSpec",
    "DISABILITY_TYPE_CODES",
    "DisabilitySpec",
    "EligibilitySpec",
    "EmployerSpec",
    "EnrolleeSpec",
    "EnrollmentSpec",
    "GROUP_CODES",
    "MemberSpec",
    "PATIENT_RELATIONSHIP_CODES",
    "PatientSpec",
    "ProviderAdjustmentSpec",
    "RemittanceSpec",
    "ServiceLineSpec",
    "StatusPatientSpec",
    "SubmissionSpec",
    "TrackedClaimSpec",
    "denial",
    "patient_responsibility",
    "provider_adjustment",
]
