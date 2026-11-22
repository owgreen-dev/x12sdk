"""
matching.py

Joins claims to the remittances that answer them, on the patient control
number (CLM01 on the 837, CLP01 on the 835), which is how real files link.

    from x12sdk.matching import match_claims, match_rows

    for match in match_claims("claims.837", ["remit-1.835", "remit-2.835"]):
        print(match.patient_control_number, match.outcome, match.billed, match.paid)

A claim can be answered more than once (a payment, then a reversal and a
corrected payment), and an 835 can pay a claim that is not in the 837s you
have, so every match carries *all* the payments found for its number, and
claims or payments without a partner are kept rather than dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from .access import PaidClaim, SubmittedClaim
from .io import X12ModelReader

#: The outcomes :attr:`Match.outcome` can take.
OUTCOMES = ("paid", "denied", "no remittance", "no claim")

MATCH_COLUMNS: Sequence[str] = (
    "patient_control_number",
    "outcome",
    "billed",
    "paid",
    "patient_responsibility",
    "payment_count",
    "claim_status_codes",
    "payer_claim_control_numbers",
    "claim_count",
)


@dataclass(frozen=True)
class Match:
    """
    One patient control number, with every claim and payment that carries it.

    ``claims`` is usually one claim; more than one means the same number was
    submitted again. ``payments`` holds every CLP for the number, in the order
    the remittances were given.
    """

    patient_control_number: str
    claims: Tuple[SubmittedClaim, ...]
    payments: Tuple[PaidClaim, ...]

    @property
    def billed(self) -> Optional[Decimal]:
        """CLM02 of the first claim, or the 835's CLP03 when no claim was given."""
        if self.claims:
            return self.claims[0].charge
        if self.payments:
            return self.payments[0].charge
        return None

    @property
    def paid(self) -> Decimal:
        """CLP04 over every payment; a reversal's negative amount nets out."""
        return sum((p.paid for p in self.payments), Decimal("0.00"))

    @property
    def patient_responsibility(self) -> Decimal:
        return sum(
            (
                p.claim.clp_segment.patient_responsibility_amount or Decimal("0.00")
                for p in self.payments
            ),
            Decimal("0.00"),
        )

    @property
    def outcome(self) -> str:
        """
        ``no remittance`` when nothing answered the claim, ``no claim`` when a
        payment's claim is not among the 837s given, otherwise ``paid`` or
        ``denied`` by whether the payments net to more than zero.
        """
        if not self.payments:
            return "no remittance"
        if not self.claims:
            return "no claim"
        return "paid" if self.paid > 0 else "denied"


def _transactions(sources) -> Iterator[Any]:
    """Text, a path, a model, or any iterable of those."""
    if isinstance(sources, (str, bytes)) or hasattr(sources, "header"):
        sources = [sources]
    for source in sources:
        if hasattr(source, "header"):
            yield source
        else:
            with X12ModelReader(source) as reader:
                yield from reader.models()


def _claims_of(sources, code: str) -> Iterator[Any]:
    for transaction in _transactions(sources):
        if transaction.header.st_segment.transaction_set_identifier_code != code:
            continue
        if not hasattr(transaction, "claims"):
            raise ValueError(
                f"matching reads 5010 transactions; this {code} is not supported"
            )
        yield from transaction.claims()


def match_claims(claims, remittances) -> List[Match]:
    """
    Pairs every claim with every payment that answers it.

    :param claims: 837 files, text or models (one or an iterable).
    :param remittances: 835 files, text or models (one or an iterable).
    :return: One :class:`Match` per patient control number: the claims' numbers
        in file order, then numbers only the remittances carry.
    """
    submitted: Dict[str, List[SubmittedClaim]] = {}
    for claim in _claims_of(claims, "837"):
        submitted.setdefault(claim.patient_control_number, []).append(claim)
    paid: Dict[str, List[PaidClaim]] = {}
    for payment in _claims_of(remittances, "835"):
        paid.setdefault(payment.patient_control_number, []).append(payment)

    order = list(submitted) + [n for n in paid if n not in submitted]
    return [
        Match(
            patient_control_number=number,
            claims=tuple(submitted.get(number, ())),
            payments=tuple(paid.get(number, ())),
        )
        for number in order
    ]


def match_rows(claims, remittances) -> Iterable[Dict[str, Any]]:
    """
    :func:`match_claims` as flat rows with :data:`MATCH_COLUMNS`, ready for a
    CSV or a DataFrame.
    """
    for match in match_claims(claims, remittances):
        yield {
            "patient_control_number": match.patient_control_number,
            "outcome": match.outcome,
            "billed": match.billed,
            "paid": match.paid,
            "patient_responsibility": match.patient_responsibility,
            "payment_count": len(match.payments),
            "claim_status_codes": ";".join(p.status for p in match.payments) or None,
            "payer_claim_control_numbers": ";".join(
                p.payer_claim_control_number or "" for p in match.payments
            )
            or None,
            "claim_count": len(match.claims),
        }
