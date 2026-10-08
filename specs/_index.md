# nao-viewer

nao-viewer is the MuJoCo window for NAO, one of the three packages of the NAO toolkit (nao-bridge, nao-local, nao-viewer; big picture in `../nao-local/specs/_overview.md`). Its core idea is a kinematic mirror, not a physics simulation: it reads joint angles and the torso pose from any NAOqi endpoint over qi, writes them into the model's `qpos`, runs `mj_kinematics` and renders. It runs in two modes: mirror mode for a real robot or a plain container, and world mode, where nao-local adds a scene and asks it to render the head cameras for injection into `ALVideoDevice`. It also owns the NAO model: a primitive MJCF built from the BSD-3 URDF is committed here. A mesh model is built only on the user's machine, after a license-gated `fetch-meshes`, because Aldebaran's meshes must never enter the repository or a package. nao-viewer depends on libqi alone, never on nao-bridge or nao-local, so the dependency chain stays one-way.

## Specs

<!-- One row per concept spec. Keep the Status column in sync with each spec's `**Status:**` line. -->

| Spec | Description | Status |
|---|---|---|
| [project.md](project.md) | Project structure and tooling: Python version, packaging with uv, layout conventions | Implemented |
| [testing.md](testing.md) | Testing strategy: two-tier `tests/`/`tests-e2e/` split, functional-test philosophy, skip-without-credentials live tier | Implemented |
| _(add concept specs here — see [_spec-template.md](_spec-template.md))_ | | |

Each spec also opens with a YAML **frontmatter** block declaring the `code:` and `tests:` files it governs — the spec → code/tests mapping the spec-drift checks use to scope what they compare. Keep it current when files move, and see [AGENTS.md](../AGENTS.md) ("Spec frontmatter") for the full convention.

### Status legend

- **Not started** — no design decisions made yet
- **Draft** — actively being brainstormed/defined, contains open questions
- **Stable** — design settled, reviewed and validated (open questions are deferrals only), **ready to implement but not necessarily implemented yet**. This is the design-review gate, before code is written.
- **Implemented** — a **Stable** spec that a `Done` plan has built: the code now exists and matches the spec (design and code in sync)
- **Updated** — an **Implemented** spec since edited in a way that needs new code, so the code no longer matches it; a new implementation plan is needed (or in progress) to catch up. Returns to **Implemented** once that plan is `Done`.
