"""
validation.py

Checking a file, with the answer in words: valid or not, and for an invalid
file, where in the loop hierarchy each problem is and what it is.

    x12sdk-validate claims.837 remit.835

    claims.837: valid — 1 transaction (837, 005010X222A2), 12 claims
    remit.835: INVALID
      loop 2000 #1 › loop 2100 #3: Claim Amount 9161.47 != Service Line Total 161.47

The rules are the library's: every model validator applies, from code values
and required segments to segment counts, HL linkage and claim and remittance
balancing. Problems are reported without echoing the file's content back.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional, Sequence

from pydantic import ValidationError

from .io import X12ModelReader
from .support import is_x12_data, is_x12_file

#: The exceptions reading a file can raise for bad input, as opposed to bugs.
READ_ERRORS = (ValidationError, ValueError, KeyError, IndexError)


@dataclass(frozen=True)
class Problem:
    """One reason a file is invalid."""

    location: str  # dotted model path, e.g. loop_2000a.0.loop_2000b.0.clm_segment
    where: str  # the same, in words: loop 2000A #1 › loop 2000B #1 › CLM segment
    message: str


@dataclass(frozen=True)
class Transaction:
    transaction_set: str
    control_number: Optional[str]
    implementation: Optional[str]
    claims: Optional[int]


@dataclass(frozen=True)
class CheckResult:
    """The outcome of checking one source."""

    valid: bool
    transactions: List[Transaction] = field(default_factory=list)
    problems: List[Problem] = field(default_factory=list)


def _where(parts: Sequence[Any]) -> str:
    words: List[str] = []
    for part in parts:
        if isinstance(part, int):
            if words:
                words[-1] += f" #{part + 1}"
            continue
        name = str(part)
        loop = re.fullmatch(r"loop_(\w+)", name)
        segment = re.fullmatch(r"(\w+?)_segment", name)
        if loop:
            words.append(f"loop {loop.group(1).upper()}")
        elif segment:
            words.append(f"{segment.group(1).upper()} segment")
        else:
            words.append(name.replace("_", " "))
    return " › ".join(words) or "file"


def problems(error: Exception) -> List[Problem]:
    """The problems behind a failed read, in words, without the file content."""
    if isinstance(error, ValidationError):
        found = []
        for detail in error.errors(include_input=False, include_url=False):
            message = re.sub(r"^Value error, ", "", detail["msg"])
            found.append(
                Problem(
                    location=".".join(str(p) for p in detail["loc"]),
                    where=_where(detail["loc"]),
                    message=message,
                )
            )
        return found
    return [Problem(location="", where="file", message=str(error))]


def _describe(model: Any) -> Transaction:
    st = model.header.st_segment
    claims = sum(1 for _ in model.claims()) if hasattr(model, "claims") else None
    return Transaction(
        transaction_set=st.transaction_set_identifier_code,
        control_number=st.transaction_set_control_number,
        implementation=getattr(st, "implementation_convention_reference", None),
        claims=claims,
    )


def check(source: str) -> CheckResult:
    """
    Checks X12 text, or the file at a path.

    :return: whether it is valid, the transactions found, and the problems.
    """
    text = source.lstrip()
    if not is_x12_data(text) and not is_x12_file(source):
        exists = (
            pathlib.Path(source).expanduser().exists() if len(source) < 4096 else False
        )
        message = (
            "not an X12 file: X12 begins with an ISA segment"
            if exists or "\n" in source or "~" in source
            else "file not found"
        )
        return CheckResult(valid=False, problems=[Problem("", "file", message)])
    try:
        with X12ModelReader(text if is_x12_data(text) else source) as reader:
            models = list(reader.models())
    except (IndexError, KeyError):
        return CheckResult(
            valid=False,
            problems=[
                Problem(
                    "",
                    "ISA segment",
                    "the interchange envelope is incomplete or malformed, so the "
                    "file cannot be read as X12",
                )
            ],
        )
    except READ_ERRORS as error:
        return CheckResult(valid=False, problems=problems(error))
    if not models:
        return CheckResult(
            valid=False,
            problems=[Problem("", "file", "no transactions found")],
        )
    return CheckResult(valid=True, transactions=[_describe(m) for m in models])


def _summary(result: CheckResult) -> str:
    sets = ", ".join(
        f"{t.transaction_set}, {t.implementation}"
        if t.implementation
        else t.transaction_set
        for t in result.transactions
    )
    count = len(result.transactions)
    text = f"{count} transaction{'s' if count != 1 else ''} ({sets})"
    claims = [t.claims for t in result.transactions if t.claims is not None]
    if claims:
        total = sum(claims)
        text += f", {total} claim{'s' if total != 1 else ''}"
    return text


def main(argv: Optional[List[str]] = None) -> int:
    """
    The ``x12sdk-validate`` entry point.

    :return: 0 when every file is valid, 1 when any is not.
    """
    parser = argparse.ArgumentParser(
        prog="x12sdk-validate",
        description=(
            "Checks X12 files against the implementation guide rules x12sdk "
            "models and says where any problem is. Reads locally; nothing is "
            "uploaded. Exits 1 if any file is invalid."
        ),
    )
    parser.add_argument("files", nargs="+", metavar="FILE")
    parser.add_argument(
        "--json", action="store_true", help="print one JSON object per file"
    )
    args = parser.parse_args(argv)

    all_valid = True
    for path in args.files:
        result = check(path)
        all_valid = all_valid and result.valid
        if args.json:
            print(json.dumps({"file": path, **asdict(result)}))
        elif result.valid:
            print(f"{path}: valid — {_summary(result)}")
        else:
            print(f"{path}: INVALID")
            for problem in result.problems:
                print(f"  {problem.where}: {problem.message}")
    return 0 if all_valid else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
