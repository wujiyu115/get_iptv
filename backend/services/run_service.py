import threading
from collections import deque
from datetime import datetime, timezone
from queue import Queue

from pipeline import runner
from pipeline.models import RunCancelled
from utils.logger import logger

_LOCK = threading.Lock()
_cancel = threading.Event()
_logs: deque = deque(maxlen=1000)
_subscribers: list[Queue] = []
_sub_lock = threading.Lock()

state = {"status": "idle", "stage": "", "run_id": None, "started_at": None}


def try_acquire() -> bool:
    return _LOCK.acquire(blocking=False)


def release() -> None:
    if _LOCK.locked():
        _LOCK.release()


def subscribe() -> Queue:
    q: Queue = Queue()
    with _sub_lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: Queue) -> None:
    with _sub_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def push_log(msg: str, stage: str = "") -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    logger.info(msg)
    _logs.append(line)
    if stage:
        state["stage"] = stage
    with _sub_lock:
        for q in list(_subscribers):
            q.put(line)


def snapshot() -> dict:
    return {**state, "logs": list(_logs)[-200:]}


def request_cancel() -> bool:
    """Signal the running task to stop. Returns False if nothing is running."""
    if not _LOCK.locked():
        return False
    _cancel.set()
    return True


def _run_thread():
    state.update(status="running", started_at=datetime.now(timezone.utc).isoformat())
    try:
        rid = runner.run(on_event=push_log, should_cancel=_cancel.is_set)
        state.update(status="done", run_id=rid)
    except RunCancelled:
        state["status"] = "cancelled"
    except Exception:  # noqa: BLE001
        state["status"] = "failed"
    finally:
        release()


def start_run_async() -> None:
    if not try_acquire():
        raise RuntimeError("a run is already in progress")
    _cancel.clear()
    _logs.clear()
    state["stage"] = ""
    threading.Thread(target=_run_thread, daemon=True).start()
