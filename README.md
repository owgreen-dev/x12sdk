# x12sdk

[![x12sdk MCP server](https://glama.ai/mcp/servers/owgreen-dev/x12sdk/badges/score.svg)](https://glama.ai/mcp/servers/owgreen-dev/x12sdk)

Read, check and generate HIPAA X12 health care transactions in Python:
claims (837P, 837I, 837D), remittances (835), eligibility (270/271), claim
status (276/277) and enrollment (834).

**[Try it in your browser](https://huggingface.co/spaces/owgreen-dev/x12sdk-playground)**:
check a file and see where it breaks, turn an 835 into a CSV, or generate
sample files, with nothing to install. The page runs x12sdk in your browser
tab, so your file is never uploaded.

- **835 or 837 to a spreadsheet:** `x12sdk-table remit.835 -o remit.csv`, one
  row per service line.
- **Sample files with no PHI:** realistic synthetic claims and remittances
  from a seed, or a [ready-made dataset](https://huggingface.co/datasets/owgreen-dev/x12sdk)
  of 30,000 claims with their remittances.
- **Every transaction typed and checked:** each file parses into
  [Pydantic v2](https://docs.pydantic.dev/) models validated against the
  implementation guide rules, and writes back out byte for byte.
- **For AI assistants:** an [MCP server](#ai-assistants-mcp) that reads,
  checks and generates X12 through the library.

Everything runs locally; no file is uploaded anywhere.

## Common tasks

### Turn an 835 or 837 into a table

```shell
pip install x12sdk
x12sdk-table remit.835 -o remit.csv
```

```python
from x12sdk.tables import read_lines, to_dataframe

rows = read_lines("remit.835")       # list of dicts, one per service line
frame = to_dataframe("remit.835")    # pandas: pip install "x12sdk[pandas]"
```

An 835 becomes one row per paid service line: the payment, the claim, the
patient, the procedure, what was charged and paid, and the adjustments totalled
by group (`co_amount`, `pr_amount`, `oa_amount`, `pi_amount`, `cr_amount`)
alongside every `GROUP-REASON` code. An 837 (professional, institutional or
dental) becomes one row per billed line, with diagnoses, revenue codes and
teeth where they apply. Claim rows and remittance rows join on
`patient_control_number` (CLM01 = CLP01). The columns are fixed
(`x12sdk.tables.REMITTANCE_COLUMNS`, `CLAIM_COLUMNS`), so a pipeline built on
them does not move. For one row per adjustment instead, see
[Denial analytics](#denial-analytics).

### Get sample 837 and 835 files

There is no shareable corpus of real X12: every claim and remittance carries
protected health information. x12sdk generates valid files from a seed
instead:

```shell
x12sdk-generate 835 --seed 7 --claims 2 --payer-name "EXAMPLE HEALTH PLAN" --payee-name "EXAMPLE MEDICAL GROUP"
```

or, from Python:

```python
from x12sdk.generate import generate_835

print(generate_835(seed=7, claims=2, payer_name="EXAMPLE HEALTH PLAN",
                   payee_name="EXAMPLE MEDICAL GROUP"))
```

Either way:

```
ISA*00*          *00*          *30*SYNTHETICPAYER *30*SYNTHETICPROV  *260101*1200*^*00501*000000001*0*T*:~
GS*HP*SYNTHETICPAYER*SYNTHETICPROV*20260101*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*1734.53*C*CHK~
TRN*1*0922121677*1661318600~
N1*PR*EXAMPLE HEALTH PLAN~
N3*9265 MAIN AVE~
N4*FRANKLIN*IL*85642~
N1*PE*EXAMPLE MEDICAL GROUP*XX*1260181593~
LX*1~
CLP*PCN000001*1*1797.81*1258.47**CH*148194179472~
NM1*QC*1*ANDERSON*LINDA****MI*X410965605~
SVC*HC:71046*1797.81*1258.47**1~
CAS*CO*45*539.34~
...
PLB*1260181593*20251231*L6*-8.63~
SE*20*0001~
GE*1*1~
IEA*1*000000001~
```

The same seed reproduces the same bytes. Every file parses through the
library's own validators, round-trips byte for byte, and carries both the
subscriber and the dependent branch of the hierarchy, the place real code
loses claims. All nine supported transaction sets generate, a claim can be
generated together with the remittance that answers it, and scenarios can be
described exactly, from a denial pattern to a multi-employer enrollment. See
[Generating synthetic files](#generating-synthetic-files), or download the
[dataset](https://huggingface.co/datasets/owgreen-dev/x12sdk).

### Check a file

```shell
x12sdk-validate claims.837 remit.835
```

```
claims.837: valid — 1 transaction (837, 005010X222A2), 12 claims
remit.835: INVALID
  loop 2000A #1 › loop 2000B #1 › loop 2300 #1: Claim Amount 9161.47 != Service Line Total 161.47
```

It exits 1 if any file is invalid, so it can gate a build; `--json` prints
one record per file. A claim whose total does not match its lines, a missing
required segment, an unknown code value, a wrong segment count, a hierarchy
whose parent ids do not line up: each is reported with where it is, without
echoing the file's content. From Python, `x12sdk.validation.check(path)`
returns the same result.

### Match remittances to claims

```python
from x12sdk.matching import match_claims, match_rows

for match in match_claims("claims.837", ["remit-1.835", "remit-2.835"]):
    print(match.patient_control_number, match.outcome, match.billed, match.paid)
```

Claims and payments join on the patient control number (CLM01 = CLP01).
Every payment for a number is kept (a payment, a reversal, a corrected
payment), and nothing is dropped: a claim no remittance answers is
`no remittance`, a payment for a claim you did not give is `no claim`.
`match_rows` gives the same as flat rows for a CSV or a DataFrame.

### Performance

Files are read one transaction at a time; a transaction is validated as a
whole, so it is held in memory as a whole. From `python scripts/benchmark.py`
on an Apple-silicon Mac, Python 3.12, one transaction per file:

| File | Claims | Size | Read and validate | Peak memory |
|---|---:|---:|---:|---:|
| 835 | 10,000 | 1.6 MB | 1.2 s (about 8,200 claims/s) | 203 MB |
| 837P | 10,000 | 4.4 MB | 4.7 s (about 2,100 claims/s) | 536 MB |

Memory grows with the size of the largest transaction, not of the file; a
file of many moderate transactions streams in roughly constant memory. Run the
script on your own machine for your own numbers.

![License](https://img.shields.io/github/license/owgreen-dev/x12sdk)
![CI](https://github.com/owgreen-dev/x12sdk/actions/workflows/continuous-integration.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)

> x12sdk is the maintained continuation of
> [LinuxForHealth x12](https://github.com/LinuxForHealth/x12), which stopped at
> 0.57.0 in June 2022. It runs on **Pydantic v2 and Python 3.10–3.14**.

Supported transaction sets:

| Set | Implementation | What it is | Parse | Generate | Accessors |
|---|---|---|---|---|---|
| 837P | 005010X222A2 | Professional claim | yes | `generate_837p` | `claims()`, `subscribers()` |
| 837I | 005010X223A3 | Institutional claim | yes | `generate_837i` | `claims()`, `subscribers()` |
| 837D | 005010X224A2 | Dental claim | yes | `generate_837d` | `claims()`, `subscribers()` |
| 835 | 005010X221A1 | Claim payment / remittance advice | yes | `generate_835` | `claims()` |
| 834 | 005010X220A1 | Benefit enrollment and maintenance | yes | `generate_834` | |
| 270 / 271 | 005010X279A1 | Eligibility inquiry / response | yes | `generate_270` / `generate_271` | `members()` |
| 276 / 277 | 005010X212 | Claim status inquiry / response | yes | `generate_276` / `generate_277` | `claims()` |

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

## Reaching the claims

The models mirror the X12 loop hierarchy, so a claim is several levels down.
On an 837 it is down one of *two* paths, because a claim sits under the
subscriber when the patient is the subscriber and under a dependent when they
are not:

```
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

Each record carries the claim plus the context you would otherwise re-derive:
`billing_provider`, `subscriber`, `payer`, `patient`, `is_dependent` and
`relationship`. `patient` already points at whoever was treated, so you never
need to know which branch the claim came from. `subscribers()` yields the
subscribers and their dependents.

`claims()` on an 835 yields the claim payments, each with `charge`, `paid`,
`status`, `adjustments`, `service_lines` and the LX `header_number`.

The eligibility and claim status pairs branch the same way, so they have
accessors too. `members()` on a 270 or 271 yields whoever the transaction is
about, with their benefits; `claims()` on a 276 or 277 yields the tracked
claims. Both hide the subscriber and dependent branch the same way `claims()`
does on an 837:

```python
for member in eligibility.members():
    print(member.name, member.is_dependent, member.service_type_codes)

for claim in status.claims():
    print(claim.trace_number, claim.charge, claim.paid)
```

A tracked claim reads its charge from AMT on an inquiry and from STC on a
response, so the caller does not have to know which it is holding.

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

`x12sdk-generate` is the shell form of [`x12sdk.generate`](#generating-synthetic-files):
one subcommand per transaction set, every option a keyword argument of the
matching `generate_*` function, so the command and the library call produce the
same bytes.

```shell
x12sdk-generate --help
usage: x12sdk-generate [-h] [--version] SET ...

positional arguments:
  SET         which transaction set to generate
    835       claim payment / remittance advice
    837p      professional claim
    837i      institutional claim
    837d      dental claim
    834       benefit enrollment and maintenance
    270       eligibility inquiry
    271       eligibility response
    276       claim status inquiry
    277       claim status response
```

```shell
x12sdk-generate 835 --seed 7 --claims 2                     # to stdout
x12sdk-generate 837p --seed 7 --claims 25 --dependent-rate 0.5 --out claims.837
x12sdk-generate 837d --claims 10 --payer-name "EXAMPLE DENTAL PLAN"
x12sdk-generate 834 --enrollees 10 --sponsor-name "EXAMPLE EMPLOYER"
x12sdk-generate 270 --members 3 -o inquiry.270 && x12sdk-generate 271 --members 3 -o response.271
x12sdk-generate 835 --claims 10 --provider-adjustments 2   # two PLB adjustments; 0 for none
```

The count option is named for what the set carries (`--claims`, `--enrollees`,
`--members`, `--patients`); `-n` works for all of them.

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

`X12ModelWriter` is the same thing as a context manager, the mirror image of
the reader: write models into it and the interchange is assembled when the
block exits. If the block raises, nothing is written.

```python
from x12sdk.io import X12ModelReader, X12ModelWriter

with X12ModelReader("in.835") as reader, X12ModelWriter(
    "out.835", sender_id="SENDERID", receiver_id="RECEIVERID"
) as writer:
    for model in reader.models():
        if model.header.st_segment.transaction_set_control_number != "0003":
            writer.write(model)   # drop one transaction, keep the rest
```

The destination can be a path, an open text stream, or nothing at all, in
which case the result is on `writer.interchange` after the block.

## Generating synthetic files

Real claims and remittances contain PHI, and there is no public X12 corpus to
test against. `x12sdk.generate` builds valid transactions from the same models
the parser produces, so your test data is guaranteed synthetic.

```python
from x12sdk.generate import generate_835

remittance = generate_835(seed=7, claims=25)   # a complete file, envelope included
```

The same seed always produces the same bytes, and generation never touches the
global random state, so it is safe inside someone else's test suite. The same
calls are available from the shell as [`x12sdk-generate`](#cli).

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

A remittance can also move money outside any claim, in the PLB segment: an
overpayment recovered, interest owed. Invented remittances carry one such
adjustment by default; a described scenario carries only what it describes,
and the check amount in BPR02 is derived from both:

```python
from x12sdk.generate import ClaimSpec, generate_835, provider_adjustment

remittance = generate_835(
    seed=1,
    claims=[ClaimSpec(charge="500.00")],
    provider_adjustments=[provider_adjustment("WO", "25.00", "PCN000099")],
)
# PLB*<payee NPI>*20251231*WO:PCN000099*25.00~   and   BPR*I*475.00*...
```

An enrollment roster has its own repeating loops that readers get wrong: a
member can have up to three employers (2100D) and several disability periods
(2200), and a parser that keeps only the last of each looks correct on most
files. Invented rosters exercise both by default; to pin them down:

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

## Denial analytics

An 835 tells you what a payer did to a claim, but in a shape built for
transmission: adjustments nested at claim and service line level, up to six
reason/amount pairs per CAS segment, remark codes in a different segment
again. `x12sdk.denials` flattens that to one record per reason code and
aggregates it the way a revenue-cycle or payer analytics team asks the
question.

```python
from x12sdk.io import X12ModelReader
from x12sdk.denials import denial_summary, iter_adjustments

with X12ModelReader("remit.835") as reader:
    for transaction in reader.models():
        rows = list(iter_adjustments(transaction))
        for row in denial_summary(rows):
            print(row.payer_name, row.group_code, row.reason_code,
                  row.category, row.claim_count, row.total_amount)
```

`denial_summary` counts payer-side groups (`CO`, `OA`, `PI`) by default and
leaves out patient cost share (`PR`), because a deductible is not a denial;
pass `include_patient_responsibility=True` to keep it. Amounts stay `Decimal`,
so totals are exact. `claim_count` counts distinct claims, so a reason hitting
three lines of one claim counts once.

For DataFrame work, install the extra and use `to_dataframe`:

```shell
pip install 'x12sdk[pandas]'
```

### Code lists

CARC and RARC **descriptions** are published by X12 and the Washington
Publishing Company and are licensed separately, so **x12sdk ships none of that
text**. What it ships is `categorize()`, x12sdk's own grouping of reason codes
into analysis categories such as `eligibility`, `authorization`, `duplicate`
and `timely_filing`, with anything unmapped resolving to `other`.

If you need the official wording, obtain the list from
[x12.org/codes](https://x12.org/codes) under whatever licence applies to you
and load it yourself:

```python
from x12sdk.denials import describe, load_code_descriptions

descriptions = load_code_descriptions("carc.csv")   # your file, not ours
for row in describe(denial_summary(rows), descriptions):
    print(row["reason_code"], row["description"], row["total_amount"])
```

Eligibility works the same way, and a 270 and the 271 answering it can be
generated as a matched pair from one specification. One inquiry may ask about
several service types, since EQ repeats:

```python
from x12sdk.generate import BenefitSpec, EligibilitySpec, MemberSpec
from x12sdk.generate import generate_270, generate_271

spec = EligibilitySpec(
    members=[MemberSpec(benefits=(BenefitSpec(service_type="35"),), dependent=True)]
)
inquiry = generate_270(seed=1, members=spec)
response = generate_271(seed=1, members=spec)
```

The eligibility transactions carry the same subscriber and dependent branch as
the 837, so generated files contain both by default here too.

Claim status works the same way. The 276 states what was billed, the 277
answers with an STC status, and on one seed the pair describes the same people
and the same claims:

```python
from x12sdk.generate import generate_276, generate_277

inquiry = generate_276(seed=9, patients=8)
response = generate_277(seed=9, patients=8)
```

Enrollment has no hierarchy to branch on. A dependent on an 834 is a separate
member record told apart by INS01 and INS02, not a loop nested under the
subscriber, and both kinds appear by default:

```python
from x12sdk.generate import generate_834

roster = generate_834(seed=3, enrollees=20)
```

All nine supported transaction sets can be generated. The institutional
and dental claims take the same specification as the professional one:

```python
from x12sdk.generate import generate_837i

submission = generate_837i(seed=7, claims=25)
```

On a dental claim a line's procedure is a CDT code, and a line done to a tooth
names it, with the surfaces treated for a filling. Invented files mix lines
with a tooth and lines without one (an exam, a cleaning):

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

### Matched claim and remittance pairs

A claim and the remittance that answers it can be generated together. Every
claim on the 837 is answered by exactly one claim payment on the 835, linked
as real files are, by CLM01 = CLP01, with the same charge, the same procedure
on each line, and the same patient, payer and payee. Outcomes are mixed by
default: some claims paid in full, most reduced by a contractual write-off,
some leaving a share to the patient, and a share denied outright
(`denial_rate`, 0.15 by default). Real pairs are PHI, so this is the only way
to have claims and their outcomes side by side in the open.

```python
from x12sdk.generate import generate_claim_pair

claim, remittance = generate_claim_pair(seed=7, claims=25, claim_type="837d")
```

`claim_type` is `"837p"`, `"837i"` or `"837d"`. To describe the outcome
yourself, give `ClaimSpec`s: the lines and charges are what was submitted, the
adjustments and `status` what the payer decided. The decision reaches the 835
and is kept off the 837:

```python
from x12sdk.generate import ClaimSpec, ServiceLineSpec, denial, generate_claim_pair

spec = [
    ClaimSpec(charge="120.00", status="4",   # denied
              lines=[ServiceLineSpec(charge="120.00", procedure="93000",
                                     adjustments=[denial("CO", "29", "120.00")])]),
]
claim, remittance = generate_claim_pair(seed=1, claims=spec)
```

Read both back with `claims()` and join on `patient_control_number`.

A prebuilt set of pairs, with the claims and service lines as tables, is
published as the [x12sdk synthetic claims and remittances](https://huggingface.co/datasets/owgreen-dev/x12sdk)
dataset; `scripts/build_dataset.py` rebuilds it byte for byte.

## AI assistants (MCP)

<!-- mcp-name: io.github.owgreen-dev/x12sdk -->

`x12sdk-mcp` is an [MCP](https://modelcontextprotocol.io) server, so an AI
assistant can read, check and generate X12 with the library instead of
guessing at the format. Install the optional extra:

```shell
pip install "x12sdk[mcp]"
claude mcp add x12sdk -- x12sdk-mcp      # Claude Code; other clients: run x12sdk-mcp over stdio
```

| Tool | What it does |
|---|---|
| `validate_x12` | Parses X12 text against the implementation guide; for an invalid file, where and why it failed |
| `parse_x12` | Each transaction as JSON, loop by loop |
| `list_claims` | One flat row per claim from an 837 (P, I or D), 835, 276 or 277 |
| `generate_x12` | A synthetic file of any supported set, reproducible from a seed |
| `generate_claim_pair` | A synthetic 837 and the 835 that answers it |

Every tool is read-only and works on the text it is given: the server never
opens files or the network, and refuses a file path rather than reading it.
What a tool returns does reach the assistant, though, so give it real claims
only if your organization is permitted to share PHI with that assistant. The
generators exist so that you need not.

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

`src/tests/audit/` is a suite of generic detectors, one per bug class that has
shipped here, run over every transaction set on every commit; it is described,
limits included, in [repo-docs/AUDIT.md](repo-docs/AUDIT.md).

Where the project is going, release by release, is in [ROADMAP.md](ROADMAP.md).

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
