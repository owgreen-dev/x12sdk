"""
test_docs.py

Every Python example on the documentation site runs, page by page, in a
directory holding the files the examples name (all generated, so synthetic).
An example that stops working fails here before a reader finds it.
"""

import pathlib
import re

import pytest

from x12sdk.generate import (
    generate_270,
    generate_835,
    generate_837p,
    generate_claim_pair,
)

DOCS = pathlib.Path(__file__).parents[2] / "docs"
PAGES = sorted(p for p in DOCS.rglob("*.md") if "_build" not in p.parts)
BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def _sample_files(directory: pathlib.Path) -> None:
    claim, remittance = generate_claim_pair(seed=7, claims=12)
    files = {
        "remit.835": remittance,
        "remit-1.835": remittance,
        "remit-2.835": generate_835(seed=8, claims=3),
        "in.835": generate_835(seed=9, claims=4),
        "claims.837": claim,
        "inquiry.270": generate_270(seed=1, members=2),
        "submission.837": generate_837p(seed=1, claims=2),
        "carc.csv": "code,text\n45,(your licensed description)\n",
    }
    for name, text in files.items():
        (directory / name).write_text(text)


def test_there_are_pages_with_examples():
    assert sum(len(BLOCK.findall(p.read_text())) for p in PAGES) >= 15


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(DOCS)))
def test_every_python_example_runs(page, tmp_path, monkeypatch, capsys):
    blocks = BLOCK.findall(page.read_text())
    if not blocks:
        pytest.skip("no Python examples")
    _sample_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    namespace = {}  # examples on one page build on each other, as a reader's session would
    for number, block in enumerate(blocks, 1):
        try:
            exec(compile(block, f"{page.name} example {number}", "exec"), namespace)
        except Exception as error:  # pragma: no cover - the failure is the report
            pytest.fail(
                f"{page.relative_to(DOCS)} example {number} failed: {error!r}\n{block}"
            )
    capsys.readouterr()
