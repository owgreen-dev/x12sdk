"""
5010 837P (005010X222A2) loop 2310D, claim supervising provider: the NM1*DQ
name segment may be followed by REF segments (state license, UPIN,
commercial number, location number), as in the sibling claim-level provider
loops. The reference segment of this loop is validated as a name segment, so
a well-formed REF is rejected for missing NM1 elements.

Inputs are built inline from invented values. The control is the same claim
without the REF.
"""

import pytest

from x12sdk.io import X12ModelReader

ISA = (
    "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     "
    "*260101*1200*^*00501*000000001*0*T*:~"
)
GS = "GS*HC*SENDERID*RECEIVERID*20260101*1200*1*X*005010X222A2~"
HEAD = [
    "ST*837*0001*005010X222A2",
    "BHT*0019*00*0123*20260101*1200*CH",
    "NM1*41*2*EXAMPLE SUBMITTER*****46*SUB001",
    "PER*IC*JANE DOE*TE*5555550100",
    "NM1*40*2*EXAMPLE RECEIVER*****46*REC001",
    "HL*1**20*1",
    "NM1*85*2*EXAMPLE CLINIC*****XX*1234567893",
    "N3*1 MAIN STREET",
    "N4*SPRINGFIELD*PA*17111",
    "REF*EI*123456789",
    "HL*2*1*22*0",
    "SBR*P*18*******CI",
    "NM1*IL*1*DOE*JANE****MI*MEMBER001",
    "N3*2 OAK STREET",
    "N4*SPRINGFIELD*PA*17111",
    "DMG*D8*19700101*F",
    "NM1*PR*2*EXAMPLE PAYER*****PI*PAYER001",
    "CLM*CLAIM001*100***11:B:1*Y*A*Y*Y",
    "HI*ABK:J069",
]
SUPERVISING = "NM1*DQ*1*MOE*MARY****XX*1234567893"
LINE = ["LX*1", "SV1*HC:99213*100*UN*1***1", "DTP*472*D8*20260101"]


def parse_and_round_trip(claim_providers: list):
    segs = HEAD + claim_providers + LINE
    segs.append(f"SE*{len(segs) + 1}*0001")
    text = ISA + GS + "~".join(segs) + "~GE*1*1~IEA*1*000000001~"
    with X12ModelReader(text) as reader:
        models = list(reader.models())
    assert len(models) == 1
    out = models[0].x12(use_new_lines=False).replace("\n", "")
    start = out.index("ST*")
    end = out.index("~", out.index("SE*", start)) + 1
    assert out[start:end].rstrip("~").split("~") == segs
    return models[0]


def claim(model):
    return model.loop_2000a[0].loop_2000b[0].loop_2300[0]


def test_837p_supervising_provider_without_reference_control():
    model = parse_and_round_trip([SUPERVISING])
    assert claim(model).loop_2310d is not None
    assert not claim(model).loop_2310d.ref_segment


@pytest.mark.parametrize("qualifier", ["0B", "1G", "G2", "LU"])
def test_837p_supervising_provider_accepts_a_reference_segment(qualifier):
    model = parse_and_round_trip([SUPERVISING, f"REF*{qualifier}*ID001"])
    refs = claim(model).loop_2310d.ref_segment
    assert [r.reference_identification_qualifier for r in refs] == [qualifier]


def test_837p_supervising_provider_two_reference_segments():
    model = parse_and_round_trip([SUPERVISING, "REF*0B*ID001", "REF*1G*ID002"])
    assert len(claim(model).loop_2310d.ref_segment) == 2
