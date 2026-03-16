"""
DocSync Configuration Module

Central configuration for all DocSync components.
Loads from config.ini (INI format) or environment variables with sensible defaults.
"""

import os
import configparser
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Mapping from INI section.key → dataclass attribute
_INI_MAP = {
    ("Storage", "data_dir"): "data_dir",
    ("Storage", "output_dir"): "output_dir",
    ("Storage", "history_dir"): "history_dir",
    ("Server", "host"): "api_host",
    ("Server", "port"): "api_port",
    ("Analysis", "similarity_threshold"): "similarity_threshold",
    ("Database", "path"): "db_path",
    ("AI_Validation", "model"): "gemini_model",
    ("Logging", "level"): "_log_level",
}

# Attributes that should be parsed as specific types
_FLOAT_ATTRS = {
    "ssim_weight", "histogram_weight", "edge_weight", "template_weight",
    "similarity_threshold", "high_confidence_threshold",
    "auto_approve_threshold", "review_threshold", "reject_threshold",
    "gemini_weight",
}
_INT_ATTRS = {"api_port", "max_versions"}
_BOOL_ATTRS = {"ollama_enabled", "gemini_enabled", "auth_enabled"}


@dataclass
class DocSyncConfig:
    """Central configuration for DocSync"""

    # Paths
    data_dir: str = "./data"
    output_dir: str = "./data/output"
    history_dir: str = "./data/history"
    plugins_dir: str = "./docsync/plugins"

    # Image comparison weights
    ssim_weight: float = 0.35
    histogram_weight: float = 0.20
    edge_weight: float = 0.25
    template_weight: float = 0.20
    similarity_threshold: float = 0.30
    high_confidence_threshold: float = 0.80

    # OCR settings
    tesseract_paths: list = field(default_factory=lambda: [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ])

    # Validation thresholds
    auto_approve_threshold: float = 0.85
    review_threshold: float = 0.60
    reject_threshold: float = 0.40

    # Ollama LLM settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_vision_model: str = "llava"
    ollama_enabled: bool = True

    # Gemini AI settings
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.0-flash"
    gemini_enabled: bool = False
    gemini_weight: float = 0.25

    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 7870

    # Auth / RBAC
    auth_enabled: bool = True
    db_path: str = "./data/docsync.db"

    # History
    max_versions: int = 50

    @classmethod
    def load(cls, config_path: str = "config.ini") -> "DocSyncConfig":
        """Load configuration from INI file, with env var overrides.

        Also supports legacy config.json for backwards compatibility.
        """
        config = cls()

        if os.path.exists(config_path):
            try:
                if config_path.endswith(".json"):
                    config._load_json(config_path)
                else:
                    config._load_ini(config_path)
                logger.info(f"Configuration loaded from {config_path}")
            except Exception as e:
                logger.warning(f"Could not load config from {config_path}: {e}")

        # Override with environment variables (prefix: DOCSYNC_)
        env_overrides = {
            "DOCSYNC_DATA_DIR": "data_dir",
            "DOCSYNC_OUTPUT_DIR": "output_dir",
            "DOCSYNC_OLLAMA_URL": "ollama_base_url",
            "DOCSYNC_OLLAMA_MODEL": "ollama_model",
            "DOCSYNC_GEMINI_KEY": "gemini_api_key",
            "DOCSYNC_API_HOST": "api_host",
            "DOCSYNC_API_PORT": "api_port",
            "DOCSYNC_DB_PATH": "db_path",
        }

        for env_key, attr in env_overrides.items():
            val = os.environ.get(env_key)
            if val is not None:
                config._set_typed(attr, val)

        return config

    def _load_ini(self, config_path: str):
        """Parse an INI config file and apply known keys."""
        parser = configparser.ConfigParser()
        parser.read(config_path, encoding="utf-8")

        for (section, key), attr in _INI_MAP.items():
            if parser.has_option(section, key):
                self._set_typed(attr, parser.get(section, key))

    def _load_json(self, config_path: str):
        """Parse a JSON config file (legacy support)."""
        with open(config_path, "r") as f:
            data = json.load(f)
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def _set_typed(self, attr: str, raw: str):
        """Set an attribute with the correct type conversion."""
        if attr.startswith("_"):
            return
        if attr in _FLOAT_ATTRS:
            setattr(self, attr, float(raw))
        elif attr in _INT_ATTRS:
            setattr(self, attr, int(raw))
        elif attr in _BOOL_ATTRS:
            setattr(self, attr, raw.lower() in ("true", "1", "yes"))
        else:
            setattr(self, attr, raw)

    def save(self, config_path: str = "config.ini"):
        """Save current configuration to INI file."""
        parser = configparser.ConfigParser()

        parser["Storage"] = {
            "data_dir": self.data_dir,
            "output_dir": self.output_dir,
            "history_dir": self.history_dir,
        }
        parser["Server"] = {
            "host": self.api_host,
            "port": str(self.api_port),
        }
        parser["Analysis"] = {
            "similarity_threshold": str(self.similarity_threshold),
            "ssim_weight": str(self.ssim_weight),
            "histogram_weight": str(self.histogram_weight),
            "edge_weight": str(self.edge_weight),
            "template_weight": str(self.template_weight),
            "high_confidence_threshold": str(self.high_confidence_threshold),
        }
        parser["Database"] = {
            "path": self.db_path,
        }
        parser["AI_Validation"] = {
            "model": self.gemini_model,
            "gemini_enabled": str(self.gemini_enabled).lower(),
        }

        with open(config_path, "w") as f:
            parser.write(f)
