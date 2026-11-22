"""
test_tables.py

x12sdk.tables turns 835s and 837s into one row per service line. The promises
checked here: the columns never move, every row balances, a claim and its
remittance line up row for row, real corpus files work (not just generated
ones), and nothing about a file's choice of separator changes the result.
"""

import io
import pathlib
from decimal import Decimal

import pytest

from x12sdk.generate import (
    ClaimSpec,
    generate_835,
    generate_837d,
    generate_claim_pair,
)
from x12sdk.tables import (
    CLAIM_COLUMNS,
    REMITTANCE_COLUMNS,
    main,
    read_lines,
    to_dataframe,
    write_csv,
)

RESOURCES = pathlib.Path(__file__).parent / "resources"
CORPUS_5010 = sorted(
    path
    for folder in (
        "835_005010X221A1",
        "837_005010X222A2",
        "837_005010X223A3",
        "837_005010X224A2",
    )
    for path in (RESOURCES / folder).iterdir()
    if path.is_file()
)


# --- shape -------------------------------------------------------------------


@pytest.mark.parametrize("claim_type", ["837p", "837i", "837d"])
def test_columns_are_fixed_for_both_kinds(claim_type):
    pair = generate_claim_pair(seed=2, claims=4, claim_type=claim_type)
    for row in read_lines(pair.claim):
        assert tuple(row) == tuple(CLAIM_COLUMNS)
    for row in read_lines(pair.remittance):
        assert tuple(row) == tuple(REMITTANCE_COLUMNS)


