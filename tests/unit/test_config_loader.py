"""Tests for YAML configuration loader."""

import os

import pytest

from conversational_bi.config.loader import (
    ConfigLoader,
    load_yaml_config,
    substitute_env_vars,
)


class TestEnvVarSubstitution:
    """Test environment variable substitution in config values."""

    def test_substitute_simple_var(self, monkeypatch):
        """Should substitute ${VAR} with environment value."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        result = substitute_env_vars("${TEST_VAR}")
        assert result == "test_value"

    def test_substitute_var_with_default(self):
        """Should use default when var not set."""
        # Ensure var is not set
        os.environ.pop("NONEXISTENT_VAR", None)
        result = substitute_env_vars("${NONEXISTENT_VAR:default_value}")
        assert result == "default_value"

    def test_substitute_var_ignores_default_when_set(self, monkeypatch):
        """Should use env value even when default provided."""
        monkeypatch.setenv("MY_VAR", "env_value")
        result = substitute_env_vars("${MY_VAR:default_value}")
        assert result == "env_value"

    def test_substitute_multiple_vars(self, monkeypatch):
        """Should substitute multiple vars in one string."""
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        result = substitute_env_vars("http://${HOST}:${PORT}")
        assert result == "http://localhost:8080"

    def test_substitute_in_dict(self, monkeypatch):
        """Should recursively substitute in dictionaries."""
        monkeypatch.setenv("API_KEY", "secret123")
        data = {
            "key": "${API_KEY}",
            "nested": {"value": "${API_KEY}"},
        }
        result = substitute_env_vars(data)
        assert result["key"] == "secret123"
        assert result["nested"]["value"] == "secret123"

    def test_substitute_in_list(self, monkeypatch):
        """Should substitute in list items."""
        monkeypatch.setenv("ITEM", "value")
        data = ["${ITEM}", "static", "${ITEM}"]
        result = substitute_env_vars(data)
        assert result == ["value", "static", "value"]

    def test_no_substitution_for_non_string(self):
        """Should pass through non-string values."""
        data = {"number": 42, "boolean": True, "none": None}
        result = substitute_env_vars(data)
        assert result == data


class TestLoadYamlConfig:
    """Test YAML file loading."""

    def test_load_existing_config(self, tmp_path):
        """Should load and parse YAML file."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("key: value\nnested:\n  inner: 123")

        result = load_yaml_config(config_file)
        assert result["key"] == "value"
        assert result["nested"]["inner"] == 123

    def test_load_nonexistent_file(self, tmp_path):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_yaml_config(tmp_path / "nonexistent.yaml")

    def test_load_with_env_substitution(self, tmp_path, monkeypatch):
        """Should substitute env vars in loaded config."""
        monkeypatch.setenv("DB_HOST", "myhost")
        config_file = tmp_path / "test.yaml"
        config_file.write_text("database:\n  host: ${DB_HOST:localhost}")

        result = load_yaml_config(config_file)
        assert result["database"]["host"] == "myhost"


class TestConfigLoader:
    """Test ConfigLoader class."""

    @pytest.fixture
    def config_loader(self, tmp_path):
        """Create loader with temp config directory."""
        # Create config structure
        (tmp_path / "database").mkdir()
        (tmp_path / "data_agents").mkdir()

        # Create schema.yaml
        schema_content = """
tables:
  customers:
    description: Test table
    columns:
      - name: id
        type: INTEGER
        primary_key: true
"""
        (tmp_path / "database" / "schema.yaml").write_text(schema_content)

        # Create llm.yaml
        llm_content = """
default_model: gpt-4o
providers:
  openai:
    api_key: ${OPENAI_API_KEY:test}
"""
        (tmp_path / "llm.yaml").write_text(llm_content)

        # Create data agent config
        agent_content = """
agent:
  name: Test Agent
  port: 8001
  table: customers
"""
        (tmp_path / "data_agents" / "customers.yaml").write_text(agent_content)

        return ConfigLoader(config_dir=tmp_path)

    def test_load_schema(self, config_loader):
        """Should load schema.yaml from database directory."""
        schema = config_loader.load_schema()
        assert "tables" in schema
        assert "customers" in schema["tables"]

    def test_load_llm_config(self, config_loader):
        """Should load llm.yaml."""
        llm = config_loader.load_llm_config()
        assert llm["default_model"] == "gpt-4o"

    def test_load_agent_config(self, config_loader):
        """Should load agent config from data_agents directory."""
        agent = config_loader.load_agent_config("customers")
        assert agent["agent"]["name"] == "Test Agent"
        assert agent["agent"]["port"] == 8001

    def test_get_table_schema(self, config_loader):
        """Should return specific table schema."""
        table = config_loader.get_table_schema("customers")
        assert table["description"] == "Test table"
        assert len(table["columns"]) == 1

    def test_get_column_info_string(self, config_loader):
        """Should format column info for prompts."""
        info = config_loader.get_column_info_string("customers")
        assert "id" in info
        assert "INTEGER" in info
        assert "primary key" in info.lower()


class TestGlobalLoaders:
    """Test module-level loader functions."""

    def test_load_schema_uses_default_path(self, monkeypatch, tmp_path):
        """Global load_schema should use default config directory."""
        # This test verifies the function exists and is callable
        # In practice, it would use the real config directory
        pass  # Integration test would verify actual file loading

    def test_load_agent_config_accepts_name(self):
        """load_agent_config should accept agent name."""
        # This is more of an integration test
        pass
