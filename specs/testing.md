---
code:
  - tests/conftest.py
  - tests-e2e/conftest.py
  - tests-e2e/support.py
tests:
---

# Testing

**Status:** Implemented

## Purpose

nao-viewer's testing strategy — the two-tier structure and what a good test looks like. It's a **cross-cutting practice**, not a runtime concept: nothing here ships in the library. It exists as a spec so the decisions have one honest home that stays in sync with the setup, rather than living half in [project.md](project.md) (the tooling choices) and half in [AGENTS.md](../AGENTS.md) (the operational how-to). The concrete shell commands to run each tier live in [AGENTS.md](../AGENTS.md) "Testing".

## Two tiers, physically separated

Tests split into two directories, and the split is structural — a directory boundary, not a marker or an opt-out flag:

| Tier | Directory | Network | Deterministic | Runs by default |
|---|---|---|---|---|
| Unit / integration | `tests/` | never | yes | **yes** |
| Live / e2e | `tests-e2e/` | a running NAOqi | no | **no** |

- **`tests/` is the normal dev loop.** Fast, deterministic, no real network, no credentials. `pyproject.toml`'s `testpaths = ["tests"]` points the default `uv run pytest` here, so this is what runs on every change and what any contributor or CI can run with zero credentials.
- **`tests-e2e/` is opt-in.** It calls a real external service — network, credentials, non-deterministic output — so it is deliberately *not* collected by the default run. Because `testpaths` already excludes it, no pytest marker or `--run-e2e` flag is needed: the physical separation is the whole mechanism. Run it explicitly (`uv run pytest tests-e2e`).

**What each tier talks to.** `tests/` never talks to Aldebaran software. Code that needs NAOqi is tested against a **mock NAOqi**: Python 3 qi services (`ALMotion` returning scripted angles and transforms, and so on) registered in a standalone `qi.Session` that listens on a loopback port inside the test process. That is still deterministic and offline. `tests-e2e/` talks to a **live NAOqi endpoint** given by URL: a real robot, or a nao-local container someone started separately. The e2e tier never imports nao-local, so testing against the container adds no package dependency and no cycle (nao-local → nao-viewer stays one-way). The dependency is a running process, not an import.

The `tests/` tier mirrors the `src/nao_viewer/` module layout (`test_<module>.py`, plus the `test_project_map.py` drift-guard); `tests-e2e/` is organized around live scenarios rather than modules.

## What a good test asserts

- **Functional, not tautological.** Exercise what a feature actually does — inputs → outputs, state changes, side effects — not that it runs or matches its own signature. A test that would pass against a broken implementation (asserting a constant, that an object isn't `None`, that a mock was called) isn't worth writing.
- **Drive the public API like a real caller.** Prefer exercising the public surface the way a consumer would over reaching into internals; assert on the observable result.
- **In the e2e tier, assert on behavior, not exact output.** Real service responses vary run to run, so a live test asserts a robust property ("a non-empty result came back", "the side effect happened"), never a specific string.

## Test isolation

If the package holds process-global or singleton state, both tiers carry an identical autouse fixture (in each tier's `conftest.py`) that resets it before and after every test, so no state — or background timers/threads — leaks across tests. The fixture is duplicated rather than shared because `tests-e2e/` isn't a package that imports from `tests/`, and it's only a few lines.

## Live tier: skip without an endpoint

A live test needs a NAOqi to talk to, and it must **skip, never fail**, when none is configured. That way anyone without a robot or a container, including CI, can run the tier without breaking it. The endpoint comes from the `NAOQI_URL` environment variable (for example `tcp://127.0.0.1:9559` for nao-local, `tcp://<robot>:9559` for a real NAO). `tests-e2e/support.require_env(NAME)` returns the variable or calls `pytest.skip(...)` when it is unset. Nothing about the endpoint is committed.

## Tooling

- **`pytest`** is the runner; **`ruff`** lints/formats; **`pyright`** (`standard` mode) type-checks. All three are the gate after any change — lint, type check, and tests must pass before work is considered done (see [AGENTS.md](../AGENTS.md), "Verification").
- **`pyright` covers test code too:** its `include` is `src`, `tests`, and `tests-e2e`, so tests are type-checked alongside the library rather than being a blind spot.

## Open questions

1. **CI wiring.** Nothing here sets up continuous integration. The default `tests/` tier is CI-ready (deterministic, no credentials), and the e2e tier is designed to skip cleanly when keys are absent — but actually running either on a hosted runner is unbuilt. Today all testing is a local, manual command.
