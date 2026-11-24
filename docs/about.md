# About

## Project

- Source, issues and contributions: [github.com/owgreen-dev/x12sdk](https://github.com/owgreen-dev/x12sdk)
- Releases: [PyPI](https://pypi.org/project/x12sdk/) and the
  [changelog](https://github.com/owgreen-dev/x12sdk/blob/main/CHANGELOG.md)
- Plans: the [roadmap](https://github.com/owgreen-dev/x12sdk/blob/main/ROADMAP.md)
- Contributing: [CONTRIBUTING.md](https://github.com/owgreen-dev/x12sdk/blob/main/CONTRIBUTING.md)
  (Apache-2.0, DCO sign-off, no copyrighted standards text, no real PHI)

## Provenance

x12sdk is a fork of **[LinuxForHealth x12](https://github.com/LinuxForHealth/x12)**
by Dixon Whitmire and the LinuxForHealth contributors (IBM), released under
the Apache License 2.0. The models, parser, readers, and test corpus
originate there; x12sdk exists to keep that work usable on current Python
and Pydantic. The original licence is retained, and attribution and
trademark notes are in
[NOTICE](https://github.com/owgreen-dev/x12sdk/blob/main/NOTICE) and
[TRADEMARK.md](https://github.com/owgreen-dev/x12sdk/blob/main/TRADEMARK.md).
x12sdk is not affiliated with or endorsed by IBM, LinuxForHealth, the Linux
Foundation, X12 or any payer.

## Related work

- **[MdClarity/x12](https://github.com/MdClarity/x12)**: an independent
  fork by MD Clarity that completed a Pydantic v2 migration and added type
  checking and fuzzing in 2026.
- **[pyx12](https://github.com/azoner/pyx12)**: the long-standing Python X12
  validator and converter (XML or dict output, map-driven). Choose pyx12 for
  validation against X12 maps; choose x12sdk for typed Python models.
- **[edi-835-parser](https://github.com/keiron-stoddart/edi-835-parser)**: a
  popular 835-only parser with pandas output.

## Licence

Apache License 2.0.
