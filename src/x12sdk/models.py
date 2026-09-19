"""
models.py

Base models for X12 parsing and validation.
"""

import abc
import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _field_type(annotation: Any) -> Any:
    """
    Returns the model/scalar type an annotation ultimately refers to.

    ``Optional[List[Loop2300]]`` -> ``Loop2300``, ``str`` -> ``str``. Used in
    place of Pydantic v1's ``ModelField.type_``.
    """
    while True:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if not args:
            return annotation
        annotation = args[0]


def _is_list_field(annotation: Any) -> bool:
    """
    True when an annotation declares a list, including ``Optional[List[T]]``.

    Replaces Pydantic v1's ``ModelField.shape == SHAPE_LIST``.
    """
    if get_origin(annotation) is list:
        return True
    return any(
        get_origin(arg) is list for arg in get_args(annotation) if arg is not type(None)
    )


class X12Delimiters(BaseModel):
    """
    X12Delimiters models the message delimiters used within a X12 transaction.
    """

    element_separator: str = Field("*", min_length=1, max_length=1)
    repetition_separator: str = Field("^", min_length=1, max_length=1)
    segment_terminator: str = Field("~", min_length=1, max_length=1)
    component_separator: str = Field(":", min_length=1, max_length=1)
    # the model is immutable and hashable
    model_config = ConfigDict(frozen=True)


class X12SegmentName(str, Enum):
    """
    Supported X12 Segment Names
    """

    AAA = "AAA"
    ACT = "ACT"
    AMT = "AMT"
    BGN = "BGN"
    BHT = "BHT"
    BPR = "BPR"
    CAS = "CAS"
    CLM = "CLM"
    CLP = "CLP"
    CL1 = "CL1"
    CN1 = "CN1"
    COB = "COB"
    CR1 = "CR1"
    CR2 = "CR2"
    CR3 = "CR3"
    CR5 = "CR5"
    CR6 = "CR6"
    CR7 = "CR7"
    CRC = "CRC"
    CTP = "CTP"
    CUR = "CUR"
    DMG = "DMG"
    DSB = "DSB"
    DTM = "DTM"
    DTP = "DTP"
    EB = "EB"
    EC = "EC"
    EQ = "EQ"
    FRM = "FRM"
    GE = "GE"
    GS = "GS"
    HCP = "HCP"
    HD = "HD"
    HI = "HI"
    HL = "HL"
    HLH = "HLH"
    HSD = "HSD"
    ICM = "ICM"
    IDC = "IDC"
    IEA = "IEA"
    III = "III"
    INS = "INS"
    ISA = "ISA"
    K3 = "K3"
    LE = "LE"
    LIN = "LIN"
    LUI = "LUI"
    LQ = "LQ"
    LS = "LS"
    LX = "LX"
    MEA = "MEA"
    MIA = "MIA"
    MOA = "MOA"
    MPI = "MPI"
    MSG = "MSG"
    N1 = "N1"
    N3 = "N3"
    N4 = "N4"
    NM1 = "NM1"
    NTE = "NTE"
    OI = "OI"
    PAT = "PAT"
    PER = "PER"
    PLA = "PLA"
    PLB = "PLB"
    PRV = "PRV"
    PS1 = "PS1"
    PWK = "PWK"
    QTY = "QTY"
    RDM = "RDM"
    REF = "REF"
    SBR = "SBR"
    SE = "SE"
    ST = "ST"
    STC = "STC"
    SVC = "SVC"
    SV1 = "SV1"
    SV2 = "SV2"
    SV5 = "SV5"
    SVD = "SVD"
    TRN = "TRN"
    TS2 = "TS2"
    TS3 = "TS3"


