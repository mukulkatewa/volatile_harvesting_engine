from datetime import date

from vhe.live.kite_instruments import cache_instruments_csv, instrument_cache_path, load_cached_instruments



def test_cache_and_load_kite_instruments(tmp_path) -> None:
    payload = """instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange
884737,3456,TATAMOTORS,TATA MOTORS,0,,,0.05,1,EQ,NSE,NSE
"""
    trading_date = date(2026, 6, 15)

    cached = cache_instruments_csv(payload, cache_dir=tmp_path, trading_date=trading_date)
    loaded = load_cached_instruments(cache_dir=tmp_path, trading_date=trading_date)

    assert cached.path == instrument_cache_path(cache_dir=tmp_path, trading_date=trading_date)
    assert loaded.instruments[0].tradingsymbol == "TATAMOTORS"
