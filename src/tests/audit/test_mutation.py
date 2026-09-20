"""
Leg 4: mutation.

Take a valid file, break one invariant, and require the parser to reject it.

Bug class: a validator that is attached but never fires, or one that a single
transaction set lacks. A green test suite proves the validators accept good
files; nothing in the inherited suite ever proved they reject bad ones.

Instances: the 834 had ``validate_segment_count`` commented out, so it alone
accepted a wrong SE01 (1.2.0); the 271 Red Cross check read a field that did
not exist and had never once fired (1.1.0).

Every sample in the corpus is mutated, so a new transaction set or sample is
covered as soon as it exists. Where a set genuinely has no validator for an
invariant, that is recorded in ``KNOWN_UNENFORCED`` with a reason and marked
as an expected failure, strictly, so adding the validator is noticed.
"""

from __future__ import annotations

import pathlib
from typing import Callable, List, Optional

import pytest

from x12sdk.io import X12ModelReader

RESOURCES = pathlib.Path(__file__).parent.parent / "resources"
ENVELOPE = {"ISA", "GS", "GE", "IEA"}

# (transaction set directory, mutation name) -> why the parser cannot be
# expected to reject it. Strict xfail.
KNOWN_UNENFORCED: dict = {}


def _samples():
    return sorted(p for p in RESOURCES.rglob("*") if p.is_file())


def _segments(text: str) -> List[str]:
    return [s for s in text.replace("\n", "").split("~") if s]


def _join(segments: List[str]) -> str:
    return "\n".join(s + "~" for s in segments)


def _rejects(text: str, tmp_path, name: str) -> Optional[str]:
    """None if the parser accepted the file; otherwise the exception's name."""
    path = tmp_path / name
    path.write_text(text)
    try:
        with X12ModelReader(str(path)) as reader:
            list(reader.models())
    except Exception as exc:  # noqa: BLE001 - any rejection is the point
        return type(exc).__name__
    return None


# --- mutations ----------------------------------------------------------------
#
# Each takes the segment list and returns a mutated list, or None when the
# file has nothing to mutate for that invariant (no HL, no CLP, ...).


def wrong_segment_count(segments: List[str]) -> Optional[List[str]]:
    """SE01 off by one. Every transaction set must reject this."""
    out = list(segments)
    for i, s in enumerate(out):
        if s.startswith("SE*"):
            fields = s.split("*")
            fields[1] = str(int(fields[1]) + 1)
            out[i] = "*".join(fields)
            return out
    return None


def dangling_hl_parent(segments: List[str]) -> Optional[List[str]]:
    """The last HL points at a parent id that no HL declares."""
    out = list(segments)
    hl = [i for i, s in enumerate(out) if s.startswith("HL*")]
    if len(hl) < 2:
        return None
    fields = out[hl[-1]].split("*")
    fields[2] = "999"
    out[hl[-1]] = "*".join(fields)
    return out


def unbalanced_835_claim(segments: List[str]) -> Optional[List[str]]:
    """CLP04 payment raised by 1.00 with no matching adjustment change."""
    out = list(segments)
    for i, s in enumerate(out):
        if s.startswith("CLP*"):
            fields = s.split("*")
            fields[4] = f"{float(fields[4]) + 1.0:.2f}"
            out[i] = "*".join(fields)
            return out
    return None


def claim_total_disagrees_with_lines(segments: List[str]) -> Optional[List[str]]:
    """837 CLM02 raised by 1.00 while the service lines stay put."""
    out = list(segments)
    for i, s in enumerate(out):
        if s.startswith("CLM*"):
            fields = s.split("*")
            fields[2] = f"{float(fields[2]) + 1.0:.2f}"
            out[i] = "*".join(fields)
            return out
    return None


MUTATIONS: List[Callable] = [
    wrong_segment_count,
    dangling_hl_parent,
    unbalanced_835_claim,
    claim_total_disagrees_with_lines,
]


def _cases():
    for path in _samples():
        segments = _segments(path.read_text())
        for mutation in MUTATIONS:
            if mutation(segments) is not None:
                yield pytest.param(
                    path,
                    mutation,
                    id=f"{path.parent.name}/{path.name}::{mutation.__name__}",
                )


@pytest.mark.parametrize("path,mutation", list(_cases()))
def test_the_parser_rejects_a_broken_invariant(path, mutation, tmp_path):
    key = (path.parent.name, mutation.__name__)
    if key in KNOWN_UNENFORCED:
        pytest.xfail(KNOWN_UNENFORCED[key])

    original = _segments(path.read_text())
    assert _rejects(_join(original), tmp_path, "original" + path.suffix) is None, (
        "the unmutated sample must parse, or the mutation proves nothing"
    )

    mutated = mutation(original)
    outcome = _rejects(_join(mutated), tmp_path, "mutated" + path.suffix)
    assert outcome is not None, (
        f"{path.name} still parsed after {mutation.__name__}(); the invariant is "
        f"not enforced on {path.parent.name}"
    )
