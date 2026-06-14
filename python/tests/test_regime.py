from vhe.strategies.regime import MarketRegime, RegimeDetector, RegimeInputs



def test_regime_detector_classifies_range_and_crash() -> None:
    detector = RegimeDetector()

    assert detector.classify(RegimeInputs(price=100, ema_20=100, ema_50=100, adx_14=12)) == MarketRegime.RANGE
    assert detector.classify(RegimeInputs(price=98, ema_20=99, ema_50=100, adx_14=12, intraday_drawdown_pct=-2)) == MarketRegime.CRASH
