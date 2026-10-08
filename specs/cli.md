---
code:
  - src/nao_viewer/cli.py
  - pyproject.toml
tests:
  - tests/test_cli.py
---

# Command line

**Status:** Draft

## Purpose

A small `nao-viewer` command for one-shot tools that don't fit in application code, plus a convenience command to open a viewer from a terminal. Viewing is done through the Python API ([api.md](api.md)); the CLI is a thin layer on top of the modules.

## Decided

### Commands

| Command | Does | Spec |
|---|---|---|
| `nao-viewer view URL [--mode mirror\|sim] [--scene S] [--ghost] [--variant V]` | Calls `nao_viewer.launch(...)` and waits until the window closes | [api.md](api.md) |
| `nao-viewer check-model URL [--samples N] [--seed N] [--tolerance-mm X] [--tolerance-deg X] [--allow-real]` | Forward-kinematics check | [check_model.md](check_model.md) |
| `nao-viewer fetch-meshes [--installer PATH]` | License prompt and mesh install (interactive) | [meshes.md](meshes.md) |
| `nao-viewer build-model --variant primitive\|meshes` | Regenerate a model | [model.md](model.md), [meshes.md](meshes.md) |

- `URL` is `tcp://host:port` or a bare host (port 9559).
- `-v`/`-q` set the log level; logs go to stderr.
- Exit codes: 0 success, 1 failure (`check-model` over tolerance, a refused or failed fetch), 2 usage error (argparse's own).

### Entry point

`[project.scripts] nao-viewer = "nao_viewer.cli:main"`. `view` goes through the public API, so the `mjpython` handling lives in one place ([api.md](api.md), Viewer process) and the CLI process itself never needs `mjpython`.

### Structure

`cli.py` only parses arguments and calls module functions. Logic belongs to the modules, so they stay testable without a subprocess.

## Open questions

None currently.
