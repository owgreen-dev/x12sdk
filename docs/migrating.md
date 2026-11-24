# Migrating from linuxforhealth-x12

x12sdk is the maintained continuation of
[LinuxForHealth x12](https://github.com/LinuxForHealth/x12), which stopped at
0.57.0 in June 2022. The models and reader API are the same; the package,
imports and commands are renamed, and it runs on Pydantic v2.

| before | after |
|---|---|
| `pip install linuxforhealth-x12` | `pip install x12sdk` |
| `from linuxforhealth.x12.io import X12ModelReader` | `from x12sdk.io import X12ModelReader` |
| `lfhx12 -m -p file.x12` | `x12sdk -m -p file.x12` |
| `lfhx12-api` (FastAPI endpoint) | removed; wrap the SDK in your own service |

Code that reads model fields keeps working. The Pydantic v1 method names
(`.dict()`, `.json()`, `parse_obj`) are deprecated in Pydantic v2; move to
`model_dump()`, `model_dump_json()` and `model_validate`.

The [changelog](https://github.com/owgreen-dev/x12sdk/blob/main/CHANGELOG.md)
lists everything that changed since the fork.
