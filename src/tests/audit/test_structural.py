"""
Leg 1: structural audit.

Static checks over every transaction package, comparing what the Pydantic
models declare against what the parser and the validators actually do. None
of these needs a sample file, which is the point: every defect below shipped
for years in a repository with a 66-file corpus and a green test suite,
because parsing a well-formed sample cannot reach them.

Each test's docstring names the bug class and the real instance that
motivated it. A failure here is a claim that the same shape has recurred.
"""

from __future__ import annotations

import ast
import inspect
from typing import List

import annotated_types
import pytest

import x12sdk.v4010.validators
import x12sdk.validators
from x12sdk.validators import validate_segment_count

from . import _introspect as I

PACKAGES = I.transaction_packages()
IDS = [I.short(p) for p in PACKAGES]


@pytest.fixture(params=PACKAGES, ids=IDS)
def pkg(request) -> I.Package:
    return I.load(request.param)


# --- 1. a list-typed loop whose initializer assigns instead of appends -------


def test_list_loops_are_appended_not_assigned(pkg):
    """
    Bug class: a loop declared ``List[...]`` whose parser initializer writes a
    fresh dict to the key, so every occurrence after the first overwrites the
    one before. Nothing raises; the file just loses data.

    Instances: 270 loop 2110C kept only the last EQ (fixed 2.0.0); 834 loop
    2200 kept only the last disability period (fixed 2.0.0). The 834 case was
    hidden because ``X12SegmentGroup`` wraps a lone record for a list field,
    so a single occurrence looked correct.

    The repeated-segment safety net added for 1.0.0 works at the segment
    level, not the loop-initializer level, which is why it caught neither.
    """
    source = I.parser_source(pkg)
    if source is None:
        pytest.skip("no parsing module")
    declared_lists = I.loop_list_fields(pkg)

    offenders: List[str] = []
    for func, node, keys in I.dict_assignments_to_subscripts(source):
        for key in keys:
            if key in declared_lists:
                models = ", ".join(m.__name__ for m in declared_lists[key])
                offenders.append(
                    f"{func.name}() line {node.lineno} assigns a dict to "
                    f"{key!r}, which {models} declare as a list"
                )
    assert not offenders, "\n".join(offenders)


def _shared_models():
    for module in I.shared_segment_modules():
        yield pytest.param(
            I.models_in(module, I.X12Segment),
            id="shared-" + module.__name__.split(".")[-2],
        )


@pytest.mark.parametrize("models", list(_shared_models()))
def test_shared_segment_fields_allowing_zero_elements_have_a_default(models):
    """The check below, applied to the shared segment modules."""
    offenders = [
        f"{m.__name__}.{n}"
        for m in models
        for n, f in m.model_fields.items()
        if I.min_len(f) == 0 and f.is_required()
    ]
    assert not offenders, "\n  ".join(["min_length=0 but required:"] + offenders)


@pytest.mark.parametrize("models", list(_shared_models()))
def test_shared_segment_defaults_are_values_not_types(models):
    """Check 5 below, applied to the shared segment modules."""
    offenders = [
        f"{m.__name__}.{n} = {f.default!r}"
        for m in models
        for n, f in m.model_fields.items()
        if isinstance(f.default, type)
        or isinstance(f.default, annotated_types.BaseMetadata)
    ]
    assert not offenders, "\n  ".join(offenders)


# --- 2. min_length=0 with no default is silently required -------------------


def test_fields_allowing_zero_elements_have_a_default(pkg):
    """
    Bug class: ``Field(min_length=0)`` with no default. Pydantic treats a
    field with no default as required, so the declaration says "may be empty"
    while the runtime says "must be passed". Parsing never notices because the
    parser pre-seeds the key; only construction in Python does.

    Instances: ``Loop2010Ba.ref_segment`` on the 837P and 837I, and
    ``Loop2000A.loop_2000b`` on the 271 (all fixed 1.1.0).
    """
    offenders: List[str] = []
    for model in I.groups_in(pkg) + I.segments_in(pkg):
        for name, field in model.model_fields.items():
            if I.min_len(field) == 0 and field.is_required():
                offenders.append(f"{model.__name__}.{name}")
    assert not offenders, (
        "min_length=0 but no default, so Pydantic requires the field:\n  "
        + "\n  ".join(offenders)
    )


# --- 3. a validator default that can never fire ------------------------------


def test_validators_do_not_default_an_always_present_key(pkg):
    """
    Bug class: ``values.get("x_segment", [])`` inside a model validator, where
    ``x_segment`` is an Optional field. On a model built in Python the key is
    always present and set to None, so the ``get()`` default never fires and
    the loop over it raises ``TypeError``. Only the parser pre-seeds a list.

    Instances: 835 ``Loop2100.validate_balance`` (fixed 1.1.0); the shared
    ``_validate_duplicate_codes`` (fixed 1.2.0, and audited separately below
    because it takes the field name as a parameter). The correct spelling is
    ``values.get("x") or []``.
    """
    offenders: List[str] = []
    for model in I.groups_in(pkg):
        for access in I.values_accesses(model):
            field = model.model_fields.get(access.field)
            if field is None:
                continue  # reported by the next test
            if I.is_non_none_literal(access.default) and not field.is_required():
                offenders.append(
                    f"{model.__name__}.{access.function}() line {access.lineno}: "
                    f"values.get({access.field!r}, <default>) on an optional "
                    f"field; the key is always present, so write "
                    f"`values.get({access.field!r}) or ...`"
                )
    assert not offenders, "\n".join(offenders)


