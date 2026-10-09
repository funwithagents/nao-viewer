# CI: the fast tier on macOS, the live tier windowed

**Status:** In progress

Implements [specs/ci.md](../specs/ci.md) ("The runner", "The workflow", "The live job"): `fast-tier` becomes a matrix over `ubuntu-24.04` and `macos-15`, and `e2e-nao-sim` a matrix over `headless` and `window`, the latter under a virtual X display. It leaves out a windowed viewer on macOS (ci.md open question 2).

## Scope

- `.github/workflows/ci.yml`: the two matrices, Linux-only apt steps, `MUJOCO_GL` and the required-GL switch by OS, the window entry's packages, `NAO_VIEWER_E2E_WINDOW` and `xvfb-run`
- `tests/test_source.py`: the rate test at 5 and 15 Hz instead of 50, which a slow macOS runner can't poll
- `specs/ci.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. `fast-tier`: `strategy.matrix.os: [ubuntu-24.04, macos-15]`, `fail-fast: false`. The apt step runs only on Linux. `MUJOCO_GL` is `egl` on Linux and empty on macOS. `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` is set on Linux only: the first macOS run showed its VM has no OpenGL (`CGLError: invalid pixel format`), so the two GL tests skip there.
2. `e2e-nao-sim`: `strategy.matrix.viewer: [headless, window]`, `fail-fast: false`. The window entry also installs `xvfb xauth libgl1 libglx-mesa0`, sets `NAO_VIEWER_E2E_WINDOW=1`, and runs pytest under `xvfb-run -a -s "-screen 0 1280x1024x24"`.
3. `test_rate_follows_rate_hz`: parametrized at 5 Hz (4 to 6) and 15 Hz (13 to 16). The first macOS run polled 27 Hz at most and failed the old 40-to-55 bound at 50 Hz.
4. Statuses, once a run on GitHub is green with ci.md's expected skips (live headless: the mirror test; macOS fast tier: the two GL tests; the others: none): this plan `Done`, ci.md `Implemented`.

## Verification

- The workflow validates against GitHub's schema.
- In an `ubuntu:24.04` container with only those packages, the live viewer tests pass windowed under `xvfb-run` against a mock NAOqi, the mirror test included (2 passed).
- On GitHub: all five entries green, with the expected skips.
