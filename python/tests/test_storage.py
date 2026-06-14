from pathlib import Path

from vhe.data.storage import build_bhavcopy_path


def test_build_bhavcopy_path_uses_expected_layout() -> None:
    path = build_bhavcopy_path(Path("data/raw"), "nse_bhavcopy", "2026-06-14")

    assert path == Path("data/raw/nse_bhavcopy/bhavcopy_2026-06-14.parquet")

