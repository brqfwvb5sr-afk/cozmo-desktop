"""Direct-worker face/sound output and refusal handling with fake transports.

These tests prove message handling and state transitions in the worker and the
real spawn/pipe path. They do not prove that a physical Cozmo shows or plays it.
"""

import asyncio
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest
from PIL import Image

from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.robot.direct import backend as endpoint
from cozmo_desktop.robot.direct.backend import DirectBackend
from cozmo_desktop.robot.direct.transport import PyCozmoTransport
from cozmo_desktop.robot.direct.worker import StaleCommand, WorkerSession
from cozmo_desktop.services import controller as controller_module
from cozmo_desktop.services.controller import RobotController

FACE = Image.new("L", (128, 64), 255).tobytes()


@pytest.fixture
def session():
    driver = Mock(last_state=10.0, hazard=False)
    session = WorkerSession(driver, 10)
    session.surface = "floor"
    session.tick(10)
    return session


def send(session, command, now=10.0, generation=0, **values):
    message = {"command": command, "generation": generation, "expires": now + 0.35, **values}
    try:
        session.command(message, now)
    except RobotError as exc:
        # Mirrors run_worker: every refusal goes through the same policy.
        session.reject(message, exc, now)
        raise


def test_stale_face_or_drive_after_stop_is_discarded_without_disarming(session):
    send(session, "arm")
    send(session, "stop", generation=1)
    for name, values in (("face", {"pixels": FACE}), ("drive", {"left": 20, "right": 20})):
        with pytest.raises(StaleCommand):
            send(session, name, **values)
        assert session.guard.armed, name
    session.driver.drive.assert_not_called()
    session.driver.face.assert_not_called()
    assert session.rejected == "drive: Cancelled command discarded."


def test_refused_face_sound_or_cube_keeps_motors_but_motion_error_locks(session):
    send(session, "arm")
    with pytest.raises(RobotError, match="face frame"):
        send(session, "face", pixels=b"short")
    with pytest.raises(RobotError, match="Expired"):
        send(session, "audio", now=11, data=b"", expires=10)
    session.driver.cube_lights.side_effect = RobotError("Cube not detected.")
    with pytest.raises(RobotError, match="Cube not detected"):
        send(session, "cube", number=1)
    assert session.guard.armed and session.rejected == "cube: Cube not detected."
    session.driver.stop.assert_not_called()
    with pytest.raises(RobotError, match="Invalid"):
        send(session, "drive", left=float("nan"), right=0)
    assert not session.guard.armed
    session.driver.stop.assert_called_once()


def test_sdk_fault_in_face_is_a_refusal_not_a_worker_crash(session):
    session.driver.face.side_effect = ValueError("codec")
    with pytest.raises(RobotError, match="Face frame could not be queued"):
        send(session, "face", pixels=FACE)
    assert session.faces == 0


def test_sound_keeps_head_gesture_but_never_plays_over_moving_wheels(session):
    send(session, "arm")
    send(session, "head", value=20)
    send(session, "audio", data=b"wav")
    session.driver.drive.assert_not_called()
    session.driver.stop.assert_not_called()
    assert not session.driver.stop_all_motors.called
    send(session, "drive", left=20, right=20)
    send(session, "audio", data=b"wav")
    session.driver.drive.assert_called_with(0, 0)
    assert session.guard.wheel_deadline is None and session.guard.armed
    assert session.sounds == 2


def test_output_report_counts_and_ages(session):
    assert session.output(10, None)["face_age"] is None
    send(session, "face", now=10, pixels=FACE, name="Happy")
    send(session, "audio", now=11, data=b"wav")
    report = session.output(12.5, (True, 321))
    assert report["faces"] == 1 and report["sounds"] == 1
    assert report["face_age"] == 2.5 and report["sound_age"] == 1.5
    assert report["stream_running"] is True and report["robot_audio_frames"] == 321
    assert session.expression == "Happy"


def test_real_sdk_stream_status_without_robot():
    pytest.importorskip("pycozmo")
    transport = PyCozmoTransport()
    transport.client.conn.sock.close()
    assert transport.stream_status() == (False, None)
    transport.started = True
    transport.client.anim_controller.enable_animations(True)
    transport.client.anim_controller.thread = Mock(is_alive=Mock(return_value=True))
    transport.client.num_audio_frames_played = 88
    assert transport.stream_status() == (True, 88)


