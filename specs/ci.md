---
code:
  - .github/workflows/ci.yml
  - pyproject.toml
tests:
---

# Continuous integration

**Status:** Updated

## Purpose

The verification gate of [AGENTS.md](../AGENTS.md) (lint, type check, tests) runs on GitHub's hosted runners for every pull request and every push to `main`, so each change gets a machine's verdict, not only a local command. CI runs both test tiers ([testing.md](testing.md)) and as much of each as a hosted runner can: the fast tier, with a real headless viewer on the mock NAOqi, and the live tier against a real NAOqi that nao-sim builds on the runner, headless and with windows. Like [testing.md](testing.md), this is a cross-cutting practice, not a runtime concept: nothing here ships in the library, and the one file that implements it is the workflow.

## Decided

### The runner

- **GitHub-hosted runners, the free tier.** The repository is public, so minutes cost nothing, and CI covers every path a runner can run reliably. Every job runs on `ubuntu-24.04`, pinned by name rather than `ubuntu-latest`, so an image only changes when the pin is bumped on purpose. No self-hosted runner.
- **Linux only.** CI is the project's Linux target: the Linux x86_64 `qi` wheel, the EGL default of a headless viewer ([api.md](api.md), "Headless"), a windowed viewer under a virtual display, and Docker running nao-sim's amd64 NAOqi with no emulation.
- **No macOS job.** GitHub's macOS runners (Apple Silicon VMs) can't test the viewer. They have no GPU and so no OpenGL: MuJoCo's CGL backend asks for an accelerated pixel format (`CGLPFAAccelerated`) and fails with `invalid pixel format`, measured on a `macos-15` fast-tier run, and GLFW, MuJoCo's other macOS backend, asks for one too. They have no Docker, so no nao-sim. A macOS fast tier would skip every rendering test and cover only the platform-neutral rest, which Linux already runs. macOS, where nao-viewer is developed, is tested locally (`mjpython`, CGL, the window).
- **One Python**, 3.12: the floor of `requires-python`, and the version `.python-version` names. uv installs it.
- **System packages.** Mesa's EGL (`libegl1 libopengl0 libgl1-mesa-dri`) in the two test jobs, for offscreen rendering with no display and no GPU. The windowed live entry adds a virtual X display and Mesa's GLX (`xvfb xauth libgl1 libglx-mesa0`). Nothing else is installed with apt.

### The workflow

One file, `.github/workflows/ci.yml`. It triggers on `pull_request`, on `push` to `main`, and on `workflow_dispatch`. Concurrency is one run per ref: a newer push cancels the older run still in flight.

| Job | What |
|---|---|
| `check` | `uv sync --locked`, then `ruff check .`, `ruff format --check .`, `pyright`: the static gate |
| `fast-tier` | Mesa's EGL; `pytest -rs`, the fast tier (`tests/` only, from `testpaths`), with `MUJOCO_GL=egl` and `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` |
| `e2e-nao-sim` | Matrix `headless`, `window`, on `ubuntu-24.04`: nao-sim at a pinned commit builds and starts NAOqi 2.1; `pytest tests-e2e -rs` with `NAOQI_URL=tcp://127.0.0.1:9559`, the `window` entry with `NAO_VIEWER_E2E_WINDOW=1` under `xvfb-run` |

The three jobs and the live job's two entries (four runners in all) run side by side, and none waits on another: a run takes as long as its slowest entry (a live one). The live matrix doesn't fail fast, so one entry failing leaves the other running.

- **`--locked`.** The sync fails when `uv.lock` doesn't match `pyproject.toml`, so a dependency edit lands with its relock or not at all.
- **The format check covers the whole repo** (`.`). `specs/` and `plans/` are excluded in `pyproject.toml`, because ruff also formats Python blocks inside Markdown and the specs' blocks are hand-aligned. A local `ruff format .` is therefore the same command, and touches Python files only.
- **uv's cache** is kept by `astral-sh/setup-uv` (`enable-cache`, keyed on the lock files).
- **Timeouts**: `check` 10 minutes, `fast-tier` 15, `e2e-nao-sim` 30 (a cold run downloads about 800 MB and builds two images). A hung test fails its job in minutes, not hours.

### The fast tier in CI

