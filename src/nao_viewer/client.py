"""The caller's side: `launch()` starts a viewer process and returns a `Viewer` handle.

Standard library and numpy only: importing nao_viewer loads neither mujoco nor qi.
"""

import json
import logging
import queue
import socket
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Literal, Self

import numpy as np

from nao_viewer import protocol

_process_log = logging.getLogger("nao_viewer.viewer_process")
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_STDERR_TAIL_LINES = 50
_STOP_TIMEOUT = 5.0  # s for the viewer process to exit after `stop`
_KILL_TIMEOUT = 2.0

Mode = Literal["mirror", "sim"]
Camera = Literal["top", "bottom"]
Variant = Literal["auto", "placeholder", "aldebaran"]


class LaunchError(RuntimeError):
    """The viewer process couldn't start (the message includes the tail of its stderr)."""


class ViewerClosed(Exception):
    """The viewer has exited (window closed, `close()`, or a crash)."""


class ModeError(Exception):
    """The request isn't available in this viewer's mode."""


@dataclass(frozen=True)
class CameraFrame:
    image: np.ndarray  # (height, width, 3) uint8 RGB, row 0 = top of the image
    camera: str
    pose_seq: int  # Sample.seq the frame was rendered at (0: no pose yet)
    pose_age: float | None  # data age of that pose, s (None: no pose yet)


@dataclass(frozen=True)
class ViewerStatus:
    mode: str  # mirror / sim
    target: str | None  # real / nao-sim / virtual; None until NAOqi first connects
    naoqi_version: str | None
    url: str
    variant: str  # placeholder / aldebaran
    rate: float  # pose updates per second
    pose_seq: int
    data_age: float | None  # s; None before the first sample


def _viewer_command(config: str) -> list[str]:
    """The command running the viewer process (tests replace it with a fake viewer process)."""
    if sys.platform == "darwin":
        # MuJoCo's window must run on the main thread of an mjpython process on macOS.
        python = Path(sys.executable).with_name("mjpython")
        if not python.exists():
            raise LaunchError(
                f"MuJoCo's window needs mjpython on macOS, and there is none next to {sys.executable}; "
                "it comes with the mujoco package, so install nao-viewer into this Python environment"
            )
    else:
        python = Path(sys.executable)
    return [str(python), "-m", "nao_viewer.viewer_process", config]


