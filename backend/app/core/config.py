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

    # Refresh-token cookie.
    # The long-lived refresh token is delivered as an httpOnly cookie so it is
    # unreadable from JavaScript (XSS cannot exfiltrate it). Scoped to the auth
    # routes so it is not attached to ordinary API calls.
    refresh_cookie_name: str = "trace_refresh_token"
    refresh_cookie_path: str = "/api/auth"
    # Must be True whenever the API is served over HTTPS.
    refresh_cookie_secure: bool = False
    # "lax" blocks cross-site POSTs (our CSRF defence for /auth/refresh).
    # A frontend on a different registrable domain needs "none" + secure=True.
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str = ""

    # Document storage (Milestone 4+)
    storage_backend: str = "local"
    storage_root: str = "./storage"
    max_upload_size_mb: int = 100
    allowed_upload_extensions: str = "pdf,docx,pptx,xlsx,txt,png,jpg,jpeg"

    # OCR (Tesseract)
    # tesseract_cmd: absolute path to the tesseract binary. Leave empty to rely
    # on PATH. Windows installs land outside PATH by default, e.g.
    #   C:/Program Files/Tesseract-OCR/tesseract.exe
    tesseract_cmd: str = ""
    # Language(s) passed to Tesseract. Multiple langs are joined with "+"
    # (e.g. "eng+deu"); the traineddata for each must be installed.
    ocr_language: str = "eng"
    # Render resolution for OCR of scanned PDF pages. Tesseract is trained on
    # ~300 DPI; lower values measurably reduce accuracy on small type.
    ocr_render_dpi: int = 300
    # Mean word confidence (0-1) below which an extraction is flagged as
    # low-quality in document metadata rather than silently trusted.
    ocr_min_confidence: float = 0.5
    # Ceiling on how many pages of one scanned PDF are OCR'd.
    #
    # OCR is by far the most expensive step in ingestion and the queue drains
    # serially on a single worker, so without a bound one document stalls every
    # other one behind it. Measured 17 September 2026 on
    # `SCN-003_Hot_Work_Permit_and_Gas_Test_Record.pdf` at the configured
    # 300 DPI: **9.4 s per page end to end** — ~1.2 s preprocessing (92% of it
    # `fastNlMeansDenoising`) and the rest Tesseract. At that rate 100 pages is
    # roughly 16 minutes and 500 pages roughly 78.
    #
    # Uploads are capped at 100 MB, which comfortably admits a 500-page scan,
    # so the ceiling is what keeps the worst case survivable. Pages past it are
    # not read: the document still indexes, and the result is flagged
    # `ocr_truncated` rather than passed off as complete.
    #
    # Nothing in the current corpus is affected — its only OCR'd document is
    # 3 pages, and the 177-page document is a .docx, which never reaches OCR.
    ocr_max_pages: int = 100

    # Security
    security_headers_hsts_enabled: bool = False  # Enable only in production

    # /api/demo/* exists to show RBAC working in a walkthrough. It is not part
    # of the product surface, so it stays out of the route table unless a demo
    # explicitly asks for it.
    demo_routes_enabled: bool = False

    # Rate limiting
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 60
    upload_rate_limit_max: int = 20
    upload_rate_limit_window_seconds: int = 60
    chat_rate_limit_max: int = 10
    chat_rate_limit_window_seconds: int = 60
    search_rate_limit_max: int = 30
    search_rate_limit_window_seconds: int = 60
    rag_rate_limit_max: int = 10
    rag_rate_limit_window_seconds: int = 60
    global_rate_limit_enabled: bool = True

    # Chunking & Embeddings (Milestone 6+)
    #
    # Passage scale, not document scale. The reranker
    # (``cross-encoder/ms-marco-MiniLM-L-6-v2``) is trained on MS MARCO
    # passages; handed a whole document it scores poorly even when the answer
    # is in there, because most of the text is unrelated to the query and every
    # document opens with the same letterhead.
    #
    # Measured over the probe corpus by scoring candidate sizes with the real
    # cross-encoder (see backend/eval/probe_results.md). Going 512 -> 256:
    # retrieval hits 8/9 -> 9/9, the top score for the no-answer control drops
    # 0.0049 -> 0.0015, and the tag questions improve markedly (T3 0.70 -> 0.95,
    # T1 0.21 -> 0.30). 128 scored higher still on this corpus but fragmented
    # the context two questions needed, and part of that gain is the known
    # short-passage bias of ms-marco rather than better relevance — revisit
    # once the corpus contains genuinely long documents.
    chunk_size: int = 256
    chunk_overlap: int = 40
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
    # Output ceiling for one answer. On a reasoning model this covers the
    # reasoning *and* the visible answer, and `gpt-oss-120b` spends it on
    # reasoning first — so a hard question can exhaust the budget before
    # emitting a single visible token and the user gets a blank answer.
    # Measured in Stage 5: 3 of 200 generations came back empty.
    #
    # The ceiling stays at 1024 and the retry below is what handles the rare
    # case. Raising the base would spend more on all 200 generations to fix 3,
    # and it would change every prompt's cache key in the evaluation harness,
    # forcing a full re-run for no measured gain. See `_generate_answer`.
    llm_answer_max_tokens: int = 1024
    llm_answer_retry_max_tokens: int = 3072

    # Retrieval (Milestone 8.1)
    retrieval_top_k: int = 15
    # Off by default: retrieval rank-limits rather than score-filters.
    #
    # The cross-encoder score is a good *ordering* signal and a poor *absolute*
    # one, so no cut point separates hits from misses. Measured over the 10-query
    # probe in ``backend/eval/probe_results.md``: correct rank-1 answers scored
    # 0.0001 to 0.6998, while the top result for a question about equipment that
    # exists in no document scored 0.0049 — above two of the correct answers.
    # Any threshold that rejected that miss also discarded real hits, and the
    # previous default of 0.25 returned an empty list for 9 of 10 questions.
    # Callers who want a floor can still pass ``similarity_threshold``.
    retrieval_similarity_threshold: float = 0.0
    retrieval_dedup_documents: bool = True
    # Passages kept per document when deduplicating. ``retrieval_top_k`` counts
    # documents, so this widens how much of each source the model sees without
    # costing a source its slot.
    #
    # Measured on the 35 answerable Stage 5 questions: the expected evidence
    # reached the reranked candidate pool for 95.7% of them but only 61.4% of it
    # survived into the LLM context, because one chunk is roughly one fifth of a
    # document at 256 tokens. Two chunks per document recovers evidence-in-context
    # to 86.2% — the same figure the 512-token ablation reached, by the same
    # mechanism — with doc recall@5 and MRR unchanged.
    retrieval_chunks_per_document: int = 2

    # Reranking.
    # Bi-encoder retrieval scores a query and a chunk independently, so it
    # ranks on rough topical similarity. A cross-encoder reads the pair
    # together and is markedly better at telling a chunk that answers the
    # question from one that merely shares its vocabulary.
    rerank_enabled: bool = True
    rerank_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Candidates pulled from the vector store before reranking. Reranking can
    # only reorder what retrieval already found, so the fetch must be wider
    # than the final cut.
    rerank_candidate_multiplier: int = 4
    rerank_max_candidates: int = 60
    # Budget for one scoring call. Reranking is a quality improvement, not a
    # correctness requirement, so exceeding this drops back to retrieval
    # order rather than making the user wait.
    rerank_timeout_seconds: float = 10.0

    # Graph arm of hybrid retrieval.
    # Stage 5 measured the graph contributing nothing to answers: across the 40
    # golden questions, 55% of the entity slots went to ``Document`` entities
    # (only 18% of the graph) and 80% of the facts reaching the prompt were
    # either a bare entity name or a document-membership edge — "this file
    # mentions this tag", which the retrieved chunk already shows. Both are
    # artefacts of ranking entities by how many query terms their *name*
    # contains: a filename like ``MNT-001_Quarterly_PM_Cooling_Tower`` matches
    # more terms than a tag like ``P-101`` simply by being longer.
    #
    # With this on, the graph arm ranks candidates by term coverage relative to
    # the name's own length and prefers domain entities over documents, and only
    # facts that actually carry a relationship count toward the merge boost.
    # Off by default so the frozen Stage 5 baseline stays reproducible; the
    # ``graph_v2`` eval config turns it on.
    graph_prefer_domain_entities: bool = False
    # Entity types that restate what the vector arm already retrieved.
    graph_deprioritized_entity_types: tuple[str, ...] = ("Document",)
    # Relationship types that only say a document mentions an entity.
    graph_membership_relationships: tuple[str, ...] = (
        "REFERENCES", "MAINTAINED_BY", "DESCRIBES", "INSPECTS",
    )
    # Candidates pulled before the graph arm re-ranks them, as a multiple of
    # the requested top_k. The re-ranking can only reorder what was fetched.
    graph_candidate_multiplier: int = 6

    # Provenance of a relationship fact: the relationship's own
    # ``source_document`` rather than the neighbour node's.
    #
    # Entity nodes are shared across documents (MERGE on a type+name hash) and
    # their ``source_document`` is COALESCEd to whichever document wrote them
    # first, so it names an arbitrary document rather than the one the fact
    # came from. Relationships carry their own ``source_document`` and the
    # batch neighbour query already returns it. Measured against the live
    # graph on 17 September 2026: the neighbour node's value disagrees with
    # the relationship's own on **63 of 87 relationships (72.4%)**.
    #
    # This is not cosmetic. ``ContextMerger`` keys ``doc_facts_map`` on the
    # fact's ``source_document``, so it decides which chunk a fact attaches to
    # (and therefore the graph boost), and ``_graph_only_item`` turns an
    # uncovered document name into a context item that can be cited — a
    # citation naming a document the fact did not come from.
    #
    # Off by default: it changes which facts attach to which chunk, so
    # enabling it would move the frozen Stage 5 baseline. It is gated exactly
    # like ``graph_prefer_domain_entities`` and promoted on the same terms —
    # measured at retrieval level, and at answer level before it ships.
    graph_fact_relationship_provenance: bool = False

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

    # Background document processing queue.
    #
    # ⚠ Single-process only. ``main.py`` starts one worker task per process and
    # ``list_pending_ingestion_jobs`` is a plain SELECT — no ``FOR UPDATE
    # SKIP LOCKED``, no atomic status claim — so two processes polling the same
    # queue both select the same pending jobs and ingest each document twice:
    # duplicate chunks, duplicate embeddings, duplicate graph writes.
    #
    # Nothing enforces the single process. It holds today only because the
    # container runs ``uvicorn app.main:app`` with no ``--workers`` flag, which
    # defaults to 1. Adding ``--workers N`` for request throughput would
    # silently enable the double-ingestion path. Before scaling out, either set
    # this to False on every replica but one, or give the queue a real claim
    # protocol.
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
