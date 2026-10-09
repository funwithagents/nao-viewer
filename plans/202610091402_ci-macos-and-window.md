# CI: the fast tier on macOS, the live tier windowed

**Status:** In progress

Implements [specs/ci.md](../specs/ci.md) ("The runner", "The workflow", "The live job"): `fast-tier` becomes a matrix over `ubuntu-24.04` and `macos-15`, and `e2e-nao-sim` a matrix over `headless` and `window`, the latter under a virtual X display. It leaves out a windowed viewer on macOS (ci.md open question 2).

## Scope

- `.github/workflows/ci.yml`: the two matrices, Linux-only apt steps, `MUJOCO_GL` by OS, the window entry's packages, `NAO_VIEWER_E2E_WINDOW` and `xvfb-run`
- `specs/ci.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. `fast-tier`: `strategy.matrix.os: [ubuntu-24.04, macos-15]`, `fail-fast: false`. The apt step runs only on Linux. `MUJOCO_GL` is `egl` on Linux and empty on macOS; `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` on both.
2. `e2e-nao-sim`: `strategy.matrix.viewer: [headless, window]`, `fail-fast: false`. The window entry also installs `xvfb xauth libgl1 libglx-mesa0`, sets `NAO_VIEWER_E2E_WINDOW=1`, and runs pytest under `xvfb-run -a -s "-screen 0 1280x1024x24"`.
3. Statuses, once a run on GitHub is green with ci.md's expected skips (headless: the mirror test; window and both fast tiers: none): this plan `Done`.

## Verification

- The workflow validates against GitHub's schema.
- In an `ubuntu:24.04` container with only those packages, the live viewer tests pass windowed under `xvfb-run` against a mock NAOqi, the mirror test included (2 passed).
- On GitHub: all five entries green, with the expected skips.
