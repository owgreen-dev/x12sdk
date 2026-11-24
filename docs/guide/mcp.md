# MCP server for AI assistants

`x12sdk-mcp` is an [MCP](https://modelcontextprotocol.io) server, so an AI
assistant can read, check and generate X12 with the library instead of
guessing at the format.

```shell
pip install "x12sdk[mcp]"
claude mcp add x12sdk -- x12sdk-mcp      # Claude Code; other clients: run x12sdk-mcp over stdio
```

It is listed in the official
[MCP Registry](https://registry.modelcontextprotocol.io) as
`io.github.owgreen-dev/x12sdk` and on
[Glama](https://glama.ai/mcp/servers/owgreen-dev/x12sdk).

| Tool | What it does |
|---|---|
| `validate_x12` | Parses X12 text against the implementation guide; for an invalid file, where and why it failed |
| `parse_x12` | Each transaction as JSON, loop by loop |
| `list_claims` | One flat row per claim from an 837 (P, I or D), 835, 276 or 277 |
| `generate_x12` | A synthetic file of any supported set, reproducible from a seed |
| `generate_claim_pair` | A synthetic 837 and the 835 that answers it |

## What it can and cannot reach

Every tool is read-only and works on the text it is given: the server never
opens files or the network, and refuses a file path rather than reading it.

What a tool returns does reach the assistant, though, so give it real claims
only if your organization is permitted to share PHI with that assistant. The
generators exist so that you need not.
