"""
test_mcp_server.py

The MCP server is a thin layer over the library, so these tests check the
layer itself: every tool is registered and described, results are what the
library would return, a mistake comes back as a message the assistant can act
on, and nothing lets an assistant read a file off the machine.
"""

import anyio
import pytest

pytest.importorskip("mcp")

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

from x12sdk.generate import (  # noqa: E402
    generate_834,
    generate_837d,
    generate_claim_pair,
)
from x12sdk.generate.cli import _SETS  # noqa: E402
from x12sdk.io import X12ModelReader  # noqa: E402
from x12sdk.mcp_server import create_server  # noqa: E402

TOOL_NAMES = {
    "validate_x12",
    "parse_x12",
    "list_claims",
    "generate_x12",
    "generate_claim_pair",
}


@pytest.fixture(scope="module")
def server():
    return create_server()


def _call(server, name, **arguments):
    """Calls a tool as a client would and returns its structured result."""

    async def call():
        return await server.call_tool(name, arguments)

    result = anyio.run(call)
    assert not result.is_error
    return result.structured_content["result"]


def _tools(server):
    async def tools():
        return await server.list_tools()

    return {tool.name: tool for tool in anyio.run(tools)}


# --- registration ------------------------------------------------------------


def test_every_tool_is_registered_and_described(server):
    tools = _tools(server)
    assert set(tools) == TOOL_NAMES
    for tool in tools.values():
        assert tool.description and len(tool.description) > 40


def test_every_tool_declares_itself_read_only_and_closed_world(server):
    for tool in _tools(server).values():
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False


# --- reading -----------------------------------------------------------------


def test_a_valid_file_validates_and_names_its_transaction(server):
    result = _call(server, "validate_x12", x12=generate_837d(seed=1, claims=2))
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["transactions"] == [
        {
            "transaction_set": "837",
            "control_number": "0001",
            "implementation": "005010X224A2",
            "model": "HealthCareClaimDental",
        }
    ]


def test_an_invalid_file_says_where_and_why_without_echoing_it(server):
    broken = generate_837d(seed=1, claims=1).replace(
        "CLM*PCN000001*", "CLM*PCN000001*9", 1
    )
    result = _call(server, "validate_x12", x12=broken)
    assert result["valid"] is False
    (error,) = result["errors"]
    assert error["location"].startswith("loop_2000a.0.loop_2000b.0")
    assert "Claim Amount" in error["message"]
    assert "input_value" not in error["message"]
    assert "PCN000001" not in error["message"]


def test_leading_whitespace_is_tolerated(server):
    result = _call(server, "validate_x12", x12="\n  " + generate_837d(seed=1, claims=1))
    assert result["valid"] is True


def test_parse_returns_each_transaction_as_json(server):
    result = _call(server, "parse_x12", x12=generate_837d(seed=2, claims=1))
    (transaction,) = result["transactions"]
    assert (
        transaction["header"]["st_segment"]["transaction_set_identifier_code"] == "837"
    )
    assert result["errors"] == []


def test_listed_claims_join_across_a_pair_on_the_control_number(server):
    pair = generate_claim_pair(seed=4, claims=6, claim_type="837d")
    submitted = _call(server, "list_claims", x12=pair.claim)["claims"]
    paid = _call(server, "list_claims", x12=pair.remittance)["claims"]

    assert [c["transaction_set"] for c in submitted] == ["837"] * 6
    assert [c["transaction_set"] for c in paid] == ["835"] * 6
    by_number = {c["patient_control_number"]: c for c in paid}
    for claim in submitted:
        payment = by_number[claim["patient_control_number"]]
        assert payment["charge"] == claim["charge"]
        assert payment["patient"] == claim["patient"]
        assert payment["status"] in ("1", "4")


def test_listing_a_set_without_claims_says_so(server):
    result = _call(server, "list_claims", x12=generate_834(seed=1, enrollees=2))
    assert result["claims"] == []
    assert result["errors"] == [{"location": "", "message": "834 carries no claims"}]


# --- no file access -----------------------------------------------------------


@pytest.mark.parametrize("tool", ["validate_x12", "parse_x12", "list_claims"])
def test_a_file_path_is_refused_not_read(server, tool, tmp_path):
    """The reader accepts paths; the server must not let an assistant use that."""
    path = tmp_path / "claims.837"
    path.write_text(generate_837d(seed=1, claims=1))

    result = _call(server, tool, x12=str(path))
    assert result["errors"] == [
        {
            "location": "",
            "message": "expected X12 text beginning with ISA; file paths are not read",
        }
    ]
    assert "PCN000001" not in str(result)


# --- generating ---------------------------------------------------------------


@pytest.mark.parametrize("transaction_set", sorted(_SETS))
def test_every_set_generates_the_same_bytes_as_the_library(server, transaction_set):
    spec = _SETS[transaction_set]
    produced = _call(
        server, "generate_x12", transaction_set=transaction_set, count=2, seed=5
    )
    assert produced == spec.generate(seed=5, **{spec.count: 2})
    with X12ModelReader(produced) as reader:
        assert len(list(reader.models())) == 1


def test_a_generated_pair_is_the_librarys_pair(server):
    result = _call(server, "generate_claim_pair", claim_type="837P", claims=3, seed=2)
    pair = generate_claim_pair(seed=2, claims=3, claim_type="837p")
    assert result == {"claim": pair.claim, "remittance": pair.remittance}


@pytest.mark.parametrize(
    "name,arguments,message",
    [
        ("generate_x12", {"transaction_set": "999"}, "must be one of 835, 837p"),
        ("generate_x12", {"transaction_set": "835", "count": 0}, "at least 1"),
        (
            "generate_x12",
            {"transaction_set": "835", "dependent_rate": 0.5},
            "835 has no subscriber hierarchy",
        ),
        ("generate_claim_pair", {"claim_type": "835"}, "claim_type must be one of"),
    ],
)
def test_a_bad_argument_comes_back_as_a_message_to_act_on(
    server, name, arguments, message
):
    """MCP hides an exception's text unless it is a ToolError; these must show."""

    async def call():
        return await server.call_tool(name, arguments)

    with pytest.raises(ToolError, match=message):
        anyio.run(call)


# --- over the wire ---------------------------------------------------------------


def test_the_server_answers_a_real_client_over_stdio():
    """The way an assistant runs it: a subprocess speaking MCP on stdin/stdout."""
    import sys

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def session_round_trip():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "x12sdk.mcp_server"]
        )
        with anyio.fail_after(60):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    tools = await session.list_tools()
                    generated = await session.call_tool(
                        "generate_x12",
                        {"transaction_set": "837d", "count": 1, "seed": 2},
                    )
                    checked = await session.call_tool(
                        "validate_x12", {"x12": generated.content[0].text}
                    )
                    return init, tools, checked

    init, tools, checked = anyio.run(session_round_trip)
    assert init.server_info.name == "x12sdk"
    assert {tool.name for tool in tools.tools} == TOOL_NAMES
    assert checked.structured_content["result"]["valid"] is True
