import json
from dataclasses import replace

import pytest

from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.services.cliff_trace import MAX_SAMPLES, CliffTrace


def direct_state(**changes):
    return replace(
        RobotState(connected=True, backend_name="direct", motors_enabled=False),
        **changes,
    )


def test_stationary_trace_records_labeled_raw_values_without_personal_data(tmp_path):
    trace = CliffTrace()
    trace.start(direct_state(), now=20)
    trace.observe(direct_state(cliff_raw=(100, 200, 300, 400)), now=20.1)
    trace.label = "front edge"
    trace.observe(direct_state(cliff_raw=(900, 201, 301, 401), cliff_detected=True), now=20.2)
    path = tmp_path / "trace.json"
    trace.export(path)
    payload = json.loads(path.read_text())
    assert payload["sample_count"] == 2
    assert payload["samples"][0]["raw"] == [100, 200, 300, 400]
    assert payload["samples"][1]["label"] == "front edge"
    assert payload["samples"][1]["cliff_detected"]
    assert "speech" not in path.read_text()
    assert "172.31" not in path.read_text()


def test_trace_rejects_arming_and_auto_stops_on_motor_enable_or_disconnect():
    trace = CliffTrace()
    with pytest.raises(RobotError, match="physical"):
        trace.start(RobotState())
    with pytest.raises(RobotError, match="Lock motors"):
        trace.start(direct_state(motors_enabled=True))
    trace.start(direct_state(), now=1)
    trace.observe(direct_state(left_speed=2), now=1.1)
    assert trace.active and trace.samples[-1]["left_speed_mm_s"] == 2
    trace.observe(direct_state(motors_enabled=True), now=1.2)
    assert not trace.active and len(trace.samples) == 1
    trace.start(direct_state(), now=2)
    trace.observe(direct_state(), now=2.1)
    trace.observe(direct_state(connected=False), now=2.2)
    assert not trace.active and len(trace.samples) == 1


def test_trace_has_fixed_memory_limit():
    trace = CliffTrace()
    trace.start(direct_state(), now=0)
    for index in range(MAX_SAMPLES + 5):
        trace.observe(direct_state(), now=index * 0.1)
    assert not trace.active and len(trace.samples) == MAX_SAMPLES
