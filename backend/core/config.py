import json
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import structlog

log = structlog.get_logger()


class Settings(BaseSettings):
    # Gemini
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    llm_model: str = Field(default="gemini-3-flash-preview", env="LLM_MODEL")
    vision_model: str = Field(default="gemini-3-flash-preview", env="VISION_MODEL")
    embedding_model: str = Field(default="gemini-embedding-001", env="EMBEDDING_MODEL")

    # Vector Store
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    qdrant_collection_name: str = Field(
        default="kyc_regulatory_corpus", env="QDRANT_COLLECTION_NAME"
    )
    qdrant_api_key: str | None = Field(default=None, env="QDRANT_API_KEY")

    # App
    app_env: str = Field(default="development", env="APP_ENV")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Risk thresholds
    identity_confidence_threshold: float = Field(
        default=0.75, env="IDENTITY_CONFIDENCE_THRESHOLD"
    )
    document_validity_threshold: float = Field(
        default=0.80, env="DOCUMENT_VALIDITY_THRESHOLD"
    )

    # FATF country list
    fatf_country_list_path: Path = Field(
        default=Path("data/fatf_high_risk_countries.json"),
        env="FATF_COUNTRY_LIST_PATH",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False

    def load_fatf_countries(self) -> dict[str, set[str]]:
        """
        Load FATF high-risk country lists from the JSON file.
        Returns dict with 'blacklist' and 'greylist' as sets of ISO alpha-3 codes.
        """
        path = self.fatf_country_list_path

        if not path.exists():
            raise FileNotFoundError(
                f"FATF country list not found at '{path}'. "
                f"Ensure data/fatf_high_risk_countries.json exists."
            )

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse FATF country list at '{path}': {e}") from e

        for required_key in ("blacklist", "greylist"):
            if required_key not in data:
                raise ValueError(
                    f"FATF country list JSON is missing required key: '{required_key}'"
                )

        log.info(
            "fatf_countries_loaded",
            path=str(path),
            blacklist_count=len(data["blacklist"]),
            greylist_count=len(data["greylist"]),
            last_updated=data.get("last_updated", "unknown"),
        )

        return {
            "blacklist": set(data["blacklist"]),
            "greylist": set(data["greylist"]),
        }


settings = Settings()