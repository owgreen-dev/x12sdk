"""
test_x12_276_005010X212.py

Tests the Health Care Claim Status Request Transaction
"""
import os

import pytest

from tests.support import assert_eq_model, resources_directory


@pytest.fixture
def resource_path() -> str:
    return os.path.join(resources_directory, "276_005010X212")


@pytest.mark.parametrize(
    "file_name",
    [
        "claim-level-status.276",
        "claim-level-status-ncpdp.276",
        "information-receiver-level-status.276",
        "provider-level-status.276",
    ],
)
def test_276_model(resource_path, file_name: str):
    x12_file_path = os.path.join(resource_path, file_name)
    assert os.path.exists(x12_file_path)
    assert_eq_model(x12_file_path)
