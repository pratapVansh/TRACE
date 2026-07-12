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

    # Security
    security_headers_hsts_enabled: bool = False  # Enable only in production

    # Rate limiting
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 60
    upload_rate_limit_max: int = 20
    upload_rate_limit_window_seconds: int = 60
    global_rate_limit_enabled: bool = True

    # Chunking & Embeddings (Milestone 6+)
    chunk_size: int = 512
    chunk_overlap: int = 64
    chunk_min_size: int = 50
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    embedding_retry_attempts: int = 3

    # Background document processing queue
    processing_queue_worker_enabled: bool = True
    processing_queue_poll_interval_seconds: float = 2.0
    processing_queue_batch_size: int = 5
    processing_queue_max_retries: int = 3

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
