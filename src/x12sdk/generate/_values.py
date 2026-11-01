"""
Seeded value generation.

Every value comes from an explicit ``random.Random`` instance, never the global
module-level RNG, so a seed reproduces a byte-identical file and a generator
running inside someone else's test suite cannot perturb their random state.

Names are deliberately the placeholder surnames that already appear throughout
the sample corpus. Nothing here is, or is derived from, real patient data.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from random import Random
from typing import List, Sequence

_SURNAMES: Sequence[str] = (
    "DOE",
    "SMITH",
    "JONES",
    "BROWN",
    "DAVIS",
    "MILLER",
    "WILSON",
    "MOORE",
    "TAYLOR",
    "ANDERSON",
    "THOMAS",
    "JACKSON",
    "WHITE",
    "HARRIS",
    "MARTIN",
)
_GIVEN_NAMES: Sequence[str] = (
    "JANE",
    "JOHN",
    "MARY",
    "JAMES",
    "PATRICIA",
    "ROBERT",
    "LINDA",
    "MICHAEL",
    "BARBARA",
    "WILLIAM",
    "SUSAN",
    "DAVID",
    "MARGARET",
    "RICHARD",
    "DOROTHY",
)
_PLAN_NAMES: Sequence[str] = (
    "EXAMPLE HEALTH PLAN",
    "SAMPLE MUTUAL",
    "TEST BENEFIT TRUST",
    "DEMO CARE NETWORK",
    "PLACEHOLDER HEALTH",
)
_PROVIDER_NAMES: Sequence[str] = (
    "EXAMPLE MEDICAL GROUP",
    "SAMPLE CLINIC",
    "TEST FAMILY PRACTICE",
    "DEMO HEALTH CENTER",
    "PLACEHOLDER ASSOCIATES",
)
_DENTAL_PROVIDER_NAMES: Sequence[str] = (
    "EXAMPLE DENTAL GROUP",
    "SAMPLE FAMILY DENTISTRY",
    "TEST DENTAL ASSOCIATES",
    "DEMO ORAL HEALTH CENTER",
)
_EMPLOYER_NAMES: Sequence[str] = (
    "EXAMPLE EMPLOYER",
    "SAMPLE MANUFACTURING INC",
    "TEST LOGISTICS LLC",
    "DEMO RETAIL GROUP",
    "PLACEHOLDER UNIVERSITY",
    "MODEL COUNTY SCHOOLS",
)
_CITIES: Sequence[str] = (
    "SPRINGFIELD",
    "FAIRVIEW",
    "RIVERSIDE",
    "GREENVILLE",
    "FRANKLIN",
)
_STATES: Sequence[str] = ("IL", "OH", "PA", "NY", "TX", "CA", "FL", "MI")

#: Common professional procedure codes, used only so generated files look
#: plausible to a human reading them.
_PROCEDURES: Sequence[str] = (
    "99213",
    "99214",
    "99203",
    "85025",
    "80053",
    "93000",
    "71046",
    "36415",
)

#: Common dental procedure codes, for the same reason: bare codes, no
#: descriptions. Each says what else the line needs to read plausibly: nothing
#: (an exam is not done to a tooth), a tooth, or a tooth and a number of its
#: surfaces, and which teeth suit it.
_POSTERIOR_TEETH: Sequence[str] = tuple(
    str(n) for n in (*range(1, 6), *range(12, 22), *range(28, 33))
)
_ANTERIOR_TEETH: Sequence[str] = tuple(str(n) for n in (*range(6, 12), *range(22, 28)))
_MOLARS: Sequence[str] = tuple(
    str(n) for n in (1, 2, 3, 14, 15, 16, 17, 18, 19, 30, 31, 32)
)
_ALL_TEETH: Sequence[str] = tuple(str(n) for n in range(1, 33))
_DENTAL_PROCEDURES: Sequence[tuple] = (
    # (code, teeth it applies to or None, surfaces touched, surfaces to choose
    # from, fee range in dollars)
    ("D0120", None, 0, "", (40, 90)),
    ("D0274", None, 0, "", (50, 110)),
    ("D1110", None, 0, "", (80, 160)),
    ("D2391", _POSTERIOR_TEETH, 1, "MODBL", (120, 250)),
    ("D2392", _POSTERIOR_TEETH, 2, "MODBL", (160, 320)),
    ("D2330", _ANTERIOR_TEETH, 1, "MDFLI", (110, 230)),
    ("D2740", _ALL_TEETH, 0, "", (900, 1700)),
    ("D3330", _MOLARS, 0, "", (900, 1600)),
    ("D7140", _ALL_TEETH, 0, "", (120, 300)),
)
_DENTAL_FEES = {code: fees for code, *_, fees in _DENTAL_PROCEDURES}

#: Common ICD-10-CM diagnosis codes, for the same reason as the procedures
#: above: so a generated file reads plausibly. ICD-10-CM is published by CMS
#: and NCHS in the public domain; only the bare codes are used, no descriptions.
_DIAGNOSES: Sequence[str] = (
    "E1165",
    "I10",
    "J069",
    "M545",
    "Z0000",
    "R5383",
    "N390",
    "K219",
)


def _luhn_check_digit(digits: str) -> str:
    """
    Returns the check digit for an NPI.

    An NPI is validated with the Luhn algorithm over the 9 significant digits
    prefixed by the constant ``80840``. Generating a well-formed one means test
    data survives downstream identifier validation.
    """
    payload = "80840" + digits
    total = 0
    for index, char in enumerate(reversed(payload)):
        value = int(char)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return str((10 - total % 10) % 10)


class ValueFactory:
    """Produces plausible, obviously synthetic values from a seeded RNG."""

    def __init__(self, seed: int) -> None:
        self.rng = Random(seed)

    # --- identifiers ------------------------------------------------------

    def npi(self) -> str:
        """A syntactically valid 10 digit NPI, check digit included."""
        body = "".join(str(self.rng.randint(0, 9)) for _ in range(9))
        # NPIs issued to individuals and organisations begin with 1 or 2
        body = self.rng.choice("12") + body[1:]
        return body + _luhn_check_digit(body)

    def tax_id(self) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(9))

    def member_id(self) -> str:
        return f"{self.rng.choice('WXYZ')}{self.rng.randint(10**8, 10**9 - 1)}"

    def control_number(self, width: int = 9) -> str:
        return str(self.rng.randint(1, 10**width - 1)).zfill(width)

    def claim_number(self, index: int) -> str:
        return f"PCN{index:06d}"

    def payer_claim_number(self) -> str:
        return str(self.rng.randint(10**11, 10**12 - 1))

    # --- people and places ------------------------------------------------

    def person_name(self) -> tuple:
        """Returns ``(last, first)``."""
        return self.rng.choice(_SURNAMES), self.rng.choice(_GIVEN_NAMES)

    def plan_name(self) -> str:
        return self.rng.choice(_PLAN_NAMES)

    def provider_name(self) -> str:
        return self.rng.choice(_PROVIDER_NAMES)

    def dental_provider_name(self) -> str:
        return self.rng.choice(_DENTAL_PROVIDER_NAMES)

    def employer_name(self) -> str:
        return self.rng.choice(_EMPLOYER_NAMES)

    def address(self) -> str:
        return f"{self.rng.randint(1, 9999)} {self.rng.choice(('MAIN', 'OAK', 'ELM', 'PARK', 'FIRST'))} {self.rng.choice(('ST', 'AVE', 'RD', 'BLVD'))}"

    def city(self) -> str:
        return self.rng.choice(_CITIES)

    def state(self) -> str:
        return self.rng.choice(_STATES)

    def postal_code(self) -> str:
        return str(self.rng.randint(10000, 99999))

    def phone_number(self) -> str:
        """Ten digits in the 555 exchange, which is reserved for fiction."""
        return f"{self.rng.randint(200, 999)}555{self.rng.randint(0, 9999):04d}"

    # --- clinical and financial -------------------------------------------

    def procedure(self) -> str:
        return self.rng.choice(_PROCEDURES)

    def dental_procedure(self) -> tuple:
        """
        Returns ``(code, tooth, surfaces)`` for a dental service line.

        ``tooth`` is ``None`` for a procedure not done to one tooth (an exam, a
        cleaning), and ``surfaces`` is empty unless the procedure is a filling,
        whose code says how many surfaces it covers.
        """
        code, teeth, count, choices, _ = self.rng.choice(_DENTAL_PROCEDURES)
        if teeth is None:
            return code, None, ()
        tooth = self.rng.choice(teeth)
        surfaces = tuple(sorted(self.rng.sample(choices, count))) if count else ()
        return code, tooth, surfaces

    def dental_fee(self, code: str) -> Decimal:
        """A fee in the usual range for a code from :meth:`dental_procedure`."""
        low, high = _DENTAL_FEES.get(code, (40, 1500))
        return self.amount(low, high)

    def diagnosis(self) -> str:
        """An ICD-10-CM code with the decimal point removed, as X12 carries it."""
        return self.rng.choice(_DIAGNOSES)

    def birth_date(self, youngest: int = 1, oldest: int = 90) -> datetime.date:
        """A date of birth, relative to the same fixed epoch as service dates."""
        epoch = datetime.date(2026, 1, 1)
        age_days = self.rng.randint(youngest * 365, oldest * 365)
        return epoch - datetime.timedelta(days=age_days)

    def amount(self, low: int = 50, high: int = 5000) -> Decimal:
        """A money amount with two decimal places."""
        cents = self.rng.randint(low * 100, high * 100)
        return (Decimal(cents) / 100).quantize(Decimal("0.01"))

    def service_date(self, within_days: int = 365) -> datetime.date:
        """A date in the recent past, relative to a fixed epoch for reproducibility."""
        epoch = datetime.date(2026, 1, 1)
        return epoch - datetime.timedelta(days=self.rng.randint(1, within_days))

    def split(self, total: Decimal, parts: int) -> List[Decimal]:
        """
        Splits an amount into ``parts`` that sum back to it exactly.

        Used so service line charges add up to the claim charge, which the 837
        models enforce.
        """
        if parts <= 1:
            return [total]
        cents = int(total * 100)
        cuts = (
            sorted(self.rng.sample(range(1, cents), parts - 1)) if cents > parts else []
        )
        if not cuts:
            base = cents // parts
            amounts = [base] * parts
            amounts[-1] += cents - base * parts
        else:
            amounts = []
            previous = 0
            for cut in cuts:
                amounts.append(cut - previous)
                previous = cut
            amounts.append(cents - previous)
        return [(Decimal(a) / 100).quantize(Decimal("0.01")) for a in amounts]
