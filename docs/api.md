# API reference

The public modules, from their docstrings. The transaction models themselves
(`x12sdk.v5010.*`) mirror the implementation guides loop by loop and are
best explored from a parsed file, or with `x12sdk -m -p file`.

## Tables

```{eval-rst}
.. automodule:: x12sdk.tables
   :members: iter_lines, read_lines, to_dataframe, write_csv, remittance_lines, claim_lines, REMITTANCE_COLUMNS, CLAIM_COLUMNS
```

## Validation

```{eval-rst}
.. automodule:: x12sdk.validation
   :members: check, problems, CheckResult, Problem, Transaction
```

## Matching

```{eval-rst}
.. automodule:: x12sdk.matching
   :members: match_claims, match_rows, Match, MATCH_COLUMNS, OUTCOMES
```

## Reading and writing

```{eval-rst}
.. automodule:: x12sdk.io
   :members: X12SegmentReader, X12ModelReader, X12ModelWriter, write_transactions
```

## Accessors

```{eval-rst}
.. automodule:: x12sdk.access
   :members: SubmittedClaim, Subscriber, PaidClaim, EligibilityMember, TrackedClaim
```

(generating)=
## Generating

```{eval-rst}
.. automodule:: x12sdk.generate
   :members: generate_835, generate_837p, generate_837i, generate_837d, generate_claim_pair, generate_270, generate_271, generate_276, generate_277, generate_834, ClaimPair, ClaimSpec, ServiceLineSpec, PatientSpec, SubmissionSpec, ProviderAdjustmentSpec, MemberSpec, BenefitSpec, EligibilitySpec, StatusPatientSpec, TrackedClaimSpec, ClaimStatusSpec, EnrolleeSpec, EnrollmentSpec, EmployerSpec, DisabilitySpec, CoverageSpec, denial, provider_adjustment, patient_responsibility
```

## Denial analytics

```{eval-rst}
.. automodule:: x12sdk.denials
   :members: iter_adjustments, denial_summary, categorize, category_map, describe, load_code_descriptions, to_dataframe, Adjustment, DenialSummaryRow
```
