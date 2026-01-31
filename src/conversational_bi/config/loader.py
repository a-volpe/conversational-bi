"""YAML configuration loader with environment variable substitution."""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


# Pattern for ${VAR} or ${VAR:default}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")

# Default config directory (relative to project root)
# loader.py is at src/conversational_bi/config/loader.py
# config dir is at config/ (project root/config)
DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


def substitute_env_vars(value: Any) -> Any:
    """
    Recursively substitute environment variables in config values.

    Supports:
    - ${VAR} - substitutes with env var, empty string if not set
    - ${VAR:default} - substitutes with env var, or default if not set

    Args:
        value: Config value (string, dict, list, or other)

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        def replace_match(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is not None:
                return env_value
            return default if default is not None else ""

        return ENV_VAR_PATTERN.sub(replace_match, value)

    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]

    else:
        return value


def load_yaml_config(path: Path) -> dict[str, Any]:
    """
    Load a YAML configuration file with environment variable substitution.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return substitute_env_vars(data)


class ConfigLoader:
    """
    Configuration loader for the application.

    Provides methods to load various configuration files
    from the config directory.
    """

    def __init__(self, config_dir: Path | None = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Path to config directory. Defaults to project's config/.
        """
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self._cache: dict[str, Any] = {}

    def _load_cached(self, key: str, path: Path) -> dict[str, Any]:
        """Load config with caching."""
        if key not in self._cache:
            self._cache[key] = load_yaml_config(path)
        return self._cache[key]

    def load_schema(self) -> dict[str, Any]:
        """Load the database schema configuration."""
        return self._load_cached(
            "schema",
            self.config_dir / "database" / "schema.yaml"
        )

    def load_llm_config(self) -> dict[str, Any]:
        """Load the LLM configuration."""
        return self._load_cached(
            "llm",
            self.config_dir / "llm.yaml"
        )

    def load_fe_agent_config(self) -> dict[str, Any]:
        """Load the frontend agent configuration."""
        return self._load_cached(
            "fe_agent",
            self.config_dir / "fe_agent.yaml"
        )

    def load_app_config(self) -> dict[str, Any]:
        """Load the application configuration."""
        return self._load_cached(
            "app",
            self.config_dir / "app.yaml"
        )

    def load_agent_config(self, agent_name: str) -> dict[str, Any]:
        """
        Load a data agent's configuration.

        Args:
            agent_name: Name of the agent (e.g., 'customers', 'orders')

        Returns:
            Agent configuration dictionary
        """
        key = f"agent_{agent_name}"
        return self._load_cached(
            key,
            self.config_dir / "data_agents" / f"{agent_name}.yaml"
        )

    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """
        Get schema for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Table schema dictionary

        Raises:
            KeyError: If table not found in schema
        """
        schema = self.load_schema()
        tables = schema.get("tables", {})
        if table_name not in tables:
            raise KeyError(f"Table '{table_name}' not found in schema")
        return tables[table_name]

    def get_column_info_string(self, table_name: str) -> str:
        """
        Format table columns as a string for use in prompts.

        Args:
            table_name: Name of the table

        Returns:
            Formatted string describing columns
        """
        table = self.get_table_schema(table_name)
        lines = []

        for col in table.get("columns", []):
            parts = [f"- {col['name']} ({col['type']})"]

            if col.get("primary_key"):
                parts.append("[PRIMARY KEY]")
            if col.get("unique"):
                parts.append("[UNIQUE]")
            if col.get("foreign_key"):
                parts.append(f"[FK -> {col['foreign_key']}]")

            if col.get("description"):
                parts.append(f": {col['description']}")

            if col.get("allowed_values"):
                parts.append(f" [Values: {', '.join(col['allowed_values'])}]")

            lines.append(" ".join(parts))

        return "\n".join(lines)

    def clear_cache(self):
        """Clear the configuration cache."""
        self._cache.clear()


# Global loader instance
_global_loader: ConfigLoader | None = None


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _global_loader
    if _global_loader is None:
        _global_loader = ConfigLoader()
    return _global_loader


# Convenience functions that use the global loader


def load_schema() -> dict[str, Any]:
    """Load the database schema configuration."""
    return get_config_loader().load_schema()


def load_llm_config() -> dict[str, Any]:
    """Load the LLM configuration."""
    return get_config_loader().load_llm_config()


def load_agent_config(agent_name: str) -> dict[str, Any]:
    """Load a data agent's configuration."""
    return get_config_loader().load_agent_config(agent_name)
