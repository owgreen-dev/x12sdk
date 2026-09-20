"""
A generic filler that builds any model from its required fields alone.

Nothing in the inherited repository ever constructed a model in Python; it
only parsed. Every "constructing crashes" defect found this year (a
validator's ``get()`` default that never fires, a field silently required,
a type in a default slot) was invisible to parsing and obvious the first time
someone called a constructor. This filler calls every constructor.

Values are deliberately dull. The goal is not realism but reaching every
validator with *something* well-formed enough to get there.
"""

from __future__ import annotations

import datetime
import enum
import re
import types
import typing
from decimal import Decimal
from typing import Any, Dict, Optional

import annotated_types
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

_MAX_DEPTH = 8


class Unfillable(Exception):
    """The filler has no strategy for a field; distinct from a model rejecting a value."""


def _constraint(field: FieldInfo, kind):
    for item in field.metadata:
        if isinstance(item, kind):
            return item
    return None


def _pattern(field: FieldInfo) -> Optional[str]:
    for item in field.metadata:
        pattern = getattr(item, "pattern", None)
        if pattern:
            return pattern
    return None


def _string(field: FieldInfo, name: str) -> str:
    """A string that satisfies the field's length and, where simple, its pattern."""
    lo = _constraint(field, annotated_types.MinLen)
    hi = _constraint(field, annotated_types.MaxLen)
    lo = lo.min_length if lo else 1
    hi = hi.max_length if hi else None
    pattern = _pattern(field)

    lowered = name.lower()
    if lowered == "interchange_date":
        value = "260101"  # ISA09 is YYMMDD
    elif "date" in lowered and "qualifier" not in lowered and "format" not in lowered:
        value = "20260101"
    elif "time" in lowered and "qualifier" not in lowered and "format" not in lowered:
        value = "1200"
    elif "postal" in lowered:
        value = "12345"
    elif "state" in lowered:
        value = "IL"
    elif "npi" in lowered or lowered == "identification_code":
        value = "1234567893"
    elif "amount" in lowered or "count" in lowered or "number" in lowered:
        value = "1"
    else:
        value = "A"

    if pattern:
        for candidate in (value, "1", "12", "123", "A", "AB", "20260101", "1200"):
            if re.fullmatch(pattern, candidate):
                value = candidate
                break
        else:
            raise Unfillable(f"{name}: no candidate matches pattern {pattern!r}")

    if len(value) < lo:
        value = (value * lo)[:lo] if value else "A" * lo
    if hi is not None and len(value) > hi:
        value = value[:hi]
    return value


