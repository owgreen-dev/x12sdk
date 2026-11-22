"""
test_validation_and_matching.py

x12sdk-validate says, in words, whether a file is valid and where it is not;
x12sdk.matching joins claims to the remittances that answer them. Both are
checked on generated files and on real corpus files.
"""

import json
import pathlib
from decimal import Decimal

import pytest

from x12sdk.generate import (
    ClaimSpec,
    generate_835,
    generate_837d,
    generate_claim_pair,
)
from x12sdk.matching import MATCH_COLUMNS, match_claims, match_rows
from x12sdk.validation import check, main

RESOURCES = pathlib.Path(__file__).parent / "resources"


def _broken() -> str:
    return generate_837d(seed=1, claims=1).replace(
        "CLM*PCN000001*", "CLM*PCN000001*9", 1
    )


# --- validation ----------------------------------------------------------------


def test_a_valid_file_is_summarised():
    result = check(generate_837d(seed=1, claims=3))
    assert result.valid
    (transaction,) = result.transactions
    assert transaction.transaction_set == "837"
    assert transaction.implementation == "005010X224A2"
    assert transaction.claims == 3


def test_a_problem_is_located_in_words_without_the_file_content():
    result = check(_broken())
    assert not result.valid
    (problem,) = result.problems
    assert problem.where == "loop 2000A #1 › loop 2000B #1 › loop 2300 #1"
    assert problem.message.startswith("Claim Amount 9")
    assert "input_value" not in problem.message
    assert "PCN000001" not in problem.message


@pytest.mark.parametrize(
    "content,expected",
    [
        ("ISA*bad", "interchange envelope is incomplete or malformed"),
        ("hello world\n", "not an X12 file"),
    ],
)
def test_unreadable_files_are_explained(tmp_path, content, expected):
    path = tmp_path / "input.x12"
    path.write_text(content)
    (problem,) = check(str(path)).problems
    assert expected in problem.message


def test_a_missing_file_is_reported_as_missing(tmp_path):
    (problem,) = check(str(tmp_path / "nope.837")).problems
    assert problem.message == "file not found"


@pytest.mark.parametrize(
    "folder",
    ["835_005010X221A1", "837_005010X222A2", "837_005010X223A3", "270_005010X279A1"],
)
def test_corpus_files_validate(folder):
    for path in (RESOURCES / folder).iterdir():
        assert check(str(path)).valid, path.name


def test_command_exit_codes_and_output(tmp_path, capsys):
    good = tmp_path / "good.837"
    good.write_text(generate_837d(seed=2, claims=2))
    bad = tmp_path / "bad.837"
    bad.write_text(_broken())

    assert main([str(good)]) == 0
    assert (
        "valid — 1 transaction (837, 005010X224A2), 2 claims" in capsys.readouterr().out
    )

    assert main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert f"{bad}: INVALID" in out
    assert "loop 2300 #1: Claim Amount" in out


def test_command_json_output(tmp_path, capsys):
    bad = tmp_path / "bad.837"
    bad.write_text(_broken())
    main(["--json", str(bad)])
    record = json.loads(capsys.readouterr().out)
    assert record["valid"] is False
    assert record["problems"][0]["where"].startswith("loop 2000A #1")


# --- matching ------------------------------------------------------------------


@pytest.mark.parametrize("claim_type", ["837p", "837i", "837d"])
def test_every_claim_in_a_pair_is_matched_once(claim_type):
    pair = generate_claim_pair(seed=4, claims=15, claim_type=claim_type)
    matches = match_claims(pair.claim, pair.remittance)
    assert len(matches) == 15
    for match in matches:
        assert len(match.claims) == 1 and len(match.payments) == 1
        assert match.billed == match.payments[0].charge
        assert match.outcome in ("paid", "denied")


def test_outcomes_follow_the_payments():
    pair = generate_claim_pair(seed=8, claims=40, denial_rate=0.5)
    matches = match_claims(pair.claim, pair.remittance)
    outcomes = {m.outcome for m in matches}
    assert outcomes == {"paid", "denied"}
    for match in matches:
        assert (match.paid > 0) == (match.outcome == "paid")


def test_unanswered_claims_and_unknown_payments_are_kept():
    """Nothing is dropped: a claim without a payment, a payment without a claim."""
    pair = generate_claim_pair(seed=3, claims=4)
    stranger = generate_835(
        seed=9,
        claims=[ClaimSpec(charge="50.00", patient_control_number="STRANGER-1")],
    )
    matches = match_claims(pair.claim, [stranger])

    assert [m.outcome for m in matches] == ["no remittance"] * 4 + ["no claim"]
    assert all(m.paid == Decimal("0.00") for m in matches[:4])
    assert matches[-1].patient_control_number == "STRANGER-1"
    assert matches[-1].billed == Decimal("50.00")


def test_several_payments_for_one_claim_are_all_kept():
    """A payment and a second remittance for the same claim both count."""
    pair = generate_claim_pair(seed=5, claims=3)
    matches = match_claims(pair.claim, [pair.remittance, pair.remittance])
    for match in matches:
        assert len(match.payments) == 2
        assert match.paid == 2 * match.payments[0].paid


def test_rows_have_the_fixed_columns():
    pair = generate_claim_pair(seed=1, claims=5)
    rows = list(match_rows(pair.claim, pair.remittance))
    assert len(rows) == 5
    assert all(tuple(row) == tuple(MATCH_COLUMNS) for row in rows)


def test_corpus_claims_without_remittances_are_unanswered():
    claims = str(RESOURCES / "837_005010X223A3" / "institutional-claim.837i")
    remittance = generate_835(seed=1, claims=1)
    (first, *_rest) = match_claims(claims, remittance)
    assert first.outcome == "no remittance"
