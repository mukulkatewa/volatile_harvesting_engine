from vhe.live.kite import nse_equity_token_map, parse_instruments_csv



def test_parse_instruments_csv_and_filter_nse_equity_tokens() -> None:
    payload = """instrument_token,exchange_token,tradingsymbol,name,exchange,instrument_type,segment,tick_size,lot_size
884737,3456,TATAMOTORS,TATA MOTORS,NSE,EQ,NSE,0.05,1
123,456,TATAMOTORS,TATA MOTORS,NFO,FUT,NFO-FUT,0.05,550
341249,1333,HDFCBANK,HDFC BANK,NSE,EQ,NSE,0.05,1
"""

    instruments = parse_instruments_csv(payload)
    token_map = nse_equity_token_map(instruments, ["tatamotors", "HDFCBANK"])

    assert token_map == {"TATAMOTORS": 884737, "HDFCBANK": 341249}
