"""
DocSync Configuration Module

Central configuration for all DocSync components.
Loads from config.json or environment variables with sensible defaults.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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
    similarity_threshold: float = 0.55
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
    gemini_enabled: bool = False  # Set to True when Gemini quota resets
    gemini_weight: float = 0.25

    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Auth / RBAC
    auth_enabled: bool = True
    db_path: str = "./data/docsync.db"

    # History
    max_versions: int = 50

    @classmethod
    def load(cls, config_path: str = "config.json") -> "DocSyncConfig":
        """Load configuration from file, with env var overrides"""
        config = cls()

        # Load from JSON file
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
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
                if attr == "api_port":
                    setattr(config, attr, int(val))
                else:
                    setattr(config, attr, val)

        return config

    def save(self, config_path: str = "config.json"):
        """Save current configuration to JSON file"""
        data = {
            "data_dir": self.data_dir,
            "output_dir": self.output_dir,
            "history_dir": self.history_dir,
            "ssim_weight": self.ssim_weight,
            "histogram_weight": self.histogram_weight,
            "edge_weight": self.edge_weight,
            "template_weight": self.template_weight,
            "similarity_threshold": self.similarity_threshold,
            "high_confidence_threshold": self.high_confidence_threshold,
            "auto_approve_threshold": self.auto_approve_threshold,
            "review_threshold": self.review_threshold,
            "reject_threshold": self.reject_threshold,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "ollama_enabled": self.ollama_enabled,
            "gemini_api_key": self.gemini_api_key,
            "gemini_model": self.gemini_model,
            "gemini_enabled": self.gemini_enabled,
            "gemini_weight": self.gemini_weight,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "auth_enabled": self.auth_enabled,
            "db_path": self.db_path,
            "max_versions": self.max_versions,
        }
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
