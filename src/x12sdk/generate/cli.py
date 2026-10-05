"""
cli.py

The ``x12sdk-generate`` command: synthetic X12 files from the shell.

    x12sdk-generate 835 --seed 7 --claims 2
    x12sdk-generate 837p --seed 7 --claims 25 --dependent-rate 0.5 --out claims.837

One subcommand per transaction set. Every option maps onto a keyword argument
of the matching ``generate_*`` function, so the command and the library call
produce the same bytes for the same inputs.
"""

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence

from .. import __version__
from . import (
    generate_270,
    generate_271,
    generate_276,
    generate_277,
    generate_834,
    generate_835,
    generate_837i,
    generate_837p,
)

CLI_DESCRIPTION = """
Generates a synthetic, PHI-free X12 interchange and prints it (or writes it to --out).
The same seed always produces the same bytes.
"""


class _TransactionSet(NamedTuple):
    """How one subcommand maps onto its generator."""

    generate: Callable[..., str]
    count: str
    count_help: str
    names: Sequence[str]
    dependent_rate: bool
    help: str
    counts: Sequence[str] = ()


_SETS: Dict[str, _TransactionSet] = {
    "835": _TransactionSet(
        generate_835,
        "claims",
        "claims to invent",
        ("payer_name", "payee_name"),
        False,
        "claim payment / remittance advice",
        ("provider_adjustments",),
    ),
    "837p": _TransactionSet(
        generate_837p,
        "claims",
        "claims to invent",
        ("billing_provider_name", "payer_name", "submitter_name"),
        True,
        "professional claim",
    ),
    "837i": _TransactionSet(
        generate_837i,
        "claims",
        "claims to invent",
        ("billing_provider_name", "payer_name", "submitter_name"),
        True,
        "institutional claim",
    ),
    "834": _TransactionSet(
        generate_834,
        "enrollees",
        "member records to invent",
        ("sponsor_name", "payer_name"),
        True,
        "benefit enrollment and maintenance",
    ),
    "270": _TransactionSet(
        generate_270,
        "members",
        "members to invent",
        ("payer_name", "provider_name"),
        True,
        "eligibility inquiry",
    ),
    "271": _TransactionSet(
        generate_271,
        "members",
        "members to invent",
        ("payer_name", "provider_name"),
        True,
        "eligibility response",
    ),
    "276": _TransactionSet(
        generate_276,
        "patients",
        "patients to invent",
        ("payer_name", "requester_name", "provider_name"),
        True,
        "claim status inquiry",
    ),
    "277": _TransactionSet(
        generate_277,
        "patients",
        "patients to invent",
        ("payer_name", "requester_name", "provider_name"),
        True,
        "claim status response",
    ),
}


def _option(name: str) -> str:
    """``payer_name`` -> ``--payer-name``."""
    return "--" + name.replace("_", "-")


def _create_arg_parser() -> argparse.ArgumentParser:
    """
    Creates the argument parser, one subcommand per transaction set.

    Options default to ``None`` and are only passed on when given, so each
    generator keeps its own defaults (the sender and receiver ids differ
    between a payer-originated 835 and a provider-originated 837).

    :return: ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="x12sdk-generate",
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(
        dest="transaction_set",
        metavar="SET",
        required=True,
        help="which transaction set to generate",
    )

    for code, spec in _SETS.items():
        sub = subparsers.add_parser(code, help=spec.help)
        sub.add_argument(
            "--seed", type=int, default=0, help="reproduces the same file (default 0)"
        )
        sub.add_argument(
            "-n",
            _option(spec.count),
            dest="count",
            type=int,
            default=5,
            metavar="N",
            help=f"number of {spec.count_help} (default 5)",
        )
        if spec.dependent_rate:
            sub.add_argument(
                "--dependent-rate",
                type=float,
                metavar="RATE",
                help="share of people who are dependents rather than subscribers (default 0.3)",
            )
        for name in spec.names:
            sub.add_argument(_option(name), metavar="NAME", help=f"{name} override")
        for name in spec.counts:
            sub.add_argument(
                _option(name), type=int, metavar="N", help=f"number of {name} to invent"
            )
        sub.add_argument("--sender-id", metavar="ID", help="ISA06 / GS02 override")
        sub.add_argument("--receiver-id", metavar="ID", help="ISA08 / GS03 override")
        sub.add_argument(
            "--control-number", metavar="N", help="ST02 / SE02, at least 4 characters"
        )
        sub.add_argument(
            "-o",
            "--out",
            metavar="FILE",
            help="write here instead of standard output",
        )

    return parser


def _generate(args: argparse.Namespace) -> str:
    """Calls the generator the subcommand names with the options that were given."""
    spec = _SETS[args.transaction_set]
    kwargs = {"seed": args.seed, spec.count: args.count}
    for name in (
        "dependent_rate",
        *spec.names,
        *spec.counts,
        "sender_id",
        "receiver_id",
        "control_number",
    ):
        value = getattr(args, name, None)
        if value is not None:
            kwargs[name] = value
    return spec.generate(**kwargs)


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI module entrypoint.

    :param argv: Arguments without the program name; defaults to ``sys.argv[1:]``.
    :return: The process exit code.
    """
    parser = _create_arg_parser()
    args = parser.parse_args(argv)

    try:
        interchange = _generate(args)
    except ValueError as error:
        parser.error(str(error))

    if args.out:
        Path(args.out).write_text(interchange)
    else:
        sys.stdout.write(interchange + "\n")
    return 0
