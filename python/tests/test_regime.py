from vhe.strategies.regime import MarketRegime, RegimeDetector, RegimeInputs



def test_regime_detector_classifies_range_and_crash() -> None:
    detector = RegimeDetector()

    assert detector.classify(RegimeInputs(price=100, ema_20=100, ema_50=100, adx_14=12)) == MarketRegime.RANGE
    assert detector.classify(RegimeInputs(price=100, ema_20=100, ema_50=100, adx_14=22)) == MarketRegime.RANGE
    # Genuine intraday collapse -> CRASH.
    assert detector.classify(RegimeInputs(price=94, ema_20=97, ema_50=100, adx_14=12, intraday_drawdown_pct=-7)) == MarketRegime.CRASH


def test_routine_intraday_dip_stays_range_not_crash() -> None:
    detector = RegimeDetector()
    # A normal 2% pullback from session high is the dip the grid harvests, not a crash.
    assert detector.classify(
        RegimeInputs(price=98, ema_20=99, ema_50=100, adx_14=12, intraday_drawdown_pct=-2)
    ) == MarketRegime.RANGE


def test_regime_warmup_adx_not_unknown() -> None:
    detector = RegimeDetector()
    assert detector.classify(RegimeInputs(price=100, ema_20=100, ema_50=100, adx_14=17)) == MarketRegime.RANGE
