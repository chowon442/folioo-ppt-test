from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_project_root() -> Path:
    """app/config.py 기준 저장소 루트(일반적으로 slide_templates/, app/ 가 함께 있는 디렉터리)."""
    return _PROJECT_ROOT


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    llm_model: str = "anthropic/claude-sonnet-4"
    max_slides: int = 10
    max_input_length: int = 5000
    store_ttl_seconds: int = 3600
    store_max_items: int = 100
    browser_concurrency: int = 3
    log_input_preview_chars: int = 120

    base_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT)
    slide_templates_dir: Path = Field(
        default_factory=lambda: _PROJECT_ROOT / "slide_templates"
    )

    @field_validator("slide_templates_dir", mode="before")
    @classmethod
    def _slide_templates_not_empty(cls, v):
        """빈 문자열·잘못된 .env 값이면 프로젝트 기본 경로 사용."""
        if v is None:
            return _PROJECT_ROOT / "slide_templates"
        if isinstance(v, str) and not v.strip():
            return _PROJECT_ROOT / "slide_templates"
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
