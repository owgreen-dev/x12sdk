"""
io.py

Reads X12 transaction sets into models, and writes models back out as a
complete X12 interchange.

The transaction models cover ST through SE. The interchange (ISA/IEA) and
functional group (GS/GE) envelopes are not modelled: the reader parses them
for delimiters and version and then discards them. :func:`write_transactions`
supplies them on the way out.
"""

import datetime
import logging
from io import StringIO, TextIOBase
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from .config import IsaDelimiters, TransactionSetVersionIds, get_config
from .models import X12Delimiters, X12SegmentGroup, X12SegmentName
from .parsing import X12Parser, create_parser
from .support import is_x12_data, is_x12_file

logger = logging.getLogger(__name__)

#: Transaction set code -> GS01 functional identifier code.
FUNCTIONAL_IDENTIFIER_CODES: Dict[str, str] = {
    "270": "HS",
    "271": "HB",
    "276": "HR",
    "277": "HN",
    "834": "BE",
    "835": "HP",
    "837": "HC",
}


class X12SegmentReader:
    """
    Streams segments from a X12 message or file.

    with X12Reader(x12_data) as r:
       for segment_name, segment_fields in r.segments():
          # do something interesting

    Segments are streamed in order received using a buffered generator function.
    Buffer size is configured using the config/env variable X12_READER_BUFFER_SIZE (default = 1MB).
    """

    def __init__(self, x12_input: str) -> None:
        """
        Initializes the X12SegmentReader with a x12 input.
        The x12 input may be a message payload or a path to a x12 file.

        :param x12_input: The X12 Message or a path to a X12 file
        """

        self._x12_input: str = x12_input

        # set in __enter__
        self._buffer_size: Optional[int] = None
        self._x12_stream: Optional[TextIOBase] = None
        self.delimiters: Optional[X12Delimiters] = None

    def _parse_isa_segment(self) -> Dict:
        """
        Parses fields from the ISA segment to set delimiters/instance attributes.
        The ISA segment is conveyed in the first 106 characters of the transmission.
        :return: The message delimiters as a dict
        """
        self._x12_stream.seek(0)

        isa_segment: str = self._x12_stream.read(IsaDelimiters.SEGMENT_LENGTH)

        return {
            "element_separator": isa_segment[IsaDelimiters.ELEMENT_SEPARATOR],
            "repetition_separator": isa_segment[IsaDelimiters.REPETITION_SEPARATOR],
            "segment_terminator": isa_segment[IsaDelimiters.SEGMENT_TERMINATOR],
            "component_separator": isa_segment[IsaDelimiters.COMPONENT_SEPARATOR],
        }

    def __enter__(self) -> "X12SegmentReader":
        """
        Initializes the X12 Stream and parses messages delimiters from the ISA segment.

        :return: The X12SegmentReader instance
        :raise: ValueError if the x12 input is invalid
        """
        if is_x12_file(self._x12_input):
            self._x12_stream = open(self._x12_input, "r")
        elif is_x12_data(self._x12_input):
            self._x12_stream = StringIO(self._x12_input)
        else:
            msg = f"Invalid x12_input {type(self._x12_input)}. Expecting string or file path"
            raise ValueError(msg)

        self._buffer_size: int = get_config().x12_reader_buffer_size

        self._x12_stream.seek(0)
        if not self._x12_stream.read(IsaDelimiters.SEGMENT_LENGTH):
            raise ValueError("Invalid X12Stream. Unable to read ISA Segment.")

        delimiters: Dict = self._parse_isa_segment()
        self.delimiters = X12Delimiters(**delimiters)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Closes the X12SegmentReader's X12 Stream and sets instance attributes to None

        :param exc_type: Exception Type
        :param exc_val: Exception Value
        :param exc_tb: Exception traceback
        """
        if not self._x12_stream.closed:
            self._x12_stream.close()

        self.delimiters = None
        self._x12_input = None

    def segments(self) -> Iterator[Tuple[str, List[str]]]:
        """
        Iterator function used to return X12 models from the underlying X12 stream.
        The read buffer size may be configured using X12_READER_BUFFER_SIZE.

        :return: Iterator containing segment name and segment fields.
        """
        self._x12_stream.seek(0)
        while True:
            buffer: str = self._x12_stream.read(self._buffer_size)

            if not buffer:
                break

            while buffer[-1] != self.delimiters.segment_terminator:
                next_character: str = self._x12_stream.read(1)
                if not next_character:
                    break
                buffer += next_character

            # buffer cleanup
            buffer = buffer.replace("\n", "").rstrip(self.delimiters.segment_terminator)

            for segment in buffer.split(self.delimiters.segment_terminator):
                segment_fields = segment.split(self.delimiters.element_separator)
                yield (segment_fields[0].upper(), segment_fields)


class X12ModelReader:
    """
    The X12ModelReader parses X12 segments into transactional models.
    Data is buffered using a X12SegmentReader.

    with X12ModelReader(x12_data) as r:
       for model in r.model():
          # do something interesting
    """

    def __init__(self, x12_input: str, output_delimiters: bool = False) -> None:
        """
        Initializes the X12ModelReader with a x12_input.
        The x12 input may be a message payload or a path to a x12 file.

        :param x12_input: The X12 Message or a path to a X12 file
        :param output_delimiters: Set to True to include delimiter metadata in the model with each segment.
            Defaults to False
        """
        self._x12_segment_reader: X12SegmentReader = X12SegmentReader(x12_input)
        self.output_delimiters = output_delimiters

    def __enter__(self) -> "X12ModelReader":
        """
        Initializes the X12 Stream.

        :return: The X12ModelReader instance
        """
        self._x12_segment_reader.__enter__()
        return self

    def _is_control_segment(self, segment_name) -> bool:
        """
        Returns True if the segment_name is a control segment.

        :param segment_name: The segment name
        :return: True if the segment is a control segment, otherwise False.
        """
        return segment_name in (
            X12SegmentName.ISA,
            X12SegmentName.GS,
            X12SegmentName.GE,
            X12SegmentName.IEA,
        )

    def _is_group_header(self, segment_name) -> bool:
        """
        Returns True if the segment_name is the functional group header segment

        :param segment_name: The segment name
        :return: True if the segment is the functional groupheader, otherwise False.
        """
        return segment_name == X12SegmentName.GS

    def _is_transaction_header(self, segment_name) -> bool:
        """
        Returns True if the segment_name is the transaction set header segment.

        :param segment_name: The segment name
        :return: True if the segment is the transaction set header, otherwise False.
        """
        return segment_name == X12SegmentName.ST

    def models(self) -> Iterator[X12SegmentGroup]:
        """
        Creates a stream of X12 models from a X12 segment stream.
        The stream returns transaction specific implementations of the X12SegmentGroup base class.

        :return: X12SegmentGroup model iterator
        """
        version: Optional[str] = None
        transaction_code: Optional[str] = None

        for segment_name, segment_fields in self._x12_segment_reader.segments():
            if self._is_group_header(segment_name):
                version: str = segment_fields[
                    TransactionSetVersionIds.IMPLEMENTATION_VERSION
                ]

            if self._is_control_segment(segment_name):
                continue

            if self._is_transaction_header(segment_name):
                transaction_code: str = segment_fields[
                    TransactionSetVersionIds.TRANSACTION_SET_CODE
                ]

                if version is None:
                    version: str = segment_fields[
                        TransactionSetVersionIds.FALLBACK_IMPLEMENTATION_VERSION
                    ]

                parser: X12Parser = create_parser(
                    transaction_code, version, self._x12_segment_reader.delimiters
                )

            model: X12SegmentGroup = parser.parse(
                segment_name, segment_fields, self.output_delimiters
            )
            if model:
                yield model

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exits the X12ModelReader and releases resources

        :param exc_type: Exception Type
        :param exc_val: Exception Value
        :param exc_tb: Exception traceback
        """
        self._x12_segment_reader.__exit__(exc_type, exc_val, exc_tb)


