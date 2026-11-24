# Install

```shell
pip install x12sdk
```

x12sdk needs Python 3.10 or later and depends only on Pydantic v2 and two
small configuration packages. Two features have optional extras:

| Extra | Adds | For |
|---|---|---|
| `pandas` | pandas | `to_dataframe` in [tables](guide/tables.md) and [denial analytics](guide/denials.md) |
| `mcp` | the MCP SDK | the [MCP server](guide/mcp.md), `x12sdk-mcp` |

```shell
pip install "x12sdk[pandas]"
pip install "x12sdk[mcp]"
```

Installing puts five commands on your path: `x12sdk`, `x12sdk-table`,
`x12sdk-validate`, `x12sdk-generate` and, with the `mcp` extra,
`x12sdk-mcp`. See [the CLI guide](guide/cli.md).

## From source

```shell
git clone https://github.com/owgreen-dev/x12sdk
cd x12sdk
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Without installing anything

The [browser playground](https://huggingface.co/spaces/owgreen-dev/x12sdk-playground)
runs the released library in your browser tab, so you can check a file, turn
it into a CSV or generate samples first. Files you open there are never
uploaded.
