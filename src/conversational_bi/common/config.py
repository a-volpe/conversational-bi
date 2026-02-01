"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute project root .env path (src/conversational_bi/common/config.py -> project root)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Prioritize .env file over system/user environment variables
        env_file_override=True,
    )

    # Database
    database_url: str = "postgresql://localhost:5432/conversational_bi"

    # OpenAI
    openai_api_key: str = ""

    # Agent ports
    orchestrator_host: str = "localhost"
    orchestrator_port: int = 8000

    customers_agent_host: str = "localhost"
    customers_agent_port: int = 8001

    orders_agent_host: str = "localhost"
    orders_agent_port: int = 8002

    products_agent_host: str = "localhost"
    products_agent_port: int = 8003

    # Logging
    log_level: str = "INFO"

    @property
    def orchestrator_url(self) -> str:
        return f"http://{self.orchestrator_host}:{self.orchestrator_port}"

    @property
    def customers_agent_url(self) -> str:
        return f"http://{self.customers_agent_host}:{self.customers_agent_port}"

    @property
    def orders_agent_url(self) -> str:
        return f"http://{self.orders_agent_host}:{self.orders_agent_port}"

    @property
    def products_agent_url(self) -> str:
        return f"http://{self.products_agent_host}:{self.products_agent_port}"

    @property
    def data_agent_urls(self) -> list[str]:
        return [
            self.customers_agent_url,
            self.orders_agent_url,
            self.products_agent_url,
        ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
