# x12sdk

Typed [Pydantic v2](https://docs.pydantic.dev/) models and a streaming SDK/CLI
for HIPAA ASC X12 5010 health care transactions.

![License](https://img.shields.io/github/license/owgreen-dev/x12sdk)
![CI](https://github.com/owgreen-dev/x12sdk/actions/workflows/continuous-integration.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

> x12sdk is the maintained continuation of
> [LinuxForHealth x12](https://github.com/LinuxForHealth/x12), which stopped at
> 0.57.0 in June 2022. It runs on **Pydantic v2 and Python 3.10–3.13**.

Supported transaction sets:

| Set | Implementation | What it is |
|---|---|---|
| 837P | 005010X222A2 | Professional claim |
| 837I | 005010X223A3 | Institutional claim |
| 835 | 005010X221A1 | Claim payment / remittance advice |
| 834 | 005010X220A1 | Benefit enrollment and maintenance |
| 270 / 271 | 005010X279A1 | Eligibility inquiry / response |
| 276 / 277 | 005010X212 | Claim status inquiry / response |

Every transaction is parsed into a validated Pydantic model and can be
serialized back to X12; the test suite asserts that round trip reproduces
each sample file byte for byte.

## Install

```shell
pip install x12sdk
```

From source:

```shell
git clone https://github.com/owgreen-dev/x12sdk
cd x12sdk
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## SDK

The `x12sdk.io` module streams either raw segments or validated transaction
models from a file.

Stream segments (each segment becomes its name plus a list of fields):

```python
from x12sdk.io import X12SegmentReader

with X12SegmentReader("/home/edi/270.x12") as r:
    for segment_name, segment_fields in r.segments():
        print(segment_name, segment_fields)
```

Stream models (the payload is validated; one model per transaction set):

```python
from x12sdk.io import X12ModelReader

with X12ModelReader("/home/edi/270.x12") as r:
    for model in r.models():
        print(model.header)   # common attributes: header, footer
        print(model.footer)
        model.x12()           # serialize back to X12
```

## CLI

```shell
x12sdk --help
usage: x12sdk [-h] [-s | -m] [-x] [-p] [-d] file

The x12sdk CLI parses and validates X12 messages.
Messages are returned in JSON format in either a segment or transactional format.

positional arguments:
  file              The path to a ASC X12 file

options:
  -h, --help        show this help message and exit
  -s, --segment     Returns X12 segments
  -m, --model       Returns X12 models
  -x, --exclude     Exclude fields set to None in model output
  -p, --pretty      Pretty print output
  -d, --delimiters  Include X12 delimiters in output (model mode only)
```

```shell
x12sdk -s -p demo-file/demo.270   # segments
x12sdk -m -p demo-file/demo.270   # models
```

## Writing X12

The transaction models cover ST through SE. `write_transactions` adds the
interchange and functional group envelopes and keeps the control numbers
consistent, so you get a file a trading partner would accept.

```python
from x12sdk.io import X12ModelReader, write_transactions

with X12ModelReader("in.835") as reader:
    transactions = list(reader.models())

out = write_transactions(transactions, sender_id="SENDERID", receiver_id="RECEIVERID")
```

## Generating synthetic files

Real claims and remittances contain PHI, and there is no public X12 corpus to
test against. `x12sdk.generate` builds valid transactions from the same models
the parser produces, so your test data is guaranteed synthetic.

```python
from x12sdk.generate import generate_835

remittance = generate_835(seed=7, claims=25)   # a complete file, envelope included
```

The same seed always produces the same bytes, and generation never touches the
global random state, so it is safe inside someone else's test suite.

To build a specific scenario, describe it:

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

Claim submissions work the same way:

```python
from x12sdk.generate import generate_837p

submission = generate_837p(seed=7, claims=25)
```

In an 837 a claim sits under the subscriber when the patient is the
subscriber, and under a dependent when they are not. Code that walks the
hierarchy often handles only the first, so generated files contain both by
default. Set `dependent_rate` to choose the mix, or pass a `SubmissionSpec`
to place each claim yourself:

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

## Migrating from `linuxforhealth-x12`

| before | after |
|---|---|
| `pip install linuxforhealth-x12` | `pip install x12sdk` |
| `from linuxforhealth.x12.io import X12ModelReader` | `from x12sdk.io import X12ModelReader` |
| `lfhx12 -m -p file.x12` | `x12sdk -m -p file.x12` |
| `lfhx12-api` (FastAPI endpoint) | removed; wrap the SDK in your own service |

See [CHANGELOG.md](CHANGELOG.md) for everything that changed.

## Development

```shell
pip install -e ".[dev]"
ruff check src
pytest --cov
```

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) (Apache-2.0,
DCO sign-off, no copyrighted standards text, no real PHI). To add a
transaction set, see [repo-docs/NEW_TRANSACTION.md](repo-docs/NEW_TRANSACTION.md);
the design is described in [repo-docs/DESIGN.md](repo-docs/DESIGN.md).

## Provenance and related work

x12sdk is a fork of **[LinuxForHealth x12](https://github.com/LinuxForHealth/x12)**
by Dixon Whitmire and the LinuxForHealth contributors (IBM), released under
the Apache License 2.0. The models, parser, readers, and test corpus
originate there; x12sdk exists to keep that work usable on current Python
and Pydantic. The original LICENSE is retained, and attribution and
trademark notes are in [NOTICE](NOTICE) and [TRADEMARK.md](TRADEMARK.md).
x12sdk is not affiliated with or endorsed by IBM, LinuxForHealth, or the
Linux Foundation.

- **[MdClarity/x12](https://github.com/MdClarity/x12)** — an independent
  fork by MD Clarity (Cary Lee) that completed a Pydantic v2 migration and
  added type checking and fuzzing in 2026. x12sdk's port is written
  separately from the 2022 upstream; their work is acknowledged here and
  their fixes are welcome upstream in x12sdk.
- **[pyx12](https://github.com/azoner/pyx12)** — the long-standing Python X12
  validator/converter (XML/dict output, map-driven). Choose pyx12 for
  validation against X12 maps; choose x12sdk for typed Python models.
- **[edi-835-parser](https://github.com/keiron-stoddart/edi-835-parser)** —
  a popular 835-only parser with pandas output.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
