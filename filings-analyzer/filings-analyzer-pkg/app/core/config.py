from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / ..env file."""

    model_config = SettingsConfigDict(env_file="..env", extra="ignore")

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/filings"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"  # used to sign JWTs
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # LLM
    # Which backend to use: "ollama" (local, free) or "anthropic" (hosted).
    llm_provider: str = "ollama"

    # Anthropic settings (used when llm_provider == "anthropic")
    anthropic_api_key: str = ""
    # Pinned to a versioned model string (not an alias) so behavior is stable.
    # Verify the current list at docs.claude.com before deploying.
    anthropic_model: str = "claude-sonnet-4-6"

    # Ollama settings (used when llm_provider == "ollama")
    # Ollama exposes an OpenAI-compatible API at this base URL by default.
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"

    # Uploads
    upload_dir: str = "uploads"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB


settings = Settings()
