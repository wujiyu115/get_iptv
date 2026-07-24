import logging
import os

os.makedirs(os.environ.get("LOG_DIR", "logs"), exist_ok=True)
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


class _MutePolls(logging.Filter):
    # uvicorn.access record.args = (client, method, path, http_ver, status)
    _MUTE = ("/api/tasks/status", "/api/tasks/logs")

    def filter(self, rec: logging.LogRecord) -> bool:
        args = rec.args
        if isinstance(args, tuple) and len(args) >= 3:
            return not str(args[2]).startswith(self._MUTE)
        return True


logging.getLogger("uvicorn.access").addFilter(_MutePolls())
logger = logging.getLogger("iptv")
