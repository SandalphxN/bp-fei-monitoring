import os
import yaml
from typing import Any, Dict

from .paths import config_dir


def load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_indicators() -> Dict[str, Dict[str, Any]]:
    return load_yaml(os.path.join(config_dir(), "indicators.yml"))


def load_faculties() -> Dict[str, Dict[str, Any]]:
    return load_yaml(os.path.join(config_dir(), "faculties.yml"))


def load_settings() -> Dict[str, Dict[str, Any]]:
    return load_yaml(os.path.join(config_dir(), "settings.yml"))