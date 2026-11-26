"""
Malformed input must end in a clean error, never a raw exception.

Reading a file the parser cannot place is allowed to fail, but only with a
pydantic ``ValidationError`` or the library's own ``X12ParseException``. A
``TypeError``, ``KeyError``, ``IndexError``, ``AttributeError`` or
``UnboundLocalError`` escaping from a segment handler is a defect: it names
library internals instead of the segment that is wrong, and a caller that
catches the documented error types is bypassed.

Every sample here is a valid file from the corpus with one deliberate fault
made to it. After each mutation the SE01 segment count is recomputed, so the
fault under test is the only thing wrong with the file. Each (transaction set,
fault) pair is one test; a failure lists the first offending cases with the
exception that escaped. The unchanged files are the positive control.

Whether a malformed file is accepted or rejected is not decided here; only the
type of the failure when there is one.
"""

from __future__ import annotations

import pathlib
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader
from x12sdk.parsing import X12ParseException

RESOURCES = pathlib.Path(__file__).parent / "resources"

# LookupError is the base of KeyError and IndexError; a bare LookupError carrying
# a message (for example "ID 999 not found") is the same fault one level up.
RAW_ERRORS = (
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    UnboundLocalError,
    LookupError,
)
CLEAN_ERRORS = (ValidationError, X12ParseException)

Segments = List[str]


def _transaction_sets() -> List[str]:
    return sorted(p.name for p in RESOURCES.iterdir() if p.is_dir())


def _samples(transaction_set: str) -> List[pathlib.Path]:
    return sorted(p for p in (RESOURCES / transaction_set).iterdir() if p.is_file())


def _split(text: str) -> Segments:
    return [s for s in text.replace("\r", "").replace("\n", "").split("~") if s]


def _build(segments: Segments) -> str:
    """Join segments, recomputing SE01 so the count is never the fault."""
    start = next(i for i, s in enumerate(segments) if s.startswith("ST*"))
    end = max(i for i, s in enumerate(segments) if s.startswith("SE*"))
    out = list(segments)
    fields = out[end].split("*")
    fields[1] = str(end - start + 1)
    out[end] = "*".join(fields)
    return "".join(s + "~" for s in out)


def _body_range(segments: Segments) -> range:
    """Indexes strictly between ST and SE."""
    start = next(i for i, s in enumerate(segments) if s.startswith("ST*"))
    end = max(i for i, s in enumerate(segments) if s.startswith("SE*"))
    return range(start + 1, end)


def _drop(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        yield f"drop {k} {ss[k].split('*')[0]}", ss[:k] + ss[k + 1 :]


def _repeat(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        yield f"repeat {k} {ss[k].split('*')[0]}", ss[: k + 1] + [ss[k]] + ss[k + 1 :]


def _swap(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    body = _body_range(ss)
    for k in body:
        if k + 1 in body:
            yield (
                f"swap {k} {ss[k].split('*')[0]}/{ss[k + 1].split('*')[0]}",
                ss[:k] + [ss[k + 1], ss[k]] + ss[k + 2 :],
            )


def _fields(ss: Segments, k: int) -> List[str]:
    return ss[k].split("*")


def _empty_first(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        f = _fields(ss, k)
        if len(f) > 2:
            yield (
                f"empty-first {k} {f[0]}",
                ss[:k] + ["*".join([f[0], ""] + f[2:])] + ss[k + 1 :],
            )


def _empty_last(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        f = _fields(ss, k)
        if len(f) > 2:
            yield (
                f"empty-last {k} {f[0]}",
                ss[:k] + ["*".join(f[:-1] + [""])] + ss[k + 1 :],
            )


def _one_element(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        f = _fields(ss, k)
        if len(f) > 2:
            yield f"one-element {k} {f[0]}", ss[:k] + [f[0] + "*" + f[1]] + ss[k + 1 :]


def _tag_only(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        f = _fields(ss, k)
        yield f"tag-only {k} {f[0]}", ss[:k] + [f[0]] + ss[k + 1 :]


def _hl_edits(
    ss: Segments, index: int, value: Callable[[str], str]
) -> Iterator[Tuple[str, Segments]]:
    for k in _body_range(ss):
        f = _fields(ss, k)
        if f[0] == "HL" and len(f) > index:
            g = list(f)
            g[index] = value(f[index])
            yield f"HL {k} element {index:02d}", ss[:k] + ["*".join(g)] + ss[k + 1 :]


def _hl_parent_missing(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for label, m in _hl_edits(ss, 2, lambda v: "999"):
        yield label.replace("element 02", "parent id names no HL"), m


def _hl04_flipped(ss: Segments) -> Iterator[Tuple[str, Segments]]:
    for label, m in _hl_edits(ss, 4, lambda v: "1" if v == "0" else "0"):
        yield label.replace("element 04", "child code flipped"), m


FAULTS: Dict[str, Callable[[Segments], Iterator[Tuple[str, Segments]]]] = {
    "segment-missing": _drop,
    "segment-repeated": _repeat,
    "segments-out-of-order": _swap,
    "first-element-empty": _empty_first,
    "last-element-empty": _empty_last,
    "too-few-elements": _one_element,
    "segment-tag-only": _tag_only,
    "hl-parent-id-names-no-hl": _hl_parent_missing,
    "hl04-disagrees-with-following-hl": _hl04_flipped,
}


def _outcome(text: str) -> Optional[BaseException]:
    """None for a model or a clean error; the exception for anything else."""
    try:
        with X12ModelReader(text) as reader:
            models = list(reader.models())
        for model in models:
            model.x12()
    except CLEAN_ERRORS:
        return None
    except RAW_ERRORS as exc:
        return exc
    except Exception:  # noqa: BLE001 - other types are outside this module's claim
        return None
    return None


@pytest.mark.parametrize("transaction_set", _transaction_sets())
def test_unchanged_samples_parse(transaction_set):
    """Positive control: every unmutated sample reads and writes without error."""
    for path in _samples(transaction_set):
        text = _build(_split(path.read_text()))
        with X12ModelReader(text) as reader:
            models = list(reader.models())
        assert len(models) >= 1, path.name
        for model in models:
            model.x12()


def test_the_check_notices_a_raw_exception(monkeypatch):
    """Control for the sweep itself: a handler that raises a bare KeyError is reported."""

    def boom(self, *args, **kwargs):
        raise KeyError("loop_9999")

    monkeypatch.setattr(X12ModelReader, "models", boom)
    text = _build(_split(next(iter(_samples(_transaction_sets()[0]))).read_text()))
    found = _outcome(text)
    assert isinstance(found, KeyError)


@pytest.mark.parametrize("fault", sorted(FAULTS))
@pytest.mark.parametrize("transaction_set", _transaction_sets())
def test_malformed_file_gives_a_clean_error(transaction_set, fault):
    """
    A file with one structural fault is read, or refused with a validation
    error or the library's parse exception. It never escapes as a raw
    TypeError, KeyError, IndexError, AttributeError or UnboundLocalError.
    """
    escaped: List[str] = []
    total = 0
    for path in _samples(transaction_set):
        for label, mutated in FAULTS[fault](_split(path.read_text())):
            total += 1
            exc = _outcome(_build(mutated))
            if exc is not None:
                escaped.append(
                    f"{path.name}: {label}: {type(exc).__name__}: {str(exc)[:60]}"
                )
    if total == 0:
        pytest.skip("this transaction set has no segment the fault applies to (no HL)")
    assert not escaped, (
        f"{len(escaped)} of {total} cases raised a raw exception; first five:\n"
        + "\n".join(escaped[:5])
    )
