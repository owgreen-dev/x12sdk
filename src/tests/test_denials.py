"""
test_denials.py

Extraction is tested against the real 835 samples; aggregation is tested on
constructed records so it does not depend on what a sample happens to contain.
"""

import json
import os
from decimal import Decimal

import pytest

from x12sdk.denials import (
    CONTRACTUAL,
    COORDINATION_OF_BENEFITS,
    OTHER,
    PATIENT_RESPONSIBILITY,
    Adjustment,
    categorize,
    category_map,
    denial_summary,
    describe,
    iter_adjustments,
    load_code_descriptions,
    to_dataframe,
)
from x12sdk.io import X12ModelReader

from .support import resources_directory

REMITTANCE_DIR = os.path.join(resources_directory, "835_005010X221A1")


def _adjustments(file_name):
    path = os.path.join(REMITTANCE_DIR, file_name)
    with open(path) as handle:
        data = handle.read()
    with X12ModelReader(data) as reader:
        transactions = list(reader.models())
    assert len(transactions) == 1
    return list(iter_adjustments(transactions[0]))


# --- extraction -----------------------------------------------------------


def test_flattens_claim_and_line_adjustments():
    """One record per CAS reason code, with claim context attached."""
    rows = _adjustments("managed-care.835")
    assert len(rows) == 5

    claim_level = [r for r in rows if r.level == "claim"]
    line_level = [r for r in rows if r.level == "line"]
    assert len(claim_level) == 2
    assert len(line_level) == 3

    first = claim_level[0]
    assert first.payer_name == "RUSHMORE LIFE"
    assert first.patient_control_number == "5554555444"
    assert (first.group_code, first.reason_code) == ("CO", "A2")
    assert first.amount == Decimal("50.00")
    assert first.claim_charge_amount == Decimal("800.00")
    assert first.procedure is None

    line = [r for r in line_level if r.reason_code == "45"][0]
    assert line.procedure == "HC:93555"
    assert line.line_charge_amount == Decimal("1200.00")
    assert line.category == CONTRACTUAL


def test_multi_position_cas_expands_to_one_record_each():
    """CAS*PR*1*150.00**2*70.00 carries two reason codes in one segment."""
    rows = _adjustments("secondary-payment.835")
    patient = [r for r in rows if r.group_code == "PR"]
    assert [(r.reason_code, r.amount) for r in patient] == [
        ("1", Decimal("150.00")),
        ("2", Decimal("70.00")),
    ]


def test_negative_adjustment_amount_is_preserved():
    """A takeback is a negative adjustment and must not be dropped or abs()'d."""
    rows = _adjustments("cob-contractural-adjustment.835")
    amounts = {r.reason_code: r.amount for r in rows}
    assert amounts["94"] == Decimal("-9.00")


def test_claim_remark_codes_are_attached():
    """MOA/MIA remark codes belong to every adjustment on that claim."""
    rows = _adjustments("medicare-part-a.835")
    with_remarks = [r for r in rows if r.remark_codes]
    assert with_remarks, "expected at least one adjustment carrying a remark code"
    assert "MA02" in with_remarks[0].remark_codes


def test_every_sample_remittance_flattens_without_error():
    """The walk must survive every 835 in the corpus, not just the tidy ones."""
    names = [f for f in sorted(os.listdir(REMITTANCE_DIR)) if f.endswith(".835")]
    assert len(names) >= 5
    for name in names:
        for row in _adjustments(name):
            assert row.level in ("claim", "line")
            assert isinstance(row.amount, Decimal)


# --- categories -----------------------------------------------------------


def test_categorize_known_and_unknown_codes():
    assert categorize("45") == CONTRACTUAL
    assert categorize("1") == PATIENT_RESPONSIBILITY
    assert categorize("23") == COORDINATION_OF_BENEFITS
    assert categorize("A2") == OTHER, "unmapped codes fall through to 'other'"
    assert categorize(None) == OTHER
    assert categorize(" 45 ") == CONTRACTUAL, "codes are trimmed"


def test_no_code_list_text_is_vendored():
    """
    Guard against a future change vendoring X12/WPC description text.

    The descriptions are licensed separately; x12sdk ships codes and its own
    categories only. See the licensing note in x12sdk.denials.
    """
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    denials_dir = os.path.join(package_root, "x12sdk", "denials")
    samples = ("Deductible amount", "Coinsurance amount", "Duplicate claim/service")
    for file_name in os.listdir(denials_dir):
        if not file_name.endswith(".py"):
            continue
        with open(os.path.join(denials_dir, file_name)) as handle:
            content = handle.read()
        for phrase in samples:
            assert phrase not in content, (
                f"{file_name} appears to vendor code-list text: {phrase!r}"
            )


# --- descriptions ---------------------------------------------------------


def test_load_code_descriptions_from_json(tmp_path):
    path = tmp_path / "carc.json"
    path.write_text(json.dumps({"45": "some text", "a2": "other text"}))
    loaded = load_code_descriptions(path)
    assert loaded["45"] == "some text"
    assert loaded["A2"] == "other text", "codes are upper-cased on load"


