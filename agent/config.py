"""Configuration loader for Evo Garden agent."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = Field(default="openrouter")
    model: str = Field(default="google/gemini-2.0-flash-001")
    api_key: str = Field(default="")
    api_url: str = Field(default="https://openrouter.ai/api/v1")

    def get_api_key(self) -> str:
        """Get API key from config, env var, or raise."""
        return self.api_key or os.environ.get("LLM_API_KEY", "")


class ProjectConfig(BaseModel):
    goals_file: str = Field(default="GOALS.md")
    max_tokens_per_run: int = Field(default=8000)
    max_cost_per_run: float = Field(default=2.00)
    test_command: str = Field(default="python -m pytest -x")


class EvolutionConfig(BaseModel):
    mode: str = Field(default="vps")
    schedule: str = Field(default="every_2h")
    max_tasks_per_run: int = Field(default=3)
    rollback_on_fail: bool = Field(default=True)


class WebConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=3000)
    sse_port: int = Field(default=8080)


class GitLawbConfig(BaseModel):
    url: str = Field(default="https://gitlawb.com")
    project: str = Field(default="username/evo-garden")
    default_branch: str = Field(default="main")
    author_name: str = Field(default="Evo Garden Agent")
    author_email: str = Field(default="agent@evo-garden.local")
    token: str = Field(default="")

    def get_token(self) -> str:
        return self.token or os.environ.get("GITLAWB_TOKEN", "")


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    gitlawb: GitLawbConfig = Field(default_factory=GitLawbConfig)


def load_config(config_path: Optional[str] = None) -> Config:
    """Load config from YAML file, fallback to defaults."""
    if config_path is None:
        config_path = os.environ.get("EVO_CONFIG", "config.yaml")

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        return Config(**raw)

    # Return defaults without config file
    return Config()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config
