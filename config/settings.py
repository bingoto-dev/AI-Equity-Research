"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnthropicSettings(BaseSettings):
    """Anthropic API settings."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_")

    api_key: SecretStr = Field(..., description="Anthropic API key")
    model: str = Field(default="claude-sonnet-4-20250514", description="Model to use")
    max_tokens: int = Field(default=4096, description="Max tokens per response")
    temperature: float = Field(default=0.7, description="Temperature for generation")


class DataSourceSettings(BaseSettings):
    """Data source API settings."""

    model_config = SettingsConfigDict(env_prefix="DATA_")

    news_api_key: Optional[SecretStr] = Field(default=None, description="NewsAPI key")
    alpha_vantage_key: Optional[SecretStr] = Field(default=None, description="Alpha Vantage key")
    fred_api_key: Optional[SecretStr] = Field(default=None, description="FRED API key")
    github_token: Optional[SecretStr] = Field(default=None, description="GitHub token for higher rate limits")
    sec_user_agent: str = Field(
        default="AI-Equity-Research research@example.com",
        description="SEC EDGAR user agent",
    )


class NotificationSettings(BaseSettings):
    """Notification settings."""

    model_config = SettingsConfigDict(env_prefix="NOTIFY_")

    slack_webhook_url: Optional[SecretStr] = Field(default=None, description="Slack webhook URL")
    discord_webhook_url: Optional[SecretStr] = Field(default=None, description="Discord webhook URL")
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    email_smtp_host: str = Field(default="smtp.gmail.com", description="SMTP host")
    email_smtp_port: int = Field(default=587, description="SMTP port")
    email_username: Optional[str] = Field(default=None, description="SMTP username")
    email_password: Optional[SecretStr] = Field(default=None, description="SMTP password")
    email_from: Optional[str] = Field(default=None, description="From email address")
    email_to: Optional[str] = Field(default=None, description="To email address")


class SchedulerSettings(BaseSettings):
    """Scheduler settings."""

    model_config = SettingsConfigDict(env_prefix="SCHEDULER_")

    cron_expression: str = Field(
        default="0 6 * * 1-5",
        description="Cron expression for scheduling (default: 6 AM weekdays)",
    )
    timezone: str = Field(default="America/New_York", description="Timezone for scheduler")


class LoopSettings(BaseSettings):
    """Convergence loop settings."""

    model_config = SettingsConfigDict(env_prefix="LOOP_")

    max_iterations: int = Field(default=5, description="Maximum loop iterations")
    convergence_threshold: float = Field(
        default=0.05,
        description="Score change threshold for convergence",
    )
    perfect_match_loops: int = Field(
        default=2,
        description="Consecutive loops needed for perfect match convergence",
    )
    set_stability_loops: int = Field(
        default=3,
        description="Consecutive loops needed for set stability convergence",
    )


class HierarchicalSettings(BaseSettings):
    """Hierarchical agent flow settings."""

    model_config = SettingsConfigDict(env_prefix="HIERARCHICAL_")

    enabled: bool = Field(default=True, description="Enable hierarchical worker pattern")
    max_cycles: int = Field(default=10, description="Maximum evaluation cycles")
    max_parallel_workers: int = Field(default=10, description="Max parallel worker agents")
    quality_threshold: float = Field(default=0.8, description="Quality score threshold")


class DatabaseSettings(BaseSettings):
    """Database settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    path: Path = Field(
        default=Path("data/research_history.db"),
        description="SQLite database path",
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Environment mode",
    )
    debug: bool = Field(default=False, description="Debug mode")

    # Sub-settings
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    data_sources: DataSourceSettings = Field(default_factory=DataSourceSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    loop: LoopSettings = Field(default_factory=LoopSettings)
    hierarchical: HierarchicalSettings = Field(default_factory=HierarchicalSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # Paths
    prompts_path: Path = Field(
        default=Path("config/agent_prompts.yaml"),
        description="Path to agent prompts YAML",
    )
    reports_dir: Path = Field(
        default=Path("data/reports"),
        description="Directory for generated reports",
    )
    templates_dir: Path = Field(
        default=Path("src/reports/templates"),
        description="Directory for report templates",
    )


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
