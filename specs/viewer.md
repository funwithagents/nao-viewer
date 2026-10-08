---
code:
  - src/nao_viewer/viewer.py
tests:
  - tests/test_viewer.py
---

# Viewer

**Status:** Draft

## Purpose

The window: it poses the model from a [pose source](source.md) and draws it, with no physics. It runs inside the viewer process ([api.md](api.md)). The mode ([api.md](api.md)) and the scene are parameters; the loop is the same.

## Decided

### Window stack: `mujoco.viewer.launch_passive`

- The built-in passive viewer gives camera controls, rendering options, text overlays and `user_scn` (used for the ghost) for free.
- On macOS, `launch_passive` must run under `mjpython`. [api.md](api.md) starts the viewer process with it, and `viewer.py` assumes it is already there.
- Both side panels start hidden; the standard MuJoCo key toggles them.
- The default camera tracks the `torso` body, so the robot stays in view when it walks. Double-click or the usual MuJoCo keys switch to a free camera.

### Loop

`run(model, source, *, title, ghost=False, attribution=None, on_frame=None)` runs on the main thread until the window closes:

1. `sample = source.latest()`; if its `seq` is new, `PoseWriter.apply` writes it into `data` (which runs `mj_kinematics`).
2. Update the ghost and the overlay.
3. Call `on_frame(model, data)` if given. The viewer process ([api.md](api.md)) uses this hook to serve camera renders and status requests between frames.
4. `handle.sync()`, then sleep to the next 1/60 s tick.

`mj_step` is never called: the pose comes only from the source.

### Status overlay (top-left)

- Lines: target and URL (`nao-sim tcp://127.0.0.1:9559`), NAOqi version, update rate (`source.rate()`, Hz), and data age in ms.
- When the data age passes 500 ms, or before the first sample, the data-age line reads `STALE` (or `NO DATA`). The robot stays in its last pose.
- Shown with `handle.set_texts`. A key (`O`) toggles it.

### Ghost (`ghost=True`)

- Needs a source built with `commanded=True`. A second `MjData` is posed from `sample.commanded` with the same torso pose.
- Its geoms are added to `handle.user_scn` each frame with `mjv_addGeoms`, recolored translucent (alpha 0.3, one flat color) so the gap between commanded and measured angles shows at a glance.

### Attribution overlay (bottom-right)

- Text: `NAO meshes © Aldebaran, CC BY-NC-ND 4.0`.
- On by default whenever the loaded model is the mesh variant; never shown with the primitive model. A key (`A`) toggles it.
- nao-viewer records no video in v1, so there is no recording case to handle.

## Open questions

1. **Colored stale marker**: a red data age would read faster. Whether `set_texts` can color a single line is to be checked at implementation time; the `STALE` text is the decided fallback.
2. **Touch input**: raising touch events for awareness by clicking on the robot (e.g. the head). That's a future [api.md](api.md) op, deferred.
