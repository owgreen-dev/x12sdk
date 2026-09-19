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

    def address(self) -> str:
        return f"{self.rng.randint(1, 9999)} {self.rng.choice(('MAIN', 'OAK', 'ELM', 'PARK', 'FIRST'))} {self.rng.choice(('ST', 'AVE', 'RD', 'BLVD'))}"

    def city(self) -> str:
        return self.rng.choice(_CITIES)

    def state(self) -> str:
        return self.rng.choice(_STATES)

    def postal_code(self) -> str:
        return str(self.rng.randint(10000, 99999))

    # --- clinical and financial -------------------------------------------

    def procedure(self) -> str:
        return self.rng.choice(_PROCEDURES)

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
