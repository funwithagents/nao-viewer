# Implementation plans

Implementation plans for nao-viewer — each plan turns a settled part of a spec (see [specs/_index.md](../specs/_index.md)) into concrete, buildable steps. Plans are ordered by their date-time filename prefix (`YYYYMMDDHHmm_`).

## Plans

<!-- One row per plan, chronological by filename prefix. Keep the Status column in sync with each plan's `**Status:**` line. -->

| Plan | Description | Status |
|---|---|---|
| [202610090930_nao-model.md](202610090930_nao-model.md) | Vendored URDF, committed `nao.xml` with placeholder visuals, `empty` scene, `model.py` (implements [model.md](../specs/model.md)) | Done |
| [202610090954_pose-source.md](202610090954_pose-source.md) | `connect`, `NaoqiSource` with reconnection and target identification, and the in-process mock NAOqi (implements [source.md](../specs/source.md), [testing.md](../specs/testing.md)) | Done |
| [202610091003_viewer-window.md](202610091003_viewer-window.md) | `ViewerState` (overlay, ghost, attribution, keys) and `run` on MuJoCo's passive viewer; window title via `load_world(name=...)` (implements [viewer.md](../specs/viewer.md)) | Done |

## Status legend

- **Todo** — written, not yet started
- **In progress** — actively being implemented
- **Done** — implemented, verified (lint/type-check/tests pass), and merged
