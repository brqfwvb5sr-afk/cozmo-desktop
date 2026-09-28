import json
from dataclasses import replace

import pytest

from cozmo_desktop.robot.base import RobotError, RobotState
from cozmo_desktop.services.cliff_trace import MAX_SAMPLES, CliffTrace, analyze_trace


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
    assert payload["analysis"]["status"] == "incomplete"
    assert payload["analysis"]["table_driving_approved"] is False
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


def test_trace_analysis_compares_each_raw_channel_without_claiming_safety():
    samples = []
    for label in ("center", "front edge", "rear edge", "left edge", "right edge"):
        for index in range(5):
            raw = [100 + index, 200 + index, 300 + index, 400 + index]
            if label == "front edge":
                raw[0] += 100
            elif label == "rear edge":
                raw[1] -= 100
            elif label == "left edge":
                raw[2] += 100
            elif label == "right edge":
                raw[3] -= 100
            samples.append({"label": label, "raw": raw, "cliff_detected": label != "center"})
    report = analyze_trace(samples)
    assert report["status"] == "comparison_only"
    assert report["insufficient_positions"] == []
    assert report["nonoverlapping_channels_vs_center"]["front edge"] == [
        {"channel": 0, "direction": "higher", "gap": 96}
    ]
    assert report["nonoverlapping_channels_vs_center"]["rear edge"] == [
        {"channel": 1, "direction": "lower", "gap": 96}
    ]
    assert report["cliff_flagged_samples"]["front edge"] == 5
    assert report["table_driving_approved"] is False


def test_trace_analysis_excludes_missing_raw_and_motion():
    samples = [
        {"label": "center", "raw": [100, 100, 100, 100]},
        {"label": "center", "raw": None},
        {"label": "front edge", "raw": [200, 100, 100, 100], "left_speed_mm_s": 2},
        {"label": "front edge", "raw": [200, 100, 100, 100], "picked_up": True},
    ]
    report = analyze_trace(samples)
    assert report["status"] == "incomplete"
    assert report["excluded_missing_raw"] == 1
    assert report["excluded_unsafe_or_moving"] == 2
    assert report["valid_samples"]["front edge"] == 0
    assert report["nonoverlapping_channels_vs_center"]["front edge"] == []
