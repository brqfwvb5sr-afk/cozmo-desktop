"""Physical adapter contracts with real PyCozmo codecs, never a robot socket send."""

import asyncio
import io
import math
import shutil
import wave
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from cozmo_desktop.robot.base import CubeEvent, RobotError, RobotState
from cozmo_desktop.robot.direct import backend as endpoint
from cozmo_desktop.robot.direct.backend import DirectBackend, synthesize, synthesize_vocalization
from cozmo_desktop.robot.direct.transport import PyCozmoTransport
from cozmo_desktop.robot.direct.worker import WorkerSession


@pytest.fixture
def session():
    driver = Mock(last_state=10.0, hazard=False)
    session = WorkerSession(driver, 10)
    session.surface = "floor"
    session.tick(10)
    return session


def command(session, name, now=10.0, **values):
    session.command({"command": name, "generation": 0, "expires": now + 0.35, **values}, now)


def test_motion_requires_explicit_arming_and_is_clamped(session):
    with pytest.raises(RobotError, match="locked"):
        command(session, "drive", left=100, right=-100)
    session.driver.drive.assert_not_called()
    command(session, "arm")
    command(session, "drive", left=100, right=-100)
    session.driver.drive.assert_called_once_with(40, -40)
    command(session, "head", value=100)
    session.driver.head.assert_called_once_with(44.5)
    command(session, "lift", value=-1)
    session.driver.lift.assert_called_once_with(0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "40", None])
def test_invalid_motor_values_never_reach_transport(session, value):
    command(session, "arm")
    with pytest.raises(RobotError, match="Invalid"):
        command(session, "drive", left=value, right=0)
    session.driver.drive.assert_not_called()


@pytest.mark.parametrize("fault", ["lease", "gui", "telemetry", "hazard"])
def test_worker_stops_and_locks_without_gui_timer(session, fault):
    command(session, "arm")
    command(session, "drive", left=20, right=20)
    now = 10.4 if fault == "lease" else 10.9
    if fault != "gui":
        command(session, "heartbeat", now)
    if fault != "telemetry":
        session.driver.last_state = now
    if fault == "hazard":
        session.driver.hazard = True
    session.tick(now)
    assert not session.guard.armed
    session.driver.stop.assert_called_once()
    assert session.closing == (fault in ("gui", "telemetry"))
    with pytest.raises(RobotError):
        command(session, "drive", now, left=20, right=20)


def test_stop_discards_inflight_motor_commands_but_tolerates_old_heartbeat(session):
    command(session, "arm")
    command(session, "stop", generation=1, expires=-1)
    with pytest.raises(RobotError, match="Cancelled"):
        command(session, "drive", left=20, right=20)
    command(session, "heartbeat")
    assert session.generation == 1
    session.driver.drive.assert_not_called()


def test_expired_commands_and_hazardous_arming_rejected(session):
    with pytest.raises(RobotError, match="Expired"):
        command(session, "arm", expires=9)
    session.guard.hazard = True
    with pytest.raises(RobotError, match="Cannot enable"):
        command(session, "arm")


def test_table_and_unknown_surface_reject_motor_commands(session):
    command(session, "surface", mode="table")
    assert session.surface == "table" and not session.guard.armed
    with pytest.raises(RobotError, match="clear-floor"):
        command(session, "arm")
    with pytest.raises(RobotError, match="locked"):
        command(session, "drive", left=10, right=10)
    command(session, "surface", mode="floor")
    command(session, "arm")
    assert session.guard.armed
    command(session, "surface", mode="unknown")
    assert not session.guard.armed


@pytest.fixture
def transport():
    pytest.importorskip("pycozmo")
    driver = PyCozmoTransport()
    # Construction opens an unconnected UDP socket; replace it before any commands.
    driver.client.conn.sock.close()
    driver.client.conn = Mock()
    yield driver


def test_real_sdk_encodes_drive_pose_face_audio_and_stop(transport):
    transport.drive(20, -20)
    transport.head(25)
    transport.lift(0.5)
    packets = [call.args[0] for call in transport.client.conn.send.call_args_list]
    assert [type(p).__name__ for p in packets] == ["DriveWheels", "SetHeadAngle", "SetLiftHeight"]
    assert packets[0].lwheel_speed_mmps == 20 and packets[0].rwheel_speed_mmps == -20
    assert packets[1].angle_rad == pytest.approx(math.radians(25))
    assert packets[2].height_mm == 62
    for packet in packets:
        assert packet.to_bytes()
    transport.face(Image.new("L", (128, 64), 255).tobytes())
    audio, face, motion = transport.client.anim_controller.queue.get()
    assert audio is None and motion is None
    assert type(face).__name__ == "DisplayImage" and face.to_bytes()
    data = io.BytesIO()
    with wave.open(data, "wb") as stream:
        stream.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 1500)
    transport.audio(data.getvalue())
    volume = transport.client.conn.send.call_args.args[0]
    assert type(volume).__name__ == "SetRobotVolume" and volume.level == 30000
    assert volume.to_bytes()
    audio, _, _ = transport.client.anim_controller.queue.get()
    assert len(audio.samples) == 744 and audio.to_bytes()
    transport.started = True
    transport.stop()
    assert transport.client.anim_controller.queue.is_empty()
    assert type(transport.client.conn.send.call_args.args[0]).__name__ == "StopAllMotors"


