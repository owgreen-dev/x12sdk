"""
test_model_writer.py

The writer is write_transactions behind a context manager, so its own contract
is about the lifecycle: what is written when the block exits, what is not
written when it raises, and that the bytes are the ones write_transactions
would have produced.
"""

import datetime
import io
import os

import pytest

from x12sdk.generate import generate_835, generate_837p
from x12sdk.io import X12ModelReader, X12ModelWriter, write_transactions

from .support import resources_directory

ENVELOPE = dict(sender_id="SENDERID", receiver_id="RECEIVERID")
# fixed so the two paths under test cannot differ by the clock
CREATED = datetime.datetime(2026, 1, 1, 12, 0)


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        return list(reader.models())


def _first_sample(directory: str) -> str:
    folder = os.path.join(resources_directory, directory)
    return open(os.path.join(folder, sorted(os.listdir(folder))[0])).read()


@pytest.mark.parametrize(
    "directory",
    sorted(d for d in os.listdir(resources_directory) if "_" in d),
)
def test_reader_to_writer_matches_write_transactions(directory, tmp_path):
    """One sample of every set: the streamed path equals the one-shot path."""
    original = _first_sample(directory)
    target = tmp_path / "out.x12"

    with (
        X12ModelReader(original) as reader,
        X12ModelWriter(str(target), created=CREATED, **ENVELOPE) as writer,
    ):
        for model in reader.models():
            writer.write(model)

    expected = write_transactions(_read(original), created=CREATED, **ENVELOPE)
    assert target.read_text() == expected
    assert writer.interchange == expected
    assert len(_read(target.read_text())) == len(_read(original))


def test_accepts_a_pathlike_destination(tmp_path):
    target = tmp_path / "out.835"
    with X12ModelWriter(target, **ENVELOPE) as writer:
        writer.write_all(_read(generate_835(seed=1, claims=2)))
    assert target.read_text() == writer.interchange


def test_writes_to_an_open_text_stream():
    stream = io.StringIO()
    with X12ModelWriter(stream, created=CREATED, **ENVELOPE) as writer:
        writer.write_all(_read(generate_835(seed=2, claims=1)))
    assert stream.getvalue() == writer.interchange
    assert stream.getvalue().startswith("ISA*")


def test_no_destination_only_builds_the_interchange(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with X12ModelWriter(created=CREATED, **ENVELOPE) as writer:
        assert writer.interchange is None, "nothing is assembled until close"
        writer.write_all(_read(generate_837p(seed=3, claims=2)))
    assert writer.interchange == write_transactions(
        _read(generate_837p(seed=3, claims=2)), created=CREATED, **ENVELOPE
    )
    assert os.listdir(tmp_path) == [], "no file appears without a destination"


def test_nothing_is_written_when_the_block_raises(tmp_path):
    target = tmp_path / "out.835"
    with pytest.raises(RuntimeError, match="upstream failure"):
        with X12ModelWriter(str(target), **ENVELOPE) as writer:
            writer.write_all(_read(generate_835(seed=4, claims=1)))
            raise RuntimeError("upstream failure")
    assert not target.exists()
    assert writer.interchange is None


def test_empty_writer_is_rejected_at_close(tmp_path):
    target = tmp_path / "out.835"
    with pytest.raises(ValueError, match="at least one"):
        with X12ModelWriter(str(target), **ENVELOPE):
            pass
    assert not target.exists()


def test_non_transaction_models_are_rejected_at_the_write_call():
    """The error names the write, not a close that happens somewhere later."""
    remittance = _read(generate_835(seed=5, claims=1))[0]
    with X12ModelWriter(**ENVELOPE) as writer:
        with pytest.raises(ValueError, match="Cannot determine the transaction set"):
            writer.write(remittance.header.st_segment)
        writer.write(remittance)
    assert writer.interchange is not None


def test_usable_without_a_with_block():
    writer = X12ModelWriter(created=CREATED, **ENVELOPE)
    models = _read(generate_835(seed=6, claims=3))
    for model in models:
        writer.write(model)
    assert len(writer) == len(models)
    returned = writer.close()
    assert returned == writer.interchange
    assert returned == write_transactions(models, created=CREATED, **ENVELOPE)


def test_mixed_transactions_share_the_writer_and_split_into_groups():
    with X12ModelWriter(**ENVELOPE) as writer:
        writer.write_all(_read(generate_835(seed=7, claims=1)))
        writer.write_all(_read(generate_837p(seed=7, claims=1)))
    headers = [
        s.split("*")[1] for s in writer.interchange.split("\n") if s.startswith("GS*")
    ]
    assert headers == ["HP", "HC"]
    assert len(writer) == 2


def test_envelope_options_are_passed_through():
    with X12ModelWriter(
        sender_id="SND",
        receiver_id="RCV",
        interchange_control_number="42",
        group_control_number="7",
        usage_indicator="P",
        created=CREATED,
    ) as writer:
        writer.write_all(_read(generate_835(seed=8, claims=1)))
    segments = {
        s.split("*")[0]: s.split("*")
        for s in writer.interchange.replace("\n", "").split("~")
        if s
    }
    assert segments["ISA"][13] == "000000042"
    assert segments["ISA"][15] == "P"
    assert segments["ISA"][9] == "260101"
    assert segments["GS"][6] == "7"
    assert segments["IEA"][2] == "000000042"


def test_interchange_ids_are_bounds_checked_at_close():
    with pytest.raises(ValueError, match="sender_id must be 2 to 15"):
        with X12ModelWriter(sender_id="X" * 16, receiver_id="RCV") as writer:
            writer.write_all(_read(generate_835(seed=9, claims=1)))
