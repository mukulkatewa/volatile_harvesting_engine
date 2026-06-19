from pathlib import Path

from vhe.sentiment.collectors.last30days_bridge import Last30DaysCollector, _engine_script, _resolve_engine_path


def test_last30days_engine_auto_detects_vendor_clone(project_root) -> None:
    vendor = project_root / "vendor" / "last30days-skill"
    if not _engine_script(vendor).exists():
        return
    collector = Last30DaysCollector(engine_path=_resolve_engine_path())
    assert collector.available
    assert collector.engine_path is not None
    assert _engine_script(collector.engine_path).name == "last30days.py"
