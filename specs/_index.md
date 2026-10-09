# nao-viewer

nao-viewer is the MuJoCo window for NAO, one of the three packages of the NAO toolkit (nao-bridge, nao-sim, nao-viewer). Its core idea is a kinematic mirror, not a physics simulation: it reads joint angles and the torso pose from any NAOqi endpoint over qi, writes them into the model's `qpos`, runs `mj_kinematics` and renders. It is a Python library: `nao_viewer.launch(url, scene=...)` starts the viewer in its own process (where MuJoCo's window and `mjpython` live) and returns a handle. The same viewer watches a real robot, or acts as nao-sim's simulated world, where nao-sim passes a scene and pulls head-camera frames to inject into `ALVideoDevice`. nao-viewer also owns the NAO model: one MJCF, converted once from the BSD-3 URDF and committed, ships in the package with styled placeholder visuals of our own. Aldebaran's meshes replace those visuals only on the user's machine, after a license-gated `fetch-meshes`, because they must never enter the repository or a package. nao-viewer depends on libqi alone, never on nao-bridge or nao-sim, so the dependency chain stays one-way.

## Specs

<!-- One row per concept spec. Keep the Status column in sync with each spec's `**Status:**` line. -->

| Spec | Description | Status |
|---|---|---|
| [project.md](project.md) | Project structure and tooling: Python version, packaging with uv, layout conventions | Implemented |
| [testing.md](testing.md) | Testing strategy: two-tier `tests/`/`tests-e2e/` split, in-process mock NAOqi, live tier gated on `NAOQI_URL` | Updated |
| [model.md](model.md) | The NAO MJCF model: committed `nao.xml` from the URDF, joints, couplings, sensors, cameras, effector sites, placeholder visuals; scenes; `NaoPose` and `PoseWriter` | Implemented |
| [meshes.md](meshes.md) | `fetch-meshes` license-gated install and conversion, and loading Aldebaran's meshes in place of the placeholder visuals | Draft |
| [source.md](source.md) | Pose sources: `connect()` with retries, `NaoqiSource` polling NAOqi at 50 Hz with reconnect and target identification | Draft |
| [viewer.md](viewer.md) | The render loop on `mujoco.viewer.launch_passive`: pose → `mj_kinematics` at 60 Hz, status overlay, ghost, attribution | Draft |
| [api.md](api.md) | Public API: `launch(url, mode="mirror"\|"sim")` starts the viewer in its own process (`mjpython` on macOS) and returns a `Viewer` handle (`camera_frame`, `status`, `wait`, `close`); loopback protocol; bundled scenes | Draft |
| [check_model.md](check_model.md) | `check-model`: forward-kinematics cross-check against NAOqi, 2 mm / 1° | Draft |
| [cli.md](cli.md) | Thin `nao-viewer` command: `view`, `check-model`, `fetch-meshes` | Draft |

Each spec also opens with a YAML **frontmatter** block declaring the `code:` and `tests:` files it governs — the spec → code/tests mapping the spec-drift checks use to scope what they compare. Keep it current when files move, and see [AGENTS.md](../AGENTS.md) ("Spec frontmatter") for the full convention.

### Status legend

- **Not started** — no design decisions made yet
- **Draft** — actively being brainstormed/defined, contains open questions
- **Stable** — design settled, reviewed and validated (open questions are deferrals only), **ready to implement but not necessarily implemented yet**. This is the design-review gate, before code is written.
- **Implemented** — a **Stable** spec that a `Done` plan has built: the code now exists and matches the spec (design and code in sync)
- **Updated** — an **Implemented** spec since edited in a way that needs new code, so the code no longer matches it; a new implementation plan is needed (or in progress) to catch up. Returns to **Implemented** once that plan is `Done`.
