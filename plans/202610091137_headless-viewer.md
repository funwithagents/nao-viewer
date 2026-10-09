# Headless viewer

**Status:** Done

Implements the `headless` config field ([specs/config.md](../specs/config.md)), headless sim with offscreen rendering ([specs/api.md](../specs/api.md), "Headless"), the headless loop ([specs/viewer.md](../specs/viewer.md), "Headless loop") and its tests ([specs/testing.md](../specs/testing.md)). With it, a viewer's caller can run sim mode on a generic Linux image with no display. It leaves out streaming and any change to the protocol: a headless viewer answers the same ops.

## Scope

- `src/nao_viewer/config.py`: `headless: bool = False` on `NaoViewerConfig`, its reader, and the two combination checks (`mirror`, `ghost`)
- `src/nao_viewer/client.py`: `_viewer_command` takes the config and uses `sys.executable` when headless; new `_viewer_env(config)` sets `MUJOCO_GL=egl` for a headless viewer on Linux when unset; `launch()` passes it to `Popen`
- `src/nao_viewer/viewer.py`: `run_headless`; `import mujoco.viewer` moves inside `run`
- `src/nao_viewer/viewer_process.py`: headless branch in `main`: render-check before the ready line, then `run_headless`
- `examples/configs/*.json`: `headless` written out in both files; new `sim-headless.json`
- `tests/test_config.py`: the field, its type check, the combinations, the new example
- `tests/test_client.py`: command and environment for a headless viewer (fixture adapted to the new `_viewer_command` signature)
- `tests/test_viewer.py`: `run_headless` poses the model, calls `on_frame`, stops on `stop`
- `tests/test_viewer_process.py`: a real headless viewer process on the mock NAOqi (skipped without offscreen GL)
- `tests-e2e/support.py`: `require_display()`
- `tests-e2e/test_viewer_live.py`: the sim frames test runs headless and windowed; windowed tests require a display
- `specs/*.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. **Config**: add `headless` after `mode` (so `to_dict` writes it there) and read it with `_as_bool`. In `__post_init__`, `headless and mode == "mirror"` is a `ConfigError` on `headless`, and `headless and ghost` is one on `ghost`. Write `"headless": false` into both examples and add `sim-headless.json` (`sim-table.json` with `headless: true`).
2. **Client**:
   - `_viewer_command(config: NaoViewerConfig)`: when `config.headless`, it uses `sys.executable` and skips the `mjpython` lookup. The JSON argument is built inside.
   - `_viewer_env(config) -> dict[str, str] | None`: `None` (inherit the environment) unless the viewer is headless, `sys.platform` is Linux and `MUJOCO_GL` is unset. In that case it returns a copy of `os.environ` with `MUJOCO_GL=egl`.
3. **Viewer**: `run_headless(model, source, *, on_frame=None, stop=None)` builds a `ViewerState` and loops `update` → `on_frame` → tick until `stop` is set. It shares the tick code with `run`. Move `import mujoco.viewer` into `run`.
4. **Viewer process**: in `main`, when headless:
   - build the `OffscreenRenderer` and render `CameraTop` at 640×480 from a fresh `MjData` before starting the loop;
   - on any exception, `fail(...)` with the `MUJOCO_GL` value in use and the fix ("install Mesa's EGL (libegl1 libopengl0 libgl1-mesa-dri), or set MUJOCO_GL=osmesa"). The exception text is read defensively, because PyOpenGL errors can fail `str()`;
   - then call `run_headless`, with the same `server.on_frame`/`stop` wiring and cleanup as the windowed path.
5. **Fast tests**: config, command, environment and `run_headless` as listed in Scope. For the real headless process:
   - a module fixture probes offscreen rendering in a subprocess, with the environment `_viewer_env` gives, and skips when the probe fails;
   - a headless sim `NaoViewer` on `mock_naoqi`: wait for `pose_seq > 0`, fetch frames from both cameras, check they aren't blank, turn `HeadYaw` with `set_pose`, and check the bottom frame changes;
   - a headless viewer exits when its caller's connection closes (`close()`), and `wait()` returns.
6. **Live tests**: add `require_display()` (skips on Linux with neither `DISPLAY` nor `WAYLAND_DISPLAY`), parametrize the sim frames test over `headless`, and make the windowed cases require a display.
7. **Statuses**: once verified, mark this plan `Done` and config, api, viewer and testing `Implemented`.

## Verification

- `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`, `uv run pytest`: all pass. On macOS the real headless test runs, it does not skip.
- In `ubuntu:24.04` and `python:3.12-slim` linux/amd64 containers with only `libegl1 libopengl0 libgl1-mesa-dri` installed, the whole fast tier passes, headless test included; without them, the headless test skips.
