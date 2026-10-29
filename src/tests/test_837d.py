"""
test_837d.py

The 837D dental claim (005010X224A2) shares the professional claim's envelope
and hierarchy; what is new is the dental detail. These tests pin that detail
on the synthetic samples in resources/837_005010X224A2: tooth numbers and
surfaces on a line, missing teeth and orthodontic months on a claim, and the
repeating line adjudication loop.
"""

import pathlib
from decimal import Decimal

import pytest

from x12sdk.io import X12ModelReader
from x12sdk.v5010.x12_837_005010X224A2.transaction_set import HealthCareClaimDental

SAMPLES = pathlib.Path(__file__).parent / "resources" / "837_005010X224A2"


def _read(name: str) -> HealthCareClaimDental:
    with X12ModelReader(str(SAMPLES / name)) as reader:
        models = list(reader.models())
    assert len(models) == 1
    assert isinstance(models[0], HealthCareClaimDental)
    return models[0]


def _subscriber_claim(model):
    return model.loop_2000a[0].loop_2000b[0].loop_2300[0]


def _dependent_claim(model):
    return model.loop_2000a[0].loop_2000b[0].loop_2000c[0].loop_2300[0]


def test_a_dental_line_carries_its_procedure_tooth_and_surfaces():
    claim = _subscriber_claim(_read("subscriber-restoration.837"))
    filling = claim.loop_2400[1]

    assert filling.sv3_segment.composite_medical_procedure_identifier == "AD:D2391"
    assert filling.sv3_segment.line_item_charge_amount == Decimal("140.00")
    assert len(filling.too_segment) == 1
    tooth = filling.too_segment[0]
    assert tooth.code_list_qualifier_code == "JP"
    assert tooth.tooth_number == "30"
    assert tooth.tooth_surface == ["M", "O"], "surfaces split into a list"


def test_a_line_without_a_tooth_has_none():
    claim = _subscriber_claim(_read("subscriber-restoration.837"))
    exam = claim.loop_2400[0]
    assert not exam.too_segment


def test_an_orthodontic_claim_carries_months_missing_teeth_and_placement():
    claim = _dependent_claim(_read("dependent-orthodontic.837"))

    assert claim.dn1_segment.orthodontic_treatment_months_count == Decimal("24")
    assert claim.dn1_segment.orthodontic_treatment_months_remaining_count == Decimal(
        "14"
    )
    assert [(t.tooth_number, t.tooth_status_code) for t in claim.dn2_segment] == [
        ("1", "M"),
        ("16", "M"),
    ]
    assert [d.date_time_qualifier for d in claim.dtp_segment] == ["452"]


def test_a_dependent_claim_sits_under_the_patient_not_the_subscriber():
    model = _read("dependent-orthodontic.837")
    subscriber = model.loop_2000a[0].loop_2000b[0]
    assert not subscriber.loop_2300
    assert subscriber.loop_2000c[0].pat_segment.individual_relationship_code == "19"


def test_every_line_adjudication_survives_the_parser():
    """
    Loop 2430 repeats, once per payer that adjudicated the line. The 837P and
    837I parsers reset the list on every SVD, keeping only the last; the
    dental parser must append.
    """
    claim = _subscriber_claim(_read("tertiary-two-line-adjudications.837"))
    adjudications = claim.loop_2400[0].loop_2430

    assert [a.svd_segment.other_payer_primary_identifier for a in adjudications] == [
        "11111",
        "22222",
    ]
    assert len(claim.loop_2320) == 2, "both prior payers are kept"


def test_the_claim_total_must_equal_the_dental_lines():
    model = _read("subscriber-restoration.837")
    claim = _subscriber_claim(model)
    bad = claim.clm_segment.model_copy(
        update={"total_claim_charge_amount": Decimal("999.00")}
    )
    with pytest.raises(ValueError, match="Claim Amount 999.00 != Service Line Total"):
        type(claim)(**{**claim.__dict__, "clm_segment": bad})


@pytest.mark.parametrize("version", ["005010X224", "005010X224A1", "005010X224A2"])
def test_every_x224_revision_reads_with_the_dental_model(version):
    text = (SAMPLES / "subscriber-restoration.837").read_text()
    text = text.replace("*005010X224A2~", f"*{version}~")
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert isinstance(models[0], HealthCareClaimDental)


def test_an_unknown_tooth_surface_is_rejected():
    text = (SAMPLES / "subscriber-restoration.837").read_text()
    text = text.replace("TOO*JP*30*M:O~", "TOO*JP*30*M:Q~")
    with pytest.raises(ValueError):
        with X12ModelReader(text) as reader:
            list(reader.models())