@pytest.mark.parametrize("path", CORPUS_5010, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_5010_corpus_file_becomes_rows(path):
    """Real sample files, not only generated ones, read without error."""
    rows = read_lines(str(path))
    assert rows
    expected = (
        REMITTANCE_COLUMNS if path.parent.name.startswith("835") else CLAIM_COLUMNS
    )
    assert all(tuple(row) == tuple(expected) for row in rows)


def test_a_4010_file_is_refused_with_a_reason():
    path = next((RESOURCES / "837_004010X098A1").iterdir())
    with pytest.raises(ValueError, match="tables read 5010 transactions"):
        read_lines(str(path))


# --- remittance rows -----------------------------------------------------------


def test_every_remittance_line_balances():
    """Charge = paid + every adjustment, line by line."""
    rows = read_lines(generate_claim_pair(seed=5, claims=40).remittance)
    for row in rows:
        adjusted = sum(row[f"{g}_amount"] for g in ("co", "pr", "oa", "pi", "cr"))
        assert row["line_charge"] == row["line_paid"] + adjusted


def test_line_payments_add_up_to_the_claim_and_the_check():
    rows = read_lines(generate_claim_pair(seed=6, claims=25).remittance)
    by_claim = {}
    for row in rows:
        by_claim.setdefault(row["patient_control_number"], []).append(row)
    for lines in by_claim.values():
        assert sum(r["line_paid"] for r in lines) == lines[0]["claim_paid"]
    assert (
        sum(lines[0]["claim_paid"] for lines in by_claim.values())
        == rows[0]["payment_amount"]
    )


def test_adjustment_codes_are_listed_in_group_reason_form():
    rows = read_lines(
        generate_claim_pair(seed=6, claims=40, denial_rate=0.5).remittance
    )
    codes = {
        c
        for row in rows
        if row["adjustment_codes"]
        for c in row["adjustment_codes"].split(";")
    }
    assert codes
    assert all(code.split("-")[0] in ("CO", "PR", "OA", "PI", "CR") for code in codes)


def test_a_claim_paid_without_line_detail_still_gets_a_row():
    remittance = generate_835(seed=1, claims=[ClaimSpec(charge="100.00")])
    rows = read_lines(remittance)
    assert len(rows) == 1
    assert rows[0]["claim_charge"] == Decimal("100.00")
    assert rows[0]["line_number"] is None


def test_a_different_component_separator_gives_the_same_codes():
    """Files pick their own separator; `HC>99213` must read like `HC:99213`."""
    x12 = generate_claim_pair(seed=7, claims=3).remittance
    isa = x12.split("~")[0]
    other = isa[:-1] + ">" + x12[len(isa) :].replace("HC:", "HC>")
    assert [
        (r["procedure_qualifier"], r["procedure_code"]) for r in read_lines(other)
    ] == [(r["procedure_qualifier"], r["procedure_code"]) for r in read_lines(x12)]


# --- claim rows ----------------------------------------------------------------


def test_claim_rows_come_from_both_branches_of_the_hierarchy():
    rows = read_lines(generate_claim_pair(seed=3, claims=20).claim)
    assert {row["is_dependent"] for row in rows} == {True, False}


def test_dental_rows_carry_teeth_and_surfaces():
    rows = read_lines(generate_837d(seed=3, claims=30))
    assert any(row["tooth_number"] for row in rows)
    assert any(row["tooth_surfaces"] and ":" in row["tooth_surfaces"] for row in rows)
    assert all(row["procedure_qualifier"] == "AD" for row in rows)


def test_institutional_rows_keep_the_revenue_codes_leading_zero():
    rows = read_lines(str(RESOURCES / "837_005010X223A3" / "institutional-claim.837i"))
    assert rows[0]["revenue_code"] == "0305"
    assert rows[0]["facility_code"] == "14"


@pytest.mark.parametrize("claim_type", ["837p", "837i", "837d"])
def test_claim_and_remittance_rows_line_up(claim_type):
    """Joined on the control number and line number, the procedure agrees."""
    pair = generate_claim_pair(seed=9, claims=10, claim_type=claim_type)
    billed = {
        (r["patient_control_number"], r["line_number"]): r
        for r in read_lines(pair.claim)
    }
    paid = read_lines(pair.remittance)
    assert len(billed) == len(paid)
    for row in paid:
        line = billed[(row["patient_control_number"], row["line_number"])]
        assert line["procedure_code"] == row["procedure_code"]
        assert line["line_charge"] == row["line_charge"]


# --- outputs -------------------------------------------------------------------


def test_csv_has_the_header_and_one_line_per_row():
    out = io.StringIO()
    count = write_csv(generate_claim_pair(seed=1, claims=3).remittance, out)
    lines = out.getvalue().splitlines()
    assert lines[0].split(",") == list(REMITTANCE_COLUMNS)
    assert len(lines) == count + 1


def test_mixing_835_and_837_in_one_table_is_refused():
    pair = generate_claim_pair(seed=1, claims=1)
    with pytest.raises(ValueError, match="mixes 835 and 837"):
        write_csv(_both(pair), io.StringIO())


def _both(pair):
    from x12sdk.io import X12ModelReader

    models = []
    for x12 in (pair.claim, pair.remittance):
        with X12ModelReader(x12) as reader:
            models.extend(reader.models())
    return models


def test_dataframe_has_the_fixed_columns():
    pytest.importorskip("pandas")
    frame = to_dataframe(generate_claim_pair(seed=1, claims=4).claim)
    assert list(frame.columns) == list(CLAIM_COLUMNS)
    assert len(frame) >= 4


def test_command_writes_csv_to_a_file(tmp_path, capsys):
    source = tmp_path / "remit.835"
    source.write_text(generate_claim_pair(seed=2, claims=3).remittance)
    out = tmp_path / "remit.csv"
    assert main([str(source), "-o", str(out)]) == 0
    assert out.read_text().splitlines()[0].startswith("transaction_set,")
    assert "rows written" in capsys.readouterr().err


def test_command_writes_to_stdout(tmp_path, capsys):
    source = tmp_path / "claims.837"
    source.write_text(generate_claim_pair(seed=2, claims=2).claim)
    main([str(source)])
    assert capsys.readouterr().out.splitlines()[0].split(",") == list(CLAIM_COLUMNS)
