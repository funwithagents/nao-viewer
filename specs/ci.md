---
code:
  - .github/workflows/ci.yml
  - pyproject.toml
tests:
---

# Continuous integration

**Status:** Implemented

## Purpose

The verification gate of [AGENTS.md](../AGENTS.md) (lint, type check, tests) runs on GitHub's hosted runners for every pull request and every push to `main`, so each change gets a machine's verdict, not only a local command. CI runs both test tiers ([testing.md](testing.md)): the fast tier, with a real headless viewer on the mock NAOqi, and the live tier against a real NAOqi that nao-sim builds on the runner. Like [testing.md](testing.md), this is a cross-cutting practice, not a runtime concept: nothing here ships in the library, and the one file that implements it is the workflow.

## Decided

### The runner

- **GitHub-hosted Linux, the free tier.** Every job runs on `ubuntu-24.04`, pinned by name rather than `ubuntu-latest`, so the image only changes when the pin is bumped on purpose. No self-hosted runner.
- **CI is the project's Linux target.** Development happens on macOS. The runner is where the Linux paths run: the Linux x86_64 `qi` wheel, the EGL default of a headless viewer ([api.md](api.md), "Headless"), and Docker running nao-sim's amd64 NAOqi with no emulation.
- **One Python**, 3.12: the floor of `requires-python`, and the version `.python-version` names. uv installs it.
- **System packages: Mesa's EGL** (`libegl1 libopengl0 libgl1-mesa-dri`) in the two test jobs, for offscreen rendering with no display and no GPU. Nothing else is installed with apt.

### The workflow

One file, `.github/workflows/ci.yml`. It triggers on `pull_request`, on `push` to `main`, and on `workflow_dispatch`. Concurrency is one run per ref: a newer push cancels the older run still in flight.

| Job | What |
|---|---|
| `check` | `uv sync --locked`, then `ruff check .`, `ruff format --check .`, `pyright`: the static gate |
| `fast-tier` | Mesa's EGL; `pytest -rs`, the fast tier (`tests/` only, from `testpaths`), with `MUJOCO_GL=egl` and `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` |
| `e2e-nao-sim` | nao-sim at a pinned commit builds and starts NAOqi 2.1; Mesa's EGL; `pytest tests-e2e -rs` with `NAOQI_URL=tcp://127.0.0.1:9559` |

The three jobs run side by side, each on its own runner, and none waits on another: a run takes as long as its slowest job (the live one).

- **`--locked`.** The sync fails when `uv.lock` doesn't match `pyproject.toml`, so a dependency edit lands with its relock or not at all.
- **The format check covers the whole repo** (`.`). `specs/` and `plans/` are excluded in `pyproject.toml`, because ruff also formats Python blocks inside Markdown and the specs' blocks are hand-aligned. A local `ruff format .` is therefore the same command, and touches Python files only.
- **uv's cache** is kept by `astral-sh/setup-uv` (`enable-cache`, keyed on the lock files).
- **Timeouts**: `check` 10 minutes, `fast-tier` 15, `e2e-nao-sim` 30 (a cold run downloads about 800 MB and builds two images). A hung test fails its job in minutes, not hours.

### The fast tier in CI

- `MUJOCO_GL=egl` for the whole run. MuJoCo's default on Linux is GLFW, which needs a display, so without this the in-process renderer test would skip. The headless viewer tests get EGL from `launch()` either way.
- `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` turns the "no offscreen OpenGL" skips into failures ([testing.md](testing.md), "Testing the viewer process"). A runner that loses its GL packages fails the job instead of passing it on skips.
- **Expected skips: none.**

### The live job: a real NAOqi from nao-sim

- **NAOqi 2.1.4.13 (NAO V5)**, the version `check-model` was validated against. 2.8 isn't run in CI (open question 1).
- **nao-sim's own tooling, at a pinned commit.** The job checks out the public [funwithagents/nao-sim](https://github.com/funwithagents/nao-sim) at the commit `NAO_SIM_REF` names in the workflow, then runs `nao-sim fetch-and-build-images 2.1` in nao-sim's own uv project. That command fetches the vendor files, builds the NAOqi and `tts` images, and checks that they boot. The job then starts them with `docker compose --profile 2.1 up -d --wait --no-build`. The pin moves only when it is bumped on purpose, so a nao-sim change can't break nao-viewer's CI without a nao-viewer commit.
- **No import, one-way dependency.** nao-viewer's tests reach nao-sim's NAOqi by URL only. nao-sim's package lives in its own environment and is never installed into nao-viewer's ([testing.md](testing.md)).
- **Aldebaran's files are cached, the image is never pushed.** The vendor files are the 2.1 Choregraphe suite and the `animations` package, which is extracted from the robot image. They are public on Aldebaran's GitHub. They are kept in this repository's Actions cache between runs, under a key that hashes nao-sim's pins (`src/nao_sim/suite.py`), so new pins fetch new files. The cache is restored before the build and saved right after it, so a failing live tier doesn't fetch again on the next run. The built image stays on the runner: it contains Aldebaran's software, and no registry ever receives it.
- **Headless.** The live tier opens its viewers headless, its default ([testing.md](testing.md), "Live tier: headless or windowed"). Viewer warnings and errors print live (`--log-cli-level=WARNING`). When the job fails, a last step prints the NAOqi containers' logs.
- **Expected skips: one**, the mirror test, which needs a window. Any other skip is a regression. Since `NAOQI_URL` is set, a NAOqi that doesn't answer fails the tests; nothing skips for want of an endpoint.

### Secrets and protection

- **No secret is required**, and none is used. nao-sim is public, so pull requests from forks run the same three jobs.
- **The status checks to require on `main`** are `check`, `fast-tier` and `e2e-nao-sim`. Requiring them is a repository setting on GitHub, outside the repo.

## Open questions

1. **NAOqi 2.8 (NAO V6).** A matrix entry beside 2.1 would catch a model or API difference between V5 and V6, at about twice the download (1.33 GB suite plus a 732 MB robot image) and a larger cache. Deferred until 2.8 matters to nao-viewer's users.
2. **Docker layer caching.** The image build itself isn't cached (only the vendor files are). If the build turns out to dominate the live job, buildx's GitHub cache could hold the layers. They'd contain Aldebaran's software, in a cache only this repository's workflows read, still never a registry. To decide with measured times.
