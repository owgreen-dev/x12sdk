# Reading and writing X12

## Reading

{mod}`x12sdk.io` streams either raw segments or validated transaction models
from a file or from text.

Segments (each a name plus a list of fields):

```python
from x12sdk.io import X12SegmentReader

with X12SegmentReader("inquiry.270") as reader:
    for segment_name, segment_fields in reader.segments():
        print(segment_name, segment_fields)
```

Models (validated; one per transaction set):

```python
from x12sdk.io import X12ModelReader

with X12ModelReader("remit.835") as reader:
    for model in reader.models():
        print(model.header, model.footer)   # common to every transaction
        model.x12()                         # serialize back to X12
```

Files are read one transaction at a time; a transaction is validated as a
whole. An invalid one raises Pydantic's `ValidationError`;
{func}`x12sdk.validation.problems` turns it into plain language.

## Reaching the claims

The models mirror the X12 loop hierarchy, so a claim is several levels down,
and on an 837 it is down one of *two* paths:

```text
loop_2000a[i].loop_2000b[j].loop_2300[k]                  patient = subscriber
loop_2000a[i].loop_2000b[j].loop_2000c[l].loop_2300[k]    patient = dependent
```

Both are ordinary. Code written against one runs happily on a file that uses
the other and reports no claims at all, so `claims()` walks both and yields a
flat record. It is a generator, so a large file is never materialized.

```python
for claim in model.claims():
    print(claim.patient_control_number, claim.charge, claim.patient_name)
```

| Transaction | Accessor | Yields |
|---|---|---|
| 837P, 837I, 837D | `claims()` | {class}`~x12sdk.access.SubmittedClaim`: the claim with `billing_provider`, `subscriber`, `payer`, `patient`, `is_dependent`, `relationship` |
| 837P, 837I, 837D | `subscribers()` | {class}`~x12sdk.access.Subscriber` with their dependents |
| 835 | `claims()` | {class}`~x12sdk.access.PaidClaim`: `charge`, `paid`, `status`, `adjustments`, `service_lines`, `header_number` |
| 270, 271 | `members()` | {class}`~x12sdk.access.EligibilityMember` with their benefits |
| 276, 277 | `claims()` | {class}`~x12sdk.access.TrackedClaim`; the charge comes from AMT on an inquiry and STC on a response |

`patient` already points at whoever was treated, so you never need to know
which branch a claim came from.

## Writing

The transaction models cover ST through SE.
{func}`~x12sdk.io.write_transactions` adds the interchange and functional
group envelopes and keeps the control numbers consistent:

```python
from x12sdk.io import X12ModelReader, write_transactions

with X12ModelReader("in.835") as reader:
    transactions = list(reader.models())

out = write_transactions(transactions, sender_id="SENDERID", receiver_id="RECEIVERID")
```

{class}`~x12sdk.io.X12ModelWriter` is the same as a context manager: write
models into it and the interchange is assembled when the block exits. If the
block raises, nothing is written.

```python
from x12sdk.io import X12ModelReader, X12ModelWriter

with X12ModelReader("in.835") as reader, X12ModelWriter(
    "out.835", sender_id="SENDERID", receiver_id="RECEIVERID"
) as writer:
    for model in reader.models():
        if model.header.st_segment.transaction_set_control_number != "0003":
            writer.write(model)   # drop one transaction, keep the rest
```

The destination can be a path, an open text stream, or nothing, in which
case the result is on `writer.interchange` after the block.
