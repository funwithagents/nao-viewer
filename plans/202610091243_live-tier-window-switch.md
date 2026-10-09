# Live tier: headless or windowed by environment

**Status:** Done

Implements [specs/testing.md](../specs/testing.md) ("Live tier: headless or windowed"): one environment variable, `NAO_VIEWER_E2E_WINDOW`, decides whether a live run opens its viewers headless (the default) or with their windows, replacing the per-test parametrization and the display check. It leaves the live tier's target as it is: a real NAOqi given by `NAOQI_URL`.

## Scope

- `tests-e2e/support.py`: `window_requested()` and `require_window()` replace `require_display()`
- `tests-e2e/test_viewer_live.py`: the sim test opens a headless or windowed viewer as the run says; the mirror test requires a window
- `AGENTS.md`: the variable in "Live/e2e tests"
- `specs/testing.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. `window_requested()`: `NAO_VIEWER_E2E_WINDOW`, stripped and lowercased, in `{"1", "true", "yes", "on"}`. `require_window()`: `pytest.skip` naming the variable when it is not requested.
2. The sim test drops its `headless` parameter and builds its config with `"headless": not window_requested()`. The mirror test calls `require_window()` after `require_env`.
3. Statuses: plan `Done`, testing.md `Implemented`.

## Verification

- Lint, type check and the fast tier pass.
- The live tier, run against a mock NAOqi started by hand on a loopback port (a check of the harness, not a substitute for a real NAOqi): headless by default, sim passing and mirror skipped; with `NAO_VIEWER_E2E_WINDOW=1`, both passing with windows.