class _ProcessOutput:
    """Drains the viewer process's stdout and stderr on threads; relays stderr to logging."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.protocol_line: queue.Queue[str | None] = queue.Queue(maxsize=1)
        self._tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        assert process.stdout is not None and process.stderr is not None
        self._stdout = threading.Thread(
            target=self._read_stdout, args=(process.stdout,), daemon=True
        )
        self._stderr = threading.Thread(
            target=self._read_stderr, args=(process.stderr,), daemon=True
        )
        self._stdout.start()
        self._stderr.start()

    def stderr_tail(self, wait: float = 0.0) -> str:
        """The last stderr lines, after waiting up to `wait` s for the stream to end."""
        self._stderr.join(wait)
        return "\n".join(self._tail)

    def _read_stdout(self, stream: IO[str]) -> None:
        # libqi writes its own log lines to stdout, so the ready (or error) line isn't
        # necessarily the first one: pick it out and relay everything else.
        announced = False
        for raw in stream:
            line = raw.rstrip("\n")
            if not announced and line.startswith(
                (protocol.READY_PREFIX, protocol.ERROR_PREFIX)
            ):
                self.protocol_line.put(line)
                announced = True
            else:
                _process_log.debug("%s", line)
        if not announced:
            self.protocol_line.put(None)  # exited without a word

    def _read_stderr(self, stream: IO[str]) -> None:
        for raw in stream:
            line = raw.rstrip("\n")
            self._tail.append(line)
            level_name, _, message = line.partition(" ")
            level = _LEVELS.get(level_name)
            if level is None:  # MuJoCo's or qi's own prints, a native crash
                _process_log.debug("%s", line)
            else:
                _process_log.log(level, "%s", message)


def _stop_process(process: subprocess.Popen[str], grace: float) -> None:
    try:
        process.wait(grace)
        return
    except subprocess.TimeoutExpired:
        process.terminate()
    try:
        process.wait(_KILL_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _with_stderr(message: str, output: _ProcessOutput) -> str:
    tail = output.stderr_tail(wait=1.0)
    return f"{message}\n--- viewer process stderr ---\n{tail}" if tail else message


def launch(
    naoqi_url: str,
    *,
    mode: Mode = "mirror",
    scene: str | Path | None = None,
    variant: Variant = "auto",
    ghost: bool = False,
    rate_hz: float = 50,
    timeout: float = 30.0,
) -> "Viewer":
    """Open a viewer on the NAOqi at `naoqi_url` in its own process; return once its window is up.

    It returns even if NAOqi is unreachable: the viewer keeps reconnecting. Raises LaunchError if
    the viewer process can't start (unknown scene, missing meshes, no display, timeout).
    """
    if mode not in ("mirror", "sim"):
        raise ValueError(f"unknown mode {mode!r}; expected 'mirror' or 'sim'")
    config = json.dumps(
        {
            "url": naoqi_url,
            "mode": mode,
            "scene": str(scene) if scene is not None else None,
            "variant": variant,
            "ghost": ghost,
            "rate_hz": rate_hz,
            "timeout": timeout,
        }
    )
    process = subprocess.Popen(
        _viewer_command(config),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    output = _ProcessOutput(process)
    try:
        line = output.protocol_line.get(timeout=timeout)
    except queue.Empty:
        _stop_process(process, grace=0)
        raise LaunchError(
            _with_stderr(
                f"the viewer process wasn't ready within {timeout:g} s", output
            )
        ) from None
    if line is None or not line.startswith(protocol.READY_PREFIX):
        _stop_process(process, grace=_KILL_TIMEOUT)
        if line is None:
            message = f"the viewer process exited (code {process.returncode}) before it was ready"
        else:
            message = line.removeprefix(protocol.ERROR_PREFIX).strip()
        raise LaunchError(_with_stderr(message, output))

    fields = dict(field.split("=", 1) for field in line.split()[1:])
    connection = socket.create_connection(
        ("127.0.0.1", int(fields["port"])), timeout=timeout
    )
    connection.settimeout(None)
    viewer = Viewer(mode, process, connection, output)
    try:
        hello, _ = viewer._request("hello")
    except (ViewerClosed, RuntimeError) as exc:
        viewer.close()
        raise LaunchError(
            _with_stderr(f"the viewer process didn't answer hello: {exc}", output)
        ) from exc
    if hello.get("protocol") != protocol.PROTOCOL:
        viewer.close()
        raise LaunchError(
            f"the viewer process speaks protocol {hello.get('protocol')}, not {protocol.PROTOCOL}"
        )
    return viewer


class Viewer:
    """A handle on a running viewer process. Calls from several threads are serialized."""

    def __init__(
        self,
        mode: Mode,
        process: subprocess.Popen[str],
        connection: socket.socket,
        output: _ProcessOutput,
    ) -> None:
        self.mode: Mode = mode
        self._process = process
        self._connection: socket.socket | None = connection
        self._output = output
        self._lock = threading.Lock()
        self._next_id = 0

    def camera_frame(self, camera: Camera, width: int, height: int) -> CameraFrame:
        """Render what a head camera sees in the simulated world (sim mode only)."""
        if self.mode != "sim":
            raise ModeError(
                "camera_frame is only available in sim mode; a real robot's cameras are served by ALVideoDevice"
            )
        if camera not in ("top", "bottom"):
            raise ValueError(f"unknown camera {camera!r}; expected 'top' or 'bottom'")
        header, payload = self._request(
            "camera_frame", camera=camera, width=width, height=height
        )
        image = np.frombuffer(payload, dtype=header["dtype"]).reshape(header["shape"])
        return CameraFrame(
            image, header["camera"], header["pose_seq"], header["pose_age"]
        )

    def status(self) -> ViewerStatus:
        header, _ = self._request("status")
        return ViewerStatus(
            **{name: header[name] for name in ViewerStatus.__dataclass_fields__}
        )

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the viewer to exit (its window closed); True once it has."""
        try:
            self._process.wait(timeout)
        except subprocess.TimeoutExpired:
            return False
        return True

    @property
    def running(self) -> bool:
        return self._process.poll() is None

    def close(self) -> None:
        """Stop the viewer: ask it to exit, then terminate it if it doesn't within 5 s."""
        with self._lock:
            connection, self._connection = self._connection, None
        if connection is not None:
            try:
                protocol.write_message(connection, {"op": "stop", "id": 0})
                protocol.read_message(connection)
            except (OSError, EOFError):
                pass  # already gone
            connection.close()
        _stop_process(self._process, grace=_STOP_TIMEOUT)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _request(self, op: str, **fields: Any) -> tuple[protocol.Header, bytearray]:
        with self._lock:
            if self._connection is None:
                raise ViewerClosed("the viewer is closed")
            self._next_id += 1
            try:
                protocol.write_message(
                    self._connection, {"op": op, "id": self._next_id, **fields}
                )
                header, payload = protocol.read_message(self._connection)
            except (OSError, EOFError) as exc:
                self._connection.close()
                self._connection = None
                raise ViewerClosed("the viewer has exited") from exc
        if not header.get("ok"):
            error = header.get("error")
            if error == "mode":
                raise ModeError(f"{op} isn't available in {self.mode} mode")
            raise RuntimeError(f"the viewer refused {op}: {error}")
        return header, payload
