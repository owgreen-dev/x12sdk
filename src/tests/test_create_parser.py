"""
test_create_parser.py

Tests the parser creation function.
"""

import pytest

from x12sdk.models import X12Delimiters
from x12sdk.parsing import create_parser


@pytest.mark.parametrize(
    "transaction_code, implementation_version, class_name",
    [("270", "005010X279A1", "X12Parser")],
)
def test_create_parser(transaction_code, implementation_version, class_name):
    parser = create_parser(transaction_code, implementation_version, X12Delimiters())
    assert class_name == parser.__class__.__name__

    assert "ST" in parser._loop_parsers
    assert "SE" in parser._loop_parsers
    assert len(parser._loop_parsers) > 2
