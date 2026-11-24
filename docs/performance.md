# Performance

Files are read one transaction at a time; a transaction is validated as a
whole, so it is held in memory as a whole. From `python scripts/benchmark.py`
on an Apple-silicon Mac, Python 3.12, one transaction per file:

| File | Claims | Size | Read and validate | Peak memory |
|---|---:|---:|---:|---:|
| 835 | 10,000 | 1.6 MB | 1.2 s (about 8,200 claims/s) | 203 MB |
| 837P | 10,000 | 4.4 MB | 4.7 s (about 2,100 claims/s) | 536 MB |

Memory grows with the size of the largest transaction, not of the file; a
file of many moderate transactions streams in roughly constant memory.

The numbers depend on the machine. To measure your own:

```shell
python scripts/benchmark.py                 # 1,000 and 10,000 claims
python scripts/benchmark.py --claims 50000
```

The script generates the files itself, so it needs no data, and prints the
Python version and platform with its results.