def test_shared_validators_do_not_default_values_get():
    """
    The shared validators in ``x12sdk.validators`` run against optional fields
    by construction, so a non-None ``values.get()`` default there is always the
    defect above. Instance: ``_validate_duplicate_codes`` (fixed 1.2.0).
    """
    offenders: List[str] = []
    for module in (x12sdk.validators, x12sdk.v4010.validators):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "values"
                and len(node.args) > 1
                and I.is_non_none_literal(node.args[1])
            ):
                offenders.append(f"{module.__name__} line {node.lineno}")
    assert not offenders, (
        "values.get(key, <default>) in a shared validator; the key is always "
        "present on a constructed model:\n  " + "\n  ".join(offenders)
    )


# --- 4. a validator that names a field that does not exist ------------------


def test_validators_reference_fields_that_exist(pkg):
    """
    Bug class: a validator reads ``values["ref_segments"]`` or
    ``values.get("ref_segments", ...)`` when the field is ``ref_segment``. The
    lookup always misses, the rule silently never applies, and the test suite
    stays green because nothing asserts the rule fires.

    Instance: 271 ``Loop2110C.validate_red_cross_eb_ref_codes`` had never
    once run (fixed 1.1.0).
    """
    offenders: List[str] = []
    for model in I.groups_in(pkg):
        for access in I.values_accesses(model):
            if access.field not in model.model_fields:
                offenders.append(
                    f"{model.__name__}.{access.function}() line {access.lineno} "
                    f"reads values[{access.field!r}], but the model has no such "
                    f"field (has: {sorted(model.model_fields)})"
                )
    assert not offenders, "\n".join(offenders)


# --- 5. a type or constraint sitting in the default slot --------------------


def test_defaults_are_values_not_types(pkg):
    """
    Bug class: ``Optional[int] = conint(gt=0)``. The constraint lands in the
    default slot instead of the annotation, so the field is "defaulted" to a
    class and the bound is never enforced.

    Instance: ``IdcSegment.identification_card_count`` (fixed 1.0.0).
    """
    offenders: List[str] = []
    for model in I.groups_in(pkg) + I.segments_in(pkg):
        for name, field in model.model_fields.items():
            default = field.default
            if isinstance(default, type) or isinstance(
                default, annotated_types.BaseMetadata
            ):
                offenders.append(f"{model.__name__}.{name} = {default!r}")
    assert not offenders, "\n".join(offenders)


# --- 6. every transaction set enforces SE01 ---------------------------------


def test_every_transaction_set_validates_its_segment_count(pkg):
    """
    Bug class: a validator every other transaction set attaches is commented
    out on one of them, so that set alone accepts a malformed file in silence.

    Instance: the 834 had ``validate_segment_count`` commented out (fixed
    1.2.0). All ten inherited samples carried a correct count, so nothing ever
    exercised the gap.
    """
    root = I.root_model(pkg)
    if root is None:
        pytest.skip("no transaction set model")
    attached = I.model_validator_functions(root).values()
    assert validate_segment_count in attached, (
        f"{root.__name__} does not attach validate_segment_count; every other "
        f"transaction set does"
    )


# --- 7. every list field says what it holds -----------------------------------


def _untyped_lists(models) -> List[str]:
    import typing

    out = []
    for model in models:
        for name, field in model.model_fields.items():
            annotation = I.unwrap_optional(field.annotation)
            bare = annotation in (list, typing.List) or (
                typing.get_origin(annotation) in (list, typing.List)
                and not typing.get_args(annotation)
            )
            if bare:
                out.append(f"{model.__name__}.{name}: {field.annotation!r}")
    return out


def test_list_fields_declare_their_item_type(pkg):
    """
    Bug class: a field annotated as a bare ``List``. Pydantic then validates
    nothing about the items, so ``[1, None, {}]`` is accepted where a list of
    code strings was meant, and the serializer's behaviour on it is undefined.

    Instance: the twelve composite fields on ``HiSegment`` in both the 4010 and
    5010 shared segment modules (found by this suite, 2026-09-20).
    """
    offenders = _untyped_lists(I.groups_in(pkg) + I.segments_in(pkg))
    assert not offenders, "\n  ".join(["bare List, no item type:"] + offenders)


@pytest.mark.parametrize("models", list(_shared_models()))
def test_shared_segment_list_fields_declare_their_item_type(models):
    """Check 7, applied to the shared segment modules."""
    offenders = _untyped_lists(models)
    assert not offenders, "\n  ".join(["bare List, no item type:"] + offenders)