- `MUJOCO_GL=egl` for the whole run. MuJoCo's default on Linux is GLFW, which needs a display, so without this the in-process renderer test would skip. The headless viewer tests get EGL from `launch()` either way.
- `NAO_VIEWER_REQUIRE_OFFSCREEN_GL=1` turns the "no offscreen OpenGL" skips into failures ([testing.md](testing.md), "Testing the viewer process"). A runner that loses its GL packages fails the job instead of passing it on skips.
- **Expected skips: none.**
- **Timing tests ask for rates any runner reaches.** A macOS runner polled the mock NAOqi at 27 Hz at most, so a test that the source follows `rate_hz` uses 5 and 15 Hz, not 50: it checks the behavior, not the machine's speed.

### The live job: a real NAOqi from nao-sim

- **NAOqi 2.1.4.13 (NAO V5)**, the version `check-model` was validated against. 2.8 isn't run in CI (open question 1).
- **nao-sim's own tooling, at a pinned commit.** The job checks out the public [funwithagents/nao-sim](https://github.com/funwithagents/nao-sim) at the commit `NAO_SIM_REF` names in the workflow, then gets nao-sim's NAOqi 2.1 and `tts` images: from the cache below, or else by running `nao-sim fetch-and-build-images 2.1` in nao-sim's own uv project. That command fetches the vendor files, builds the two images, and checks that they boot. The job then starts them with `docker compose --profile 2.1 up -d --wait --no-build`. The pin moves only when it is bumped on purpose, so a nao-sim change can't break nao-viewer's CI without a nao-viewer commit.
- **No import, one-way dependency.** nao-viewer's tests reach nao-sim's NAOqi by URL only. nao-sim's package lives in its own environment and is never installed into nao-viewer's ([testing.md](testing.md)).
- **The images are cached, not Aldebaran's files.** The vendor files (the 2.1 Choregraphe suite, and the `animations` package extracted from the robot image) are fetched only to build nao-sim's images, as on a user's machine. The cache holds the result, not the inputs: the two images, written by `docker save` as one file of about 1.6 GB, in this repository's Actions cache, keyed on `NAO_SIM_REF`.
  - **Hit**: `docker load`, with no fetch, build or nao-sim boot check. `compose up --wait` still waits for NAOqi's healthcheck.
  - **Miss** (a new pin): `fetch-and-build-images`, then `docker save`, then the cache is saved right after the build rather than at the end of the job, so a failing live tier doesn't build again on the next run.
  - **What a pin freezes.** A cached image keeps the base images and the `tts` image's unpinned `pip install` as they were when it was built, until the pin moves. Runs are reproducible, and an upstream change reaches CI only with a bump.
  - **Never pushed.** The images contain Aldebaran's software. They sit in a cache only this repository's workflows restore, and no registry ever receives them.
  - **Measured**: on a miss, `fetch-and-build-images` takes about 2.5 minutes (downloads, build, boot check) and the save 10 s, for a live job of about 3.7 minutes. On a hit, the restore takes 20 s and `docker load` 42 s, for a live job of 2 minutes.
- **Headless and windowed, one entry each.** The live tier opens its viewers as the run says ([testing.md](testing.md), "Live tier: headless or windowed"). The `headless` entry uses the tier's default and needs no display. The `window` entry sets `NAO_VIEWER_E2E_WINDOW=1` and runs under `xvfb-run`, so the windowed loop (`launch_passive`, the overlay) and the mirror test run against a real NAOqi. Each entry has its own runner and its own NAOqi. Both read the same image cache: on a new pin both miss and build, and the second save is refused because the key already exists, which is harmless.
- Viewer warnings and errors print live (`--log-cli-level=WARNING`). When an entry fails, a last step prints the NAOqi containers' logs.
- **Expected skips: one in `headless`**, the mirror test, which needs a window, **and none in `window`**. Any other skip is a regression. Since `NAOQI_URL` is set, a NAOqi that doesn't answer fails the tests; nothing skips for want of an endpoint.

### Secrets and protection

- **No secret is required**, and none is used. nao-sim is public, so pull requests from forks run the same three jobs.
- **The status checks to require on `main`** are every entry: `lint, format, types`, `fast tier`, `live tier, nao-sim NAOqi 2.1, headless` and `live tier, nao-sim NAOqi 2.1, window`. Requiring them is a repository setting on GitHub, outside the repo.

## Open questions

1. **NAOqi 2.8 (NAO V6).** A matrix entry beside 2.1 would catch a model or API difference between V5 and V6, at about twice the download (1.33 GB suite plus a 732 MB robot image) and a second cached image (about 2.4 GB on disk for 2.8, against the 10 GB per repository). Deferred until 2.8 matters to nao-viewer's users.