def test_real_sdk_telemetry_has_no_simulated_battery_or_camera(transport):
    cli = transport.client
    transport.ready = True
    cli.battery_voltage = 3.91
    cli.head_angle = transport.api.util.Angle(degrees=12)
    cli.robot_status = transport.api.robot.RobotStatusFlag.IS_PICKED_UP
    cli.connected_objects[7] = {"object_type": 2, "factory_id": 42}
    transport._on_tap(cli, SimpleNamespace(object_id=7))
    transport._on_tap(cli, SimpleNamespace(object_id=7))
    transport._on_move(cli, SimpleNamespace(object_id=7))
    transport._on_raw_state(
        cli,
        transport.api.protocol_encoder.RobotState(cliff_data_raw=(3, 4, 5, 6)),
    )
    transport._on_state(cli)
    state = transport.snapshot()
    assert state.connected and state.battery is None and state.battery_voltage == 3.91
    assert state.head_angle == pytest.approx(12) and transport.hazard
    assert not state.face_detected and not state.camera_available
    assert state.cubes[1].connected and state.cubes[1].tapped
    assert state.cubes[1].tap_sequence == 2 and state.cubes[1].move_sequence == 1
    assert state.cube_events == (
        CubeEvent(1, 2, "tap"),
        CubeEvent(2, 2, "tap"),
        CubeEvent(3, 2, "move"),
    )
    assert state.cliff_raw == (3, 4, 5, 6) and state.picked_up
    transport._on_camera(cli, Image.new("L", (320, 240)))
    transport._on_state(cli)
    assert transport.snapshot().camera_available
    assert Image.open(io.BytesIO(transport.camera_jpeg())).size == (320, 240)


def test_real_cube_connect_and_lights_packets(transport):
    cli = transport.client
    cli.available_objects[42] = SimpleNamespace(
        object_type=transport.api.protocol_encoder.ObjectType.Block_LIGHTCUBE1
    )
    transport.cube_lights(1)
    packet = cli.conn.send.call_args.args[0]
    assert type(packet).__name__ == "ObjectConnect" and packet.factory_id == 42
    assert packet.to_bytes()
    cli.connected_objects[7] = {"object_type": 1, "factory_id": 42}
    transport.cube_lights(1)
    packets = [c.args[0] for c in cli.conn.send.call_args_list[-2:]]
    assert [type(p).__name__ for p in packets] == ["CubeId", "CubeLights"]
    assert all(p.to_bytes() for p in packets)
    transport.cube_lights(1, "red")
    assert transport._cube_colors[1] == "red"
    assert transport.client.conn.send.call_args.args[0].to_bytes()


def test_original_vocalization_is_small_pcm_and_real_sdk_audio(transport):
    for kind in ("chirp", "grumble"):
        data = synthesize_vocalization(kind)
        assert len(data) < 25_000
        with wave.open(io.BytesIO(data)) as stream:
            assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (
                22050,
                1,
                2,
            )
        transport.audio(data)
        packet, _, _ = transport.client.anim_controller.queue.get()
        assert packet.to_bytes()
    with pytest.raises(RobotError):
        synthesize_vocalization("copyrighted-file.wav")


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="eSpeak NG tested in Ubuntu CI")
def test_espeak_output_encodes_with_real_sdk(transport):
    data = synthesize("Hallo Cozmo!")
    transport.audio(data)
    packet, _, _ = transport.client.anim_controller.queue.get()
    assert packet is not None and packet.to_bytes()


async def test_worker_failure_cannot_be_overwritten_by_late_telemetry(monkeypatch):
    backend = DirectBackend()
    backend._state = RobotState(connected=True, backend_name="direct")
    backend._fail("lost")
    messages = iter([{"state": RobotState(connected=True)}, {"camera": b"old"}])

    def read():
        try:
            return next(messages)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(backend, "_read", read)
    await backend._listen()
    assert not backend.state.connected and backend._camera is None


async def test_missing_dependency_fails_without_simulator_fallback(monkeypatch):
    monkeypatch.setattr(endpoint.importlib.util, "find_spec", lambda _: None)
    backend = DirectBackend()
    with pytest.raises(RobotError, match="extra"):
        await backend.connect()
    assert not backend.state.connected and backend.state.backend_name == "direct"


async def test_speech_stop_cancels_synthesis_before_transmission(monkeypatch):
    from cozmo_desktop.services.controller import RobotController

    backend = DirectBackend()
    backend._state = replace(backend.state, connected=True)
    gate = asyncio.Event()

    async def synthesize_wait(*args, **kwargs):
        await gate.wait()
        return b"unused"

    monkeypatch.setattr(endpoint.asyncio, "to_thread", synthesize_wait)
    backend._send = Mock(side_effect=AssertionError("Audio must not be transmitted"))
    controller = RobotController(backend)
    controller.submit("speech", lambda: backend.speak("hello"))
    await asyncio.sleep(0)
    controller.emergency_stop()
    await asyncio.sleep(0)
    gate.set()
    await controller.shutdown()
    backend._send.assert_not_called()


def test_cli_rejects_unattended_physical_smoke_test(monkeypatch):
    from cozmo_desktop.app.main import main

    monkeypatch.setattr("sys.argv", ["cozmo-desktop", "--backend", "direct", "--smoke-test", "."])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
