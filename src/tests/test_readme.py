"""
test_readme.py

The README opens with a command and the file it prints. Generation is promised
to be reproducible from a seed, so that file is a contract: if a change to a
generator moves those bytes, existing users' seeded fixtures move too, and
this test is where that should be noticed.
"""

import pathlib
import re

from x12sdk.generate import generate_835

README = pathlib.Path(__file__).parents[2] / "README.md"


def _sample_lines():
    """The segments in the first bare code block after "Either way:"."""
    text = README.read_text()
    block = re.search(r"Either way:\s*```\n(.*?)```", text, re.S)
    assert block, "the README's sample output block has moved"
    return [line for line in block.group(1).splitlines() if line and line != "..."]


def test_the_readme_sample_is_what_the_library_prints():
    printed = generate_835(
        seed=7,
        claims=2,
        payer_name="EXAMPLE HEALTH PLAN",
        payee_name="EXAMPLE MEDICAL GROUP",
    ).splitlines()

    sample = _sample_lines()
    assert len(sample) > 10
    # the README elides the middle; what it shows must appear, in order
    position = 0
    for line in sample:
        assert line in printed[position:], f"README line not printed: {line}"
        position = printed.index(line, position) + 1
