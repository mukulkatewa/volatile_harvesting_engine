from vhe.platform.events import event
from vhe.platform.state import PlatformState



def test_platform_state_caps_events_and_serializes_latest() -> None:
    state = PlatformState()
    for index in range(205):
        state.append_event(event("test", f"event {index}"))

    snapshot = state.snapshot()

    assert len(state.events) == 200
    assert len(snapshot["events"]) == 40
    assert snapshot["events"][-1]["message"] == "event 204"
    assert snapshot["events"][-1]["severity"] == "info"