def _transaction_identity(transaction: X12SegmentGroup) -> Tuple[str, str]:
    """
    Returns ``(transaction_set_code, implementation_version)`` for a model.

    The transaction package encodes both, e.g. ``x12sdk.v5010.x12_835_005010X221A1``
    yields ``("835", "005010X221A1")``. That is more reliable than reading ST03,
    which is optional on some transaction sets (the 835 among them).
    """
    for part in type(transaction).__module__.split("."):
        if part.startswith("x12_"):
            _, code, version = part.split("_", 2)
            return code, version
    raise ValueError(
        f"Cannot determine the transaction set of {type(transaction).__name__}; "
        "it does not live in an x12_<code>_<version> package."
    )


def _interchange_id(value: str, field: str) -> str:
    """
    Validates an interchange id and pads it to the 15 characters ISA requires.

    The same value also becomes the GS application code, which the standard
    bounds at 2 to 15 characters. Checking both here gives a message that names
    the argument, rather than a validation error about a GS field the caller
    never mentioned.
    """
    stripped = value.strip()
    if not 2 <= len(stripped) <= 15:
        raise ValueError(
            f"{field} must be 2 to 15 characters, got {len(stripped)}: {value!r}"
        )
    return stripped.ljust(15)


def write_transactions(
    transactions: Iterable[X12SegmentGroup],
    *,
    sender_id: str,
    receiver_id: str,
    sender_qualifier: str = "30",
    receiver_qualifier: str = "30",
    interchange_control_number: str = "000000001",
    group_control_number: str = "1",
    created: Optional[datetime.datetime] = None,
    usage_indicator: str = "T",
    path: Optional[str] = None,
) -> str:
    """
    Writes transaction models as a complete X12 interchange.

    Transaction models cover ST through SE; this adds the ISA/IEA interchange
    and GS/GE functional group envelopes around them. Consecutive transactions
    of the same type share a functional group, so a mixed list produces one
    group per run of like transactions.

    Control numbers are kept consistent for you: IEA02 matches ISA13 and GE02
    matches GS06, and both counts reflect what was actually written.

    :param transactions: Transaction set models, e.g. from :class:`X12ModelReader`.
    :param sender_id: ISA06 interchange sender id, padded to 15 characters.
    :param receiver_id: ISA08 interchange receiver id, padded to 15 characters.
    :param sender_qualifier: ISA05, defaults to ``30`` (US federal tax id).
    :param receiver_qualifier: ISA07, defaults to ``30``.
    :param interchange_control_number: ISA13/IEA02, padded to 9 digits.
    :param group_control_number: GS06/GE02 for the first group; later groups increment.
    :param created: Timestamp for ISA09/10 and GS04/05. Defaults to now.
    :param usage_indicator: ISA15, ``T`` for test or ``P`` for production.
    :param path: Optional file to write to. The interchange is returned either way.
    :return: The complete X12 interchange.
    :raises ValueError: if a transaction's type cannot be determined, or an
        interchange id is not 2 to 15 characters.
    """
    from .v5010.segments import GeSegment, GsSegment, IeaSegment, IsaSegment

    transactions = list(transactions)
    if not transactions:
        raise ValueError("write_transactions requires at least one transaction")

    created = created or datetime.datetime.now()

    # group consecutive transactions of the same type into one functional group
    groups: List[Tuple[str, str, List[X12SegmentGroup]]] = []
    for transaction in transactions:
        code, version = _transaction_identity(transaction)
        if groups and groups[-1][0] == code and groups[-1][1] == version:
            groups[-1][2].append(transaction)
        else:
            groups.append((code, version, [transaction]))

    isa = IsaSegment(
        authorization_information_qualifier="00",
        authorization_information=" " * 10,
        security_information_qualifier="00",
        security_information=" " * 10,
        interchange_sender_qualifier=sender_qualifier,
        interchange_sender_id=_interchange_id(sender_id, "sender_id"),
        interchange_receiver_qualifier=receiver_qualifier,
        interchange_receiver_id=_interchange_id(receiver_id, "receiver_id"),
        interchange_date=created.strftime("%y%m%d"),
        interchange_time=created.strftime("%H%M"),
        repetition_separator="^",
        interchange_control_version_number="00501",
        interchange_control_number=interchange_control_number.zfill(9),
        acknowledgment_requested="0",
        interchange_usage_indicator=usage_indicator,
        component_element_separator=":",
    )

    chunks: List[str] = [isa.x12()]

    for index, (code, version, members) in enumerate(groups):
        if code not in FUNCTIONAL_IDENTIFIER_CODES:
            raise ValueError(
                f"No functional identifier code known for transaction set {code}"
            )
        control_number = str(int(group_control_number) + index)
        chunks.append(
            GsSegment(
                functional_identifier_code=FUNCTIONAL_IDENTIFIER_CODES[code],
                application_sender_code=sender_id.strip(),
                application_receiver_code=receiver_id.strip(),
                functional_group_creation_date=created.strftime("%Y%m%d"),
                functional_group_creation_time=created.strftime("%H%M"),
                group_control_number=control_number,
                responsible_agency_code="X",
                version_identifier_code=version,
            ).x12()
        )
        chunks.extend(member.x12() for member in members)
        chunks.append(
            GeSegment(
                number_of_transaction_sets_included=len(members),
                group_control_number=control_number,
            ).x12()
        )

    chunks.append(
        IeaSegment(
            number_of_included_functional_groups=len(groups),
            interchange_control_number=interchange_control_number.zfill(9),
        ).x12()
    )

    interchange = "\n".join(chunks)

    if path is not None:
        Path(path).write_text(interchange)

    return interchange