def fill(annotation, field: FieldInfo, name: str, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        raise Unfillable(f"{name}: nesting deeper than {_MAX_DEPTH}")

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin in (typing.Union, types.UnionType):
        candidates = [a for a in args if a is not type(None)]
        if str in candidates:
            return fill(str, field, name, depth)
        return fill(candidates[0], field, name, depth)

    if origin is typing.Literal:
        return args[0]

    if origin in (list, typing.List) or annotation in (list, typing.List):
        lo = _constraint(field, annotated_types.MinLen)
        count = max(lo.min_length if lo else 0, 1)
        # a bare ``List`` declares no item type; fill it with strings and let
        # the structural leg report the missing annotation
        item = args[0] if args else str
        return [fill(item, FieldInfo(), name, depth + 1) for _ in range(count)]

    if origin is typing.Annotated:
        inner, *meta = args
        merged = FieldInfo()
        merged.metadata = list(field.metadata) + list(meta)
        return fill(inner, merged, name, depth)

    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return list(annotation)[0].value
        if issubclass(annotation, BaseModel):
            return minimal(annotation, depth + 1)
        if annotation is str:
            return _string(field, name)
        if annotation is bool:
            return True
        if annotation is int:
            gt = _constraint(field, annotated_types.Gt)
            return (gt.gt + 1) if gt else 1
        if annotation is float:
            return 1.0
        if annotation is Decimal:
            return Decimal("1.00")
        if annotation is datetime.datetime:
            return datetime.datetime(2026, 1, 1, 12, 0)
        if annotation is datetime.date:
            return datetime.date(2026, 1, 1)
        if annotation is dict:
            return {}

    if annotation is Any:
        return "A"

    raise Unfillable(f"{name}: no strategy for annotation {annotation!r}")


#: A qualifier that is filled drags its value field along. The models enforce
#: these pairs as all-or-nothing, so a qualifier alone is never valid.
COMPANIONS = {
    "identification_code_qualifier": "identification_code",
    "reference_identification_qualifier": "reference_identification",
    "date_time_period_format_qualifier": "date_time_period",
    "product_service_id_qualifier": "product_service_id",
    "communication_number_qualifier_1": "communication_number_1",
    "communication_number_qualifier_2": "communication_number_2",
    "communication_number_qualifier_3": "communication_number_3",
    "quantity_qualifier": "quantity",
}

#: (package short name, model name) -> function(kwargs) -> kwargs, applied
#: after the generic fill for the few models with a cross-field invariant the
#: filler cannot infer. Each entry says why.
OVERRIDES: Dict[tuple, Any] = {}


def _short(model: type) -> str:
    """The audit's package label for a model: ``835_005010X221A1`` or ``shared-v5010``."""
    module = model.__module__
    if module.endswith(".segments") and module.count(".") == 2:  # x12sdk.v5010.segments
        return "shared-" + module.split(".")[1]
    package = module.rsplit(".", 1)[0].rsplit(".", 1)[-1]
    return package.removeprefix("x12_")


_REVERSE = {value: qualifier for qualifier, value in COMPANIONS.items()}


def _qualifier_of(name: str) -> Optional[str]:
    """The qualifier that must accompany a required value field, if any."""
    return _REVERSE.get(name, name + "_qualifier")


def _companion(name: str) -> Optional[str]:
    if name in COMPANIONS:
        return COMPANIONS[name]
    if name.endswith("_qualifier"):
        return name[: -len("_qualifier")]
    return None


def required_kwargs(model: type, depth: int = 0) -> Dict[str, Any]:
    """Values for every required field, plus the companion of any qualifier."""
    out: Dict[str, Any] = {}
    fields = model.model_fields
    for name, field in fields.items():
        if not field.is_required():
            continue
        out[name] = fill(field.annotation, field, name, depth)
        partner = _companion(name) or _qualifier_of(name)
        if partner and partner in fields and partner not in out:
            out[partner] = fill(
                fields[partner].annotation, fields[partner], partner, depth
            )
    override = OVERRIDES.get((_short(model), model.__name__))
    if override:
        out = override(out)
    return out


def _enum_fields(model: type):
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if typing.get_origin(annotation) in (typing.Union, types.UnionType):
            annotation = [
                a for a in typing.get_args(annotation) if a is not type(None)
            ][0]
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            yield name, list(annotation)


def minimal(model: type, depth: int = 0) -> BaseModel:
    """
    Construct ``model`` from its required fields alone. Raises on rejection.

    A validator may reject the first value of an enum (ACH payment demands
    nine bank fields; the first CRC category is not valid on a claim). On a
    rejection, each enum field is rotated through its values in turn, bounded
    so a genuine defect still surfaces rather than being searched around.
    """
    kwargs = required_kwargs(model, depth)
    try:
        return model(**kwargs)
    except ValidationError as first:
        attempts = 0
        for name, values in _enum_fields(model):
            if name not in kwargs:
                continue
            for value in values[1:]:
                attempts += 1
                if attempts > 24:
                    raise first
                try:
                    return model(**{**kwargs, name: value.value})
                except ValidationError:
                    continue
        raise first


# --- overrides ---------------------------------------------------------------


def _claim_charge_matches_lines(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    837 Loop2300 requires CLM02 to equal the sum of the service line charges,
    but CLM02 is optional in the model with a default of 0.00 while the line
    charge is required, so a generic fill always disagrees by exactly one
    line. Set the claim charge to the line total.
    """
    total = Decimal("0.00")
    for line in kwargs.get("loop_2400", []):
        for attr in ("sv1_segment", "sv2_segment"):
            segment = getattr(line, attr, None)
            if segment is not None and hasattr(segment, "line_item_charge_amount"):
                total += segment.line_item_charge_amount
    clm = kwargs["clm_segment"]
    kwargs["clm_segment"] = clm.model_copy(update={"total_claim_charge_amount": total})
    return kwargs


for _package in (
    "837_004010X096A1",
    "837_004010X098A1",
    "837_005010X222A2",
    "837_005010X223A3",
):
    OVERRIDES[(_package, "Loop2300")] = _claim_charge_matches_lines


def _crc_category_valid_on_a_claim(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    CRC01 on a claim is narrowed by a validator to a handful of categories
    while the field type carries the full code list, so the type's first value
    is rejected. 75 is accepted by every implementation's claim-level list.
    """
    kwargs["code_category"] = "75"
    kwargs["certification_condition_indicator"] = "Y"
    return kwargs


def _crc_professional(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """The professional implementations further narrow CRC03 under category 75."""
    kwargs = _crc_category_valid_on_a_claim(kwargs)
    kwargs["condition_code_1"] = "IH"
    return kwargs


OVERRIDES[("837_005010X222A2", "Loop2300CrcSegment")] = _crc_professional
OVERRIDES[("837_004010X098A1", "Loop2300CrcSegment")] = _crc_professional
OVERRIDES[("837_004010X096A1", "Loop2300CrcSegment")] = _crc_category_valid_on_a_claim
OVERRIDES[("837_005010X223A3", "Loop2300CrcSegment")] = _crc_category_valid_on_a_claim


def _eq_asks_about_something(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """EQ requires a service type or a procedure; both are optional fields."""
    kwargs["service_type_code"] = ["30"]
    return kwargs


def _rdm_names_the_payee(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """RDM requires a name whenever the remittance goes by mail."""
    kwargs["name"] = "EXAMPLE PAYEE"
    return kwargs


for _shared in ("shared-v5010", "shared-v4010"):
    OVERRIDES[(_shared, "EqSegment")] = _eq_asks_about_something
    OVERRIDES[(_shared, "RdmSegment")] = _rdm_names_the_payee
