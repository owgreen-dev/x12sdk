"""
Flattened access to the loop hierarchy.

Reaching a claim through the models means walking the HL hierarchy by hand,
and on an 837 that hierarchy branches: a claim sits under the subscriber when
the patient *is* the subscriber, and under a dependent when they are not.

    loop_2000a[i].loop_2000b[j].loop_2300[k]                  patient = subscriber
    loop_2000a[i].loop_2000b[j].loop_2000c[l].loop_2300[k]    patient = dependent

Both are ordinary; neither is rare. Code written against one branch runs
without error on a file that uses the other and silently reports no claims, so
this is a correctness trap rather than an inconvenience. The generators here
walk both and hand back the claim together with the context needed to read it.

    with X12ModelReader("claims.837") as reader:
        for model in reader.models():
            for claim in model.claims():
                print(claim.patient_control_number, claim.charge, claim.is_dependent)

Everything is yielded lazily, so a large file is never held in memory at once,
and every record keeps a reference to the underlying loop, so nothing the
models expose is hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterator, List, Optional, Tuple


def _name(nm1_segment: Any) -> Tuple[Optional[str], Optional[str]]:
    """``(last or organization, first)`` from any NM1, or ``(None, None)``."""
    if nm1_segment is None:
        return None, None
    return (
        nm1_segment.name_last_or_organization_name,
        nm1_segment.name_first,
    )


# --- 837 professional and institutional ------------------------------------


@dataclass(frozen=True)
class SubmittedClaim:
    """
    One claim on an 837, with the loops that give it meaning.

    ``patient`` is the loop describing whoever was treated: loop 2010CA when
    the patient is a dependent, and the subscriber's own loop 2010BA when they
    are not. Reading it does not require knowing which, which is the point.
    """

    claim: Any
    billing_provider: Any
    subscriber: Any
    payer: Any
    patient: Any
    is_dependent: bool
    relationship: Optional[str]

    @property
    def patient_control_number(self) -> str:
        """CLM01, the provider's own identifier for the claim."""
        return self.claim.clm_segment.patient_control_number

    @property
    def charge(self) -> Decimal:
        """CLM02, the total charge submitted."""
        return self.claim.clm_segment.total_claim_charge_amount

    @property
    def service_lines(self) -> List[Any]:
        """The 2400 loops, one per service line."""
        return list(self.claim.loop_2400 or [])

    @property
    def patient_name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.patient.nm1_segment)

    @property
    def subscriber_name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.subscriber.nm1_segment)

    @property
    def member_id(self) -> Optional[str]:
        """NM109 on loop 2010BA, the subscriber's identifier with the payer."""
        return self.subscriber.nm1_segment.identification_code

    @property
    def payer_name(self) -> Optional[str]:
        return _name(self.payer.nm1_segment)[0]

    @property
    def billing_provider_name(self) -> Optional[str]:
        return _name(self.billing_provider.nm1_segment)[0]

    @property
    def billing_provider_npi(self) -> Optional[str]:
        """NM109 on loop 2010AA, present when NM108 qualifies it as an NPI."""
        nm1_segment = self.billing_provider.nm1_segment
        if nm1_segment.identification_code_qualifier == "XX":
            return nm1_segment.identification_code
        return None


@dataclass(frozen=True)
class Subscriber:
    """One subscriber on an 837, and the dependents filed beneath them."""

    subscriber: Any
    billing_provider: Any
    payer: Any
    dependents: Tuple[Any, ...]

    @property
    def name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.subscriber.nm1_segment)

    @property
    def member_id(self) -> Optional[str]:
        return self.subscriber.nm1_segment.identification_code


