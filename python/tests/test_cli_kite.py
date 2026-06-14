from pathlib import Path

from vhe.cli import main



def test_kite_cache_and_token_map_cli(tmp_path, capsys, monkeypatch) -> None:
    csv_path = tmp_path / "instruments.csv"
    csv_path.write_text(
        """instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange
884737,3456,TATAMOTORS,TATA MOTORS,0,,,0.05,1,EQ,NSE,NSE
341249,1333,HDFCBANK,HDFC BANK,0,,,0.05,1,EQ,NSE,NSE
"""
    )
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
environment: test
timezone: Asia/Kolkata
paths:
  raw_data_dir: data/raw
  processed_data_dir: data/processed
  research_data_dir: data/research
  reports_dir: reports
universe:
  name: test
  symbols: [TATAMOTORS, HDFCBANK, MISSING]
market:
  exchange: NSE
  timezone: Asia/Kolkata
  session_start: "09:15"
  session_end: "15:30"
data:
  source: nse_bhavcopy
  adjusted_prices: true
  timeframe: 1d
  turnover_threshold_inr: 100000000
  min_close_price_inr: 100
"""
    )
    cache_dir = tmp_path / "kite"

    monkeypatch.setattr(
        "sys.argv",
        ["vhe", "--config", str(config_path), "kite-cache-instruments", "--csv", str(csv_path), "--date", "2026-06-15", "--cache-dir", str(cache_dir)],
    )
    main()
    assert "instruments=2" in capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        ["vhe", "--config", str(config_path), "kite-token-map", "--date", "2026-06-15", "--cache-dir", str(cache_dir)],
    )
    main()
    output = capsys.readouterr().out

    assert "HDFCBANK=341249" in output
    assert "TATAMOTORS=884737" in output
    assert "missing=MISSING" in output
