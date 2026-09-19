"""
test_repeatable_segments.py

Regression tests for repeatable segments whose loop initializers did not
pre-seed a list. Before the fix, the first occurrence failed model validation
(a dict where a list was declared) and any further occurrence was silently
dropped by the parser.
"""

import os

import pytest

from x12sdk.io import X12ModelReader
from x12sdk.models import X12SegmentGroup

from .support import assert_eq_model, resources_directory


def _model(relative_path: str):
    path = os.path.join(resources_directory, relative_path)
    with open(path) as f:
        data = f.read()
    with X12ModelReader(data) as r:
        models = list(r.models())
    assert len(models) == 1
    return models[0]


def test_835_payer_identification_keeps_every_per_segment():
    """Loop 1000A PER repeats; both contacts must survive parsing."""
    model = _model("835_005010X221A1/managed-care-payer-contacts.835")
    per_segments = model.loop_1000a.per_segment
    assert [p.contact_function_code for p in per_segments] == ["BL", "CX"]
    assert [p.communication_number_1 for p in per_segments] == [
        "5551234567",
        "5559876543",
    ]


def test_837i_claim_note_and_form_identification_are_parsed():
    """Loop 2300 NTE and the loop 2440 LQ/FRM pair were previously dropped."""
    model = _model("837_005010X223A3/institutional-claim-note-and-form.837i")
    claim = model.loop_2000a[0].loop_2000b[0].loop_2300[0]
    assert [n.description for n in claim.nte_segment] == [
        "PATIENT TRANSFERRED FROM ANOTHER FACILITY"
    ]
    form_loops = claim.loop_2400[0].loop_2440
    assert len(form_loops) == 1
    assert form_loops[0].lq_segment.form_identifier == "0100"
    assert [f.question_number_letter for f in form_loops[0].frm_segment] == ["1"]
    assert claim.loop_2400[1].loop_2440 is None


def test_271_information_source_provider_is_parsed():
    """Loop 2100A PRV is a repeatable segment and was never pre-seeded."""
    model = _model(
        "271_005010X279A1/subscriber-health-benefit-check-source-provider.271"
    )
    prv_segments = model.loop_2000a[0].loop_2100a.prv_segment
    assert [p.reference_identification for p in prv_segments] == ["207Q00000X"]


def _find_loops(group: X12SegmentGroup, field_name: str):
    """Yields every populated ``field_name`` value found anywhere under ``group``."""
    for name, field in group.__fields__.items():
        value = getattr(group, name)
        if value is None:
            continue
        if name == field_name:
            yield value
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, X12SegmentGroup):
                yield from _find_loops(item, field_name)


@pytest.mark.parametrize(
    "relative_path",
    [
        "837_004010X098A1/coordination-of-benefits-home-health.837",
        "837_004010X096A1/automobile-accident-home-health.837",
    ],
)
def test_4010_home_health_care_plan_loop_is_parsed(relative_path):
    """Loop 2305 (CR7 + HSD) had a model but no loop initializer in either 4010 837."""
    model = _model(relative_path)
    loops = list(_find_loops(model, "loop_2305"))
    assert len(loops) == 1
    loop_2305 = loops[0]
    assert loop_2305.cr7_segment.discipline_type_code == "AI"
    assert [
        (h.quantity_qualifier, h.measurement_code) for h in loop_2305.hsd_segment
    ] == [("VS", "WK")]


@pytest.mark.parametrize(
    "relative_path",
    [
        "835_005010X221A1/managed-care-payer-contacts.835",
        "837_005010X223A3/institutional-claim-note-and-form.837i",
        "271_005010X279A1/subscriber-health-benefit-check-source-provider.271",
        "837_004010X098A1/coordination-of-benefits-home-health.837",
        "837_004010X096A1/automobile-accident-home-health.837",
    ],
)
def test_new_samples_round_trip(relative_path):
    assert_eq_model(os.path.join(resources_directory, relative_path))


def test_segment_group_wraps_single_dict_for_list_field():
    """A bare dict for a List[...] field is accepted as a one-element list."""
    from typing import List

    from pydantic import Field

    from x12sdk.v5010.segments import NteSegment

    class Notes(X12SegmentGroup):
        nte_segment: List[NteSegment] = Field(min_items=1)

    group = Notes(nte_segment={"note_reference_code": "ADD", "description": "x"})
    assert len(group.nte_segment) == 1
    assert group.nte_segment[0].description == "x"
