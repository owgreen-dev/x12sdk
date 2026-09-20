"""
parsing.py

Parses X12 270 005010X279A1 segments into a transactional domain model.

The parsing module includes a specific parser for the 270 transaction and loop parsing functions to create new loops
as segments are streamed to the transactional data model.

Loop parsing functions are implemented as set_[description]_loop(context: X12ParserContext, segment_data: Dict).
"""

from enum import Enum
from typing import Dict, Optional

from x12sdk.parsing import X12ParserContext, match


class TransactionLoops(str, Enum):
    """
    The loops used to support the 270 005010X279A1 format.
    """

    HEADER = "header"
    INFORMATION_SOURCE = "loop_2000a"
    INFORMATION_SOURCE_NAME = "loop_2100a"
    INFORMATION_RECEIVER = "loop_2000b"
    INFORMATION_RECEIVER_NAME = "loop_2100b"
    SUBSCRIBER = "loop_2000c"
    SUBSCRIBER_NAME = "loop_2100c"
    SUBSCRIBER_ELIGIBILITY = "loop_2110c"
    DEPENDENT = "loop_2000d"
    DEPENDENT_NAME = "loop_2100d"
    DEPENDENT_ELIGIBILITY = "loop_2110d"
    FOOTER = "footer"


def _get_info_source(context) -> Dict:
    """Returns the current information source"""

    return context.transaction_data[TransactionLoops.INFORMATION_SOURCE][-1]


def _get_info_receiver(context) -> Dict:
    """Returns the current information receiver"""

    info_source = _get_info_source(context)
    return info_source[TransactionLoops.INFORMATION_RECEIVER][-1]


# eligibility 270 loop parsing functions
@match("ST")
def set_header_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the transaction set header loop for the 270 transaction set.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """

    context.set_loop_context(
        TransactionLoops.HEADER, context.transaction_data[TransactionLoops.HEADER]
    )


@match("HL", conditions={"hierarchical_level_code": "20"})
def set_information_source_hl_loop(
    context: X12ParserContext, segment_data: Dict
) -> None:
    """
    Sets the Information Source (Payer/Clearinghouse) loop.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """
    if TransactionLoops.INFORMATION_SOURCE not in context.transaction_data:
        context.transaction_data[TransactionLoops.INFORMATION_SOURCE] = []

    context.transaction_data[TransactionLoops.INFORMATION_SOURCE].append({})
    info_source = context.transaction_data[TransactionLoops.INFORMATION_SOURCE][-1]
    context.set_loop_context(TransactionLoops.INFORMATION_SOURCE, info_source)


@match("HL", conditions={"hierarchical_level_code": "21"})
def set_information_receiver_hl_loop(
    context: X12ParserContext, segment_data: Dict
) -> None:
    """
    Sets the Information Receiver (Provider) loop.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """
    info_source = _get_info_source(context)

    if TransactionLoops.INFORMATION_RECEIVER not in info_source:
        info_source[TransactionLoops.INFORMATION_RECEIVER] = []

    info_source[TransactionLoops.INFORMATION_RECEIVER].append({})
    info_receiver = info_source[TransactionLoops.INFORMATION_RECEIVER][-1]
    context.set_loop_context(TransactionLoops.INFORMATION_RECEIVER, info_receiver)


@match("HL", conditions={"hierarchical_level_code": "22"})
def set_subscriber_hl_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the Subscriber (Member) loop
    Initializes optional TRN segment list.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """

    info_receiver = _get_info_receiver(context)

    if TransactionLoops.SUBSCRIBER not in info_receiver:
        info_receiver[TransactionLoops.SUBSCRIBER] = []

    info_receiver[TransactionLoops.SUBSCRIBER].append({"trn_segment": []})
    context.subscriber_record = info_receiver[TransactionLoops.SUBSCRIBER][-1]
    context.set_loop_context(TransactionLoops.SUBSCRIBER, context.subscriber_record)

    if context.hl_segment.get("hierarchical_child_code", "0") == "0":
        context.patient_record = context.subscriber_record


@match("NM1")
def set_entity_name_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the entity name loop based on the current loop context.
    Initializes optional REF segment list

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """

    new_loop_name: Optional[str] = None

    if context.loop_name == TransactionLoops.INFORMATION_SOURCE:
        new_loop_name = TransactionLoops.INFORMATION_SOURCE_NAME
    elif context.loop_name == TransactionLoops.INFORMATION_RECEIVER:
        new_loop_name = TransactionLoops.INFORMATION_RECEIVER_NAME
    elif context.loop_name == TransactionLoops.SUBSCRIBER:
        new_loop_name = TransactionLoops.SUBSCRIBER_NAME
    elif context.loop_name == TransactionLoops.DEPENDENT:
        new_loop_name = TransactionLoops.DEPENDENT_NAME

    context.loop_container[new_loop_name] = {"ref_segment": []}
    context.set_loop_context(new_loop_name, context.loop_container[new_loop_name])


@match("EQ")
def set_eligibility_inquiry_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the eligibility inquiry loop, 2110C or 2110D, for a subscriber or dependent record.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """

    # EQ repeats within loop 2110, so the second and later EQ segments arrive
    # while the context already sits in the eligibility loop rather than the
    # name loop. Deciding the branch from the current loop name alone was safe
    # only while a single EQ was possible.
    if context.loop_name in (
        TransactionLoops.SUBSCRIBER_NAME,
        TransactionLoops.SUBSCRIBER_ELIGIBILITY,
    ):
        name_loop = TransactionLoops.SUBSCRIBER_NAME
        loop_name = TransactionLoops.SUBSCRIBER_ELIGIBILITY
    else:
        name_loop = TransactionLoops.DEPENDENT_NAME
        loop_name = TransactionLoops.DEPENDENT_ELIGIBILITY

    patient_record = context.patient_record[name_loop]
    # Appending, not assigning: assigning kept only the last inquiry, so a
    # request covering several service types lost all but one with no error.
    patient_record.setdefault(loop_name, []).append({"amt_segment": []})
    context.set_loop_context(loop_name, patient_record[loop_name][-1])


@match("HL", conditions={"hierarchical_level_code": "23"})
def set_dependent_hl_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the hierarchy level for a dependent segment.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """
    if TransactionLoops.DEPENDENT not in context.subscriber_record:
        context.subscriber_record[TransactionLoops.DEPENDENT] = []

    context.subscriber_record[TransactionLoops.DEPENDENT].append({"trn_segment": []})

    context.patient_record = context.subscriber_record[TransactionLoops.DEPENDENT][-1]
    context.set_loop_context(TransactionLoops.DEPENDENT, context.patient_record)


@match("SE")
def set_se_loop(context: X12ParserContext, segment_data: Dict) -> None:
    """
    Sets the transaction set footer loop.

    :param context: The X12Parsing context which contains the current loop and transaction record.
    :param segment_data: The current segment's data
    """

    context.set_loop_context(
        TransactionLoops.FOOTER, context.transaction_data["footer"]
    )