class ClaimSubmissionAccess:
    """
    ``claims()`` and ``subscribers()`` for the 837 transaction models.

    The professional and institutional implementations have identical loop
    names down every level this walks, so one traversal serves both.
    """

    def subscribers(self) -> Iterator[Subscriber]:
        """Yields every subscriber in the transaction, in file order."""
        for loop_2000a in self.loop_2000a:
            billing_provider = loop_2000a.loop_2010aa
            for loop_2000b in loop_2000a.loop_2000b:
                yield Subscriber(
                    subscriber=loop_2000b.loop_2010ba,
                    billing_provider=billing_provider,
                    payer=loop_2000b.loop_2010bb,
                    dependents=tuple(
                        loop_2000c.loop_2010ca
                        for loop_2000c in (loop_2000b.loop_2000c or [])
                    ),
                )

    def claims(self) -> Iterator[SubmittedClaim]:
        """
        Yields every claim in the transaction, in file order.

        Claims filed for the subscriber and claims filed for a dependent both
        appear; ``SubmittedClaim.is_dependent`` says which, and ``patient``
        already points at the right loop either way.
        """
        for loop_2000a in self.loop_2000a:
            billing_provider = loop_2000a.loop_2010aa
            for loop_2000b in loop_2000a.loop_2000b:
                subscriber = loop_2000b.loop_2010ba
                payer = loop_2000b.loop_2010bb

                # the subscriber is the patient
                relationship = getattr(
                    loop_2000b.sbr_segment, "individual_relationship_code", None
                )
                for claim in loop_2000b.loop_2300 or []:
                    yield SubmittedClaim(
                        claim=claim,
                        billing_provider=billing_provider,
                        subscriber=subscriber,
                        payer=payer,
                        patient=subscriber,
                        is_dependent=False,
                        relationship=relationship,
                    )

                # the patient is a dependent of the subscriber
                for loop_2000c in loop_2000b.loop_2000c or []:
                    dependent_relationship = getattr(
                        loop_2000c.pat_segment, "individual_relationship_code", None
                    )
                    for claim in loop_2000c.loop_2300 or []:
                        yield SubmittedClaim(
                            claim=claim,
                            billing_provider=billing_provider,
                            subscriber=subscriber,
                            payer=payer,
                            patient=loop_2000c.loop_2010ca,
                            is_dependent=True,
                            relationship=dependent_relationship,
                        )


# --- 835 remittance advice -------------------------------------------------


@dataclass(frozen=True)
class PaidClaim:
    """One claim on an 835, with the payer and payee that settled it."""

    claim: Any
    payer: Any
    payee: Any
    header_number: str

    @property
    def patient_control_number(self) -> str:
        """CLP01, matching CLM01 on the claim that was submitted."""
        return self.claim.clp_segment.patient_control_number

    @property
    def status(self) -> str:
        """CLP02, the claim status code: 1 processed as primary, 4 denied, ..."""
        return self.claim.clp_segment.claim_status_code

    @property
    def charge(self) -> Decimal:
        """CLP03, the total charge submitted."""
        return self.claim.clp_segment.total_claim_charge_amount

    @property
    def paid(self) -> Decimal:
        """CLP04, what the payer paid."""
        return self.claim.clp_segment.claim_payment_amount

    @property
    def payer_claim_control_number(self) -> Optional[str]:
        """CLP07, the payer's own identifier for the claim."""
        return self.claim.clp_segment.payer_claim_control_number

    @property
    def service_lines(self) -> List[Any]:
        """The 2110 loops, one per service line the payer reported."""
        return list(self.claim.loop_2110 or [])

    @property
    def adjustments(self) -> List[Any]:
        """The claim-level CAS segments. Service lines carry their own."""
        return list(self.claim.cas_segment or [])

    @property
    def patient(self) -> Optional[Any]:
        """The NM1*QC patient name, which the 835 does not require."""
        for nm1_segment in self.claim.nm1_segment or []:
            if nm1_segment.entity_identifier_code == "QC":
                return nm1_segment
        return None

    @property
    def patient_name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.patient)

    @property
    def payer_name(self) -> Optional[str]:
        return self.payer.n1_segment.name

    @property
    def payee_name(self) -> Optional[str]:
        return self.payee.n1_segment.name


class RemittanceAccess:
    """``claims()`` for the 835 transaction model."""

    def claims(self) -> Iterator[PaidClaim]:
        """
        Yields every claim payment in the transaction, in file order.

        An 835 groups claims under LX header numbers; ``header_number`` keeps
        the grouping available without having to nest to reach it.
        """
        payer = self.loop_1000a
        payee = self.loop_1000b
        for loop_2000 in self.loop_2000:
            header_number = loop_2000.lx_segment.assigned_number
            for claim in loop_2000.loop_2100:
                yield PaidClaim(
                    claim=claim,
                    payer=payer,
                    payee=payee,
                    header_number=header_number,
                )


__all__ = [
    "ClaimSubmissionAccess",
    "PaidClaim",
    "RemittanceAccess",
    "SubmittedClaim",
    "Subscriber",
]