class X12Segment(abc.ABC, BaseModel):
    """
    X12BaseSegment serves as the abstract base class for all X12 segment models.
    """

    delimiters: Optional[X12Delimiters] = None
    segment_name: X12SegmentName
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    def _process_multivalue_field(
        self,
        field_name: str,
        field_value: List,
        custom_delimiters: X12Delimiters = None,
    ) -> str:
        """
        Converts a X12 multi-value (list) field into a a single delimited string.

        A "multi-value" field is a field which contains sub-fields, or components, or allows repeats.
        The X12 specification uses separate delimiters for component and repeating fields.

        By default the method will use default X12 delimiters. Custom delimiters may be specified if desired using
        the `custom_delimiters` parameter.

        :param field_name: The field name used to lookup field metadata.
        :param field_value: The field's list values
        :param custom_delimiters: Used when custom delimiters are required. Defaults to None.
        """

        delimiters = custom_delimiters or X12Delimiters()
        extra = type(self).model_fields[field_name].json_schema_extra or {}
        is_component_field: bool = extra.get("is_component", False)
        if is_component_field:
            join_character = delimiters.component_separator
        else:
            join_character = delimiters.repetition_separator
        return join_character.join(field_value)

    def x12(self, custom_delimiters: X12Delimiters = None) -> str:
        """
        Generates a X12 formatted string for the segment.
        By default, the method will use default X12 delimiters. Custom delimiters may be specified if desired using
        the `custom_delimiters` parameter.

        :param custom_delimiters: Used when custom delimiters are required. Defaults to None.
        :return: the X12 representation of the model instance
        """

        delimiters = custom_delimiters or X12Delimiters()
        x12_values = []
        for k, v in self.model_dump(exclude={"delimiters"}).items():
            if isinstance(v, str):
                x12_values.append(v)
            elif isinstance(v, list):
                x12_values.append(
                    self._process_multivalue_field(k, v, custom_delimiters=delimiters)
                )
            elif isinstance(v, datetime.datetime):
                x12_values.append(v.strftime("%Y%m%d%H%M"))
            elif isinstance(v, datetime.date):
                x12_values.append(v.strftime("%Y%m%d"))
            elif isinstance(v, datetime.time):
                x12_values.append(v.strftime("%H%M"))
            elif isinstance(v, Decimal):
                # Decimal keeps the scale it was parsed with, so "2" stays "2"
                # and "545.00" stays "545.00". "f" avoids scientific notation.
                x12_values.append(format(v, "f"))
            elif v is None:
                x12_values.append("")
            else:
                x12_values.append(str(v))

        x12_str = delimiters.element_separator.join(x12_values).rstrip(
            delimiters.element_separator
        )
        return x12_str + delimiters.segment_terminator


class X12SegmentGroup(abc.ABC, BaseModel):
    """
    Abstract base class for a container, typically a loop or transaction, which groups x12 segments.
    """

    @model_validator(mode="before")
    @classmethod
    def _wrap_single_repeatable_segments(cls, values):
        """
        Accepts a single segment record where the model declares a list.

        The parser stores the first occurrence of a segment as a dict and only
        appends when the loop initializer pre-seeded a list. If an initializer
        misses a repeatable segment, the model would otherwise reject a bare
        dict for a ``List[...]`` field. Wrapping it here keeps a missed
        pre-seed from being a validation failure.
        """
        if not isinstance(values, dict):
            return values
        for name, field in cls.model_fields.items():
            if not _is_list_field(field.annotation):
                continue
            value = values.get(name)
            if isinstance(value, dict):
                values[name] = [value]
        return values

    def x12(
        self, use_new_lines: bool = True, custom_delimiters: X12Delimiters = None
    ) -> str:
        """
        Generates a X12 formatted string for the segment.

        By default the method will use default X12 delimiters. Custom delimiters may be specified if desired using
        the `custom_delimiters` parameter.

        :param use_new_lines: Indicates if the X12 output includes newline characters. Defaults to True.
        :param custom_delimiters: Used when custom delimiters are required. Defaults to None.
        :return: Generates a X12 representation of the loop using its segments.
        """
        delimiters = custom_delimiters or X12Delimiters()
        x12_segments: List[str] = []
        fields = [
            name
            for name, field in type(self).model_fields.items()
            if hasattr(_field_type(field.annotation), "x12")
        ]

        for field_name in fields:
            field_instance = getattr(self, field_name)

            if field_instance is None:
                continue
            elif isinstance(field_instance, list):
                for item in field_instance:
                    if isinstance(item, X12Segment):
                        x12_segments.append(item.x12(custom_delimiters=delimiters))
                    else:
                        x12_segments.append(
                            item.x12(
                                use_new_lines=use_new_lines,
                                custom_delimiters=delimiters,
                            )
                        )
            else:
                if isinstance(field_instance, X12Segment):
                    x12_segments.append(
                        field_instance.x12(custom_delimiters=delimiters)
                    )
                else:
                    x12_segments.append(
                        field_instance.x12(
                            use_new_lines=use_new_lines, custom_delimiters=delimiters
                        )
                    )

        join_char: str = "\n" if use_new_lines else ""
        return join_char.join(x12_segments)
