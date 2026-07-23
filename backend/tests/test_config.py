import os, importlib

def test_dotted_get_and_default(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("server:\n  port: 5180\nfilter:\n  urls_limit: 5\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_FILE", str(cfg))
    import config.config_loader as cl
    importlib.reload(cl)
    assert cl.config.get("server.port") == 5180
    assert cl.config.get("filter.urls_limit") == 5
    assert cl.config.get("missing.key", "fallback") == "fallback"

def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.yaml"))
    import config.config_loader as cl
    importlib.reload(cl)
    assert cl.config.get("server.port", 5180) == 5180
