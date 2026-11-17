"""
test_build_dataset.py

scripts/build_dataset.py builds the public dataset. Its promises are the
dataset card's promises, so they are checked here at a small size: the tables
are read back out of the X12, every claim and line balances, the tables join,
the card is filled in, and the same arguments rebuild the same bytes.
"""

import csv
import importlib.util
import pathlib
from decimal import Decimal

import pytest

SCRIPT = pathlib.Path(__file__).parents[2] / "scripts" / "build_dataset.py"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_dataset", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dataset(builder, tmp_path_factory):
    out = tmp_path_factory.mktemp("dataset")
    stats = builder.build(out, seed=3, pairs=2, claims_per_pair=15)
    return out, stats


def _rows(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def test_every_claim_type_is_written_as_x12_pairs(dataset):
    out, stats = dataset
    for claim_type in ("837p", "837i", "837d"):
        names = sorted(p.name for p in (out / "x12" / claim_type).iterdir())
        assert names == ["pair-000.835", "pair-000.837", "pair-001.835", "pair-001.837"]
    assert stats["files"] == 12
    assert stats["claims"] == 3 * 2 * 15


def test_claims_balance_and_join_their_lines(dataset):
    out, _ = dataset
    claims = _rows(out / "data" / "claims.csv")
    lines = _rows(out / "data" / "service_lines.csv")
    assert len(claims) == 90

    totals = {}
    for line in lines:
        key = (line["claim_type"], line["pair"], line["patient_control_number"])
        totals[key] = totals.get(key, Decimal("0")) + Decimal(line["line_charge"])
        assert Decimal(line["line_charge"]) == (
            Decimal(line["line_paid"])
            + Decimal(line["contractual_adjustment"])
            + Decimal(line["patient_responsibility"])
        )

    for claim in claims:
        key = (claim["claim_type"], claim["pair"], claim["patient_control_number"])
        assert totals[key] == Decimal(claim["claim_charge"])
        assert Decimal(claim["claim_charge"]) == (
            Decimal(claim["paid_amount"])
            + Decimal(claim["contractual_adjustment"])
            + Decimal(claim["patient_responsibility"])
        )
        if claim["denied"] == "True":
            assert Decimal(claim["paid_amount"]) == 0
            assert claim["denial_reason_code"] in {"16", "27", "29", "96", "197"}


def test_tables_hold_no_names_or_member_ids(dataset):
    """Placeholder names stay in the X12, where the format needs them."""
    out, _ = dataset
    header = (out / "data" / "claims.csv").read_text().splitlines()[0]
    assert "name_first" not in header and "member_id" not in header
    assert "patient_name" not in header


def test_the_card_is_filled_in(dataset):
    out, stats = dataset
    card = (out / "README.md").read_text()
    assert card.startswith("---\nlicense: cc-by-4.0\n")
    assert "{" not in card.split("```")[0].replace("{{", "")
    assert f"{stats['claims']} rows, one per claim" in card
    assert f"--seed {stats['seed']}" in card


def test_the_same_arguments_rebuild_the_same_bytes(builder, dataset, tmp_path):
    out, _ = dataset
    builder.build(tmp_path, seed=3, pairs=2, claims_per_pair=15)
    for path in out.rglob("*"):
        if path.is_file():
            assert (tmp_path / path.relative_to(out)).read_bytes() == path.read_bytes()


def test_a_non_empty_output_directory_is_refused(builder, tmp_path):
    (tmp_path / "keep.txt").write_text("not mine")
    with pytest.raises(SystemExit):
        builder.main(["--out", str(tmp_path), "--pairs", "1", "--claims-per-pair", "1"])
