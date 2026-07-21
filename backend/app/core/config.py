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
    database_url: str = ""
    database_url_sync: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:3000"

    # JWT (Milestone 2+)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Document storage (Milestone 4+)
    storage_backend: str = "local"
    storage_root: str = "./storage"
    max_upload_size_mb: int = 100
    allowed_upload_extensions: str = "pdf,docx,pptx,xlsx,txt,png,jpg,jpeg"

    # Cloudinary (alternative to local storage)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "trace_documents"
    cloudinary_upload_preset: str = "trueTone-uploads"
    cloudinary_image_quality: str = "auto"
    cloudinary_image_format: str = "auto"

    # Security
    security_headers_hsts_enabled: bool = False  # Enable only in production

    # Rate limiting
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 60
    upload_rate_limit_max: int = 300
    upload_rate_limit_window_seconds: int = 60
    chat_rate_limit_max: int = 10
    chat_rate_limit_window_seconds: int = 60
    search_rate_limit_max: int = 30
    search_rate_limit_window_seconds: int = 60
    rag_rate_limit_max: int = 10
    rag_rate_limit_window_seconds: int = 60
    global_rate_limit_enabled: bool = True
    global_rate_limit_max: int = 500
    global_rate_limit_window_seconds: int = 60

    # Chunking & Embeddings (Milestone 6+)
    chunk_size: int = 512
    chunk_overlap: int = 64
    chunk_min_size: int = 50
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    embedding_retry_attempts: int = 3

    # Qdrant vector store (Milestone 7+)
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "document_chunks"
    qdrant_timeout_seconds: int = 30
    qdrant_max_retries: int = 3

    # Ranking weights (Milestone 7.6)
    ranking_semantic_weight: float = 0.35
    ranking_keyword_weight: float = 0.30
    ranking_metadata_weight: float = 0.20
    ranking_freshness_weight: float = 0.15
    ranking_freshness_decay_days: int = 365

    # LLM / AI Copilot (Milestone 8)
    groq_api_key: str = ""
    llm_provider: str = "groq"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: int = 60
    groq_max_retries: int = 3

    # Retrieval (Milestone 8.1)
    retrieval_top_k: int = 15
    retrieval_similarity_threshold: float = 0.25
    retrieval_dedup_documents: bool = True

    # Neo4j graph store (Milestone 9)
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""
    neo4j_database: str = ""
    neo4j_connection_timeout_seconds: int = 30
    neo4j_max_connection_lifetime_seconds: int = 3600

    # Observability — OpenTelemetry (optional)
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""

    # Filesystem workspace sandbox
    workspace_root: str = ""

    @property
    def workspace_root_path(self) -> Path:
        root = Path(self.workspace_root) if self.workspace_root else (ROOT_DIR / "workspace")
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

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


    @property
    def get_database_url(self) -> str:
        from app.core.vault import vault_client
        return vault_client.get_secret("database/creds/trace", "url", self.database_url)

    @property
    def get_jwt_secret_key(self) -> str:
        from app.core.vault import vault_client
        return vault_client.get_secret("secret/data/trace", "jwt_secret_key", self.jwt_secret_key)

settings = Settings()
