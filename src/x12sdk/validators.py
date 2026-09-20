"""
validators.py

The validator functions in this module are reused across loops within a X12 transaction model.

Model validators have the signature (self) and are registered with
``model_validator(mode="after")``. They read field values through
``self.__dict__`` and return ``self``.

Field validators are registered with ``field_validator(<field name>)`` and take
either (cls, v) or (cls, v, info), where ``info.data`` holds the fields
validated before this one.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, Union

from pydantic import ValidationInfo

from .support import count_segments, parse_x12_date


def _validate_duplicate_codes(values: Dict, segment_name: str, code_field: str):
    """
    Validates duplicate code values for repeating segments.

    Example: Some transactional loops support multiple date, DTP, segments. For these cases this validation ensures
    that the date_time_qualifier is unique within the loop for the repeating segments.

    Given _validate_duplicate_codes(values, "amt_segment", "amount_qualifier_code"), the following segments are valid:
    AMT*D*411~
    AMT*A8*420~

    The following segments are invalid due to duplicate codes
    AMT*D*411~
    AMT*D*411~
    """
    codes = defaultdict(int)
    # `or []` rather than a get() default: on a model built in Python the key
    # is always present and set to None. Only the parser pre-seeds a list, so
    # a get() default never fires and every constructed loop raised TypeError.
    for segment in values.get(segment_name) or []:
        # account for differing internal representation: model vs dict
        if not isinstance(segment, dict):
            segment = segment.model_dump()

        code = segment.get(code_field)
        codes[code] += 1

    duplicate_codes = {k for k, v in codes.items() if v > 1}
    if duplicate_codes:
        raise ValueError(
            f"Duplicate {segment_name}.{code_field} codes {duplicate_codes}"
        )
    return values


def validate_duplicate_ref_codes(self):
    """
    Validates that a loop does not contain duplicate REF codes.

    :param values: The validated transaction data.
    :raises: ValueError if duplicate REF codes are found.
    """
    values = self.__dict__
    _validate_duplicate_codes(
        values, "ref_segment", "reference_identification_qualifier"
    )
    return self


def validate_duplicate_amt_codes(self):
    """
    Validates that a loop does not contain duplicate REF codes.

    :param values: The validated transaction data.
    :raises: ValueError if duplicate REF codes are found.
    """
    values = self.__dict__
    _validate_duplicate_codes(values, "amt_segment", "amount_qualifier_code")
    return self


def validate_duplicate_date_qualifiers(self):
    """
    Validates that a loop does not contain duplicate DTP date qualifiers.

    :param values: The validated transaction data.
    :raises: ValueError if duplicate DTP date qualifiers are found.
    """
    values = self.__dict__
    _validate_duplicate_codes(values, "dtp_segment", "date_time_qualifier")
    return self


def validate_date_field(
    cls, v, info: ValidationInfo
) -> Union[datetime.date, str, None]:
    """
    Validates a date field using the segment's date_time_period_format_qualifier (D8 or RD8).
    The date_time_period_format_qualifier is used to indicate if a date field is a specific date or a date range.
    Specific dates are have a "D8" qualifier value, while date ranges are qualified using "RD8".

    :param v: The date field value
    :param info: Validation context; ``info.data`` holds the fields already validated.
    :return: The validated date field value
    :raises: ValueError if the date field value is an invalid format.
    """
    from x12sdk.v5010.segments import DtpSegment

    def handle_x12_date(date_string: str):
        """Parses a x12 date string, raising a ValueError if an error occurs"""
        try:
            return parse_x12_date(date_string)
        except ValueError:
            raise ValueError(f"Invalid date value {date_string}")

    qualifier = info.data.get("date_time_period_format_qualifier")

    # the date field may be "optional" in which case the qualifier is not present
    # if the qualifier field is required, it will be validated at the field level
    if not qualifier:
        return v

    if (
        qualifier == DtpSegment.DateTimePeriodFormatQualifier.DATE_RANGE
        and "-" not in v
    ):
        raise ValueError(f"Invalid date range {v}")
    elif qualifier == DtpSegment.DateTimePeriodFormatQualifier.DATE_RANGE:
        for d in v.split("-"):
            handle_x12_date(d)
        return v
    else:
        return handle_x12_date(v)


def validate_segment_count(self):
    """
    Validates the segment count conveyed in the transaction set footer, or SE segment.
    This function is only able to count "valid" segments since it is invoked as a "post" validator.

    :param values: The valid transaction set values.
    """
    values = self.__dict__
    expected_count: int = values["footer"].se_segment.transaction_segment_count

    if not expected_count:
        raise ValueError("Expected transaction count not found in SE segment")

    actual_count: int = count_segments(values)

    if expected_count != actual_count:
        raise ValueError(
            f"SE segment count {expected_count} != actual count {actual_count}"
        )

    return self
