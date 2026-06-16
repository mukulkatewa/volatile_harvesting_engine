from vhe.live.kite_session import kite_session_checksum


def test_kite_session_checksum() -> None:
    value = kite_session_checksum("api", "req", "secret")
    assert len(value) == 64
    assert value == kite_session_checksum("api", "req", "secret")
