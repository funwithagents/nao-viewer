---
code:
  - .github/workflows/ci.yml
  - pyproject.toml
tests:
---

# Continuous integration

**Status:** Updated

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
- **nao-sim's own tooling, at a pinned commit.** The job checks out the public [funwithagents/nao-sim](https://github.com/funwithagents/nao-sim) at the commit `NAO_SIM_REF` names in the workflow, then gets nao-sim's NAOqi 2.1 and `tts` images: from the cache below, or else by running `nao-sim fetch-and-build-images 2.1` in nao-sim's own uv project. That command fetches the vendor files, builds the two images, and checks that they boot. The job then starts them with `docker compose --profile 2.1 up -d --wait --no-build`. The pin moves only when it is bumped on purpose, so a nao-sim change can't break nao-viewer's CI without a nao-viewer commit.
- **No import, one-way dependency.** nao-viewer's tests reach nao-sim's NAOqi by URL only. nao-sim's package lives in its own environment and is never installed into nao-viewer's ([testing.md](testing.md)).
- **The images are cached, not Aldebaran's files.** The vendor files (the 2.1 Choregraphe suite, and the `animations` package extracted from the robot image) are fetched only to build nao-sim's images, as on a user's machine. The cache holds the result, not the inputs: the two images, written by `docker save` as one file of about 1.6 GB, in this repository's Actions cache, keyed on `NAO_SIM_REF`.
  - **Hit**: `docker load`, with no fetch, build or nao-sim boot check. `compose up --wait` still waits for NAOqi's healthcheck.
  - **Miss** (a new pin): `fetch-and-build-images`, then `docker save`, then the cache is saved right after the build rather than at the end of the job, so a failing live tier doesn't build again on the next run.
  - **What a pin freezes.** A cached image keeps the base images and the `tts` image's unpinned `pip install` as they were when it was built, until the pin moves. Runs are reproducible, and an upstream change reaches CI only with a bump.
  - **Never pushed.** The images contain Aldebaran's software. They sit in a cache only this repository's workflows restore, and no registry ever receives them.
  - **Measured** on the first run, before this cache: a cold build takes about 2 minutes (downloads about 16 s, build about 80 s, boot check 28 s), of a 3-minute live job.
- **Headless.** The live tier opens its viewers headless, its default ([testing.md](testing.md), "Live tier: headless or windowed"). Viewer warnings and errors print live (`--log-cli-level=WARNING`). When the job fails, a last step prints the NAOqi containers' logs.
- **Expected skips: one**, the mirror test, which needs a window. Any other skip is a regression. Since `NAOQI_URL` is set, a NAOqi that doesn't answer fails the tests; nothing skips for want of an endpoint.

### Secrets and protection

- **No secret is required**, and none is used. nao-sim is public, so pull requests from forks run the same three jobs.
- **The status checks to require on `main`** are `check`, `fast-tier` and `e2e-nao-sim`. Requiring them is a repository setting on GitHub, outside the repo.

## Open questions

1. **NAOqi 2.8 (NAO V6).** A matrix entry beside 2.1 would catch a model or API difference between V5 and V6, at about twice the download (1.33 GB suite plus a 732 MB robot image) and a second cached image (about 2.4 GB on disk for 2.8, against the 10 GB per repository). Deferred until 2.8 matters to nao-viewer's users.
