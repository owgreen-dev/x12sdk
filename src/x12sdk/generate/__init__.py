"""
Synthetic X12 generation.

Real remittances and claims contain PHI and cannot be used as test data, and
no public healthcare X12 corpus exists. This builds valid transactions from
the same models the parser produces, so you can test an X12 pipeline against
files that are guaranteed to be synthetic.

Ask for a number of claims:

```python
from x12sdk.generate import generate_835

remittance = generate_835(seed=7, claims=25)   # a complete file, envelope included
```

Or describe exactly what you want, which is how you build a test case for a
particular denial pattern:

```python
from x12sdk.generate import ClaimSpec, ServiceLineSpec, denial, generate_835

spec = [
    ClaimSpec(
        charge="500.00",
        lines=[ServiceLineSpec(charge="500.00", adjustments=[denial("CO", "97", "150.00")])],
    )
]
remittance = generate_835(seed=1, claims=spec, payer_name="EXAMPLE HEALTH PLAN")
```

A claim's payment is always derived as charge minus adjustments, so a
specification that would break the 835 balance rule cannot be expressed.

Claim submissions work the same way:

```python
from x12sdk.generate import generate_837p

submission = generate_837p(seed=7, claims=25)
```

An 837 puts a claim under the subscriber when the patient is the subscriber
and under a dependent when they are not, and code that walks the hierarchy
often handles only the first. Generated files contain both by default; set
``dependent_rate`` to choose the mix, or give a ``SubmissionSpec`` to place
each claim yourself.

Output is deterministic: the same seed produces byte-identical bytes.
"""

import datetime
from typing import Optional, Sequence, Union

from ..io import write_transactions
from ._834 import build_834, random_enrollees
from ._835 import build_835, random_claims
from ._837i import build_837i
from ._837p import build_837p, claim_specs_to_patients, random_patients
from ._claim_status import build_276, build_277, random_status_patients
from ._eligibility import build_270, build_271, random_members
from ._spec import (
    BENEFIT_STATUS_CODES,
    GROUP_CODES,
    PATIENT_RELATIONSHIP_CODES,
    AdjustmentSpec,
    BenefitSpec,
    ClaimSpec,
    ClaimStatusSpec,
    CoverageSpec,
    EligibilitySpec,
    EnrolleeSpec,
    EnrollmentSpec,
    MemberSpec,
    PatientSpec,
    RemittanceSpec,
    ServiceLineSpec,
    StatusPatientSpec,
    SubmissionSpec,
    TrackedClaimSpec,
    denial,
    patient_responsibility,
)
from ._values import ValueFactory

#: Generation is reproducible, so the interchange timestamp is fixed rather
#: than read from the clock. Write the transaction yourself if you need a
#: real timestamp.
_EPOCH = datetime.datetime(2026, 1, 1, 12, 0)


