"""
Grouping of Claim Adjustment Reason Codes into analysis categories.

**No code-list text ships with x12sdk.** CARC and RARC *descriptions* are
published by X12 and the Washington Publishing Company and are licensed
separately; see <https://x12.org/codes>. What this module provides instead is
a mapping from code to an analysis *category*, which is x12sdk's own editorial
judgement about what a denial is telling you, not a reproduction of anyone's
descriptive text.

If you need the official descriptions, obtain the list under whatever licence
applies to you and load it with :func:`load_code_descriptions`.

The mapping below is a deliberately conservative starting set: codes whose
meaning is unambiguous in routine remittance work. Everything else resolves to
:data:`OTHER`, which is a statement that x12sdk has no opinion, not that the
code is unimportant. Extend it for your own book of business.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Union

# Analysis categories.
PATIENT_RESPONSIBILITY = "patient_responsibility"
CONTRACTUAL = "contractual"
ELIGIBILITY = "eligibility"
AUTHORIZATION = "authorization"
CODING = "coding"
DUPLICATE = "duplicate"
TIMELY_FILING = "timely_filing"
COORDINATION_OF_BENEFITS = "coordination_of_benefits"
MEDICAL_NECESSITY = "medical_necessity"
BUNDLING = "bundling"
NON_COVERED = "non_covered"
BENEFIT_MAXIMUM = "benefit_maximum"
MISSING_INFORMATION = "missing_information"
OTHER = "other"

# CARC -> category. Curated; see the module docstring.
_CARC_CATEGORY: Dict[str, str] = {
    # cost share
    "1": PATIENT_RESPONSIBILITY,
    "2": PATIENT_RESPONSIBILITY,
    "3": PATIENT_RESPONSIBILITY,
    # contractual write-off
    "45": CONTRACTUAL,
    # coverage in force
    "26": ELIGIBILITY,
    "27": ELIGIBILITY,
    "31": ELIGIBILITY,
    "32": ELIGIBILITY,
    "33": ELIGIBILITY,
    "177": ELIGIBILITY,
    # prior authorisation / referral
    "15": AUTHORIZATION,
    "39": AUTHORIZATION,
    "62": AUTHORIZATION,
    "197": AUTHORIZATION,
    # code set consistency
    "4": CODING,
    "5": CODING,
    "6": CODING,
    "7": CODING,
    "8": CODING,
    "9": CODING,
    "10": CODING,
    "11": CODING,
    "12": CODING,
    "13": CODING,
    "14": CODING,
    # administrative
    "16": MISSING_INFORMATION,
    "18": DUPLICATE,
    "29": TIMELY_FILING,
    # other payer liability
    "19": COORDINATION_OF_BENEFITS,
    "20": COORDINATION_OF_BENEFITS,
    "21": COORDINATION_OF_BENEFITS,
    "22": COORDINATION_OF_BENEFITS,
    "23": COORDINATION_OF_BENEFITS,
    # coverage determination
    "50": MEDICAL_NECESSITY,
    "55": MEDICAL_NECESSITY,
    "56": MEDICAL_NECESSITY,
    "96": NON_COVERED,
    "109": NON_COVERED,
    "204": NON_COVERED,
    "119": BENEFIT_MAXIMUM,
    # payment already made under another line
    "97": BUNDLING,
    "234": BUNDLING,
    #
    # Deliberately NOT mapped, though both are contractual write-offs in
    # routine remittance work:
    #
    #   A2  payer-discretionary in practice, and `contractual` is the category
    #       an analyst skips. Leaving it in `other` keeps it visible.
    #   42  retired in favour of 45. A payer still sending it is itself worth
    #       a second look, which folding it into `contractual` would hide.
    #
    # This is a judgement about what a denial review should surface, not an
    # oversight. Override it with your own mapping if your book of business
    # treats them as routine.
}


def categorize(reason_code: Optional[str]) -> str:
    """
    Returns the analysis category for a CARC, or ``other`` when unmapped.

    >>> categorize("45")
    'contractual'
    >>> categorize("A2")
    'other'
    """
    if reason_code is None:
        return OTHER
    return _CARC_CATEGORY.get(str(reason_code).strip().upper(), OTHER)


def category_map() -> Mapping[str, str]:
    """Returns a copy of the CARC to category mapping."""
    return dict(_CARC_CATEGORY)


def load_code_descriptions(
    source: Union[str, Path], *, code_field: str = "code", text_field: str = "text"
) -> Dict[str, str]:
    """
    Loads CARC/RARC descriptions from a file **you** supply.

    x12sdk ships no code-list text. Obtain the official list from
    <https://x12.org/codes> (or a CMS publication of it) under the licence that
    applies to you, then load it here.

    Accepts either a JSON object of ``{code: text}`` or a CSV with a code
    column and a text column, whose names default to ``code`` and ``text``.

    :param source: Path to a ``.json`` or ``.csv`` file.
    :param code_field: CSV column holding the code.
    :param text_field: CSV column holding the description.
    :return: Mapping of code to description.
    """
    path = Path(source)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("JSON code list must be an object of {code: text}")
        return {str(k).strip().upper(): str(v) for k, v in data.items()}

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or code_field not in reader.fieldnames:
            raise ValueError(
                f"CSV code list needs a {code_field!r} column; "
                f"found {reader.fieldnames}"
            )
        return {
            str(row[code_field]).strip().upper(): str(row.get(text_field, ""))
            for row in reader
            if row.get(code_field)
        }
