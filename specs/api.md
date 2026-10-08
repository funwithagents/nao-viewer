---
code:
  - src/nao_viewer/__init__.py
  - src/nao_viewer/client.py
  - src/nao_viewer/protocol.py
  - src/nao_viewer/viewer_process.py
  - src/nao_viewer/scenes/table.xml
tests:
  - tests/test_client.py
  - tests/test_protocol.py
  - tests/test_viewer_process.py
---

# Viewer API

**Status:** Draft

## Purpose

The public interface of nao-viewer: Python functions that open a viewer on a NAO and return a handle to control it. Each viewer runs in its own process. MuJoCo's window, OpenGL and the macOS `mjpython` requirement stay inside that process, so the caller only sees a plain Python object.

## Decided

### Two modes, one argument

The mode is an argument of `launch`, because it changes what the viewer does:

| | `mode="mirror"` | `mode="sim"` |
|---|---|---|
| For | Watching any NAO, typically a real robot | nao-sim's simulated world (or a plain virtual robot) |
| Pose | From NAOqi | From NAOqi |
| Default scene | `"empty"` (floor and light) | `"table"` (objects in front of the robot) |
| `camera_frame` | Refused with `ModeError`. A real robot has its own cameras, served by `ALVideoDevice`. | Renders what the head cameras see in the simulated world |
| Window title | `nao-viewer · mirror · <url>` | `nao-viewer · sim · <url>` |

Both modes run the same [viewer loop](viewer.md) and [pose source](source.md). The mode only sets the defaults above and which requests the viewer process accepts. Sim mode does not refuse a real robot as its target, but the frames would show the simulated scene, not the robot's surroundings.

### Public API (`nao_viewer`)

```python
import nao_viewer

with nao_viewer.launch("tcp://127.0.0.1:9559", mode="sim") as viewer:
    frame = viewer.camera_frame("top", 640, 480)      # RGB numpy image
    print(viewer.status())
    viewer.wait()                                     # until the window is closed
```

```python
def launch(naoqi_url: str, *, mode: Literal["mirror", "sim"] = "mirror",
           scene: str | Path | None = None, variant: str = "auto", ghost: bool = False,
           rate_hz: float = 50, timeout: float = 30.0) -> Viewer

class Viewer:
    mode: Literal["mirror", "sim"]
    def camera_frame(self, camera: Literal["top", "bottom"], width: int, height: int) -> CameraFrame
    def status(self) -> ViewerStatus
    def wait(self, timeout: float | None = None) -> bool    # True once the viewer has exited
    @property
    def running(self) -> bool
    def close(self) -> None                                  # also a context manager

@dataclass(frozen=True)
class CameraFrame:
    image: np.ndarray        # (height, width, 3) uint8 RGB, row 0 = top of the image
    camera: str
    pose_seq: int            # Sample.seq the frame was rendered at (0: no pose yet)
    pose_age: float          # data age of that pose, s

@dataclass(frozen=True)
class ViewerStatus:
    mode: str                # mirror / sim
    target: str              # real / nao-sim / virtual (source.md)
    naoqi_version: str | None
    url: str
    variant: str             # primitive / meshes
    rate: float              # pose updates per second
    pose_seq: int
    data_age: float | None   # s; None before the first sample

class ViewerClosed(Exception): ...   # raised by calls after the viewer has exited
class ModeError(Exception): ...      # the request isn't available in this mode
```

- `scene` is either a bundled scene name (`"empty"`, `"table"`) or a path to a user MJCF file ([model.md](model.md), Scenes). When it is omitted, the mode's default is used.
- `launch` returns once the viewer is up, even if NAOqi is unreachable. The viewer keeps reconnecting ([source.md](source.md)), and `status().data_age` stays `None` until poses arrive. Errors only the viewer process can detect (an unknown scene, `variant="meshes"` without meshes) are reported by the viewer process and raised from `launch`.
- `camera_frame` is checked on the client side first, so mirror mode raises `ModeError` without a round trip; the viewer process refuses it too. In sim mode it blocks until the frame is rendered, which takes about one frame (17 ms) plus render time. Calls from several threads are serialized.
- `nao_viewer/__init__.py` exports only the names above. Importing it loads neither `mujoco` nor `qi`: `client.py` uses the standard library and `numpy` only, so importing nao-viewer costs nao-sim nothing.

### Viewer process (`viewer_process.py`)

