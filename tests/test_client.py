import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

import nao_viewer
from nao_viewer import client
from nao_viewer.client import LaunchError, ModeError, ViewerClosed

FAKE_VIEWER = Path(__file__).with_name("fake_viewer_process.py")
URL = "tcp://127.0.0.1:9559"


@pytest.fixture(autouse=True)
def fake_viewer_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """launch() runs the fake viewer process instead of the real one."""
    monkeypatch.setattr(
        client,
        "_viewer_command",
        lambda config: [sys.executable, str(FAKE_VIEWER), config],
    )


@pytest.fixture
def ops_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "ops.txt"
    monkeypatch.setenv("NAO_FAKE_VIEWER_OPS", str(path))
    return path


def received_ops(path: Path) -> list[str]:
    return path.read_text().split() if path.exists() else []


def test_launch_handshake_and_status(ops_file: Path):
    with nao_viewer.launch(URL, mode="sim") as viewer:
        assert viewer.mode == "sim"
        assert viewer.running
        status = viewer.status()
        assert status == nao_viewer.ViewerStatus(
            mode="sim",
            target="nao-sim",
            naoqi_version="0.3.0",
            url=URL,
            variant="placeholder",
            rate=50.0,
            pose_seq=12,
            data_age=0.008,
        )
    assert received_ops(ops_file) == ["hello", "status", "stop"]
    assert not viewer.running


def test_camera_frame_returns_the_rendered_image():
    with nao_viewer.launch(URL, mode="sim") as viewer:
        frame = viewer.camera_frame("bottom", 320, 240)
        assert frame.image.shape == (240, 320, 3) and frame.image.dtype == np.uint8
        assert (frame.camera, frame.pose_seq, frame.pose_age) == ("bottom", 12, 0.02)
        # Row 0 is the top of the image, columns run left to right, and it's the bottom camera.
        assert frame.image[5, 7].tolist() == [5, 7, 2]
        assert frame.image[239, 319].tolist() == [239, 319 % 256, 2]
        frame.image[0, 0] = 0  # the caller owns a writable array


def test_camera_frame_in_mirror_mode_raises_without_a_round_trip(ops_file: Path):
    with nao_viewer.launch(URL, mode="mirror") as viewer, pytest.raises(ModeError):
        viewer.camera_frame("top", 640, 480)
    assert "camera_frame" not in received_ops(ops_file)


def test_camera_frame_rejects_an_unknown_camera():
    with (
        nao_viewer.launch(URL, mode="sim") as viewer,
        pytest.raises(ValueError, match="left"),
    ):
        viewer.camera_frame("left", 640, 480)  # type: ignore[arg-type]


def test_launch_error_from_the_viewer_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NAO_FAKE_VIEWER", "error")
    with pytest.raises(LaunchError, match="unknown scene 'nope'") as raised:
        nao_viewer.launch(URL, scene="nope")
    assert "loading the scene" in str(raised.value)  # the stderr tail comes along


def test_launch_error_when_the_viewer_process_exits_early(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("NAO_FAKE_VIEWER", "crash")
    with pytest.raises(LaunchError, match="exited \\(code 3\\)") as raised:
        nao_viewer.launch(URL)
    assert "GLFW could not open a window" in str(raised.value)


def test_launch_times_out_and_stops_the_viewer_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NAO_FAKE_VIEWER", "hang")
    started = time.monotonic()
    processes: list[subprocess.Popen[str]] = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    with pytest.raises(LaunchError, match="wasn't ready within 1 s") as raised:
        nao_viewer.launch(URL, timeout=1.0)
    assert time.monotonic() - started < 5
    assert "never ready" in str(raised.value)
    assert processes[0].poll() is not None  # not left running


def test_protocol_mismatch_is_a_launch_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NAO_FAKE_VIEWER_PROTOCOL", "2")
    with pytest.raises(LaunchError, match="protocol 2"):
        nao_viewer.launch(URL)


def test_calls_after_the_viewer_exits_raise_viewer_closed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "NAO_FAKE_VIEWER", "close-after-2"
    )  # hello, status, then the window closes
    viewer = nao_viewer.launch(URL, mode="sim")
    viewer.status()
    assert viewer.wait(timeout=5)
    assert not viewer.running
    with pytest.raises(ViewerClosed):
        viewer.status()
    with pytest.raises(ViewerClosed):
        viewer.camera_frame("top", 64, 48)
    viewer.close()  # harmless once gone


def test_wait_times_out_while_the_viewer_runs():
    with nao_viewer.launch(URL) as viewer:
        assert viewer.wait(timeout=0.1) is False


def test_calls_after_close_raise_viewer_closed():
    viewer = nao_viewer.launch(URL)
    viewer.close()
    assert not viewer.running
    with pytest.raises(ViewerClosed):
        viewer.status()


def test_viewer_process_logs_reach_the_callers_logging(
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.DEBUG, logger="nao_viewer.viewer_process"):
        with nao_viewer.launch(URL) as viewer:
            viewer.status()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not any(
            "native log line" in r.getMessage() for r in caplog.records
        ):
            time.sleep(0.01)
    records = {
        r.getMessage(): r.levelno
        for r in caplog.records
        if r.name == "nao_viewer.viewer_process"
    }
    assert records["nao_viewer.source: connected to the fake NAOqi"] == logging.INFO
    assert (
        records["nao_viewer.viewer: a warning from the viewer process"]
        == logging.WARNING
    )
    native = [message for message in records if "native log line" in message]
    assert native and records[native[0]] == logging.DEBUG
    qi_stdout = [message for message in records if "qi.path.sdklayout" in message]
    assert (
        qi_stdout and records[qi_stdout[0]] == logging.DEBUG
    )  # stdout chatter before the ready line


def test_concurrent_calls_get_their_own_answers():
    with nao_viewer.launch(URL, mode="sim") as viewer:
        sizes = [(32 + i, 24 + i) for i in range(8)]
        results: dict[int, tuple[int, ...]] = {}

        def fetch(i: int) -> None:
            width, height = sizes[i]
            shapes = {
                viewer.camera_frame("top", width, height).image.shape for _ in range(5)
            }
            results[i] = shapes.pop() if len(shapes) == 1 else (0,)

        threads = [threading.Thread(target=fetch, args=(i,)) for i in range(len(sizes))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert results == {i: (h, w, 3) for i, (w, h) in enumerate(sizes)}


def test_missing_mjpython_on_macos_is_a_launch_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.undo()  # the real command, not the fake viewer process
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    with pytest.raises(LaunchError, match="mjpython"):
        nao_viewer.launch(URL)


def test_importing_nao_viewer_loads_neither_mujoco_nor_qi():
    code = "import sys, nao_viewer; print(sorted(m for m in ('mujoco', 'qi') if m in sys.modules))"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
