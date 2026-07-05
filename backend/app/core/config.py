from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "TRACE Backend"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://trace:trace@localhost:5432/trace"
    database_url_sync: str = "postgresql+psycopg2://trace:trace@localhost:5432/trace"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:3000"

    # JWT (Milestone 2+)
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Document storage (Milestone 4+)
    storage_backend: str = "local"
    storage_root: str = "./storage"
    max_upload_size_mb: int = 100
    allowed_upload_extensions: str = "pdf,docx,pptx,xlsx,txt,png,jpg,jpeg"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]

    @property
    def storage_root_path(self) -> Path:
        root = Path(self.storage_root)
        if not root.is_absolute():
            root = BACKEND_DIR / root
        return root.resolve()

    @property
    def allowed_upload_extensions_set(self) -> frozenset[str]:
        return frozenset(
            extension.strip().lower()
            for extension in self.allowed_upload_extensions.split(",")
            if extension.strip()
        )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
