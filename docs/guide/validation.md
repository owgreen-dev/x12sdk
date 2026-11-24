# Checking files

```shell
x12sdk-validate claims.837 remit.835
```

```text
claims.837: valid — 1 transaction (837, 005010X222A2), 12 claims
remit.835: INVALID
  loop 2000A #1 › loop 2000B #1 › loop 2300 #1: Claim Amount 9161.47 != Service Line Total 161.47
```

Every problem names **where** it is, as a path through the loops a person
can follow in the file, and **what** is wrong, in words. The file's content
is never echoed, so the output is safe to paste into a ticket.

The command exits 1 if any file is invalid, so it can gate a build or a
pre-submission step. `--json` prints one record per file:

```shell
x12sdk-validate --json remit.835
```

## What is checked

The file is parsed into the models for its implementation guide, and the
rules those models carry are enforced as it is, for example:

- a required segment is missing;
- a code value is not one the guide allows;
- a claim's total does not match its service lines;
- the transaction's segment count (SE01) is wrong;
- the hierarchy's parent ids do not line up.

These are the structural and arithmetic rules of the implementation guide,
not a payer's own edits.

A file that cannot be read as X12 at all is reported as such ("not an X12
file", "the interchange envelope is incomplete or malformed") rather than
with a traceback.

## From Python

```python
from x12sdk.validation import check

result = check("remit.835")          # a path or X12 text
if not result.valid:
    for problem in result.problems:
        print(problem.where, "—", problem.message)
else:
    for transaction in result.transactions:
        print(transaction.transaction_set, transaction.implementation, transaction.claims)
```

{func}`~x12sdk.validation.problems` turns the `ValidationError` raised by
{class}`~x12sdk.io.X12ModelReader` into the same plain-language list, for
code that reads files itself.

## In the browser

The [playground](https://huggingface.co/spaces/owgreen-dev/x12sdk-playground)
runs the same check on a pasted or dropped file, inside your browser tab.
