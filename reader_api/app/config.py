import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


@dataclass(frozen=True)
class Auth0MCPConfig:
    fast_mcp_client_id: str
    fast_mcp_client_secret: str


@dataclass(frozen=True)
class Auth0Config:
    api_audience: str
    issuer_domain: str
    algorithms: Tuple[str, ...]
    mcp: Auth0MCPConfig


@dataclass(frozen=True)
class LoggingConfig:
    level_name: str
    level: int


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    echo: bool


@dataclass(frozen=True)
class NetworkingConfig:
    reader_api_url: str
    content_service_url: str


class Config:
    instance: Optional["Config"] = None

    def __init__(self):
        # Load environment variables from .env file
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        self.auth0 = self._load_auth0_config()
        self.logging = self._load_logging_config()
        self.database = self._load_database_config()
        self.networking = self._load_networking_config()

        logging.basicConfig(level=self.logging.level)

    def _load_networking_config(self) -> NetworkingConfig:
        reader_api_url = self._require_env("READER_API_PUBLIC_URL")
        content_service_url = self._require_env("CONTENT_SERVICE_URL")
        return NetworkingConfig(
            reader_api_url=reader_api_url,
            content_service_url=content_service_url,
        )

    def _load_auth0_config(self) -> Auth0Config:
        api_audience = self._require_env("AUTH0_API_AUDIENCE")
        issuer_domain = self._require_env("AUTH0_ISSUER_DOMAIN")
        if not issuer_domain:
            raise ValueError("AUTH0_ISSUER_DOMAIN must include a valid domain")
        algorithms_value = self._require_env("AUTH0_ALGORITHMS")
        algorithms = tuple(
            algorithm.strip()
            for algorithm in algorithms_value.split(",")
            if algorithm.strip()
        )
        if not algorithms:
            raise ValueError(
                "AUTH0_ALGORITHMS must specify at least one algorithm"
            )
        fast_mcp_client_id = self._require_env("AUTH0_FAST_MCP_CLIENT_ID")
        fast_mcp_client_secret = self._require_env(
            "AUTH0_FAST_MCP_CLIENT_SECRET"
        )

        return Auth0Config(
            api_audience=api_audience,
            issuer_domain=issuer_domain,
            algorithms=algorithms,
            mcp=Auth0MCPConfig(
                fast_mcp_client_id=fast_mcp_client_id,
                fast_mcp_client_secret=fast_mcp_client_secret,
            ),
        )

    def _load_database_config(self) -> DatabaseConfig:
        url = self._require_env("DATABASE_URL")
        echo_raw = os.getenv("DB_ECHO", "false").strip().lower()
        echo = echo_raw in {"1", "true", "yes", "on"}
        return DatabaseConfig(url=url, echo=echo)

    def _load_logging_config(self) -> LoggingConfig:
        level_name = os.getenv("LOG_LEVEL", "WARNING").strip().upper()
        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        level = level_mapping.get(level_name, logging.WARNING)
        resolved_name = level_name if level_name in level_mapping else "WARNING"
        return LoggingConfig(level_name=resolved_name, level=level)

    @staticmethod
    def _require_env(var_name: str) -> str:
        value = os.getenv(var_name)
        if value is None or value.strip() == "":
            raise ValueError(f"Environment variable {var_name} is required")
        return value.strip()

    @staticmethod
    def get_instance() -> "Config":
        if Config.instance is None:
            Config.instance = Config()
        return Config.instance

    @staticmethod
    def initialize() -> None:
        Config.get_instance()

    def get_logging_level(self) -> int:
        return self.logging.level
