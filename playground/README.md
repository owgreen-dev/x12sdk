---
title: x12sdk playground
emoji: 🧾
colorFrom: blue
colorTo: green
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Check and generate X12 835/837 files in your browser
datasets:
  - owgreen-dev/x12sdk
tags:
  - healthcare
  - x12
  - edi
  - hipaa
  - claims
  - synthetic-data
  - pyodide
---

# x12sdk playground

Check, tabulate, generate and match HIPAA X12 health care files in the
browser: claims (837P/I/D), remittances (835), eligibility (270/271), claim
status (276/277) and enrollment (834).

- **Check a file:** paste or drop an X12 file and see whether it is valid,
  and if not, where it breaks, in plain words.
- **Get a table:** a valid 835 or 837 becomes one row per service line,
  downloadable as CSV.
- **Generate samples:** synthetic files with no PHI, reproducible from a seed,
  including an 837 with the 835 that pays it.
- **Match claims to payments:** join an 837 to an 835 on the patient control
  number and see what was paid, denied or never answered.

It runs [x12sdk](https://github.com/owgreen-dev/x12sdk) in
[Pyodide](https://pyodide.org) (Python compiled to WebAssembly), so the
files you open are processed inside your browser tab and never uploaded. The
page downloads Python and x12sdk on first visit; that is the only network
traffic.

The same library, from Python: `pip install x12sdk`. The 30,000-claim
dataset made with it is [owgreen-dev/x12sdk](https://huggingface.co/datasets/owgreen-dev/x12sdk).

This Space is built from the [`playground/`](https://github.com/owgreen-dev/x12sdk/tree/main/playground)
folder of the x12sdk repository. Not affiliated with X12 or any payer.
