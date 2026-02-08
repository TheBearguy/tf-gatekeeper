"""Configuration management for tf-gate."""

from pathlib import Path
from typing import Any, Optional, Union

import yaml

DEFAULT_CONFIG = {
    "opa": {
        "policy_dir": "./policies",
        "strict_mode": True,
    },
    "phases": {
        "phase_3_time_gating": {
            "friday_cutoff_hour": 15,
            "weekend_blocking": True,
        },
        "phase_4_intent": {
            "provider": "ollama",
            "model": "llama3",
            "enabled": False,
        },
    },
    "blast_radius": {
        "thresholds": {
            "green": 5,
            "yellow": 20,
            "red": 50,
        },
    },
    "notifications": {
        "slack_webhook": None,
        "pagerduty_key": None,
    },
}


class Config:
    """Configuration manager for tf-gate."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file. If None, uses defaults.
        """
        self._config = DEFAULT_CONFIG.copy()

        if config_path:
            self.load_from_file(config_path)

    def load_from_file(self, config_path: Union[str, Path]) -> None:
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file.
        """
        config_path = Path(config_path)

        if not config_path.exists():
            return

        with open(config_path) as f:
            user_config = yaml.safe_load(f)

        if user_config:
            self._merge_config(user_config)

    def _merge_config(self, user_config: dict[str, Any]) -> None:
        """Merge user config with defaults.

        Args:
            user_config: User-provided configuration dictionary.
        """

        def merge_dict(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
            return base

        merge_dict(self._config, user_config)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Supports dot notation for nested keys (e.g., "opa.policy_dir").

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key.

        Args:
            key: Configuration key (supports dot notation).
            value: Value to set.
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary.

        Returns:
            Configuration dictionary.
        """
        return self._config.copy()

    def save_to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path to save configuration file.
        """
        config_path = Path(config_path)

        with open(config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False)


def find_config_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find configuration file in current directory or parents.

    Args:
        start_dir: Directory to start searching from. Defaults to current directory.

    Returns:
        Path to config file if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    config_names = ["tf-gate.yaml", "tf-gate.yml", ".tf-gate.yaml", ".tf-gate.yml"]

    current = start_dir.resolve()

    while True:
        for config_name in config_names:
            config_path = current / config_name
            if config_path.exists():
                return config_path

        # Check if we've reached the root
        if current.parent == current:
            break

        current = current.parent

    return None


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Load configuration from file or use defaults.

    Args:
        config_path: Optional explicit config file path.

    Returns:
        Config object.
    """
    if config_path:
        return Config(config_path)

    # Try to find config file
    found_path = find_config_file()
    if found_path:
        return Config(found_path)

    return Config()