Two processes are involved. The **caller's process** is the program that calls `nao_viewer.launch()`, for example nao-sim's host program. It imports only `client.py` and `protocol.py`. The **viewer process** is a separate operating-system process that `launch` starts. It runs `viewer_process.py`, which loads MuJoCo, connects to NAOqi and owns the window. With a viewer open, `ps` shows both.

- `launch` starts `<python> -m nao_viewer.viewer_process <JSON config>` as a subprocess:
  - `<python>` is `mjpython` next to `sys.executable` on macOS, and `sys.executable` elsewhere.
  - If `mjpython` is missing, `launch` raises an error that says why.
- The viewer process loads the world ([model.md](model.md)), builds a `NaoqiSource` ([source.md](source.md)), then runs the [viewer](viewer.md) loop. Every viewer has a window.
- It binds a loopback port and prints `NAO_VIEWER_READY port=<n> protocol=1` as its first stdout line, or `NAO_VIEWER_ERROR <message>` and exits 1. `launch` waits for that line up to `timeout`, then connects and sends `hello`. On a timeout or an early exit, `launch` raises with the tail of the viewer process's stderr.
- **Lifetime is tied to the caller**: the viewer process exits when its control connection closes. That covers `close()`, and the caller's process exiting or crashing, so a viewer window is never orphaned. Closing the window also ends the viewer process; the next call raises `ViewerClosed`, and `wait()` returns.
- A server thread reads requests and queues them. In sim mode, camera renders are served from the render loop through the viewer's `on_frame` hook, because rendering must happen on the thread that owns the OpenGL context. There is one `mujoco.Renderer` per requested resolution, using the model cameras `CameraTop`/`CameraBottom`. In mirror mode no renderer is created, and `camera_frame` is refused with the error `mode`.
- `close()` sends `stop`, waits up to 5 s, then terminates the viewer process.
- **Viewer-process logs reach the caller's logging**: after the ready line, the viewer process logs to stderr, one record per line, with its level in the line. A reader thread in `client.py` drains stderr and passes each line to the `nao_viewer.viewer_process` logger at that level. Lines without a level (a native crash, MuJoCo's own prints) go out at `DEBUG`. A working viewer is quiet in a default log, and a problem inside it shows up in the caller's log without extra setup. The reader also keeps the last 50 lines, which `launch` includes in its error when the viewer process fails to start.

### Protocol (`protocol.py`)

- One TCP connection on `127.0.0.1`. Every message is `u32 header_len | u32 payload_len | header (UTF-8 JSON) | payload (raw bytes)`, with big-endian lengths, the same style as nao-sim's host link.
- Requests are `{"op": ..., "id": n, ...}`. Responses echo `id`, with `"ok": true` and the result fields, or `"ok": false, "error": "..."`.
- Ops in protocol 1:
  - `hello` → `{"protocol": 1, "nao_viewer": version, "mode": mode}`
  - `status` → the `ViewerStatus` fields
  - `camera_frame {camera, width, height}` (sim only) → `{shape, dtype, camera, pose_seq, pose_age}` plus RGB bytes
  - `stop` → `{}`, then the viewer process exits
- Unknown ops are answered with `ok: false` without closing the connection, so a newer client can probe an older viewer process.
- Encoding and decoding are shared by both sides, and they are the only code `client.py` and `viewer_process.py` have in common.

### Bundled scenes

`src/nao_viewer/scenes/` ships with the package:

- `empty.xml` (`"empty"`): floor and light, the mirror default, described in [model.md](model.md);
- `table.xml` (`"table"`): a table with a few objects in front of the robot, the sim default, so the cameras have something to see.

## Open questions

1. **Headless sim (deferred)**: sim mode without a window, serving frames on demand, for nao-sim on a machine without a display. Not needed by nao-viewer's tests (see [testing.md](testing.md)), so it is added only if nao-sim asks for it. On Linux it would need EGL or OSMesa (`MUJOCO_GL=egl`).
2. **Streaming**: pull (one request per frame) is the v1 decision. If nao-sim needs two cameras at 30 fps, per-request latency or the copy cost (0.9 MB per VGA frame over loopback) may matter. Then add a `camera_stream` op that pushes frames at a requested rate, or shared memory for the pixels. To decide with measurements.
3. **Colorspace**: RGB out keeps the viewer generic, and nao-sim converts to the NAO format. If that conversion is costly, `camera_frame` could take a target colorspace.
4. **Further ops**: touch events from clicks on the robot (for `ALTouch`/awareness), and human figures with their positions for nao-sim's perception feed. Each is a new op, with the protocol version raised.
