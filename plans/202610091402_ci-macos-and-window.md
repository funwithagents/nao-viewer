# CI: the live tier windowed, and no macOS job

**Status:** In progress

Implements [specs/ci.md](../specs/ci.md) ("The runner", "The workflow", "The live job"): `e2e-nao-sim` becomes a matrix over `headless` and `window`, the latter under a virtual X display. A macOS fast tier was tried and removed: its runners have no OpenGL, so it could not test the viewer.

## Scope

- `.github/workflows/ci.yml`: the live matrix, the window entry's packages, `NAO_VIEWER_E2E_WINDOW` and `xvfb-run`
- `tests/test_source.py`: the rate test at 5 and 15 Hz instead of 50, which the macOS runner couldn't poll; kept, since it now tests the behavior rather than the machine's speed
- `specs/ci.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. `e2e-nao-sim`: `strategy.matrix.viewer: [headless, window]`, `fail-fast: false`. The window entry also installs `xvfb xauth libgl1 libglx-mesa0`, sets `NAO_VIEWER_E2E_WINDOW=1`, and runs pytest under `xvfb-run -a -s "-screen 0 1280x1024x24"`.
2. A `macos-15` fast-tier entry, tried on [run 37927534189](https://github.com/funwithagents/nao-viewer/actions/runs/37927534189) and [run 37928068757](https://github.com/funwithagents/nao-viewer/actions/runs/37928068757). Its VM has no OpenGL (`CGLError: invalid pixel format`), so both GL tests skipped, and what remained is platform-neutral code Linux already runs. Removed; ci.md records why.
3. `test_rate_follows_rate_hz`: parametrized at 5 Hz (4 to 6) and 15 Hz (13 to 16). The macOS runner polled 27 Hz at most and failed the old 40-to-55 bound at 50 Hz.
4. Statuses, once a run on GitHub is green with ci.md's expected skips (live headless: the mirror test; the others: none): this plan `Done`, ci.md `Implemented`.

## Verification

- The workflow validates against GitHub's schema.
- In an `ubuntu:24.04` container with only those packages, the live viewer tests pass windowed under `xvfb-run` against a mock NAOqi, the mirror test included (2 passed).
- On GitHub: the four entries green, with the expected skips.
