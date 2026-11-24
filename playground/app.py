"""
app.py

The Python half of the browser playground. worker.js loads x12sdk into
Pyodide, then calls these functions; each returns JSON text for the page.

Everything here runs inside the visitor's browser tab. Nothing is sent
anywhere, which is why the page can say so.
"""

import csv
import io
import json
from dataclasses import asdict

from x12sdk import __version__
from x12sdk.generate import (
    generate_270,
    generate_271,
    generate_276,
    generate_277,
    generate_834,
    generate_835,
    generate_837d,
    generate_837i,
    generate_837p,
    generate_claim_pair,
)
from x12sdk.matching import MATCH_COLUMNS, match_rows
from x12sdk.tables import CLAIM_COLUMNS, REMITTANCE_COLUMNS, read_lines
from x12sdk.validation import READ_ERRORS, check, problems

#: Rows drawn on the page; the CSV download always has every row.
ROWS_SHOWN = 200

#: The most a visitor can generate at once, to keep the tab responsive.
MAX_COUNT = 2000

#: kind -> (generator, the name of its count argument, what is counted)
GENERATORS = {
    "835": (generate_835, "claims", "claims"),
    "837P": (generate_837p, "claims", "claims"),
    "837I": (generate_837i, "claims", "claims"),
    "837D": (generate_837d, "claims", "claims"),
    "270": (generate_270, "members", "members"),
    "271": (generate_271, "members", "members"),
    "276": (generate_276, "patients", "patients"),
    "277": (generate_277, "patients", "patients"),
    "834": (generate_834, "enrollees", "enrollees"),
}

PAIR_TYPES = ("837P", "837I", "837D")


def _cell(value):
    return "" if value is None else str(value)


def _table(columns, rows):
    """Columns, the first rows for the page, and every row as CSV."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    cells = [[_cell(row.get(c)) for c in columns] for row in rows]
    writer.writerows(cells)
    return {
        "columns": list(columns),
        "rows": cells[:ROWS_SHOWN],
        "total": len(cells),
        "csv": buffer.getvalue(),
    }


def _bounded(count):
    count = int(count)
    if not 1 <= count <= MAX_COUNT:
        raise ValueError(f"choose between 1 and {MAX_COUNT:,}")
    return count


def version():
    return __version__


def inspect(text):
    """
    Checks X12 text and, when it is a valid 835 or 837, turns it into one row
    per service line.
    """
    if not text.strip():
        return json.dumps(
            {
                "valid": False,
                "transactions": [],
                "problems": [{"where": "file", "message": "the file is empty"}],
            }
        )
    if not text.lstrip().startswith("ISA"):
        # check() also accepts a path; in the browser only text makes sense
        return json.dumps(
            {
                "valid": False,
                "transactions": [],
                "problems": [
                    {
                        "where": "file",
                        "message": "not an X12 file: X12 begins with an ISA segment",
                    }
                ],
            }
        )
    result = check(text)
    out = {
        "valid": result.valid,
        "transactions": [asdict(t) for t in result.transactions],
        "problems": [{"where": p.where, "message": p.message} for p in result.problems],
    }
    if result.valid:
        try:
            rows = read_lines(text)
        except ValueError as error:  # e.g. a 4010 file: valid, but no table
            out["table_note"] = str(error)
        else:
            kinds = {row["transaction_set"] for row in rows}
            if not rows:
                out["table_note"] = (
                    "tables are made from 835 and 837 files; this file has "
                    "no claims or service lines"
                )
            elif len(kinds) > 1:
                out["table_note"] = (
                    "this file mixes 835 and 837 transactions, whose columns "
                    "differ; open each kind separately"
                )
            else:
                columns = REMITTANCE_COLUMNS if kinds == {"835"} else CLAIM_COLUMNS
                out["table"] = _table(columns, rows)
    return json.dumps(out)


def sample(kind, seed, count):
    """A synthetic file of one kind, as X12 text."""
    generator, argument, _ = GENERATORS[kind]
    return generator(seed=int(seed), **{argument: _bounded(count)})


def pair(claim_type, seed, count, denial_rate):
    """A claim file, the remittance that answers it, and how they match."""
    if claim_type not in PAIR_TYPES:
        raise ValueError(f"claim type must be one of {', '.join(PAIR_TYPES)}")
    rate = float(denial_rate)
    if not 0 <= rate <= 1:
        raise ValueError("the denial rate is a share between 0 and 1")
    made = generate_claim_pair(
        seed=int(seed),
        claims=_bounded(count),
        claim_type=claim_type.lower(),
        denial_rate=rate,
    )
    return json.dumps(
        {
            "claim": made.claim,
            "remittance": made.remittance,
            "matches": _table(
                MATCH_COLUMNS, list(match_rows(made.claim, made.remittance))
            ),
        }
    )


def match(claims_text, remittance_text):
    """Joins a visitor's own 837 and 835 on the patient control number."""
    for name, text in (("claim", claims_text), ("remittance", remittance_text)):
        if not text.lstrip().startswith("ISA"):
            raise ValueError(
                f"the {name} file is not X12: X12 begins with an ISA segment"
            )
    rows = list(match_rows(claims_text, remittance_text))
    return json.dumps({"matches": _table(MATCH_COLUMNS, rows)})


_ACTIONS = {"inspect": inspect, "sample": sample, "pair": pair, "match": match}


def call(action, arguments_json):
    """
    The one entry point worker.js uses: runs an action and returns
    ``{"ok": result}`` or ``{"error": message}``, so a bad file comes back as
    a sentence rather than a traceback.
    """
    try:
        result = _ACTIONS[action](*json.loads(arguments_json))
    except READ_ERRORS as error:
        found = problems(error) or [None]
        first = found[0]
        if first is None:
            message = str(error)
        elif first.where == "file":
            message = first.message
        else:
            message = f"{first.where}: {first.message}"
        if len(found) > 1:
            message += f" (and {len(found) - 1} more)"
        return json.dumps({"error": message})
    if action in ("inspect", "pair", "match"):
        return json.dumps({"ok": json.loads(result)})
    return json.dumps({"ok": result})
