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


# --- 270 and 271 eligibility ------------------------------------------------


def _as_tuple(value) -> Tuple[Any, ...]:
    """
    Normalises a loop that is a list on one transaction and a single loop on
    the other.

    The 271 holds a list of 2110 benefit loops; the 270 holds exactly one. A
    caller should not have to care which, so both arrive as a tuple.
    """
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


@dataclass(frozen=True)
class EligibilityMember:
    """
    One person an eligibility transaction is about, with its context.

    ``member`` is the loop describing whoever the question is about: loop
    2100D when they are a dependent, and the subscriber's own loop 2100C when
    they are not. Reading it does not require knowing which.
    """

    member: Any
    subscriber: Any
    payer: Any
    provider: Any
    benefits: Tuple[Any, ...]
    is_dependent: bool

    @property
    def name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.member.nm1_segment)

    @property
    def subscriber_name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.subscriber.nm1_segment)

    @property
    def member_id(self) -> Optional[str]:
        """NM109 on loop 2100C, the subscriber's identifier with the payer."""
        return self.subscriber.nm1_segment.identification_code

    @property
    def payer_name(self) -> Optional[str]:
        return _name(self.payer.nm1_segment)[0]

    @property
    def provider_name(self) -> Optional[str]:
        return _name(self.provider.nm1_segment)[0]

    @property
    def service_type_codes(self) -> Tuple[str, ...]:
        """
        The service types asked about or answered, across every benefit loop.

        EQ01 on an inquiry and EB03 on a response both repeat, so both come
        back flattened.
        """
        codes: List[str] = []
        for benefit in self.benefits:
            segment = getattr(benefit, "eq_segment", None) or getattr(
                benefit, "eb_segment", None
            )
            if segment is None:
                continue
            value = getattr(segment, "service_type_code", None)
            if value is None:
                continue
            codes.extend(str(code) for code in _as_tuple(value))
        return tuple(codes)


class EligibilityAccess:
    """
    ``members()`` for the 270 and 271 transaction models.

    The inquiry and the response have identical loop names at every level this
    walks, so one traversal serves both.
    """

    def members(self) -> Iterator[EligibilityMember]:
        """
        Yields every person the transaction is about, in file order.

        Subscribers who are themselves the patient and dependents both appear;
        ``EligibilityMember.is_dependent`` says which, and ``member`` already
        points at the right loop either way.
        """
        for loop_2000a in self.loop_2000a:
            payer = loop_2000a.loop_2100a
            for loop_2000b in loop_2000a.loop_2000b:
                provider = loop_2000b.loop_2100b
                for loop_2000c in loop_2000b.loop_2000c or []:
                    subscriber = loop_2000c.loop_2100c
                    dependents = loop_2000c.loop_2000d or []
                    own_benefits = _as_tuple(getattr(subscriber, "loop_2110c", None))

                    # The subscriber is a member in their own right whenever
                    # the transaction says something about them, and also when
                    # they are the only person in the record. A subscriber who
                    # carries benefits *and* has dependents is both, so
                    # yielding only the dependents would drop their coverage.
                    if own_benefits or not dependents:
                        yield EligibilityMember(
                            member=subscriber,
                            subscriber=subscriber,
                            payer=payer,
                            provider=provider,
                            benefits=own_benefits,
                            is_dependent=False,
                        )

                    for loop_2000d in dependents:
                        dependent = loop_2000d.loop_2100d
                        yield EligibilityMember(
                            member=dependent,
                            subscriber=subscriber,
                            payer=payer,
                            provider=provider,
                            benefits=_as_tuple(getattr(dependent, "loop_2110d", None)),
                            is_dependent=True,
                        )


# --- 276 and 277 claim status ----------------------------------------------


@dataclass(frozen=True)
class TrackedClaim:
    """
    One claim being asked about on a 276 or reported on a 277.

    ``patient`` is loop 2100E when the patient is a dependent and the
    subscriber's own loop 2100D when they are not.
    """

    status: Any
    patient: Any
    subscriber: Any
    payer: Any
    requester: Any
    provider: Any
    is_dependent: bool

    @property
    def trace_number(self) -> Optional[str]:
        """TRN02, which ties an inquiry to the response answering it."""
        return self.status.trn_segment.reference_identification_1

    @property
    def patient_name(self) -> Tuple[Optional[str], Optional[str]]:
        return _name(self.patient.nm1_segment)

    @property
    def member_id(self) -> Optional[str]:
        return self.subscriber.nm1_segment.identification_code

    @property
    def payer_name(self) -> Optional[str]:
        return _name(self.payer.nm1_segment)[0]

    @property
    def provider_name(self) -> Optional[str]:
        return _name(self.provider.nm1_segment)[0]

    @property
    def statuses(self) -> Tuple[Any, ...]:
        """The STC segments. Empty on a 276, which asks rather than answers."""
        return _as_tuple(getattr(self.status, "stc_segment", None))

    @property
    def charge(self) -> Optional[Decimal]:
        """
        What was billed.

        The inquiry states it in AMT*T3 and the response in STC04, so the
        caller does not have to know which transaction it is holding.
        """
        amt_segment = getattr(self.status, "amt_segment", None)
        if amt_segment is not None:
            return amt_segment.monetary_amount
        for stc in self.statuses:
            if stc.total_claim_charge_amount is not None:
                return stc.total_claim_charge_amount
        return None

    @property
    def paid(self) -> Optional[Decimal]:
        """STC05, present only on a response."""
        for stc in self.statuses:
            if stc.claim_payment_amount is not None:
                return stc.claim_payment_amount
        return None


class ClaimStatusAccess:
    """
    ``claims()`` for the 276 and 277 transaction models.

    The inquiry and the response have identical loop names at every level this
    walks, so one traversal serves both.
    """

    def claims(self) -> Iterator[TrackedClaim]:
        """
        Yields every tracked claim in the transaction, in file order.

        A claim hangs off the subscriber when the subscriber is the patient
        and off the dependent otherwise, never both.
        """
        for loop_2000a in self.loop_2000a:
            payer = loop_2000a.loop_2100a
            for loop_2000b in loop_2000a.loop_2000b or []:
                requester = loop_2000b.loop_2100b
                for loop_2000c in loop_2000b.loop_2000c or []:
                    provider = loop_2000c.loop_2100c
                    for loop_2000d in loop_2000c.loop_2000d or []:
                        subscriber = loop_2000d.loop_2100d
                        context = {
                            "subscriber": subscriber,
                            "payer": payer,
                            "requester": requester,
                            "provider": provider,
                        }

                        for status in loop_2000d.loop_2200d or []:
                            yield TrackedClaim(
                                status=status,
                                patient=subscriber,
                                is_dependent=False,
                                **context,
                            )

                        for loop_2000e in loop_2000d.loop_2000e or []:
                            dependent = loop_2000e.loop_2100e
                            for status in loop_2000e.loop_2200e or []:
                                yield TrackedClaim(
                                    status=status,
                                    patient=dependent,
                                    is_dependent=True,
                                    **context,
                                )


__all__ = [
    "ClaimStatusAccess",
    "ClaimSubmissionAccess",
    "EligibilityAccess",
    "EligibilityMember",
    "PaidClaim",
    "RemittanceAccess",
    "SubmittedClaim",
    "Subscriber",
    "TrackedClaim",
]
