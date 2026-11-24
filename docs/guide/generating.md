# Generating synthetic files

There is no shareable corpus of real X12: every claim and remittance carries
protected health information. `x12sdk.generate` builds valid transactions
from the same models the parser produces, so test data is synthetic by
construction.

```python
from x12sdk.generate import generate_835, generate_837p

remittance = generate_835(seed=7, claims=25)    # a complete file, envelope included
submission = generate_837p(seed=7, claims=25)
```

or from the shell, with the same bytes:

```shell
x12sdk-generate 835 --seed 7 --claims 25 -o remit.835
```

## Guarantees

- **The same seed reproduces the same bytes**, and generation never touches
  the global random state, so it is safe inside someone else's test suite.
- **Every file is valid:** it parses through the library's own validators
  and round-trips byte for byte.
- **Both branches of the hierarchy appear.** In an 837 a claim sits under
  the subscriber when the patient is the subscriber, and under a dependent
  when they are not. Code that walks the hierarchy often handles only the
  first, so generated files contain both by default. `dependent_rate` sets
  the mix.

## Every supported set

| Call | Count argument | Notes |
|---|---|---|
| `generate_835` | `claims` | One PLB provider adjustment by default; `provider_adjustments` to choose |
| `generate_837p`, `generate_837i`, `generate_837d` | `claims` | Dental lines carry a tooth and surfaces where the procedure has them |
| `generate_270`, `generate_271` | `members` | The same seed and spec make a matched inquiry and response |
| `generate_276`, `generate_277` | `patients` | The same seed makes a matched inquiry and response |
| `generate_834` | `enrollees` | Several employers and disability periods per member by default |
| `generate_claim_pair` | `claims` | An 837 and the 835 that answers it; see [Pairs and matching](matching.md) |

## Describing a scenario

Pass specifications instead of a count to pin down exactly what is in the
file:

```python
from x12sdk.generate import ClaimSpec, ServiceLineSpec, denial, generate_835

spec = [
    ClaimSpec(
        charge="900.00",
        lines=[ServiceLineSpec(charge="900.00", procedure="99214",
                               adjustments=[denial("CO", "97", "300.00")])],
    )
]
remittance = generate_835(seed=1, claims=spec, payer_name="EXAMPLE HEALTH PLAN")
```

A claim's payment is derived as charge minus adjustments, so a specification
that would break the 835 balance rule cannot be written down.

To place each claim under a subscriber or a dependent yourself:

```python
from x12sdk.generate import (
    ClaimSpec, PatientSpec, ServiceLineSpec, SubmissionSpec, generate_837p
)

spec = SubmissionSpec(
    patients=[
        PatientSpec(
            claims=[ClaimSpec(charge="450.00",
                              lines=[ServiceLineSpec(charge="450.00",
                                                     procedure="99214")])],
            dependent=True,
            relationship="19",   # child
        )
    ]
)
submission = generate_837p(seed=1, claims=spec)
```

### Provider-level adjustments

A remittance can move money outside any claim, in the PLB segment: an
overpayment recovered, interest owed. The check amount in BPR02 is derived
from both:

```python
from x12sdk.generate import ClaimSpec, generate_835, provider_adjustment

remittance = generate_835(
    seed=1,
    claims=[ClaimSpec(charge="500.00")],
    provider_adjustments=[provider_adjustment("WO", "25.00", "PCN000099")],
)
# PLB*<payee NPI>*20251231*WO:PCN000099*25.00~   and   BPR*I*475.00*...
```

### Dental claims

On a dental claim a line's procedure is a CDT code, and a line done to a
tooth names it, with the surfaces treated for a filling:

```python
from x12sdk.generate import (
    ClaimSpec, PatientSpec, ServiceLineSpec, SubmissionSpec, generate_837d
)

spec = SubmissionSpec(
    patients=[
        PatientSpec(
            claims=[ClaimSpec(charge="395.00", lines=[
                ServiceLineSpec(charge="55.00", procedure="D0120"),
                ServiceLineSpec(charge="340.00", procedure="D2392",
                                tooth="19", surfaces=("M", "O")),
            ])]
        )
    ]
)
submission = generate_837d(seed=1, claims=spec)   # ... SV3*AD:D2392*340.00****1~ TOO*JP*19*M:O~
```

A tooth on an 837P or 837I is refused rather than dropped.

### Eligibility and claim status

```python
from x12sdk.generate import BenefitSpec, EligibilitySpec, MemberSpec
from x12sdk.generate import generate_270, generate_271, generate_276, generate_277

spec = EligibilitySpec(
    members=[MemberSpec(benefits=(BenefitSpec(service_type="35"),), dependent=True)]
)
inquiry = generate_270(seed=1, members=spec)
response = generate_271(seed=1, members=spec)

status_inquiry = generate_276(seed=9, patients=8)
status_response = generate_277(seed=9, patients=8)
```

### Enrollment

A member on an 834 can have up to three employers (2100D) and several
disability periods (2200); a parser that keeps only the last of each looks
correct on most files. Invented rosters exercise both by default; to pin them
down:

```python
from x12sdk.generate import DisabilitySpec, EmployerSpec, EnrolleeSpec, EnrollmentSpec, generate_834

roster = EnrollmentSpec(
    enrollees=[
        EnrolleeSpec(
            employers=[EmployerSpec("FIRST EMPLOYER"), EmployerSpec("SECOND EMPLOYER")],
            disabilities=[
                DisabilitySpec(type="2", begins="20250101", ends="20250601"),
                DisabilitySpec(type="3", begins="20250701"),
            ],
        )
    ]
)
enrollment = generate_834(seed=1, enrollees=roster)
```

Every specification class and generator is listed in the
[API reference](../api.md#generating).
