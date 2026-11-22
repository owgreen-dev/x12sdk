"""
Times x12sdk on large files, so claims about speed rest on numbers.

    python scripts/benchmark.py              # 1,000 and 10,000 claims
    python scripts/benchmark.py --claims 50000

For each size it generates an 835 and an 837P with that many claims (one
transaction each, the hard case: a transaction is validated as a whole, so it
is held in memory as a whole), then times reading it into validated models and
turning it into one row per service line (which includes reading it), and
separately records peak Python memory during a read.

Numbers depend on the machine; the script prints the Python version and
platform with them. Generation time is not counted.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
import tracemalloc

from x12sdk import __version__
from x12sdk.generate import generate_835, generate_837p
from x12sdk.io import X12ModelReader
from x12sdk.tables import read_lines
from x12sdk.validation import check


def _timed(function):
    start = time.perf_counter()
    result = function()
    return result, time.perf_counter() - start


def _read(x12: str):
    with X12ModelReader(x12) as reader:
        return list(reader.models())


def run(sizes):
    print(
        f"x12sdk {__version__} · Python {platform.python_version()} · "
        f"{platform.system()} {platform.machine()}"
    )
    print()
    print("| File | Claims | Size | Read + validate | Rows (tables) | Peak memory |")
    print("|---|---:|---:|---:|---:|---:|")
    for claims in sizes:
        for name, generate in (("835", generate_835), ("837P", generate_837p)):
            x12 = generate(seed=1, claims=claims)
            size_mb = len(x12.encode()) / 1_000_000

            # timed without the memory tracer, which slows Python down a lot
            _, read_seconds = _timed(lambda: _read(x12))
            tracemalloc.start()
            _read(x12)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            rows, rows_seconds = _timed(lambda: read_lines(x12))
            result, _ = _timed(lambda: check(x12))
            assert result.valid

            print(
                f"| {name} | {claims:,} | {size_mb:.1f} MB | {read_seconds:.1f} s "
                f"({claims / read_seconds:,.0f} claims/s) | {rows_seconds:.1f} s "
                f"for {len(rows):,} rows | {peak / 1_000_000:,.0f} MB |"
            )
            sys.stdout.flush()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--claims", type=int, nargs="+", default=[1_000, 10_000], metavar="N"
    )
    args = parser.parse_args(argv)
    run(args.claims)
    return 0


if __name__ == "__main__":
    sys.exit(main())
