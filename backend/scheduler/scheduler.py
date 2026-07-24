from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.config_loader import config
from services import run_service
from utils.logger import logger

_scheduler: BackgroundScheduler | None = None
_override: dict = {}


def get_schedule() -> dict:
    base = {
        "update_mode": config.get("schedule.update_mode", "interval"),
        "update_interval": config.get("schedule.update_interval", 12),
        "update_times": config.get("schedule.update_times", []),
        "update_startup": config.get("schedule.update_startup", True),
        "time_zone": config.get("schedule.time_zone", "Asia/Shanghai"),
    }
    base.update(_override)
    return base


def set_schedule(d: dict) -> None:
    _override.update(d)
    if _scheduler is not None:
        _rebuild_jobs()


def _job() -> None:
    try:
        run_service.start_run_async()
    except RuntimeError:
        logger.info("scheduled run skipped — a run is in progress")


def _rebuild_jobs() -> None:
    sched = get_schedule()
    _scheduler.remove_all_jobs()
    if sched["update_mode"] == "time":
        for hhmm in sched["update_times"]:
            hh, mm = hhmm.split(":")
            _scheduler.add_job(_job, CronTrigger(hour=int(hh), minute=int(mm),
                                                 timezone=sched["time_zone"]))
    else:
        _scheduler.add_job(_job, IntervalTrigger(hours=sched["update_interval"],
                                                 timezone=sched["time_zone"]))


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = get_schedule()
    _scheduler = BackgroundScheduler(timezone=sched["time_zone"])
    _rebuild_jobs()
    _scheduler.start()
    if sched["update_startup"]:
        try:
            run_service.start_run_async()
        except RuntimeError:
            pass


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
