"""
test_hl_linkage.py

Every HL segment's parent id must name the HL it is nested under, on every
transaction set that has a hierarchy. Until 2.1.0 only the 270 and 271
checked this; the audit suite's mutation leg showed the other six accepted a
dangling parent in silence.
"""

import pytest

from x12sdk.generate import generate_276, generate_277, generate_837p
from x12sdk.io import X12ModelReader

GENERATORS = {
    "837P": lambda: generate_837p(seed=1, claims=4, dependent_rate=0.5),
    "276": lambda: generate_276(seed=1, patients=4, dependent_rate=0.5),
    "277": lambda: generate_277(seed=1, patients=4, dependent_rate=0.5),
}


def _parse(path):
    with X12ModelReader(str(path)) as reader:
        return list(reader.models())


def _edit_last_hl(x12: str, index: int, value: str) -> str:
    lines = x12.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("HL*"):
            fields = lines[i].rstrip("~").split("*")
            fields[index] = value
            lines[i] = "*".join(fields) + "~"
            return "\n".join(lines)
    raise AssertionError("no HL segment")


@pytest.mark.parametrize("label", sorted(GENERATORS))
def test_a_dangling_hl_parent_is_rejected(label, tmp_path):
    good = GENERATORS[label]()
    (tmp_path / "good").write_text(good)
    assert _parse(tmp_path / "good"), "the valid file must parse"
    (tmp_path / "bad").write_text(_edit_last_hl(good, 2, "999"))
    with pytest.raises(Exception, match="names parent '999'"):
        _parse(tmp_path / "bad")


@pytest.mark.parametrize("label", sorted(GENERATORS))
def test_a_duplicate_hl_id_is_rejected(label, tmp_path):
    good = GENERATORS[label]()
    first_id = next(line for line in good.splitlines() if line.startswith("HL*")).split(
        "*"
    )[1]
    (tmp_path / "dup").write_text(_edit_last_hl(good, 1, first_id))
    with pytest.raises(Exception, match="duplicate HL id"):
        _parse(tmp_path / "dup")
