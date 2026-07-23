import os
import yaml

_here = os.path.dirname(os.path.abspath(__file__))
_default_path = os.path.join(_here, "..", "config.yaml")


class Config:
    def __init__(self):
        path = os.environ.get("CONFIG_FILE") or _default_path
        self._data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def get(self, key, default=None):
        cur = self._data
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


config = Config()