def test_load_code_descriptions_from_csv(tmp_path):
    path = tmp_path / "carc.csv"
    path.write_text("code,text\n45,some text\n18,other text\n")
    loaded = load_code_descriptions(path)
    assert loaded == {"45": "some text", "18": "other text"}


def test_load_code_descriptions_rejects_a_csv_without_the_code_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("reason,text\n45,some text\n")
    with pytest.raises(ValueError, match="code"):
        load_code_descriptions(path)


# --- aggregation ----------------------------------------------------------


def _adjustment(**overrides):
    base = dict(
        payer_name="PAYER",
        payer_id="P1",
        patient_control_number="CLAIM1",
        payer_claim_control_number="ICN1",
        claim_status_code="1",
        claim_charge_amount=Decimal("100.00"),
        claim_payment_amount=Decimal("80.00"),
        patient_responsibility_amount=Decimal("0.00"),
        level="claim",
        group_code="CO",
        reason_code="45",
        amount=Decimal("20.00"),
        quantity=None,
        category=CONTRACTUAL,
    )
    base.update(overrides)
    return Adjustment(**base)


def test_denial_summary_excludes_patient_responsibility_by_default():
    rows = denial_summary(
        [
            _adjustment(group_code="CO", reason_code="45", amount=Decimal("20.00")),
            _adjustment(
                group_code="PR",
                reason_code="1",
                amount=Decimal("30.00"),
                category=PATIENT_RESPONSIBILITY,
            ),
        ]
    )
    assert [(r.group_code, r.reason_code) for r in rows] == [("CO", "45")]


def test_denial_summary_includes_patient_responsibility_when_asked():
    rows = denial_summary(
        [
            _adjustment(group_code="CO", reason_code="45", amount=Decimal("20.00")),
            _adjustment(
                group_code="PR",
                reason_code="1",
                amount=Decimal("30.00"),
                category=PATIENT_RESPONSIBILITY,
            ),
        ],
        include_patient_responsibility=True,
    )
    assert len(rows) == 2
    assert rows[0].total_amount == Decimal("30.00"), "sorted by amount descending"


def test_denial_summary_counts_distinct_claims_not_occurrences():
    """A reason hitting three lines of one claim is one claim, three adjustments."""
    rows = denial_summary(
        [
            _adjustment(level="line", amount=Decimal("5.00")),
            _adjustment(level="line", amount=Decimal("6.00")),
            _adjustment(level="line", amount=Decimal("7.00")),
            _adjustment(payer_claim_control_number="ICN2", amount=Decimal("1.00")),
        ]
    )
    assert len(rows) == 1
    assert rows[0].adjustment_count == 4
    assert rows[0].claim_count == 2
    assert rows[0].total_amount == Decimal("19.00")


def test_denial_summary_totals_are_exact():
    """Decimal in, Decimal out — no float drift in money."""
    rows = denial_summary(
        [
            _adjustment(amount=Decimal("0.10")),
            _adjustment(amount=Decimal("0.20")),
        ]
    )
    assert rows[0].total_amount == Decimal("0.30")


def test_describe_attaches_descriptions_from_a_supplied_list():
    rows = denial_summary([_adjustment()])
    described = describe(rows, {"45": "some text"})
    assert described[0]["description"] == "some text"
    assert described[0]["reason_code"] == "45"

    unmapped = describe(denial_summary([_adjustment(reason_code="ZZ")]), {})
    assert unmapped[0]["description"] is None


# --- pandas ---------------------------------------------------------------


def test_to_dataframe_shapes_the_records():
    pd = pytest.importorskip("pandas")
    frame = to_dataframe(
        [
            _adjustment(),
            _adjustment(level="line", procedure="HC:99213", remark_codes=("MA02",)),
        ]
    )
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2
    assert frame["reason_code"].tolist() == ["45", "45"]
    assert frame["remark_codes"].tolist() == ["", "MA02"]
    # claim-level rows have no service line, which pandas renders as NaN
    assert pd.isna(frame["procedure"].iloc[0])
    assert frame["procedure"].iloc[1] == "HC:99213"
    # amounts stay Decimal, so sums are exact
    assert frame["amount"].sum() == Decimal("40.00")


def test_a2_and_42_stay_uncategorized_on_purpose():
    """
    Both are contractual write-offs in routine work, and both are left in
    ``other`` anyway. ``contractual`` is the category a denial review skips:
    A2 is payer-discretionary in practice, and 42 was retired in favour of 45,
    so a payer still sending it is itself worth a second look. Pinning the
    decision here stops it being "fixed" as an oversight.
    """
    assert categorize("A2") == OTHER
    assert categorize("42") == OTHER
    assert categorize("45") == CONTRACTUAL

    mapping = category_map()
    assert "A2" not in mapping
    assert "42" not in mapping
