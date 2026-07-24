import importlib


def test_get_set_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "c.yaml"))
    (tmp_path / "c.yaml").write_text(
        "schedule:\n  update_mode: interval\n  update_interval: 12\n"
        "  update_startup: false\n  time_zone: Asia/Shanghai\n", encoding="utf-8")
    import config.config_loader as cl
    import scheduler.scheduler as s
    importlib.reload(cl); importlib.reload(s)
    sched = s.get_schedule()
    assert sched["update_mode"] == "interval" and sched["update_interval"] == 12
    s.set_schedule({"update_interval": 6})
    assert s.get_schedule()["update_interval"] == 6


def test_start_builds_jobs_no_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "c.yaml"))
    (tmp_path / "c.yaml").write_text(
        "schedule:\n  update_mode: interval\n  update_interval: 3\n"
        "  update_startup: false\n  time_zone: UTC\n", encoding="utf-8")
    import config.config_loader as cl
    import scheduler.scheduler as s
    importlib.reload(cl); importlib.reload(s)
    s.start()
    assert s._scheduler is not None
    assert len(s._scheduler.get_jobs()) == 1
    s.shutdown()
