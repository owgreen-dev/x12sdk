"""
hl04_support.py

Helpers for the HL04 (hierarchical child code) handling tests.

Every sample is built inline from invented data. `build` wraps a body in the
interchange, group and transaction envelope and computes the SE segment count,
so a test lists only the segments it is about.
"""

from typing import List, Optional

import pytest
from pydantic import ValidationError

from x12sdk.io import X12ModelReader
from x12sdk.parsing import X12ParseException

ISA = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    "*260101*1200*^*00501*000000001*0*T*:~"
)

# The only failures that are an acceptable answer to a file the parser cannot
# place: a model validation error or the library's own parse exception.
CLEAN_ERRORS = (ValidationError, X12ParseException)


def build(
    transaction: str,
    group_code: str,
    version: str,
    body: List[str],
    st_version: bool = True,
) -> str:
    """Return a complete interchange; each body item is one segment without its terminator."""
    st = f"ST*{transaction}*0001*{version}" if st_version else f"ST*{transaction}*0001"
    segments = [st] + body
    segments.append(f"SE*{len(segments) + 1}*0001")
    gs = f"GS*{group_code}*SENDER*RECEIVER*20260101*1200*1*X*{version}"
    inner = "".join(f"{s}~" for s in segments)
    return f"{ISA}{gs}~{inner}GE*1*1~IEA*1*000000001~"


def transaction_set(x12_text: str) -> str:
    """The ST..SE segments of a built interchange, which is what model.x12() writes."""
    start = x12_text.index("ST*")
    end = x12_text.index("GE*")
    return x12_text[start:end]


def parse_or_clean_error(x12_text: str) -> Optional[list]:
    """
    Parse and re-serialize `x12_text`. Returns the models, or None when the
    library refused the file with a clean error. Any other exception (a raw
    TypeError, AttributeError, KeyError, ...) fails the test.
    """
    try:
        with X12ModelReader(x12_text) as reader:
            models = list(reader.models())
        for model in models:
            model.x12()
    except CLEAN_ERRORS:
        return None
    except Exception as e:  # noqa: BLE001 - the point is to name any other type
        pytest.fail(f"raw {type(e).__name__} instead of a model or a clean error: {e}")
    return models


def assert_round_trips(x12_text: str, models: list) -> None:
    """The transaction set written back equals the one read, SE count included."""
    assert len(models) == 1
    assert models[0].x12().replace("\n", "") == transaction_set(x12_text)


class Family:
    """
    The pieces of one transaction family that the HL04 scenarios are built from.

    `subscriber(hl, parent, child, tag)` and `dependent(hl, parent, tag)` give
    the segments that open a loop; `detail(tag)` gives the segments that belong
    to that loop's own detail (the benefit, status trace or claim). `tag` is
    "1", "2" or "3" so every detail is distinguishable in the model.
    """

    def __init__(
        self,
        transaction: str,
        group_code: str,
        version: str,
        head: List[str],
        first_hl: int,
        parent: int,
        subscriber,
        dependent,
        detail,
        marker,
        subscribers,
        st_version: bool = True,
    ):
        self.transaction = transaction
        self.group_code = group_code
        self.version = version
        self.head = head
        self.first_hl = first_hl
        self.parent = parent
        self.subscriber = subscriber
        self.dependent = dependent
        self.detail = detail
        self.marker = marker
        self.subscribers = subscribers
        self.st_version = st_version

    def _text(self, body: List[str]) -> str:
        return build(
            self.transaction,
            self.group_code,
            self.version,
            self.head + body,
            self.st_version,
        )

    def _sub(self, n: int, child: str, tag: str, with_detail: bool = True) -> List[str]:
        hl = self.first_hl + n
        out = self.subscriber(hl, self.parent, child, tag)
        return out + (self.detail(tag) if with_detail else [])

    def _dep(self, n: int, parent_n: int, tag: str) -> List[str]:
        return self.dependent(
            self.first_hl + n, self.first_hl + parent_n, tag
        ) + self.detail(tag)

    def two_leaf_subscribers(self) -> str:
        """Both subscribers are the patient (HL04 = 0) and carry their own detail."""
        return self._text(self._sub(0, "0", "1") + self._sub(1, "0", "2"))

    def dependent_carries_detail(self) -> str:
        """The subscriber (HL04 = 1) has only a name; its dependent carries the detail."""
        return self._text(self._sub(0, "1", "1", False) + self._dep(1, 0, "2"))

    def two_child_one_subscribers(self) -> str:
        """Two subscribers, both HL04 = 1, each with its own detail and no dependent."""
        return self._text(self._sub(0, "1", "1") + self._sub(1, "1", "2"))

    def child_one_first(self) -> str:
        """The first subscriber has HL04 = 1 and its own detail, no dependent follows."""
        return self._text(self._sub(0, "1", "1"))

    def child_one_after_leaf(self) -> str:
        """A (HL04 = 0, detail 1) then B (HL04 = 1, detail 2), no dependent."""
        return self._text(self._sub(0, "0", "1") + self._sub(1, "1", "2"))

    def child_one_after_leaf_with_dependent(self) -> str:
        """As above, then a dependent of B with detail 3."""
        return self._text(
            self._sub(0, "0", "1") + self._sub(1, "1", "2") + self._dep(2, 1, "3")
        )

    def tags_by_subscriber(self, model) -> List[set]:
        """For each subscriber in the model, the detail tags found under it."""
        out = []
        for subscriber in self.subscribers(model):
            text = subscriber.x12()
            out.append({t for t in ("1", "2", "3") if self.marker(t) in text})
        return out

    def check(self, x12_text: str, expected: List[set]) -> None:
        """
        The contract: a clean error is acceptable; otherwise the file parses,
        every detail sits under the subscriber it was written under and the
        transaction set round-trips. A raw exception fails inside
        `parse_or_clean_error`.
        """
        models = parse_or_clean_error(x12_text)
        if models is None:
            return
        assert_round_trips(x12_text, models)
        assert self.tags_by_subscriber(models[0]) == expected

    def check_parses(self, x12_text: str, expected: List[set]) -> None:
        """A positive control: the file must parse, with the details where written."""
        models = parse_or_clean_error(x12_text)
        assert models is not None, "a valid file was refused"
        assert_round_trips(x12_text, models)
        assert self.tags_by_subscriber(models[0]) == expected
