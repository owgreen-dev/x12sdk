"""
Leg 2: construction audit.

Build every loop model and every segment model in every package from its
required fields alone, and require it to validate.

Bug class: anything that only breaks when a model is *constructed* rather
than parsed. The parser pre-seeds every list key and never passes ``None``,
so a validator that mishandles an absent optional field, or a field that is
required by accident, is unreachable from any sample file no matter how many
there are.

Instances: 835 ``Loop2100.validate_balance`` raised ``TypeError`` on any
claim with no adjustments (1.1.0); the shared duplicate-code validator raised
on any loop without REF (1.2.0); ``Loop2010Ba.ref_segment`` and
``Loop2000A.loop_2000b`` were required by accident (1.1.0). Every one of
these fails here and passed every parsing test.

Transaction-set roots are excluded: their segment-count validator needs a
real SE01, and the generators already construct every root. Models the
filler genuinely cannot build are listed in ``KNOWN_UNFILLABLE`` with a
reason and marked as expected failures, strictly, so a fix is noticed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from . import _fill
from . import _introspect as I


class _Shared:
    """Stands in for a Package when the model comes from a shared module."""

    def __init__(self, short: str) -> None:
        self.short = short


# (package short name, model name) -> why the generic filler cannot build it.
# Strict xfail: if one of these starts passing, the entry must be removed.
KNOWN_UNFILLABLE: dict = {}


def _cases():
    for module in I.shared_segment_modules():
        label = "shared-" + module.__name__.split(".")[-2]
        for model in I.models_in(module, I.X12Segment):
            yield pytest.param(_Shared(label), model, id=f"{label}::{model.__name__}")
    for package in I.transaction_packages():
        pkg = I.load(package)
        root = I.root_model(pkg)
        for model in I.groups_in(pkg):
            if model is root:
                continue
            yield pytest.param(pkg, model, id=f"{pkg.short}::{model.__name__}")
        for model in I.segments_in(pkg):
            yield pytest.param(pkg, model, id=f"{pkg.short}::{model.__name__}")


@pytest.mark.parametrize("pkg,model", list(_cases()))
def test_model_constructs_from_required_fields_alone(pkg, model):
    key = (pkg.short, model.__name__)
    if key in KNOWN_UNFILLABLE:
        pytest.xfail(KNOWN_UNFILLABLE[key])

    try:
        instance = _fill.minimal(model)
    except _fill.Unfillable as exc:
        pytest.fail(f"filler gap, not a model defect: {exc}")
    except ValidationError as exc:
        pytest.fail(f"{model.__name__} rejected a minimal construction:\n{exc}")
    except TypeError as exc:
        pytest.fail(
            f"{model.__name__} raised TypeError during validation, the signature "
            f"of a validator that read an optional field with a get() default: "
            f"{exc}"
        )

    # What it built must also render. A loop with no required fields at all
    # legitimately renders to nothing, so only demand output when something
    # was filled; a crash here is a model that validates but cannot be written.
    try:
        rendered = instance.x12()
    except Exception as exc:  # noqa: BLE001 - any failure is the finding
        pytest.fail(
            f"{model.__name__} validated but x12() raised {type(exc).__name__}: {exc}"
        )
    assert isinstance(rendered, str)
    if _fill.required_kwargs(model):
        assert rendered, f"{model.__name__} had required fields but rendered nothing"
