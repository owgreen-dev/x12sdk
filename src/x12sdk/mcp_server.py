"""
mcp_server.py

An MCP server, so an AI assistant can read, check and generate X12 itself
instead of guessing at a format it cannot see inside. Install the extra and
point the assistant at the ``x12sdk-mcp`` command:

    pip install "x12sdk[mcp]"
    x12sdk-mcp            # speaks MCP over stdio

Five tools, each a thin layer over the library:

- ``validate_x12``: does it parse, and if not, where and why
- ``parse_x12``: the transactions as JSON
- ``list_claims``: one flat row per claim, from an 837, 835, 276 or 277
- ``generate_x12``: a synthetic file of any supported set
- ``generate_claim_pair``: a synthetic 837 and the 835 that answers it

The server runs locally and reads only what it is given; it never opens files
or the network. What a tool returns goes to the assistant, though, so X12
containing real patient data should only be given to an assistant your
organisation is permitted to share PHI with. The generators exist so that it
need not be.
"""

from __future__ import annotations

import functools
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from . import __version__
from .generate import generate_claim_pair as _generate_claim_pair
from .generate.cli import _SETS
from .io import X12ModelReader
from .support import is_x12_data, is_x12_file
from .validation import problems

INSTRUCTIONS = """
Tools for ASC X12 5010 health care transactions: 837P/837I/837D claims, 835
remittances, 834 enrollment, 270/271 eligibility, 276/277 claim status.
Use validate_x12 to check a file and see exactly which rule failed, parse_x12
for its full structure, and list_claims for a flat summary of the claims in it.
generate_x12 and generate_claim_pair produce synthetic, PHI-free files that are
reproducible from a seed; prefer them over inventing X12 by hand.
""".strip()


def _read(x12: str) -> List[Any]:
    """
    Parses X12 *text*. The reader also accepts a file path, which an assistant
    must not be able to use to read files off the machine, so anything that
    is not X12 text, or that happens to name a file, is refused.
    """
    x12 = x12.lstrip()
    if not is_x12_data(x12) or is_x12_file(x12):
        raise ValueError(
            "expected X12 text beginning with ISA; file paths are not read"
        )
    with X12ModelReader(x12) as reader:
        return list(reader.models())


def _errors(error: Exception) -> List[Dict[str, str]]:
    """
    Where and why a file failed, without echoing its content back: Pydantic's
    error carries the offending input, which may be large or sensitive.
    """
    return [
        {"location": problem.location, "message": problem.message}
        for problem in problems(error)
    ]


def _transaction(model: Any) -> Dict[str, Optional[str]]:
    st = model.header.st_segment
    return {
        "transaction_set": st.transaction_set_identifier_code,
        "control_number": st.transaction_set_control_number,
        "implementation": getattr(st, "implementation_convention_reference", None),
        "model": type(model).__name__,
    }


def validate_x12(x12: str) -> Dict[str, Any]:
    """
    Checks that X12 text parses into valid transactions.

    Every implementation-guide rule the library models is applied: required
    segments and loops, code values, segment counts, HL linkage, claim and
    remittance balancing. Returns ``valid``, the transactions found, and for
    an invalid file the location and reason of each failure.
    """
    try:
        models = _read(x12)
    except (ValidationError, ValueError, KeyError, IndexError) as error:
        return {"valid": False, "transactions": [], "errors": _errors(error)}
    return {
        "valid": bool(models),
        "transactions": [_transaction(model) for model in models],
        "errors": []
        if models
        else [{"location": "", "message": "no transactions found"}],
    }


def parse_x12(x12: str) -> Dict[str, Any]:
    """
    Parses X12 text and returns each transaction as JSON, loop by loop and
    segment by segment, with fields named as the implementation guide names
    them. Fields that are absent from the file are left out.
    """
    try:
        models = _read(x12)
    except (ValidationError, ValueError, KeyError, IndexError) as error:
        return {"transactions": [], "errors": _errors(error)}
    return {
        "transactions": [
            model.model_dump(mode="json", exclude_unset=True, exclude_none=True)
            for model in models
        ],
        "errors": [],
    }


def _name(parts) -> Optional[str]:
    last, first = parts
    return ", ".join(part for part in (last, first) if part) or None


def _money(value) -> Optional[str]:
    return None if value is None else str(value)


def _claim_row(transaction_set: str, claim: Any) -> Dict[str, Any]:
    """One claim as a flat row; which fields exist depends on the transaction."""
    if transaction_set == "837":
        return {
            "patient_control_number": claim.patient_control_number,
            "charge": _money(claim.charge),
            "patient": _name(claim.patient_name),
            "is_dependent": claim.is_dependent,
            "member_id": claim.member_id,
            "payer": claim.payer_name,
            "billing_provider": claim.billing_provider_name,
            "billing_provider_npi": claim.billing_provider_npi,
            "service_lines": len(claim.service_lines),
        }
    if transaction_set == "835":
        return {
            "patient_control_number": claim.patient_control_number,
            "status": claim.status,
            "charge": _money(claim.charge),
            "paid": _money(claim.paid),
            "patient": _name(claim.patient_name),
            "payer": claim.payer_name,
            "payee": claim.payee_name,
            "payer_claim_control_number": claim.payer_claim_control_number,
            "service_lines": len(claim.service_lines),
        }
    return {
        "trace_number": claim.trace_number,
        "charge": _money(claim.charge),
        "paid": _money(claim.paid),
        "patient": _name(claim.patient_name),
        "member_id": claim.member_id,
        "payer": claim.payer_name,
        "provider": claim.provider_name,
    }


