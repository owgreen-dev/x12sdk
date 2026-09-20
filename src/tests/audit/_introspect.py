"""
Shared introspection for the audit suite.

The audit does not test any one transaction set. It walks every package under
``x12sdk.v4010`` and ``x12sdk.v5010``, reads the Pydantic models and the
parser source, and applies the same check to each. A new transaction set is
covered the moment it exists.

Nothing here knows about a specific bug. That knowledge lives in the tests, in
their docstrings, so each check can say which real defect it exists to catch.
"""

from __future__ import annotations

import ast
import enum
import importlib
import inspect
import pkgutil
import types
import typing
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

import annotated_types

import x12sdk.v4010 as v4010
import x12sdk.v5010 as v5010
from x12sdk.models import X12Segment, X12SegmentGroup

# --- packages ---------------------------------------------------------------


def transaction_packages() -> List[str]:
    """Every ``x12_*`` package under both versions, sorted for stable ids."""
    found = []
    for version in (v4010, v5010):
        for module in pkgutil.iter_modules(version.__path__):
            if module.ispkg and module.name.startswith("x12_"):
                found.append(f"{version.__name__}.{module.name}")
    return sorted(found)


def shared_segment_modules() -> List[types.ModuleType]:
    """
    The segment modules every package imports from: ``x12sdk.v5010.segments``
    and ``x12sdk.v4010.segments``. A package's own ``segments`` module defines
    only its specialisations, so these hold most segment classes and must be
    audited in their own right.
    """
    import x12sdk.v4010.segments
    import x12sdk.v5010.segments

    return [x12sdk.v5010.segments, x12sdk.v4010.segments]


def short(package: str) -> str:
    """``x12sdk.v5010.x12_835_005010X221A1`` -> ``835_005010X221A1``."""
    return package.rsplit(".", 1)[-1].removeprefix("x12_")


@dataclass
class Package:
    name: str
    loops: Optional[types.ModuleType]
    segments: Optional[types.ModuleType]
    parsing: Optional[types.ModuleType]
    transaction_set: Optional[types.ModuleType]

    @property
    def short(self) -> str:
        return short(self.name)


def load(package: str) -> Package:
    def maybe(sub: str):
        try:
            return importlib.import_module(f"{package}.{sub}")
        except ModuleNotFoundError:
            return None

    return Package(
        name=package,
        loops=maybe("loops"),
        segments=maybe("segments"),
        parsing=maybe("parsing"),
        transaction_set=maybe("transaction_set"),
    )


# --- models -----------------------------------------------------------------


def models_in(module, base) -> List[type]:
    """Classes defined in ``module`` (not merely imported) that subclass ``base``."""
    out = []
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        if issubclass(cls, base) and cls is not base:
            out.append(cls)
    return sorted(out, key=lambda c: c.__name__)


def groups_in(pkg: Package) -> List[type]:
    """Every loop and transaction model in the package."""
    out: List[type] = []
    for module in (pkg.loops, pkg.transaction_set):
        if module is not None:
            out.extend(models_in(module, X12SegmentGroup))
    return out


def segments_in(pkg: Package) -> List[type]:
    return models_in(pkg.segments, X12Segment) if pkg.segments else []


def root_model(pkg: Package) -> Optional[type]:
    """The transaction set model: the one group declaring both header and footer."""
    if pkg.transaction_set is None:
        return None
    for cls in models_in(pkg.transaction_set, X12SegmentGroup):
        if {"header", "footer"} <= set(cls.model_fields):
            return cls
    return None


# --- annotations ------------------------------------------------------------


def unwrap_optional(annotation):
    """``Optional[X]`` -> ``X``; anything else unchanged."""
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def is_optional(annotation) -> bool:
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        return type(None) in typing.get_args(annotation)
    return False


def is_list(annotation) -> bool:
    return typing.get_origin(unwrap_optional(annotation)) in (list, List)


def list_item(annotation):
    args = typing.get_args(unwrap_optional(annotation))
    return args[0] if args else Any


def min_len(field) -> Optional[int]:
    for item in field.metadata:
        if isinstance(item, annotated_types.MinLen):
            return item.min_length
    return None


def max_len(field) -> Optional[int]:
    for item in field.metadata:
        if isinstance(item, annotated_types.MaxLen):
            return item.max_length
    return None


def list_fields(model: type) -> Dict[str, Any]:
    """Field name -> FieldInfo for every list-typed field on the model."""
    return {n: f for n, f in model.model_fields.items() if is_list(f.annotation)}


def loop_list_fields(pkg: Package) -> Dict[str, List[type]]:
    """
    ``loop_*`` field names declared as a list anywhere in the package, mapped to
    the models declaring them.
    """
    out: Dict[str, List[type]] = {}
    for model in groups_in(pkg):
        for name, field in model.model_fields.items():
            if name.startswith("loop_") and is_list(field.annotation):
                out.setdefault(name, []).append(model)
    return out


# --- validators -------------------------------------------------------------


def model_validator_functions(model: type) -> Dict[str, Any]:
    """Validator name -> underlying function for every model validator."""
    decorators = getattr(model, "__pydantic_decorators__", None)
    if decorators is None:
        return {}
    return {name: dec.func for name, dec in decorators.model_validators.items()}


# --- parser source ----------------------------------------------------------


@dataclass
class ParserSource:
    module: types.ModuleType
    text: str
    tree: ast.Module
    loop_names: Dict[str, str]  # TransactionLoops.NAME -> "loop_xxxx"


