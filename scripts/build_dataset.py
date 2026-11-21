"""
Builds the public synthetic dataset: X12 claim submissions, the remittances
that answer them, and two flat tables read back out of those files.

    python scripts/build_dataset.py --out dataset

Everything comes from x12sdk's generators, so nothing here is, or is derived
from, real patient data, and the same arguments rebuild the same bytes. The
tables are made by *parsing* the generated X12 with the library's own reader
and accessors, the way a user's pipeline would, not by copying the specs
the files were made from.

Layout written under --out:

    data/claims.jsonl        one row per claim: as billed, and what the payer did
    data/service_lines.jsonl one row per service line, likewise
    data/*.csv               the same two tables as CSV, for spreadsheets

The tables are written twice on purpose. JSON Lines carries types: a code such
as revenue code 0510 stays text, and amounts stay numbers. CSV does not, and
a loader that guesses types from it turns 0510 into 510. The dataset card
points Hugging Face's viewer at the JSON Lines files.
    x12/<type>/pair-NNN.837  a claim submission (ISA..IEA)
    x12/<type>/pair-NNN.835  the remittance answering it
    README.md                the dataset card, with the counts filled in
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from x12sdk import __version__
from x12sdk.generate import generate_claim_pair
from x12sdk.io import X12ModelReader

CLAIM_TYPES = ("837p", "837i", "837d")

CLAIM_COLUMNS = [
    "claim_type",
    "pair",
    "patient_control_number",
    "service_date",
    "claim_charge",
    "line_count",
    "is_dependent",
    "relationship_code",
    "patient_gender",
    "patient_birth_year",
    "diagnosis_code",
    "payer_name",
    "billing_provider_name",
    "billing_provider_npi",
    "claim_status_code",
    "denied",
    "paid_amount",
    "contractual_adjustment",
    "patient_responsibility",
    "denial_reason_code",
    "payer_claim_control_number",
]

LINE_COLUMNS = [
    "claim_type",
    "pair",
    "patient_control_number",
    "line_number",
    "procedure_qualifier",
    "procedure_code",
    "revenue_code",
    "units",
    "line_charge",
    "tooth_number",
    "tooth_surfaces",
    "line_paid",
    "contractual_adjustment",
    "patient_responsibility",
    "adjustment_reasons",
]

ZERO = Decimal("0.00")


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        (model,) = list(reader.models())
    return model


def _service_segment(line):
    for name in ("sv1_segment", "sv2_segment", "sv3_segment"):
        segment = getattr(line, name, None)
        if segment is not None:
            return segment
    raise ValueError("a service line without SV1, SV2 or SV3")


def _procedure(segment) -> str:
    return getattr(segment, "product_service_id_qualifier", None) or (
        segment.composite_medical_procedure_identifier
    )


def _adjustments(cas_segments) -> Dict[str, object]:
    """Totals by group, and every group-reason pair in file order."""
    totals = {"CO": ZERO, "PR": ZERO}
    reasons: List[str] = []
    for cas in cas_segments or []:
        for n in range(1, 7):
            reason = getattr(cas, f"adjustment_reason_code_{n}")
            if reason is None:
                continue
            amount = getattr(cas, f"monetary_amount_{n}") or ZERO
            group = cas.adjustment_group_code
            totals[group] = totals.get(group, ZERO) + amount
            reasons.append(f"{group}-{reason}")
    return {
        "contractual_adjustment": totals.get("CO", ZERO),
        "patient_responsibility": totals.get("PR", ZERO),
        "reasons": reasons,
    }


def _service_date(claim) -> Optional[str]:
    for dtp in claim.claim.dtp_segment or []:
        if dtp.date_time_qualifier in ("431", "434", "472"):
            return str(dtp.date_time_period)
    for line in claim.service_lines:
        for dtp in getattr(line, "dtp_segment", None) or []:
            if dtp.date_time_qualifier == "472":
                return str(dtp.date_time_period)
    return None


def _diagnosis(claim) -> Optional[str]:
    for hi in claim.claim.hi_segment or []:
        if hi.health_care_code_1:
            return hi.health_care_code_1[1]
    return None


def _rows(claim_type: str, pair_number: int, claim_x12: str, remittance_x12: str):
    submission = _read(claim_x12)
    remittance = _read(remittance_x12)
    paid_by_number = {c.patient_control_number: c for c in remittance.claims()}

    claims, lines = [], []
    for claim in submission.claims():
        paid = paid_by_number[claim.patient_control_number]
        dmg = getattr(claim.patient, "dmg_segment", None)
        line_adjustments = [_adjustments(svc.cas_segment) for svc in paid.service_lines]
        claim_level = _adjustments(paid.adjustments)
        reasons = [r for a in line_adjustments for r in a["reasons"]]
        claims.append(
            {
                "claim_type": claim_type,
                "pair": pair_number,
                "patient_control_number": claim.patient_control_number,
                "service_date": _service_date(claim),
                "claim_charge": claim.charge,
                "line_count": len(claim.service_lines),
                "is_dependent": claim.is_dependent,
                "relationship_code": claim.relationship,
                "patient_gender": dmg.gender_code if dmg else None,
                "patient_birth_year": dmg.date_time_period.year if dmg else None,
                "diagnosis_code": _diagnosis(claim),
                "payer_name": claim.payer_name,
                "billing_provider_name": claim.billing_provider_name,
                "billing_provider_npi": claim.billing_provider_npi,
                "claim_status_code": paid.status,
                "denied": paid.status == "4",
                "paid_amount": paid.paid,
                "contractual_adjustment": sum(
                    (a["contractual_adjustment"] for a in line_adjustments),
                    claim_level["contractual_adjustment"],
                ),
                "patient_responsibility": sum(
                    (a["patient_responsibility"] for a in line_adjustments),
                    claim_level["patient_responsibility"],
                ),
                "denial_reason_code": reasons[0].split("-", 1)[1]
                if paid.status == "4" and reasons
                else None,
                "payer_claim_control_number": paid.payer_claim_control_number,
            }
        )

        for number, (line, svc, adjusted) in enumerate(
            zip(claim.service_lines, paid.service_lines, line_adjustments), start=1
        ):
            segment = _service_segment(line)
            qualifier, code = _procedure(segment).split(":", 1)
            too = (getattr(line, "too_segment", None) or [None])[0]
            lines.append(
                {
                    "claim_type": claim_type,
                    "pair": pair_number,
                    "patient_control_number": claim.patient_control_number,
                    "line_number": number,
                    "procedure_qualifier": qualifier,
                    "procedure_code": code,
                    "revenue_code": getattr(segment, "service_line_revenue_code", None),
                    "units": getattr(segment, "service_unit_count", None)
                    or getattr(segment, "procedure_count", None),
                    "line_charge": segment.line_item_charge_amount,
                    "tooth_number": too.tooth_number if too else None,
                    "tooth_surfaces": ":".join(too.tooth_surface or [])
                    if too
                    else None,
                    "line_paid": svc.svc_segment.line_item_provider_payment_amount,
                    "contractual_adjustment": adjusted["contractual_adjustment"],
                    "patient_responsibility": adjusted["patient_responsibility"],
                    "adjustment_reasons": ";".join(adjusted["reasons"]) or None,
                }
            )
    return claims, lines


def _write_csv(path: pathlib.Path, columns: List[str], rows: Iterable[Dict]) -> int:
    count = 0
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if v is None else v for k, v in row.items()})
            count += 1
    return count


#: Columns written as JSON integers and numbers; every other column is text,
#: because codes and identifiers (0510, 01, PCN000001) are not quantities.
INTEGER_COLUMNS = {"pair", "line_count", "patient_birth_year", "line_number", "units"}
NUMBER_COLUMNS = {
    "claim_charge",
    "paid_amount",
    "contractual_adjustment",
    "patient_responsibility",
    "line_charge",
    "line_paid",
}


def _typed(column: str, value):
    if value is None or isinstance(value, bool):
        return value
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in NUMBER_COLUMNS:
        return float(value)
    return str(value)


def _write_jsonl(path: pathlib.Path, columns: List[str], rows: Iterable[Dict]) -> int:
    count = 0
    with path.open("w") as handle:
        for row in rows:
            typed = {column: _typed(column, row[column]) for column in columns}
            handle.write(json.dumps(typed, separators=(",", ":")) + "\n")
            count += 1
    return count


def build(out: pathlib.Path, seed: int, pairs: int, claims_per_pair: int) -> Dict:
    (out / "data").mkdir(parents=True, exist_ok=True)
    all_claims, all_lines = [], []
    for type_index, claim_type in enumerate(CLAIM_TYPES):
        folder = out / "x12" / claim_type
        folder.mkdir(parents=True, exist_ok=True)
        for number in range(pairs):
            pair_seed = seed * 10_000 + type_index * 1_000 + number
            pair = generate_claim_pair(
                seed=pair_seed, claims=claims_per_pair, claim_type=claim_type
            )
            (folder / f"pair-{number:03d}.837").write_text(pair.claim + "\n")
            (folder / f"pair-{number:03d}.835").write_text(pair.remittance + "\n")
            claims, lines = _rows(claim_type, number, pair.claim, pair.remittance)
            all_claims.extend(claims)
            all_lines.extend(lines)

    stats = {
        "claims": _write_csv(out / "data" / "claims.csv", CLAIM_COLUMNS, all_claims),
        "lines": _write_csv(
            out / "data" / "service_lines.csv", LINE_COLUMNS, all_lines
        ),
        "claims_jsonl": _write_jsonl(
            out / "data" / "claims.jsonl", CLAIM_COLUMNS, all_claims
        ),
        "lines_jsonl": _write_jsonl(
            out / "data" / "service_lines.jsonl", LINE_COLUMNS, all_lines
        ),
        "files": pairs * len(CLAIM_TYPES) * 2,
        "denied": sum(1 for c in all_claims if c["denied"]),
        "version": __version__,
        "seed": seed,
        "pairs": pairs,
        "claims_per_pair": claims_per_pair,
    }
    card = pathlib.Path(__file__).with_name("dataset_card.md").read_text()
    (out / "README.md").write_text(card.format(**stats))
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--pairs", type=int, default=50, help="pairs per claim type")
    parser.add_argument("--claims-per-pair", type=int, default=200)
    args = parser.parse_args(argv)
    if args.out.exists() and any(args.out.iterdir()):
        parser.error(f"{args.out} is not empty; give a new or empty directory")
    stats = build(args.out, args.seed, args.pairs, args.claims_per_pair)
    print(
        f"{stats['claims']} claims, {stats['lines']} lines, {stats['files']} X12 files "
        f"({stats['denied']} denied) in {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
