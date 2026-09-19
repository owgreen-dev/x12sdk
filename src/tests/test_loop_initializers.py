"""
test_loop_initializers.py

Every repeatable segment (a ``List[...]`` field on a loop or transaction
model) must be pre-seeded as an empty list by a loop initializer in the
transaction's ``parsing`` module. The parser stores the first occurrence of a
segment as a dict and appends only when it finds a list, so a missing
pre-seed used to lose the second occurrence.

Two safety nets now exist (``X12Parser`` promotes a repeated dict to a list;
``X12SegmentGroup`` wraps a bare dict for a list field), so a missed pre-seed
is no longer a data-loss bug. This test keeps the initializers honest anyway.

The check is package-level: the set of list-typed segment fields declared in
``loops.py``/``transaction_set.py`` must be a subset of the keys pre-seeded
somewhere in ``parsing.py``. That is a lower bound (a key seeded for one loop
satisfies the check for another), which is why the runtime safety nets exist.
"""

import importlib
import inspect
import pkgutil
import re

import pytest

import x12sdk.v4010 as v4010
import x12sdk.v5010 as v5010
from x12sdk.models import X12SegmentGroup, _is_list_field

PRESEED_PATTERN = re.compile(r'"(\w+_segment)":\s*\[\]')


def _transaction_packages():
    for version in (v4010, v5010):
        for module in pkgutil.iter_modules(version.__path__):
            if module.ispkg and module.name.startswith("x12_"):
                yield f"{version.__name__}.{module.name}"


def _list_segment_fields(package_name: str) -> set:
    """List-typed ``*_segment`` fields declared by the package's segment groups."""
    fields = set()
    for module_name in ("loops", "transaction_set"):
        try:
            module = importlib.import_module(f"{package_name}.{module_name}")
        except ModuleNotFoundError:
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls, X12SegmentGroup) or cls is X12SegmentGroup:
                continue
            for name, field in cls.model_fields.items():
                if name.endswith("_segment") and _is_list_field(field.annotation):
                    # a container (List[...]) rather than a bare segment
                    fields.add(name)
    return fields


def _preseeded_keys(package_name: str) -> set:
    parsing = importlib.import_module(f"{package_name}.parsing")
    return set(PRESEED_PATTERN.findall(inspect.getsource(parsing)))


@pytest.mark.parametrize("package_name", sorted(_transaction_packages()))
def test_repeatable_segments_are_preseeded(package_name):
    missing = _list_segment_fields(package_name) - _preseeded_keys(package_name)
    assert not missing, (
        f"{package_name}: list-typed segment fields with no '\"<name>\": []' "
        f"pre-seed in parsing.py: {sorted(missing)}"
    )