def list_claims(x12: str) -> Dict[str, Any]:
    """
    Lists every claim in an 837 (P, I or D), 835, 276 or 277 as one flat row,
    whichever branch of the hierarchy it sits on. An 837 claim and its 835
    payment share ``patient_control_number`` (CLM01 = CLP01).
    """
    try:
        models = _read(x12)
    except (ValidationError, ValueError, KeyError, IndexError) as error:
        return {"claims": [], "errors": _errors(error)}
    claims = []
    skipped = []
    for model in models:
        transaction = _transaction(model)
        if not hasattr(model, "claims"):
            skipped.append(transaction["transaction_set"])
            continue
        for claim in model.claims():
            row = _claim_row(transaction["transaction_set"], claim)
            row["transaction_set"] = transaction["transaction_set"]
            claims.append(row)
    errors = [
        {"location": "", "message": f"{code} carries no claims"}
        for code in sorted(set(skipped))
    ]
    return {"claims": claims, "errors": errors}


def generate_x12(
    transaction_set: str,
    count: int = 5,
    seed: int = 0,
    dependent_rate: Optional[float] = None,
) -> str:
    """
    Generates a synthetic, PHI-free X12 interchange (ISA through IEA).

    :param transaction_set: One of 835, 837p, 837i, 837d, 834, 270, 271, 276,
        277.
    :param count: How many claims, members, enrollees or patients to invent.
    :param seed: The same seed always produces the same bytes.
    :param dependent_rate: The share of people who are a dependent rather than
        the subscriber, for the sets with a subscriber hierarchy.
    """
    code = transaction_set.lower()
    if code not in _SETS:
        raise ValueError(
            f"transaction_set must be one of {', '.join(_SETS)}, got {transaction_set!r}"
        )
    spec = _SETS[code]
    kwargs: Dict[str, Any] = {"seed": seed, spec.count: count}
    if dependent_rate is not None:
        if not spec.dependent_rate:
            raise ValueError(f"{code} has no subscriber hierarchy; omit dependent_rate")
        kwargs["dependent_rate"] = dependent_rate
    return spec.generate(**kwargs)


def generate_claim_pair(
    claim_type: str = "837p",
    claims: int = 5,
    seed: int = 0,
    denial_rate: float = 0.15,
) -> Dict[str, str]:
    """
    Generates a synthetic claim submission and the remittance that answers it.

    Every claim on the 837 is paid, reduced or denied by exactly one claim
    payment on the 835, linked by CLM01 = CLP01. Outcomes are random, not
    learned from real payers: denials use administrative reasons only.

    :param claim_type: 837p, 837i or 837d.
    :param claims: How many claims.
    :param seed: The same seed always produces the same pair.
    :param denial_rate: The share of claims denied outright.
    """
    pair = _generate_claim_pair(
        seed=seed, claims=claims, claim_type=claim_type.lower(), denial_rate=denial_rate
    )
    return {"claim": pair.claim, "remittance": pair.remittance}


TOOLS = (validate_x12, parse_x12, list_claims, generate_x12, generate_claim_pair)


def create_server():
    """
    Builds the MCP server with every tool registered.

    :raises ImportError: with the install command, if the ``mcp`` extra is
        missing.
    """
    try:
        from mcp.server import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp.types import ToolAnnotations
    except ImportError as error:  # pragma: no cover - exercised by hand
        raise ImportError(
            'the MCP server needs the mcp extra: pip install "x12sdk[mcp]"'
        ) from error

    server = MCPServer(
        name="x12sdk",
        title="x12sdk: ASC X12 health care transactions",
        instructions=INSTRUCTIONS,
        version=__version__,
        website_url="https://github.com/owgreen-dev/x12sdk",
    )
    for tool in TOOLS:
        server.tool(
            annotations=ToolAnnotations(
                read_only_hint=True, idempotent_hint=True, open_world_hint=False
            )
        )(_explained(tool, ToolError))
    return server


def _explained(tool, tool_error):
    """
    Passes a ValueError's message to the assistant. MCP hides the text of any
    exception but its own ToolError, which is right for a crash; a bad argument
    (an unknown set, a count of zero) is the caller's to correct, and the
    message says how.
    """

    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except ValueError as error:
            raise tool_error(str(error)) from error

    return wrapper


def main() -> None:  # pragma: no cover - runs until the client disconnects
    """The ``x12sdk-mcp`` entry point: serves over stdio."""
    create_server().run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
