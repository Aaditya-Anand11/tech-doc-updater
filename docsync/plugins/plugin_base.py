"""
DocSync Plugin Base Class and Registry

Provides the abstract base class for all plugins and
a registry to discover, load, and manage them.
"""

import os
import json
import logging
import importlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

logger = logging.getLogger("docsync.plugins")


class PluginBase(ABC):
    """
    Abstract base class for all DocSync plugins.
    
    Every plugin must define:
        - name: unique identifier
        - version: semver string
        - description: what the plugin does
        - initialize(): setup logic
        - execute(**kwargs): main processing
    """

    name: str = "base_plugin"
    version: str = "1.0.0"
    description: str = "Base plugin"

    @abstractmethod
    def initialize(self, config: Dict) -> bool:
        """Initialize the plugin with configuration. Return True on success."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the plugin's primary functionality."""
        pass

    def health_check(self) -> Dict:
        """Check plugin health/availability"""
        return {"name": self.name, "status": "ok", "version": self.version}


class PluginRegistry:
    """
    Discovers, loads, and manages plugins.
    
    Supports:
        - Built-in plugins (in docsync/plugins/builtin/)
        - External plugins (from a configured directory)
        - Configuration-driven enable/disable
    """

    def __init__(self, config_path: str = "./data/plugins_config.json"):
        self._plugins: Dict[str, PluginBase] = {}  # active/enabled
        self._all_plugins: Dict[str, PluginBase] = {}  # all discovered
        self._config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict:
        """Load plugin enable/disable config"""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        """Persist plugin enable/disable config"""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(self._config, f, indent=2)

    def register(self, plugin: PluginBase, config: Dict = None) -> bool:
        """Register and initialize a plugin"""
        # Always track in _all_plugins
        self._all_plugins[plugin.name] = plugin

        if plugin.name in self._plugins:
            logger.warning(f"Plugin '{plugin.name}' already registered, replacing")

        # Check if plugin is enabled in config
        if not self._config.get(plugin.name, True):
            logger.info(f"Plugin '{plugin.name}' is disabled in config")
            return False

        try:
            init_config = config or {}
            if plugin.initialize(init_config):
                self._plugins[plugin.name] = plugin
                logger.info(
                    f"Plugin registered: {plugin.name} v{plugin.version}"
                )
                return True
            else:
                logger.warning(f"Plugin '{plugin.name}' failed to initialize")
                return False
        except Exception as e:
            logger.error(f"Error initializing plugin '{plugin.name}': {e}")
            return False

    def get(self, name: str) -> Optional[PluginBase]:
        """Get a registered plugin by name"""
        return self._plugins.get(name)

    def list_plugins(self) -> List[Dict]:
        """List all active/enabled plugins with their status"""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "health": p.health_check(),
            }
            for p in self._plugins.values()
        ]

    def list_all_plugins(self) -> List[Dict]:
        """List ALL known plugins with enabled/disabled state"""
        result = []
        for name, p in self._all_plugins.items():
            enabled = name in self._plugins
            result.append({
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "enabled": enabled,
            })
        return result

    def toggle_plugin(self, name: str) -> bool:
        """Toggle a plugin on/off. Returns new enabled state."""
        plugin = self._all_plugins.get(name)
        if not plugin:
            raise ValueError(f"Plugin '{name}' not found")

        currently_enabled = name in self._plugins

        if currently_enabled:
            # Disable
            self._plugins.pop(name, None)
            self._config[name] = False
            logger.info(f"Plugin '{name}' disabled")
            new_state = False
        else:
            # Enable
            try:
                if plugin.initialize({}):
                    self._plugins[name] = plugin
                    self._config[name] = True
                    logger.info(f"Plugin '{name}' enabled")
                    new_state = True
                else:
                    new_state = False
            except Exception as e:
                logger.error(f"Failed to enable plugin '{name}': {e}")
                new_state = False

        self._save_config()
        return new_state

    def execute_plugin(self, name: str, **kwargs) -> Any:
        """Execute a plugin by name"""
        plugin = self.get(name)
        if plugin is None:
            raise ValueError(f"Plugin '{name}' not found")
        return plugin.execute(**kwargs)

    def discover_builtin(self):
        """Auto-discover and register built-in plugins"""
        from docsync.plugins.builtin.ssim_plugin import SSIMPlugin
        from docsync.plugins.builtin.histogram_plugin import HistogramPlugin
        from docsync.plugins.builtin.edge_plugin import EdgePlugin
        from docsync.plugins.builtin.template_plugin import TemplatePlugin
        from docsync.plugins.builtin.phash_plugin import PerceptualHashPlugin

        builtin_plugins = [
            SSIMPlugin(),
            HistogramPlugin(),
            EdgePlugin(),
            TemplatePlugin(),
            PerceptualHashPlugin(),
        ]

        for plugin in builtin_plugins:
            self.register(plugin)

        # Try to register Ollama plugin (optional)
        try:
            from docsync.plugins.builtin.ollama_plugin import OllamaLLMPlugin
            ollama = OllamaLLMPlugin()
            self.register(ollama)
        except Exception as e:
            logger.info(f"Ollama plugin not available: {e}")

