"""
test_generate_cli.py

The command is a thin shell over the generate_* functions, so the contract is
simple: the same inputs produce the same bytes as the library call, every set
is reachable, and bad input fails with an argparse error rather than a trace.
"""

import pytest

from x12sdk.generate import (
    generate_270,
    generate_271,
    generate_276,
    generate_277,
    generate_834,
    generate_835,
    generate_837i,
    generate_837p,
)
from x12sdk.generate.cli import main
from x12sdk.io import X12ModelReader


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        return list(reader.models())


@pytest.mark.parametrize(
    "transaction_set,generate,count",
    [
        ("835", generate_835, "claims"),
        ("837p", generate_837p, "claims"),
        ("837i", generate_837i, "claims"),
        ("834", generate_834, "enrollees"),
        ("270", generate_270, "members"),
        ("271", generate_271, "members"),
        ("276", generate_276, "patients"),
        ("277", generate_277, "patients"),
    ],
)
def test_every_set_matches_the_library_call(transaction_set, generate, count, tmp_path):
    """--out writes exactly what the generate_* function returns, and it parses."""
    target = tmp_path / f"out.{transaction_set}"
    exit_code = main([transaction_set, "--seed", "3", "-n", "2", "--out", str(target)])

    assert exit_code == 0
    expected = generate(seed=3, **{count: 2})
    assert target.read_text() == expected
    assert len(_read(target.read_text())) == 1


def test_stdout_is_the_interchange_plus_a_newline(capsys):
    assert main(["835", "--seed", "7", "--claims", "2"]) == 0
    captured = capsys.readouterr()
    assert captured.out == generate_835(seed=7, claims=2) + "\n"
    assert captured.err == ""


def test_long_count_option_is_named_for_the_set(tmp_path):
    """--claims on an 835, --members on a 270: the library's own vocabulary."""
    target = tmp_path / "out.270"
    main(["270", "--members", "3", "--out", str(target)])
    assert target.read_text() == generate_270(members=3)


def test_name_overrides_reach_the_file(capsys):
    main(["835", "--payer-name", "ACME HEALTH", "--payee-name", "ACME CLINIC"])
    out = capsys.readouterr().out
    assert "N1*PR*ACME HEALTH~" in out
    assert "N1*PE*ACME CLINIC" in out


def test_envelope_overrides_are_passed_through(capsys):
    main(
        [
            "837p",
            "--sender-id",
            "SND",
            "--receiver-id",
            "RCV",
            "--control-number",
            "0042",
        ]
    )
    out = capsys.readouterr().out
    isa = out.split("\n")[0].split("*")
    assert isa[6].strip() == "SND"
    assert isa[8].strip() == "RCV"
    assert "ST*837*0042*" in out
    assert "SE*" in out and "*0042~" in out


def test_dependent_rate_applies_only_where_the_hierarchy_exists(capsys):
    assert main(["837p", "--dependent-rate", "1.0", "--claims", "2"]) == 0
    assert capsys.readouterr().out == generate_837p(claims=2, dependent_rate=1.0) + "\n"

    with pytest.raises(SystemExit) as raised:
        main(["835", "--dependent-rate", "1.0"])
    assert raised.value.code == 2


def test_defaults_match_the_library_defaults(capsys):
    """No options at all is the library call with no arguments."""
    main(["834"])
    assert capsys.readouterr().out == generate_834() + "\n"


def test_bad_values_are_argparse_errors_not_tracebacks(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["835", "--claims", "0"])
    assert raised.value.code == 2
    assert "claims must be at least 1" in capsys.readouterr().err

    with pytest.raises(SystemExit) as raised:
        main(["835", "--sender-id", "X" * 16])
    assert raised.value.code == 2
    assert "sender_id must be 2 to 15" in capsys.readouterr().err


def test_unknown_set_and_missing_set_are_rejected():
    with pytest.raises(SystemExit) as raised:
        main(["999"])
    assert raised.value.code == 2

    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == 2


def test_version_flag(capsys):
    from x12sdk import __version__

    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out.strip() == __version__
