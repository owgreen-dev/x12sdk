"""
test_resource_roundtrip.py

The round-trip oracle: every sample X12 file under ``resources/`` must parse
into models, validate, and serialize back to exactly the input bytes.

This sweep is the safety net for refactors and library migrations. Transaction
specific tests exercise individual samples; this module guarantees that no
sample is silently left out and that any regression in serialization fidelity
is reported per file.
"""

import os

import pytest

from .support import assert_eq_model, resources_directory


def _sample_files():
    """All sample files under the resources directory, sorted for stable ids."""
    files = []
    for root, _, names in os.walk(resources_directory):
        for name in names:
            files.append(os.path.join(root, name))
    return sorted(files)


def _sample_id(path: str) -> str:
    """``<implementation>/<file>`` so failures read as e.g. 835_005010X221A1/managed-care.835."""
    return os.path.relpath(path, resources_directory)


SAMPLE_FILES = _sample_files()


def test_resources_present():
    """Guard against the sweep silently running over an empty directory."""
    assert len(SAMPLE_FILES) >= 61, SAMPLE_FILES


@pytest.mark.parametrize("x12_path", SAMPLE_FILES, ids=_sample_id)
def test_resource_roundtrip(x12_path):
    """parse -> validate -> serialize reproduces the sample byte for byte."""
    assert_eq_model(x12_path)