class RecordingTransport:
    """Runs inside the spawned worker; reports counts through the real state pipe."""

    ready = True
    hazard = False

    def __init__(self):
        self.state = RobotState(connected=True, battery=None, backend_name="direct")
        self.frames = 0

    @property
    def last_state(self):
        return time.monotonic()

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass

    def snapshot(self):
        return self.state

    def camera_jpeg(self):
        return None

    def drive(self, left, right):
        self.state = replace(self.state, left_speed=left, right_speed=right)

    def head(self, degrees):
        pass

    def lift(self, ratio):
        pass

    def face(self, pixels):
        assert len(pixels) == 128 * 64

    def audio(self, data):
        assert data.startswith(b"RIFF")
        self.frames += 25

    def cube_lights(self, number, color="green"):
        pass

    def stream_status(self):
        return True, self.frames or None


def recording_worker(pipe):
    from cozmo_desktop.robot.direct import worker

    worker.PyCozmoTransport = RecordingTransport
    worker.run_worker(pipe)


@pytest.fixture
async def direct(monkeypatch):
    monkeypatch.setattr(endpoint, "run_worker", recording_worker)
    monkeypatch.setattr(endpoint, "check_route", lambda: "172.31.1.2")
    monkeypatch.setattr(endpoint.importlib.util, "find_spec", lambda _: True)
    backend = DirectBackend()
    yield backend
    await backend.disconnect()


async def until(predicate, seconds=6.0):
    async with asyncio.timeout(seconds):
        while not predicate():  # noqa: ASYNC110 - observe another process, no local event
            await asyncio.sleep(0.02)


async def test_wake_and_idle_life_faces_and_sounds_reach_the_worker(direct):
    controller = RobotController(direct)
    await direct.connect()
    await controller.wake_up()
    # Wake: two faces and two sounds; idle life then redraws the face at once.
    await until(lambda: direct.output.faces >= 3 and direct.output.sounds >= 2)
    assert controller.ambient_running
    assert direct.output.stream_running is True
    assert direct.output.robot_audio_frames == 50
    assert time.monotonic() - direct.output.last_face < 2
    faces = direct.output.faces
    # First blink is due 3 s after idle life starts: closed + open frame.
    await until(lambda: direct.output.faces >= faces + 2)
    assert not direct.output.rejected
    assert not direct.state.motors_enabled  # Idle life never arms anything.
    await controller.shutdown()


async def test_stale_face_crossing_stop_leaves_real_worker_armed(direct):
    await direct.connect()
    await direct.set_surface("floor")
    await direct.arm_motors()
    await direct.stop()
    generation = direct._generation
    direct._generation = generation - 1  # A face written just before the STOP.
    try:
        with pytest.raises(RobotError, match="Cancelled"):
            await direct.display_face(Image.new("RGB", (128, 64)), "Neutral")
    finally:
        direct._generation = generation
    await until(lambda: "Cancelled" in direct.output.rejected)
    assert direct.state.connected and direct.state.motors_enabled


async def test_idle_life_waits_while_driving_and_resumes_afterwards(direct, monkeypatch):
    monkeypatch.setattr(controller_module, "AMBIENT_RESUME_DELAY", 0.4)
    controller = RobotController(direct)
    await direct.connect()
    await direct.set_surface("floor")
    await direct.arm_motors()
    controller.start_ambient()
    await until(lambda: controller.ambient_running and direct.output.faces >= 1)
    faces, sounds = direct.output.faces, direct.output.sounds
    for _ in range(12):  # About 1.2 s of held keys, like the 100 ms UI refresh.
        controller.submit("drive", lambda: controller.drive(20, 20))
        await asyncio.sleep(0.1)
        assert not controller.ambient_running
    assert (direct.output.faces, direct.output.sounds) == (faces, sounds)
    controller.stop_motion()
    await until(lambda: controller.ambient_running, 3)
    assert direct.state.motors_enabled
    await controller.shutdown()
