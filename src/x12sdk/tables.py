"""
tables.py

One row per service line, for remittances and claims: the shape a
spreadsheet, a SQL table or a DataFrame wants, which is not the shape X12
arrives in.

    from x12sdk.tables import read_lines, to_dataframe

    rows = read_lines("remit.835")          # list of dicts, one per service line
    frame = to_dataframe("remit.835")       # the same, as a pandas DataFrame

Or from the shell, with no pandas needed:

    x12sdk-table remit.835 -o remit.csv

An 835 becomes one row per paid service line, with the payment, the claim it
belongs to, and its adjustments totalled by group (``co_amount``,
``pr_amount`` ...) alongside every ``GROUP-REASON`` code. An 837 (professional,
institutional or dental) becomes one row per billed service line, with the
claim, patient, payer and provider. Claim and remittance rows share
``patient_control_number`` (CLM01 = CLP01), which is how the two join.

Columns are fixed and documented in :data:`REMITTANCE_COLUMNS` and
:data:`CLAIM_COLUMNS`, so a pipeline built on them does not move when a file
lacks some segment: an absent value is ``None``. Amounts stay ``Decimal`` and
dates stay ``date``, so totals are exact; convert them yourself if you need
floats.

For one row per adjustment instead of per line, with reason-code categories,
see :mod:`x12sdk.denials`.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional, Sequence, TextIO

from .io import X12ModelReader

REMITTANCE_COLUMNS: Sequence[str] = (
    "transaction_set",
    "transaction_control_number",
    "payer_name",
    "payer_id",
    "payee_name",
    "payee_npi",
    "payment_trace_number",
    "payment_method",
    "payment_amount",
    "payment_date",
    "patient_control_number",
    "payer_claim_control_number",
    "claim_status_code",
    "claim_filing_indicator",
    "claim_charge",
    "claim_paid",
    "claim_patient_responsibility",
    "claim_adjustment_codes",
    "patient_last_name",
    "patient_first_name",
    "member_id",
    "line_number",
    "procedure_qualifier",
    "procedure_code",
    "modifiers",
    "revenue_code",
    "units_paid",
    "line_charge",
    "line_paid",
    "service_date",
    "co_amount",
    "pr_amount",
    "oa_amount",
    "pi_amount",
    "cr_amount",
    "adjustment_codes",
    "remark_codes",
)

CLAIM_COLUMNS: Sequence[str] = (
    "transaction_set",
    "transaction_control_number",
    "implementation",
    "billing_provider_name",
    "billing_provider_npi",
    "payer_name",
    "subscriber_last_name",
    "subscriber_first_name",
    "member_id",
    "patient_last_name",
    "patient_first_name",
    "is_dependent",
    "relationship_code",
    "patient_control_number",
    "claim_charge",
    "facility_code",
    "claim_frequency_code",
    "principal_diagnosis",
    "diagnosis_codes",
    "claim_service_date",
    "line_number",
    "procedure_qualifier",
    "procedure_code",
    "modifiers",
    "revenue_code",
    "units",
    "line_charge",
    "line_service_date",
    "tooth_number",
    "tooth_surfaces",
)

_ADJUSTMENT_GROUPS = ("CO", "PR", "OA", "PI", "CR")
_CAS_POSITIONS = range(1, 7)


def _composite(value: Optional[str]) -> List[str]:
    """
    Splits a composite such as ``HC:99213:25`` into its components.

    The models keep a composite as the file wrote it, and files choose their
    own component separator (``:`` and ``>`` are both common). Codes and
    qualifiers are letters and digits, so the first other character is the
    separator.
    """
    if not value:
        return []
    match = re.search(r"[^A-Za-z0-9]", value)
    return value.split(match.group(0)) if match else [value]


def _procedure(value: Optional[str]) -> Dict[str, Optional[str]]:
    parts = _composite(value)
    return {
        "procedure_qualifier": parts[0] if parts else None,
        "procedure_code": parts[1] if len(parts) > 1 else None,
        "modifiers": ";".join(p for p in parts[2:6] if p) or None,
    }


def _adjustments(cas_segments) -> Dict[str, Any]:
    """Totals by group code, and every ``GROUP-REASON`` in file order."""
    totals = {group: Decimal("0.00") for group in _ADJUSTMENT_GROUPS}
    codes: List[str] = []
    for cas in cas_segments or []:
        group = cas.adjustment_group_code
        for n in _CAS_POSITIONS:
            reason = getattr(cas, f"adjustment_reason_code_{n}", None)
            if reason is None:
                continue
            amount = getattr(cas, f"monetary_amount_{n}", None) or Decimal("0.00")
            if group in totals:
                totals[group] += amount
            codes.append(f"{group}-{reason}")
    row = {f"{group.lower()}_amount": total for group, total in totals.items()}
    row["adjustment_codes"] = ";".join(codes) or None
    return row


def _date(segments, qualifiers, field: str):
    # a loop holds either a list of date segments or, in places, a single one
    if segments is not None and not isinstance(segments, (list, tuple)):
        segments = [segments]
    for segment in segments or []:
        if segment.date_time_qualifier in qualifiers:
            return getattr(segment, field, None)
    return None


def _line_remarks(loop_2110) -> Optional[str]:
    codes = [
        str(lq.form_identifier)
        for lq in getattr(loop_2110, "lq_segment", None) or []
        if str(getattr(lq, "code_list_qualifier_code", "")).upper() == "HE"
        and lq.form_identifier
    ]
    return ";".join(codes) or None


def remittance_lines(transaction) -> Iterator[Dict[str, Any]]:
    """
    One row per service line of an 835, in file order.

    A claim paid without line detail (no 2110 loops) still gets one row, with
    the line columns empty, so no payment is lost from the table.
    """
    header = transaction.header
    bpr = header.bpr_segment
    trn = header.trn_segment
    payee_n1 = transaction.loop_1000b.n1_segment
    context = {
        "transaction_set": "835",
        "transaction_control_number": header.st_segment.transaction_set_control_number,
        "payer_id": getattr(
            transaction.loop_1000a.n1_segment, "identification_code", None
        ),
        "payee_npi": payee_n1.identification_code
        if payee_n1.identification_code_qualifier == "XX"
        else None,
        "payment_trace_number": getattr(trn, "reference_identification_1", None),
        "payment_method": bpr.payment_method_code,
        "payment_amount": bpr.total_actual_provider_payment_amount,
        "payment_date": getattr(bpr, "eft_effective_date", None),
    }
    for paid in transaction.claims():
        clp = paid.claim.clp_segment
        patient = paid.patient
        claim_adjustments = _adjustments(paid.adjustments)
        claim = dict(
            context,
            payer_name=paid.payer_name,
            payee_name=paid.payee_name,
            patient_control_number=clp.patient_control_number,
            payer_claim_control_number=clp.payer_claim_control_number,
            claim_status_code=clp.claim_status_code,
            claim_filing_indicator=clp.claim_filing_indicator_code,
            claim_charge=clp.total_claim_charge_amount,
            claim_paid=clp.claim_payment_amount,
            claim_patient_responsibility=clp.patient_responsibility_amount,
            claim_adjustment_codes=claim_adjustments["adjustment_codes"],
            patient_last_name=patient.name_last_or_organization_name
            if patient
            else None,
            patient_first_name=patient.name_first if patient else None,
            member_id=patient.identification_code if patient else None,
        )
        lines = paid.service_lines
        if not lines:
            yield {column: claim.get(column) for column in REMITTANCE_COLUMNS}
            continue
        for number, loop_2110 in enumerate(lines, start=1):
            svc = loop_2110.svc_segment
            row = dict(
                claim,
                line_number=number,
                **_procedure(svc.composite_medical_procedure_identifier_1),
                revenue_code=svc.revenue_code,
                units_paid=svc.units_of_service_paid_count,
                line_charge=svc.line_item_charge_amount,
                line_paid=svc.line_item_provider_payment_amount,
                service_date=_date(
                    loop_2110.dtm_segment, ("472", "150"), "production_date"
                ),
                remark_codes=_line_remarks(loop_2110),
                **_adjustments(loop_2110.cas_segment),
            )
            yield {column: row.get(column) for column in REMITTANCE_COLUMNS}


def _service(line):
    for name in ("sv1_segment", "sv2_segment", "sv3_segment"):
        segment = getattr(line, name, None)
        if segment is not None:
            return name, segment
    return None, None


def _diagnoses(claim_loop) -> List[str]:
    codes: List[str] = []
    for hi in getattr(claim_loop, "hi_segment", None) or []:
        for n in range(1, 13):
            value = getattr(hi, f"health_care_code_{n}", None)
            if value and len(value) > 1 and value[1]:
                codes.append(value[1])
    return codes


def _line_fields(line) -> Dict[str, Any]:
    kind, segment = _service(line)
    if kind == "sv1_segment":
        procedure, units, revenue = (
            segment.product_service_id_qualifier,
            segment.service_unit_count,
            None,
        )
    elif kind == "sv2_segment":
        procedure, units, revenue = (
            segment.composite_medical_procedure_identifier,
            segment.service_unit_count,
            segment.service_line_revenue_code,
        )
    elif kind == "sv3_segment":
        procedure, units, revenue = (
            segment.composite_medical_procedure_identifier,
            segment.procedure_count,
            None,
        )
    else:
        return {}
    too = (getattr(line, "too_segment", None) or [None])[0]
    surfaces = None
    if too is not None and too.tooth_surface:
        surfaces = ":".join(getattr(s, "value", s) for s in too.tooth_surface)
    return {
        **_procedure(procedure),
        "revenue_code": revenue,
        "units": units,
        "line_charge": segment.line_item_charge_amount,
        "line_service_date": _date(line.dtp_segment, ("472",), "date_time_period"),
        "tooth_number": too.tooth_number if too else None,
        "tooth_surfaces": surfaces,
    }


def claim_lines(transaction) -> Iterator[Dict[str, Any]]:
    """
    One row per service line of an 837 (P, I or D), in file order, from both
    the subscriber and the dependent branch of the hierarchy.
    """
    header = transaction.header
    st = header.st_segment
    context = {
        "transaction_set": "837",
        "transaction_control_number": st.transaction_set_control_number,
        "implementation": getattr(st, "implementation_convention_reference", None),
    }
    for claim in transaction.claims():
        clm = claim.claim.clm_segment
        location = _composite(clm.health_care_service_location_information)
        diagnoses = _diagnoses(claim.claim)
        subscriber_last, subscriber_first = claim.subscriber_name
        patient_last, patient_first = claim.patient_name
        row = dict(
            context,
            billing_provider_name=claim.billing_provider_name,
            billing_provider_npi=claim.billing_provider_npi,
            payer_name=claim.payer_name,
            subscriber_last_name=subscriber_last,
            subscriber_first_name=subscriber_first,
            member_id=claim.member_id,
            patient_last_name=patient_last,
            patient_first_name=patient_first,
            is_dependent=claim.is_dependent,
            relationship_code=claim.relationship,
            patient_control_number=claim.patient_control_number,
            claim_charge=claim.charge,
            facility_code=location[0] if location else None,
            claim_frequency_code=location[2] if len(location) > 2 else None,
            principal_diagnosis=diagnoses[0] if diagnoses else None,
            diagnosis_codes=";".join(diagnoses) or None,
            claim_service_date=_date(
                claim.claim.dtp_segment, ("472", "431", "434"), "date_time_period"
            ),
        )
        for number, line in enumerate(claim.service_lines, start=1):
            full = dict(row, line_number=number, **_line_fields(line))
            yield {column: full.get(column) for column in CLAIM_COLUMNS}


def _transactions(source) -> Iterator[Any]:
    """A model, an iterable of models, X12 text, or a path to an X12 file."""
    if isinstance(source, str):
        with X12ModelReader(source) as reader:
            yield from reader.models()
    elif hasattr(source, "header"):
        yield source
    else:
        yield from source


def iter_lines(source) -> Iterator[Dict[str, Any]]:
    """
    Rows for every 835 and 837 transaction in ``source``, one per service line.

    Other transaction sets in the same interchange are skipped. Rows from an
    835 have :data:`REMITTANCE_COLUMNS`; rows from an 837 have
    :data:`CLAIM_COLUMNS`. A file normally holds one kind; to split a mixed
    one, filter on ``transaction_set``.
    """
    for transaction in _transactions(source):
        code = transaction.header.st_segment.transaction_set_identifier_code
        if code in ("835", "837") and not hasattr(transaction, "claims"):
            raise ValueError(
                f"tables read 5010 transactions; this {code} "
                f"({type(transaction).__module__.split('.')[-2]}) is not supported"
            )
        if code == "835":
            yield from remittance_lines(transaction)
        elif code == "837":
            yield from claim_lines(transaction)


def read_lines(source) -> List[Dict[str, Any]]:
    """:func:`iter_lines` as a list."""
    return list(iter_lines(source))


def _columns_for(rows: Sequence[Dict[str, Any]]) -> Sequence[str]:
    kinds = {row["transaction_set"] for row in rows}
    if kinds == {"835"}:
        return REMITTANCE_COLUMNS
    if kinds == {"837"}:
        return CLAIM_COLUMNS
    if not kinds:
        return REMITTANCE_COLUMNS
    raise ValueError(
        "the source mixes 835 and 837 transactions; their columns differ, so "
        "read each kind separately (filter rows on transaction_set)"
    )


def to_dataframe(source):
    """
    The service-line rows of ``source`` as a pandas ``DataFrame``.

    Requires the optional pandas dependency: ``pip install 'x12sdk[pandas]'``.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "to_dataframe requires pandas. Install it with: "
            "pip install 'x12sdk[pandas]'"
        ) from exc
    rows = read_lines(source)
    return pd.DataFrame.from_records(rows, columns=list(_columns_for(rows)))


def write_csv(source, out: TextIO) -> int:
    """
    Writes the service-line rows of ``source`` as CSV to ``out``.

    :return: The number of rows written, not counting the header.
    """
    rows = read_lines(source)
    writer = csv.DictWriter(
        out, fieldnames=list(_columns_for(rows)), lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "" if v is None else v for k, v in row.items()})
    return len(rows)


def main(argv: Optional[List[str]] = None) -> int:
    """The ``x12sdk-table`` entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="x12sdk-table",
        description=(
            "Writes an 835 or 837 as CSV, one row per service line. "
            "Reads the file locally; nothing is uploaded."
        ),
    )
    parser.add_argument("file", help="path to an X12 835 or 837 file")
    parser.add_argument(
        "-o", "--out", metavar="FILE", help="write here instead of standard output"
    )
    args = parser.parse_args(argv)

    buffer = io.StringIO()
    try:
        count = write_csv(args.file, buffer)
    except ValueError as error:
        parser.error(str(error))
    if args.out:
        with open(args.out, "w", newline="") as handle:
            handle.write(buffer.getvalue())
        print(f"{count} rows written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(buffer.getvalue())
    return 0
