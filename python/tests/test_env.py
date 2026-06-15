from vhe.config.env import load_env_file


def test_load_env_file_reads_dotenv(tmp_path, monkeypatch) -> None:
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "live_paper.yaml").write_text("mode: paper\n")
    (tmp_path / ".env").write_text("KITE_API_KEY=from_dotenv\n")
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    path = load_env_file(tmp_path)
    assert path is not None
    import os

    assert os.environ.get("KITE_API_KEY") == "from_dotenv"
