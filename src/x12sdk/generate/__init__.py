"""
Synthetic X12 generation.

Real remittances and claims contain PHI and cannot be used as test data, and
no public healthcare X12 corpus exists. This builds valid transactions from
the same models the parser produces, so you can test an X12 pipeline against
files that are guaranteed to be synthetic.

Ask for a number of claims:

```python
from x12sdk.generate import generate_835

remittance = generate_835(seed=7, claims=25)   # a complete file, envelope included
```

Or describe exactly what you want, which is how you build a test case for a
particular denial pattern:

```python
from x12sdk.generate import ClaimSpec, ServiceLineSpec, denial, generate_835

spec = [
    ClaimSpec(
        charge="500.00",
        lines=[ServiceLineSpec(charge="500.00", adjustments=[denial("CO", "97", "150.00")])],
    )
]
remittance = generate_835(seed=1, claims=spec, payer_name="EXAMPLE HEALTH PLAN")
```

A claim's payment is always derived as charge minus adjustments, so a
specification that would break the 835 balance rule cannot be expressed.

Output is deterministic: the same seed produces byte-identical bytes.
"""

import datetime
from typing import Optional, Sequence, Union

from ..io import write_transactions
from ._835 import build_835, random_claims
from ._spec import (
    GROUP_CODES,
    AdjustmentSpec,
    ClaimSpec,
    RemittanceSpec,
    ServiceLineSpec,
    denial,
    patient_responsibility,
)
from ._values import ValueFactory

#: Generation is reproducible, so the interchange timestamp is fixed rather
#: than read from the clock. Write the transaction yourself if you need a
#: real timestamp.
_EPOCH = datetime.datetime(2026, 1, 1, 12, 0)


def generate_835(
    *,
    seed: int = 0,
    claims: Union[int, Sequence[ClaimSpec]] = 5,
    payer_name: Optional[str] = None,
    payee_name: Optional[str] = None,
    sender_id: str = "SYNTHETICPAYER",
    receiver_id: str = "SYNTHETICPROV",
    control_number: str = "0001",
) -> str:
    """
    Generates a complete 835 remittance advice.

    :param seed: Reproduces the same file when unchanged.
    :param claims: A number of claims to invent, or specifications to follow.
    :param payer_name: Defaults to a synthetic plan name.
    :param payee_name: Defaults to a synthetic provider name.
    :param sender_id: ISA06 / GS02.
    :param receiver_id: ISA08 / GS03.
    :param control_number: ST02 / SE02, at least 4 characters.
    :return: The interchange, ISA through IEA.
    """
    if isinstance(claims, int):
        if claims < 1:
            raise ValueError("claims must be at least 1")
        claims = random_claims(claims, ValueFactory(seed))

    spec = RemittanceSpec(
        claims=list(claims), payer_name=payer_name, payee_name=payee_name
    )
    transaction = build_835(spec, seed=seed, control_number=control_number)
    return write_transactions(
        [transaction],
        sender_id=sender_id,
        receiver_id=receiver_id,
        # fixed so output depends only on the seed
        created=_EPOCH,
    )


__all__ = [
    "AdjustmentSpec",
    "ClaimSpec",
    "GROUP_CODES",
    "RemittanceSpec",
    "ServiceLineSpec",
    "ValueFactory",
    "build_835",
    "denial",
    "generate_835",
    "patient_responsibility",
    "random_claims",
]