def parser_source(pkg: Package) -> Optional[ParserSource]:
    if pkg.parsing is None:
        return None
    text = inspect.getsource(pkg.parsing)
    tree = ast.parse(text)
    loop_names: Dict[str, str] = {}
    loops_enum = getattr(pkg.parsing, "TransactionLoops", None)
    if loops_enum is not None and issubclass(loops_enum, enum.Enum):
        loop_names = {member.name: member.value for member in loops_enum}
    return ParserSource(pkg.parsing, text, tree, loop_names)


def resolve_key(
    node: ast.AST, source: ParserSource, scope: ast.FunctionDef
) -> List[str]:
    """
    The possible string values of a subscript key.

    Handles a literal, ``TransactionLoops.NAME``, and a local variable assigned
    from either of those anywhere in the enclosing function (the 270 handler
    assigned ``loop_name`` in an if/else before using it).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Attribute) and node.attr in source.loop_names:
        return [source.loop_names[node.attr]]
    if isinstance(node, ast.Name):
        values: List[str] = []
        for sub in ast.walk(scope):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    if isinstance(target, ast.Name) and target.id == node.id:
                        values.extend(resolve_key(sub.value, source, scope))
        return values
    return []


def _guarded_values(test: ast.AST, variable: str, source: ParserSource) -> List[str]:
    """
    The values ``variable`` is known to hold when ``test`` is true, for tests
    of the form ``variable == X`` or ``variable in (X, Y)``. Empty otherwise.
    """
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return []
    if not (isinstance(test.left, ast.Name) and test.left.id == variable):
        return []
    op, right = test.ops[0], test.comparators[0]
    if isinstance(op, ast.Eq):
        return _literal_values(right, source)
    if isinstance(op, ast.In) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
        out: List[str] = []
        for element in right.elts:
            out.extend(_literal_values(element, source))
        return out
    return []


def _literal_values(node: ast.AST, source: ParserSource) -> List[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Attribute) and node.attr in source.loop_names:
        return [source.loop_names[node.attr]]
    return []


def dict_assignments_to_subscripts(
    source: ParserSource,
) -> Iterator[Tuple[ast.FunctionDef, ast.Assign, List[str]]]:
    """
    Every ``something[key] = {...}`` in the parser, with the key resolved.

    This is the shape of the assign-instead-of-append defect: a bare dict
    written to a key that the model declares as a list.

    The walk is flow-sensitive for one pattern, the guard the fix uses::

        if loop_name == TransactionLoops.REPEATING:
            record.setdefault(loop_name, []).append({...})
        else:
            record[loop_name] = {...}

    Inside the ``else``, ``loop_name`` cannot be the guarded value, so it is
    subtracted from what the key may resolve to. Without this the fixed code
    would be reported for the assignment its own guard makes unreachable.
    """

    def visit(node: ast.AST, func: ast.FunctionDef, excluded: Dict[str, set]):
        if isinstance(node, ast.If):
            for child in node.body:
                yield from visit(child, func, excluded)
            narrowed = {k: set(v) for k, v in excluded.items()}
            for variable in {
                n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)
            }:
                guarded = _guarded_values(node.test, variable, source)
                if guarded:
                    narrowed.setdefault(variable, set()).update(guarded)
            for child in node.orelse:
                yield from visit(child, func, narrowed)
            return
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    keys = resolve_key(target.slice, source, func)
                    if isinstance(target.slice, ast.Name):
                        keys = [
                            k
                            for k in keys
                            if k not in excluded.get(target.slice.id, set())
                        ]
                    if keys:
                        yield func, node, keys
            return
        for child in ast.iter_child_nodes(node):
            yield from visit(child, func, excluded)

    for func in ast.walk(source.tree):
        if isinstance(func, ast.FunctionDef):
            for child in func.body:
                yield from visit(child, func, {})


# --- validator source -------------------------------------------------------


@dataclass
class ValuesAccess:
    model: type
    function: str
    field: str
    default: Optional[ast.AST]  # None when accessed as values["x"]
    lineno: int


def values_accesses(model: type) -> List[ValuesAccess]:
    """
    Every ``values["x"]`` and ``values.get("x", ...)`` inside the model's own
    validators, as written in its source.

    Shared validators from ``x12sdk.validators`` are not walked here; they
    take the field name as a parameter and are audited separately.
    """
    out: List[ValuesAccess] = []
    for name, func in model_validator_functions(model).items():
        if func.__module__ != model.__module__:
            continue
        try:
            text = inspect.getsource(func)
        except (OSError, TypeError):
            continue
        tree = ast.parse(_dedent(text))
        base_line = func.__code__.co_firstlineno
        for node in ast.walk(tree):
            # values.get("x", default)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "values"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                default = node.args[1] if len(node.args) > 1 else None
                out.append(
                    ValuesAccess(
                        model,
                        name,
                        node.args[0].value,
                        default,
                        base_line + node.lineno - 1,
                    )
                )
            # values["x"]
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == "values"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                out.append(
                    ValuesAccess(
                        model, name, node.slice.value, None, base_line + node.lineno - 1
                    )
                )
    return out


def _dedent(text: str) -> str:
    import textwrap

    return textwrap.dedent(text)


def is_non_none_literal(node: Optional[ast.AST]) -> bool:
    """A default that is not ``None``: ``[]``, ``{}``, ``0``, ``""`` and so on."""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return node.value is not None
    return isinstance(node, (ast.List, ast.Dict, ast.Tuple, ast.Set))
