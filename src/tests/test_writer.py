"""
test_writer.py

The writer closes the loop: a file read into models must be writable back out
as a valid interchange. The strongest check is over the whole corpus — parse
every sample, re-emit it, and require that the transaction body survives
unchanged and the result parses again.
"""

import os

import pytest

from x12sdk.io import FUNCTIONAL_IDENTIFIER_CODES, X12ModelReader, write_transactions

from .support import resources_directory


def _sample_files():
    files = []
    for root, _, names in os.walk(resources_directory):
        files.extend(os.path.join(root, name) for name in names)
    return sorted(files)


def _sample_id(path):
    return os.path.relpath(path, resources_directory)


SAMPLE_FILES = _sample_files()


def _read_models(x12: str):
    with X12ModelReader(x12) as reader:
        return list(reader.models())


def _transaction_body(x12: str) -> str:
    """The ST..SE portion, with the interchange and group envelopes stripped."""
    segments = [s for s in x12.replace("\n", "").split("~") if s]
    body = [s for s in segments if s.split("*")[0] not in ("ISA", "GS", "GE", "IEA")]
    return "~".join(body)


@pytest.mark.parametrize("path", SAMPLE_FILES, ids=_sample_id)
def test_every_sample_rewrites_and_reparses(path):
    """Parse -> write -> parse. The transaction body must survive untouched."""
    with open(path) as handle:
        original = handle.read()

    rewritten = write_transactions(
        _read_models(original), sender_id="SENDER", receiver_id="RECEIVER"
    )

    assert _transaction_body(rewritten) == _transaction_body(original)
    # and the output is genuinely readable, not just string-equal
    assert len(_read_models(rewritten)) == len(_read_models(original))


def test_control_numbers_are_internally_consistent():
    """IEA02 must match ISA13 and GE02 must match GS06, with accurate counts."""
    models = _read_models(open(SAMPLE_FILES[0]).read())
    out = write_transactions(
        models,
        sender_id="SND",
        receiver_id="RCV",
        interchange_control_number="42",
        group_control_number="7",
    )
    segments = {
        s.split("*")[0]: s.split("*") for s in out.replace("\n", "").split("~") if s
    }

    assert segments["ISA"][13] == "000000042", "ISA13 is zero-padded to 9"
    assert segments["IEA"][2] == segments["ISA"][13]
    assert segments["GS"][6] == "7"
    assert segments["GE"][2] == segments["GS"][6]
    assert segments["GE"][1] == str(len(models))
    assert segments["IEA"][1] == "1", "one functional group"


@pytest.mark.parametrize(
    "sample_dir,expected_code",
    [
        ("835_005010X221A1", "HP"),
        ("837_005010X222A2", "HC"),
        ("834_005010X220A1", "BE"),
        ("270_005010X279A1", "HS"),
        ("271_005010X279A1", "HB"),
        ("276_005010X212", "HR"),
        ("277_005010X212", "HN"),
    ],
)
def test_functional_identifier_is_derived_from_the_transaction(
    sample_dir, expected_code
):
    """GS01 is not guessable from ST03 (the 835 has none), so it comes from the model."""
    directory = os.path.join(resources_directory, sample_dir)
    path = os.path.join(directory, sorted(os.listdir(directory))[0])
    out = write_transactions(
        _read_models(open(path).read()), sender_id="SND", receiver_id="RCV"
    )
    gs_segment = next(s for s in out.split("\n") if s.startswith("GS*"))
    assert gs_segment.split("*")[1] == expected_code


def test_version_is_derived_from_the_transaction_package():
    """GS08 carries the implementation version the reader dispatches on."""
    path = os.path.join(resources_directory, "835_005010X221A1", "tertiary-payment.835")
    out = write_transactions(
        _read_models(open(path).read()), sender_id="SND", receiver_id="RCV"
    )
    gs_segment = next(s for s in out.split("\n") if s.startswith("GS*"))
    assert gs_segment.split("*")[8].rstrip("~") == "005010X221A1"


def test_unlike_transactions_get_their_own_functional_group():
    """A functional group holds one transaction type, so a mixed list splits."""
    remittance = _read_models(
        open(
            os.path.join(
                resources_directory, "835_005010X221A1", "tertiary-payment.835"
            )
        ).read()
    )
    eligibility = _read_models(
        open(
            os.path.join(
                resources_directory,
                "270_005010X279A1",
                "subscriber-health-benefit-check.270",
            )
        ).read()
    )

    out = write_transactions(
        remittance + eligibility, sender_id="SND", receiver_id="RCV"
    )
    group_headers = [s.split("*")[1] for s in out.split("\n") if s.startswith("GS*")]
    assert group_headers == ["HP", "HS"]
    assert out.count("GE*") == 2
    iea = next(s for s in out.split("\n") if s.startswith("IEA*"))
    assert iea.split("*")[1] == "2", "two functional groups"


def test_interchange_ids_are_padded_and_bounds_checked():
    models = _read_models(open(SAMPLE_FILES[0]).read())
    out = write_transactions(models, sender_id="SHORT", receiver_id="RCV")
    isa = next(s for s in out.split("\n") if s.startswith("ISA*")).split("*")
    assert isa[6] == "SHORT".ljust(15), "ISA06 is fixed width"

    # too long is refused rather than silently truncating an identifier
    with pytest.raises(ValueError, match="sender_id must be 2 to 15"):
        write_transactions(models, sender_id="X" * 16, receiver_id="RCV")

    # too short would otherwise fail deep inside GS validation
    with pytest.raises(ValueError, match="receiver_id must be 2 to 15"):
        write_transactions(models, sender_id="SND", receiver_id="R")


def test_empty_transaction_list_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        write_transactions([], sender_id="SND", receiver_id="RCV")


def test_writes_to_a_path(tmp_path):
    models = _read_models(open(SAMPLE_FILES[0]).read())
    target = tmp_path / "out.x12"
    returned = write_transactions(
        models, sender_id="SND", receiver_id="RCV", path=str(target)
    )
    assert target.read_text() == returned
    assert len(_read_models(target.read_text())) == len(models)


def test_every_supported_transaction_has_a_functional_identifier():
    """Guard: a new transaction set must be added to the lookup or writing fails."""
    directories = {d.split("_")[0] for d in os.listdir(resources_directory)}
    assert directories <= set(FUNCTIONAL_IDENTIFIER_CODES), (
        f"transaction sets with no GS01 mapping: "
        f"{sorted(directories - set(FUNCTIONAL_IDENTIFIER_CODES))}"
    )