def generate_835(
    *,
    seed: int = 0,
    claims: Union[int, Sequence[ClaimSpec]] = 5,
    payer_name: Optional[str] = None,
    payee_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPAYER",
    receiver_id: str = "SYNTHETICPROV",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 835 remittance advice.

    :param seed: Reproduces the same file when unchanged.
    :param claims: A number of claims to invent, or specifications to follow.
    :param payer_name: Defaults to a synthetic plan name.
    :param payee_name: Defaults to a synthetic provider name.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    if isinstance(claims, int):
        if claims < 1:
            raise ValueError("claims must be at least 1")
        claims = random_claims(claims, ValueFactory(seed))

    spec = RemittanceSpec(
        claims=list(claims), payer_name=payer_name, payee_name=payee_name
    )
    transaction = build_835(spec, seed=seed, control_number=control_number)
    return write_transactions(
        [transaction],
        sender_id=sender_id,
        receiver_id=receiver_id,
        # fixed so output depends only on the seed
        created=_EPOCH,
    )


def generate_837p(
    *,
    seed: int = 0,
    claims: Union[int, Sequence[ClaimSpec], SubmissionSpec] = 5,
    dependent_rate: float = 0.3,
    billing_provider_name: Optional[str] = None,
    payer_name: Optional[str] = None,
    submitter_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPROV",
    receiver_id: str = "SYNTHETICPAYER",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 837P professional claim submission.

    :param seed: Reproduces the same file when unchanged.
    :param claims: A number of claims to invent, specifications to follow, or a
        whole :class:`SubmissionSpec` when you want to place each claim on a
        particular patient.
    :param dependent_rate: The share of patients who are a dependent of the
        subscriber rather than the subscriber themselves, so generated files
        exercise both branches of the hierarchy. Ignored when a
        ``SubmissionSpec`` is given, which says where each claim goes.
    :param billing_provider_name: Defaults to a synthetic provider name.
    :param payer_name: Defaults to a synthetic plan name.
    :param submitter_name: Defaults to the billing provider.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    if isinstance(claims, SubmissionSpec):
        spec = claims
    else:
        values = ValueFactory(seed)
        if isinstance(claims, int):
            if claims < 1:
                raise ValueError("claims must be at least 1")
            patients = random_patients(claims, values, dependent_rate=dependent_rate)
        else:
            patients = claim_specs_to_patients(
                list(claims), values, dependent_rate=dependent_rate
            )
        spec = SubmissionSpec(
            patients=patients,
            billing_provider_name=billing_provider_name,
            payer_name=payer_name,
            submitter_name=submitter_name,
        )

    transaction = build_837p(spec, seed=seed, control_number=control_number)
    return write_transactions(
        [transaction],
        sender_id=sender_id,
        receiver_id=receiver_id,
        # fixed so output depends only on the seed
        created=_EPOCH,
    )


def _eligibility_spec(
    members, seed, dependent_rate, payer_name, provider_name
) -> EligibilitySpec:
    """Turns a count, a list of members, or a whole spec into a spec."""
    if isinstance(members, EligibilitySpec):
        return members
    if isinstance(members, int):
        if members < 1:
            raise ValueError("members must be at least 1")
        members = random_members(
            members, ValueFactory(seed), dependent_rate=dependent_rate
        )
    return EligibilitySpec(
        members=list(members), payer_name=payer_name, provider_name=provider_name
    )


def generate_270(
    *,
    seed: int = 0,
    members: Union[int, Sequence[MemberSpec], EligibilitySpec] = 5,
    dependent_rate: float = 0.3,
    payer_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPROV",
    receiver_id: str = "SYNTHETICPAYER",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 270 eligibility inquiry.

    :param seed: Reproduces the same file when unchanged.
    :param members: A number of members to invent, specifications to follow, or
        a whole :class:`EligibilitySpec`.
    :param dependent_rate: The share of members who are a dependent of the
        subscriber rather than the subscriber themselves, so generated files
        exercise both branches. Ignored when an ``EligibilitySpec`` is given.
    :param payer_name: Defaults to a synthetic plan name.
    :param provider_name: Defaults to a synthetic provider name.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    spec = _eligibility_spec(members, seed, dependent_rate, payer_name, provider_name)
    return write_transactions(
        [build_270(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


def generate_271(
    *,
    seed: int = 0,
    members: Union[int, Sequence[MemberSpec], EligibilitySpec] = 5,
    dependent_rate: float = 0.3,
    payer_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPAYER",
    receiver_id: str = "SYNTHETICPROV",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 271 eligibility response.

    Takes the same specification as :func:`generate_270`, so an inquiry and
    the response to it can be generated as a matched pair from one spec.

    :return: The interchange, ISA through IEA.
    """
    spec = _eligibility_spec(members, seed, dependent_rate, payer_name, provider_name)
    return write_transactions(
        [build_271(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


def _claim_status_spec(
    patients, seed, dependent_rate, payer_name, requester_name, provider_name
) -> ClaimStatusSpec:
    """Turns a count, a list of patients, or a whole spec into a spec."""
    if isinstance(patients, ClaimStatusSpec):
        return patients
    if isinstance(patients, int):
        if patients < 1:
            raise ValueError("patients must be at least 1")
        patients = random_status_patients(
            patients, ValueFactory(seed), dependent_rate=dependent_rate
        )
    return ClaimStatusSpec(
        patients=list(patients),
        payer_name=payer_name,
        requester_name=requester_name,
        provider_name=provider_name,
    )


def generate_276(
    *,
    seed: int = 0,
    patients: Union[int, Sequence[StatusPatientSpec], ClaimStatusSpec] = 5,
    dependent_rate: float = 0.3,
    payer_name: Optional[str] = None,
    requester_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPROV",
    receiver_id: str = "SYNTHETICPAYER",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 276 claim status inquiry.

    :param seed: Reproduces the same file when unchanged.
    :param patients: A number of patients to invent, specifications to follow,
        or a whole :class:`ClaimStatusSpec`.
    :param dependent_rate: The share of patients who are a dependent of the
        subscriber rather than the subscriber themselves, so generated files
        exercise both branches. Ignored when a ``ClaimStatusSpec`` is given.
    :param payer_name: Defaults to a synthetic plan name.
    :param requester_name: The information receiver asking. Defaults to a
        synthetic name.
    :param provider_name: The service provider the claims belong to.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    spec = _claim_status_spec(
        patients, seed, dependent_rate, payer_name, requester_name, provider_name
    )
    return write_transactions(
        [build_276(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


def generate_277(
    *,
    seed: int = 0,
    patients: Union[int, Sequence[StatusPatientSpec], ClaimStatusSpec] = 5,
    dependent_rate: float = 0.3,
    payer_name: Optional[str] = None,
    requester_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPAYER",
    receiver_id: str = "SYNTHETICPROV",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 277 claim status response.

    Takes the same specification as :func:`generate_276` and stays in step with
    it on the same seed, so an inquiry and the response to it describe the same
    people and the same claims.

    :return: The interchange, ISA through IEA.
    """
    spec = _claim_status_spec(
        patients, seed, dependent_rate, payer_name, requester_name, provider_name
    )
    return write_transactions(
        [build_277(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


def generate_834(
    *,
    seed: int = 0,
    enrollees: Union[int, Sequence[EnrolleeSpec], EnrollmentSpec] = 5,
    dependent_rate: float = 0.3,
    sponsor_name: Optional[str] = None,
    payer_name: Optional[str] = None,
    sender_id: str = "SYNTHSPONSOR",
    receiver_id: str = "SYNTHETICPAYER",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 834 benefit enrollment and maintenance transaction.

    The 834 has no HL hierarchy: a dependent is a separate member record told
    apart by INS01 and INS02, not a loop nested under the subscriber. Both
    kinds of record appear by default so code reading an 834 can be tested on
    each.

    :param seed: Reproduces the same file when unchanged.
    :param enrollees: A number of members to invent, specifications to follow,
        or a whole :class:`EnrollmentSpec`.
    :param dependent_rate: The share of records marked as a dependent. Ignored
        when an ``EnrollmentSpec`` is given.
    :param sponsor_name: The plan sponsor. Defaults to a synthetic name.
    :param payer_name: Defaults to a synthetic plan name.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    if isinstance(enrollees, EnrollmentSpec):
        spec = enrollees
    else:
        if isinstance(enrollees, int):
            if enrollees < 1:
                raise ValueError("enrollees must be at least 1")
            enrollees = random_enrollees(
                enrollees, ValueFactory(seed), dependent_rate=dependent_rate
            )
        spec = EnrollmentSpec(
            enrollees=list(enrollees),
            sponsor_name=sponsor_name,
            payer_name=payer_name,
        )
    return write_transactions(
        [build_834(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


def generate_837i(
    *,
    seed: int = 0,
    claims: Union[int, Sequence[ClaimSpec], SubmissionSpec] = 5,
    dependent_rate: float = 0.3,
    billing_provider_name: Optional[str] = None,
    payer_name: Optional[str] = None,
    submitter_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPROV",
    receiver_id: str = "SYNTHETICPAYER",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 837I institutional claim submission.

    Takes the same specification as :func:`generate_837p`; a ServiceLineSpec's
    procedure becomes the SV2 procedure composite, billed under a revenue
    code. The subscriber/dependent branch is the same, and both appear by
    default.

    :return: The interchange, ISA through IEA.
    """
    if isinstance(claims, SubmissionSpec):
        spec = claims
    else:
        values = ValueFactory(seed)
        if isinstance(claims, int):
            if claims < 1:
                raise ValueError("claims must be at least 1")
            patients = random_patients(claims, values, dependent_rate=dependent_rate)
        else:
            patients = claim_specs_to_patients(
                list(claims), values, dependent_rate=dependent_rate
            )
        spec = SubmissionSpec(
            patients=patients,
            billing_provider_name=billing_provider_name,
            payer_name=payer_name,
            submitter_name=submitter_name,
        )
    return write_transactions(
        [build_837i(spec, seed=seed, control_number=control_number)],
        sender_id=sender_id,
        receiver_id=receiver_id,
        created=_EPOCH,
    )


__all__ = [
    "AdjustmentSpec",
    "BENEFIT_STATUS_CODES",
    "BenefitSpec",
    "ClaimSpec",
    "ClaimStatusSpec",
    "CoverageSpec",
    "EligibilitySpec",
    "EnrolleeSpec",
    "EnrollmentSpec",
    "GROUP_CODES",
    "MemberSpec",
    "PATIENT_RELATIONSHIP_CODES",
    "PatientSpec",
    "RemittanceSpec",
    "ServiceLineSpec",
    "StatusPatientSpec",
    "SubmissionSpec",
    "TrackedClaimSpec",
    "ValueFactory",
    "build_270",
    "build_271",
    "build_276",
    "build_277",
    "build_834",
    "build_835",
    "build_837i",
    "build_837p",
    "claim_specs_to_patients",
    "denial",
    "generate_270",
    "generate_271",
    "generate_276",
    "generate_277",
    "generate_834",
    "generate_835",
    "generate_837i",
    "generate_837p",
    "patient_responsibility",
    "random_claims",
    "random_enrollees",
    "random_members",
    "random_patients",
    "random_status_patients",
]
