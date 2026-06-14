from __future__ import annotations

import struct
from datetime import datetime, timezone

from vhe.live.kite_binary import parse_kite_binary_message, parse_kite_packet



def _packet_message(packet: bytes) -> bytes:
    return struct.pack(">H", 1) + struct.pack(">H", len(packet)) + packet



def test_parse_ltp_packet() -> None:
    packet = struct.pack(">ii", 884737, 95025)

    parsed = parse_kite_binary_message(_packet_message(packet))[0]

    assert parsed.instrument_token == 884737
    assert parsed.ltp == 950.25



def test_parse_quote_packet() -> None:
    packet = struct.pack(
        ">iiiiiiiiiii",
        884737,
        95025,
        10,
        94980,
        1_000_000,
        50_000,
        45_000,
        94000,
        95500,
        93000,
        94800,
    )

    parsed = parse_kite_packet(packet)

    assert parsed.ltp == 950.25
    assert parsed.volume == 1_000_000
    assert parsed.open == 940.0
    assert parsed.close == 948.0



def test_parse_full_packet_with_depth_and_timestamp() -> None:
    header = struct.pack(
        ">iiiiiiiiiiiiiiii",
        884737,
        95025,
        10,
        94980,
        1_000_000,
        50_000,
        45_000,
        94000,
        95500,
        93000,
        94800,
        1_717_000_000,
        0,
        0,
        0,
        1_717_000_001,
    )
    bids = b"".join(struct.pack(">iiHxx", 100 + i, 95000 - i * 5, 2 + i) for i in range(5))
    asks = b"".join(struct.pack(">iiHxx", 200 + i, 95100 + i * 5, 3 + i) for i in range(5))

    parsed = parse_kite_packet(header + bids + asks)
    quote = parsed.to_live_quote({884737: "TATAMOTORS"})

    assert parsed.exchange_timestamp == datetime.fromtimestamp(1_717_000_001, tz=timezone.utc)
    assert quote.symbol == "TATAMOTORS"
    assert quote.bid.price == 950.0
    assert quote.ask.price == 951.0
    assert round(quote.spread_bps, 2) == 10.52
