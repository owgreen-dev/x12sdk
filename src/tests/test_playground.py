"""
test_playground.py

The browser playground's Python half (playground/app.py) runs here exactly as
it does in Pyodide, so its behaviour is tested like the rest of the library.
"""

import importlib.util
import json
import pathlib
import re

import pytest

from x12sdk import __version__
from x12sdk.generate import generate_837p

PLAYGROUND = pathlib.Path(__file__).parents[2] / "playground"

_spec = importlib.util.spec_from_file_location("playground_app", PLAYGROUND / "app.py")
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)


def call(action, *args):
    return json.loads(app.call(action, json.dumps(args)))


def test_the_worker_installs_the_released_version():
    worker = (PLAYGROUND / "worker.js").read_text()
    pinned = re.search(r'X12SDK_VERSION = "([^"]+)"', worker).group(1)
    assert pinned == __version__


def test_the_space_card_links_the_dataset():
    card = (PLAYGROUND / "README.md").read_text()
    assert "sdk: static" in card
    assert "- owgreen-dev/x12sdk" in card
    description = re.search(r"short_description: (.+)", card).group(1)
    assert len(description) <= 60


@pytest.mark.parametrize("kind", sorted(app.GENERATORS))
def test_every_sample_kind_checks_valid(kind):
    text = call("sample", kind, 1, 3)["ok"]
    result = call("inspect", text)["ok"]
    assert result["valid"], result["problems"]
    assert result["problems"] == []
    if kind in ("835", "837P", "837I", "837D"):
        table = result["table"]
        assert table["total"] >= 3
        assert table["csv"].splitlines()[0].split(",") == table["columns"]
    else:
        assert "table" not in result
        assert "no claims" in result["table_note"]


def test_a_broken_file_says_where_it_breaks():
    good = generate_837p(seed=7, claims=3)
    broken = re.sub(r"CLM\*([^*]+)\*[^*]+", r"CLM*\1*12O.00", good, count=1)
    result = call("inspect", broken)["ok"]
    assert not result["valid"]
    problem = result["problems"][0]
    assert "loop 2300 #1" in problem["where"]
    assert "CLM segment" in problem["where"]
    assert "decimal" in problem["message"]
    assert "12O.00" not in json.dumps(result)  # file content is not echoed


def test_text_that_is_not_x12_is_refused_without_reading_paths():
    for text in ("", "   ", "/etc/passwd", "hello"):
        result = call("inspect", text)["ok"]
        assert not result["valid"]
        assert result["problems"][0]["where"] == "file"


def test_large_tables_show_a_preview_but_download_everything():
    text = call("sample", "835", 2, 300)["ok"]
    table = call("inspect", text)["ok"]["table"]
    assert len(table["rows"]) == app.ROWS_SHOWN
    assert table["total"] > app.ROWS_SHOWN
    assert len(table["csv"].splitlines()) == table["total"] + 1


@pytest.mark.parametrize("claim_type", app.PAIR_TYPES)
def test_a_pair_matches_every_claim(claim_type):
    made = call("pair", claim_type, 3, 20, 0.3)["ok"]
    matches = made["matches"]
    assert matches["total"] == 20
    outcome = matches["columns"].index("outcome")
    assert {row[outcome] for row in matches["rows"]} <= {"paid", "denied"}
    again = call("match", made["claim"], made["remittance"])["ok"]["matches"]
    assert again == matches


def test_matching_reports_unanswered_claims():
    claims = call("sample", "837P", 4, 5)["ok"]
    remittance = call("pair", "837P", 9, 2, 0)["ok"]["remittance"]
    rows = call("match", claims, remittance)["ok"]["matches"]
    outcomes = [r[1] for r in rows["rows"]]
    assert "no remittance" in outcomes


@pytest.mark.parametrize(
    "action, args, words",
    [
        ("sample", ("835", 1, 0), "between 1 and 2,000"),
        ("sample", ("835", 1, 5000), "between 1 and 2,000"),
        ("pair", ("835", 1, 5, 0.1), "claim type"),
        ("pair", ("837P", 1, 5, 2), "denial rate"),
        ("match", ("nope", "ISA*"), "claim file is not X12"),
    ],
)
def test_bad_requests_come_back_as_sentences(action, args, words):
    reply = call(action, *args)
    assert words in reply["error"]
    assert "Traceback" not in reply["error"]


def test_a_malformed_match_input_is_an_error_not_a_crash():
    good = generate_837p(seed=1, claims=2)
    broken = re.sub(r"CLM\*([^*]+)\*[^*]+", r"CLM*\1*ABC", good, count=1)
    reply = call("match", broken, broken)
    assert "error" in reply
    assert "CLM segment" in reply["error"]
