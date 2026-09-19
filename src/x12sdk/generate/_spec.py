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
class RemittanceSpec:
    """A whole 835: one payer paying one payee for a set of claims."""

    claims: Sequence[ClaimSpec]
    payer_name: Optional[str] = None
    payee_name: Optional[str] = None

    @property
    def total_paid(self) -> Decimal:
        return sum((claim.paid for claim in self.claims), Decimal("0.00"))


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


__all__ = [
    "AdjustmentSpec",
    "ClaimSpec",
    "GROUP_CODES",
    "RemittanceSpec",
    "ServiceLineSpec",
    "denial",
    "patient_responsibility",
]
