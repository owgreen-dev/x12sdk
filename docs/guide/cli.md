# Command line

Installing x12sdk puts these commands on your path. Each reads files
locally; nothing is uploaded.

| Command | Does |
|---|---|
| `x12sdk-table` | An 835 or 837 as CSV, one row per service line ([Tables](tables.md)) |
| `x12sdk-validate` | Valid, or where each file breaks; exits 1 if any is invalid ([Checking files](validation.md)) |
| `x12sdk-generate` | A synthetic file of any supported set ([Generating](generating.md)) |
| `x12sdk` | A file as JSON, segment by segment or model by model |
| `x12sdk-mcp` | The [MCP server](mcp.md), with the `mcp` extra |

## x12sdk-table

```shell
x12sdk-table remit.835 -o remit.csv
x12sdk-table claims.837 > claims.csv
```

## x12sdk-validate

```shell
x12sdk-validate claims.837 remit.835
x12sdk-validate --json remit.835      # one JSON object per file
```

## x12sdk-generate

One subcommand per transaction set, every option a keyword argument of the
matching `generate_*` function, so the command and the library call produce
the same bytes.

```shell
x12sdk-generate 835 --seed 7 --claims 2                     # to standard output
x12sdk-generate 837p --seed 7 --claims 25 --dependent-rate 0.5 --out claims.837
x12sdk-generate 837d --claims 10 --payer-name "EXAMPLE DENTAL PLAN"
x12sdk-generate 834 --enrollees 10 --sponsor-name "EXAMPLE EMPLOYER"
x12sdk-generate 270 --members 3 -o inquiry.270 && x12sdk-generate 271 --members 3 -o response.271
x12sdk-generate 835 --claims 10 --provider-adjustments 2   # two PLB adjustments; 0 for none
```

The count option is named for what the set carries (`--claims`,
`--enrollees`, `--members`, `--patients`); `-n` works for all of them.
`x12sdk-generate SET --help` lists a set's options.

## x12sdk

```text
usage: x12sdk [-h] [-s | -m] [-x] [-p] [-d] file

  -s, --segment     Returns X12 segments
  -m, --model       Returns X12 models
  -x, --exclude     Exclude fields set to None in model output
  -p, --pretty      Pretty print output
  -d, --delimiters  Include X12 delimiters in output (model mode only)
```

```shell
x12sdk -s -p inquiry.270   # segments
x12sdk -m -p inquiry.270   # models
```
