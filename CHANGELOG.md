# Changelog

All notable changes to x12sdk. The project was forked from
[LinuxForHealth x12](https://github.com/LinuxForHealth/x12) at its final
release, 0.57.0 (June 2022); entries below describe changes made since.

## Unreleased (1.0.0.dev0)

### Changed
- Renamed the package and import namespace from `linuxforhealth.x12` to
  `x12sdk`; the CLI command is now `x12sdk` (was `lfhx12`).
- Moved packaging from `setup.cfg` to `pyproject.toml` (`[project]`);
  fixed the invalid `setuptools>-42` build requirement that broke
  `pip install -e .`.
- Minimum Python is now 3.10 (was 3.8).
- Adopted ruff for linting.

### Removed
- The experimental FastAPI endpoint (`lfhx12-api`, `x12.api`,
  `X12ApiConfig`), its `api` extra, and the Dockerfile / container tooling.
  x12sdk is an SDK and CLI; wrap it in the web framework of your choice.

### Migration from `linuxforhealth-x12`
| before | after |
|---|---|
| `pip install linuxforhealth-x12` | `pip install x12sdk` |
| `from linuxforhealth.x12.io import X12ModelReader` | `from x12sdk.io import X12ModelReader` |
| `lfhx12 -m -p file.x12` | `x12sdk -m -p file.x12` |
| `lfhx12-api` | removed |
